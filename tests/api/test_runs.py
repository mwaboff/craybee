from tests.conftest import wait_for_run


async def test_create_and_fetch_run(client):
    created = await client.post("/api/v1/runs", json={"prompt": "hello there"})
    assert created.status_code == 201
    created_body = created.json()
    run_id = created_body["id"]
    assert created_body["conversation_id"]

    body = await wait_for_run(client, run_id)
    assert body["status"] == "succeeded"
    assert body["conversation_id"] == created_body["conversation_id"]
    assert any(event["type"] == "token" for event in body["events"])
    assert any(event["type"] == "usage" for event in body["events"])


async def test_missing_run_is_404(client):
    response = await client.get("/api/v1/runs/nope")
    assert response.status_code == 404
