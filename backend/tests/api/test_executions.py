"""Tests for executions API router."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from flowforge.main import app
from flowforge.api.deps import get_current_user, get_tenant_id
from flowforge.db.session import get_db
from flowforge.models import (
    Execution,
    ExecutionStep,
    Session,
    TokenUsage,
    Workflow,
    WorkflowVersion,
)

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


def make_workflow():
    wf = MagicMock(spec=Workflow)
    wf.id = uuid.uuid4()
    wf.slug = "test-workflow"
    wf.name = "Test Workflow"
    wf.tenant_id = uuid.UUID(TENANT_ID)
    return wf


def make_wf_version(wf_id, version=1):
    wv = MagicMock(spec=WorkflowVersion)
    wv.id = uuid.uuid4()
    wv.workflow_id = wf_id
    wv.version = version
    wv.status = "active"
    return wv


def make_session(tenant_id=None):
    s = MagicMock(spec=Session)
    s.id = uuid.uuid4()
    s.tenant_id = uuid.UUID(tenant_id or TENANT_ID)
    return s


def make_execution(tenant_id=None, status="queued"):
    e = MagicMock(spec=Execution)
    e.id = uuid.uuid4()
    e.tenant_id = uuid.UUID(tenant_id or TENANT_ID)
    e.workflow_slug = "test-workflow"
    e.workflow_version = 1
    e.status = status
    e.duration_ms = 1200
    e.queued_at = datetime.now(timezone.utc)
    e.input_data = {}
    return e


class TestTriggerExecution:
    def teardown_method(self):
        clear_overrides()

    def test_trigger_returns_202(self):
        db = make_mock_db()
        wf = make_workflow()
        wv = make_wf_version(wf.id)
        session = make_session()
        execution = make_execution()

        # Set up IDs that will be captured by the endpoint
        session.id = uuid.uuid4()
        execution.id = uuid.uuid4()

        # Workflow lookup, version lookup
        execute_results = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=wf)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=wv)),
        ]
        db.execute = AsyncMock(side_effect=execute_results)

        # Capture the objects added to the session
        added_objects = []

        def capture_add(obj):
            added_objects.append(obj)
            # If it's a Session, give it an ID
            if isinstance(obj, Session):
                pass  # real object is added

        # Mock the db.add to capture real Session/Execution objects
        db.add = capture_add

        async def mock_flush():
            pass

        db.flush = AsyncMock(side_effect=mock_flush)

        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch("flowforge.api.executions._get_redis", return_value=mock_redis):
            client = override_deps(db=db)
            resp = client.post(
                "/api/v1/executions/trigger",
                json={"workflow_slug": "test-workflow", "input_data": {"key": "value"}},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert "execution_id" in data
        assert "session_id" in data
        assert data["status"] == "queued"

    def test_trigger_publishes_to_redis(self):
        db = make_mock_db()
        wf = make_workflow()
        wv = make_wf_version(wf.id)

        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=wf)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=wv)),
            ]
        )

        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch("flowforge.api.executions._get_redis", return_value=mock_redis):
            client = override_deps(db=db)
            resp = client.post(
                "/api/v1/executions/trigger",
                json={"workflow_slug": "test-workflow", "input_data": {}},
            )

        assert resp.status_code == 202
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == "flowforge:messages"

    def test_trigger_nonexistent_workflow_404(self):
        db = make_mock_db()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        client = override_deps(db=db)
        resp = client.post(
            "/api/v1/executions/trigger",
            json={"workflow_slug": "does-not-exist", "input_data": {}},
        )
        assert resp.status_code == 404


class TestGetExecution:
    def teardown_method(self):
        clear_overrides()

    def test_get_existing_execution(self):
        db = make_mock_db()
        execution = make_execution(status="completed")
        execution_id = uuid.uuid4()
        execution.id = execution_id

        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=execution)),
                MagicMock(
                    scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
                ),
                MagicMock(
                    scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
                ),
            ]
        )

        client = override_deps(db=db)
        resp = client.get(f"/api/v1/executions/{execution_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "steps" in data

    def test_get_nonexistent_execution_404(self):
        db = make_mock_db()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        client = override_deps(db=db)
        resp = client.get(f"/api/v1/executions/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_get_invalid_uuid_400(self):
        db = make_mock_db()
        client = override_deps(db=db)
        resp = client.get("/api/v1/executions/not-a-uuid")
        assert resp.status_code == 400


class TestListExecutions:
    def teardown_method(self):
        clear_overrides()

    def test_list_returns_executions(self):
        db = make_mock_db()
        e1 = make_execution(status="completed")
        e2 = make_execution(status="queued")

        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one=MagicMock(return_value=2)),
                MagicMock(
                    scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[e1, e2])))
                ),
            ]
        )

        client = override_deps(db=db)
        resp = client.get("/api/v1/executions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["executions"]) == 2

    def test_list_filter_by_workflow_slug(self):
        db = make_mock_db()
        db.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one=MagicMock(return_value=0)),
                MagicMock(
                    scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
                ),
            ]
        )

        client = override_deps(db=db)
        resp = client.get("/api/v1/executions?workflow_slug=my-workflow")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Fixtures and test for enriched GET /executions/{id}
# ---------------------------------------------------------------------------


@pytest.fixture
def execution_with_steps():
    """Return a tuple (execution, step) with MagicMock objects."""
    execution = make_execution(status="completed")
    execution.started_at = datetime.now(timezone.utc)
    execution.completed_at = datetime.now(timezone.utc)
    execution.output_data = {"result": "ok"}

    step = MagicMock(spec=ExecutionStep)
    step.step_id = "step-1"
    step.step_name = "My Step"
    step.step_type = "llm"
    step.status = "completed"
    step.duration_ms = 500
    step.input_data = {"prompt": "hello"}
    step.output_data = {"text": "world"}
    step.started_at = datetime.now(timezone.utc)
    step.step_metadata = {"model": "gpt-4o", "input_tokens": 10, "output_tokens": 20}

    return execution, step


@pytest.fixture
def client(execution_with_steps):
    """TestClient wired with a mock DB that returns execution_with_steps."""
    execution, step = execution_with_steps
    db = make_mock_db()

    # Build a mock TokenUsage row matching the step metadata
    token_row = MagicMock(spec=TokenUsage)
    token_row.model = "gpt-4o"
    token_row.input_tokens = 10
    token_row.output_tokens = 20

    # Three db.execute calls: 1) get execution, 2) get token_rows, 3) get steps
    db.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=execution)),
            MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[token_row])))
            ),
            MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[step])))
            ),
        ]
    )

    return override_deps(db=db)


def test_get_execution_includes_enriched_fields(client, execution_with_steps):
    """GET /executions/{id} must include model, tokens, duration per step."""
    execution, _ = execution_with_steps
    resp = client.get(f"/api/v1/executions/{execution.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "queued_at" in data
    assert "duration_ms" in data
    assert "workflow_slug" in data
    step = data["steps"][0]
    assert "step_name" in step
    assert "model" in step
    assert "input_tokens" in step
    assert "output_tokens" in step
    assert "duration_ms" in step

    # Step-level value assertions
    assert step["model"] == "gpt-4o"
    assert step["input_tokens"] == 10
    assert step["output_tokens"] == 20

    # Top-level token and cost assertions
    assert data["total_input_tokens"] == 10
    assert data["total_output_tokens"] == 20
    assert "estimated_cost_usd" in data
    assert data["estimated_cost_usd"] >= 0
