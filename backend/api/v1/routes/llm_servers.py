from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.llm_server import LLMServerCreate, LLMServerRead, LLMServerUpdate, ModelList
from backend.services import llm_servers

router = APIRouter(prefix="/llm-servers", tags=["llm-servers"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.get("")
async def list_llm_servers(session: DbDep) -> list[LLMServerRead]:
    return [LLMServerRead.model_validate(s) for s in await llm_servers.list_servers(session)]


@router.post("", status_code=201)
async def create_llm_server(body: LLMServerCreate, session: DbDep) -> LLMServerRead:
    return LLMServerRead.model_validate(await llm_servers.create(session, body))


@router.get("/{server_id}")
async def get_llm_server(server_id: str, session: DbDep) -> LLMServerRead:
    return LLMServerRead.model_validate(await llm_servers.get(session, server_id))


@router.patch("/{server_id}")
async def update_llm_server(server_id: str, body: LLMServerUpdate, session: DbDep) -> LLMServerRead:
    return LLMServerRead.model_validate(await llm_servers.patch(session, server_id, body))


@router.delete("/{server_id}", status_code=204)
async def delete_llm_server(server_id: str, session: DbDep) -> None:
    await llm_servers.delete(session, server_id)


@router.post("/{server_id}/default")
async def set_default_llm_server(server_id: str, session: DbDep) -> LLMServerRead:
    return LLMServerRead.model_validate(await llm_servers.set_default(session, server_id))


@router.get("/{server_id}/models")
async def list_llm_server_models(server_id: str, session: DbDep) -> ModelList:
    server = await llm_servers.get(session, server_id)
    return ModelList(models=await llm_servers.list_models(server))
