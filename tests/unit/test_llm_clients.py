from types import SimpleNamespace
from typing import Self

import anthropic
import openai
import pytest

from backend.core.exceptions import LLMError
from backend.models.llm_server import LLMServer, ProviderKind
from backend.services.llm import build_client
from backend.services.llm.anthropic_api import AnthropicClient
from backend.services.llm.claude_cli import ClaudeCliClient
from backend.services.llm.conversation import Role, Turn, Usage
from backend.services.llm.openai_compat import OpenAICompatClient
from backend.services.llm.options import AnthropicOptions, OpenAICompatOptions
from tests.unit.helpers import collect


def _server(**kwargs) -> LLMServer:
    defaults = {
        "name": "s",
        "base_url": None,
        "api_key": None,
        "executable_path": None,
        "default_model": None,
        "options": {},
    }
    return LLMServer(**{**defaults, **kwargs})


async def _model_used(client: OpenAICompatClient, monkeypatch) -> str:
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)

        async def gen():
            return
            yield

        return gen()

    monkeypatch.setattr(client._client.chat.completions, "create", fake_create)
    [_ async for _ in client.stream_chat([Turn(role=Role.USER, content="hi")])]
    return captured["model"]


async def test_build_client_openai_compatible_passes_url_and_key(monkeypatch):
    server = _server(
        provider=ProviderKind.OPENAI_COMPATIBLE,
        base_url="http://127.0.0.1:1234/v1",
        api_key="k",
        default_model="m",
    )
    client = build_client(server)
    assert isinstance(client, OpenAICompatClient)
    assert str(client._client.base_url) == "http://127.0.0.1:1234/v1/"
    assert client._client.api_key == "k"
    assert await _model_used(client, monkeypatch) == "m"


async def test_build_client_openai_compatible_without_key_uses_placeholder(monkeypatch):
    client = build_client(_server(provider=ProviderKind.OPENAI_COMPATIBLE, base_url="http://x/v1"))
    assert isinstance(client, OpenAICompatClient)
    assert client._client.api_key == "not-needed"
    assert await _model_used(client, monkeypatch) == "local-model"


def test_build_client_anthropic_passes_key_and_optional_base_url():
    client = build_client(
        _server(provider=ProviderKind.ANTHROPIC, api_key="sk-x", base_url="http://proxy/")
    )
    assert isinstance(client, AnthropicClient)
    assert client._client.api_key == "sk-x"
    assert str(client._client.base_url).startswith("http://proxy")

    default = build_client(_server(provider=ProviderKind.ANTHROPIC, api_key="sk-y"))
    assert isinstance(default, AnthropicClient)
    assert "anthropic.com" in str(default._client.base_url)


def test_build_client_claude_cli_defaults_executable():
    # isolated_db (autouse) already sets CRAYBEE_DATA_DIR and clears the settings cache.
    client = build_client(_server(provider=ProviderKind.CLAUDE_CLI))
    assert isinstance(client, ClaudeCliClient)
    assert client._exe == "claude"

    custom = build_client(
        _server(
            provider=ProviderKind.CLAUDE_CLI,
            executable_path="/opt/claude",
            options={"extra_args": ["--tools", ""], "cwd": "/somewhere"},
        )
    )
    assert isinstance(custom, ClaudeCliClient)
    assert custom._exe == "/opt/claude"


def _chunk(text: str | None, *, choices: bool = True, usage=None):
    if not choices:
        return SimpleNamespace(choices=[], usage=usage)
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))], usage=usage
    )


def _usage_chunk(prompt: int, completion: int, cached: int | None = None):
    details = SimpleNamespace(cached_tokens=cached) if cached is not None else None
    return _chunk(
        None,
        choices=False,
        usage=SimpleNamespace(
            prompt_tokens=prompt, completion_tokens=completion, prompt_tokens_details=details
        ),
    )


