from sqlalchemy import text

from backend.core.exceptions import LLMError
from backend.database import db
from tests.conftest import FakeLLMClient, wait_for_run

BASE = "/api/v1/llm-servers"
SEED_NAME = "Local (from env)"


async def _create(client, **fields):
    response = await client.post(BASE, json=fields)
    assert response.status_code == 201, response.text
    return response.json()


async def _servers(client) -> list[dict]:
    return (await client.get(BASE)).json()


async def test_seed_creates_one_default_from_env(client):
    body = await _servers(client)
    assert len(body) == 1
    seed = body[0]
    assert seed["name"] == SEED_NAME
    assert seed["provider"] == "openai_compatible"
    assert seed["is_default"] is True
    assert seed["base_url"].endswith("/v1")
    assert "api_key" not in seed and seed["has_api_key"] is False


async def test_create_returns_201_and_hides_api_key(client):
    r = await client.post(BASE, json={"name": "claude", "provider": "anthropic", "api_key": "sk-x"})
    assert r.status_code == 201
    assert r.json()["has_api_key"] is True and "api_key" not in r.json()


async def test_provider_rules_are_422(client):
    r = await client.post(BASE, json={"name": "x", "provider": "openai_compatible"})
    assert r.status_code == 422
    r = await client.post(BASE, json={"name": "y", "provider": "anthropic"})
    assert r.status_code == 422
    r = await client.post(BASE, json={"name": "z", "provider": "claude_cli"})
    assert r.status_code == 201


async def test_duplicate_name_is_409(client):
    payload = {"name": "dupe", "provider": "claude_cli"}
    assert (await client.post(BASE, json=payload)).status_code == 201
    assert (await client.post(BASE, json=payload)).status_code == 409


async def test_set_default_moves_the_flag(client):
    new = await _create(client, name="cli", provider="claude_cli")
    r = await client.post(f"{BASE}/{new['id']}/default")
    assert r.status_code == 200 and r.json()["is_default"] is True
    defaults = [s["id"] for s in await _servers(client) if s["is_default"]]
    assert defaults == [new["id"]]


async def test_create_with_is_default_clears_previous_default(client):
    new = await _create(client, name="cli", provider="claude_cli", is_default=True)
    assert new["is_default"] is True
    defaults = [s["id"] for s in await _servers(client) if s["is_default"]]
    assert defaults == [new["id"]]


async def test_capability_defaults_follow_provider_and_can_be_overridden(client):
    cli = await _create(client, name="cli", provider="claude_cli")
    assert (cli["supports_tools"], cli["supports_vision"], cli["supports_structured_output"]) == (
        True,
        True,
        False,
    )
    seed = next(s for s in await _servers(client) if s["name"] == SEED_NAME)
    assert seed["supports_tools"] is False and seed["supports_streaming"] is True
    local = await _create(
        client,
        name="llava",
        provider="openai_compatible",
        base_url="http://127.0.0.1:11434/v1",
        supports_vision=True,
    )
    assert local["supports_vision"] is True and local["supports_tools"] is False
    patched = await client.patch(f"{BASE}/{local['id']}", json={"supports_tools": True})
    assert patched.json()["supports_tools"] is True


