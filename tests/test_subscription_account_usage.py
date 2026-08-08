from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import sqlite3
import stat
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


_ACCOUNT_ID = "acct_fixture_raw_identifier"
_ACCESS_TOKEN = "access-token-fixture-must-not-escape"
_ID_TOKEN_SENTINEL = "id-token-fixture-must-not-escape"
_OBSERVED_AT = "2026-08-08T12:00:00+00:00"


@pytest.fixture(autouse=True)
def _isolate_oauth_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile-state.db"))
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))


def _jwt(payload: dict) -> str:
    def encode(value: dict) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{encode({'alg': 'none'})}.{encode(payload)}.fixture-signature"


def _token_record(*, account_id: str = _ACCOUNT_ID, claimed_account_id: str | None = None):
    from src.auth_drivers.token_store import StoredTokenRecord

    claimed = claimed_account_id if claimed_account_id is not None else account_id
    id_token = _jwt(
        {
            "https://api.openai.com/auth": {
                "chatgpt_account_id": claimed,
                "chatgpt_plan_type": "plus",
            }
        }
    )
    return StoredTokenRecord(
        access_token=_ACCESS_TOKEN,
        expires_at="2026-08-09T12:00:00+00:00",
        plan_type="plus",
        account_label="ChatGPT Plus",
        metadata={
            "account_id": account_id,
            "id_token": id_token,
            "fixture_sentinel": _ID_TOKEN_SENTINEL,
        },
    )


class _TokenStore:
    def __init__(self, record):
        self.record = record
        self.loads = 0

    def load(self, *, provider, auth_mode, credential_id):
        self.loads += 1
        return self.record


def _rate_limits_payload() -> dict:
    bucket = {
        "limitId": "codex",
        "limitName": "Codex",
        "primary": {
            "usedPercent": 100,
            "windowDurationMins": 300,
            "resetsAt": 1786208400,
        },
        "secondary": {
            "usedPercent": 34,
            "windowDurationMins": 10080,
            "resetsAt": 1786773600,
        },
        "planType": "plus",
        "rateLimitReachedType": "rate_limit_reached",
        "credits": {"balance": "0", "hasCredits": False, "unlimited": False},
        "individualLimit": {
            "limit": "25.00",
            "used": "25.00",
            "remainingPercent": 0,
            "resetsAt": 1786773600,
        },
        "spendControlReached": True,
        "rawAccountId": _ACCOUNT_ID,
    }
    return {
        "rateLimits": bucket,
        "rateLimitsByLimitId": {"codex": bucket},
        "rateLimitResetCredits": {"availableCount": 0, "credits": []},
        "unknownTopLevel": _ID_TOKEN_SENTINEL,
    }


def _usage_payload() -> dict:
    return {
        "summary": {
            "lifetimeTokens": 14_243_654_879,
            "peakDailyTokens": 987_654,
            "longestRunningTurnSec": 321,
            "currentStreakDays": 8,
            "longestStreakDays": 21,
        },
        "dailyUsageBuckets": [
            {"startDate": "2026-08-07", "tokens": 1000},
            {"startDate": "2026-08-08", "tokens": 2000},
        ],
        "rawToken": _ACCESS_TOKEN,
    }


