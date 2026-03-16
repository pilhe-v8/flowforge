"""
Task 7 example content tests.

Tests MCP server logic (via _impl functions), agent profiles, Jinja2 templates,
and the customer-service example YAML.
"""

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml
from jinja2.sandbox import SandboxedEnvironment

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent.parent  # /…/flowforge


def load_module(path: Path, module_name: str):
    """Dynamically load a Python file as a module."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def run(coro):
    """Run a coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# MCP server: customer-lookup
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def customer_lookup_mod():
    return load_module(
        REPO_ROOT / "mcp-tools" / "customer-lookup" / "server.py",
        "customer_lookup_server",
    )


class TestCustomerLookup:
    def test_known_email_alice(self, customer_lookup_mod):
        result = run(customer_lookup_mod._customer_lookup_impl("alice@example.com"))
        assert result["customer_id"] == "cust-001"
        assert result["name"] == "Alice Johnson"
        assert result["tier"] == "enterprise"
        assert len(result["past_tickets"]) == 3

    def test_known_email_bob(self, customer_lookup_mod):
        result = run(customer_lookup_mod._customer_lookup_impl("bob@startup.io"))
        assert result["customer_id"] == "cust-042"
        assert result["tier"] == "pro"
        assert len(result["past_tickets"]) == 2

    def test_known_email_carol(self, customer_lookup_mod):
        result = run(customer_lookup_mod._customer_lookup_impl("carol@freelance.dev"))
        assert result["tier"] == "free"
        assert result["past_tickets"] == []

    def test_unknown_email_returns_guest(self, customer_lookup_mod):
        result = run(customer_lookup_mod._customer_lookup_impl("nobody@unknown.org"))
        assert result["customer_id"] == "guest"
        assert result["tier"] == "free"
        assert result["past_tickets"] == []

    def test_case_insensitive(self, customer_lookup_mod):
        result = run(customer_lookup_mod._customer_lookup_impl("ALICE@EXAMPLE.COM"))
        assert result["customer_id"] == "cust-001"

    def test_ticket_fields(self, customer_lookup_mod):
        result = run(customer_lookup_mod._customer_lookup_impl("alice@example.com"))
        ticket = result["past_tickets"][0]
        assert "id" in ticket
        assert "subject" in ticket
        assert "status" in ticket
        assert "created_at" in ticket


# ---------------------------------------------------------------------------
# MCP server: sentiment-analysis
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def sentiment_mod():
    return load_module(
        REPO_ROOT / "mcp-tools" / "sentiment-analysis" / "server.py",
        "sentiment_server",
    )


class TestSentimentAnalysis:
    def test_angry_text(self, sentiment_mod):
        result = run(
            sentiment_mod._sentiment_analysis_impl(
                "This is absolutely ridiculous and unacceptable! I am furious!"
            )
        )
        assert result["sentiment"] == "angry"
        assert 0.0 <= result["confidence"] <= 1.0

    def test_positive_text(self, sentiment_mod):
        result = run(
            sentiment_mod._sentiment_analysis_impl(
                "Thank you so much! This is amazing, I love it. Great work!"
            )
        )
        assert result["sentiment"] == "positive"
        assert result["confidence"] > 0.5

    def test_negative_text(self, sentiment_mod):
        result = run(
            sentiment_mod._sentiment_analysis_impl(
                "The app is broken and I cannot login. There is a bug in the system."
            )
        )
        assert result["sentiment"] == "negative"
        assert result["confidence"] > 0.5

    def test_neutral_text(self, sentiment_mod):
        result = run(
            sentiment_mod._sentiment_analysis_impl("Hello, I would like to know my account status.")
        )
        assert result["sentiment"] == "neutral"
        assert result["confidence"] == 0.5

    def test_confidence_is_float(self, sentiment_mod):
        result = run(sentiment_mod._sentiment_analysis_impl("great service"))
        assert isinstance(result["confidence"], float)

    def test_confidence_bounds(self, sentiment_mod):
        result = run(
            sentiment_mod._sentiment_analysis_impl(
                "amazing excellent wonderful fantastic love happy great awesome brilliant perfect"
            )
        )
        assert result["confidence"] <= 1.0
        assert result["confidence"] >= 0.0


