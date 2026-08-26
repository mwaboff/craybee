import json
import time

from fastapi.testclient import TestClient

from backend.main import create_app

TERMINAL = {"succeeded", "failed", "cancelled"}


def _drain(ws) -> list[dict]:
    """Read until a terminal status arrives."""
    events = []
    while True:
        event = json.loads(ws.receive_text())
        events.append(event)
        if event["type"] == "status" and event["data"]["status"] in TERMINAL:
            return events


def test_stream_delivers_tokens_and_terminal_status():
    with TestClient(create_app()) as client:
        run_id = client.post("/api/v1/runs", json={"prompt": "hello stream"}).json()["id"]
        with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
            events = _drain(ws)

    text = "".join(e["data"].get("text", "") for e in events if e["type"] == "token")
    assert text.strip() == "Echoing: hello stream"
    assert events[-1]["data"]["status"] == "succeeded"


def test_reconnecting_client_gets_full_replay():
    """The client rebuilds from scratch on reconnect, so the replay must be complete
    and must end in a terminal status -- otherwise it would retry forever."""
    with TestClient(create_app()) as client:
        run_id = client.post("/api/v1/runs", json={"prompt": "replay me"}).json()["id"]
        with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
            first = _drain(ws)

        # Reconnect after the run is over, as a dropped socket would.
        with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
            replay = _drain(ws)

    assert replay == first
    assert any(e["type"] == "status" and e["data"]["status"] in TERMINAL for e in replay)


def test_unknown_run_is_rejected_not_retried():
    """Code 4404 tells the client to stop reconnecting."""
    # The close code is what the client keys off, so assert it directly.
    with (
        TestClient(create_app()) as client,
        client.websocket_connect("/ws/runs/does-not-exist") as ws,
    ):
        message = ws.receive()
    assert message["type"] == "websocket.close"
    assert message["code"] == 4404


def test_cancel_stops_a_run():
    with TestClient(create_app()) as client:
        run_id = client.post("/api/v1/runs", json={"prompt": " ".join(["x"] * 50)}).json()["id"]
        time.sleep(0.1)
        client.post(f"/api/v1/runs/{run_id}/cancel")
        detail = None
        for _ in range(50):
            detail = client.get(f"/api/v1/runs/{run_id}").json()
            if detail["status"] in TERMINAL:
                break
            time.sleep(0.1)
    assert detail["status"] == "cancelled"
