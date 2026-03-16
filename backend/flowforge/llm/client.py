"""LLM client — thin wrapper around litellm for async chat completions."""

import litellm
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Typed wrapper around a chat completion response."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int


class LLMClient:
    """Async LLM client backed by litellm (supports OpenAI, Anthropic, etc.)."""

    def __init__(self, default_model: str = "gpt-4o-mini"):
        self.default_model = default_model

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> LLMResponse:
        """Send a chat completion request and return an :class:`LLMResponse`.

        Args:
            messages: OpenAI-style message list, e.g.
                      [{"role": "system", "content": "..."}, ...]
            model:    Override the default model for this request.
        """
        model = model or self.default_model
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            temperature=0.3,
        )
        return LLMResponse(
            content=response.choices[0].message.content,
            model=model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
