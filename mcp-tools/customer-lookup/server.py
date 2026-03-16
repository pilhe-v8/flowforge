"""
MCP server: CRM Service — customer_lookup tool.

Provides customer profile lookups by email address.
Run with: python server.py  (stdio transport)
"""

import asyncio
import copy
import json
import logging
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)

mcp = FastMCP("crm-service")

# ---------------------------------------------------------------------------
# Sample customer data
# ---------------------------------------------------------------------------
_CUSTOMERS: dict[str, dict] = {
    "alice@example.com": {
        "customer_id": "cust-001",
        "name": "Alice Johnson",
        "tier": "enterprise",
        "past_tickets": [
            {
                "id": "TKT-1001",
                "subject": "Cannot access admin dashboard",
                "status": "resolved",
                "created_at": "2025-01-15T09:23:00Z",
            },
            {
                "id": "TKT-1042",
                "subject": "SSO integration not working",
                "status": "resolved",
                "created_at": "2025-02-10T14:05:00Z",
            },
            {
                "id": "TKT-1078",
                "subject": "Need bulk export feature",
                "status": "open",
                "created_at": "2025-03-01T11:00:00Z",
            },
        ],
    },
    "bob@startup.io": {
        "customer_id": "cust-042",
        "name": "Bob Martinez",
        "tier": "pro",
        "past_tickets": [
            {
                "id": "TKT-2200",
                "subject": "Billing charge discrepancy",
                "status": "resolved",
                "created_at": "2025-02-28T16:45:00Z",
            },
            {
                "id": "TKT-2215",
                "subject": "API rate limit too low",
                "status": "open",
                "created_at": "2025-03-10T08:30:00Z",
            },
        ],
    },
    "carol@freelance.dev": {
        "customer_id": "cust-117",
        "name": "Carol Wei",
        "tier": "free",
        "past_tickets": [],
    },
    "dave@bigcorp.com": {
        "customer_id": "cust-008",
        "name": "Dave Patel",
        "tier": "enterprise",
        "past_tickets": [
            {
                "id": "TKT-0500",
                "subject": "On-premise deployment guide",
                "status": "resolved",
                "created_at": "2024-12-20T10:00:00Z",
            },
        ],
    },
}

_GUEST_CUSTOMER = {
    "customer_id": "guest",
    "name": "Guest",
    "tier": "free",
    "past_tickets": [],
}


# ---------------------------------------------------------------------------
# Pure implementation (testable without MCP framework)
# ---------------------------------------------------------------------------
async def _customer_lookup_impl(email: str) -> dict:
    """Return customer profile for *email*, or a guest record if not found."""
    return copy.deepcopy(_CUSTOMERS.get(email.lower().strip(), _GUEST_CUSTOMER))


# ---------------------------------------------------------------------------
# MCP tool
# ---------------------------------------------------------------------------
@mcp.tool()
async def customer_lookup(email: str) -> list[TextContent]:
    """Finds a customer profile and history by their email address."""
    result = await _customer_lookup_impl(email)
    return [TextContent(type="text", text=json.dumps(result))]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # stdio transport (default — works with MCP clients and testing)
    asyncio.run(mcp.run_stdio_async())

    # SSE transport (uncomment for Docker / HTTP usage):
    # import uvicorn
    # uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=9000)
