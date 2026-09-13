import logging
from collections.abc import Awaitable, Callable

from backend.orchestration.events import RunEvent
from backend.orchestration.registry import Run
from backend.services import llm_servers

logger = logging.getLogger(__name__)

CommandHandler = Callable[[Run, list[str]], Awaitable[None]]

_COMMANDS: dict[str, CommandHandler] = {}


def command(name: str) -> Callable[[CommandHandler], CommandHandler]:
    def register(handler: CommandHandler) -> CommandHandler:
        _COMMANDS[name] = handler
        return handler

    return register


async def dispatch(run: Run, prompt: str) -> bool:
    """Returns True if the prompt was a recognized command and was handled."""
    if not prompt.startswith("/"):
        return False
    logger.debug("Received a slash command: %s", prompt)
    parts = prompt[1:].split()
    if not parts:
        return False
    name, *args = parts
    handler = _COMMANDS.get(name)
    if handler is None:
        return False
    await handler(run, args)
    return True


@command("models")
async def models_command(run: Run, args: list[str]) -> None:
    server, client = await llm_servers.open_default_client()
    try:
        models = await client.list_models()
    finally:
        await client.aclose()
    logger.debug("Received models from %s: %s", server.name, models)
    run.publish(RunEvent(type="log", run_id=run.id, data={"server": server.name, "models": models}))
