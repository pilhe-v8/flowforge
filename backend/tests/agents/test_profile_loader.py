"""Tests for ProfileLoader and markdown helper functions."""

import pytest
from dataclasses import is_dataclass

from flowforge.agents.profile_loader import (
    AgentProfile,
    ProfileLoader,
    extract_h1,
    split_by_h2,
    parse_bullets,
    parse_examples,
)

# ---------------------------------------------------------------------------
# Sample markdown fixture
# ---------------------------------------------------------------------------

SAMPLE_MARKDOWN = """\
# Customer Support Agent

## Role
You are a helpful customer support agent.

## Context
You have access to order history and customer details.

## Guidelines
- Always greet the customer by name
- Be concise and polite
* Escalate unresolved issues

## Output
A short response to the customer query.

## Examples
Input: What is the status of my order?
Output: Your order #1234 is being processed.

Input: Can I return this item?
Output: Yes, you can return the item within 30 days.
"""


# ---------------------------------------------------------------------------
# extract_h1
# ---------------------------------------------------------------------------


class TestExtractH1:
    def test_extracts_first_h1(self):
        assert extract_h1(SAMPLE_MARKDOWN) == "Customer Support Agent"

    def test_returns_empty_when_no_h1(self):
        assert extract_h1("## Section\nNo H1 here") == ""

    def test_ignores_h2(self):
        assert extract_h1("## Not H1\n# Real Title\n") == "Real Title"

    def test_strips_whitespace(self):
        assert extract_h1("#   Padded Title   \n") == "Padded Title"

    def test_first_h1_wins(self):
        content = "# First\n# Second\n"
        assert extract_h1(content) == "First"


# ---------------------------------------------------------------------------
# split_by_h2
# ---------------------------------------------------------------------------


class TestSplitByH2:
    def test_parses_role_section(self):
        sections = split_by_h2(SAMPLE_MARKDOWN)
        assert "Role" in sections
        assert "You are a helpful customer support agent." in sections["Role"]

    def test_parses_multiple_sections(self):
        sections = split_by_h2(SAMPLE_MARKDOWN)
        assert set(sections.keys()) == {"Role", "Context", "Guidelines", "Output", "Examples"}

    def test_section_body_is_stripped(self):
        md = "## Section\n   trimmed body   \n"
        sections = split_by_h2(md)
        assert sections["Section"] == "trimmed body"

    def test_empty_section(self):
        md = "## Empty\n## Next\nhas content"
        sections = split_by_h2(md)
        assert sections["Empty"] == ""

    def test_text_before_first_h2_is_ignored(self):
        md = "Intro text\n## First\nfirst body"
        sections = split_by_h2(md)
        assert "First" in sections
        assert len(sections) == 1


# ---------------------------------------------------------------------------
# parse_bullets
# ---------------------------------------------------------------------------


class TestParseBullets:
    def test_dash_bullets(self):
        text = "- item one\n- item two\n"
        assert parse_bullets(text) == ["item one", "item two"]

    def test_asterisk_bullets(self):
        text = "* star one\n* star two"
        assert parse_bullets(text) == ["star one", "star two"]

    def test_mixed_bullets(self):
        text = "- dash\n* star"
        assert parse_bullets(text) == ["dash", "star"]

    def test_non_bullets_ignored(self):
        text = "Some prose\n- bullet\nMore prose"
        assert parse_bullets(text) == ["bullet"]

    def test_empty_text(self):
        assert parse_bullets("") == []

    def test_strips_bullet_content(self):
        text = "-   leading spaces  \n"
        assert parse_bullets(text) == ["leading spaces"]


# ---------------------------------------------------------------------------
# parse_examples
# ---------------------------------------------------------------------------


class TestParseExamples:
    def test_single_example(self):
        text = "Input: Hello\nOutput: Hi there"
        result = parse_examples(text)
        assert result == [{"input": "Hello", "output": "Hi there"}]

    def test_multiple_examples(self):
        text = (
            "Input: What is my order?\n"
            "Output: Order #1234 is being processed.\n"
            "\n"
            "Input: Can I return?\n"
            "Output: Yes, within 30 days."
        )
        result = parse_examples(text)
        assert len(result) == 2
        assert result[0]["input"] == "What is my order?"
        assert result[1]["output"] == "Yes, within 30 days."

    def test_empty_text(self):
        assert parse_examples("") == []

    def test_ignores_incomplete_pairs(self):
        # Input without Output
        text = "Input: orphan"
        result = parse_examples(text)
        assert result == []

    def test_strips_whitespace(self):
        text = "Input:   spaced   \nOutput:   spaced out   "
        result = parse_examples(text)
        assert result[0]["input"] == "spaced"
        assert result[0]["output"] == "spaced out"


