from pydantic import BaseModel

from backend.services.llm.conversation import Turn


class ConversationRead(BaseModel):
    id: str
    turns: list[Turn]
    active_run_id: str | None
