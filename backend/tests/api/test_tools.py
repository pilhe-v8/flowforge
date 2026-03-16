"""Tests for tools API router."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from flowforge.main import app
from flowforge.api.deps import get_current_user, get_tenant_id
from flowforge.db.session import get_db
from flowforge.models import ToolRegistration

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


def make_tool_reg(slug="my-tool", name="My Tool"):
    t = MagicMock(spec=ToolRegistration)
    t.id = uuid.uuid4()
    t.tenant_id = uuid.UUID(TENANT_ID)
    t.slug = slug
    t.name = name
    t.protocol = "mcp"
    t.endpoint = f"mcp://example.com/{slug}"
    t.description = "A test tool"
    t.input_schema = {}
    t.output_schema = {}
    t.is_active = True
    t.created_at = datetime.now(timezone.utc)
    return t


class TestToolCatalogue:
    def teardown_method(self):
        clear_overrides()

    def test_catalogue_returns_tools(self):
        db = make_mock_db()
        tool = make_tool_reg()
        db.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[tool])))
            )
        )

        client = override_deps(db=db)
        resp = client.get("/api/v1/tools/catalogue")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        assert len(data["tools"]) == 1
        assert data["tools"][0]["slug"] == "my-tool"

    def test_catalogue_empty(self):
        db = make_mock_db()
        db.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            )
        )

        client = override_deps(db=db)
        resp = client.get("/api/v1/tools/catalogue")
        assert resp.status_code == 200
        assert resp.json()["tools"] == []

    def test_catalogue_requires_auth(self):
        clear_overrides()
        client = TestClient(app)
        resp = client.get("/api/v1/tools/catalogue")
        assert resp.status_code in (401, 403)


class TestRegisterTool:
    def teardown_method(self):
        clear_overrides()

    def test_register_success_no_discovery(self):
        """Register succeeds even if discovery fails."""
        db = make_mock_db()
        # For duplicate check in loop (no existing tools)
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        client = override_deps(db=db)
        resp = client.post(
            "/api/v1/tools/register",
            json={"endpoint": "mcp://example.com", "name": "Example"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "endpoint" in data
        assert "registered_count" in data
        assert "discovered_tools" in data

    def test_register_returns_201(self):
        db = make_mock_db()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        client = override_deps(db=db)
        resp = client.post(
            "/api/v1/tools/register",
            json={"endpoint": "mcp://localhost:8080", "name": "Test MCP"},
        )
        assert resp.status_code == 201


class TestRefreshTools:
    def teardown_method(self):
        clear_overrides()

    def test_refresh_returns_counts(self):
        db = make_mock_db()
        tool = make_tool_reg()
        db.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[tool])))
            )
        )

        client = override_deps(db=db)
        resp = client.post("/api/v1/tools/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert "refreshed_endpoints" in data
        assert "total_tools" in data
        assert "new_tools" in data
