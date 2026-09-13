from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class CraybeeError(Exception):
    """Base class for errors that should surface to the client as 4xx."""

    status_code = 400

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFoundError(CraybeeError):
    status_code = 404


class ConflictError(CraybeeError):
    status_code = 409


class LLMError(CraybeeError):
    """Provider failure (bad URL, auth, subprocess exit). 502 when raised from a route."""

    status_code = 502


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CraybeeError)
    async def _handle(request: Request, exc: CraybeeError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
