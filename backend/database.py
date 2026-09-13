from collections.abc import AsyncIterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._sessions: async_sessionmaker[AsyncSession] | None = None

    def configure(self, url: str | None = None) -> None:
        """(Re)bind to a URL. Call before the app starts; tests use this."""
        settings = get_settings()
        self._engine = create_async_engine(url or settings.database_url, echo=settings.debug)
        self._sessions = async_sessionmaker(self._engine, expire_on_commit=False)

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            self.configure()
        assert self._engine is not None
        return self._engine

    def session(self) -> AsyncSession:
        if self._sessions is None:
            self.configure()
        assert self._sessions is not None
        return self._sessions()

    async def migrate(self) -> None:
        """Apply pending Alembic migrations on this engine. Alembic is sync, hence run_sync."""

        def _upgrade(connection: Connection) -> None:
            cfg = alembic_config()
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")

        async with self.engine.begin() as conn:
            await conn.run_sync(_upgrade)

    async def dispose(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
        self._engine = None
        self._sessions = None


def alembic_config(url: str | None = None) -> Config:
    """Programmatic Alembic config: no alembic.ini; scripts live inside the package."""
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    if url is not None:
        cfg.set_main_option("sqlalchemy.url", url)
    return cfg


db = Database()


async def get_db() -> AsyncIterator[AsyncSession]:
    async with db.session() as session:
        yield session
