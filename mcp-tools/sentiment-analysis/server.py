"""
MCP server: ML Services — sentiment_analysis tool.

Analyses the emotional tone of a text message using keyword heuristics.
Run with: python server.py  (stdio transport)
"""

import asyncio
import json
import logging
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)

mcp = FastMCP("ml-services")

# ---------------------------------------------------------------------------
# Keyword lists for heuristic sentiment detection
# ---------------------------------------------------------------------------
_ANGRY_WORDS = {
    "angry",
    "furious",
    "outraged",
    "unacceptable",
    "ridiculous",
    "horrible",
    "terrible",
    "disgusting",
    "awful",
    "worst",
    "hate",
    "demand",
    "useless",
    "incompetent",
    "scam",
    "fraud",
    "appalling",
    "pathetic",
    "disgusted",
    "livid",
    "infuriated",
    "enraged",
}

_POSITIVE_WORDS = {
    "great",
    "excellent",
    "amazing",
    "wonderful",
    "fantastic",
    "love",
    "happy",
    "pleased",
    "satisfied",
    "good",
    "awesome",
    "brilliant",
    "perfect",
    "thank",
    "thanks",
    "appreciate",
    "helpful",
    "impressed",
    "outstanding",
    "superb",
    "delighted",
    "thrilled",
    "glad",
}

_NEGATIVE_WORDS = {
    "bad",
    "poor",
    "disappointed",
    "frustrating",
    "annoying",
    "broken",
    "issue",
    "problem",
    "error",
    "fail",
    "failed",
    "unusable",
    "slow",
    "wrong",
    "unhappy",
    "dissatisfied",
    "concern",
    "bug",
    "crash",
    "missing",
    "unable",
    "cannot",
    "stuck",
    "lost",
}


# ---------------------------------------------------------------------------
# Pure implementation (testable without MCP framework)
# ---------------------------------------------------------------------------
async def _sentiment_analysis_impl(text: str) -> dict:
    """Classify sentiment of *text* using keyword heuristics.

    Returns a dict with ``sentiment`` and ``confidence`` keys.
    """
    lowered = text.lower()
    words = set(lowered.split())

    angry_hits = len(words & _ANGRY_WORDS)
    positive_hits = len(words & _POSITIVE_WORDS)
    negative_hits = len(words & _NEGATIVE_WORDS)

    total_hits = angry_hits + positive_hits + negative_hits

    if total_hits == 0:
        return {"sentiment": "neutral", "confidence": 0.5}

    if angry_hits >= positive_hits and angry_hits >= negative_hits:
        sentiment = "angry"
        hits = angry_hits
    elif positive_hits >= negative_hits:
        sentiment = "positive"
        hits = positive_hits
    else:
        sentiment = "negative"
        hits = negative_hits

    # Confidence: saturates at ~5 keyword hits → 0.95
    confidence = min(0.5 + hits * 0.1, 0.95)
    return {"sentiment": sentiment, "confidence": round(confidence, 2)}


# ---------------------------------------------------------------------------
# MCP tool
# ---------------------------------------------------------------------------
@mcp.tool()
async def sentiment_analysis(text: str) -> list[TextContent]:
    """Analyses the emotional tone of a text message."""
    result = await _sentiment_analysis_impl(text)
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

        uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=9001)
