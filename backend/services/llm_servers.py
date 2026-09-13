"""CRUD, default selection, and first-start seeding for saved LLM servers."""

import logging

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings
from backend.core.exceptions import ConflictError, CraybeeError, NotFoundError
from backend.database import db
from backend.models.llm_server import LLMServer, ProviderKind
from backend.schemas.llm_server import LLMServerCreate, LLMServerUpdate, check_provider_rules
from backend.services.llm import LLMClient, build_client

logger = logging.getLogger(__name__)
SEED_NAME = "Local (from env)"


async def list_servers(session: AsyncSession) -> list[LLMServer]:
    return list(await session.scalars(select(LLMServer).order_by(LLMServer.created_at)))


async def get(session: AsyncSession, server_id: str) -> LLMServer:
    server = await session.get(LLMServer, server_id)
    if server is None:
        raise NotFoundError(f"No LLM server with id {server_id}")
    return server


async def get_default(session: AsyncSession) -> LLMServer:
    server = await session.scalar(
        select(LLMServer).where(LLMServer.is_default.is_(True), LLMServer.is_enabled.is_(True))
    )
    if server is None:
        raise NotFoundError("No enabled default LLM server is configured")
    return server


async def create(session: AsyncSession, body: LLMServerCreate) -> LLMServer:
    if body.is_default:
        await _clear_default(session)
    server = LLMServer(**body.model_dump())
    session.add(server)
    await _commit_or_conflict(session, body.name)
    return server


async def patch(session: AsyncSession, server_id: str, body: LLMServerUpdate) -> LLMServer:
    server = await get(session, server_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(server, field, value)
    try:
        check_provider_rules(
            server.provider,
            base_url=server.base_url,
            api_key=server.api_key,
            options=server.options,
        )
    except ValueError as exc:
        await session.rollback()
        raise CraybeeError(str(exc)) from exc
    if server.is_default and not server.is_enabled:
        await session.rollback()
        raise ConflictError("The default server cannot be disabled; set another default first")
    await _commit_or_conflict(session, server.name)
    return server


async def delete(session: AsyncSession, server_id: str) -> None:
    server = await get(session, server_id)
    if server.is_default:
        raise ConflictError("Cannot delete the default server; set another default first")
    await session.delete(server)
    await session.commit()


async def set_default(session: AsyncSession, server_id: str) -> LLMServer:
    server = await get(session, server_id)
    if not server.is_enabled:
        raise ConflictError("A disabled server cannot be the default")
    # Same transaction: clear, then set, so the partial unique index never sees two defaults.
    await _clear_default(session)
    server.is_default = True
    await session.commit()
    return server


async def list_models(server: LLMServer) -> list[str]:
    client = build_client(server)
    try:
        return await client.list_models()
    finally:
        await client.aclose()


async def open_default_client() -> tuple[LLMServer, LLMClient]:
    """For background work with no request session (runner, slash commands)."""
    async with db.session() as session:
        server = await get_default(session)
    return server, build_client(server)


async def seed_from_settings(session: AsyncSession, settings: Settings) -> None:
    """First start only: turn the CRAYBEE_LLM_* env settings into the default server row."""
    if await session.scalar(select(LLMServer.id).limit(1)) is not None:
        return
    # Go through the create schema so capability defaults are applied in exactly one place.
    body = LLMServerCreate(
        name=SEED_NAME,
        provider=ProviderKind.OPENAI_COMPATIBLE,
        # The /v1 suffix is added here, once. Nothing downstream appends anything.
        base_url=f"{settings.llm_scheme}://{settings.llm_host}:{settings.llm_port}/v1",
        default_model=settings.llm_model,
        is_default=True,
    )
    session.add(LLMServer(**body.model_dump()))
    await session.commit()
    logger.info("Seeded default LLM server %r from environment settings", SEED_NAME)


async def _clear_default(session: AsyncSession) -> None:
    await session.execute(
        update(LLMServer).where(LLMServer.is_default.is_(True)).values(is_default=False)
    )


async def _commit_or_conflict(session: AsyncSession, name: str) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(f"An LLM server named {name!r} already exists") from exc
