"""Tests for WorkflowParser — written first (TDD)."""

import pytest
from flowforge.compiler.parser import (
    WorkflowParser,
    WorkflowDef,
    TriggerDef,
    StepDef,
    FallbackDef,
    GateRule,
)

FULL_EXAMPLE_YAML = """
workflow:
  name: Customer Service
  slug: customer-service
  version: 1
  tenant_id: acme
  trigger:
    type: email_received
    config:
      mailbox: support@acme.com
    output: [sender, subject, body]
  steps:
    - id: lookup_customer
      name: Look Up Customer
      type: tool
      tool: "mcp://crm-service/customer-lookup"
      input:
        email: "{{trigger.sender}}"
      output: [customer_id, name, tier]
      next: classify

    - id: classify
      name: Classify Intent
      type: tool
      tool: "mcp://ml-services/intent-classifier"
      input:
        text: "{{trigger.body}}"
      output: [intent, intent_confidence]
      fallback:
        when: "intent_confidence < 0.85"
        agent: classifier-agent
        input:
          text: "{{trigger.body}}"
        output: [intent]
      next: route

    - id: route
      name: Route by Intent
      type: router
      on: "{{classify.intent}}"
      routes:
        password_reset: handle_password
        technical: tech_diagnosis
      default: general_response

    - id: handle_password
      name: Handle Password Reset
      type: deterministic
      operation: render_template
      template: password_reset
      template_vars:
        name: "{{lookup_customer.name}}"
      output: [draft_response]
      next: quality_gate

    - id: tech_diagnosis
      name: Technical Diagnosis
      type: agent
      agent: tech-support
      model: gpt-4o
      context:
        issue: "{{trigger.body}}"
        customer_name: "{{lookup_customer.name}}"
      output: [resolution]
      next: quality_gate

    - id: general_response
      name: General Response
      type: agent
      agent: general-agent
      context:
        body: "{{trigger.body}}"
      output: [resolution]
      next: quality_gate

    - id: quality_gate
      name: Quality Gate
      type: gate
      rules:
        - if: "len(draft_response) < 20"
          then: tech_diagnosis
          label: "Response too short"
        - if: "tier == 'enterprise'"
          then: tech_diagnosis
          label: "VIP escalation"
      default: send_reply

    - id: send_reply
      name: Send Reply
      type: output
      action: "mcp://email-service/send"
      input:
        to: "{{trigger.sender}}"
        subject: "Re: {{trigger.subject}}"
        body: "{{tech_diagnosis.resolution}}"
"""

MINIMAL_YAML = """
workflow:
  name: Simple Workflow
  trigger:
    type: manual
    output: [input_text]
  steps:
    - id: step1
      name: Step One
      type: output
      action: "mcp://some-service/action"
"""

NO_SLUG_YAML = """
workflow:
  name: My Fancy Workflow
  trigger:
    type: manual
    output: []
  steps:
    - id: step1
      name: Step One
      type: output
      action: "mcp://some-service/action"
"""

INVALID_YAML = """
workflow:
  name: [invalid
"""


@pytest.fixture
def parser():
    return WorkflowParser()


def test_parse_returns_workflow_def(parser):
    """parse() should return a WorkflowDef instance."""
    result = parser.parse(FULL_EXAMPLE_YAML)
    assert isinstance(result, WorkflowDef)


def test_parse_trigger(parser):
    """Trigger fields should be correctly parsed."""
    result = parser.parse(FULL_EXAMPLE_YAML)
    trigger = result.trigger
    assert isinstance(trigger, TriggerDef)
    assert trigger.type == "email_received"
    assert trigger.config == {"mailbox": "support@acme.com"}
    assert trigger.output == ["sender", "subject", "body"]


def test_parse_tool_step(parser):
    """Tool step fields should be correctly parsed."""
    result = parser.parse(FULL_EXAMPLE_YAML)
    step = result.steps[0]  # lookup_customer
    assert isinstance(step, StepDef)
    assert step.id == "lookup_customer"
    assert step.name == "Look Up Customer"
    assert step.step_type == "tool"
    assert step.tool_uri == "mcp://crm-service/customer-lookup"
    assert step.input_mapping == {"email": "{{trigger.sender}}"}
    assert step.output_vars == ["customer_id", "name", "tier"]
    assert step.next_step == "classify"


def test_parse_tool_with_fallback(parser):
    """FallbackDef should be parsed from the fallback block."""
    result = parser.parse(FULL_EXAMPLE_YAML)
    step = result.steps[1]  # classify
    assert step.id == "classify"
    assert step.fallback is not None
    fallback = step.fallback
    assert isinstance(fallback, FallbackDef)
    assert fallback.when == "intent_confidence < 0.85"
    assert fallback.agent == "classifier-agent"
    assert fallback.input == {"text": "{{trigger.body}}"}
    assert fallback.output == ["intent"]


