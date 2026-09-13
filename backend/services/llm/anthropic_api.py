from collections.abc import AsyncIterator
from typing import Any

import anthropic

from backend.core.exceptions import LLMError
from backend.services.llm.conversation import StreamChunk, Turn, Usage
from backend.services.llm.options import AnthropicOptions

DEFAULT_MODEL = "claude-opus-5"


class AnthropicClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None,
        default_model: str | None,
        options: AnthropicOptions,
    ) -> None:
        # base_url=None falls back to the SDK default.
        self._client = anthropic.AsyncAnthropic(api_key=api_key, base_url=base_url)
        self._model = default_model or DEFAULT_MODEL
        self._options = options

    async def list_models(self) -> list[str]:
        try:
            return [m.id async for m in self._client.models.list()]  # auto-paginates
        except anthropic.AnthropicError as exc:
            raise LLMError(f"anthropic: {exc}") from exc

    async def stream_chat(
        self,
        messages: list[Turn],
        *,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        system = system_prompt or self._options.system_prompt
        kwargs: dict[str, Any] = {"system": system} if system else {}
        try:
            async with self._client.messages.stream(
                model=model or self._model,
                max_tokens=self._options.max_tokens,
                messages=[{"role": t.role.value, "content": t.content} for t in messages],
                **kwargs,
            ) as stream:
                async for text in stream.text_stream:
                    yield StreamChunk(text=text)
                final = await stream.get_final_message()
                if final.usage is not None:
                    yield StreamChunk(
                        usage=Usage(
                            input_tokens=final.usage.input_tokens,
                            output_tokens=final.usage.output_tokens,
                            cache_read_tokens=final.usage.cache_read_input_tokens or 0,
                            cache_write_tokens=final.usage.cache_creation_input_tokens or 0,
                        )
                    )
        except anthropic.AnthropicError as exc:
            raise LLMError(f"anthropic: {exc}") from exc

    async def aclose(self) -> None:
        await self._client.close()
