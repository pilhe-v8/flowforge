"""Tests for tenants API router."""

import uuid
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from flowforge.main import app
from flowforge.api.deps import get_current_user, get_tenant_id
from flowforge.db.session import get_db
from flowforge.models import Tenant

TENANT_ID = str(uuid.uuid4())
ADMIN_USER = {"sub": "admin-1", "tenant_id": TENANT_ID, "role": "admin"}
EDITOR_USER = {"sub": "editor-1", "tenant_id": TENANT_ID, "role": "editor"}
VIEWER_USER = {"sub": "viewer-1", "tenant_id": TENANT_ID, "role": "viewer"}


def make_mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


def override_deps(db=None, user=None):
    if user is None:
        user = ADMIN_USER
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_tenant_id] = lambda: user["tenant_id"]
    if db is not None:
        app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def clear_overrides():
    app.dependency_overrides.clear()


CREATE_BODY = {
    "name": "Acme Corp",
    "slug": "acme-corp",
    "config": {
        "default_llm_model": "gpt-4o-mini",
        "daily_token_budget": 1000000,
        "max_concurrent_sessions": 100,
    },
}


class TestCreateTenant:
    def teardown_method(self):
        clear_overrides()

    def test_admin_can_create_tenant(self):
        db = make_mock_db()
        client = override_deps(db=db, user=ADMIN_USER)
        resp = client.post("/api/v1/tenants", json=CREATE_BODY)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Acme Corp"
        assert data["slug"] == "acme-corp"
        assert "id" in data

    def test_editor_cannot_create_tenant(self):
        db = make_mock_db()
        client = override_deps(db=db, user=EDITOR_USER)
        resp = client.post("/api/v1/tenants", json=CREATE_BODY)
        assert resp.status_code == 403

    def test_viewer_cannot_create_tenant(self):
        db = make_mock_db()
        client = override_deps(db=db, user=VIEWER_USER)
        resp = client.post("/api/v1/tenants", json=CREATE_BODY)
        assert resp.status_code == 403

    def test_create_without_config(self):
        db = make_mock_db()
        client = override_deps(db=db, user=ADMIN_USER)
        resp = client.post(
            "/api/v1/tenants",
            json={"name": "Simple Corp", "slug": "simple-corp"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == "simple-corp"

    def test_unauthenticated_gets_403(self):
        clear_overrides()
        client = TestClient(app)
        resp = client.post("/api/v1/tenants", json=CREATE_BODY)
        assert resp.status_code in (401, 403)