# ---------------------------------------------------------------------------
# MCP server: email-sender
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def email_mod():
    return load_module(
        REPO_ROOT / "mcp-tools" / "email-sender" / "server.py",
        "email_sender_server",
    )


class TestSendEmail:
    def test_returns_message_id_and_status(self, email_mod):
        result = run(
            email_mod._send_email_impl(
                to="customer@example.com",
                subject="Re: Your ticket",
                body="Hello, we have resolved your issue.",
            )
        )
        assert result["status"] == "sent"
        assert "message_id" in result
        assert len(result["message_id"]) == 36  # UUID format

    def test_message_id_is_uuid(self, email_mod):
        import uuid

        result = run(
            email_mod._send_email_impl(
                to="test@test.com",
                subject="Test",
                body="Test body",
            )
        )
        # Should not raise
        uuid.UUID(result["message_id"])

    def test_each_call_unique_message_id(self, email_mod):
        r1 = run(email_mod._send_email_impl("a@b.com", "S1", "B1"))
        r2 = run(email_mod._send_email_impl("a@b.com", "S2", "B2"))
        assert r1["message_id"] != r2["message_id"]


# ---------------------------------------------------------------------------
# Agent profiles
# ---------------------------------------------------------------------------
AGENT_PROFILES_DIR = REPO_ROOT / "agent-profiles"

REQUIRED_SECTIONS = ["# ", "## Role", "## Context", "## Guidelines", "## Output"]


@pytest.mark.parametrize(
    "filename",
    ["classifier.md", "tech-support.md", "reply-drafter.md"],
)
def test_agent_profile_exists(filename):
    path = AGENT_PROFILES_DIR / filename
    assert path.exists(), f"{filename} not found"


@pytest.mark.parametrize(
    "filename",
    ["classifier.md", "tech-support.md", "reply-drafter.md"],
)
def test_agent_profile_required_sections(filename):
    content = (AGENT_PROFILES_DIR / filename).read_text()
    for section in REQUIRED_SECTIONS:
        assert section in content, f"Missing section '{section}' in {filename}"


def test_classifier_mentions_all_intents():
    content = (AGENT_PROFILES_DIR / "classifier.md").read_text()
    for intent in [
        "billing",
        "technical",
        "password_reset",
        "order_status",
        "complaint",
        "general",
    ]:
        assert intent in content, f"Intent '{intent}' missing from classifier.md"


def test_tech_support_mentions_enterprise():
    content = (AGENT_PROFILES_DIR / "tech-support.md").read_text()
    assert "enterprise" in content


def test_reply_drafter_mentions_all_sentiments():
    content = (AGENT_PROFILES_DIR / "reply-drafter.md").read_text()
    for sentiment in ["angry", "neutral", "positive"]:
        assert sentiment in content, f"Sentiment '{sentiment}' missing from reply-drafter.md"


# ---------------------------------------------------------------------------
# Jinja2 response templates
# ---------------------------------------------------------------------------
TEMPLATES_DIR = REPO_ROOT / "response-templates"


@pytest.fixture(scope="module")
def jinja_env():
    return SandboxedEnvironment()


def load_template(env, filename):
    source = (TEMPLATES_DIR / filename).read_text()
    return env.from_string(source)


class TestPasswordResetTemplate:
    def test_renders_with_name(self, jinja_env):
        tmpl = load_template(jinja_env, "password_reset.j2")
        output = tmpl.render(
            name="Alice",
            reset_link="https://example.com/reset/abc",
            expires_in=30,
        )
        assert "Alice" in output

    def test_renders_with_reset_link(self, jinja_env):
        tmpl = load_template(jinja_env, "password_reset.j2")
        output = tmpl.render(
            name="Alice",
            reset_link="https://example.com/reset/abc",
            expires_in=30,
        )
        assert "https://example.com/reset/abc" in output

    def test_renders_expires_in(self, jinja_env):
        tmpl = load_template(jinja_env, "password_reset.j2")
        output = tmpl.render(
            name="Alice",
            reset_link="https://example.com/reset/abc",
            expires_in=30,
        )
        assert "30" in output


