"""Tests for MCPDiscovery and helpers."""

import pytest
from dataclasses import is_dataclass
from unittest.mock import AsyncMock, MagicMock, patch

from flowforge.tools.discovery import MCPDiscovery, ToolSchema, slugify


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_lowercase(self):
        assert slugify("HELLO") == "hello"

    def test_spaces_to_hyphens(self):
        assert slugify("Customer Lookup") == "customer-lookup"

    def test_strips_non_alphanumeric(self):
        assert slugify("get@user!data") == "getuserdata"

    def test_collapses_multiple_hyphens(self):
        assert slugify("foo--bar") == "foo-bar"

    def test_already_slug(self):
        assert slugify("my-tool") == "my-tool"

    def test_numbers_preserved(self):
        assert slugify("Tool 42") == "tool-42"

    def test_leading_trailing_spaces(self):
        assert slugify("  hello world  ") == "hello-world"


# ---------------------------------------------------------------------------
# ToolSchema dataclass
# ---------------------------------------------------------------------------


class TestToolSchemaDataclass:
    def test_is_dataclass(self):
        assert is_dataclass(ToolSchema)

    def test_fields_present(self):
        ts = ToolSchema(
            name="My Tool",
            slug="my-tool",
            uri="mcp://server:9000/my-tool",
            description="Does things",
            input_schema={"type": "object"},
            output_schema={},
        )
        assert ts.name == "My Tool"
        assert ts.slug == "my-tool"
        assert ts.uri == "mcp://server:9000/my-tool"
        assert ts.description == "Does things"
        assert ts.input_schema == {"type": "object"}
        assert ts.output_schema == {}

    def test_default_schemas_are_empty_dicts(self):
        ts = ToolSchema(name="T", slug="t", uri="mcp://s/t", description="")
        assert ts.input_schema == {}
        assert ts.output_schema == {}


# ---------------------------------------------------------------------------
# MCPDiscovery.discover_all — continues on failure
# ---------------------------------------------------------------------------


def make_registration(endpoint: str):
    reg = MagicMock()
    reg.endpoint = endpoint
    return reg


@pytest.mark.asyncio
async def test_discover_all_continues_on_failure():
    """discover_all should skip failing endpoints and collect the rest."""
    discovery = MCPDiscovery()

    good_tool = ToolSchema(
        name="Good Tool",
        slug="good-tool",
        uri="mcp://good:9000/Good Tool",
        description="Works",
    )

    async def mock_discover(endpoint: str):
        if "bad" in endpoint:
            raise ConnectionError("cannot connect")
        return [good_tool]

    discovery.discover = mock_discover  # type: ignore[method-assign]

    regs = [make_registration("mcp://good:9000"), make_registration("mcp://bad:9000")]
    results = await discovery.discover_all(regs)

    assert len(results) == 1
    assert results[0].name == "Good Tool"


@pytest.mark.asyncio
async def test_discover_all_empty_registrations():
    """discover_all with no registrations returns an empty list."""
    discovery = MCPDiscovery()
    results = await discovery.discover_all([])
    assert results == []


@pytest.mark.asyncio
async def test_discover_all_all_fail():
    """discover_all returns empty list when every endpoint fails."""
    discovery = MCPDiscovery()

    async def mock_discover(endpoint):
        raise RuntimeError("fail")

    discovery.discover = mock_discover  # type: ignore[method-assign]

    regs = [make_registration("mcp://bad1:9000"), make_registration("mcp://bad2:9000")]
    results = await discovery.discover_all(regs)
    assert results == []


@pytest.mark.asyncio
async def test_discover_all_accumulates_multiple():
    """discover_all accumulates tools from multiple endpoints."""
    discovery = MCPDiscovery()

    tool_a = ToolSchema(name="A", slug="a", uri="mcp://ep1/A", description="")
    tool_b = ToolSchema(name="B", slug="b", uri="mcp://ep2/B", description="")

    async def mock_discover(endpoint: str):
        if "ep1" in endpoint:
            return [tool_a]
        return [tool_b]

    discovery.discover = mock_discover  # type: ignore[method-assign]

    regs = [make_registration("mcp://ep1"), make_registration("mcp://ep2")]
    results = await discovery.discover_all(regs)
    assert len(results) == 2
