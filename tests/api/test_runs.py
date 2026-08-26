import asyncio


async def test_create_and_fetch_run(client):
    created = await client.post("/api/v1/runs", json={"prompt": "hello there"})
    assert created.status_code == 201
    run_id = created.json()["id"]

    await asyncio.sleep(0.5)  # let the placeholder runner finish

    detail = await client.get(f"/api/v1/runs/{run_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "succeeded"
    assert any(event["type"] == "token" for event in body["events"])


async def test_missing_run_is_404(client):
    response = await client.get("/api/v1/runs/nope")
    assert response.status_code == 404
