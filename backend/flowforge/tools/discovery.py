"""MCP tool discovery — enumerates available tools from MCP servers."""

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import quote

from mcp import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Convert a display name to a URL-friendly slug.

    Example:
        "Customer Lookup" → "customer-lookup"
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text


@dataclass
class ToolSchema:
    """Represents a discovered tool from an MCP server."""

    name: str
    slug: str
    uri: str
    description: str
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)


class _MCPDiscoverySession:
    """Thin async context manager that opens an MCP session for discovery."""

    def __init__(self, endpoint: str):
        # Convert mcp:// scheme to http:// for the SSE transport
        if endpoint.startswith("mcp://"):
            self._url = "http://" + endpoint[len("mcp://") :] + "/sse"
        else:
            self._url = endpoint + "/sse"
        self._sse_cm = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> ClientSession:
        self._sse_cm = sse_client(self._url)
        read_stream, write_stream = await self._sse_cm.__aenter__()
        self._session = ClientSession(read_stream, write_stream)
        await self._session.__aenter__()
        await self._session.initialize()
        return self._session

    async def __aexit__(self, *exc_info) -> None:
        if self._session is not None:
            await self._session.__aexit__(*exc_info)
        if self._sse_cm is not None:
            await self._sse_cm.__aexit__(*exc_info)


class MCPDiscovery:
    """Discovers tools from one or more MCP server endpoints."""

    async def discover(self, endpoint: str) -> list[ToolSchema]:
        """Return a list of :class:`ToolSchema` objects for all tools on *endpoint*."""
        async with _MCPDiscoverySession(endpoint) as session:
            result = await session.list_tools()
            tools = result.tools
            return [
                ToolSchema(
                    name=tool.name,
                    slug=slugify(tool.name),
                    uri=f"{endpoint}/{quote(tool.name, safe='')}",
                    description=tool.description or "",
                    input_schema=tool.inputSchema if tool.inputSchema else {},
                    output_schema=getattr(tool, "outputSchema", None) or {},
                )
                for tool in tools
            ]

    async def discover_all(self, registrations: list) -> list[ToolSchema]:
        """Discover tools from all registrations, skipping endpoints that fail."""
        all_tools: list[ToolSchema] = []
        for reg in registrations:
            try:
                tools = await self.discover(reg.endpoint)
                all_tools.extend(tools)
            except Exception as exc:
                logger.warning("Discovery failed for %s: %s", reg.endpoint, exc)
        return all_tools
