"""Tenant create router (admin only)."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from flowforge.api.deps import require_admin
from flowforge.db.session import get_db
from flowforge.models import Tenant

router = APIRouter(prefix="/tenants", tags=["tenants"])


class TenantConfig(BaseModel):
    default_llm_model: str = "gpt-4o-mini"
    daily_token_budget: int = 1000000
    max_concurrent_sessions: int = 100


class TenantCreateBody(BaseModel):
    name: str
    slug: str
    config: Optional[TenantConfig] = None


@router.post("", status_code=201)
async def create_tenant(
    body: TenantCreateBody,
    user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    config = body.config.model_dump() if body.config else {}
    tenant = Tenant(
        id=uuid.uuid4(),
        name=body.name,
        slug=body.slug,
        config=config,
    )
    db.add(tenant)
    await db.commit()

    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "config": config,
    }
