from fastapi import APIRouter

from backend.api.v1.routes import health, runs

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(runs.router)
