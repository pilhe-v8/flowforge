"""Tests for NodeFactory."""

import pytest


@pytest.mark.asyncio
async def test_agent_node_calls_llm_without_profile_loader():
    """Agent node must call LLM even when profile_loader is None."""
    from unittest.mock import AsyncMock, MagicMock

    mock_llm = AsyncMock()
    mock_llm.chat.return_value = MagicMock(
        content="Hello from LLM",
        input_tokens=10,
        output_tokens=5,
    )
    from flowforge.compiler.node_factory import NodeFactory
    from flowforge.compiler.parser import StepDef

    factory = NodeFactory(llm_client=mock_llm, profile_loader=None)
    step = StepDef(
        id="greet",
        name="Greet",
        step_type="agent",
        agent_slug="any-agent",
        context_mapping={"message": "hi"},
        output_vars=["reply"],
    )
    node_fn = factory.build_node(step)
    state = {"trigger": {"message": "hi"}}
    result = await node_fn(state)

    mock_llm.chat.assert_called_once()
    assert result["greet"]["reply"] == "Hello from LLM"
    # Also verify audit trail entry was appended
    trail = result.get("_audit_trail", [])
    assert len(trail) == 1
    assert trail[0]["input_tokens"] == 10
    assert trail[0]["output_tokens"] == 5
    assert trail[0]["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_agent_node_uses_inline_system_prompt():
    """When step.system_prompt is set, it is used directly — profile_loader is NOT called."""
    from unittest.mock import AsyncMock, MagicMock

    mock_llm = AsyncMock()
    mock_llm.chat.return_value = MagicMock(
        content="Rewritten text",
        input_tokens=12,
        output_tokens=8,
    )
    mock_profiles = AsyncMock()

    from flowforge.compiler.node_factory import NodeFactory
    from flowforge.compiler.parser import StepDef

    factory = NodeFactory(llm_client=mock_llm, profile_loader=mock_profiles)
    step = StepDef(
        id="rewrite",
        name="Rewrite",
        step_type="agent",
        agent_slug=None,
        system_prompt="You are a writing assistant. Rewrite to be concise.",
        model="default",
        context_mapping={"text": "{{trigger.input_data}}"},
        output_vars=["reply"],
    )
    node_fn = factory.build_node(step)
    state = {"trigger": {"input_data": "This is some verbose text."}}
    result = await node_fn(state)

    # profile_loader.load() must NOT have been called
    mock_profiles.load.assert_not_called()

    # LLM was called with our system prompt as the system message
    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    assert messages[0]["role"] == "system"
    assert "writing assistant" in messages[0]["content"]
    assert messages[1]["role"] == "user"

    # Output is stored under "reply"
    assert result["rewrite"]["reply"] == "Rewritten text"

    # Audit trail entry present and correct
    trail = result["_audit_trail"]
    assert trail[0]["step_type"] == "agent"
    assert trail[0]["input_tokens"] == 12
    assert trail[0]["output_tokens"] == 8


@pytest.mark.asyncio
async def test_agent_node_inline_stores_output_under_declared_vars():
    """When system_prompt is set, the LLM response is stored under every declared output var."""
    from unittest.mock import AsyncMock, MagicMock

    mock_llm = AsyncMock()
    mock_llm.chat.return_value = MagicMock(
        content="Done",
        input_tokens=5,
        output_tokens=3,
    )
    from flowforge.compiler.node_factory import NodeFactory
    from flowforge.compiler.parser import StepDef

    factory = NodeFactory(llm_client=mock_llm)
    step = StepDef(
        id="s1",
        name="S1",
        step_type="agent",
        system_prompt="Be helpful.",
        output_vars=["reply"],
    )
    node_fn = factory.build_node(step)
    result = await node_fn({"trigger": {}})
    assert result["s1"]["reply"] == "Done"


@pytest.mark.asyncio
async def test_output_action_log_does_not_call_tool_executor_and_records_audit():
    """Output steps with action 'log' are built-in and must not route via ToolExecutor."""
    from unittest.mock import AsyncMock

    from flowforge.compiler.node_factory import NodeFactory
    from flowforge.compiler.parser import StepDef

    tool_executor = AsyncMock()
    factory = NodeFactory(tool_executor=tool_executor)

    step = StepDef(
        id="out",
        name="Out",
        step_type="output",
        action_uri="log",
        input_mapping={"message": "hello"},
    )

    node_fn = factory.build_node(step)
    state = {"trigger": {}, "_audit_trail": []}
    result = await node_fn(state)

    tool_executor.execute.assert_not_called()
    assert result["out"] == {"message": "hello"}
    assert result["_audit_trail"][-1]["step_id"] == "out"
    assert result["_audit_trail"][-1]["type"] == "output"