class TestOrderStatusTemplate:
    def test_renders_with_name(self, jinja_env):
        tmpl = load_template(jinja_env, "order_status.j2")
        output = tmpl.render(
            name="Bob",
            order_id="ORD-123",
            status="Shipped",
            eta="2025-03-20",
        )
        assert "Bob" in output

    def test_renders_order_id(self, jinja_env):
        tmpl = load_template(jinja_env, "order_status.j2")
        output = tmpl.render(
            name="Bob",
            order_id="ORD-123",
            status="Shipped",
            eta="2025-03-20",
        )
        assert "ORD-123" in output

    def test_renders_eta_when_present(self, jinja_env):
        tmpl = load_template(jinja_env, "order_status.j2")
        output = tmpl.render(
            name="Bob",
            order_id="ORD-123",
            status="Shipped",
            eta="2025-03-20",
        )
        assert "2025-03-20" in output

    def test_omits_eta_when_none(self, jinja_env):
        tmpl = load_template(jinja_env, "order_status.j2")
        output = tmpl.render(
            name="Bob",
            order_id="ORD-123",
            status="Processing",
            eta=None,
        )
        assert "Estimated arrival" not in output


class TestBillingResponseTemplate:
    def test_renders_with_name(self, jinja_env):
        tmpl = load_template(jinja_env, "billing_response.j2")
        output = tmpl.render(
            name="Carol",
            invoice_id="INV-456",
            amount="99.99",
            due_date="2025-04-01",
        )
        assert "Carol" in output

    def test_renders_invoice_id(self, jinja_env):
        tmpl = load_template(jinja_env, "billing_response.j2")
        output = tmpl.render(
            name="Carol",
            invoice_id="INV-456",
            amount="99.99",
            due_date="2025-04-01",
        )
        assert "INV-456" in output

    def test_renders_amount(self, jinja_env):
        tmpl = load_template(jinja_env, "billing_response.j2")
        output = tmpl.render(
            name="Carol",
            invoice_id="INV-456",
            amount="99.99",
            due_date="2025-04-01",
        )
        assert "99.99" in output


# ---------------------------------------------------------------------------
# Example YAML: customer-service
# ---------------------------------------------------------------------------
EXAMPLES_DIR = REPO_ROOT / "examples"


@pytest.fixture(scope="module")
def customer_service_yaml():
    path = EXAMPLES_DIR / "customer-service.yaml"
    assert path.exists(), "customer-service.yaml not found"
    with open(path) as f:
        return yaml.safe_load(f)


class TestCustomerServiceYaml:
    def test_is_valid_yaml(self, customer_service_yaml):
        assert customer_service_yaml is not None

    def test_top_level_workflow_key(self, customer_service_yaml):
        assert "workflow" in customer_service_yaml

    def test_workflow_name(self, customer_service_yaml):
        assert customer_service_yaml["workflow"]["name"] == "Customer Service"

    def test_workflow_slug(self, customer_service_yaml):
        assert customer_service_yaml["workflow"]["slug"] == "customer-service"

    def test_workflow_has_steps(self, customer_service_yaml):
        assert "steps" in customer_service_yaml["workflow"]

    def test_step_count(self, customer_service_yaml):
        steps = customer_service_yaml["workflow"]["steps"]
        # The customer-service workflow defines 16 steps
        assert len(steps) == 16, f"Expected 16 steps, got {len(steps)}"

    def test_quality_gate_step_exists(self, customer_service_yaml):
        steps = customer_service_yaml["workflow"]["steps"]
        step_ids = {s["id"] for s in steps}
        assert "quality_gate" in step_ids

    def test_quality_gate_type_is_gate(self, customer_service_yaml):
        steps = customer_service_yaml["workflow"]["steps"]
        gate = next(s for s in steps if s["id"] == "quality_gate")
        assert gate["type"] == "gate"

    def test_trigger_defined(self, customer_service_yaml):
        assert "trigger" in customer_service_yaml["workflow"]
        assert customer_service_yaml["workflow"]["trigger"]["type"] == "email_received"
