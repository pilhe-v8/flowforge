"""Tests for GraphBuilder — written first (TDD)."""

import pytest
from flowforge.compiler.parser import WorkflowDef, TriggerDef, StepDef
from flowforge.compiler.node_factory import NodeFactory
from flowforge.compiler.graph_builder import GraphBuilder


def make_builder() -> GraphBuilder:
    return GraphBuilder(NodeFactory())


def linear_workflow() -> WorkflowDef:
    """A simple 2-step workflow: tool → output."""
    return WorkflowDef(
        name="Linear",
        slug="linear",
        version=1,
        description="",
        tenant_id="t1",
        trigger=TriggerDef(type="manual", config={}, output=["input_text"]),
        steps=[
            StepDef(
                id="process",
                name="Process",
                step_type="tool",
                tool_uri="mcp://svc/tool",
                input_mapping={"text": "{{trigger.input_text}}"},
                output_vars=["result"],
                next_step="done",
            ),
            StepDef(
                id="done",
                name="Done",
                step_type="output",
                action_uri="mcp://svc/output",
                input_mapping={"data": "{{process.result}}"},
            ),
        ],
    )


def router_workflow() -> WorkflowDef:
    """A 3-step workflow: router → output_a | output_b, routing on trigger var."""
    return WorkflowDef(
        name="Router WF",
        slug="router-wf",
        version=1,
        description="",
        tenant_id="t1",
        trigger=TriggerDef(type="manual", config={}, output=["intent"]),
        steps=[
            StepDef(
                id="route",
                name="Route",
                step_type="router",
                # Route directly on trigger output to avoid tool-executor dependency
                route_on="{{trigger.intent}}",
                routes={"billing": "out_billing", "tech": "out_tech"},
                default_target="out_tech",
            ),
            StepDef(
                id="out_billing",
                name="Billing Output",
                step_type="output",
                action_uri="mcp://svc/billing",
                input_mapping={},
            ),
            StepDef(
                id="out_tech",
                name="Tech Output",
                step_type="output",
                action_uri="mcp://svc/tech",
                input_mapping={},
            ),
        ],
    )


# ── Tests ────────────────────────────────────────────────────────────────────


def test_build_returns_compiled_graph():
    """build() should return a non-None compiled LangGraph graph."""
    builder = make_builder()
    wf = linear_workflow()
    graph = builder.build(wf)
    assert graph is not None


def test_graph_has_trigger_node():
    """The built graph should contain a 'trigger' node."""
    builder = make_builder()
    wf = linear_workflow()
    graph = builder.build(wf)
    # LangGraph compiled graphs expose their node structure
    assert "trigger" in graph.get_graph().nodes


def test_graph_has_all_step_nodes():
    """All step IDs should be present as nodes in the compiled graph."""
    builder = make_builder()
    wf = linear_workflow()
    graph = builder.build(wf)
    node_ids = set(graph.get_graph().nodes.keys())
    assert "process" in node_ids
    assert "done" in node_ids


async def test_simple_linear_workflow_runs():
    """A linear tool→output workflow should run with ainvoke and produce _audit_trail."""
    builder = make_builder()
    wf = linear_workflow()
    graph = builder.build(wf)
    initial_state = {"trigger": {"input_text": "hello world"}}
    final_state = await graph.ainvoke(initial_state)
    assert "_audit_trail" in final_state
    assert len(final_state["_audit_trail"]) >= 1


async def test_router_workflow_routes_correctly():
    """Router step should route to 'out_billing' when intent='billing'."""
    builder = make_builder()
    wf = router_workflow()
    graph = builder.build(wf)
    initial_state = {
        "trigger": {"intent": "billing"},
    }
    final_state = await graph.ainvoke(initial_state)
    assert "_audit_trail" in final_state
    # The billing output node should have run
    audit_step_ids = [entry["step_id"] for entry in final_state["_audit_trail"]]
    assert "out_billing" in audit_step_ids


async def test_router_workflow_routes_to_default():
    """Router step should route to default when value doesn't match any route."""
    builder = make_builder()
    wf = router_workflow()
    graph = builder.build(wf)
    initial_state = {
        "trigger": {"intent": "something_unknown"},
    }
    final_state = await graph.ainvoke(initial_state)
    audit_step_ids = [entry["step_id"] for entry in final_state["_audit_trail"]]
    assert "out_tech" in audit_step_ids
