"""WebSocket live execution trace router."""

import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flowforge.db.session import AsyncSessionLocal
from flowforge.models import Execution, ExecutionStep

router = APIRouter(prefix="/ws", tags=["ws"])


@router.websocket("/executions/{execution_id}")
async def ws_execution_trace(websocket: WebSocket, execution_id: str):
    await websocket.accept()

    try:
        exec_uuid = uuid.UUID(execution_id)
    except ValueError:
        await websocket.send_json({"event": "error", "message": "Invalid execution ID"})
        await websocket.close()
        return

    sent_step_ids: set[str] = set()

    async with AsyncSessionLocal() as db:
        for _ in range(10):
            # Check execution status
            exec_stmt = select(Execution).where(Execution.id == exec_uuid)
            execution = (await db.execute(exec_stmt)).scalar_one_or_none()

            if execution is None:
                await websocket.send_json({"event": "error", "message": "Execution not found"})
                break

            # Send new steps
            steps_stmt = select(ExecutionStep).where(ExecutionStep.execution_id == exec_uuid)
            steps = (await db.execute(steps_stmt)).scalars().all()

            for step in steps:
                step_key = str(step.id)
                if step_key not in sent_step_ids:
                    await websocket.send_json(
                        {
                            "event": "step_completed",
                            "step_id": step.step_id,
                            "step_name": step.step_name,
                            "type": step.step_type,
                            "status": step.status,
                            "duration_ms": step.duration_ms,
                            "input": step.input_data,
                            "output": step.output_data,
                        }
                    )
                    sent_step_ids.add(step_key)

            if execution.status in ("completed", "failed"):
                await websocket.send_json(
                    {
                        "event": "execution_finished",
                        "status": execution.status,
                    }
                )
                break

            await asyncio.sleep(1)

    try:
        await websocket.close()
    except Exception:
        pass
