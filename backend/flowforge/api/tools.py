"""Tool catalogue + register + refresh router."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flowforge.api.deps import get_tenant_id
from flowforge.db.session import get_db
from flowforge.models import ToolRegistration
from flowforge.tools.discovery import MCPDiscovery, slugify

router = APIRouter(prefix="/tools", tags=["tools"])


class RegisterBody(BaseModel):
    endpoint: str
    name: str


@router.get("/catalogue")
async def list_catalogue(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    tid = uuid.UUID(tenant_id)
    stmt = select(ToolRegistration).where(
        ToolRegistration.tenant_id == tid,
        ToolRegistration.is_active == True,
    )
    tools = (await db.execute(stmt)).scalars().all()

    return {
        "tools": [
            {
                "slug": t.slug,
                "name": t.name,
                "uri": t.endpoint,
                "protocol": t.protocol,
                "description": t.description,
                "input_schema": t.input_schema or {},
                "output_schema": t.output_schema or {},
            }
            for t in tools
        ]
    }


@router.post("/register", status_code=201)
async def register_tool(
    body: RegisterBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    tid = uuid.UUID(tenant_id)

    # Save the endpoint registration
    endpoint_slug = slugify(body.name)
    endpoint_reg = ToolRegistration(
        tenant_id=tid,
        slug=endpoint_slug,
        name=body.name,
        protocol="mcp",
        endpoint=body.endpoint,
        discovered_at=datetime.now(timezone.utc),
    )
    db.add(endpoint_reg)

    # Discover tools from endpoint
    discovery = MCPDiscovery()
    discovered_tools = []
    try:
        tools = await discovery.discover(body.endpoint)
    except Exception:
        tools = []

    registered_count = 0
    for tool in tools:
        # Check if already exists
        existing = await db.execute(
            select(ToolRegistration).where(
                ToolRegistration.tenant_id == tid,
                ToolRegistration.slug == tool.slug,
            )
        )
        if existing.scalar_one_or_none() is None:
            reg = ToolRegistration(
                tenant_id=tid,
                slug=tool.slug,
                name=tool.name,
                protocol="mcp",
                endpoint=tool.uri,
                description=tool.description,
                input_schema=tool.input_schema,
                output_schema=tool.output_schema,
                discovered_at=datetime.now(timezone.utc),
            )
            db.add(reg)
            registered_count += 1
            discovered_tools.append({"slug": tool.slug, "name": tool.name, "uri": tool.uri})

    await db.commit()

    return {
        "endpoint": body.endpoint,
        "discovered_tools": discovered_tools,
        "registered_count": registered_count,
    }


@router.post("/refresh")
async def refresh_tools(
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    tid = uuid.UUID(tenant_id)

    # Get all unique endpoints (parent registrations — those without a specific tool path)
    stmt = select(ToolRegistration).where(ToolRegistration.tenant_id == tid)
    registrations = (await db.execute(stmt)).scalars().all()

    # Find unique base endpoints
    endpoints = list({r.endpoint for r in registrations})
    discovery = MCPDiscovery()

    total_tools = 0
    new_tools = 0
    existing_slugs = {r.slug for r in registrations}

    for endpoint in endpoints:
        try:
            tools = await discovery.discover(endpoint)
            for tool in tools:
                total_tools += 1
                if tool.slug not in existing_slugs:
                    reg = ToolRegistration(
                        tenant_id=tid,
                        slug=tool.slug,
                        name=tool.name,
                        protocol="mcp",
                        endpoint=tool.uri,
                        description=tool.description,
                        input_schema=tool.input_schema,
                        output_schema=tool.output_schema,
                        discovered_at=datetime.now(timezone.utc),
                    )
                    db.add(reg)
                    new_tools += 1
                    existing_slugs.add(tool.slug)
        except Exception:
            pass

    await db.commit()

    return {
        "refreshed_endpoints": len(endpoints),
        "total_tools": total_tools,
        "new_tools": new_tools,
    }
