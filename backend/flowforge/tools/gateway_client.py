"""Tool Gateway client.

This client calls the Tool Gateway's invoke endpoint using a service JWT.
"""

import httpx


class ToolGatewayClient:
    def __init__(
        self,
        base_url: str,
        jwt_token: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.jwt_token = jwt_token
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=30.0)

    async def aclose(self) -> None:
        is_closed = getattr(self._client, "is_closed", None)
        if is_closed is None:
            is_closed = getattr(self._client, "closed", False)

        if self._owns_client and not is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> "ToolGatewayClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def invoke(
        self,
        tool_uri: str,
        inputs: dict[str, object],
        context: dict[str, object] | None = None,
    ) -> object:
        url = f"{self.base_url}/v1/tool-calls:invoke"
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        payload: dict[str, object] = {"tool_uri": tool_uri, "inputs": inputs}
        if context is not None:
            payload["context"] = context

        response = await self._client.post(url, json=payload, headers=headers)
        if 200 <= response.status_code < 300:
            try:
                data = response.json()
            except ValueError as e:
                raise RuntimeError(
                    f"Tool gateway invoke returned non-JSON response ({response.status_code}) for {tool_uri}"
                ) from e
            output = data.get("output") if isinstance(data, dict) else None
            return {} if output is None else output

        raise RuntimeError(f"Tool gateway invoke failed ({response.status_code}) for {tool_uri}")
