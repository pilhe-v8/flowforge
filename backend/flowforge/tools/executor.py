"""Tool executor — routes tool calls by URI scheme."""


class ToolExecutor:
    """Routes tool execution to the appropriate client based on URI scheme."""

    def __init__(self, mcp_client, http_client):
        self.mcp = mcp_client
        self.http = http_client

    async def execute(
        self,
        tool_uri: str,
        inputs: dict,
        auth: dict | None = None,
    ) -> dict:
        """Execute the tool at *tool_uri* with the given *inputs*.

        Routing:
            mcp://…    → MCPToolClient
            http://…   → HTTPToolClient
            https://…  → HTTPToolClient

        Raises:
            ValueError: if the URI scheme is not recognised.
        """
        if tool_uri.startswith("mcp://"):
            return await self.mcp.call(tool_uri, inputs)
        elif tool_uri.startswith("http://") or tool_uri.startswith("https://"):
            return await self.http.call(tool_uri, inputs, auth)
        else:
            raise ValueError(f"Unknown protocol in URI: {tool_uri}")
