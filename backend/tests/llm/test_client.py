"""Tests for LLMClient — proxy-based implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import is_dataclass

from flowforge.llm.client import LLMClient, LLMResponse

BASE_URL = "http://localhost:4000"
API_KEY = "sk-test"


def make_openai_response(content: str, model: str, prompt_tokens: int, completion_tokens: int):
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


class TestLLMResponse:
    def test_is_dataclass(self):
        assert is_dataclass(LLMResponse)

    def test_fields(self):
        resp = LLMResponse(content="hello", model="default", input_tokens=10, output_tokens=5)
        assert resp.content == "hello"
        assert resp.model == "default"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5


class TestLLMClientChat:
    def _make_client(self, default_model: str = "default") -> LLMClient:
        return LLMClient(base_url=BASE_URL, api_key=API_KEY, default_model=default_model)

    @pytest.mark.asyncio
    async def test_calls_openai_create(self):
        mock_response = make_openai_response("Hi there", "default", 10, 5)
        messages = [{"role": "user", "content": "Hello"}]
        with patch("flowforge.llm.client.openai.AsyncOpenAI") as MockAsyncOpenAI:
            mock_create = AsyncMock(return_value=mock_response)
            MockAsyncOpenAI.return_value.chat.completions.create = mock_create
            client = self._make_client()
            await client.chat(messages)
        mock_create.assert_awaited_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["model"] == "default"
        assert call_kwargs["messages"] == messages
        assert call_kwargs["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_returns_llm_response(self):
        mock_response = make_openai_response("Result text", "default", 20, 8)
        with patch("flowforge.llm.client.openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value.chat.completions.create = AsyncMock(
                return_value=mock_response
            )
            client = self._make_client()
            result = await client.chat([{"role": "user", "content": "test"}])
        assert isinstance(result, LLMResponse)
        assert result.content == "Result text"
        assert result.model == "default"
        assert result.input_tokens == 20
        assert result.output_tokens == 8

    @pytest.mark.asyncio
    async def test_model_override(self):
        mock_response = make_openai_response("ok", "azure-fallback", 5, 3)
        with patch("flowforge.llm.client.openai.AsyncOpenAI") as MockAsyncOpenAI:
            mock_create = AsyncMock(return_value=mock_response)
            MockAsyncOpenAI.return_value.chat.completions.create = mock_create
            client = self._make_client(default_model="default")
            result = await client.chat([{"role": "user", "content": "hi"}], model="azure-fallback")
        assert mock_create.call_args[1]["model"] == "azure-fallback"
        assert result.model == "azure-fallback"

    @pytest.mark.asyncio
    async def test_default_model_used_when_not_specified(self):
        mock_response = make_openai_response("response", "default", 1, 1)
        with patch("flowforge.llm.client.openai.AsyncOpenAI") as MockAsyncOpenAI:
            mock_create = AsyncMock(return_value=mock_response)
            MockAsyncOpenAI.return_value.chat.completions.create = mock_create
            client = self._make_client(default_model="default")
            await client.chat([{"role": "user", "content": "hi"}])
        assert mock_create.call_args[1]["model"] == "default"

    @pytest.mark.asyncio
    async def test_token_counts_mapped_correctly(self):
        mock_response = make_openai_response("text", "default", 100, 50)
        with patch("flowforge.llm.client.openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value.chat.completions.create = AsyncMock(
                return_value=mock_response
            )
            client = self._make_client()
            result = await client.chat([{"role": "user", "content": "test"}])
        assert result.input_tokens == 100
        assert result.output_tokens == 50

    @pytest.mark.asyncio
    async def test_proxy_base_url_and_key_passed_to_client(self):
        mock_response = make_openai_response("ok", "default", 1, 1)
        with patch("flowforge.llm.client.openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value.chat.completions.create = AsyncMock(
                return_value=mock_response
            )
            LLMClient(base_url="http://proxy:4000", api_key="sk-secret")
        MockAsyncOpenAI.assert_called_once_with(base_url="http://proxy:4000", api_key="sk-secret")
