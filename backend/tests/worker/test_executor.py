"""Tests for Executor — stateless workflow graph runner."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from flowforge.worker.executor import Executor, ExecutionResult
from flowforge.worker.session_manager import Session


def make_session(state=None, step_count=0):
    return Session(
        id="session-abc",
        state=state or {},
        step_count=step_count,
    )


def make_graph(result_state: dict):
    """Create a mock LangGraph-like graph that returns result_state on ainvoke."""
    graph = AsyncMock()
    graph.ainvoke = AsyncMock(return_value=result_state)
    return graph


@pytest.mark.asyncio
async def test_executor_merges_state_with_trigger():
    """Executor.run should merge session state and trigger into the invocation state."""
    session = make_session(state={"existing": "value"})
    graph = make_graph({"existing": "value", "trigger": {"msg": "hello"}, "_audit_trail": []})

    await Executor.run(graph, session, {"msg": "hello"})

    call_args = graph.ainvoke.call_args[0][0]
    assert call_args["existing"] == "value"
    assert call_args["trigger"] == {"msg": "hello"}


@pytest.mark.asyncio
async def test_executor_passes_session_id_in_config():
    """Executor.run should pass session_id in the LangGraph config."""
    session = make_session()
    graph = make_graph({"_audit_trail": []})

    await Executor.run(graph, session, {})

    config = graph.ainvoke.call_args[1]["config"]
    assert config["configurable"]["session_id"] == "session-abc"


@pytest.mark.asyncio
async def test_executor_increments_step_count():
    """Executor.run should increment session.step_count by 1."""
    session = make_session(step_count=5)
    graph = make_graph({"_audit_trail": []})

    await Executor.run(graph, session, {})

    assert session.step_count == 6


@pytest.mark.asyncio
async def test_executor_updates_session_state():
    """Executor.run should update session.state to the graph result state."""
    session = make_session(state={"old": True})
    new_state = {"new": True, "_audit_trail": []}
    graph = make_graph(new_state)

    await Executor.run(graph, session, {})

    assert session.state == new_state


@pytest.mark.asyncio
async def test_executor_sets_updated_at():
    """Executor.run should set session.updated_at to approximately now."""
    session = make_session()
    assert session.updated_at is None
    graph = make_graph({"_audit_trail": []})

    before = datetime.utcnow()
    await Executor.run(graph, session, {})
    after = datetime.utcnow()

    assert session.updated_at is not None
    assert before <= session.updated_at <= after


@pytest.mark.asyncio
async def test_executor_returns_execution_result():
    """Executor.run should return an ExecutionResult dataclass."""
    session = make_session()
    graph = make_graph({"_audit_trail": []})

    result = await Executor.run(graph, session, {})

    assert isinstance(result, ExecutionResult)
    assert result.session_id == "session-abc"


@pytest.mark.asyncio
async def test_executor_steps_executed_from_audit_trail():
    """ExecutionResult.steps_executed should reflect the _audit_trail list."""
    session = make_session()
    audit = [{"step_id": "step1"}, {"step_id": "step2"}]
    graph = make_graph({"_audit_trail": audit})

    result = await Executor.run(graph, session, {})

    assert result.steps_executed == audit


@pytest.mark.asyncio
async def test_executor_steps_executed_empty_when_no_audit_trail():
    """ExecutionResult.steps_executed should be empty list when no _audit_trail."""
    session = make_session()
    graph = make_graph({"some_key": "value"})  # no _audit_trail

    result = await Executor.run(graph, session, {})

    assert result.steps_executed == []


@pytest.mark.asyncio
async def test_execution_result_dataclass_fields():
    """ExecutionResult should be a proper dataclass with expected fields."""
    result = ExecutionResult(
        session_id="s1",
        final_state={"key": "val"},
        steps_executed=[{"step_id": "x"}],
    )
    assert result.session_id == "s1"
    assert result.final_state == {"key": "val"}
    assert result.steps_executed == [{"step_id": "x"}]
