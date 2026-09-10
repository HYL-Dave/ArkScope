"""Task 2: real card routes/fixed functions, SDK boundaries, temporary SQLite."""

import json
import sqlite3
from types import SimpleNamespace

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.agents import config as cfg
from src.api.routes import analysis_cards as api
from src.auth_drivers import subscription_structured_output as subscription
from src.auth_drivers.token_store import StoredTokenRecord
from src.card_runs import CardRunStore
from src.evidence_packet import EvidencePacket
from src.model_credentials import CredentialStore
from src.model_route_store import ModelRouteStore
from src.result_card import ResultCard, Traceability


UNKNOWN = {"provider": None, "model": None, "effort": None, "auth_mode": None}
CASES = [
    ("openai", "gpt-5.6-luna", "xhigh", "api_key"),
    ("anthropic", "claude-sonnet-5", "high", "api_key"),
    ("openai", "gpt-5.6-luna", "xhigh", "chatgpt_oauth"),
    ("anthropic", "claude-sonnet-5", "high", "claude_code_oauth"),
]


def card(conclusion="original"):
    return ResultCard(
        ticker="AAPL", analysis_time="2026-09-09T00:00:00Z",
        conclusion=conclusion, counter_thesis=["risk"], confidence_level="low",
        traceability=Traceability(),
    ).model_dump()


class Tokens:
    def __init__(self):
        self.records = {}
        self.loads = []

    def load(self, *, provider, auth_mode, credential_id):
        self.loads.append((provider, auth_mode, credential_id))
        return self.records.get(credential_id)

    def save(self, *, provider, auth_mode, credential_id, record):
        self.records[credential_id] = record


@pytest.fixture
def world(monkeypatch, tmp_path):
    from src import env_keys

    monkeypatch.setattr(env_keys, "read_env_file_values", lambda: {})
    monkeypatch.setattr(cfg, "get_agent_config", lambda: cfg.AgentConfig())
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile.db"))
    tokens = Tokens()
    monkeypatch.setattr("src.auth_drivers.token_store.get_token_store", lambda: tokens)
    monkeypatch.setattr(subscription, "get_token_store", lambda: tokens)
    monkeypatch.setattr(api, "resolve_personalization", lambda stance: ("", {}))
    monkeypatch.setattr(api, "require_db_write", lambda *args, **kwargs: None)
    monkeypatch.setattr(api, "gather_evidence", lambda *args, **kwargs: EvidencePacket(
        ticker="AAPL", generated_at="2026-09-09T00:00:00Z", items=[],
    ))
    store = CardRunStore(tmp_path / "cards.db")
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_card_store] = lambda: store
    app.dependency_overrides[api.get_dal] = lambda: object()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield SimpleNamespace(
            client=client, cards=store, routes=ModelRouteStore(),
            credentials=CredentialStore(), tokens=tokens, path=tmp_path,
        )


