"""Tests for SafeExprEvaluator — written first (TDD)."""

import pytest
from flowforge.compiler.safe_eval import SafeExprEvaluator


def make_eval(variables: dict) -> SafeExprEvaluator:
    """Helper: wrap flat variables as {step_id: {var: val}} structure."""
    return SafeExprEvaluator({"step": variables})


def test_equality():
    """x == 'hello' should be True when x='hello'."""
    ev = make_eval({"x": "hello"})
    assert ev.evaluate("x == 'hello'") is True


def test_equality_false():
    """x == 'hello' should be False when x='world'."""
    ev = make_eval({"x": "world"})
    assert ev.evaluate("x == 'hello'") is False


def test_inequality():
    """x != 'hello' should be True when x='world'."""
    ev = make_eval({"x": "world"})
    assert ev.evaluate("x != 'hello'") is True


def test_less_than():
    """score < 0.85 should be True when score=0.7."""
    ev = make_eval({"score": 0.7})
    assert ev.evaluate("score < 0.85") is True


def test_greater_than():
    """score > 0.5 should be True when score=0.9."""
    ev = make_eval({"score": 0.9})
    assert ev.evaluate("score > 0.5") is True


def test_less_than_or_equal():
    """score <= 0.85 edge case."""
    ev = make_eval({"score": 0.85})
    assert ev.evaluate("score <= 0.85") is True


def test_greater_than_or_equal():
    """score >= 0.5 edge case."""
    ev = make_eval({"score": 0.5})
    assert ev.evaluate("score >= 0.5") is True


def test_and_operator():
    """x == 'a' and y == 'b' should be True when both hold."""
    ev = make_eval({"x": "a", "y": "b"})
    assert ev.evaluate("x == 'a' and y == 'b'") is True


def test_and_operator_false():
    """x == 'a' and y == 'b' should be False when y doesn't match."""
    ev = make_eval({"x": "a", "y": "c"})
    assert ev.evaluate("x == 'a' and y == 'b'") is False


def test_or_operator():
    """x == 'a' or x == 'b' should be True when x='a'."""
    ev = make_eval({"x": "a"})
    assert ev.evaluate("x == 'a' or x == 'b'") is True


def test_or_operator_false():
    """x == 'a' or x == 'b' should be False when x='c'."""
    ev = make_eval({"x": "c"})
    assert ev.evaluate("x == 'a' or x == 'b'") is False


def test_not_operator():
    """not x == 'a' should be True when x='b'."""
    ev = make_eval({"x": "b"})
    assert ev.evaluate("not x == 'a'") is True


def test_not_operator_false():
    """not x == 'a' should be False when x='a'."""
    ev = make_eval({"x": "a"})
    assert ev.evaluate("not x == 'a'") is False


def test_in_operator():
    """intent in ['billing', 'refund'] should be True when intent='billing'."""
    ev = make_eval({"intent": "billing"})
    assert ev.evaluate("intent in ['billing', 'refund']") is True


def test_in_operator_false():
    """intent in ['billing', 'refund'] should be False when intent='other'."""
    ev = make_eval({"intent": "other"})
    assert ev.evaluate("intent in ['billing', 'refund']") is False


def test_len_function():
    """len(text) < 20 should be True when text='hello'."""
    ev = make_eval({"text": "hello"})
    assert ev.evaluate("len(text) < 20") is True


def test_len_function_false():
    """len(text) < 5 should be False when text='hello world'."""
    ev = make_eval({"text": "hello world"})
    assert ev.evaluate("len(text) < 5") is False


def test_contains_function():
    """contains(body, 'urgent') should be True when body contains 'urgent'."""
    ev = make_eval({"body": "This is urgent please help"})
    assert ev.evaluate("contains(body, 'urgent')") is True


def test_contains_function_false():
    """contains(body, 'urgent') should be False when body doesn't contain it."""
    ev = make_eval({"body": "Normal request"})
    assert ev.evaluate("contains(body, 'urgent')") is False


