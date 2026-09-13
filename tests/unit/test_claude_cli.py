import asyncio
import json
import os
import stat
import textwrap
from pathlib import Path

import pytest
import yaml

from backend.core.exceptions import LLMError
from backend.services.llm.claude_cli import (
    ClaudeCliClient,
    build_transcript,
    extract_text,
    iter_events,
)
from backend.services.llm.conversation import Role, Turn, Usage
from backend.services.llm.options import ClaudeCliOptions
from tests.unit.helpers import collect

_HI = [Turn(role=Role.USER, content="hi")]


def test_build_transcript_round_trips_via_yaml():
    messages = [
        Turn(role=Role.USER, content="hi"),
        Turn(role=Role.ASSISTANT, content="hello there"),
    ]
    transcript = build_transcript(messages)
    _, _, yaml_body = transcript.partition("\n\n")
    doc = yaml.safe_load(yaml_body)
    assert doc == {
        "turns": [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello there"},
        ]
    }


def test_build_transcript_emits_partial_only_on_partial_turns():
    messages = [
        Turn(role=Role.USER, content="hi"),
        Turn(role=Role.ASSISTANT, content="cut off", partial=True),
    ]
    transcript = build_transcript(messages)
    _, _, yaml_body = transcript.partition("\n\n")
    doc = yaml.safe_load(yaml_body)
    assert doc == {
        "turns": [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "cut off", "partial": True},
        ]
    }


def _delta(text: str) -> dict:
    return {
        "type": "stream_event",
        "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": text}},
    }


async def _lines(*items: str):
    for item in items:
        yield item.encode()


def test_extract_text_returns_text_delta():
    assert extract_text(_delta("hi")) == "hi"


@pytest.mark.parametrize(
    "record",
    [
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "message": {"content": []}},
        {
            "type": "stream_event",
            "event": {"type": "content_block_delta", "delta": {"type": "thinking_delta"}},
        },
        {"type": "stream_event", "event": {"type": "content_block_start"}},
        _delta(""),
    ],
)
def test_extract_text_skips_non_text_records(record):
    assert extract_text(record) is None


async def test_iter_events_yields_deltas_and_ignores_garbage():
    lines = _lines(
        json.dumps({"type": "system", "subtype": "init"}) + "\n",
        "not json at all\n",
        "\n",
        json.dumps(_delta("hello ")) + "\n",
        json.dumps(_delta("world")) + "\n",
        json.dumps({"type": "result", "is_error": False}) + "\n",
    )
    text, usage = await collect(iter_events(lines))
    assert text == "hello world"
    assert usage is None  # result record has no "usage" key: no usage chunk


async def test_iter_events_raises_on_error_result():
    lines = _lines(
        json.dumps({"type": "result", "is_error": True, "errors": ["bad key", "oops"]}) + "\n"
    )
    with pytest.raises(LLMError, match="claude failed: bad key; oops"):
        async for _ in iter_events(lines):
            pass


async def test_iter_events_yields_usage_from_result_record():
    lines = _lines(
        json.dumps(_delta("hi")) + "\n",
        json.dumps(
            {
                "type": "result",
                "is_error": False,
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 10,
                    "cache_read_input_tokens": 5,
                    "cache_creation_input_tokens": 2,
                },
                "total_cost_usd": 0.05,
                "modelUsage": {"claude-opus-5": {"contextWindow": 200000}},
            }
        )
        + "\n",
    )
    text, usage = await collect(iter_events(lines))
    assert text == "hi"
    assert usage == Usage(
        input_tokens=100,
        output_tokens=10,
        cache_read_tokens=5,
        cache_write_tokens=2,
        cost_usd=0.05,
        context_window=200000,
    )


def _write_fake(tmp_path: Path, body: str) -> Path:
    fake = tmp_path / "claude"
    fake.write_text("#!/usr/bin/env python3\n" + textwrap.dedent(body))
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return fake


async def test_subprocess_streams_and_surfaces_stderr(tmp_path):
    fake = _write_fake(
        tmp_path,
        """\
        import json, sys
        d = lambda t: {"type": "stream_event", "event": {"type": "content_block_delta",
                       "delta": {"type": "text_delta", "text": t}}}
        print(json.dumps({"type": "system", "subtype": "init"}))
        print(json.dumps(d("hello "))); print(json.dumps(d("world")))
        print(json.dumps({"type": "result", "is_error": False}))
        if "--model" in sys.argv and sys.argv[sys.argv.index("--model") + 1] == "explode":
            print("kaboom", file=sys.stderr); sys.exit(3)
        """,
    )

    client = ClaudeCliClient(
        executable=str(fake), default_model=None, options=ClaudeCliOptions(cwd=str(tmp_path))
    )
    text, _ = await collect(client.stream_chat(_HI))
    assert text == "hello world"
    with pytest.raises(LLMError, match="status 3: kaboom"):
        async for _ in client.stream_chat(_HI, model="explode"):
            pass


