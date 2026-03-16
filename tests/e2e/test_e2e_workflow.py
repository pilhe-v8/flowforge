"""
E2E test suite — requires live Docker Compose stack.
Run with: pytest tests/e2e/ -v -s

These tests prove the full API→worker→LLM→DB round-trip:
  1. Create a workflow via POST /workflows
  2. Deploy it via POST /workflows/{slug}/deploy
  3. Trigger an execution and poll until completed, then assert a non-empty LLM reply
"""

import time
import pathlib
import pytest
import httpx
import yaml

WORKFLOW_YAML_PATH = pathlib.Path(__file__).parent / "e2e_workflow.yaml"
POLL_INTERVAL = 2  # seconds between status polls
POLL_TIMEOUT = 90  # seconds total before failing


@pytest.fixture(scope="module")
def workflow_yaml() -> dict:
    """Load and return the parsed workflow YAML."""
    return yaml.safe_load(WORKFLOW_YAML_PATH.read_text())


@pytest.fixture(scope="module")
def workflow_slug(workflow_yaml: dict) -> str:
    """Extract the slug from the workflow YAML."""
    return workflow_yaml["workflow"]["slug"]


@pytest.fixture(scope="module")
def workflow_name(workflow_yaml: dict) -> str:
    """Extract the name from the workflow YAML."""
    return workflow_yaml["workflow"]["name"]


def test_create_workflow(
    http: httpx.Client, workflow_slug: str, workflow_name: str
) -> None:
    """POST /workflows creates the workflow (201) or it already exists (409).

    The API accepts {"name": str, "yaml_definition": str} — not the parsed YAML dict.
    The slug is derived server-side from the name via slugify().
    """
    yaml_definition = WORKFLOW_YAML_PATH.read_text()
    payload = {
        "name": workflow_name,
        "yaml_definition": yaml_definition,
    }
    resp = http.post("/workflows", json=payload)
    assert resp.status_code in (201, 409), (
        f"Expected 201 (created) or 409 (already exists), got {resp.status_code}: {resp.text}"
    )
    if resp.status_code == 201:
        data = resp.json()
        assert data.get("slug") == workflow_slug, (
            f"Expected slug '{workflow_slug}', got '{data.get('slug')}'"
        )
        assert data.get("status") == "draft", (
            f"Expected status 'draft' after creation, got '{data.get('status')}'"
        )


def test_deploy_workflow(http: httpx.Client, workflow_slug: str) -> None:
    """POST /workflows/{slug}/deploy activates the latest draft version.

    The deploy endpoint runs compilation — if the YAML is invalid it returns 422.
    A successful deploy returns 200 with {"status": "active", ...}.
    """
    resp = http.post(f"/workflows/{workflow_slug}/deploy")
    assert resp.status_code == 200, (
        f"Deploy failed with {resp.status_code}. "
        f"Check that the YAML is valid and compilation succeeds.\n{resp.text}"
    )
    data = resp.json()
    assert data.get("status") == "active", (
        f"Expected status 'active' after deploy, got: {data}"
    )
    assert data.get("slug") == workflow_slug, (
        f"Expected slug '{workflow_slug}', got '{data.get('slug')}'"
    )


def test_trigger_and_poll_execution(http: httpx.Client, workflow_slug: str) -> None:
    """POST /executions/trigger → poll GET /executions/{id} → assert completed + non-empty LLM reply.

    Flow:
      1. Trigger the workflow execution (returns 202 with execution_id)
      2. Poll the execution status until "completed" or "failed" (or timeout)
      3. Assert final status == "completed"
      4. Assert at least one step produced a non-empty output (LLM reply)
    """
    # Step 1: Trigger the execution
    resp = http.post(
        "/executions/trigger",
        json={
            "workflow_slug": workflow_slug,
            "input_data": {"message": "Say hello in one sentence."},
        },
    )
    assert resp.status_code in (200, 201, 202), (
        f"Trigger failed with {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    execution_id = body.get("execution_id") or body.get("id")
    assert execution_id, f"No execution_id in trigger response: {body}"

    # Step 2: Poll until completed or failed (or timeout)
    deadline = time.time() + POLL_TIMEOUT
    status = None
    final_data = None

    while time.time() < deadline:
        poll = http.get(f"/executions/{execution_id}")
        assert poll.status_code == 200, (
            f"GET /executions/{execution_id} returned {poll.status_code}: {poll.text}"
        )
        final_data = poll.json()
        status = final_data.get("status")
        if status in ("completed", "failed"):
            break
        time.sleep(POLL_INTERVAL)
    else:
        pytest.fail(
            f"Execution {execution_id} timed out after {POLL_TIMEOUT}s. "
            f"Last status: {status!r}. Data: {final_data}"
        )

    # Step 3: Assert the execution completed successfully
    assert status == "completed", (
        f"Expected status 'completed', got '{status}'. Full data: {final_data}"
    )

    # Step 4: Assert at least one step produced a non-empty LLM reply
    steps = final_data.get("steps", [])
    assert len(steps) > 0, (
        f"Expected at least one step in execution result, got none. Data: {final_data}"
    )

    # Find the 'greet' step (or fall back to first step)
    greet_step = next(
        (
            s
            for s in steps
            if s.get("step_id") == "greet" or s.get("step_name") == "greet"
        ),
        steps[0],
    )
    assert greet_step.get("status") == "completed", (
        f"Step 'greet' did not complete. Step data: {greet_step}"
    )

    output = greet_step.get("output") or {}

    # Accept any key that carries the LLM text output
    reply_value = None
    for key in ("reply", "content", "text", "output", "response", "result"):
        if key in output and output[key]:
            reply_value = output[key]
            break

    # Fall back to first non-empty value in the output dict
    if reply_value is None and output:
        reply_value = next((v for v in output.values() if v), None)

    assert reply_value, (
        f"Expected a non-empty LLM reply in step output, "
        f"got: {output!r}. Full step: {greet_step}"
    )