def test_starts_with_function():
    """starts_with(subject, 'Re:') should be True when subject starts with 'Re:'."""
    ev = make_eval({"subject": "Re: Your ticket"})
    assert ev.evaluate("starts_with(subject, 'Re:')") is True


def test_starts_with_function_false():
    """starts_with(subject, 'Re:') should be False when subject doesn't start with it."""
    ev = make_eval({"subject": "New ticket"})
    assert ev.evaluate("starts_with(subject, 'Re:')") is False


def test_is_empty_none():
    """is_empty(value) should be True when value is None."""
    ev = make_eval({"value": None})
    assert ev.evaluate("is_empty(value)") is True


def test_is_empty_empty_string():
    """is_empty(value) should be True when value is empty string."""
    ev = make_eval({"value": ""})
    assert ev.evaluate("is_empty(value)") is True


def test_is_empty_empty_list():
    """is_empty(value) should be True when value is empty list."""
    ev = make_eval({"value": []})
    assert ev.evaluate("is_empty(value)") is True


def test_is_empty_empty_dict():
    """is_empty(value) should be True when value is empty dict."""
    ev = make_eval({"value": {}})
    assert ev.evaluate("is_empty(value)") is True


def test_is_empty_nonempty():
    """is_empty(value) should be False when value is non-empty."""
    ev = make_eval({"value": "hello"})
    assert ev.evaluate("is_empty(value)") is False


def test_unknown_function_raises():
    """Calling an unknown function should raise ValueError."""
    ev = make_eval({"x": "foo"})
    with pytest.raises(ValueError, match="Unknown function"):
        ev.evaluate("evil_func(x)")


def test_exec_not_allowed():
    """Attempting to import or use __import__ should raise ValueError."""
    ev = make_eval({})
    with pytest.raises(ValueError):
        ev.evaluate("__import__('os')")


def test_invalid_syntax_raises():
    """Broken expression should raise ValueError."""
    ev = make_eval({})
    with pytest.raises(ValueError, match="Invalid expression syntax"):
        ev.evaluate("x ==")


def test_variable_from_nested_state():
    """Variables should be extracted from nested {step_id: {var: val}} state."""
    ev = SafeExprEvaluator({"my_step": {"score": 0.9}, "other": {"flag": True}})
    assert ev.evaluate("score > 0.5") is True
    assert ev.evaluate("flag == True") is True


def test_ternary_not_allowed():
    """Ternary (if-else) expressions should raise ValueError."""
    ev = make_eval({"x": 1})
    with pytest.raises(ValueError):
        ev.evaluate("1 if x == 1 else 0")


def test_not_in_operator():
    """intent not in ['billing', 'refund'] should be True when intent='other'."""
    ev = make_eval({"intent": "other"})
    assert ev.evaluate("intent not in ['billing', 'refund']") is True


def test_step_scoped_attribute_lookup():
    """Dot-notation (step_id.var_name) should resolve from the correct step namespace."""
    ev = SafeExprEvaluator({"step_a": {"score": 0.9}, "step_b": {"score": 0.1}})
    assert ev.evaluate("step_a.score > 0.5") is True
    assert ev.evaluate("step_b.score > 0.5") is False


def test_step_scoped_no_collision():
    """When two steps produce the same variable name, scoped access must disambiguate."""
    ev = SafeExprEvaluator({"step_a": {"score": 0.9}, "step_b": {"score": 0.2}})
    # Flat lookup ('score') would be ambiguous; scoped access is unambiguous
    assert ev.evaluate("step_a.score > 0.8") is True
    assert ev.evaluate("step_b.score > 0.8") is False


def test_step_scoped_attribute_missing_step():
    """Accessing a var from a nonexistent step_id should return None gracefully."""
    ev = SafeExprEvaluator({"step_a": {"score": 0.5}})
    # nonexistent.score → None, so None == None is True
    result = ev.evaluate("nonexistent_step.score == None")
    assert result is True
