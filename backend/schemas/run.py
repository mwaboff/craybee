from pydantic import BaseModel, Field

from backend.orchestration.events import RunEvent, RunStatus


class RunCreate(BaseModel):
    prompt: str = Field(min_length=1)
    conversation_id: str | None = None


class RunSummary(BaseModel):
    id: str
    prompt: str
    status: RunStatus
    conversation_id: str


class RunDetail(RunSummary):
    events: list[RunEvent]
