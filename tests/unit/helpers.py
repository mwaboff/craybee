from collections.abc import AsyncIterator

from backend.services.llm.conversation import StreamChunk, Usage


async def collect(stream: AsyncIterator[StreamChunk]) -> tuple[str, Usage | None]:
    """Join chunk.text and keep the last chunk.usage from a StreamChunk stream."""
    text: list[str] = []
    usage: Usage | None = None
    async for chunk in stream:
        if chunk.text:
            text.append(chunk.text)
        if chunk.usage:
            usage = chunk.usage
    return "".join(text), usage
