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
        self._client = client or httpx.AsyncClient(timeout=30.0)

    async def invoke(
        self,
        tool_uri: str,
        inputs: dict,
        context: dict | None = None,
    ) -> dict:
        url = f"{self.base_url}/v1/tool-calls:invoke"
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        payload: dict[str, object] = {"tool_uri": tool_uri, "inputs": inputs, "context": context}

        response = await self._client.post(url, json=payload, headers=headers)
        if 200 <= response.status_code < 300:
            data = response.json()
            output = data.get("output") if isinstance(data, dict) else None
            return output or {}

        detail = None
        try:
            ct = response.headers.get("content-type", "")
            if "json" in ct or ct.startswith("text/"):
                detail = response.text
        except Exception:
            detail = None

        if detail:
            detail = detail[:1000]
            raise RuntimeError(
                f"Tool gateway invoke failed ({response.status_code}) for {tool_uri}: {detail}"
            )
        raise RuntimeError(f"Tool gateway invoke failed ({response.status_code}) for {tool_uri}")