@pytest.fixture
def wire(monkeypatch, world):
    """Replace external I/O only; keep SDK request serialization and admission."""
    from openai import OpenAI
    from anthropic import Anthropic
    from claude_agent_sdk import ResultMessage, SystemMessage

    state = SimpleNamespace(calls=[], fail=False, result="first", clients=[])

    def payload(name, schema):
        if "translated_text" in schema["properties"]:
            return {"translated_text": state.result}
        if name == "emit_result_card":
            return {"conclusion": state.result, "counter_thesis": ["risk"],
                    "confidence_level": "low", "claims": []}
        return {"conclusion": state.result, "counter_thesis": ["risk"]}

    def handler(request):
        body = json.loads(request.content)
        provider = "openai" if request.url.path.endswith("/responses") else "anthropic"
        state.calls.append((provider, request, body))
        if state.fail:
            # Deliberately nonstandard key shape: only captured-key redaction works.
            return httpx2.Response(400, json={"error": {
                "message": "bad chosen-card-secret and Bearer synthetic-token",
                "type": "invalid_request_error"}})
        name = body["tools"][0]["name"]
        schema = body["tools"][0].get("parameters") or body["tools"][0].get("input_schema")
        if provider == "openai":
            return httpx2.Response(200, json={
                "id": "resp_test", "object": "response", "created_at": 1,
                "model": body["model"], "status": "completed", "error": None,
                "output": [{"type": "function_call", "id": "fc_test", "call_id": "call_test",
                            "name": name, "status": "completed", "arguments": json.dumps(payload(name, schema))}],
            })
        return httpx2.Response(200, json={
            "id": "msg_test", "type": "message", "role": "assistant", "model": body["model"],
            "content": [{"type": "tool_use", "id": "tool_test", "name": name, "input": payload(name, schema)}],
            "stop_reason": "tool_use", "usage": {"input_tokens": 1, "output_tokens": 1},
        })

    def construct(cls, kwargs):
        client = cls(**kwargs, http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
        state.clients.append(client)
        return client

    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: construct(OpenAI, kwargs))
    monkeypatch.setattr("anthropic.Anthropic", lambda **kwargs: construct(Anthropic, kwargs))

    def oauth_client(token, base_url, timeout_s):
        def create(**kwargs):
            state.calls.append(("openai_oauth", token, kwargs))
            if state.fail:
                raise RuntimeError("Bearer synthetic-token")
            name = kwargs["tools"][0]["name"]
            return iter([
                {"type": "response.output_item.done", "item": {
                    "type": "function_call", "name": name, "call_id": "call_test",
                    "arguments": json.dumps(payload(name, kwargs["tools"][0]["parameters"]))}},
                {"type": "response.completed", "response": {"output": []}},
            ])
        return SimpleNamespace(responses=SimpleNamespace(create=create), close=lambda: None)

    monkeypatch.setattr(subscription, "_openai_client", oauth_client)
    monkeypatch.setattr(subscription, "_claude_transport", lambda **kwargs: object())

    async def claude_query(*, prompt, options, transport):
        state.calls.append(("anthropic_oauth", options.env["CLAUDE_CODE_OAUTH_TOKEN"], options))
        if state.fail:
            raise RuntimeError("Bearer synthetic-token")
        yield SystemMessage(subtype="init", data={"apiKeySource": "none"})
        name = "emit_result_card" if "claims" in options.output_format["schema"]["properties"] else "emit_translation"
        yield ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1,
                            is_error=False, num_turns=2, session_id="synthetic",
                            structured_output=payload(name, options.output_format["schema"]))

    monkeypatch.setattr(subscription, "_claude_query", claude_query)
    yield state
    for client in state.clients:
        client.close()


def select(world, task, provider, model, effort, mode):
    world.routes.set(task, provider, model, effort)
    if mode == "api_key":
        cred = world.credentials.add(provider=provider, auth_type=mode, alias="synthetic", secret="chosen-card-secret")
    else:
        cred = world.credentials.add_oauth_credential(provider=provider, auth_mode=mode, alias="synthetic")
    world.tokens.records[f"local:{cred.id}"] = StoredTokenRecord(
        access_token="synthetic-token", expires_at="2999-01-01T00:00:00+00:00",
    )
    return cred


def change_settings(world, task, provider, cred, monkeypatch):
    world.routes.set(task, "anthropic" if provider == "openai" else "openai",
                     "claude-opus-5" if provider == "openai" else "gpt-5.6-sol", "low")
    if cred.auth_type == "api_key":
        world.credentials.update(f"local:{cred.id}", secret="mutated-card-secret")
    world.credentials.add(provider=provider, auth_type="api_key", alias="replacement", secret="replacement-card-secret")
    for p in ("OPENAI", "ANTHROPIC"):
        monkeypatch.setenv(f"{p}_API_KEY", "ambient-card-secret")
        monkeypatch.setenv(f"{p}_BASE_URL", "https://wrong.invalid")
        monkeypatch.setenv(f"{p}_CUSTOM_HEADERS", "Authorization: Bearer wrong\nx-api-key: wrong")
    monkeypatch.setattr("src.auth_drivers.token_store.get_token_store", lambda: Tokens())
    monkeypatch.setattr(subscription, "get_token_store", lambda: Tokens())


