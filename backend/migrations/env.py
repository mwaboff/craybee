import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from backend.database import Base
from backend.models import LLMServer  # noqa: F401  registers tables on Base.metadata

config = context.config
target_metadata = Base.metadata


def _configure_and_run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite cannot ALTER most things; batch mode rebuilds the table
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_with_own_engine() -> None:
    engine = create_async_engine(config.get_main_option("sqlalchemy.url"), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_configure_and_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
elif (shared := config.attributes.get("connection")) is not None:
    _configure_and_run(shared)  # app startup and tests: connection handed over via run_sync
else:
    asyncio.run(_run_with_own_engine())  # `craybee db ...` CLI
