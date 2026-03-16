"""LLM client — calls the LiteLLM Proxy via the OpenAI-compatible HTTP API."""

import openai
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Typed wrapper around a chat completion response."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int


class LLMClient:
    """Async LLM client that calls a LiteLLM Proxy endpoint.

    The proxy is OpenAI-API-compatible, so we use the standard openai SDK
    pointed at the proxy's base URL. The proxy handles provider routing,
    retries, and fallback — this client stays credential-free.

    Args:
        base_url:      Full URL of the LiteLLM Proxy, e.g. ``http://litellm:4000``.
        api_key:       LiteLLM master key (set in the proxy's general_settings).
        default_model: Virtual model name declared in ``litellm.config.yaml``.
                       Defaults to ``"default"`` (Mistral primary → Azure fallback).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:4000",
        api_key: str = "sk-flowforge-local",
        default_model: str = "default",
    ):
        self._client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.default_model = default_model

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> LLMResponse:
        """Send a chat completion request via the LiteLLM Proxy.

        Args:
            messages: OpenAI-style message list.
            model:    Override the virtual model name for this request.
                      Must match a ``model_name`` in ``litellm.config.yaml``.

        Raises:
            openai.APIConnectionError: The proxy could not be reached (network
                failure, wrong ``base_url``, proxy not running, etc.).
            openai.RateLimitError: The proxy returned HTTP 429 (rate limit
                exceeded on the upstream provider or the proxy itself).
            openai.APIStatusError: Any other non-2xx HTTP response from the
                proxy (e.g. 400 bad request, 500 server error). The status
                code and response body are available on the exception.
        """
        target_model = model or self.default_model
        response = await self._client.chat.completions.create(
            model=target_model,
            messages=messages,
            temperature=0.3,
        )
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        return LLMResponse(
            content=response.choices[0].message.content,
            model=target_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
