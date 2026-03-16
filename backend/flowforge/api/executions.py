"""Trigger + get + list executions router."""

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from flowforge.api.deps import get_tenant_id
from flowforge.config import get_settings
from flowforge.db.session import get_db
from flowforge.models import (
    Execution,
    ExecutionStep,
    Session,
    TokenUsage,
    Workflow,
    WorkflowVersion,
)

router = APIRouter(prefix="/executions", tags=["executions"])
settings = get_settings()

COST_TABLE = {
    "mistral-large-latest": {"input": 0.003, "output": 0.009},
    "default": {"input": 0.003, "output": 0.009},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "azure-fallback": {"input": 0.005, "output": 0.015},
}


def _get_redis():
    return aioredis.from_url(settings.redis_url)


class TriggerBody(BaseModel):
    workflow_slug: str
    input_data: dict = {}
    session_id: Optional[str] = None


@router.post("/trigger", status_code=202)
async def trigger_execution(
    body: TriggerBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    tid = uuid.UUID(tenant_id)

    # Verify workflow exists
    wf_stmt = select(Workflow).where(
        Workflow.tenant_id == tid,
        Workflow.slug == body.workflow_slug,
    )
    wf = (await db.execute(wf_stmt)).scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Get active version
    version_stmt = (
        select(WorkflowVersion)
        .where(
            WorkflowVersion.workflow_id == wf.id,
            WorkflowVersion.status == "active",
        )
        .order_by(WorkflowVersion.version.desc())
        .limit(1)
    )
    wv = (await db.execute(version_stmt)).scalar_one_or_none()
    workflow_version = wv.version if wv else 1

    # Create or find session
    if body.session_id:
        session_id = uuid.UUID(body.session_id)
        session_stmt = select(Session).where(Session.id == session_id)
        session = (await db.execute(session_stmt)).scalar_one_or_none()
        if session is None:
            session = Session(
                id=session_id,
                tenant_id=tid,
                workflow_slug=body.workflow_slug,
                workflow_version=workflow_version,
                workflow_state={},
            )
            db.add(session)
            await db.flush()
    else:
        session = Session(
            tenant_id=tid,
            workflow_slug=body.workflow_slug,
            workflow_version=workflow_version,
            workflow_state={},
        )
        db.add(session)
        await db.flush()
        session_id = session.id

    # Create execution
    execution = Execution(
        tenant_id=tid,
        session_id=session_id,
        workflow_slug=body.workflow_slug,
        workflow_version=workflow_version,
        status="queued",
        input_data=body.input_data,
    )
    db.add(execution)
    await db.flush()
    execution_id = execution.id

    await db.commit()

    # Publish to Redis Stream
    redis_client = _get_redis()
    try:
        await redis_client.xadd(
            "flowforge:messages",
            {
                "session_id": str(session_id),
                "workflow_slug": body.workflow_slug,
                "tenant_id": tenant_id,
                "input_data": json.dumps(body.input_data),
                "execution_id": str(execution_id),
            },
        )
    finally:
        await redis_client.aclose()

    return {
        "execution_id": str(execution_id),
        "session_id": str(session_id),
        "status": "queued",
    }


@router.get("/{execution_id}")
async def get_execution(
    execution_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    tid = uuid.UUID(tenant_id)
    try:
        exec_uuid = uuid.UUID(execution_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid execution ID")

    stmt = select(Execution).where(
        Execution.id == exec_uuid,
        Execution.tenant_id == tid,
    )
    execution = (await db.execute(stmt)).scalar_one_or_none()
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")

    # Compute token totals from TokenUsage table
    token_rows = (
        (await db.execute(select(TokenUsage).where(TokenUsage.execution_id == exec_uuid)))
        .scalars()
        .all()
    )

    total_input = sum(t.input_tokens for t in token_rows)
    total_output = sum(t.output_tokens for t in token_rows)

    estimated_cost = sum(
        t.input_tokens / 1000 * COST_TABLE.get(t.model, COST_TABLE["default"])["input"]
        + t.output_tokens / 1000 * COST_TABLE.get(t.model, COST_TABLE["default"])["output"]
        for t in token_rows
    )

    # Order steps by started_at
    steps_stmt = (
        select(ExecutionStep)
        .where(ExecutionStep.execution_id == exec_uuid)
        .order_by(ExecutionStep.started_at.asc().nullsfirst())
    )
    steps = (await db.execute(steps_stmt)).scalars().all()

    return {
        "execution_id": str(execution.id),
        "workflow_slug": execution.workflow_slug,
        "status": execution.status,
        "queued_at": execution.queued_at.isoformat() if execution.queued_at else None,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        "duration_ms": execution.duration_ms,
        "input_data": execution.input_data,
        "output_data": execution.output_data,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "estimated_cost_usd": round(estimated_cost, 6),
        "steps": [
            {
                "step_id": s.step_id,
                "step_name": s.step_name,
                "type": s.step_type,
                "status": s.status,
                "model": s.step_metadata.get("model") if s.step_metadata else None,
                "input_tokens": s.step_metadata.get("input_tokens") if s.step_metadata else None,
                "output_tokens": s.step_metadata.get("output_tokens") if s.step_metadata else None,
                "duration_ms": s.duration_ms,
                "input": s.input_data,
                "output": s.output_data,
            }
            for s in steps
        ],
    }


@router.get("")
async def list_executions(
    workflow_slug: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    tid = uuid.UUID(tenant_id)
    stmt = select(Execution).where(Execution.tenant_id == tid)

    if workflow_slug:
        stmt = stmt.where(Execution.workflow_slug == workflow_slug)
    if status:
        stmt = stmt.where(Execution.status == status)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Execution.queued_at.desc()).offset((page - 1) * per_page).limit(per_page)
    executions = (await db.execute(stmt)).scalars().all()

    return {
        "executions": [
            {
                "execution_id": str(e.id),
                "workflow_slug": e.workflow_slug,
                "status": e.status,
                "duration_ms": e.duration_ms,
                "queued_at": e.queued_at.isoformat() if e.queued_at else None,
            }
            for e in executions
        ],
        "total": total,
        "page": page,
    }
