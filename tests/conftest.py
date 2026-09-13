import asyncio
from collections.abc import AsyncIterator
from typing import ClassVar

import pytest
from httpx import ASGITransport, AsyncClient

from backend.config import get_settings
from backend.database import db
from backend.main import create_app
from backend.services import llm_servers
from backend.services.llm.conversation import StreamChunk, Turn, Usage

_TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Every test gets its own SQLite file; the lifespan migrates and seeds it."""
    monkeypatch.setenv("CRAYBEE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    db.configure(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    yield
    get_settings.cache_clear()


class FakeLLMClient:
    """Echoes the last user turn one word at a time; slow enough for the cancel test to land."""

    received: ClassVar[list[list[Turn]]] = []

    async def stream_chat(
        self,
        messages: list[Turn],
        *,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        FakeLLMClient.received.append(list(messages))
        prompt = messages[-1].content
        for word in ("Echoing: " + prompt).split(" "):
            await asyncio.sleep(0.02)
            yield StreamChunk(text=word + " ")
        yield StreamChunk(usage=Usage(input_tokens=3, output_tokens=2))

    async def list_models(self) -> list[str]:
        return ["fake-model-a", "fake-model-b"]

    async def aclose(self) -> None:
        return None


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    FakeLLMClient.received = []
    monkeypatch.setattr(llm_servers, "build_client", lambda server: FakeLLMClient())


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    # httpx's ASGITransport does not run lifespan; drive it so migrations and seed happen.
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac,
    ):
        yield ac


async def wait_until(
    client: AsyncClient,
    run_id: str,
    predicate,
    timeout: float = 5.0,
    interval: float = 0.02,
    description: str = "condition",
) -> dict:
    """Poll GET /api/v1/runs/{id} until `predicate(detail)` is true.

    Raises AssertionError with the last-seen run detail if `timeout` elapses first.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        detail = (await client.get(f"/api/v1/runs/{run_id}")).json()
        if predicate(detail):
            return detail
        if asyncio.get_event_loop().time() >= deadline:
            raise AssertionError(f"run {run_id} never met {description}: {detail}")
        await asyncio.sleep(interval)


async def wait_for_run(client: AsyncClient, run_id: str, timeout: float = 5.0) -> dict:
    """Poll GET /api/v1/runs/{id} until the run reaches a terminal status."""
    return await wait_until(
        client,
        run_id,
        lambda detail: detail["status"] in _TERMINAL_STATUSES,
        timeout=timeout,
        description="a terminal status",
    )
