"""Tests for HTTPToolClient."""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from flowforge.tools.http_client import HTTPToolClient


def make_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


@pytest.fixture
def http_client():
    return HTTPToolClient()


@pytest.mark.asyncio
async def test_successful_post(http_client):
    """A 200 response should return parsed JSON."""
    expected = {"status": "ok", "data": 42}
    mock_resp = make_response(expected)

    with patch.object(http_client.client, "post", new=AsyncMock(return_value=mock_resp)):
        result = await http_client.call("https://api.example.com/tool", {"input": "hello"})

    assert result == expected


@pytest.mark.asyncio
async def test_bearer_auth_header(http_client):
    """Bearer auth should set Authorization header."""
    mock_resp = make_response({"ok": True})
    post_mock = AsyncMock(return_value=mock_resp)

    with patch.object(http_client.client, "post", new=post_mock):
        await http_client.call(
            "https://api.example.com/tool",
            {},
            auth={"type": "bearer", "token": "mytoken"},
        )

    _, kwargs = post_mock.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer mytoken"


@pytest.mark.asyncio
async def test_api_key_auth_header(http_client):
    """API key auth should set the configured header name."""
    mock_resp = make_response({"ok": True})
    post_mock = AsyncMock(return_value=mock_resp)

    with patch.object(http_client.client, "post", new=post_mock):
        await http_client.call(
            "https://api.example.com/tool",
            {},
            auth={"type": "api_key", "header": "X-API-Key", "key": "secret-key"},
        )

    _, kwargs = post_mock.call_args
    assert kwargs["headers"]["X-API-Key"] == "secret-key"


@pytest.mark.asyncio
async def test_no_auth_no_extra_headers(http_client):
    """When no auth is provided, headers dict should be empty."""
    mock_resp = make_response({"ok": True})
    post_mock = AsyncMock(return_value=mock_resp)

    with patch.object(http_client.client, "post", new=post_mock):
        await http_client.call("https://api.example.com/tool", {"x": 1})

    _, kwargs = post_mock.call_args
    assert kwargs["headers"] == {}


@pytest.mark.asyncio
async def test_raises_on_non_2xx_response(http_client):
    """A 4xx/5xx response should raise an exception."""
    mock_resp = make_response({}, status_code=404)

    with patch.object(http_client.client, "post", new=AsyncMock(return_value=mock_resp)):
        with pytest.raises(httpx.HTTPStatusError):
            await http_client.call("https://api.example.com/tool", {})


@pytest.mark.asyncio
async def test_posts_inputs_as_json(http_client):
    """Inputs should be sent as JSON body."""
    mock_resp = make_response({"result": "done"})
    post_mock = AsyncMock(return_value=mock_resp)
    payload = {"name": "Alice", "age": 30}

    with patch.object(http_client.client, "post", new=post_mock):
        await http_client.call("https://api.example.com/tool", payload)

    _, kwargs = post_mock.call_args
    assert kwargs["json"] == payload


@pytest.mark.asyncio
async def test_close_calls_aclose(http_client):
    """close() should call aclose on the underlying httpx client."""
    with patch.object(http_client.client, "aclose", new=AsyncMock()) as aclose_mock:
        await http_client.close()
    aclose_mock.assert_awaited_once()