@pytest.mark.parametrize("same_provider", [False, True])
@pytest.mark.parametrize("task", ["card_synthesis", "card_translation"])
@pytest.mark.parametrize("provider,model,effort,mode", CASES)
def test_api_fixed_dispatch_pins_complete_selection(world, wire, monkeypatch, same_provider, task, provider, model, effort, mode):
    cred = select(world, task, provider, model, effort, mode)
    reads = []
    original_get = ModelRouteStore.get

    def read(store, task):
        reads.append(task)
        return original_get(store, task)

    monkeypatch.setattr(ModelRouteStore, "get", read)
    def mutate():
        change_settings(world, task, provider, cred, monkeypatch)
        if same_provider:
            world.routes.set(task, provider, "gpt-5.6-sol" if provider == "openai" else "claude-opus-5", "low")
    if task == "card_synthesis":
        gather = api.gather_evidence
        def changed_gather(*args, **kwargs):
            mutate()
            return gather(*args, **kwargs)
        monkeypatch.setattr(api, "gather_evidence", changed_gather)
        response = world.client.post("/analysis/card/AAPL", json={"include_sa": False})
    else:
        runtime = api.resolve_fixed_task_runtime
        def changed_runtime(task):
            mutate()
            return runtime(task)
        monkeypatch.setattr(api, "resolve_fixed_task_runtime", changed_runtime)
        run = world.cards.record(ticker="AAPL", result_card=card())
        response = world.client.post(f"/analysis/cards/{run.id}/translate", json={"lang": "zh-Hant"})
    assert response.status_code == 200, response.text
    assert len(wire.calls) == 1
    actual_provider, auth, sent = wire.calls[0]
    assert actual_provider == (provider if mode == "api_key" else f"{provider}_oauth")
    if mode == "api_key":
        assert auth.url.host == ("api.openai.com" if provider == "openai" else "api.anthropic.com")
        header = "authorization" if provider == "openai" else "x-api-key"
        assert auth.headers[header] == ("Bearer chosen-card-secret" if provider == "openai" else "chosen-card-secret")
        assert "wrong" not in str(auth.headers)
        assert sent["model"] == model
        assert sent["reasoning" if provider == "openai" else "output_config"]["effort"] == effort
    else:
        assert auth == "synthetic-token"
        assert world.tokens.loads == [(provider, mode, f"local:{cred.id}")]
        actual = (sent["model"], sent["reasoning"]["effort"]) if provider == "openai" else (sent.model, sent.effort)
        assert actual == (model, effort)
    assert reads == [task]
    receipt = {"provider": provider, "model": model, "effort": effort, "auth_mode": mode}
    assert response.json()["execution_receipt"] == receipt
    rid = response.json()["run_id"]
    reopened = CardRunStore(world.cards.db_path)
    if task == "card_synthesis":
        assert reopened.get(rid).execution_receipt.model_dump() == receipt
        assert world.client.get(f"/analysis/cards/{rid}").json()["execution_receipt"] == receipt
        assert world.client.get("/analysis/cards").json()["cards"][0]["execution_receipt"] == receipt
    else:
        cached = world.client.post(f"/analysis/cards/{rid}/translate", json={"lang": "zh-Hant"}).json()
        assert cached["cached"] is True and cached["execution_receipt"] == receipt
        assert len(wire.calls) == 1
    with sqlite3.connect(world.cards.db_path) as conn:
        dump = "\n".join(conn.iterdump())
    for secret in ("chosen-card-secret", "synthetic-token", "mutated-card-secret", "replacement-card-secret", "credential_id"):
        assert secret not in response.text + dump


