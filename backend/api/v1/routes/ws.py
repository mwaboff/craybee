import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.exceptions import NotFoundError
from backend.orchestration.registry import registry

router = APIRouter()


@router.websocket("/ws/runs/{run_id}")
async def run_events(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    try:
        queue = registry.subscribe(run_id)
    except NotFoundError as exc:
        await websocket.close(code=4404, reason=exc.message)
        return

    try:
        while True:
            event = await queue.get()
            await websocket.send_text(event.model_dump_json())
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        registry.unsubscribe(run_id, queue)