def _write_codex_fixture(
    root: Path,
    *,
    version: str = "0.147.0",
    unexpected_method: str | None = None,
    hang_method: str | None = None,
) -> tuple[Path, Path, Path]:
    executable = root / "codex-fixture"
    transcript = root / "methods.jsonl"
    pid_path = root / "app-server.pid"
    rate_limits = json.dumps(_rate_limits_payload(), separators=(",", ":"))
    usage = json.dumps(_usage_payload(), separators=(",", ":"))
    source = '''#!%s
import json
import os
import sys
import time

VERSION = %r
TRANSCRIPT = %r
PID_PATH = %r
RATE_LIMITS = json.loads(%r)
USAGE = json.loads(%r)
UNEXPECTED = %r
HANG = %r

if sys.argv[1:] == ["--version"]:
    print(f"codex-cli {VERSION}", flush=True)
    raise SystemExit(0)

Path = __import__("pathlib").Path
Path(PID_PATH).write_text(str(os.getpid()), encoding="utf-8")

def emit(value):
    print(json.dumps(value, separators=(",", ":")), flush=True)

for raw in sys.stdin:
    message = json.loads(raw)
    method = message.get("method")
    with open(TRANSCRIPT, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"method": method, "codex_home": os.environ.get("CODEX_HOME")}) + "\\n")
    if method == HANG:
        while True:
            time.sleep(1)
    if method == "initialized":
        continue
    request_id = message["id"]
    if method == "initialize":
        emit({"id": request_id, "result": {"codexHome": os.environ.get("CODEX_HOME"), "platformFamily": "unix", "platformOs": "linux", "userAgent": "fixture"}})
    elif method == "account/login/start":
        emit({"id": request_id, "result": {"type": "chatgptAuthTokens"}})
    elif method == "account/read":
        emit({"id": request_id, "result": {"account": {"type": "chatgpt", "email": "raw@example.invalid", "planType": "plus"}, "requiresOpenaiAuth": True}})
    elif method == "account/rateLimits/read":
        if UNEXPECTED:
            emit({"method": UNEXPECTED, "params": {"secret": %r}})
        emit({"id": request_id, "result": RATE_LIMITS})
    elif method == "account/usage/read":
        emit({"id": request_id, "result": USAGE})
    else:
        emit({"id": request_id, "error": {"code": -32601, "message": "unknown method"}})
''' % (
        sys.executable,
        version,
        str(transcript),
        str(pid_path),
        rate_limits,
        usage,
        unexpected_method,
        hang_method,
        _ACCOUNT_ID,
    )
    executable.write_text(source, encoding="utf-8")
    executable.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return executable, transcript, pid_path


def _wait_for_process_exit(pid: int) -> None:
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.02)
    pytest.fail(f"fixture app-server process {pid} remained alive")


def _snapshot_input(
    *,
    credential_id: str = "local:1",
    observed_at: str = _OBSERVED_AT,
    account_fingerprint: str = "f" * 64,
):
    from src.auth_drivers.oauth_status import (
        OAuthAccountObservation,
        OAuthAccountPayload,
        OAuthRateLimitSnapshot,
        OAuthRateLimitWindow,
        OAuthUsageSummary,
    )

    return OAuthAccountObservation(
        account_fingerprint=account_fingerprint,
        source="codex_app_server",
        schema_version=1,
        observed_at=observed_at,
        status="available",
        payload=OAuthAccountPayload(
            rate_limits=OAuthRateLimitSnapshot(
                limit_id="codex",
                plan_type="plus",
                primary=OAuthRateLimitWindow(
                    used_percent=50,
                    window_duration_minutes=300,
                    resets_at=1786208400,
                ),
            ),
            usage_summary=OAuthUsageSummary(lifetime_tokens=1234),
        ),
    )


def _seed_snapshot(
    store,
    *,
    credential_id: str = "local:1",
    observed_at: str = _OBSERVED_AT,
    account_fingerprint: str = "f" * 64,
):
    store.record_account_snapshot(
        credential_id=credential_id,
        provider="openai",
        auth_mode="chatgpt_oauth",
        observation=_snapshot_input(
            credential_id=credential_id,
            observed_at=observed_at,
            account_fingerprint=account_fingerprint,
        ),
    )
    return store.read_account_snapshot(credential_id)


def test_codex_account_sync_reads_limits_and_usage_without_starting_thread_or_turn(tmp_path):
    from src.auth_drivers.codex_account_usage import CodexAccountUsageAdapter

    executable, transcript, pid_path = _write_codex_fixture(tmp_path)
    adapter = CodexAccountUsageAdapter(executable=executable, timeout_seconds=2.0)
    observation = adapter.read_account_usage(
        credential_id="local:1",
        record=_token_record(),
        observed_at=_OBSERVED_AT,
    )

    assert observation.status == "available"
    assert observation.source == "codex_app_server"
    assert observation.payload.rate_limits.primary.used_percent == 100
    assert observation.payload.rate_limits.secondary.used_percent == 34
    assert observation.payload.rate_limits.credits.balance == "0"
    assert observation.payload.rate_limits.spend_control_reached is True
    assert observation.payload.usage_summary.lifetime_tokens == 14_243_654_879
    assert [row.tokens for row in observation.payload.daily_usage_buckets] == [1000, 2000]
    assert observation.account_fingerprint == hashlib.sha256(
        f"local:1\0{_ACCOUNT_ID}".encode()
    ).hexdigest()

    serialized = json.dumps(observation.model_dump(), sort_keys=True)
    assert _ACCOUNT_ID not in serialized
    assert _ACCESS_TOKEN not in serialized
    assert _ID_TOKEN_SENTINEL not in serialized
    assert "raw@example.invalid" not in serialized
    methods = [json.loads(line)["method"] for line in transcript.read_text().splitlines()]
    assert methods == [
        "initialize",
        "initialized",
        "account/login/start",
        "account/read",
        "account/rateLimits/read",
        "account/usage/read",
    ]
    assert not any(method.startswith(("thread/", "turn/")) for method in methods)
    homes = {json.loads(line)["codex_home"] for line in transcript.read_text().splitlines()}
    assert len(homes) == 1
    assert next(iter(homes)) != str(Path.home() / ".codex")
    _wait_for_process_exit(int(pid_path.read_text()))