def test_cache_refresh_failure_and_prior_versions_survive_reopen(world, wire):
    select(world, "card_translation", *CASES[0])
    run = world.cards.record(ticker="AAPL", result_card=card())
    url = f"/analysis/cards/{run.id}/translate"
    first = world.client.post(url, json={"lang": "zh-Hant"})
    assert first.status_code == 200
    first_receipt = {"provider": "openai", "model": "gpt-5.6-luna", "effort": "xhigh", "auth_mode": "api_key"}
    wire.result = "second"
    world.routes.set("card_translation", "openai", "gpt-5.6-sol", "low")
    cached = world.client.post(url, json={"lang": "zh-Hant"}).json()
    assert cached["cached"] is True and cached["card"]["conclusion"] == "first"
    assert len(wire.calls) == 1
    refreshed = world.client.post(url, json={"lang": "zh-Hant", "refresh": True})
    assert refreshed.status_code == 200
    assert refreshed.json()["card"]["conclusion"] == "second"
    assert len(wire.calls) == 2
    assert refreshed.json()["execution_receipt"] == {**first_receipt, "model": "gpt-5.6-sol", "effort": "low"}
    wire.fail = True
    assert world.client.post(url, json={"lang": "zh-Hant", "refresh": True}).status_code == 502
    assert len(wire.calls) == 3
    reopened = CardRunStore(world.cards.db_path)
    assert reopened.get_translation(run.id, "zh-Hant")["conclusion"] == "second"
    versions = reopened.translation_versions(run.id, "zh-Hant")
    assert [v["card"]["conclusion"] for v in versions] == ["first", "second"]
    assert versions[0]["execution_receipt"] == first_receipt


def test_legacy_unknown_cache_never_reads_settings_or_auth(world, monkeypatch):
    run = world.cards.record(ticker="AAPL", result_card=card(), provider="openai", model="gpt-5.4-mini")
    with sqlite3.connect(world.cards.db_path) as conn:
        conn.execute("UPDATE ai_card_runs SET translations_json = ? WHERE id = ?",
                     (json.dumps({"zh-Hant": card("legacy translation")}), run.id))
    def forbidden(*args, **kwargs):
        pytest.fail("cache/history must not resolve current Settings")
    monkeypatch.setattr(api, "task_route", forbidden)
    monkeypatch.setattr(CredentialStore, "list", forbidden)
    cached = world.client.post(f"/analysis/cards/{run.id}/translate", json={"lang": "zh-Hant"})
    assert cached.status_code == 200 and cached.json()["cached"] is True
    assert cached.json()["execution_receipt"] == UNKNOWN
    detail = world.client.get(f"/analysis/cards/{run.id}").json()
    assert detail["execution_receipt"] == {**UNKNOWN, "provider": "openai", "model": "gpt-5.4-mini"}


def test_empty_prose_is_zero_dispatch_no_receipt_or_new_version(world, wire, monkeypatch):
    run = world.cards.record(ticker="AAPL", result_card={"ticker": "AAPL"})
    def forbidden(*args, **kwargs):
        raise RuntimeError("a no-op must not select an execution")
    monkeypatch.setattr(api, "task_route", forbidden)
    response = world.client.post(f"/analysis/cards/{run.id}/translate", json={"lang": "zh-Hant", "refresh": True})
    assert response.status_code == 200
    assert response.json() == {"run_id": run.id, "lang": "zh-Hant", "card": {"ticker": "AAPL"},
                               "cached": False, "no_op": True, "execution_receipt": None}
    assert wire.calls == []
    assert world.cards.get(run.id).translations is None


@pytest.mark.parametrize("task", ["card_synthesis", "card_translation"])
def test_route_read_failure_is_bounded_http_and_zero_dispatch(world, wire, monkeypatch, task):
    def fail(*args):
        raise RuntimeError("route-store-secret")
    monkeypatch.setattr(ModelRouteStore, "get", fail)
    if task == "card_synthesis":
        response = world.client.post("/analysis/card/AAPL", json={"include_sa": False})
    else:
        run = world.cards.record(ticker="AAPL", result_card=card())
        response = world.client.post(f"/analysis/cards/{run.id}/translate", json={"lang": "zh-Hant"})
    assert response.status_code == 503
    assert response.json()["detail"] == {"code": "model_route_unavailable"}
    assert wire.calls == []


