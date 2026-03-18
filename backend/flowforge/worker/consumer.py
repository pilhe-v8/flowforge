import json
import logging
import os
import time
import uuid
from datetime import datetime
from dataclasses import dataclass
from datetime import datetime, timezone

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from flowforge.db.session import AsyncSessionLocal
from flowforge.models import Execution as ExecutionModel, ExecutionStep, TokenUsage
from flowforge.worker.lock import SessionLock
from flowforge.worker.executor import Executor
from flowforge.worker.session_manager import SessionManager
from flowforge.worker.graph_cache import GraphCache

logger = logging.getLogger(__name__)


class RetryLater(Exception):
    """Signal to skip ACK so the message will be re-delivered."""


@dataclass
class MessageEnvelope:
    """Parsed message from the Redis stream."""

    session_id: str
    workflow_slug: str
    tenant_id: str
    input_data: dict
    execution_id: str | None = None

    @classmethod
    def parse(cls, data: dict) -> "MessageEnvelope":
        """Decode bytes keys/values from a Redis stream message dict."""

        def _decode(v):
            if isinstance(v, bytes):
                return v.decode()
            return v

        decoded = {
            _decode(k): _decode(v)
            for k, v in data.items()
            if not (k.startswith(b"_") if isinstance(k, bytes) else k.startswith("_"))
        }
        # input_data may be a JSON-encoded field; if missing, use empty dict
        raw_input = data.get(b"input_data", data.get("input_data", "{}"))
        if isinstance(raw_input, bytes):
            raw_input = raw_input.decode()
        try:
            input_data = json.loads(raw_input)
        except (json.JSONDecodeError, TypeError):
            input_data = {}

        return cls(
            session_id=decoded.get("session_id", ""),
            workflow_slug=decoded.get("workflow_slug", ""),
            tenant_id=decoded.get("tenant_id", ""),
            input_data=input_data,
            execution_id=decoded.get("execution_id"),
        )


class AuditLog:
    """Writes execution audit records to PostgreSQL."""

    @staticmethod
    def _coerce_dt(value: object) -> datetime | None:
        """Coerce ISO-8601 string timestamps to datetime for asyncpg.

        The executor records timestamps as ISO strings; asyncpg requires actual
        datetime objects for TIMESTAMP/TIMESTAMPTZ columns.
        """

        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    async def write(envelope: MessageEnvelope, result, workflow_version: int = 0) -> None:
        # Validate tenant_id early — bail out loudly rather than crash mid-write
        try:
            tenant_uuid = uuid.UUID(envelope.tenant_id)
        except (ValueError, AttributeError) as e:
            logger.error("Invalid tenant_id in envelope: %s — %s", envelope.tenant_id, e)
            return

        async with AsyncSessionLocal() as db:
            # Use the execution_id from the envelope so we UPDATE the existing
            # "queued" row that the API already inserted, rather than creating
            # a new orphan row.
            if envelope.execution_id:
                execution_id = uuid.UUID(envelope.execution_id)
            else:
                execution_id = uuid.uuid4()

            now = datetime.now(timezone.utc)

            # Compute timing from the audit trail (single pass)
            starts = []
            ends = []

            # Single loop: write ExecutionStep + TokenUsage rows together
            for step_entry in result.steps_executed:
                if not isinstance(step_entry, dict):
                    continue

                started_at_dt = AuditLog._coerce_dt(step_entry.get("started_at"))
                completed_at_dt = AuditLog._coerce_dt(step_entry.get("completed_at"))

                # Collect timing data
                if started_at_dt is not None:
                    starts.append(started_at_dt)
                if completed_at_dt is not None:
                    ends.append(completed_at_dt)

                # Build step_metadata, omitting keys whose values are None
                raw_meta = {
                    "model": step_entry.get("model"),
                    "input_tokens": step_entry.get("input_tokens"),
                    "output_tokens": step_entry.get("output_tokens"),
                }
                step_metadata = {k: v for k, v in raw_meta.items() if v is not None} or None

                # Write ExecutionStep row
                step_stmt = pg_insert(ExecutionStep).values(
                    id=uuid.uuid4(),
                    execution_id=execution_id,
                    step_id=step_entry.get("step_id", "unknown"),
                    step_name=step_entry.get("step_name", step_entry.get("step_id", "unknown")),
                    step_type=step_entry.get("step_type", "unknown"),
                    status=step_entry.get("status", "completed"),
                    input_data=step_entry.get("input"),
                    output_data=step_entry.get("output"),
                    started_at=started_at_dt,
                    completed_at=completed_at_dt,
                    duration_ms=step_entry.get("duration_ms"),
                    step_metadata=step_metadata,
                )
                await db.execute(step_stmt)

                # Write TokenUsage row when token data is present
                input_tokens = step_entry.get("input_tokens")
                output_tokens = step_entry.get("output_tokens")
                if input_tokens is not None and output_tokens is not None:
                    await db.execute(
                        pg_insert(TokenUsage).values(
                            id=uuid.uuid4(),
                            tenant_id=tenant_uuid,
                            execution_id=execution_id,
                            step_id=step_entry.get("step_id", "unknown"),
                            model=step_entry.get("model", "unknown"),
                            input_tokens=int(input_tokens),
                            output_tokens=int(output_tokens),
                            cost_usd=None,
                        )
                    )

            # Compute timing values (None when no step timing data available)
            started_at: datetime | None = None
            completed_at: datetime | None = now
            duration_ms: int | None = None
            if starts and ends:
                t0 = min(starts)
                t1 = max(ends)
                started_at = t0
                completed_at = t1
                duration_ms = int((t1 - t0).total_seconds() * 1000)

            # Single Execution upsert — covers both the timing and status in one round-trip
            exec_insert = pg_insert(ExecutionModel).values(
                id=execution_id,
                tenant_id=tenant_uuid,
                session_id=envelope.session_id,
                workflow_slug=envelope.workflow_slug,
                workflow_version=workflow_version,
                status="completed",
                input_data=envelope.input_data,
                output_data=result.final_state,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
            )
            exec_stmt = exec_insert.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "status": exec_insert.excluded.status,
                    "output_data": exec_insert.excluded.output_data,
                    "started_at": exec_insert.excluded.started_at,
                    "completed_at": exec_insert.excluded.completed_at,
                    "duration_ms": exec_insert.excluded.duration_ms,
                },
            )
            await db.execute(exec_stmt)

            await db.commit()


