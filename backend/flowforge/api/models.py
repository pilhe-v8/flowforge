"""Proxy LiteLLM /v1/models to the frontend — avoids CORS and network issues."""

import httpx
from fastapi import APIRouter, Depends
from flowforge.api.deps import get_current_user
from flowforge.config import get_settings

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def list_models(
    _: dict = Depends(get_current_user),  # require JWT — same pattern as rest of API
):
    """Proxy GET /v1/models from LiteLLM to the browser.

    Returns a JSON object with a 'data' array of model objects (each has an 'id' field).
    Falls back to the two known static models if LiteLLM is unreachable.
    """
    settings = get_settings()
    url = f"{settings.litellm_url}/v1/models"
    headers = {"Authorization": f"Bearer {settings.litellm_master_key}"}
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            # Graceful fallback — return known static models
            return {
                "data": [
                    {"id": "default"},
                    {"id": "azure-fallback"},
                ]
            }
