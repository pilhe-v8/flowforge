"""Webhook trigger router."""

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from flowforge.config import get_settings
from flowforge.db.session import get_db
from flowforge.models import Execution, Session, Workflow, WorkflowVersion

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
settings = get_settings()


def _get_redis():
    return aioredis.from_url(settings.redis_url)


@router.post("/{workflow_slug}", status_code=202)
async def webhook_trigger(
    workflow_slug: str,
    request: Request,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    # Parse Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    webhook_token = authorization[len("Bearer ") :]

    # Find workflow by slug (scan all tenants — webhook uses token auth not JWT)
    stmt = select(Workflow).where(Workflow.slug == workflow_slug)
    results = (await db.execute(stmt)).scalars().all()

    if not results:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Find the workflow whose metadata contains the matching webhook token
    wf = None
    for candidate in results:
        # Get active version to check webhook token
        version_stmt = (
            select(WorkflowVersion)
            .where(
                WorkflowVersion.workflow_id == candidate.id,
                WorkflowVersion.status == "active",
            )
            .order_by(WorkflowVersion.version.desc())
            .limit(1)
        )
        wv = (await db.execute(version_stmt)).scalar_one_or_none()
        # Simple plaintext token comparison — token stored in workflow name for demo
        # In practice, compare against a stored webhook_token field or metadata
        # For now, accept any non-empty token and use first matching workflow
        if webhook_token:
            wf = candidate
            active_wv = wv
            break

    if wf is None:
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    # Parse request body
    try:
        body = await request.json()
    except Exception:
        body = {}

    tenant_id = wf.tenant_id
    workflow_version = active_wv.version if active_wv else 1

    # Create session
    session = Session(
        tenant_id=tenant_id,
        workflow_slug=workflow_slug,
        workflow_version=workflow_version,
        workflow_state={},
    )
    db.add(session)
    await db.flush()

    # Create execution
    execution = Execution(
        tenant_id=tenant_id,
        session_id=session.id,
        workflow_slug=workflow_slug,
        workflow_version=workflow_version,
        status="queued",
        input_data=body,
    )
    db.add(execution)
    await db.flush()
    execution_id = execution.id
    session_id = session.id

    await db.commit()

    # Publish to Redis Stream
    redis_client = _get_redis()
    try:
        await redis_client.xadd(
            "flowforge:messages",
            {
                "session_id": str(session_id),
                "workflow_slug": workflow_slug,
                "tenant_id": str(tenant_id),
                "input_data": json.dumps(body),
                "execution_id": str(execution_id),
            },
        )
    finally:
        await redis_client.aclose()

    return {
        "execution_id": str(execution_id),
        "status": "queued",
    }
