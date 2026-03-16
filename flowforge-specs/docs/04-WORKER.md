# 04 - Stateless Worker Specification

## Overview

Workers are stateless Python processes that consume messages from Redis Streams,
execute compiled LangGraph workflows, and persist results to PostgreSQL.

## Process Lifecycle

```
Worker starts
  -> Connect to Redis, PostgreSQL, Qdrant
  -> Join consumer group "flowforge-workers"
  -> Enter consume loop:
       1. XREADGROUP from stream (block 5s)
       2. Receive message envelope
       3. Acquire session lock (Redis SET NX EX 120)
          - If lock fails: NACK message, retry after 2s backoff
       4. Load session state from PostgreSQL
       5. Load compiled graph from Redis cache
          - Cache miss: load YAML from PostgreSQL, compile, cache
       6. Execute graph with session state
       7. Save updated session state to PostgreSQL
       8. Write audit log entries (execution + execution_steps)
       9. XACK message
      10. Release lock (DEL key via Lua script)
      11. Loop back to step 1
```

## Module: consumer.py

```python
import asyncio
import os
from uuid import uuid4
import redis.asyncio as redis

class StreamConsumer:
    def __init__(self, settings):
        self.redis = redis.from_url(settings.redis_url)
        self.group = "flowforge-workers"
        self.consumer_id = f"worker-{os.getpid()}-{uuid4().hex[:8]}"
        self.stream_key = "flowforge:messages"
        self.message_count = 0

    async def setup(self):
        try:
            await self.redis.xgroup_create(
                self.stream_key, self.group, id="0", mkstream=True
            )
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
                    except RetryLater:
                        # Message will be re-delivered after visibility timeout
                        pass
                    except Exception as e:
                        await self.handle_failure(msg_id, data, e)

    async def process_message(self, data: dict):
        envelope = MessageEnvelope.parse(data)
        async with SessionLock(self.redis, envelope.session_id, ttl=120) as lock:
            if not lock.acquired:
                raise RetryLater("Session locked by another worker")

            session = await SessionManager.load(envelope.session_id)
            graph = await GraphCache.get_or_compile(
                self.redis, envelope.workflow_slug, envelope.tenant_id
            )
            result = await Executor.run(graph, session, envelope.input_data)
            await SessionManager.save(session)
            await AuditLog.write(envelope, result)

    async def handle_failure(self, msg_id, data, error):
        # Log error, increment retry counter, DLQ after 3 retries
        retry_count = int(data.get(b"_retries", 0)) + 1
        if retry_count >= 3:
            await self.move_to_dlq(msg_id, data, error)
            await self.redis.xack(self.stream_key, self.group, msg_id)
        else:
            # Re-add with incremented retry count
            data[b"_retries"] = str(retry_count).encode()
            await self.redis.xadd(self.stream_key, data)
            await self.redis.xack(self.stream_key, self.group, msg_id)

    async def move_to_dlq(self, msg_id, data, error):
        dlq_key = f"{self.stream_key}:dlq"
        data[b"_error"] = str(error).encode()
        await self.redis.xadd(dlq_key, data)
```

## Module: lock.py

```python
from uuid import uuid4

class SessionLock:
    def __init__(self, redis_client, session_id: str, ttl: int = 120):
        self.redis = redis_client
        self.key = f"flowforge:lock:{session_id}"
        self.ttl = ttl
        self.token = uuid4().hex
        self.acquired = False

    async def __aenter__(self):
        self.acquired = await self.redis.set(
            self.key, self.token, nx=True, ex=self.ttl
        )
        return self

    async def __aexit__(self, *args):
        if self.acquired:
            # Lua script: only release if we still own the lock
            lua = (
                'if redis.call("get", KEYS[1]) == ARGV[1] then '
                '  return redis.call("del", KEYS[1]) '
                'else '
                '  return 0 '
                'end'
            )
            await self.redis.eval(lua, 1, self.key, self.token)
```

## Module: executor.py

```python
from datetime import datetime

class Executor:
    @staticmethod
    async def run(graph, session, input_data: dict) -> ExecutionResult:
        state = {**session.state, "trigger": input_data}
        config = {"configurable": {"session_id": session.id}}

        result_state = await graph.ainvoke(state, config=config)

        session.state = result_state
        session.step_count += 1
        session.updated_at = datetime.utcnow()

        return ExecutionResult(
            session_id=session.id,
            final_state=result_state,
            steps_executed=result_state.get("_audit_trail", []),
        )
```

## Module: session_manager.py

```python
from sqlalchemy import select, insert
from datetime import datetime

class SessionManager:
    @staticmethod
    async def load(session_id: str) -> Session:
        async with db_session() as db:
            row = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            model = row.scalar_one_or_none()
            if model is None:
                return Session(id=session_id, state={}, step_count=0)
            return Session(
                id=model.id,
                state=model.workflow_state,
                step_count=model.step_count,
            )

    @staticmethod
    async def save(session: Session):
        async with db_session() as db:
            await db.execute(
                insert(SessionModel)
                .values(
                    id=session.id,
                    workflow_state=session.state,
                    step_count=session.step_count,
                    updated_at=datetime.utcnow(),
                )
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "workflow_state": session.state,
                        "step_count": session.step_count,
                        "updated_at": datetime.utcnow(),
                    },
                )
            )
            await db.commit()
```

## Graph Cache

```python
import pickle

class GraphCache:
    CACHE_TTL = 300  # 5 minutes

    @staticmethod
    async def get_or_compile(redis_client, workflow_slug: str, tenant_id: str):
        cache_key = f"flowforge:graph:{tenant_id}:{workflow_slug}"
        cached = await redis_client.get(cache_key)
        if cached:
            return pickle.loads(cached)

        yaml_def = await WorkflowRepo.get_active_yaml(workflow_slug, tenant_id)
        graph = Compiler.compile(yaml_def)
        await redis_client.setex(
            cache_key, GraphCache.CACHE_TTL, pickle.dumps(graph)
        )
        return graph
```

## Dead Letter Queue (DLQ)

Messages that fail 3 times are moved to a DLQ stream (flowforge:messages:dlq).
An admin UI or API endpoint lists DLQ messages for investigation and replay.

## Health Check

Workers expose a simple HTTP health endpoint (background thread, configurable port):

```python
from aiohttp import web

async def health_handler(request):
    return web.json_response({
        "status": "healthy",
        "consumer_id": consumer.consumer_id,
        "messages_processed": consumer.message_count,
    })

# Start on port from env var HEALTH_PORT (default 8081)
```

## Scaling

Workers scale via Kubernetes HPA based on Redis Stream lag:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: flowforge-workers
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: flowforge-worker
  minReplicas: 2
  maxReplicas: 50
  metrics:
    - type: External
      external:
        metric:
          name: redis_stream_pending_messages
        target:
          type: AverageValue
          averageValue: "10"
```

## Worker Entry Point

```python
# backend/flowforge/worker/__main__.py
import asyncio
from flowforge.config import get_settings
from flowforge.worker.consumer import StreamConsumer

async def main():
    settings = get_settings()
    consumer = StreamConsumer(settings)
    await consumer.consume()

if __name__ == "__main__":
    asyncio.run(main())
```

Run: `python -m flowforge.worker`
