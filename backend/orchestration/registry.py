"""In-process registry of active runs.

Deliberately not Celery/Redis: this is a local single-user tool, so an
asyncio.Task plus a dict is the right amount of machinery. Each run keeps a
replay buffer so a client that connects late (or reconnects) sees the whole
history rather than only what arrives after it subscribes.
"""

import asyncio
import uuid
from dataclasses import dataclass, field

from backend.core.exceptions import NotFoundError
from backend.orchestration.events import RunEvent, RunStatus


@dataclass
class Run:
    id: str
    prompt: str
    status: RunStatus = RunStatus.PENDING
    events: list[RunEvent] = field(default_factory=list)
    subscribers: set[asyncio.Queue[RunEvent]] = field(default_factory=set)
    task: asyncio.Task | None = None

    def publish(self, event: RunEvent) -> None:
        self.events.append(event)
        for queue in self.subscribers:
            queue.put_nowait(event)


class RunRegistry:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}

    def create(self, prompt: str) -> Run:
        run = Run(id=uuid.uuid4().hex, prompt=prompt)
        self._runs[run.id] = run
        return run

    def get(self, run_id: str) -> Run:
        run = self._runs.get(run_id)
        if run is None:
            raise NotFoundError(f"No run with id {run_id}")
        return run

    def list(self) -> list[Run]:
        return list(self._runs.values())

    async def cancel(self, run_id: str) -> Run:
        run = self.get(run_id)
        if run.task is not None and not run.task.done():
            run.task.cancel()
        return run

    def subscribe(self, run_id: str) -> asyncio.Queue[RunEvent]:
        """Subscribe to a run, pre-loaded with everything already emitted."""
        run = self.get(run_id)
        queue: asyncio.Queue[RunEvent] = asyncio.Queue()
        for event in run.events:
            queue.put_nowait(event)
        run.subscribers.add(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[RunEvent]) -> None:
        run = self._runs.get(run_id)
        if run is not None:
            run.subscribers.discard(queue)


registry = RunRegistry()