class StreamConsumer:
    """Consumes messages from a Redis Stream and executes workflow graphs."""

    def __init__(self, settings):
        self.redis = redis.from_url(settings.redis_url)
        self.group = "flowforge-workers"
        self.consumer_id = f"worker-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self.stream_key = "flowforge:messages"
        self.message_count = 0
        self.last_processed_at: float = time.monotonic()

    async def setup(self):
        try:
            await self.redis.xgroup_create(self.stream_key, self.group, id="0", mkstream=True)
        except redis.ResponseError:
            pass  # Group already exists

    async def consume(self):
        await self.setup()
        while True:
            messages = await self.redis.xreadgroup(
                groupname=self.group,
                consumername=self.consumer_id,
                streams={self.stream_key: ">"},
                count=1,
                block=5000,
            )
            if not messages:
                continue

            for stream, msg_list in messages:
                for msg_id, data in msg_list:
                    try:
                        await self.process_message(data)
                        await self.redis.xack(self.stream_key, self.group, msg_id)
                        self.message_count += 1
                        self.last_processed_at = time.monotonic()
                    except RetryLater as e:
                        logger.warning("RetryLater for message: %s", e)
                        pass
                    except Exception as e:
                        await self.handle_failure(msg_id, data, e)

    async def process_message(self, data: dict):
        envelope = MessageEnvelope.parse(data)
        async with SessionLock(self.redis, envelope.session_id, ttl=120) as lock:
            if not lock.acquired:
                raise RetryLater("Session locked by another worker")

            session = await SessionManager.load(
                envelope.session_id,
                tenant_id=envelope.tenant_id,
                workflow_slug=envelope.workflow_slug,
            )
            graph, workflow_version = await GraphCache.get_or_compile(
                self.redis, envelope.workflow_slug, envelope.tenant_id
            )
            result = await Executor.run(graph, session, envelope.input_data)
            await SessionManager.save(session)
            await AuditLog.write(envelope, result, workflow_version=workflow_version)

    async def handle_failure(self, msg_id, data, error):
        retry_count = int(data.get(b"_retries", 0)) + 1
        logger.error("Message processing failed (retry %d): %s", retry_count, error, exc_info=True)
        if retry_count >= 3:
            await self.move_to_dlq(msg_id, data, error)
            await self.redis.xack(self.stream_key, self.group, msg_id)
        else:
            data[b"_retries"] = str(retry_count).encode()
            await self.redis.xadd(self.stream_key, data)
            await self.redis.xack(self.stream_key, self.group, msg_id)

    async def move_to_dlq(self, msg_id, data, error):
        dlq_key = f"{self.stream_key}:dlq"
        data[b"_error"] = str(error).encode()
        await self.redis.xadd(dlq_key, data)
