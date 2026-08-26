"""Drives a run to completion in the background.

The body of `_execute` is a placeholder that streams a few tokens; replace it
with real harness calls. The surrounding lifecycle -- status transitions,
cancellation, error capture -- is the part worth keeping.
"""

import asyncio

from backend.orchestration.events import RunEvent, RunStatus
from backend.orchestration.registry import Run, registry


def start(prompt: str) -> Run:
    run = registry.create(prompt)
    run.task = asyncio.create_task(_lifecycle(run))
    return run


async def _lifecycle(run: Run) -> None:
    _set_status(run, RunStatus.RUNNING)
    try:
        await _execute(run)
    except asyncio.CancelledError:
        _set_status(run, RunStatus.CANCELLED)
        raise
    except Exception as exc:  # noqa: BLE001 - task boundary: any failure must reach the UI
        run.publish(RunEvent(type="error", run_id=run.id, data={"message": str(exc)}))
        _set_status(run, RunStatus.FAILED)
    else:
        _set_status(run, RunStatus.SUCCEEDED)


async def _execute(run: Run) -> None:
    for word in f"Echoing: {run.prompt}".split():
        await asyncio.sleep(0.08)
        run.publish(RunEvent(type="token", run_id=run.id, data={"text": word + " "}))


def _set_status(run: Run, status: RunStatus) -> None:
    run.status = status
    run.publish(RunEvent(type="status", run_id=run.id, data={"status": status}))
