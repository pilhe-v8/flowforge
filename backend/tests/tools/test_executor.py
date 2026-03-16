"""Tests for ToolExecutor — routes calls by URI scheme."""

import pytest
from unittest.mock import AsyncMock

from flowforge.tools.executor import ToolExecutor


@pytest.fixture
def mcp_client():
    client = AsyncMock()
    client.call = AsyncMock(return_value={"mcp": "result"})
    return client


@pytest.fixture
def http_client():
    client = AsyncMock()
    client.call = AsyncMock(return_value={"http": "result"})
    return client


@pytest.fixture
def executor(mcp_client, http_client):
    return ToolExecutor(mcp_client=mcp_client, http_client=http_client)


@pytest.mark.asyncio
async def test_mcp_routing(executor, mcp_client):
    """MCP URI should be dispatched to the MCP client."""
    result = await executor.execute("mcp://crm-service:9000/customer-lookup", {"id": "123"})
    mcp_client.call.assert_awaited_once_with(
        "mcp://crm-service:9000/customer-lookup", {"id": "123"}
    )
    assert result == {"mcp": "result"}


@pytest.mark.asyncio
async def test_http_routing(executor, http_client):
    """HTTP URI should be dispatched to the HTTP client."""
    result = await executor.execute("http://api.example.com/tool", {"key": "val"})
    http_client.call.assert_awaited_once_with("http://api.example.com/tool", {"key": "val"}, None)
    assert result == {"http": "result"}


@pytest.mark.asyncio
async def test_https_routing(executor, http_client):
    """HTTPS URI should be dispatched to the HTTP client."""
    result = await executor.execute("https://api.example.com/tool", {"key": "val"})
    http_client.call.assert_awaited_once_with("https://api.example.com/tool", {"key": "val"}, None)
    assert result == {"http": "result"}


@pytest.mark.asyncio
async def test_http_routing_with_auth(executor, http_client):
    """Auth dict should be forwarded to the HTTP client."""
    auth = {"type": "bearer", "token": "tok123"}
    await executor.execute("https://api.example.com/tool", {}, auth=auth)
    http_client.call.assert_awaited_once_with("https://api.example.com/tool", {}, auth)


@pytest.mark.asyncio
async def test_unknown_protocol_raises_value_error(executor):
    """Unknown URI schemes should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown protocol"):
        await executor.execute("ftp://some-server/tool", {})


@pytest.mark.asyncio
async def test_mcp_not_called_for_http(executor, mcp_client):
    """MCP client must not be called when URI is HTTP."""
    await executor.execute("http://example.com/tool", {})
    mcp_client.call.assert_not_awaited()


@pytest.mark.asyncio
async def test_http_not_called_for_mcp(executor, http_client):
    """HTTP client must not be called when URI is MCP."""
    await executor.execute("mcp://server:9000/tool", {})
    http_client.call.assert_not_awaited()
