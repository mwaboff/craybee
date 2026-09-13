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
from backend.services.llm.conversation import Turn

LIVE_STATUSES = {RunStatus.PENDING, RunStatus.RUNNING}


@dataclass
class Run:
    id: str
    prompt: str
    conversation_id: str
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

    def create(self, prompt: str, conversation_id: str) -> Run:
        run = Run(id=uuid.uuid4().hex, prompt=prompt, conversation_id=conversation_id)
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


@dataclass
class ConversationRecord:
    id: str
    turns: list[Turn] = field(default_factory=list)
    active_run: Run | None = None

    @property
    def live_run(self) -> Run | None:
        """The active run, if it is still pending or running; None once it settles."""
        if self.active_run is not None and self.active_run.status in LIVE_STATUSES:
            return self.active_run
        return None


class ConversationRegistry:
    def __init__(self) -> None:
        self._conversations: dict[str, ConversationRecord] = {}

    def create(self) -> ConversationRecord:
        record = ConversationRecord(id=uuid.uuid4().hex)
        self._conversations[record.id] = record
        return record

    def get(self, conversation_id: str) -> ConversationRecord:
        record = self._conversations.get(conversation_id)
        if record is None:
            raise NotFoundError(f"No conversation with id {conversation_id}")
        return record


conversations = ConversationRegistry()