def test_exhausted_account_fixture_preserves_usage_across_five_rate_limit_reads(tmp_path):
    from src.auth_drivers.codex_account_usage import CodexAccountUsageAdapter

    before = _usage_payload()["summary"]
    observed = []
    for index in range(5):
        root = tmp_path / str(index)
        root.mkdir()
        executable, transcript, _ = _write_codex_fixture(root)
        result = CodexAccountUsageAdapter(
            executable=executable, timeout_seconds=2.0
        ).read_account_usage(
            credential_id="local:1",
            record=_token_record(),
            observed_at=_OBSERVED_AT,
        )
        observed.append(result.payload.usage_summary.model_dump())
        methods = [json.loads(line)["method"] for line in transcript.read_text().splitlines()]
        assert methods.count("account/rateLimits/read") == 1
        assert not any(method.startswith(("thread/", "turn/")) for method in methods)

    expected = {
        "lifetime_tokens": before["lifetimeTokens"],
        "peak_daily_tokens": before["peakDailyTokens"],
        "longest_running_turn_seconds": before["longestRunningTurnSec"],
        "current_streak_days": before["currentStreakDays"],
        "longest_streak_days": before["longestStreakDays"],
    }
    assert observed == [expected] * 5


def test_account_sync_rejects_account_mismatch_without_replacing_last_good_snapshot(tmp_path):
    from src.api.dependencies import OAuthAccountSyncService
    from src.auth_drivers.codex_account_usage import CodexAccountUsageAdapter
    from src.auth_drivers.oauth_status import OAuthObservationStore

    observations = OAuthObservationStore(tmp_path / "profile.db")
    original = _seed_snapshot(
        observations,
        account_fingerprint=hashlib.sha256(b"local:1\0acct_expected").hexdigest(),
    )
    executable, _, pid_path = _write_codex_fixture(tmp_path)
    service = OAuthAccountSyncService(
        observation_store=observations,
        token_store=_TokenStore(
            _token_record(account_id="acct_expected", claimed_account_id="acct_other")
        ),
        adapter=CodexAccountUsageAdapter(executable=executable, timeout_seconds=2.0),
    )

    result = service.sync(
        credential_id="local:1", provider="openai", auth_mode="chatgpt_oauth"
    )
    assert result.sync_status == "failed"
    assert result.sync_error_code == "account_mismatch"
    assert result.snapshot == original
    assert observations.read_account_snapshot("local:1") == original
    assert not pid_path.exists()


def test_account_sync_rejects_unknown_protocol_and_preserves_last_good_snapshot(tmp_path):
    from src.api.dependencies import OAuthAccountSyncService
    from src.auth_drivers.codex_account_usage import CodexAccountUsageAdapter
    from src.auth_drivers.oauth_status import OAuthObservationStore

    observations = OAuthObservationStore(tmp_path / "profile.db")
    original = _seed_snapshot(observations)
    executable, _, pid_path = _write_codex_fixture(
        tmp_path, unexpected_method="thread/started"
    )
    service = OAuthAccountSyncService(
        observation_store=observations,
        token_store=_TokenStore(_token_record()),
        adapter=CodexAccountUsageAdapter(executable=executable, timeout_seconds=2.0),
    )

    result = service.sync(
        credential_id="local:1", provider="openai", auth_mode="chatgpt_oauth"
    )
    assert result.sync_status == "failed"
    assert result.sync_error_code == "protocol_incompatible"
    assert result.snapshot == original
    assert observations.read_account_snapshot("local:1") == original
    _wait_for_process_exit(int(pid_path.read_text()))


