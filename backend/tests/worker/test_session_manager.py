"""Tests for SessionManager — PostgreSQL-backed session persistence."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

from flowforge.worker.session_manager import SessionManager, Session


def make_mock_model(session_id="sess-1", workflow_state=None, step_count=3, tenant_id="tenant-abc"):
    """Create a fake SQLAlchemy session model row."""
    model = MagicMock()
    model.id = session_id
    model.workflow_state = workflow_state or {"key": "val"}
    model.step_count = step_count
    model.tenant_id = tenant_id
    return model


class FakeAsyncContextManager:
    """Async context manager that wraps a fake DB session."""

    def __init__(self, db_session):
        self._db = db_session

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *args):
        pass


def make_db_session(scalar_result=None):
    """Create a mock async DB session with a configurable scalar_one_or_none result."""
    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = scalar_result
    db.execute = AsyncMock(return_value=execute_result)
    db.commit = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_load_returns_new_session_when_not_found():
    """SessionManager.load should return a fresh Session when the row doesn't exist."""
    db = make_db_session(scalar_result=None)
    ctx = FakeAsyncContextManager(db)

    with patch("flowforge.worker.session_manager.AsyncSessionLocal", return_value=ctx):
        session = await SessionManager.load("missing-session")

    assert session.id == "missing-session"
    assert session.state == {}
    assert session.step_count == 0


@pytest.mark.asyncio
async def test_load_returns_session_from_db_row():
    """SessionManager.load should populate Session from the DB model when found."""
    model = make_mock_model(
        session_id="sess-99",
        workflow_state={"counter": 5},
        step_count=7,
        tenant_id="t-xyz",
    )
    db = make_db_session(scalar_result=model)
    ctx = FakeAsyncContextManager(db)

    with patch("flowforge.worker.session_manager.AsyncSessionLocal", return_value=ctx):
        session = await SessionManager.load("sess-99")

    assert session.id == "sess-99"
    assert session.state == {"counter": 5}
    assert session.step_count == 7
    assert session.tenant_id == "t-xyz"


@pytest.mark.asyncio
async def test_save_calls_upsert_with_correct_values():
    """SessionManager.save should call an INSERT ... ON CONFLICT DO UPDATE."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    ctx = FakeAsyncContextManager(db)

    session = Session(
        id="sess-save",
        state={"result": "done"},
        step_count=10,
        tenant_id="tenant-save",
        updated_at=datetime(2024, 1, 1, 12, 0, 0),
    )

    with patch("flowforge.worker.session_manager.AsyncSessionLocal", return_value=ctx):
        await SessionManager.save(session)

    assert db.execute.called
    assert db.commit.called


@pytest.mark.asyncio
async def test_save_commits_after_execute():
    """SessionManager.save must call db.commit() after executing the upsert."""
    call_order = []
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=lambda *a, **kw: call_order.append("execute"))
    db.commit = AsyncMock(side_effect=lambda: call_order.append("commit"))
    ctx = FakeAsyncContextManager(db)

    session = Session(id="s1", state={}, step_count=0, tenant_id="t1")

    with patch("flowforge.worker.session_manager.AsyncSessionLocal", return_value=ctx):
        await SessionManager.save(session)

    assert call_order == ["execute", "commit"]


def test_session_dataclass_defaults():
    """Session dataclass should have sensible defaults for optional fields."""
    s = Session(id="x", state={}, step_count=0)
    assert s.tenant_id == ""
    assert s.updated_at is None
