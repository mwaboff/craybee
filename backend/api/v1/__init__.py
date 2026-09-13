from fastapi import APIRouter

from backend.api.v1.routes import conversations, health, llm_servers, runs

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(runs.router)
api_router.include_router(conversations.router)
api_router.include_router(llm_servers.router)
