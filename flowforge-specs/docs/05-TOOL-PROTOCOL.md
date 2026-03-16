# 05 - Tool Protocol Specification (MCP Integration)

## Overview

Tools are external deterministic functions (DB queries, ML models, APIs, code) that
workflow nodes can call. FlowForge uses MCP (Model Context Protocol) as the primary
tool integration protocol, with HTTP and gRPC as fallbacks.

## Tool Registration

Tools are registered per-tenant in the database (see 09-DATA-MODEL.md for schema).

```
POST /api/v1/tools/register
Body: {"endpoint": "mcp://crm-service:9000", "name": "CRM Service"}
```

## MCP Discovery

At startup and on-demand, the control plane queries all registered MCP servers:

```python
class MCPDiscovery:
    async def discover(self, endpoint: str) -> list[ToolSchema]:
        async with MCPClient(endpoint) as client:
            tools = await client.list_tools()
            return [
                ToolSchema(
                    name=tool.name,
                    slug=slugify(tool.name),
                    uri=f"{endpoint}/{tool.name}",
                    description=tool.description,
                    input_schema=tool.inputSchema,
                    output_schema=tool.outputSchema,
                )
                for tool in tools
            ]

    async def discover_all(self, registrations: list) -> list[ToolSchema]:
        all_tools = []
        for reg in registrations:
            try:
                tools = await self.discover(reg.endpoint)
                all_tools.extend(tools)
            except Exception as e:
                logger.warning(f"Discovery failed for {reg.endpoint}: {e}")
        return all_tools
```

The result populates the ToolCatalogue, served to the frontend for dropdowns.

## MCP Client (Runtime)

```python
import json
from mcp import ClientSession

class MCPToolClient:
    def __init__(self):
        self._sessions: dict[str, ClientSession] = {}

    async def call(self, tool_uri: str, inputs: dict) -> dict:
        endpoint, tool_name = parse_mcp_uri(tool_uri)

        if endpoint not in self._sessions:
            self._sessions[endpoint] = await self._connect(endpoint)

        session = self._sessions[endpoint]
        result = await session.call_tool(tool_name, arguments=inputs)

        return self._extract_result(result)

    def _extract_result(self, result) -> dict:
        if result.content and result.content[0].type == "text":
            return json.loads(result.content[0].text)
        return {"raw": str(result.content)}

    async def _connect(self, endpoint: str) -> ClientSession:
        # Parse mcp://host:port
        host, port = parse_host_port(endpoint)
        # Connect via stdio or SSE transport depending on config
        session = ClientSession(...)
        await session.initialize()
        return session
```

## HTTP Fallback Client

For tools exposed as plain REST APIs:

```python
import httpx

class HTTPToolClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def call(self, endpoint: str, inputs: dict, auth: dict | None) -> dict:
        headers = {}
        if auth:
            if auth["type"] == "bearer":
                headers["Authorization"] = f"Bearer {auth['token']}"
            elif auth["type"] == "api_key":
                headers[auth["header"]] = auth["key"]

        response = await self.client.post(endpoint, json=inputs, headers=headers)
        response.raise_for_status()
        return response.json()
```

## Unified Tool Executor

Routes to the correct client based on URI scheme:

```python
class ToolExecutor:
    def __init__(self, mcp_client, http_client):
        self.mcp = mcp_client
        self.http = http_client

    async def execute(self, tool_uri: str, inputs: dict, auth: dict | None = None) -> dict:
        if tool_uri.startswith("mcp://"):
            return await self.mcp.call(tool_uri, inputs)
        elif tool_uri.startswith("http://") or tool_uri.startswith("https://"):
            return await self.http.call(tool_uri, inputs, auth)
        else:
            raise ValueError(f"Unknown protocol in URI: {tool_uri}")
```

## Tool Catalogue API Response

```json
GET /api/v1/tools/catalogue

{
  "tools": [
    {
      "slug": "customer-lookup",
      "name": "Customer Lookup",
      "uri": "mcp://crm-service:9000/customer-lookup",
      "protocol": "mcp",
      "description": "Finds a customer by email",
      "input_schema": {
        "type": "object",
        "properties": {
          "email": {"type": "string", "description": "Customer email"}
        },
        "required": ["email"]
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "customer_id": {"type": "string"},
          "name": {"type": "string"},
          "tier": {"type": "string", "enum": ["free", "pro", "enterprise"]},
          "past_tickets": {"type": "array"}
        }
      }
    }
  ]
}
```

## Example MCP Tool Servers

### customer-lookup/server.py
```python
from mcp.server import Server
from mcp.types import TextContent
import json

server = Server("crm-service")

@server.tool()
async def customer_lookup(email: str) -> list[TextContent]:
    """Finds a customer profile and history by their email address."""
    customer = await db.fetchone(
        "SELECT id, name, tier FROM customers WHERE email = $1", email
    )
    tickets = await db.fetch(
        "SELECT id, subject, status, created_at FROM tickets "
        "WHERE customer_id = $1 ORDER BY created_at DESC LIMIT 5",
        customer["id"]
    )
    result = {
        "customer_id": customer["id"],
        "name": customer["name"],
        "tier": customer["tier"],
        "past_tickets": [dict(t) for t in tickets],
    }
    return [TextContent(type="text", text=json.dumps(result))]

if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    asyncio.run(stdio_server(server))
```

### sentiment-analysis/server.py
```python
from mcp.server import Server
from mcp.types import TextContent
import json, joblib

server = Server("ml-services")
model = joblib.load("models/sentiment.pkl")
vectorizer = joblib.load("models/tfidf.pkl")

@server.tool()
async def sentiment_analysis(text: str) -> list[TextContent]:
    """Analyses the emotional tone of a text message."""
    features = vectorizer.transform([text])
    sentiment = model.predict(features)[0]
    confidence = float(model.predict_proba(features).max())
    result = {"sentiment": sentiment, "confidence": confidence}
    return [TextContent(type="text", text=json.dumps(result))]

if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    asyncio.run(stdio_server(server))
```

### email-sender/server.py
```python
from mcp.server import Server
from mcp.types import TextContent
import json

server = Server("email-service")

@server.tool()
async def send_email(to: str, subject: str, body: str) -> list[TextContent]:
    """Sends an email to the specified recipient."""
    # In production, use SendGrid, Mailgun, SES, etc.
    result = await email_provider.send(to=to, subject=subject, body=body)
    return [TextContent(type="text", text=json.dumps({"message_id": result.id, "status": "sent"}))]

if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    asyncio.run(stdio_server(server))
```

## MCP Server Registration Flow

1. Developer deploys an MCP server (Docker container, process, etc.)
2. Admin registers endpoint via API: POST /api/v1/tools/register
3. Control plane calls MCPDiscovery.discover(endpoint)
4. Discovered tools stored in tool_registrations table
5. Frontend fetches updated catalogue; new tools appear in dropdowns
6. Periodic re-discovery (every 5 min) via background task catches new tools
