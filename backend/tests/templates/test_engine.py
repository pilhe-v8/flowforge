"""Tests for TemplateEngine."""

import pytest
from jinja2 import UndefinedError

from flowforge.templates.engine import TemplateEngine


@pytest.fixture
def engine():
    return TemplateEngine()


class TestTemplateEngineRender:
    def test_simple_variable_substitution(self, engine):
        result = engine.render("Hello, {{ name }}!", {"name": "World"})
        assert result == "Hello, World!"

    def test_multiple_variables(self, engine):
        result = engine.render("{{ greeting }}, {{ name }}!", {"greeting": "Hi", "name": "Alice"})
        assert result == "Hi, Alice!"

    def test_integer_variable(self, engine):
        result = engine.render("Count: {{ count }}", {"count": 42})
        assert result == "Count: 42"

    def test_no_variables(self, engine):
        result = engine.render("No variables here.", {})
        assert result == "No variables here."

    def test_multiline_template(self, engine):
        template = "Line 1: {{ a }}\nLine 2: {{ b }}\nLine 3: {{ c }}"
        result = engine.render(template, {"a": "alpha", "b": "beta", "c": "gamma"})
        assert result == "Line 1: alpha\nLine 2: beta\nLine 3: gamma"

    def test_conditional_block(self, engine):
        template = "{% if show %}Visible{% else %}Hidden{% endif %}"
        assert engine.render(template, {"show": True}) == "Visible"
        assert engine.render(template, {"show": False}) == "Hidden"

    def test_loop(self, engine):
        template = "{% for item in items %}{{ item }} {% endfor %}"
        result = engine.render(template, {"items": ["a", "b", "c"]})
        assert result == "a b c "

    def test_missing_variable_renders_empty_string(self, engine):
        """Jinja2 default: undefined vars render as empty string."""
        result = engine.render("Hello, {{ missing }}!", {})
        assert result == "Hello, !"

    def test_extra_variables_ignored(self, engine):
        """Variables not referenced in template are silently ignored."""
        result = engine.render("{{ used }}", {"used": "yes", "unused": "ignored"})
        assert result == "yes"

    def test_dict_attribute_access(self, engine):
        result = engine.render("{{ user.name }}", {"user": {"name": "Bob"}})
        assert result == "Bob"

    def test_reusable_engine(self, engine):
        """TemplateEngine can render multiple templates in sequence."""
        r1 = engine.render("{{ x }}", {"x": "first"})
        r2 = engine.render("{{ y }}", {"y": "second"})
        assert r1 == "first"
        assert r2 == "second"