async def test_openai_compat_stream_chat_yields_deltas(monkeypatch):
    client = OpenAICompatClient(
        base_url="http://127.0.0.1:1234/v1",
        api_key="k",
        default_model="local",
        options=OpenAICompatOptions(request={"temperature": 0.2}),
    )
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)

        async def gen():
            for c in (_chunk("hel"), _chunk(None), _chunk("", choices=False), _chunk("lo")):
                yield c

        return gen()

    monkeypatch.setattr(client._client.chat.completions, "create", fake_create)
    messages = [Turn(role=Role.USER, content="hi")]
    text, usage = await collect(client.stream_chat(messages))
    assert text == "hello"
    assert usage is None
    assert captured["model"] == "local"
    assert captured["stream"] is True
    assert captured["temperature"] == 0.2
    assert captured["messages"] == [{"role": "user", "content": "hi"}]
    assert captured["stream_options"] == {"include_usage": True}

    await collect(client.stream_chat(messages, model="other"))
    assert captured["model"] == "other"

    await collect(client.stream_chat(messages, system_prompt="be brief"))
    assert captured["messages"] == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hi"},
    ]
    await client.aclose()


async def test_openai_compat_request_can_override_stream_options(monkeypatch):
    client = OpenAICompatClient(
        base_url="http://127.0.0.1:1234/v1",
        api_key="k",
        default_model="local",
        options=OpenAICompatOptions(request={"stream_options": None}),
    )
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)

        async def gen():
            return
            yield

        return gen()

    monkeypatch.setattr(client._client.chat.completions, "create", fake_create)
    await collect(client.stream_chat([Turn(role=Role.USER, content="hi")]))
    assert captured["stream_options"] is None


async def test_openai_compat_usage_mapping(monkeypatch):
    client = OpenAICompatClient(
        base_url="http://x/v1", api_key="k", default_model="local", options=OpenAICompatOptions()
    )

    async def make_stream(*chunks):
        async def fake_create(**kwargs):
            async def gen():
                for c in chunks:
                    yield c

            return gen()

        monkeypatch.setattr(client._client.chat.completions, "create", fake_create)
        return await collect(client.stream_chat([Turn(role=Role.USER, content="hi")]))

    # With prompt_tokens_details.cached_tokens.
    _, usage = await make_stream(_chunk("hi"), _usage_chunk(100, 10, cached=20))
    assert usage == Usage(input_tokens=80, output_tokens=10, cache_read_tokens=20)

    # Without prompt_tokens_details.
    _, usage = await make_stream(_chunk("hi"), _usage_chunk(100, 10))
    assert usage == Usage(input_tokens=100, output_tokens=10)

    # No usage reported at all: no usage chunk.
    _, usage = await make_stream(_chunk("hi"))
    assert usage is None


async def test_openai_compat_system_prompt_from_options_can_be_overridden(monkeypatch):
    client = OpenAICompatClient(
        base_url="http://127.0.0.1:1234/v1",
        api_key="k",
        default_model="local",
        options=OpenAICompatOptions(system_prompt="server default"),
    )
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)

        async def gen():
            return
            yield

        return gen()

    monkeypatch.setattr(client._client.chat.completions, "create", fake_create)
    messages = [Turn(role=Role.USER, content="hi")]

    [_ async for _ in client.stream_chat(messages)]
    assert captured["messages"][0] == {"role": "system", "content": "server default"}

    [_ async for _ in client.stream_chat(messages, system_prompt="be brief")]
    assert captured["messages"][0] == {"role": "system", "content": "be brief"}


async def test_openai_compat_list_models(monkeypatch):
    client = OpenAICompatClient(
        base_url="http://x/v1", api_key="k", default_model=None, options=OpenAICompatOptions()
    )

    async def fake_list():
        return SimpleNamespace(data=[SimpleNamespace(id="a"), SimpleNamespace(id="b")])

    monkeypatch.setattr(client._client.models, "list", fake_list)
    assert await client.list_models() == ["a", "b"]
    await client.aclose()


class _FakeAnthropicStream:
    def __init__(self, chunks: list[str], usage=None) -> None:
        self._chunks = chunks
        self._usage = usage

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info) -> None:
        return None

    @property
    async def text_stream(self):
        for chunk in self._chunks:
            yield chunk

    async def get_final_message(self):
        return SimpleNamespace(usage=self._usage)


async def test_anthropic_stream_chat_yields_deltas(monkeypatch):
    client = AnthropicClient(
        api_key="sk",
        base_url=None,
        default_model="claude-opus-5",
        options=AnthropicOptions(max_tokens=500),
    )
    captured: dict = {}

    def fake_stream(**kwargs):
        captured.clear()
        captured.update(kwargs)
        return _FakeAnthropicStream(["hel", "lo"])

    monkeypatch.setattr(client._client.messages, "stream", fake_stream)

    messages = [Turn(role=Role.USER, content="hi"), Turn(role=Role.ASSISTANT, content="yo")]
    text, usage = await collect(client.stream_chat(messages, system_prompt="be brief"))
    assert text == "hello"
    assert usage is None
    assert captured["system"] == "be brief"
    assert captured["max_tokens"] == 500
    assert captured["model"] == "claude-opus-5"
    assert captured["messages"] == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "yo"},
    ]
    assert "system" not in captured["messages"][0] and "system" not in captured["messages"][1]

    await collect(client.stream_chat(messages, model="other"))
    assert captured["model"] == "other"
    assert "system" not in captured


