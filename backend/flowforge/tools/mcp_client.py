"""MCP tool client — calls tools on MCP servers over SSE transport."""

import json
import logging
from typing import Any
from mcp import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)


def parse_mcp_uri(uri: str) -> tuple[str, str]:
    """Parse an MCP URI into (endpoint, tool_name).

    Example:
        "mcp://crm-service:9000/customer-lookup"
        → ("mcp://crm-service:9000", "customer-lookup")
    """
    # Strip the scheme to find the path separator
    # uri looks like mcp://host:port/tool-name
    without_scheme = uri[len("mcp://") :]
    slash_idx = without_scheme.find("/")
    if slash_idx == -1:
        raise ValueError(f"Invalid MCP URI (no tool path): {uri}")
    host_port = without_scheme[:slash_idx]
    tool_name = without_scheme[slash_idx + 1 :]
    endpoint = f"mcp://{host_port}"
    return endpoint, tool_name


def parse_host_port(endpoint: str) -> tuple[str, int]:
    """Parse an MCP endpoint string into (host, port).

    Example:
        "mcp://crm-service:9000" → ("crm-service", 9000)
    """
    without_scheme = endpoint[len("mcp://") :]
    if ":" in without_scheme:
        host, port_str = without_scheme.rsplit(":", 1)
        return host, int(port_str)
    return without_scheme, 9000  # default port


class MCPToolClient:
    """Calls tools on MCP servers.  Sessions are cached per endpoint."""

    def __init__(self):
        self._sessions: dict[str, ClientSession] = {}
        self._sse_cms: dict[str, Any] = {}  # store CMs for cleanup

    async def call(self, tool_uri: str, inputs: dict) -> dict:
        """Execute a tool identified by *tool_uri* with the given *inputs*."""
        endpoint, tool_name = parse_mcp_uri(tool_uri)

        if endpoint not in self._sessions:
            self._sessions[endpoint] = await self._connect(endpoint)

        session = self._sessions[endpoint]
        try:
            result = await session.call_tool(tool_name, arguments=inputs)
        except Exception:
            # Session may be stale — evict and retry once
            logger.warning("MCP session for %s appears stale, reconnecting and retrying.", endpoint)
            del self._sessions[endpoint]
            if endpoint in self._sse_cms:
                del self._sse_cms[endpoint]
            self._sessions[endpoint] = await self._connect(endpoint)
            session = self._sessions[endpoint]
            result = await session.call_tool(tool_name, arguments=inputs)

        return self._extract_result(result)

    def _extract_result(self, result) -> dict:
        """Extract a plain dict from an MCP CallToolResult."""
        if result.content and result.content[0].type == "text":
            text = result.content[0].text
            try:
                return json.loads(text)
            except (json.JSONDecodeError, ValueError):
                return {"raw": text}
        return {"raw": str(result.content)}

    async def _connect(self, endpoint: str) -> ClientSession:
        """Open an SSE connection to *endpoint* and return an initialized session.

        NOTE: This requires a live MCP server.  In tests, mock ``_connect``
        or inject a pre-built session into ``self._sessions``.
        """
        host, port = parse_host_port(endpoint)
        # Convert mcp:// scheme to http:// for the SSE transport
        http_url = f"http://{host}:{port}/sse"

        cm = sse_client(http_url)
        read_stream, write_stream = await cm.__aenter__()
        self._sse_cms[endpoint] = cm  # store for later cleanup
        session = ClientSession(read_stream, write_stream)
        await session.initialize()
        return session

    async def close(self):
        """Close all cached MCP sessions and release SSE connections."""
        for endpoint, cm in self._sse_cms.items():
            try:
                await cm.__aexit__(None, None, None)
            except Exception:
                pass
        self._sessions.clear()
        self._sse_cms.clear()
