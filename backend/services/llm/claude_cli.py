"""`claude -p` as a provider: one subprocess per prompt, NDJSON on stdout."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import yaml

from backend.config import get_settings
from backend.core.exceptions import LLMError
from backend.services.llm.conversation import StreamChunk, Turn, Usage
from backend.services.llm.options import ClaudeCliOptions

logger = logging.getLogger(__name__)

# The CLI has no list-models command; these are the --model aliases it accepts.
MODEL_ALIASES = ["fable", "opus", "sonnet", "haiku"]
# stream-json lines can exceed StreamReader's 64 KiB default.
_STREAM_LIMIT = 16 * 1024 * 1024

_PREAMBLE = (
    "The following is the full transcript of an ongoing back-and-forth conversation "
    "between a user and an assistant, given as YAML. Continue the conversation "
    "naturally, responding only to the final user turn.\n\n"
)


def build_transcript(messages: list[Turn]) -> str:
    turns = []
    for t in messages:
        turn: dict[str, Any] = {"role": t.role.value, "content": t.content}
        if t.partial:
            turn["partial"] = True
        turns.append(turn)
    doc = {"turns": turns}
    return _PREAMBLE + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def extract_text(record: dict[str, Any]) -> str | None:
    """Text delta from one NDJSON record, or None if it is not a text delta."""
    if record.get("type") != "stream_event":
        return None
    event = record.get("event") or {}
    if event.get("type") != "content_block_delta":
        return None
    delta = event.get("delta") or {}
    if delta.get("type") != "text_delta":
        return None
    return delta.get("text") or None


def _map_usage(record: dict[str, Any]) -> Usage:
    usage = record["usage"]
    context_window = None
    for model_usage in (record.get("modelUsage") or {}).values():
        if "contextWindow" in model_usage:
            context_window = model_usage["contextWindow"]
        break
    return Usage(
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        cache_read_tokens=usage.get("cache_read_input_tokens") or 0,
        cache_write_tokens=usage.get("cache_creation_input_tokens") or 0,
        cost_usd=record.get("total_cost_usd"),
        context_window=context_window,
    )


async def iter_events(lines: AsyncIterator[bytes]) -> AsyncIterator[StreamChunk]:
    """Yield text/usage chunks from NDJSON lines; raise LLMError on an error result record."""
    async for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("claude: non-JSON line ignored: %r", line[:200])
            continue
        if record.get("type") == "result":
            if record.get("is_error"):
                errors = record.get("errors") or [record.get("result") or record.get("subtype")]
                raise LLMError(f"claude failed: {'; '.join(map(str, errors))}")
            if "usage" in record:
                yield StreamChunk(usage=_map_usage(record))
            continue
        if (text := extract_text(record)) is not None:
            yield StreamChunk(text=text)


async def _readlines(reader: asyncio.StreamReader) -> AsyncIterator[bytes]:
    while line := await reader.readline():
        yield line


class ClaudeCliClient:
    def __init__(
        self,
        *,
        executable: str,
        default_model: str | None,
        options: ClaudeCliOptions,
    ) -> None:
        self._exe = executable
        self._model = default_model
        self._options = options
        self._extra_args: list[str] = list(options.extra_args)
        # Run away from the repo so claude -p does not pick up craybee's own CLAUDE.md / .claude.
        self._cwd: str = options.cwd or str(get_settings().data_dir)

    async def list_models(self) -> list[str]:
        return list(MODEL_ALIASES)

    async def stream_chat(
        self,
        messages: list[Turn],
        *,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        args = [
            self._exe,
            "-p",
            build_transcript(messages),
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]
        if chosen := (model or self._model):
            args += ["--model", chosen]
        if system := (system_prompt or self._options.system_prompt):
            args += ["--append-system-prompt", system]
        args += self._extra_args

        # The default cwd is the data dir, which may not exist yet on a fresh install;
        # a missing cwd would otherwise surface as a misleading "executable not found".
        Path(self._cwd).mkdir(parents=True, exist_ok=True)
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._cwd,
                limit=_STREAM_LIMIT,
            )
        except FileNotFoundError as exc:
            raise LLMError(f"claude executable not found: {self._exe}") from exc

        assert proc.stdout is not None and proc.stderr is not None
        stderr_task = asyncio.create_task(proc.stderr.read())  # drain so the child never blocks
        try:
            async for chunk in iter_events(_readlines(proc.stdout)):
                yield chunk
            code = await proc.wait()
            stderr = (await stderr_task).decode(errors="replace").strip()
            if code != 0:
                raise LLMError(f"claude exited with status {code}: {stderr or 'no stderr'}")
        finally:
            if proc.returncode is None:  # cancelled or errored mid-stream: do not orphan it
                proc.kill()
                await proc.wait()
            stderr_task.cancel()

    async def aclose(self) -> None:
        return None
