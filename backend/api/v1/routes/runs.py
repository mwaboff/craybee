from fastapi import APIRouter

from backend.orchestration import runner
from backend.orchestration.registry import Run, registry
from backend.schemas.run import RunCreate, RunDetail, RunSummary

router = APIRouter(prefix="/runs", tags=["runs"])


def _summary(run: Run) -> RunSummary:
    return RunSummary(id=run.id, prompt=run.prompt, status=run.status)


@router.post("", status_code=201)
async def create_run(body: RunCreate) -> RunSummary:
    """Start a run and return immediately; progress arrives over /ws/runs/{id}."""
    return _summary(runner.start(body.prompt))


@router.get("")
async def list_runs() -> list[RunSummary]:
    return [_summary(run) for run in registry.list()]


@router.get("/{run_id}")
async def get_run(run_id: str) -> RunDetail:
    run = registry.get(run_id)
    return RunDetail(id=run.id, prompt=run.prompt, status=run.status, events=run.events)


@router.post("/{run_id}/cancel")
async def cancel_run(run_id: str) -> RunSummary:
    return _summary(await registry.cancel(run_id))
