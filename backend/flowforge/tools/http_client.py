"""HTTP tool client — calls tools exposed over plain HTTP endpoints."""

import httpx


class HTTPToolClient:
    """Calls tools that expose a simple HTTP POST interface."""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def call(
        self,
        endpoint: str,
        inputs: dict,
        auth: dict | None = None,
    ) -> dict:
        """POST *inputs* as JSON to *endpoint* and return the parsed JSON response.

        Args:
            endpoint: Full HTTP/HTTPS URL of the tool.
            inputs:   Payload to send as JSON body.
            auth:     Optional auth config dict with one of the shapes:
                        {"type": "bearer", "token": "..."}
                        {"type": "api_key", "header": "X-API-Key", "key": "..."}
        """
        headers: dict[str, str] = {}
        if auth:
            if auth["type"] == "bearer":
                headers["Authorization"] = f"Bearer {auth['token']}"
            elif auth["type"] == "api_key":
                headers[auth["header"]] = auth["key"]

        response = await self.client.post(endpoint, json=inputs, headers=headers)
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()
