"""Tests for agents API router."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from flowforge.main import app
from flowforge.api.deps import get_current_user, get_tenant_id
from flowforge.db.session import get_db
from flowforge.models import AgentProfile

TENANT_ID = str(uuid.uuid4())
FAKE_USER = {"sub": "user-1", "tenant_id": TENANT_ID, "role": "editor"}


def make_mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


def override_deps(db=None, user=None):
    if user is None:
        user = FAKE_USER
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_tenant_id] = lambda: user["tenant_id"]
    if db is not None:
        app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def clear_overrides():
    app.dependency_overrides.clear()


def make_agent(slug="my-agent", name="My Agent"):
    a = MagicMock(spec=AgentProfile)
    a.id = uuid.uuid4()
    a.tenant_id = uuid.UUID(TENANT_ID)
    a.slug = slug
    a.name = name
    a.content = "You are an agent."
    a.default_model = "gpt-4o-mini"
    a.updated_at = datetime.now(timezone.utc)
    return a


class TestListAgents:
    def teardown_method(self):
        clear_overrides()

    def test_list_returns_agents(self):
        db = make_mock_db()
        agent = make_agent()
        db.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[agent])))
            )
        )

        client = override_deps(db=db)
        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert data["agents"][0]["slug"] == "my-agent"

    def test_list_empty(self):
        db = make_mock_db()
        db.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            )
        )

        client = override_deps(db=db)
        resp = client.get("/api/v1/agents")
        assert resp.status_code == 200
        assert resp.json()["agents"] == []


class TestGetAgent:
    def teardown_method(self):
        clear_overrides()

    def test_get_existing_agent(self):
        db = make_mock_db()
        agent = make_agent()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=agent))
        )

        client = override_deps(db=db)
        resp = client.get("/api/v1/agents/my-agent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "my-agent"
        assert data["content"] == "You are an agent."

    def test_get_nonexistent_returns_404(self):
        db = make_mock_db()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        client = override_deps(db=db)
        resp = client.get("/api/v1/agents/nonexistent")
        assert resp.status_code == 404


class TestUpsertAgent:
    def teardown_method(self):
        clear_overrides()

    def test_create_new_agent(self):
        db = make_mock_db()
        # No existing agent
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        client = override_deps(db=db)
        resp = client.put(
            "/api/v1/agents/new-agent",
            json={
                "name": "New Agent",
                "content": "You are helpful.",
                "default_model": "gpt-4o-mini",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "new-agent"
        assert "updated_at" in data

    def test_update_existing_agent(self):
        db = make_mock_db()
        existing = make_agent()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing))
        )

        client = override_deps(db=db)
        resp = client.put(
            "/api/v1/agents/my-agent",
            json={
                "name": "Updated Agent",
                "content": "Updated content.",
                "default_model": "gpt-4o",
            },
        )
        assert resp.status_code == 200
        # Verify the existing agent was modified
        assert existing.name == "Updated Agent"
        assert existing.content == "Updated content."
