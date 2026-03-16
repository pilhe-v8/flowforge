"""Agent profiles router."""

import uuid
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flowforge.api.deps import get_tenant_id
from flowforge.db.session import get_db
from flowforge.models import AgentProfile

router = APIRouter(prefix="/agents", tags=["agents"])


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text


class AgentPutBody(BaseModel):
    name: str
    content: str
    default_model: Optional[str] = None


@router.get("")
async def list_agents(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    tid = uuid.UUID(tenant_id)
    stmt = select(AgentProfile).where(AgentProfile.tenant_id == tid)
    agents = (await db.execute(stmt)).scalars().all()

    return {
        "agents": [
            {
                "slug": a.slug,
                "name": a.name,
                "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            }
            for a in agents
        ]
    }


@router.get("/{slug}")
async def get_agent(
    slug: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    tid = uuid.UUID(tenant_id)
    stmt = select(AgentProfile).where(
        AgentProfile.tenant_id == tid,
        AgentProfile.slug == slug,
    )
    agent = (await db.execute(stmt)).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent profile not found")

    return {
        "slug": agent.slug,
        "name": agent.name,
        "content": agent.content,
        "default_model": agent.default_model,
    }


@router.put("/{slug}")
async def upsert_agent(
    slug: str,
    body: AgentPutBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    tid = uuid.UUID(tenant_id)
    now = datetime.now(timezone.utc)

    stmt = select(AgentProfile).where(
        AgentProfile.tenant_id == tid,
        AgentProfile.slug == slug,
    )
    agent = (await db.execute(stmt)).scalar_one_or_none()

    if agent is None:
        agent = AgentProfile(
            tenant_id=tid,
            slug=slug,
            name=body.name,
            content=body.content,
            default_model=body.default_model,
            updated_at=now,
        )
        db.add(agent)
    else:
        agent.name = body.name
        agent.content = body.content
        agent.default_model = body.default_model
        agent.updated_at = now

    await db.commit()

    return {
        "slug": agent.slug,
        "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
    }