async def test_anthropic_stream_chat_system_prompt_overrides_server_default(monkeypatch):
    client = AnthropicClient(
        api_key="sk",
        base_url=None,
        default_model=None,
        options=AnthropicOptions(system_prompt="server default"),
    )
    captured: dict = {}

    def fake_stream(**kwargs):
        captured.update(kwargs)
        return _FakeAnthropicStream(["hi"])

    monkeypatch.setattr(client._client.messages, "stream", fake_stream)
    messages = [Turn(role=Role.USER, content="hi")]

    await collect(client.stream_chat(messages, system_prompt="be brief"))
    assert captured["system"] == "be brief"

    await collect(client.stream_chat(messages))
    assert captured["system"] == "server default"


async def test_anthropic_usage_from_get_final_message(monkeypatch):
    client = AnthropicClient(
        api_key="sk", base_url=None, default_model=None, options=AnthropicOptions()
    )
    usage = SimpleNamespace(
        input_tokens=100,
        output_tokens=10,
        cache_read_input_tokens=5,
        cache_creation_input_tokens=None,
    )

    def fake_stream(**kwargs):
        return _FakeAnthropicStream(["hi"], usage=usage)

    monkeypatch.setattr(client._client.messages, "stream", fake_stream)
    _, mapped = await collect(client.stream_chat([Turn(role=Role.USER, content="hi")]))
    assert mapped == Usage(input_tokens=100, output_tokens=10, cache_read_tokens=5)


async def test_anthropic_list_models(monkeypatch):
    client = AnthropicClient(
        api_key="sk", base_url=None, default_model=None, options=AnthropicOptions()
    )

    def fake_list(**kwargs):
        async def gen():
            for name in ("claude-opus-5", "claude-sonnet-5"):
                yield SimpleNamespace(id=name)

        return gen()

    monkeypatch.setattr(client._client.models, "list", fake_list)
    assert await client.list_models() == ["claude-opus-5", "claude-sonnet-5"]
    await client.aclose()


def test_anthropic_options():
    options = AnthropicOptions.model_validate({"max_tokens": "2048", "system_prompt": "be brief"})
    assert options.max_tokens == 2048
    assert options.system_prompt == "be brief"

    client = AnthropicClient(api_key="sk", base_url=None, default_model=None, options=options)
    assert client._model == "claude-opus-5"


async def test_openai_compat_errors_surface_as_llm_error(monkeypatch):
    client = OpenAICompatClient(
        base_url="http://x/v1", api_key="k", default_model="local", options=OpenAICompatOptions()
    )

    async def fake_create(**kwargs):
        raise openai.APIConnectionError(request=SimpleNamespace())

    monkeypatch.setattr(client._client.chat.completions, "create", fake_create)
    with pytest.raises(LLMError, match="openai:"):
        await collect(client.stream_chat([Turn(role=Role.USER, content="hi")]))

    async def fake_list():
        raise openai.APIConnectionError(request=SimpleNamespace())

    monkeypatch.setattr(client._client.models, "list", fake_list)
    with pytest.raises(LLMError, match="openai:"):
        await client.list_models()


async def test_anthropic_errors_surface_as_llm_error(monkeypatch):
    client = AnthropicClient(
        api_key="sk", base_url=None, default_model=None, options=AnthropicOptions()
    )

    def fake_stream(**kwargs):
        raise anthropic.APIConnectionError(request=SimpleNamespace())

    monkeypatch.setattr(client._client.messages, "stream", fake_stream)
    with pytest.raises(LLMError, match="anthropic:"):
        await collect(client.stream_chat([Turn(role=Role.USER, content="hi")]))

    def fake_list(**kwargs):
        raise anthropic.APIConnectionError(request=SimpleNamespace())

    monkeypatch.setattr(client._client.models, "list", fake_list)
    with pytest.raises(LLMError, match="anthropic:"):
        await client.list_models()
