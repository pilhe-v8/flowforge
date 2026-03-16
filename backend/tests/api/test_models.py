"""Tests for GET /api/v1/models proxy endpoint."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from flowforge.main import app
from flowforge.api.deps import get_current_user

FAKE_USER = {"sub": "user-1", "tenant_id": "test-tenant", "role": "editor"}


def override_deps():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return TestClient(app)


def clear_overrides():
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_models_endpoint_returns_fallback_when_litellm_down():
    """When LiteLLM is unreachable, endpoint returns static fallback models."""
    with patch("flowforge.api.models.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get.side_effect = Exception("LiteLLM down")
        mock_client_cls.return_value = mock_client

        client = override_deps()
        try:
            response = client.get("/api/v1/models")
            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            ids = [m["id"] for m in data["data"]]
            assert "default" in ids
            assert "azure-fallback" in ids
        finally:
            clear_overrides()


def test_models_endpoint_requires_auth():
    """Without a JWT the endpoint should return 401."""
    clear_overrides()  # ensure no overrides are active
    client = TestClient(app)
    response = client.get("/api/v1/models")
    assert response.status_code == 401
