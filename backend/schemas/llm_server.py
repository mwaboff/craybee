from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from backend.models.llm_server import ProviderKind
from backend.services.llm.options import parse_options

CAPABILITY_FIELDS = (
    "supports_tools",
    "supports_vision",
    "supports_streaming",
    "supports_structured_output",
)

# Defaults applied when the create body omits a flag. Keyed in CAPABILITY_FIELDS order.
CAPABILITY_DEFAULTS: dict[ProviderKind, tuple[bool, bool, bool, bool]] = {
    ProviderKind.OPENAI_COMPATIBLE: (False, False, True, False),
    ProviderKind.ANTHROPIC: (True, True, True, True),
    ProviderKind.CLAUDE_CLI: (True, True, True, False),
}


def check_provider_rules(
    provider: ProviderKind,
    *,
    base_url: str | None,
    api_key: str | None,
    options: dict[str, Any],
) -> None:
    """Per-provider required fields and options shape. Shared by create validation and the
    patch path."""
    if provider is ProviderKind.OPENAI_COMPATIBLE and not base_url:
        raise ValueError("base_url is required for openai_compatible servers")
    if provider is ProviderKind.ANTHROPIC and not api_key:
        raise ValueError("api_key is required for anthropic servers")
    try:
        parse_options(provider, options)
    except ValidationError as exc:
        msg = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise ValueError(f"options: {msg}") from exc


class LLMServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: ProviderKind
    base_url: str | None = None
    api_key: str | None = None
    executable_path: str | None = None
    default_model: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    # None means "use the provider default"; after validation these are always bool.
    supports_tools: bool | None = None
    supports_vision: bool | None = None
    supports_streaming: bool | None = None
    supports_structured_output: bool | None = None
    is_enabled: bool = True
    is_default: bool = False

    @model_validator(mode="after")
    def _provider_rules(self) -> LLMServerCreate:
        check_provider_rules(
            self.provider, base_url=self.base_url, api_key=self.api_key, options=self.options
        )
        defaults = CAPABILITY_DEFAULTS[self.provider]
        for field, default in zip(CAPABILITY_FIELDS, defaults, strict=True):
            if getattr(self, field) is None:
                setattr(self, field, default)
        return self


class LLMServerUpdate(BaseModel):
    """Partial update. Only fields present in the body are applied;
    `api_key: null` clears the key, omitting it keeps the current one."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    provider: ProviderKind | None = None
    base_url: str | None = None
    api_key: str | None = None
    executable_path: str | None = None
    default_model: str | None = None
    options: dict[str, Any] | None = None
    supports_tools: bool | None = None
    supports_vision: bool | None = None
    supports_streaming: bool | None = None
    supports_structured_output: bool | None = None
    is_enabled: bool | None = None


class LLMServerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    provider: ProviderKind
    base_url: str | None
    has_api_key: bool  # comes from the ORM property; api_key is not a field here, so it cannot leak
    executable_path: str | None
    default_model: str | None
    options: dict[str, Any]
    supports_tools: bool
    supports_vision: bool
    supports_streaming: bool
    supports_structured_output: bool
    is_default: bool
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def _assume_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class ModelList(BaseModel):
    models: list[str]
