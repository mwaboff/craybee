from tests.conftest import FakeLLMClient, wait_for_run, wait_until

_LIVE_STATUSES = {"pending", "running"}


async def _wait_for_status(client, run_id: str, statuses: set[str], timeout: float = 5.0) -> dict:
    """Poll GET /api/v1/runs/{id} until its status is one of `statuses`."""
    return await wait_until(
        client,
        run_id,
        lambda detail: detail["status"] in statuses,
        timeout=timeout,
        interval=0.01,
        description=f"one of {statuses}",
    )


async def _wait_for_token(client, run_id: str, timeout: float = 5.0) -> dict:
    """Poll GET /api/v1/runs/{id} until at least one token event has streamed."""
    return await wait_until(
        client,
        run_id,
        lambda detail: any(event["type"] == "token" for event in detail["events"]),
        timeout=timeout,
        interval=0.01,
        description="a streamed token",
    )


async def test_run_without_conversation_id_creates_conversation(client):
    created = (await client.post("/api/v1/runs", json={"prompt": "hello there"})).json()
    conversation_id = created["conversation_id"]
    assert conversation_id

    await wait_for_run(client, created["id"])

    convo = (await client.get(f"/api/v1/conversations/{conversation_id}")).json()
    assert [t["role"] for t in convo["turns"]] == ["user", "assistant"]
    assert convo["active_run_id"] is None


async def test_second_run_sees_prior_turns(client):
    first = (await client.post("/api/v1/runs", json={"prompt": "hello there"})).json()
    conversation_id = first["conversation_id"]
    await wait_for_run(client, first["id"])

    second = (
        await client.post(
            "/api/v1/runs", json={"prompt": "and then?", "conversation_id": conversation_id}
        )
    ).json()
    assert second["conversation_id"] == conversation_id
    await wait_for_run(client, second["id"])

    convo = (await client.get(f"/api/v1/conversations/{conversation_id}")).json()
    assert [t["role"] for t in convo["turns"]] == ["user", "assistant", "user", "assistant"]
    # The second stream_chat call should have seen the full prior history plus the new prompt.
    assert len(FakeLLMClient.received[1]) == 3


async def test_unknown_conversation_is_404(client):
    response = await client.get("/api/v1/conversations/nope")
    assert response.status_code == 404

    response = await client.post("/api/v1/runs", json={"prompt": "hi", "conversation_id": "nope"})
    assert response.status_code == 404


async def test_second_live_run_in_same_conversation_conflicts(client):
    prompt = " ".join(["x"] * 30)
    first = (await client.post("/api/v1/runs", json={"prompt": prompt})).json()
    conversation_id = first["conversation_id"]
    await _wait_for_token(client, first["id"])

    response = await client.post(
        "/api/v1/runs", json={"prompt": "another", "conversation_id": conversation_id}
    )
    assert response.status_code == 409

    await client.post(f"/api/v1/runs/{first['id']}/cancel")
    await wait_for_run(client, first["id"])


async def test_cancel_mid_stream_leaves_partial_assistant_turn(client):
    prompt = " ".join(["x"] * 30)
    created = (await client.post("/api/v1/runs", json={"prompt": prompt})).json()
    conversation_id = created["conversation_id"]
    await _wait_for_token(client, created["id"])

    await client.post(f"/api/v1/runs/{created['id']}/cancel")
    detail = await wait_for_run(client, created["id"])
    assert detail["status"] == "cancelled"

    convo = (await client.get(f"/api/v1/conversations/{conversation_id}")).json()
    assert convo["turns"][-1]["role"] == "assistant"
    assert convo["turns"][-1]["partial"] is True
    assert convo["turns"][-1]["content"] != ""


async def test_get_conversation_while_live_excludes_inflight_user_turn(client):
    prompt = " ".join(["x"] * 30)
    created = (await client.post("/api/v1/runs", json={"prompt": prompt})).json()
    conversation_id = created["conversation_id"]
    await _wait_for_status(client, created["id"], {"running"})

    convo = (await client.get(f"/api/v1/conversations/{conversation_id}")).json()
    assert convo["turns"] == []
    assert convo["active_run_id"] == created["id"]

    await client.post(f"/api/v1/runs/{created['id']}/cancel")
    await wait_for_run(client, created["id"])
