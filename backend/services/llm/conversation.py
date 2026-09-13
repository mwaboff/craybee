from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.services.llm import LLMClient


class Role(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class Usage(BaseModel):
    """Token accounting for one request. `input_tokens` is UNCACHED input only, so
    total = input + output + cache_read + cache_write holds for every provider."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float | None = None  # only the CLI reports this today
    context_window: int | None = None  # model's window size when the provider reports it (CLI only today)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_read_tokens + self.cache_write_tokens

    def __add__(self, other: Usage) -> Usage:
        if other.cost_usd is not None and self.cost_usd is not None:
            cost_usd = self.cost_usd + other.cost_usd
        else:
            cost_usd = other.cost_usd if other.cost_usd is not None else self.cost_usd
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
            cost_usd=cost_usd,
            context_window=other.context_window if other.context_window is not None else self.context_window,
        )


class StreamChunk(BaseModel):
    text: str | None = None
    usage: Usage | None = None


class Turn(BaseModel):
    role: Role
    content: str
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    partial: bool = False  # assistant turn cut short by error or cancel
    usage: Usage | None = None  # assistant turns only, when the provider reported it


class Conversation:
    def __init__(
        self,
        *,
        client: LLMClient,
        system_prompt: str | None = None,
        model: str | None = None,
        turns: list[Turn] | None = None,
    ) -> None:
        self._client = client
        self.system_prompt = system_prompt
        self.model = model
        # Shared with the caller (not copied): callers that own long-lived history
        # (e.g. the conversation registry) rely on this list being the same object,
        # so appends here are visible to them without any write-back step.
        self.turns: list[Turn] = turns if turns is not None else []

    @property
    def usage(self) -> Usage:
        total = Usage()
        for turn in self.turns:
            if turn.role is Role.ASSISTANT and turn.usage is not None:
                total = total + turn.usage
        return total

    @property
    def context_tokens(self) -> int:
        for turn in reversed(self.turns):
            if turn.role is Role.ASSISTANT and turn.usage is not None:
                usage = turn.usage
                return usage.input_tokens + usage.cache_read_tokens + usage.cache_write_tokens + usage.output_tokens
        return 0

    async def send(self, content: str) -> AsyncIterator[str]:
        self.turns.append(Turn(role=Role.USER, content=content))
        collected: list[str] = []
        usage: Usage | None = None
        completed = False
        try:
            async for chunk in self._client.stream_chat(
                list(self.turns), system_prompt=self.system_prompt, model=self.model
            ):
                if chunk.text:
                    collected.append(chunk.text)
                    yield chunk.text
                if chunk.usage:
                    usage = chunk.usage
            completed = True
        finally:
            if collected:
                self.turns.append(
                    Turn(
                        role=Role.ASSISTANT,
                        content="".join(collected),
                        partial=not completed,
                        usage=usage,
                    )
                )
            else:
                self.turns.pop()  # nothing came back: do not leave a dangling user turn
