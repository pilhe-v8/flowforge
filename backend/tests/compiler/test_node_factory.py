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
