"""Drives a run to completion in the background.

`_execute` resolves the default LLM server from the database and streams its
reply as token events. The surrounding lifecycle -- status transitions,
cancellation, error capture -- is provider-independent.
"""

import asyncio
import contextlib
import logging

from backend.core.exceptions import ConflictError
from backend.orchestration import commands
from backend.orchestration.events import RunEvent, RunStatus
from backend.orchestration.registry import Run, conversations, registry
from backend.services import llm_servers
from backend.services.llm.conversation import Conversation

logger = logging.getLogger(__name__)


def start(prompt: str, conversation_id: str | None = None) -> Run:
    record = conversations.get(conversation_id) if conversation_id is not None else conversations.create()
    if record.live_run is not None:
        raise ConflictError(f"Conversation {record.id} already has a run in progress")
    run = registry.create(prompt, record.id)
    record.active_run = run
    run.task = asyncio.create_task(_lifecycle(run))
    return run


async def _lifecycle(run: Run) -> None:
    _set_status(run, RunStatus.RUNNING)
    try:
        await _execute(run)
    except asyncio.CancelledError:
        _set_status(run, RunStatus.CANCELLED)
        raise
    except Exception as exc:  # task boundary: any failure must reach the UI
        logger.exception("Run %s failed", run.id)
        run.publish(RunEvent(type="error", run_id=run.id, data={"message": str(exc)}))
        _set_status(run, RunStatus.FAILED)
    else:
        _set_status(run, RunStatus.SUCCEEDED)


async def _execute(run: Run) -> None:
    if await commands.dispatch(run, run.prompt):
        return
    record = conversations.get(run.conversation_id)
    # Resolved here, not in the route, so a missing default surfaces as a run error event.
    _, client = await llm_servers.open_default_client()
    try:
        # The record owns `turns`; this Conversation is throwaway and shares that
        # list, so its appends land directly in the record with no write-back.
        convo = Conversation(client=client, turns=record.turns)
        turns_before = len(convo.turns)
        # aclosing: an early exit (cancel, error) still runs the generator's cleanup.
        async with contextlib.aclosing(convo.send(run.prompt)) as chunks:
            async for text in chunks:
                run.publish(RunEvent(type="token", run_id=run.id, data={"text": text}))
        if len(convo.turns) == turns_before + 2:
            usage = convo.turns[-1].usage
            if usage is not None:
                run.publish(RunEvent(type="usage", run_id=run.id, data=usage.model_dump()))
    finally:
        await client.aclose()


def _set_status(run: Run, status: RunStatus) -> None:
    run.status = status
    run.publish(RunEvent(type="status", run_id=run.id, data={"status": status}))
