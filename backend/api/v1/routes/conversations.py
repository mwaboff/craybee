from fastapi import APIRouter

from backend.orchestration.registry import conversations
from backend.schemas.conversation import ConversationRead
from backend.services.llm.conversation import Role

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str) -> ConversationRead:
    record = conversations.get(conversation_id)
    turns = record.turns
    live_run = record.live_run
    if live_run is not None and turns and turns[-1].role is Role.USER:
        # The in-flight user turn (and its eventual reply) is only visible over
        # the run's websocket until the run settles.
        turns = turns[:-1]
    return ConversationRead(id=record.id, turns=turns, active_run_id=live_run.id if live_run else None)
