"""
MCP server: Email Service — send_email tool.

Stub email sender that logs the message and returns a fake message ID.
Run with: python server.py  (stdio transport)
"""

import asyncio
import json
import logging
from uuid import uuid4
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("email-service")


# ---------------------------------------------------------------------------
# Pure implementation (testable without MCP framework)
# ---------------------------------------------------------------------------
async def _send_email_impl(to: str, subject: str, body: str) -> dict:
    """Stub email sender — logs the message and returns a fake message_id."""
    message_id = str(uuid4())
    logger.info(
        "Sending email",
        extra={
            "message_id": message_id,
            "to": to,
            "subject": subject,
            "body_preview": body[:120],
        },
    )
    return {"message_id": message_id, "status": "sent"}


# ---------------------------------------------------------------------------
# MCP tool
# ---------------------------------------------------------------------------
@mcp.tool()
async def send_email(to: str, subject: str, body: str) -> list[TextContent]:
    """Sends an email to the specified recipient."""
    result = await _send_email_impl(to, subject, body)
    return [TextContent(type="text", text=json.dumps(result))]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if "--stdio" in sys.argv:
        # stdio transport (useful for local MCP client testing)
        asyncio.run(mcp.run_stdio_async())
    else:
        # SSE transport (default — required for Docker / HTTP deployments)
        import uvicorn

        uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=9006)