def test_account_sync_requires_allowlisted_codex_version_and_cleans_child(tmp_path):
    from src.auth_drivers.codex_account_usage import (
        CodexAccountUsageAdapter,
        CodexAccountUsageError,
    )

    wrong_root = tmp_path / "wrong"
    wrong_root.mkdir()
    executable, _, wrong_pid = _write_codex_fixture(wrong_root, version="0.148.0")
    with pytest.raises(CodexAccountUsageError) as caught:
        CodexAccountUsageAdapter(
            executable=executable, timeout_seconds=2.0
        ).read_account_usage(
            credential_id="local:1",
            record=_token_record(),
            observed_at=_OBSERVED_AT,
        )
    assert caught.value.code == "version_incompatible"
    assert not wrong_pid.exists()

    good_root = tmp_path / "good"
    good_root.mkdir()
    executable, _, good_pid = _write_codex_fixture(good_root)
    CodexAccountUsageAdapter(executable=executable, timeout_seconds=2.0).read_account_usage(
        credential_id="local:1", record=_token_record(), observed_at=_OBSERVED_AT
    )
    _wait_for_process_exit(int(good_pid.read_text()))

    hang_root = tmp_path / "hang"
    hang_root.mkdir()
    executable, _, hang_pid = _write_codex_fixture(
        hang_root, hang_method="account/rateLimits/read"
    )
    with pytest.raises(CodexAccountUsageError) as caught:
        CodexAccountUsageAdapter(
            executable=executable, timeout_seconds=0.2
        ).read_account_usage(
            credential_id="local:1",
            record=_token_record(),
            observed_at=_OBSERVED_AT,
        )
    assert caught.value.code == "timeout"
    _wait_for_process_exit(int(hang_pid.read_text()))


def test_cached_account_status_is_credential_bound_and_missing_is_unknown(tmp_path):
    from src.auth_drivers.oauth_status import OAuthObservationStore, cached_account_usage

    missing_path = tmp_path / "missing" / "profile.db"
    missing = OAuthObservationStore(missing_path)
    unknown = cached_account_usage("local:1", missing)
    assert unknown.model_dump() == {
        "credential_id": "local:1",
        "snapshot": None,
        "sync_status": "not_requested",
        "sync_error_code": None,
    }
    assert not missing_path.parent.exists()

    observations = OAuthObservationStore(tmp_path / "profile.db")
    seeded = _seed_snapshot(observations, credential_id="local:1")
    assert cached_account_usage("local:1", observations).snapshot == seeded
    assert cached_account_usage("local:2", observations).snapshot is None
    replacement = _seed_snapshot(
        observations,
        credential_id="local:1",
        observed_at="2026-08-08T12:05:00+00:00",
    )
    assert replacement.observed_at == "2026-08-08T12:05:00+00:00"
    with sqlite3.connect(observations.db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM oauth_account_snapshot").fetchone()[0] == 1


def test_account_routes_split_inventory_cached_read_and_mutating_sync(tmp_path, monkeypatch):
    import fastapi.routing
    import httpx
    from fastapi import FastAPI

    import src.api.routes.config_routes as routes
    from src.api.dependencies import OAuthAccountSyncService
    from src.auth_drivers.oauth_status import (
        OAuthAccountSyncView,
        OAuthObservationStore,
    )
    from src.model_credentials import CredentialStore

    credential_store = CredentialStore(tmp_path / "profile.db")
    row = credential_store.add_oauth_credential(
        provider="openai",
        auth_mode="chatgpt_oauth",
        alias="ChatGPT Plus",
    )
    credential_id = f"local:{row.id}"
    token_store = _TokenStore(_token_record())
    observations = OAuthObservationStore(credential_store.db_path)
    seeded = _seed_snapshot(observations, credential_id=credential_id)

    class SyncService:
        def __init__(self):
            self.calls = []

        def sync(self, *, credential_id, provider, auth_mode):
            self.calls.append((credential_id, provider, auth_mode))
            return OAuthAccountSyncView(
                credential_id=credential_id,
                snapshot=seeded,
                sync_status="succeeded",
            )

    sync_service = SyncService()
    unsupported_tokens = _TokenStore(_token_record())

    class BombAdapter:
        def read_account_usage(self, **_kwargs):
            pytest.fail("unsupported auth mode launched the account adapter")

    unsupported = OAuthAccountSyncService(
        observation_store=observations,
        token_store=unsupported_tokens,
        adapter=BombAdapter(),
    ).sync(
        credential_id="local:2",
        provider="anthropic",
        auth_mode="claude_code_oauth",
    )
    assert unsupported.sync_status == "unsupported"
    assert unsupported.sync_error_code == "unsupported_auth_mode"
    assert unsupported_tokens.loads == 0
    gates = []
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_credential_store] = lambda: credential_store
    app.dependency_overrides[routes.get_oauth_token_store] = lambda: token_store
    app.dependency_overrides[routes.get_oauth_observation_store] = lambda: observations
    app.dependency_overrides[routes.get_oauth_account_sync_service] = lambda: sync_service

    async def run_inline(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(fastapi.routing, "run_in_threadpool", run_inline)
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda action, detail: gates.append((action, detail)),
    )

    async def exercise():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            inventory = await client.get("/config/credentials")
            cached = await client.get(
                f"/config/credentials/{credential_id}/account-usage"
            )
            synced = await client.post(
                f"/config/credentials/{credential_id}/account-usage/sync"
            )
        return inventory, cached, synced

    inventory, cached, synced = asyncio.run(exercise())
    assert inventory.status_code == 200
    assert cached.status_code == 200
    assert cached.json()["sync_status"] == "not_requested"
    assert sync_service.calls == [(credential_id, "openai", "chatgpt_oauth")]
    assert synced.status_code == 200
    assert synced.json()["sync_status"] == "succeeded"
    assert gates == [
        (
            "oauth_account_usage_sync",
            {"credential_id": credential_id, "provider": "openai"},
        )
    ]


