"""Tests for StreamConsumer — Redis Streams consumer with retry/DLQ logic."""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from flowforge.worker.consumer import MessageEnvelope, RetryLater, StreamConsumer


# ── AuditLog helpers ──────────────────────────────────────────────────────────


class FakeAsyncContextManager:
    """Async context manager wrapping a fake DB session for use with AsyncSessionLocal."""

    def __init__(self, db_session):
        self._db = db_session

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *args):
        pass


def make_mock_db():
    """Return an AsyncMock that behaves like an AsyncSession, tracking executed statements."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


# ── MessageEnvelope.parse ─────────────────────────────────────────────────────


class TestMessageEnvelopeParse:
    def test_parse_decodes_bytes_keys_and_values(self):
        """parse() should decode bytes keys/values from a Redis stream dict."""
        data = {
            b"session_id": b"sess-001",
            b"workflow_slug": b"my-workflow",
            b"tenant_id": b"tenant-xyz",
            b"input_data": b'{"prompt": "hello"}',
        }
        envelope = MessageEnvelope.parse(data)

        assert envelope.session_id == "sess-001"
        assert envelope.workflow_slug == "my-workflow"
        assert envelope.tenant_id == "tenant-xyz"
        assert envelope.input_data == {"prompt": "hello"}

    def test_parse_handles_string_keys(self):
        """parse() should also work with string keys (non-bytes)."""
        data = {
            "session_id": "sess-002",
            "workflow_slug": "wf-slug",
            "tenant_id": "t-001",
            "input_data": '{"x": 1}',
        }
        envelope = MessageEnvelope.parse(data)

        assert envelope.session_id == "sess-002"
        assert envelope.input_data == {"x": 1}

    def test_parse_input_data_invalid_json_defaults_to_empty_dict(self):
        """parse() should use empty dict for input_data when JSON is malformed."""
        data = {
            b"session_id": b"s",
            b"workflow_slug": b"wf",
            b"tenant_id": b"t",
            b"input_data": b"not-json",
        }
        envelope = MessageEnvelope.parse(data)
        assert envelope.input_data == {}

    def test_parse_missing_input_data_defaults_to_empty_dict(self):
        """parse() should use empty dict when input_data key is absent."""
        data = {
            b"session_id": b"s",
            b"workflow_slug": b"wf",
            b"tenant_id": b"t",
        }
        envelope = MessageEnvelope.parse(data)
        assert envelope.input_data == {}

    def test_parse_skips_internal_underscore_keys(self):
        """parse() should ignore keys starting with _ (retry metadata)."""
        data = {
            b"session_id": b"s",
            b"workflow_slug": b"wf",
            b"tenant_id": b"t",
            b"input_data": b"{}",
            b"_retries": b"2",
        }
        envelope = MessageEnvelope.parse(data)
        # Should not raise and should parse normally
        assert envelope.session_id == "s"


# ── handle_failure ────────────────────────────────────────────────────────────


def make_consumer():
    """Create a StreamConsumer with a mocked Redis client."""
    settings = MagicMock()
    settings.redis_url = "redis://localhost:6379"

    with patch("flowforge.worker.consumer.redis.from_url") as mock_from_url:
        mock_redis = AsyncMock()
        mock_from_url.return_value = mock_redis
        consumer = StreamConsumer(settings)
        consumer.redis = mock_redis
    return consumer


@pytest.mark.asyncio
async def test_handle_failure_increments_retry_and_readds_to_stream():
    """handle_failure should increment _retries and re-add to stream on first failure."""
    consumer = make_consumer()
    consumer.redis.xadd = AsyncMock()
    consumer.redis.xack = AsyncMock()

    data = {b"session_id": b"s", b"_retries": b"0"}
    error = ValueError("something broke")

    await consumer.handle_failure("msg-001", data, error)

    # Should re-add to stream with incremented retry count
    consumer.redis.xadd.assert_awaited_once()
    added_data = consumer.redis.xadd.call_args[0][1]
    assert added_data[b"_retries"] == b"1"

    # Should ACK the original message
    consumer.redis.xack.assert_awaited_once_with(consumer.stream_key, consumer.group, "msg-001")


@pytest.mark.asyncio
async def test_handle_failure_second_retry_increments_to_two():
    """handle_failure should set _retries=2 on second failure."""
    consumer = make_consumer()
    consumer.redis.xadd = AsyncMock()
    consumer.redis.xack = AsyncMock()

    data = {b"session_id": b"s", b"_retries": b"1"}
    error = RuntimeError("error again")

    await consumer.handle_failure("msg-002", data, error)

    added_data = consumer.redis.xadd.call_args[0][1]
    assert added_data[b"_retries"] == b"2"


@pytest.mark.asyncio
async def test_handle_failure_moves_to_dlq_after_three_retries():
    """handle_failure should move to DLQ (not retry) when retry_count reaches 3."""
    consumer = make_consumer()
    consumer.redis.xadd = AsyncMock()
    consumer.redis.xack = AsyncMock()

    # Simulate the message has already been retried twice (count will become 3)
    data = {b"session_id": b"s", b"_retries": b"2"}
    error = Exception("fatal")

    await consumer.handle_failure("msg-003", data, error)

    # Should have called xadd for DLQ
    consumer.redis.xadd.assert_awaited_once()
    dlq_key = consumer.redis.xadd.call_args[0][0]
    assert ":dlq" in dlq_key

    # Should still ACK the original
    consumer.redis.xack.assert_awaited_once_with(consumer.stream_key, consumer.group, "msg-003")


@pytest.mark.asyncio
async def test_handle_failure_dlq_includes_error_message():
    """DLQ message should include _error field with the error string."""
    consumer = make_consumer()
    consumer.redis.xadd = AsyncMock()
    consumer.redis.xack = AsyncMock()

    data = {b"session_id": b"s", b"_retries": b"2"}
    error = Exception("critical failure")

    await consumer.handle_failure("msg-004", data, error)

    dlq_data = consumer.redis.xadd.call_args[0][1]
    assert b"_error" in dlq_data
    assert b"critical failure" in dlq_data[b"_error"]


# ── RetryLater ────────────────────────────────────────────────────────────────


def test_retry_later_is_exception():
    """RetryLater should be a subclass of Exception."""
    assert issubclass(RetryLater, Exception)


def test_retry_later_can_be_raised():
    with pytest.raises(RetryLater, match="locked"):
        raise RetryLater("Session locked by another worker")


# ── AuditLog.write — token usage ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_log_writes_token_usage():
    """AuditLog.write() must insert TokenUsage rows when audit trail has token data."""
    from flowforge.worker.consumer import AuditLog, MessageEnvelope
    from flowforge.worker.executor import ExecutionResult
    from flowforge.models import TokenUsage
    from datetime import datetime, timezone
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    tenant_id = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    envelope = MessageEnvelope(
        session_id=str(uuid.uuid4()),
        workflow_slug="test-wf",
        tenant_id=tenant_id,
        input_data={},
        execution_id=execution_id,
    )
    result = ExecutionResult(
        session_id=envelope.session_id,
        final_state={},
        steps_executed=[
            {
                "step_id": "greet",
                "step_name": "Greet",
                "step_type": "agent",
                "status": "completed",
                "model": "mistral-large-latest",
                "input_tokens": 42,
                "output_tokens": 17,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": 1234,
                "input_data": {},
                "output_data": {},
            }
        ],
    )

    # Track all statements executed against the DB mock
    executed_statements = []

    db = make_mock_db()
    db.execute = AsyncMock(side_effect=lambda stmt: executed_statements.append(stmt))
    ctx = FakeAsyncContextManager(db)

    with patch("flowforge.worker.consumer.AsyncSessionLocal", return_value=ctx):
        await AuditLog.write(envelope, result, workflow_version=1)

    # Find TokenUsage insert statements among executed statements
    token_usage_inserts = []
    for stmt in executed_statements:
        # pg_insert statements have a 'table' attribute; match by table name
        if hasattr(stmt, "table") and stmt.table.name == TokenUsage.__table__.name:
            token_usage_inserts.append(stmt)

    assert len(token_usage_inserts) == 1, (
        f"Expected 1 TokenUsage insert, got {len(token_usage_inserts)}"
    )

    # Inspect the values compiled into the INSERT statement
    insert_values = token_usage_inserts[0].compile(compile_kwargs={"literal_binds": True})
    insert_str = str(insert_values)
    assert "42" in insert_str, f"Expected input_tokens=42 in INSERT, got: {insert_str}"
    assert "17" in insert_str, f"Expected output_tokens=17 in INSERT, got: {insert_str}"
    assert "mistral-large-latest" in insert_str, f"Expected model in INSERT, got: {insert_str}"
