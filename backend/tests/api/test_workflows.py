"""Tests for workflows API router."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from flowforge.main import app
from flowforge.api.deps import get_current_user, get_tenant_id
from flowforge.db.session import get_db
from flowforge.models import Workflow, WorkflowVersion

TENANT_ID = str(uuid.uuid4())
FAKE_USER = {
    "sub": "user-1",
    "tenant_id": TENANT_ID,
    "role": "editor",
}

VALID_YAML = """
workflow:
  name: test-workflow
  trigger:
    type: manual
    output: []
  steps:
    - id: step1
      name: Step 1
      type: deterministic
      operation: passthrough
      output: []
"""

INVALID_YAML = "not: valid: yaml: ["


def make_mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


def override_deps(db=None, user=None):
    """Apply dependency overrides and return the test client."""
    if user is None:
        user = FAKE_USER

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_tenant_id] = lambda: user["tenant_id"]
    if db is not None:
        app.dependency_overrides[get_db] = lambda: db

    return TestClient(app)


def clear_overrides():
    app.dependency_overrides.clear()


def make_workflow(slug="my-workflow", name="My Workflow", tenant_id=None):
    wf = MagicMock(spec=Workflow)
    wf.id = uuid.uuid4()
    wf.slug = slug
    wf.name = name
    wf.tenant_id = uuid.UUID(tenant_id or TENANT_ID)
    wf.created_at = datetime.now(timezone.utc)
    return wf


def make_version(wf_id=None, version=1, status="draft", yaml_def=VALID_YAML):
    wv = MagicMock(spec=WorkflowVersion)
    wv.id = uuid.uuid4()
    wv.workflow_id = wf_id or uuid.uuid4()
    wv.version = version
    wv.status = status
    wv.yaml_definition = yaml_def
    wv.compiled_at = datetime.now(timezone.utc)
    wv.compilation_errors = []
    wv.trigger_type = "manual"
    wv.node_count = 1
    wv.created_at = datetime.now(timezone.utc)
    return wv


class TestListWorkflows:
    def teardown_method(self):
        clear_overrides()

    def test_list_returns_workflows_for_tenant(self):
        db = make_mock_db()
        wf = make_workflow()
        wv = make_version(wf.id)

        # Mock execute results: first call for count, second for list, then version
        execute_results = [
            MagicMock(scalar_one=MagicMock(return_value=1)),  # count
            MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[wf])))
            ),  # list
            MagicMock(scalar_one_or_none=MagicMock(return_value=wv)),  # latest version
        ]
        db.execute = AsyncMock(side_effect=execute_results)

        client = override_deps(db=db)
        resp = client.get("/api/v1/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert "workflows" in data
        assert "total" in data
        assert data["total"] == 1

    def test_list_pagination(self):
        db = make_mock_db()
        execute_results = [
            MagicMock(scalar_one=MagicMock(return_value=0)),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
        ]
        db.execute = AsyncMock(side_effect=execute_results)

        client = override_deps(db=db)
        resp = client.get("/api/v1/workflows?page=2&per_page=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
        assert data["per_page"] == 5

    def test_list_requires_auth(self):
        clear_overrides()
        client = TestClient(app)
        resp = client.get("/api/v1/workflows")
        assert resp.status_code in (401, 403)


class TestGetWorkflow:
    def teardown_method(self):
        clear_overrides()

    def test_get_existing_workflow(self):
        db = make_mock_db()
        wf = make_workflow()
        wv = make_version(wf.id, status="active")

        # workflow lookup, active version lookup
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=wf)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=wv)),
            ]
        )

        client = override_deps(db=db)
        resp = client.get(f"/api/v1/workflows/{wf.slug}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == wf.slug
        assert "yaml_definition" in data

    def test_get_nonexistent_workflow_returns_404(self):
        db = make_mock_db()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        client = override_deps(db=db)
        resp = client.get("/api/v1/workflows/nonexistent")
        assert resp.status_code == 404

    def test_get_workflow_filters_by_tenant(self):
        """Ensure tenant filter is applied — other-tenant workflow not found."""
        db = make_mock_db()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        # User from different tenant
        other_user = {**FAKE_USER, "tenant_id": str(uuid.uuid4())}
        client = override_deps(db=db, user=other_user)
        resp = client.get("/api/v1/workflows/my-workflow")
        assert resp.status_code == 404


class TestCreateWorkflow:
    def teardown_method(self):
        clear_overrides()

    def test_create_returns_201(self):
        db = make_mock_db()
        # Check uniqueness: None found
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        client = override_deps(db=db)
        resp = client.post(
            "/api/v1/workflows",
            json={"name": "My Workflow", "yaml_definition": VALID_YAML},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "slug" in data
        assert data["version"] == 1
        assert data["status"] == "draft"

    def test_create_slug_from_name(self):
        db = make_mock_db()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        client = override_deps(db=db)
        resp = client.post(
            "/api/v1/workflows",
            json={"name": "Hello World Workflow", "yaml_definition": VALID_YAML},
        )
        assert resp.status_code == 201
        assert resp.json()["slug"] == "hello-world-workflow"

    def test_create_duplicate_name_returns_409(self):
        db = make_mock_db()
        existing = make_workflow()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing))
        )

        client = override_deps(db=db)
        resp = client.post(
            "/api/v1/workflows",
            json={"name": "My Workflow", "yaml_definition": VALID_YAML},
        )
        assert resp.status_code == 409


class TestUpdateWorkflow:
    def teardown_method(self):
        clear_overrides()

    def test_update_creates_new_version(self):
        db = make_mock_db()
        wf = make_workflow()

        # workflow lookup, max version query
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=wf)),
                MagicMock(scalar_one=MagicMock(return_value=2)),  # current max version
            ]
        )

        client = override_deps(db=db)
        resp = client.put(
            f"/api/v1/workflows/{wf.slug}",
            json={"yaml_definition": VALID_YAML},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 3
        assert data["status"] == "draft"

    def test_update_returns_compilation_errors(self):
        db = make_mock_db()
        wf = make_workflow()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=wf)),
                MagicMock(scalar_one=MagicMock(return_value=1)),
            ]
        )

        client = override_deps(db=db)
        resp = client.put(
            f"/api/v1/workflows/{wf.slug}",
            json={"yaml_definition": INVALID_YAML},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["compilation_errors"]) > 0


class TestDeployWorkflow:
    def teardown_method(self):
        clear_overrides()

    def test_deploy_success(self):
        db = make_mock_db()
        wf = make_workflow()
        wv = make_version(wf.id, version=2, yaml_def=VALID_YAML)
        all_versions = [make_version(wf.id, version=1), wv]

        db.execute = AsyncMock(
            side_effect=[
                # workflow lookup
                MagicMock(scalar_one_or_none=MagicMock(return_value=wf)),
                # version lookup
                MagicMock(scalar_one_or_none=MagicMock(return_value=wv)),
                # all versions for status update
                MagicMock(
                    scalars=MagicMock(
                        return_value=MagicMock(all=MagicMock(return_value=all_versions))
                    )
                ),
            ]
        )

        client = override_deps(db=db)
        resp = client.post(f"/api/v1/workflows/{wf.slug}/deploy", json={"version": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["version"] == 2
        assert "deployed_at" in data

    def test_deploy_invalid_yaml_returns_422(self):
        db = make_mock_db()
        wf = make_workflow()
        wv = make_version(wf.id, version=1, yaml_def=INVALID_YAML)

        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=wf)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=wv)),
            ]
        )

        client = override_deps(db=db)
        resp = client.post(f"/api/v1/workflows/{wf.slug}/deploy", json={"version": 1})
        assert resp.status_code == 422
        data = resp.json()
        assert "errors" in data["detail"]

    def test_deploy_missing_version_returns_404(self):
        db = make_mock_db()
        wf = make_workflow()

        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=wf)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
            ]
        )

        client = override_deps(db=db)
        resp = client.post(f"/api/v1/workflows/{wf.slug}/deploy", json={"version": 99})
        assert resp.status_code == 404


class TestRollbackWorkflow:
    def teardown_method(self):
        clear_overrides()

    def test_rollback_success(self):
        db = make_mock_db()
        wf = make_workflow()
        wv_old = make_version(wf.id, version=1, status="inactive")
        wv_new = make_version(wf.id, version=2, status="active")

        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=wf)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=wv_old)),
                MagicMock(
                    scalars=MagicMock(
                        return_value=MagicMock(all=MagicMock(return_value=[wv_old, wv_new]))
                    )
                ),
            ]
        )

        client = override_deps(db=db)
        resp = client.post(f"/api/v1/workflows/{wf.slug}/rollback", json={"version": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 1
        assert data["status"] == "active"


class TestListVersions:
    def teardown_method(self):
        clear_overrides()

    def test_list_versions(self):
        db = make_mock_db()
        wf = make_workflow()
        v1 = make_version(wf.id, version=1, status="inactive")
        v2 = make_version(wf.id, version=2, status="active")

        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=wf)),
                MagicMock(
                    scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[v2, v1])))
                ),
            ]
        )

        client = override_deps(db=db)
        resp = client.get(f"/api/v1/workflows/{wf.slug}/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert "versions" in data
        assert len(data["versions"]) == 2
        assert data["versions"][0]["version"] == 2
