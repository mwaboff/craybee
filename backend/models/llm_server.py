import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class ProviderKind(StrEnum):
    OPENAI_COMPATIBLE = "openai_compatible"
    ANTHROPIC = "anthropic"
    CLAUDE_CLI = "claude_cli"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class LLMServer(Base):
    __tablename__ = "llm_servers"
    __table_args__ = (
        # At most one default. Partial index; hand-written in migration 0001.
        Index(
            "ux_llm_servers_default",
            "is_default",
            unique=True,
            sqlite_where=text("is_default = 1"),
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    name: Mapped[str] = mapped_column(String, unique=True)
    provider: Mapped[ProviderKind] = mapped_column(
        Enum(
            ProviderKind,
            name="provider_kind",
            native_enum=False,
            create_constraint=True,  # emit CHECK(provider IN (...)); off by default since SA 1.4
            values_callable=lambda e: [m.value for m in e],  # store "anthropic", not "ANTHROPIC"
        )
    )
    # Opaque: the literal URL the client calls, path included.
    base_url: Mapped[str | None] = mapped_column(String, default=None)
    api_key: Mapped[str | None] = mapped_column(String, default=None)
    executable_path: Mapped[str | None] = mapped_column(String, default=None)
    default_model: Mapped[str | None] = mapped_column(String, default=None)
    options: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default=text("'{}'"))
    # Capabilities of the default model. Recorded now; adapters act on them in a follow-up.
    # No Python defaults here: the create schema fills them per provider.
    supports_tools: Mapped[bool] = mapped_column(Boolean)
    supports_vision: Mapped[bool] = mapped_column(Boolean)
    supports_streaming: Mapped[bool] = mapped_column(Boolean)
    supports_structured_output: Mapped[bool] = mapped_column(Boolean)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    @property
    def has_api_key(self) -> bool:
        """Read by LLMServerRead via from_attributes; the key itself never leaves the server."""
        return bool(self.api_key)