async def test_subprocess_receives_prompt_model_and_extra_args(tmp_path):
    fake = _write_fake(
        tmp_path,
        """\
        import json, sys
        print(json.dumps({"type": "stream_event", "event": {"type": "content_block_delta",
              "delta": {"type": "text_delta", "text": json.dumps(sys.argv[1:])}}}))
        """,
    )
    client = ClaudeCliClient(
        executable=str(fake),
        default_model="sonnet",
        options=ClaudeCliOptions(extra_args=["--tools", ""], cwd=str(tmp_path)),
    )
    messages = [Turn(role=Role.USER, content="say hi")]
    text, _ = await collect(client.stream_chat(messages, system_prompt="be terse"))
    argv = json.loads(text)
    assert argv[0] == "-p"
    assert "say hi" in argv[1]
    assert argv[2:] == [
        "--output-format", "stream-json", "--verbose", "--include-partial-messages",
        "--model", "sonnet", "--append-system-prompt", "be terse", "--tools", "",
    ]  # fmt: skip


async def test_subprocess_uses_options_system_prompt_when_none_given_per_call(tmp_path):
    fake = _write_fake(
        tmp_path,
        """\
        import json, sys
        print(json.dumps({"type": "stream_event", "event": {"type": "content_block_delta",
              "delta": {"type": "text_delta", "text": json.dumps(sys.argv[1:])}}}))
        """,
    )
    client = ClaudeCliClient(
        executable=str(fake),
        default_model=None,
        options=ClaudeCliOptions(system_prompt="server default"),
    )
    text, _ = await collect(client.stream_chat(_HI))
    argv = json.loads(text)
    assert "--append-system-prompt" in argv
    assert argv[argv.index("--append-system-prompt") + 1] == "server default"

    overridden_text, _ = await collect(client.stream_chat(_HI, system_prompt="be terse"))
    overridden = json.loads(overridden_text)
    assert overridden[overridden.index("--append-system-prompt") + 1] == "be terse"


async def test_default_executable_and_cwd_is_the_data_dir(tmp_path):
    # isolated_db (autouse) already points CRAYBEE_DATA_DIR at tmp_path.
    fake = _write_fake(
        tmp_path,
        """\
        import json, os
        print(json.dumps({"type": "stream_event", "event": {"type": "content_block_delta",
              "delta": {"type": "text_delta", "text": os.getcwd()}}}))
        """,
    )
    client = ClaudeCliClient(executable=str(fake), default_model=None, options=ClaudeCliOptions())
    text, _ = await collect(client.stream_chat(_HI))
    assert text == str(tmp_path)


async def test_missing_executable_is_llm_error(tmp_path):
    client = ClaudeCliClient(
        executable=str(tmp_path / "nope"),
        default_model=None,
        options=ClaudeCliOptions(cwd=str(tmp_path)),
    )
    with pytest.raises(LLMError, match="not found"):
        async for _ in client.stream_chat(_HI):
            pass


async def test_cancel_kills_the_child(tmp_path):
    pid_file = tmp_path / "pid"
    fake = _write_fake(
        tmp_path,
        f"""\
        import json, os, sys, time
        open({str(pid_file)!r}, "w").write(str(os.getpid()))
        print(json.dumps({{"type": "stream_event", "event": {{"type": "content_block_delta",
              "delta": {{"type": "text_delta", "text": "first"}}}}}}), flush=True)
        time.sleep(3600)
        """,
    )
    client = ClaudeCliClient(
        executable=str(fake), default_model=None, options=ClaudeCliOptions(cwd=str(tmp_path))
    )
    first_token = asyncio.Event()

    async def consume() -> None:
        async for _ in client.stream_chat(_HI):
            first_token.set()

    task = asyncio.create_task(consume())
    await asyncio.wait_for(first_token.wait(), timeout=10)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    pid = int(pid_file.read_text())
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        await asyncio.sleep(0.05)
    else:
        pytest.fail(f"child {pid} still alive after cancel")
