"""Tool executor.

All tool calls are routed through the Tool Gateway (fail-closed).
"""

from __future__ import annotations

from typing import Protocol, cast

from flowforge.config import get_settings
from flowforge.tools.gateway_client import ToolGatewayClient


class GatewayClient(Protocol):
    async def invoke(self, tool_uri: str, inputs: dict, context: dict | None = None) -> object: ...


class ToolExecutor:
    """Executes tools via ToolGatewayClient (fail-closed)."""

    def __init__(
        self,
        gateway_client: GatewayClient | None = None,
        tool_gateway_url: str | None = None,
        tool_gateway_jwt: str | None = None,
    ) -> None:
        if gateway_client is not None:
            self.gateway_client: GatewayClient = gateway_client
            return

        settings = get_settings()
        url = tool_gateway_url if tool_gateway_url is not None else settings.tool_gateway_url
        jwt = tool_gateway_jwt if tool_gateway_jwt is not None else settings.tool_gateway_jwt

        if not url or not jwt:
            raise RuntimeError(
                "Tool gateway is not configured (fail-closed). "
                "Set FLOWFORGE_TOOL_GATEWAY_URL and FLOWFORGE_TOOL_GATEWAY_JWT."
            )

        self.gateway_client = cast(
            GatewayClient,
            ToolGatewayClient(base_url=url, jwt_token=jwt),
        )

    async def execute(
        self,
        tool_uri: str,
        inputs: dict,
        auth: dict | None = None,
        context: dict | None = None,
    ) -> object:
        """Execute the tool at *tool_uri* with the given *inputs* via gateway.

        Note: *auth* is kept for backwards compatibility but is not used here;
        callers should include identity/tenant metadata in *context*.
        """
        _ = auth
        try:
            return await self.gateway_client.invoke(tool_uri, inputs, context=context)
        except Exception as e:
            raise RuntimeError(
                f"Tool gateway invocation failed for tool_uri={tool_uri!r}. "
                "Check tool gateway connectivity/configuration and tool URI validity."
            ) from e
