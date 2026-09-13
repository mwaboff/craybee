"""llm_servers

Revision ID: 0001
Revises:
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same type object as the model so compare_type never sees a diff.
PROVIDER_KIND = sa.Enum(
    "openai_compatible",
    "anthropic",
    "claude_cli",
    name="provider_kind",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    op.create_table(
        "llm_servers",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("provider", PROVIDER_KIND, nullable=False),
        sa.Column("base_url", sa.String(), nullable=True),
        sa.Column("api_key", sa.String(), nullable=True),
        sa.Column("executable_path", sa.String(), nullable=True),
        sa.Column("default_model", sa.String(), nullable=True),
        sa.Column("options", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("supports_tools", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("supports_vision", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("supports_streaming", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "supports_structured_output", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    # Hand-written: autogenerate does not diff sqlite_where.
    op.create_index(
        "ux_llm_servers_default",
        "llm_servers",
        ["is_default"],
        unique=True,
        sqlite_where=sa.text("is_default = 1"),
    )


def downgrade() -> None:
    op.drop_index("ux_llm_servers_default", table_name="llm_servers")
    op.drop_table("llm_servers")
