"""Tests for MCPToolClient."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from flowforge.tools.mcp_client import MCPToolClient, parse_mcp_uri, parse_host_port


# ---------------------------------------------------------------------------
# parse_mcp_uri
# ---------------------------------------------------------------------------


class TestParseMcpUri:
    def test_standard_uri(self):
        endpoint, tool = parse_mcp_uri("mcp://crm-service:9000/customer-lookup")
        assert endpoint == "mcp://crm-service:9000"
        assert tool == "customer-lookup"

    def test_no_port(self):
        endpoint, tool = parse_mcp_uri("mcp://myhost/my-tool")
        assert endpoint == "mcp://myhost"
        assert tool == "my-tool"

    def test_invalid_uri_raises(self):
        with pytest.raises(ValueError, match="Invalid MCP URI"):
            parse_mcp_uri("mcp://host-only")

    def test_tool_name_with_slashes(self):
        endpoint, tool = parse_mcp_uri("mcp://host:8080/nested/tool")
        assert endpoint == "mcp://host:8080"
        assert tool == "nested/tool"


# ---------------------------------------------------------------------------
# parse_host_port
# ---------------------------------------------------------------------------


class TestParseHostPort:
    def test_with_port(self):
        host, port = parse_host_port("mcp://myhost:9000")
        assert host == "myhost"
        assert port == 9000

    def test_without_port_defaults_to_9000(self):
        host, port = parse_host_port("mcp://myhost")
        assert host == "myhost"
        assert port == 9000

    def test_numeric_port(self):
        _, port = parse_host_port("mcp://svc:1234")
        assert port == 1234


# ---------------------------------------------------------------------------
# MCPToolClient._extract_result
# ---------------------------------------------------------------------------


class TestExtractResult:
    def setup_method(self):
        self.client = MCPToolClient()

    def _make_result(self, text: str):
        content_item = MagicMock()
        content_item.type = "text"
        content_item.text = text
        result = MagicMock()
        result.content = [content_item]
        return result

    def test_json_text_is_parsed(self):
        result = self._make_result('{"key": "value"}')
        assert self.client._extract_result(result) == {"key": "value"}

    def test_non_json_text_returns_raw(self):
        result = self._make_result("plain text response")
        assert self.client._extract_result(result) == {"raw": "plain text response"}

    def test_invalid_json_returns_raw(self):
        result = self._make_result("{not: valid json}")
        assert self.client._extract_result(result) == {"raw": "{not: valid json}"}

    def test_empty_content_returns_raw_str(self):
        result = MagicMock()
        result.content = []
        assert "raw" in self.client._extract_result(result)

    def test_non_text_content_type_returns_raw(self):
        content_item = MagicMock()
        content_item.type = "binary"
        result = MagicMock()
        result.content = [content_item]
        assert "raw" in self.client._extract_result(result)


# ---------------------------------------------------------------------------
# MCPToolClient.call — session caching and reconnection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_caches_session():
    """call() reuses the same session for subsequent calls to the same endpoint."""
    client = MCPToolClient()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = []
    mock_session.call_tool.return_value = mock_result

    client._sessions["mcp://svc:9000"] = mock_session

    await client.call("mcp://svc:9000/my-tool", {"x": 1})
    await client.call("mcp://svc:9000/my-tool", {"x": 2})

    assert mock_session.call_tool.call_count == 2


@pytest.mark.asyncio
async def test_call_reconnects_on_stale_session():
    """call() evicts a dead session and retries once."""
    client = MCPToolClient()

    # First session always fails
    stale_session = AsyncMock()
    stale_session.call_tool.side_effect = RuntimeError("connection reset")

    # Fresh session succeeds
    fresh_session = AsyncMock()
    fresh_result = MagicMock()
    fresh_result.content = []
    fresh_session.call_tool.return_value = fresh_result

    client._sessions["mcp://svc:9000"] = stale_session

    connect_calls = []

    async def mock_connect(endpoint):
        connect_calls.append(endpoint)
        return fresh_session

    client._connect = mock_connect

    result = await client.call("mcp://svc:9000/tool", {})

    assert len(connect_calls) == 1
    assert fresh_session.call_tool.call_count == 1
    assert "raw" in result or result == {}


@pytest.mark.asyncio
async def test_call_connects_when_no_session():
    """call() connects fresh when no cached session exists."""
    client = MCPToolClient()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = []
    mock_session.call_tool.return_value = mock_result

    async def mock_connect(endpoint):
        return mock_session

    client._connect = mock_connect

    await client.call("mcp://svc:9000/tool", {"a": "b"})

    assert mock_session.call_tool.call_count == 1
    mock_session.call_tool.assert_called_with("tool", arguments={"a": "b"})


# ---------------------------------------------------------------------------
# MCPToolClient.close
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_exits_all_sse_cms():
    """close() calls __aexit__ on every stored SSE context manager."""
    client = MCPToolClient()

    cm1 = AsyncMock()
    cm2 = AsyncMock()
    client._sse_cms["mcp://ep1:9000"] = cm1
    client._sse_cms["mcp://ep2:9000"] = cm2
    client._sessions["mcp://ep1:9000"] = AsyncMock()
    client._sessions["mcp://ep2:9000"] = AsyncMock()

    await client.close()

    cm1.__aexit__.assert_called_once_with(None, None, None)
    cm2.__aexit__.assert_called_once_with(None, None, None)
    assert client._sessions == {}
    assert client._sse_cms == {}


@pytest.mark.asyncio
async def test_close_tolerates_aexit_errors():
    """close() continues even if __aexit__ raises."""
    client = MCPToolClient()

    bad_cm = AsyncMock()
    bad_cm.__aexit__.side_effect = RuntimeError("cleanup failure")
    client._sse_cms["mcp://ep:9000"] = bad_cm

    # Should not raise
    await client.close()

    assert client._sessions == {}
    assert client._sse_cms == {}
