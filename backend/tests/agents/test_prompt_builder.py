"""Tests for PromptBuilder."""

import json
import pytest

from flowforge.agents.profile_loader import AgentProfile
from flowforge.agents.prompt_builder import PromptBuilder


def make_profile(**kwargs) -> AgentProfile:
    defaults = dict(
        name="TestBot",
        role_prompt="You are a test bot.",
        guidelines=["Be helpful"],
    )
    defaults.update(kwargs)
    return AgentProfile(**defaults)


class TestBuildMessages:
    def test_returns_two_messages(self):
        profile = make_profile()
        messages = PromptBuilder.build_messages(profile, {"query": "hello"})
        assert len(messages) == 2

    def test_first_message_is_system(self):
        profile = make_profile()
        messages = PromptBuilder.build_messages(profile, {})
        assert messages[0]["role"] == "system"

    def test_second_message_is_user(self):
        profile = make_profile()
        messages = PromptBuilder.build_messages(profile, {"query": "hello"})
        assert messages[1]["role"] == "user"

    def test_system_contains_role_prompt(self):
        profile = make_profile(role_prompt="You are a specialist.")
        messages = PromptBuilder.build_messages(profile, {})
        assert "You are a specialist." in messages[0]["content"]

    def test_scalar_values_rendered_inline(self):
        profile = make_profile()
        messages = PromptBuilder.build_messages(profile, {"name": "Alice", "age": 30})
        user_content = messages[1]["content"]
        assert "**name:** Alice" in user_content
        assert "**age:** 30" in user_content

    def test_dict_values_formatted_as_json(self):
        profile = make_profile()
        data = {"key": "value", "num": 42}
        messages = PromptBuilder.build_messages(profile, {"payload": data})
        user_content = messages[1]["content"]
        assert "**payload:**" in user_content
        # Should be pretty-printed JSON
        expected_json = json.dumps(data, indent=2)
        assert expected_json in user_content

    def test_list_values_formatted_as_json(self):
        profile = make_profile()
        items = [1, 2, 3]
        messages = PromptBuilder.build_messages(profile, {"items": items})
        user_content = messages[1]["content"]
        assert json.dumps(items, indent=2) in user_content

    def test_empty_context_user_content_is_empty_string(self):
        profile = make_profile()
        messages = PromptBuilder.build_messages(profile, {})
        assert messages[1]["content"] == ""

    def test_multiple_context_keys_separated_by_double_newline(self):
        profile = make_profile()
        messages = PromptBuilder.build_messages(profile, {"a": "alpha", "b": "beta"})
        user_content = messages[1]["content"]
        assert "\n\n" in user_content

    def test_system_prompt_includes_guidelines(self):
        profile = make_profile(guidelines=["Rule A", "Rule B"])
        messages = PromptBuilder.build_messages(profile, {})
        system = messages[0]["content"]
        assert "- Rule A" in system
        assert "- Rule B" in system
