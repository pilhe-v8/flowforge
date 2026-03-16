"""Response templates router."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flowforge.api.deps import get_tenant_id
from flowforge.db.session import get_db
from flowforge.models import ResponseTemplate

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplatePutBody(BaseModel):
    name: str
    content: str
    variables: List[str] = []


@router.get("")
async def list_templates(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    tid = uuid.UUID(tenant_id)
    stmt = select(ResponseTemplate).where(ResponseTemplate.tenant_id == tid)
    templates = (await db.execute(stmt)).scalars().all()

    return {
        "templates": [
            {
                "slug": t.slug,
                "name": t.name,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in templates
        ]
    }


@router.put("/{slug}")
async def upsert_template(
    slug: str,
    body: TemplatePutBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    tid = uuid.UUID(tenant_id)
    now = datetime.now(timezone.utc)

    stmt = select(ResponseTemplate).where(
        ResponseTemplate.tenant_id == tid,
        ResponseTemplate.slug == slug,
    )
    template = (await db.execute(stmt)).scalar_one_or_none()

    if template is None:
        template = ResponseTemplate(
            tenant_id=tid,
            slug=slug,
            name=body.name,
            content=body.content,
            variables=body.variables,
            updated_at=now,
        )
        db.add(template)
    else:
        template.name = body.name
        template.content = body.content
        template.variables = body.variables
        template.updated_at = now

    await db.commit()

    return {
        "slug": template.slug,
        "name": template.name,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }
