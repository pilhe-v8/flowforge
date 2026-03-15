"""Tests for WorkflowValidator — written first (TDD)."""

import pytest
from flowforge.compiler.parser import (
    WorkflowParser,
    WorkflowDef,
    TriggerDef,
    StepDef,
    GateRule,
    FallbackDef,
)
from flowforge.compiler.validator import WorkflowValidator, ValidationError


# ── Fixtures ────────────────────────────────────────────────────────────────

TOOL_CATALOGUE = {
    "mcp://crm-service/customer-lookup": {},
    "mcp://ml-services/intent-classifier": {},
    "mcp://email-service/send": {},
}

AGENT_PROFILES = {
    "classifier-agent": {},
    "tech-support": {},
    "general-agent": {},
}


def make_validator():
    return WorkflowValidator(TOOL_CATALOGUE, AGENT_PROFILES)


def simple_workflow(steps: list[StepDef]) -> WorkflowDef:
    return WorkflowDef(
        name="Test",
        slug="test",
        version=1,
        description="",
        tenant_id="t1",
        trigger=TriggerDef(
            type="manual",
            config={},
            output=["sender", "body"],
        ),
        steps=steps,
    )


# ── Tests ────────────────────────────────────────────────────────────────────


def test_valid_workflow_no_errors():
    """A complete valid workflow should produce zero validation errors."""
    parser = WorkflowParser()
    from tests.compiler.test_parser import FULL_EXAMPLE_YAML

    wf = parser.parse(FULL_EXAMPLE_YAML)
    validator = WorkflowValidator(TOOL_CATALOGUE, AGENT_PROFILES)
    errors = validator.validate(wf)
    assert errors == []


def test_missing_tool_produces_error():
    """A tool step referencing a nonexistent tool URI should produce an error."""
    step = StepDef(
        id="s1",
        name="S1",
        step_type="tool",
        tool_uri="mcp://unknown/tool",
        input_mapping={},
        output_vars=["out"],
        next_step=None,
    )
    wf = simple_workflow([step])
    errors = make_validator().validate(wf)
    assert any(e.field == "tool" and "not found" in e.message for e in errors)


def test_missing_agent_produces_error():
    """An agent step referencing a nonexistent profile should produce an error."""
    step = StepDef(
        id="s1",
        name="S1",
        step_type="agent",
        agent_slug="nonexistent-agent",
        output_vars=["out"],
    )
    wf = simple_workflow([step])
    errors = make_validator().validate(wf)
    assert any(e.field == "agent" and "not found" in e.message for e in errors)


def test_invalid_next_step_produces_error():
    """A next_step pointing to a nonexistent step ID should produce an error."""
    step = StepDef(
        id="s1",
        name="S1",
        step_type="tool",
        tool_uri="mcp://crm-service/customer-lookup",
        output_vars=["out"],
        next_step="nonexistent_step",
    )
    wf = simple_workflow([step])
    errors = make_validator().validate(wf)
    assert any(e.field == "next" and "not found" in e.message for e in errors)


def test_invalid_route_target_produces_error():
    """A router step with a route pointing to a nonexistent step should produce an error."""
    router = StepDef(
        id="rt",
        name="Router",
        step_type="router",
        route_on="{{trigger.body}}",
        routes={"val_a": "step_a", "val_b": "missing_step"},
    )
    step_a = StepDef(id="step_a", name="A", step_type="output", action_uri="mcp://svc/act")
    wf = simple_workflow([router, step_a])
    errors = make_validator().validate(wf)
    assert any("missing_step" in e.message for e in errors)


def test_invalid_gate_target_produces_error():
    """A gate rule target that doesn't exist should produce an error."""
    gate = StepDef(
        id="g1",
        name="Gate",
        step_type="gate",
        rules=[GateRule(condition="x == 1", target="nonexistent", label="bad")],
        default_target="end_step",
    )
    end_step = StepDef(id="end_step", name="End", step_type="output", action_uri="mcp://svc/act")
    wf = simple_workflow([gate, end_step])
    errors = make_validator().validate(wf)
    assert any("nonexistent" in e.message for e in errors)


def test_variable_available_upstream():
    """A variable produced by an upstream step should not produce an error."""
    producer = StepDef(
        id="lookup",
        name="Lookup",
        step_type="tool",
        tool_uri="mcp://crm-service/customer-lookup",
        input_mapping={"email": "{{trigger.sender}}"},
        output_vars=["name"],
        next_step="consumer",
    )
    consumer = StepDef(
        id="consumer",
        name="Consumer",
        step_type="agent",
        agent_slug="tech-support",
        context_mapping={"customer_name": "{{lookup.name}}"},
        output_vars=["result"],
    )
    wf = simple_workflow([producer, consumer])
    errors = make_validator().validate(wf)
    assert errors == []


def test_variable_not_upstream_produces_error():
    """Referencing a variable from a step that is NOT upstream should produce an error."""
    step_a = StepDef(
        id="step_a",
        name="A",
        step_type="agent",
        agent_slug="tech-support",
        # References step_b which comes AFTER, not before
        context_mapping={"data": "{{step_b.result}}"},
        output_vars=["out_a"],
        next_step="step_b",
    )
    step_b = StepDef(
        id="step_b",
        name="B",
        step_type="output",
        action_uri="mcp://email-service/send",
        input_mapping={},
        output_vars=["result"],
    )
    wf = simple_workflow([step_a, step_b])
    errors = make_validator().validate(wf)
    assert any("step_b.result" in e.message for e in errors)


def test_trigger_vars_available():
    """Variables from the trigger output should always be available."""
    step = StepDef(
        id="s1",
        name="S1",
        step_type="tool",
        tool_uri="mcp://crm-service/customer-lookup",
        input_mapping={"email": "{{trigger.sender}}"},
        output_vars=["out"],
    )
    wf = simple_workflow([step])
    errors = make_validator().validate(wf)
    assert errors == []


def test_fallback_agent_missing_produces_error():
    """A fallback that references a nonexistent agent should produce an error."""
    step = StepDef(
        id="s1",
        name="S1",
        step_type="tool",
        tool_uri="mcp://crm-service/customer-lookup",
        output_vars=["out"],
        fallback=FallbackDef(
            when="score < 0.5",
            agent="nonexistent-fallback-agent",
            input={},
            output=[],
        ),
    )
    wf = simple_workflow([step])
    errors = make_validator().validate(wf)
    assert any("fallback.agent" in e.field for e in errors)


def test_invalid_default_target_produces_error():
    """A default_target pointing to a nonexistent step should produce an error."""
    router = StepDef(
        id="rt",
        name="Router",
        step_type="router",
        route_on="{{trigger.body}}",
        routes={},
        default_target="ghost_step",
    )
    wf = simple_workflow([router])
    errors = make_validator().validate(wf)
    assert any("ghost_step" in e.message for e in errors)