@pytest.mark.parametrize("provider,model,effort,mode", CASES[:2])
def test_failed_generation_redacts_selected_key_after_activation(world, wire, monkeypatch, caplog, provider, model, effort, mode):
    cred = select(world, "card_synthesis", provider, model, effort, mode)
    gather = api.gather_evidence
    def changed(*args, **kwargs):
        change_settings(world, "card_synthesis", provider, cred, monkeypatch)
        return gather(*args, **kwargs)
    monkeypatch.setattr(api, "gather_evidence", changed)
    wire.fail = True
    response = world.client.post("/analysis/card/AAPL", json={"include_sa": False})
    assert response.status_code == 502
    assert len(wire.calls) == 1 and world.cards.recent() == []
    assert "chosen-card-secret" not in response.text + caplog.text
    assert "synthetic-token" not in response.text + caplog.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.parametrize("status", [401, 403, 429])
def test_card_oauth_auth_failure_survives_sdk_to_http_without_retry_or_storage(
    world, monkeypatch, caplog, status,
):
    import httpx
    from openai import AsyncOpenAI

    select(world, "card_synthesis", "openai", "gpt-5.6-luna", "max", "chatgpt_oauth")
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, json={"error": {
            "message": "Provided access token is expired. Bearer synthetic-token",
            "type": "authentication_error" if status == 401 else "invalid_request_error",
        }})

    monkeypatch.setattr("openai.AsyncOpenAI", lambda **kw: AsyncOpenAI(
        **kw, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    ))
    response = world.client.post("/analysis/card/AMD", json={"include_sa": False})
    assert response.status_code == 502
    assert len(requests) == 1
    assert requests[0].headers.get_list("authorization") == ["Bearer synthetic-token"]
    body = json.loads(requests[0].content)
    assert (body["model"], body["reasoning"]) == ("gpt-5.6-luna", {"effort": "max"})
    assert world.cards.recent() == []
    assert "synthetic-token" not in response.text + caplog.text
    if status == 401:
        assert response.json()["detail"] == {
            "code": "reauth_required", "task": "card_synthesis", "provider": "openai",
            "model": "gpt-5.6-luna", "effort": "max", "auth_mode": "chatgpt_oauth",
        }
        assert "Provided access token" not in response.text
    else:
        assert "reauth_required" not in response.text


def test_additive_schema_preserves_legacy_payload_and_versions(tmp_path):
    from src.card_execution import ExecutionReceipt

    db = tmp_path / "legacy.db"
    raw = '{ "conclusion": "historical" }'
    legacy = json.dumps({"zh-Hant": {"conclusion": "old translation"}})
    with sqlite3.connect(db) as conn:
        conn.executescript("""
            CREATE TABLE ai_card_runs (
                id INTEGER PRIMARY KEY, ticker TEXT, question TEXT, horizon TEXT,
                card_type TEXT, result_card_json TEXT, evidence_packet_json TEXT,
                provider TEXT, model TEXT, generated_at TEXT, as_of TEXT, status TEXT,
                saved_report_id INTEGER, expires_at TEXT, translations_json TEXT
            );
        """)
        conn.execute("INSERT INTO ai_card_runs (id, ticker, result_card_json, translations_json, status) VALUES (7, 'AAPL', ?, ?, 'saved')", (raw, legacy))
    store = CardRunStore(db)
    assert store.get(7).execution_receipt.model_dump() == UNKNOWN
    receipt = ExecutionReceipt(provider="openai", model="gpt-5.6-luna", effort="xhigh", auth_mode="api_key")
    store.set_translation(7, "zh-Hant", {"conclusion": "new translation"}, execution_receipt=receipt)
    store = CardRunStore(db)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT result_card_json FROM ai_card_runs").fetchone()[0] == raw
    versions = store.translation_versions(7, "zh-Hant")
    assert [v["card"]["conclusion"] for v in versions] == ["old translation", "new translation"]
    assert versions[0]["execution_receipt"] == UNKNOWN
    assert versions[1]["execution_receipt"] == receipt.model_dump()


