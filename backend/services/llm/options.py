from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.models.llm_server import ProviderKind


class BaseOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Server-level default; a per-conversation system_prompt overrides it. Honored by all providers.
    system_prompt: str | None = None


class OpenAICompatOptions(BaseOptions):
    # Extra kwargs merged over the client's own kwargs for chat.completions.create,
    # e.g. {"temperature": 0.2}. May override or remove stream_options for servers that reject it.
    request: dict[str, Any] = Field(default_factory=dict)


class AnthropicOptions(BaseOptions):
    max_tokens: int = Field(default=16000, ge=1)


class ClaudeCliOptions(BaseOptions):
    extra_args: list[str] = Field(default_factory=list)
    cwd: str | None = None  # None -> settings.data_dir (existing behavior)


OPTIONS_BY_PROVIDER: dict[ProviderKind, type[BaseOptions]] = {
    ProviderKind.OPENAI_COMPATIBLE: OpenAICompatOptions,
    ProviderKind.ANTHROPIC: AnthropicOptions,
    ProviderKind.CLAUDE_CLI: ClaudeCliOptions,
}


def parse_options(provider: ProviderKind, raw: dict[str, Any]) -> BaseOptions:
    return OPTIONS_BY_PROVIDER[provider].model_validate(raw)