# ---------------------------------------------------------------------------
# ProfileLoader.parse_markdown
# ---------------------------------------------------------------------------


class TestParseMarkdown:
    def test_returns_agent_profile(self):
        profile = ProfileLoader.parse_markdown(SAMPLE_MARKDOWN)
        assert isinstance(profile, AgentProfile)

    def test_name(self):
        profile = ProfileLoader.parse_markdown(SAMPLE_MARKDOWN)
        assert profile.name == "Customer Support Agent"

    def test_role_prompt(self):
        profile = ProfileLoader.parse_markdown(SAMPLE_MARKDOWN)
        assert "helpful customer support agent" in profile.role_prompt

    def test_context_description(self):
        profile = ProfileLoader.parse_markdown(SAMPLE_MARKDOWN)
        assert "order history" in profile.context_description

    def test_guidelines(self):
        profile = ProfileLoader.parse_markdown(SAMPLE_MARKDOWN)
        assert len(profile.guidelines) == 3
        assert "Always greet the customer by name" in profile.guidelines

    def test_output_description(self):
        profile = ProfileLoader.parse_markdown(SAMPLE_MARKDOWN)
        assert "short response" in profile.output_description

    def test_examples(self):
        profile = ProfileLoader.parse_markdown(SAMPLE_MARKDOWN)
        assert len(profile.examples) == 2
        assert profile.examples[0]["input"] == "What is the status of my order?"

    def test_default_model_is_none(self):
        profile = ProfileLoader.parse_markdown(SAMPLE_MARKDOWN)
        assert profile.default_model is None

    def test_is_dataclass(self):
        assert is_dataclass(AgentProfile)


# ---------------------------------------------------------------------------
# ProfileLoader.build_system_prompt
# ---------------------------------------------------------------------------


class TestBuildSystemPrompt:
    def test_includes_role_prompt(self):
        profile = AgentProfile(name="Bot", role_prompt="You are a bot.")
        prompt = ProfileLoader.build_system_prompt(profile)
        assert "You are a bot." in prompt

    def test_guidelines_included(self):
        profile = AgentProfile(
            name="Bot",
            role_prompt="Role.",
            guidelines=["Be concise", "Be polite"],
        )
        prompt = ProfileLoader.build_system_prompt(profile)
        assert "Guidelines:" in prompt
        assert "- Be concise" in prompt
        assert "- Be polite" in prompt

    def test_no_guidelines_section_when_empty(self):
        profile = AgentProfile(name="Bot", role_prompt="Role.", guidelines=[])
        prompt = ProfileLoader.build_system_prompt(profile)
        assert "Guidelines:" not in prompt

    def test_output_description_included(self):
        profile = AgentProfile(
            name="Bot",
            role_prompt="Role.",
            output_description="A JSON response.",
        )
        prompt = ProfileLoader.build_system_prompt(profile)
        assert "Expected output: A JSON response." in prompt

    def test_no_output_section_when_empty(self):
        profile = AgentProfile(name="Bot", role_prompt="Role.")
        prompt = ProfileLoader.build_system_prompt(profile)
        assert "Expected output" not in prompt

    def test_examples_included(self):
        profile = AgentProfile(
            name="Bot",
            role_prompt="Role.",
            examples=[{"input": "hi", "output": "hello"}],
        )
        prompt = ProfileLoader.build_system_prompt(profile)
        assert "Examples:" in prompt
        assert "Input: hi" in prompt
        assert "Output: hello" in prompt

    def test_no_examples_section_when_empty(self):
        profile = AgentProfile(name="Bot", role_prompt="Role.", examples=[])
        prompt = ProfileLoader.build_system_prompt(profile)
        assert "Examples:" not in prompt

    def test_full_profile(self):
        profile = ProfileLoader.parse_markdown(SAMPLE_MARKDOWN)
        prompt = ProfileLoader.build_system_prompt(profile)
        assert "You are a helpful customer support agent." in prompt
        assert "Guidelines:" in prompt
        assert "Examples:" in prompt
