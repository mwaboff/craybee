from pydantic import BaseModel, Field

from backend.orchestration.events import RunEvent, RunStatus


class RunCreate(BaseModel):
    prompt: str = Field(min_length=1)


class RunSummary(BaseModel):
    id: str
    prompt: str
    status: RunStatus


class RunDetail(RunSummary):
    events: list[RunEvent]
