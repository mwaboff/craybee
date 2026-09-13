from collections.abc import AsyncIterator
from typing import Any

import openai
from openai import AsyncOpenAI

from backend.core.exceptions import LLMError
from backend.services.llm.conversation import StreamChunk, Turn, Usage
from backend.services.llm.options import OpenAICompatOptions


def _map_usage(usage: Any) -> Usage:
    details = usage.prompt_tokens_details
    cached = (details.cached_tokens or 0) if details else 0
    return Usage(
        input_tokens=usage.prompt_tokens - cached,
        output_tokens=usage.completion_tokens,
        cache_read_tokens=cached,
        cache_write_tokens=0,
    )


class OpenAICompatClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        default_model: str | None,
        options: OpenAICompatOptions,
    ) -> None:
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self._model = default_model or "local-model"
        self._options = options

    async def list_models(self) -> list[str]:
        try:
            response = await self._client.models.list()
        except openai.OpenAIError as exc:
            raise LLMError(f"openai: {exc}") from exc
        return [m.id for m in response.data]

    async def stream_chat(
        self,
        messages: list[Turn],
        *,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        system = system_prompt or self._options.system_prompt
        chat_messages: list[dict[str, str]] = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages += [{"role": t.role.value, "content": t.content} for t in messages]
        kwargs: dict[str, Any] = {"stream_options": {"include_usage": True}, **self._options.request}
        try:
            stream = await self._client.chat.completions.create(
                model=model or self._model,
                messages=chat_messages,
                stream=True,
                **kwargs,
            )
            async for chunk in stream:
                if chunk.choices and (delta := chunk.choices[0].delta.content):
                    yield StreamChunk(text=delta)
                if chunk.usage:
                    yield StreamChunk(usage=_map_usage(chunk.usage))
        except openai.OpenAIError as exc:
            raise LLMError(f"openai: {exc}") from exc

    async def aclose(self) -> None:
        await self._client.close()
