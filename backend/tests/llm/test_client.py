"""Tests for LLMClient."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import is_dataclass

from flowforge.llm.client import LLMClient, LLMResponse


def make_litellm_response(content: str, model: str, prompt_tokens: int, completion_tokens: int):
    """Build a mock litellm response with the expected structure."""
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
        resp = LLMResponse(
            content="hello",
            model="gpt-4o-mini",
            input_tokens=10,
            output_tokens=5,
        )
        assert resp.content == "hello"
        assert resp.model == "gpt-4o-mini"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5


class TestLLMClientChat:
    @pytest.mark.asyncio
    async def test_calls_litellm_acompletion(self):
        """chat() should call litellm.acompletion with correct args."""
        mock_response = make_litellm_response("Hi there", "gpt-4o-mini", 10, 5)
        messages = [{"role": "user", "content": "Hello"}]

        with patch(
            "flowforge.llm.client.litellm.acompletion", new=AsyncMock(return_value=mock_response)
        ) as mock_acompletion:
            client = LLMClient()
            await client.chat(messages)

        mock_acompletion.assert_awaited_once()
        call_kwargs = mock_acompletion.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs["messages"] == messages
        assert call_kwargs["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_returns_llm_response(self):
        """chat() should return a properly mapped LLMResponse."""
        mock_response = make_litellm_response("Result text", "gpt-4o-mini", 20, 8)

        with patch(
            "flowforge.llm.client.litellm.acompletion", new=AsyncMock(return_value=mock_response)
        ):
            client = LLMClient()
            result = await client.chat([{"role": "user", "content": "test"}])

        assert isinstance(result, LLMResponse)
        assert result.content == "Result text"
        assert result.model == "gpt-4o-mini"
        assert result.input_tokens == 20
        assert result.output_tokens == 8

    @pytest.mark.asyncio
    async def test_model_override(self):
        """Passing model= should override the default."""
        mock_response = make_litellm_response("ok", "claude-3-haiku", 5, 3)

        with patch(
            "flowforge.llm.client.litellm.acompletion", new=AsyncMock(return_value=mock_response)
        ) as mock_acompletion:
            client = LLMClient(default_model="gpt-4o-mini")
            result = await client.chat([{"role": "user", "content": "hi"}], model="claude-3-haiku")

        call_kwargs = mock_acompletion.call_args[1]
        assert call_kwargs["model"] == "claude-3-haiku"
        assert result.model == "claude-3-haiku"

    @pytest.mark.asyncio
    async def test_default_model_used_when_not_specified(self):
        """When model= is not passed, default_model should be used."""
        mock_response = make_litellm_response("response", "gpt-4o", 1, 1)

        with patch(
            "flowforge.llm.client.litellm.acompletion", new=AsyncMock(return_value=mock_response)
        ) as mock_acompletion:
            client = LLMClient(default_model="gpt-4o")
            await client.chat([{"role": "user", "content": "hi"}])

        call_kwargs = mock_acompletion.call_args[1]
        assert call_kwargs["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_token_counts_mapped_correctly(self):
        """input_tokens and output_tokens should be mapped from prompt/completion tokens."""
        mock_response = make_litellm_response("text", "gpt-4o-mini", 100, 50)

        with patch(
            "flowforge.llm.client.litellm.acompletion", new=AsyncMock(return_value=mock_response)
        ):
            client = LLMClient()
            result = await client.chat([{"role": "user", "content": "test"}])

        assert result.input_tokens == 100
        assert result.output_tokens == 50
