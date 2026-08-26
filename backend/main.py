from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.v1 import api_router
from backend.api.v1.routes import ws
from backend.config import get_settings
from backend.core.exceptions import register_exception_handlers

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)

    register_exception_handlers(app)

    # Order matters: API and WS routes must be registered before the SPA
    # catch-all, or the catch-all swallows them.
    app.include_router(api_router)
    app.include_router(ws.router)

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the compiled SPA, if this install has one.

    In dev there is no backend/static/ -- Vite serves the frontend on its own
    port and proxies /api and /ws back here, so the absence is expected.
    """
    index = STATIC_DIR / "index.html"
    if not index.exists():
        return

    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    # response_model=None: the union return type is not a Pydantic field, and
    # FastAPI would otherwise try to build a response model from it.
    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    async def spa(full_path: str) -> FileResponse | JSONResponse:
        # A real file (favicon, manifest) wins; everything else is a client-side
        # route and must return index.html so deep links survive a refresh.
        candidate = (STATIC_DIR / full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(STATIC_DIR.resolve()):
            return FileResponse(candidate)
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        return FileResponse(index)


app = create_app()
