from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from flowforge.db.session import AsyncSessionLocal
from flowforge.models import Session as SessionModel


@dataclass
class Session:
    """In-memory representation of a workflow session."""

    id: str
    state: dict
    step_count: int
    tenant_id: str = ""
    updated_at: Optional[datetime] = None


class SessionManager:
    """Handles loading and saving workflow sessions from/to PostgreSQL."""

    @staticmethod
    async def load(session_id: str) -> Session:
        async with AsyncSessionLocal() as db:
            row = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
            model = row.scalar_one_or_none()
            if model is None:
                return Session(id=session_id, state={}, step_count=0)
            return Session(
                id=str(model.id),
                state=model.workflow_state,
                step_count=model.step_count or 0,
                tenant_id=str(model.tenant_id),
            )

    @staticmethod
    async def save(session: Session):
        async with AsyncSessionLocal() as db:
            stmt = (
                pg_insert(SessionModel)
                .values(
                    id=session.id,
                    tenant_id=session.tenant_id or "00000000-0000-0000-0000-000000000000",
                    workflow_slug="",
                    workflow_version=0,
                    workflow_state=session.state,
                    step_count=session.step_count,
                    updated_at=session.updated_at or datetime.utcnow(),
                )
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "workflow_state": session.state,
                        "step_count": session.step_count,
                        "updated_at": session.updated_at or datetime.utcnow(),
                    },
                )
            )
            await db.execute(stmt)
            await db.commit()
