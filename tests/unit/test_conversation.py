from backend.services.llm.conversation import Conversation, Role, StreamChunk, Turn, Usage


def _as_tuples(turns: list[Turn]) -> list[tuple[Role, str]]:
    return [(t.role, t.content) for t in turns]


class FakeClient:
    def __init__(
        self,
        replies: list[list[str]],
        *,
        fail_after: int | None = None,
        usage: list[Usage | None] | None = None,
    ) -> None:
        self._replies = replies
        self._fail_after = fail_after
        self._usage = usage
        self.calls: list[dict] = []

    async def stream_chat(self, messages, *, system_prompt=None, model=None):
        self.calls.append(
            {
                "messages": list(messages),
                "system_prompt": system_prompt,
                "model": model,
            }
        )
        call_index = len(self.calls) - 1
        chunks = self._replies[call_index]
        for i, chunk in enumerate(chunks):
            if self._fail_after is not None and i == self._fail_after:
                raise RuntimeError("boom")
            yield StreamChunk(text=chunk)
        if self._usage is not None and (usage := self._usage[call_index]) is not None:
            yield StreamChunk(usage=usage)

    async def list_models(self) -> list[str]:
        return []

    async def aclose(self) -> None:
        return None


async def test_send_appends_user_turn_before_call():
    client = FakeClient([["hi"]])
    convo = Conversation(client=client)
    [_ async for _ in convo.send("hello")]
    assert _as_tuples(client.calls[0]["messages"]) == [(Role.USER, "hello")]


async def test_send_forwards_system_prompt_and_model():
    client = FakeClient([["hi"]])
    convo = Conversation(client=client, system_prompt="be brief", model="sonnet")
    [_ async for _ in convo.send("hello")]
    assert client.calls[0]["system_prompt"] == "be brief"
    assert client.calls[0]["model"] == "sonnet"


async def test_send_appends_assistant_turn_after_full_stream():
    client = FakeClient([["hel", "lo"]])
    convo = Conversation(client=client)
    assert [c async for c in convo.send("hi")] == ["hel", "lo"]
    assert _as_tuples(convo.turns) == [(Role.USER, "hi"), (Role.ASSISTANT, "hello")]


async def test_turns_accumulate_across_two_sends():
    client = FakeClient([["hi there"], ["bye"]])
    convo = Conversation(client=client)
    [_ async for _ in convo.send("hello")]
    [_ async for _ in convo.send("goodbye")]
    assert [t.role for t in convo.turns] == [
        Role.USER,
        Role.ASSISTANT,
        Role.USER,
        Role.ASSISTANT,
    ]
    assert client.calls[1]["messages"] == convo.turns[:3]


async def test_partial_text_is_appended_when_stream_raises_midway():
    client = FakeClient([["hel", "lo", "unreachable"]], fail_after=2)
    convo = Conversation(client=client)
    collected: list[str] = []
    try:
        async for chunk in convo.send("hi"):
            collected.append(chunk)
    except RuntimeError:
        pass
    assert collected == ["hel", "lo"]
    assert _as_tuples(convo.turns) == [(Role.USER, "hi"), (Role.ASSISTANT, "hello")]
    assert convo.turns[-1].partial is True


async def test_failure_before_first_chunk_removes_user_turn():
    client = FakeClient([["unreachable"]], fail_after=0)
    convo = Conversation(client=client)
    collected: list[str] = []
    try:
        async for chunk in convo.send("hi"):
            collected.append(chunk)
    except RuntimeError:
        pass
    assert collected == []
    assert convo.turns == []


async def test_usage_totals_across_two_sends():
    client = FakeClient(
        [["hi there"], ["bye"]],
        usage=[
            Usage(input_tokens=10, output_tokens=5),
            Usage(input_tokens=20, output_tokens=8, cache_read_tokens=2),
        ],
    )
    convo = Conversation(client=client)
    [_ async for _ in convo.send("hello")]
    [_ async for _ in convo.send("goodbye")]
    assert convo.usage == Usage(input_tokens=30, output_tokens=13, cache_read_tokens=2)


async def test_context_tokens_reflects_only_last_turn():
    client = FakeClient(
        [["hi there"], ["bye"]],
        usage=[
            Usage(input_tokens=10, output_tokens=5),
            Usage(input_tokens=20, output_tokens=8, cache_read_tokens=2, cache_write_tokens=1),
        ],
    )
    convo = Conversation(client=client)
    [_ async for _ in convo.send("hello")]
    assert convo.context_tokens == 15
    [_ async for _ in convo.send("goodbye")]
    assert convo.context_tokens == 31


def test_context_tokens_is_zero_with_no_usage():
    convo = Conversation(client=FakeClient([["hi"]]))
    assert convo.context_tokens == 0
    assert convo.usage == Usage()


async def test_turns_list_is_shared_with_caller():
    """The registry owns history across runs, so Conversation must mutate the
    caller's list in place rather than copying it."""
    shared_turns: list[Turn] = []
    client = FakeClient([["hi"]])
    convo = Conversation(client=client, turns=shared_turns)
    assert convo.turns is shared_turns
    [_ async for _ in convo.send("hello")]
    assert _as_tuples(shared_turns) == [(Role.USER, "hello"), (Role.ASSISTANT, "hi")]
