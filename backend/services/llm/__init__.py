from collections.abc import AsyncIterator
from typing import Protocol

from backend.core.exceptions import LLMError
from backend.models.llm_server import LLMServer, ProviderKind
from backend.services.llm.anthropic_api import AnthropicClient
from backend.services.llm.claude_cli import ClaudeCliClient
from backend.services.llm.conversation import StreamChunk, Turn
from backend.services.llm.openai_compat import OpenAICompatClient
from backend.services.llm.options import AnthropicOptions, ClaudeCliOptions, OpenAICompatOptions


class LLMClient(Protocol):
    def stream_chat(
        self, messages: list[Turn], *, system_prompt: str | None = None, model: str | None = None
    ) -> AsyncIterator[StreamChunk]: ...
    async def list_models(self) -> list[str]: ...
    async def aclose(self) -> None: ...


def build_client(server: LLMServer) -> LLMClient:
    match server.provider:
        case ProviderKind.OPENAI_COMPATIBLE:
            return OpenAICompatClient(
                base_url=server.base_url or "",
                api_key=server.api_key or "not-needed",
                default_model=server.default_model,
                options=OpenAICompatOptions.model_validate(server.options),
            )
        case ProviderKind.ANTHROPIC:
            return AnthropicClient(
                api_key=server.api_key or "",
                base_url=server.base_url,
                default_model=server.default_model,
                options=AnthropicOptions.model_validate(server.options),
            )
        case ProviderKind.CLAUDE_CLI:
            return ClaudeCliClient(
                executable=server.executable_path or "claude",
                default_model=server.default_model,
                options=ClaudeCliOptions.model_validate(server.options),
            )
    raise LLMError(f"Unsupported provider {server.provider!r}")