async def test_options_typo_on_create_is_422(client):
    r = await client.post(
        BASE,
        json={"name": "x", "provider": "anthropic", "api_key": "sk-x", "options": {"max_token": 1}},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert any(item["loc"] == ["body"] and "max_token" in item["msg"] for item in detail)


async def test_options_invalid_type_on_patch_is_400(client):
    new = await _create(client, name="claude", provider="anthropic", api_key="sk-x")
    r = await client.patch(f"{BASE}/{new['id']}", json={"options": {"max_tokens": "abc"}})
    assert r.status_code == 400


async def test_options_round_trip_unchanged_per_provider(client):
    openai_server = await _create(
        client,
        name="openai",
        provider="openai_compatible",
        base_url="http://x/v1",
        options={"system_prompt": "be terse", "request": {"temperature": 0.1}},
    )
    assert openai_server["options"] == {"system_prompt": "be terse", "request": {"temperature": 0.1}}

    anthropic_server = await _create(
        client,
        name="claude",
        provider="anthropic",
        api_key="sk-x",
        options={"system_prompt": "be terse", "max_tokens": 2048},
    )
    assert anthropic_server["options"] == {"system_prompt": "be terse", "max_tokens": 2048}

    cli_server = await _create(
        client,
        name="cli",
        provider="claude_cli",
        options={"system_prompt": "be terse", "extra_args": ["--tools", ""], "cwd": "/tmp/x"},
    )
    assert cli_server["options"] == {
        "system_prompt": "be terse",
        "extra_args": ["--tools", ""],
        "cwd": "/tmp/x",
    }


async def test_delete_default_is_409(client):
    seed = (await _servers(client))[0]
    r = await client.delete(f"{BASE}/{seed['id']}")
    assert r.status_code == 409
    assert len(await _servers(client)) == 1


async def test_delete_non_default_is_204_then_404(client):
    new = await _create(client, name="cli", provider="claude_cli")
    assert (await client.delete(f"{BASE}/{new['id']}")).status_code == 204
    assert (await client.get(f"{BASE}/{new['id']}")).status_code == 404
    assert (await client.delete(f"{BASE}/{new['id']}")).status_code == 404


async def test_patch_keeps_api_key_unless_explicitly_cleared(client):
    new = await _create(client, name="claude", provider="anthropic", api_key="sk-x")
    kept = await client.patch(f"{BASE}/{new['id']}", json={"name": "claude-renamed"})
    assert kept.status_code == 200
    assert kept.json()["name"] == "claude-renamed" and kept.json()["has_api_key"] is True

    # Anthropic requires a key, so clearing it is rejected there...
    r = await client.patch(f"{BASE}/{new['id']}", json={"api_key": None})
    assert r.status_code == 400
    # ...but on a provider that does not need one, null clears it.
    cli = await _create(client, name="cli", provider="claude_cli", api_key="unused")
    assert cli["has_api_key"] is True
    cleared = await client.patch(f"{BASE}/{cli['id']}", json={"api_key": None})
    assert cleared.status_code == 200 and cleared.json()["has_api_key"] is False


async def test_patch_changing_provider_reapplies_rules(client):
    cli = await _create(client, name="cli", provider="claude_cli")
    r = await client.patch(f"{BASE}/{cli['id']}", json={"provider": "anthropic"})
    assert r.status_code == 400
    assert "api_key" in r.json()["detail"]
    # The failed patch must not have been persisted.
    assert (await client.get(f"{BASE}/{cli['id']}")).json()["provider"] == "claude_cli"

    r = await client.patch(f"{BASE}/{cli['id']}", json={"provider": "anthropic", "api_key": "sk-x"})
    assert r.status_code == 200 and r.json()["provider"] == "anthropic"


async def test_default_cannot_be_disabled(client):
    seed = (await _servers(client))[0]
    r = await client.patch(f"{BASE}/{seed['id']}", json={"is_enabled": False})
    assert r.status_code == 409


async def test_models_returns_client_list(client):
    seed = (await _servers(client))[0]
    r = await client.get(f"{BASE}/{seed['id']}/models")
    assert r.status_code == 200
    assert r.json() == {"models": ["fake-model-a", "fake-model-b"]}


async def test_run_streams_from_default_server(client):
    run_id = (await client.post("/api/v1/runs", json={"prompt": "hi there"})).json()["id"]
    detail = await wait_for_run(client, run_id)
    assert detail["status"] == "succeeded"
    text_out = "".join(e["data"]["text"] for e in detail["events"] if e["type"] == "token")
    assert text_out.strip() == "Echoing: hi there"
    non_status = [e for e in detail["events"] if e["type"] != "status"]
    assert non_status[-1]["type"] == "usage"
    assert non_status[-1]["data"]["output_tokens"] == 2


async def test_list_is_ordered_by_creation_with_exactly_one_default(client):
    await _create(client, name="b", provider="claude_cli")
    await _create(client, name="a", provider="claude_cli")
    servers = await _servers(client)
    assert [s["name"] for s in servers] == [SEED_NAME, "b", "a"]
    assert sum(1 for s in servers if s["is_default"]) == 1


async def test_validation_error_shapes_used_by_frontend(client):
    r = await client.post(BASE, json={"name": "", "provider": "claude_cli"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert any(item["loc"] == ["body", "name"] for item in detail)

    r = await client.post(BASE, json={"name": "x", "provider": "openai_compatible"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert any(item["loc"] == ["body"] and "base_url" in item["msg"] for item in detail)


async def test_patch_ignores_is_default(client):
    new = await _create(client, name="cli", provider="claude_cli")
    assert new["is_default"] is False
    r = await client.patch(f"{BASE}/{new['id']}", json={"is_default": True})
    assert r.status_code == 200
    assert r.json()["is_default"] is False


async def test_models_provider_failure_is_502(client, monkeypatch):
    class FailingLLMClient(FakeLLMClient):
        async def list_models(self) -> list[str]:
            raise LLMError("boom")

    from backend.services import llm_servers

    monkeypatch.setattr(llm_servers, "build_client", lambda server: FailingLLMClient())

    seed = (await _servers(client))[0]
    r = await client.get(f"{BASE}/{seed['id']}/models")
    assert r.status_code == 502
    assert r.json()["detail"] == "boom"


async def test_migrate_is_idempotent_and_stamps_head(client):
    await db.migrate()  # lifespan already ran it once; a second pass must be a no-op
    async with db.engine.connect() as conn:
        version = await conn.scalar(text("SELECT version_num FROM alembic_version"))
        tables = set(
            await conn.scalars(text("SELECT name FROM sqlite_master WHERE type = 'table'"))
        )
    assert version == "0001"
    assert {"llm_servers", "alembic_version"} <= tables