def test_parse_router_step(parser):
    """Router step fields should be correctly parsed."""
    result = parser.parse(FULL_EXAMPLE_YAML)
    step = result.steps[2]  # route
    assert step.id == "route"
    assert step.step_type == "router"
    assert step.route_on == "{{classify.intent}}"
    assert step.routes == {"password_reset": "handle_password", "technical": "tech_diagnosis"}
    assert step.default_target == "general_response"


def test_parse_gate_step(parser):
    """Gate step rules should be parsed as GateRule objects."""
    result = parser.parse(FULL_EXAMPLE_YAML)
    step = result.steps[6]  # quality_gate
    assert step.id == "quality_gate"
    assert step.step_type == "gate"
    assert len(step.rules) == 2
    rule0 = step.rules[0]
    assert isinstance(rule0, GateRule)
    assert rule0.condition == "len(draft_response) < 20"
    assert rule0.target == "tech_diagnosis"
    assert rule0.label == "Response too short"
    rule1 = step.rules[1]
    assert rule1.condition == "tier == 'enterprise'"
    assert rule1.target == "tech_diagnosis"
    assert rule1.label == "VIP escalation"
    assert step.default_target == "send_reply"


def test_parse_deterministic_step(parser):
    """Deterministic step fields should be correctly parsed."""
    result = parser.parse(FULL_EXAMPLE_YAML)
    step = result.steps[3]  # handle_password
    assert step.id == "handle_password"
    assert step.step_type == "deterministic"
    assert step.operation == "render_template"
    assert step.template == "password_reset"
    assert step.template_vars == {"name": "{{lookup_customer.name}}"}
    assert step.output_vars == ["draft_response"]
    assert step.next_step == "quality_gate"


def test_parse_agent_step(parser):
    """Agent step fields should be correctly parsed."""
    result = parser.parse(FULL_EXAMPLE_YAML)
    step = result.steps[4]  # tech_diagnosis
    assert step.id == "tech_diagnosis"
    assert step.step_type == "agent"
    assert step.agent_slug == "tech-support"
    assert step.model == "gpt-4o"
    assert step.context_mapping == {
        "issue": "{{trigger.body}}",
        "customer_name": "{{lookup_customer.name}}",
    }
    assert step.output_vars == ["resolution"]
    assert step.next_step == "quality_gate"


def test_parse_output_step(parser):
    """Output step fields should be correctly parsed."""
    result = parser.parse(FULL_EXAMPLE_YAML)
    step = result.steps[7]  # send_reply
    assert step.id == "send_reply"
    assert step.step_type == "output"
    assert step.action_uri == "mcp://email-service/send"
    assert step.input_mapping == {
        "to": "{{trigger.sender}}",
        "subject": "Re: {{trigger.subject}}",
        "body": "{{tech_diagnosis.resolution}}",
    }


def test_slug_auto_generated(parser):
    """When no slug is in YAML, it should be auto-generated from the name."""
    result = parser.parse(NO_SLUG_YAML)
    assert result.slug == "my-fancy-workflow"


def test_slug_explicit_is_preserved(parser):
    """When slug is in YAML, it should be used as-is."""
    result = parser.parse(FULL_EXAMPLE_YAML)
    assert result.slug == "customer-service"


def test_parse_invalid_yaml_raises(parser):
    """Malformed YAML should raise an exception."""
    with pytest.raises(Exception):
        parser.parse(INVALID_YAML)


def test_parse_workflow_metadata(parser):
    """Top-level workflow metadata fields are parsed correctly."""
    result = parser.parse(FULL_EXAMPLE_YAML)
    assert result.name == "Customer Service"
    assert result.version == 1
    assert result.tenant_id == "acme"


def test_parse_all_steps_present(parser):
    """All 8 steps from the YAML should be parsed."""
    result = parser.parse(FULL_EXAMPLE_YAML)
    assert len(result.steps) == 8
    step_ids = [s.id for s in result.steps]
    assert "lookup_customer" in step_ids
    assert "classify" in step_ids
    assert "route" in step_ids
    assert "handle_password" in step_ids
    assert "tech_diagnosis" in step_ids
    assert "general_response" in step_ids
    assert "quality_gate" in step_ids
    assert "send_reply" in step_ids


def test_parse_default_version(parser):
    """When version is not specified, it defaults to 1."""
    result = parser.parse(MINIMAL_YAML)
    assert result.version == 1
