"""Workflow CRUD + deploy + rollback + versions router."""

import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from flowforge.api.deps import get_current_user, get_tenant_id
from flowforge.db.session import get_db
from flowforge.models import Workflow, WorkflowVersion
from flowforge.compiler import Compiler

router = APIRouter(prefix="/workflows", tags=["workflows"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text


def _try_compile(yaml_definition: str):
    """Attempt compilation with empty catalogues. Returns (errors_list, compiled_at_or_None)."""
    compiler = Compiler(tool_catalogue={}, agent_profiles={})
    result = compiler.compile(yaml_definition)
    if result.success:
        return [], datetime.now(timezone.utc)
    errors = [{"step_id": e.step_id, "field": e.field, "message": e.message} for e in result.errors]
    return errors, None


async def _get_workflow_or_404(db: AsyncSession, tenant_id: str, slug: str) -> Workflow:
    stmt = select(Workflow).where(
        Workflow.tenant_id == uuid.UUID(tenant_id),
        Workflow.slug == slug,
    )
    result = await db.execute(stmt)
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


async def _get_active_version(
    db: AsyncSession, workflow_id: uuid.UUID
) -> Optional[WorkflowVersion]:
    stmt = (
        select(WorkflowVersion)
        .where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.status == "active",
        )
        .order_by(WorkflowVersion.version.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_latest_version(
    db: AsyncSession, workflow_id: uuid.UUID
) -> Optional[WorkflowVersion]:
    stmt = (
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.version.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class WorkflowCreateBody(BaseModel):
    name: str
    yaml_definition: str


class WorkflowUpdateBody(BaseModel):
    yaml_definition: str


class DeployBody(BaseModel):
    version: int


class RollbackBody(BaseModel):
    version: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_workflows(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    tid = uuid.UUID(tenant_id)
    stmt = select(Workflow).where(Workflow.tenant_id == tid)
    if search:
        stmt = stmt.where(Workflow.name.ilike(f"%{search}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    rows = (await db.execute(stmt)).scalars().all()

    items = []
    for wf in rows:
        # Get latest version info
        latest = await _get_latest_version(db, wf.id)
        items.append(
            {
                "slug": wf.slug,
                "name": wf.name,
                "version": latest.version if latest else 0,
                "status": latest.status if latest else "draft",
                "trigger_type": latest.trigger_type if latest else None,
                "node_count": latest.node_count if latest else 0,
                "execution_count_24h": 0,
                "created_at": wf.created_at.isoformat() if wf.created_at else None,
                "updated_at": wf.created_at.isoformat() if wf.created_at else None,
            }
        )

    return {"workflows": items, "total": total, "page": page, "per_page": per_page}


@router.get("/{slug}")
async def get_workflow(
    slug: str,
    version: Optional[int] = Query(None),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    wf = await _get_workflow_or_404(db, tenant_id, slug)

    if version is not None:
        stmt = select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == wf.id,
            WorkflowVersion.version == version,
        )
    else:
        # Get latest (prefer active, else latest)
        active = await _get_active_version(db, wf.id)
        if active:
            wv = active
        else:
            wv = await _get_latest_version(db, wf.id)
        if wv is None:
            raise HTTPException(status_code=404, detail="No versions found")
        return {
            "slug": wf.slug,
            "name": wf.name,
            "version": wv.version,
            "status": wv.status,
            "yaml_definition": wv.yaml_definition,
            "compiled_at": wv.compiled_at.isoformat() if wv.compiled_at else None,
            "compilation_errors": wv.compilation_errors or [],
        }

    result = await db.execute(stmt)
    wv = result.scalar_one_or_none()
    if wv is None:
        raise HTTPException(status_code=404, detail="Version not found")

    return {
        "slug": wf.slug,
        "name": wf.name,
        "version": wv.version,
        "status": wv.status,
        "yaml_definition": wv.yaml_definition,
        "compiled_at": wv.compiled_at.isoformat() if wv.compiled_at else None,
        "compilation_errors": wv.compilation_errors or [],
    }


@router.post("", status_code=201)
async def create_workflow(
    body: WorkflowCreateBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    tid = uuid.UUID(tenant_id)
    slug = slugify(body.name)

    # Check uniqueness
    existing = await db.execute(
        select(Workflow).where(Workflow.tenant_id == tid, Workflow.slug == slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Workflow with this name already exists")

    wf = Workflow(tenant_id=tid, slug=slug, name=body.name)
    db.add(wf)
    await db.flush()  # Get the ID

    errors, compiled_at = _try_compile(body.yaml_definition)

    wv = WorkflowVersion(
        workflow_id=wf.id,
        version=1,
        yaml_definition=body.yaml_definition,
        status="draft",
        compilation_errors=errors,
        compiled_at=compiled_at,
    )
    db.add(wv)
    await db.commit()

    return {"slug": wf.slug, "version": 1, "status": "draft"}


@router.put("/{slug}")
async def update_workflow(
    slug: str,
    body: WorkflowUpdateBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    wf = await _get_workflow_or_404(db, tenant_id, slug)

    # Get max version
    stmt = select(func.max(WorkflowVersion.version)).where(WorkflowVersion.workflow_id == wf.id)
    max_version = (await db.execute(stmt)).scalar_one() or 0
    new_version = max_version + 1

    errors, compiled_at = _try_compile(body.yaml_definition)

    wv = WorkflowVersion(
        workflow_id=wf.id,
        version=new_version,
        yaml_definition=body.yaml_definition,
        status="draft",
        compilation_errors=errors,
        compiled_at=compiled_at,
    )
    db.add(wv)
    await db.commit()

    return {
        "slug": wf.slug,
        "version": new_version,
        "status": "draft",
        "compilation_errors": errors,
    }


@router.post("/{slug}/deploy")
async def deploy_workflow(
    slug: str,
    body: DeployBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    wf = await _get_workflow_or_404(db, tenant_id, slug)

    # Find the version
    stmt = select(WorkflowVersion).where(
        WorkflowVersion.workflow_id == wf.id,
        WorkflowVersion.version == body.version,
    )
    result = await db.execute(stmt)
    wv = result.scalar_one_or_none()
    if wv is None:
        raise HTTPException(status_code=404, detail="Version not found")

    # Try to compile
    errors, compiled_at = _try_compile(wv.yaml_definition)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"errors": errors},
        )

    # Set all versions to inactive
    all_versions_stmt = select(WorkflowVersion).where(WorkflowVersion.workflow_id == wf.id)
    all_versions = (await db.execute(all_versions_stmt)).scalars().all()
    for v in all_versions:
        v.status = "inactive"

    wv.status = "active"
    wv.compiled_at = compiled_at
    wv.compilation_errors = []
    await db.commit()

    deployed_at = datetime.now(timezone.utc)
    return {
        "slug": wf.slug,
        "version": body.version,
        "status": "active",
        "deployed_at": deployed_at.isoformat(),
    }


@router.post("/{slug}/rollback")
async def rollback_workflow(
    slug: str,
    body: RollbackBody,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    wf = await _get_workflow_or_404(db, tenant_id, slug)

    # Find the version to rollback to
    stmt = select(WorkflowVersion).where(
        WorkflowVersion.workflow_id == wf.id,
        WorkflowVersion.version == body.version,
    )
    result = await db.execute(stmt)
    wv = result.scalar_one_or_none()
    if wv is None:
        raise HTTPException(status_code=404, detail="Version not found")

    # Set all versions to inactive
    all_versions_stmt = select(WorkflowVersion).where(WorkflowVersion.workflow_id == wf.id)
    all_versions = (await db.execute(all_versions_stmt)).scalars().all()
    for v in all_versions:
        v.status = "inactive"

    wv.status = "active"
    await db.commit()

    return {"slug": wf.slug, "version": body.version, "status": "active"}


@router.get("/{slug}/versions")
async def list_versions(
    slug: str,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    wf = await _get_workflow_or_404(db, tenant_id, slug)

    stmt = (
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == wf.id)
        .order_by(WorkflowVersion.version.desc())
    )
    versions = (await db.execute(stmt)).scalars().all()

    return {
        "versions": [
            {
                "version": v.version,
                "status": v.status,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ]
    }