@pytest.mark.parametrize("operation", ["generation", "translation"])
def test_output_and_receipt_commit_atomically(world, operation):
    from src.card_execution import ExecutionReceipt

    receipt = ExecutionReceipt(provider="openai", model="gpt-5.6-luna", effort="xhigh", auth_mode="api_key")
    run = world.cards.record(ticker="AAPL", result_card=card())
    world.cards.set_translation(run.id, "zh-Hant", card("prior"), execution_receipt=receipt)
    table = "ai_card_execution_receipts" if operation == "generation" else "ai_card_translation_versions"
    with sqlite3.connect(world.cards.db_path) as conn:
        conn.execute(f"CREATE TRIGGER reject_receipt BEFORE INSERT ON {table} BEGIN SELECT RAISE(ABORT, 'synthetic storage failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        if operation == "generation":
            world.cards.record(ticker="AAPL", result_card=card("not committed"), execution_receipt=receipt)
        else:
            world.cards.set_translation(run.id, "zh-Hant", card("not committed"), execution_receipt=receipt)
    reopened = CardRunStore(world.cards.db_path)
    assert len(reopened.recent()) == 1
    assert reopened.get_translation(run.id, "zh-Hant")["conclusion"] == "prior"
    assert len(reopened.translation_versions(run.id, "zh-Hant")) == 1


@pytest.mark.parametrize("task,provider,model,effort,mode,code", [
    ("card_synthesis", "openai", "gpt-5.3-codex-spark", "high", "chatgpt_oauth", "model_task_unsupported"),
    ("card_translation", "openai", "gpt-5.3-codex-spark", "high", "api_key", "task_auth_mode_unsupported"),
    ("card_synthesis", "anthropic", "claude-opus-4-7", "high", "api_key", "model_retired"),
    ("card_translation", "anthropic", "claude-opus-4-7", "high", "api_key", "model_retired"),
    ("card_synthesis", "anthropic", "claude-fable-5-1", "high", "claude_code_oauth", "model_auth_unverified"),
    ("card_translation", "anthropic", "claude-fable-5-1", "high", "claude_code_oauth", "model_auth_unverified"),
    ("card_translation", "openai", "gpt-5.6-luna", "default", "api_key", "effort_required"),
])
def test_model_auth_admission_stays_typed_without_dispatch(world, wire, task, provider, model, effort, mode, code):
    select(world, task, provider, model, effort, mode)
    if task == "card_synthesis":
        response = world.client.post("/analysis/card/AAPL", json={"include_sa": False})
        assert world.cards.recent() == []
    else:
        run = world.cards.record(ticker="AAPL", result_card=card())
        response = world.client.post(f"/analysis/cards/{run.id}/translate", json={"lang": "zh-Hant"})
        assert world.cards.get(run.id).translations is None
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == code
    assert wire.calls == []


@pytest.mark.parametrize("provider,model,effort,mode", CASES[2:])
def test_oauth_selected_token_missing_never_bills_replacement_key(world, wire, monkeypatch, provider, model, effort, mode):
    cred = select(world, "card_translation", provider, model, effort, mode)
    run = world.cards.record(ticker="AAPL", result_card=card())
    with sqlite3.connect(world.cards.db_path) as conn:
        conn.execute("UPDATE ai_card_runs SET translations_json = ? WHERE id = ?",
                     (json.dumps({"zh-Hant": card("legacy cached")}), run.id))
    runtime = api.resolve_fixed_task_runtime
    def revoke(task):
        world.tokens.records.clear()
        change_settings(world, task, provider, cred, monkeypatch)
        return runtime(task)
    monkeypatch.setattr(api, "resolve_fixed_task_runtime", revoke)
    response = world.client.post(f"/analysis/cards/{run.id}/translate", json={"lang": "zh-Hant", "refresh": True})
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "translation_auth_rejected"
    assert world.tokens.loads == [(provider, mode, f"local:{cred.id}")]
    assert wire.calls == []
    assert world.cards.get_translation(run.id, "zh-Hant")["conclusion"] == "legacy cached"
    assert world.cards.translation_versions(run.id, "zh-Hant") == []


@pytest.mark.parametrize("provider,model", [("anthropic", "claude-opus-5"), ("openai", "gpt-5.6-sol")])
def test_genuine_missing_route_env_auth_and_explicit_provider_override(world, wire, monkeypatch, provider, model):
    monkeypatch.setenv(f"{provider.upper()}_API_KEY", "chosen-card-secret")
    gather = api.gather_evidence
    def change_env(*args, **kwargs):
        monkeypatch.setenv(f"{provider.upper()}_API_KEY", "replacement-card-secret")
        return gather(*args, **kwargs)
    monkeypatch.setattr(api, "gather_evidence", change_env)
    # OpenAI is a deliberate override of the missing route's Anthropic default.
    response = world.client.post("/analysis/card/AAPL", json={"include_sa": False, "provider": provider})
    assert response.status_code == 200, response.text
    assert response.json()["execution_receipt"] == {"provider": provider, "model": model, "effort": "high", "auth_mode": "api_key"}
    assert len(wire.calls) == 1
    _, request, sent = wire.calls[0]
    assert sent["model"] == model
    assert request.headers["authorization" if provider == "openai" else "x-api-key"] == (
        "Bearer chosen-card-secret" if provider == "openai" else "chosen-card-secret"
    )


def test_selected_broken_credential_is_not_genuine_env_fallback(world, wire, monkeypatch):
    select(world, "card_synthesis", *CASES[0])
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-must-not-bill")
    with sqlite3.connect(world.path / "profile.db") as conn:
        conn.execute("UPDATE llm_credentials SET secret = NULL WHERE active = 1")
    response = world.client.post("/analysis/card/AAPL", json={"include_sa": False})
    assert response.status_code == 503
    assert response.json()["detail"] == {"code": "runtime_auth_unavailable"}
    assert wire.calls == [] and world.cards.recent() == []


def test_receipt_rejects_extra_internal_fields_before_storage(world):
    from pydantic import ValidationError
    from src.card_execution import ExecutionReceipt, capture_card_execution

    with pytest.raises(ValidationError):
        ExecutionReceipt(provider="openai", model="gpt-5.6-luna", effort="high", auth_mode="api_key", credential_id="local:1")
    select(world, "card_synthesis", *CASES[0])
    execution = capture_card_execution("card_synthesis", cfg.task_route("card_synthesis"))
    assert "chosen-card-secret" not in repr(execution)
    with pytest.raises(ValueError, match="execution_receipt_invalid"):
        world.cards.record(ticker="AAPL", result_card=card(), execution_receipt=execution.auth)
    assert world.cards.recent() == []


@pytest.mark.parametrize("fails", [False, True])
def test_original_oauth_id_can_refresh_normally_without_reselection(world, wire, monkeypatch, fails):
    from src.auth_drivers import chatgpt_oauth_login as login

    cred = select(world, "card_synthesis", *CASES[2])
    cid = f"local:{cred.id}"
    world.tokens.records[cid] = StoredTokenRecord(
        access_token="expired-token", refresh_token="synthetic-refresh",
        expires_at="2000-01-01T00:00:00+00:00",
    )
    grants = []
    def grant(*, refresh_token):
        grants.append(refresh_token)
        if fails:
            raise RuntimeError("synthetic refresh failure")
        return {"access_token": "refreshed-token", "expires_in": 3600}
    monkeypatch.setattr(login, "_refresh_token_grant", grant)
    monkeypatch.setattr(login, "_sync_account_after_token_mutation", lambda *args: None)
    gather = api.gather_evidence
    def changed(*args, **kwargs):
        change_settings(world, "card_synthesis", "openai", cred, monkeypatch)
        return gather(*args, **kwargs)
    monkeypatch.setattr(api, "gather_evidence", changed)
    response = world.client.post("/analysis/card/AAPL", json={"include_sa": False})
    assert grants == ["synthetic-refresh"]
    assert world.tokens.loads == [("openai", "chatgpt_oauth", cid)]
    if fails:
        assert response.status_code == 502
        assert wire.calls == [] and world.cards.recent() == []
    else:
        assert response.status_code == 200, response.text
        assert len(wire.calls) == 1 and wire.calls[0][1] == "refreshed-token"
        assert world.tokens.records[cid].access_token == "refreshed-token"
        assert response.json()["execution_receipt"] == {
            "provider": "openai", "model": "gpt-5.6-luna", "effort": "xhigh", "auth_mode": "chatgpt_oauth",
        }