def test_account_sync_is_singleflight_per_credential(tmp_path):
    from src.api.dependencies import OAuthAccountSyncService
    from src.auth_drivers.chatgpt_oauth_login import oauth_credential_lock
    from src.auth_drivers.oauth_status import OAuthObservationStore

    class BlockingAdapter:
        def __init__(self):
            import threading

            self.calls = 0
            self.started = threading.Event()
            self.release = threading.Event()

        def read_account_usage(self, *, credential_id, record, observed_at=None):
            self.calls += 1
            self.started.set()
            assert self.release.wait(timeout=2.0)
            return _snapshot_input(credential_id=credential_id)

    observations = OAuthObservationStore(tmp_path / "profile.db")
    token_store = _TokenStore(_token_record())
    adapter = BlockingAdapter()
    service = OAuthAccountSyncService(
        observation_store=observations,
        token_store=token_store,
        adapter=adapter,
    )

    def sync():
        return service.sync(
            credential_id="local:1", provider="openai", auth_mode="chatgpt_oauth"
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(sync)
        assert adapter.started.wait(timeout=2.0)
        second = pool.submit(sync)
        time.sleep(0.05)
        adapter.release.set()
        results = [first.result(timeout=2.0), second.result(timeout=2.0)]

    assert adapter.calls == 1
    assert [result.sync_status for result in results] == ["succeeded", "succeeded"]
    assert results[0] == results[1]

    stale_adapter = BlockingAdapter()
    stale_service = OAuthAccountSyncService(
        observation_store=observations,
        token_store=token_store,
        adapter=stale_adapter,
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(
            stale_service.sync,
            credential_id="local:1",
            provider="openai",
            auth_mode="chatgpt_oauth",
        )
        assert stale_adapter.started.wait(timeout=2.0)
        with oauth_credential_lock("local:1"):
            token_store.record = None
            observations.delete_credential_observations("local:1")
        stale_adapter.release.set()
        stale = pending.result(timeout=2.0)

    assert stale.sync_status == "failed"
    assert stale.sync_error_code == "credential_changed_during_sync"
    assert stale.snapshot is None
    assert observations.read_account_snapshot("local:1") is None


def test_listing_credentials_never_refreshes_or_contacts_provider(tmp_path, monkeypatch):
    import src.api.routes.config_routes as routes
    from src.auth_drivers.codex_account_usage import CodexAccountUsageAdapter
    from src.auth_drivers.oauth_status import OAuthObservationStore
    from src.model_credentials import CredentialStore

    store = CredentialStore(tmp_path / "profile.db")
    row = store.add_oauth_credential(
        provider="openai", auth_mode="chatgpt_oauth", alias="ChatGPT Plus"
    )
    credential_id = f"local:{row.id}"
    token_store = _TokenStore(_token_record())
    monkeypatch.setattr(
        CodexAccountUsageAdapter,
        "read_account_usage",
        lambda *_args, **_kwargs: pytest.fail("credential listing contacted app-server"),
    )

    result = routes.list_credentials(
        store=store,
        token_store=token_store,
        observation_store=OAuthObservationStore(store.db_path),
    )
    rows = result["credentials"]["openai"]
    assert any(row["id"] == credential_id for row in rows)
    assert token_store.loads == 1
