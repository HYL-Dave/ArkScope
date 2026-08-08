from __future__ import annotations

import json
import multiprocessing
import os
import stat
import time
from datetime import datetime, timezone
from pathlib import Path


_CREDENTIAL_ID = "local:1"
_PROVIDER = "openai"
_AUTH_MODE = "chatgpt_oauth"


def _write_json(path: str | Path, payload: dict) -> None:
    Path(path).write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _read_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _wait_for(predicate, *, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise TimeoutError("cross-process test synchronization timed out")
        time.sleep(0.01)


def _join_processes(processes, *, timeout: float = 12.0) -> None:
    deadline = time.monotonic() + timeout
    for process in processes:
        process.join(max(0.0, deadline - time.monotonic()))
    alive = [process for process in processes if process.is_alive()]
    for process in alive:
        process.terminate()
    for process in alive:
        process.join(2.0)
    assert not alive, "spawned OAuth lock worker exceeded its bounded join"
    assert [process.exitcode for process in processes] == [0] * len(processes)


def _configure_worker(lock_dir: str, profile_db: str) -> None:
    os.environ["ARKSCOPE_LOCK_DIR"] = lock_dir
    os.environ["ARKSCOPE_PROFILE_DB"] = profile_db


def _rotating_refresh_worker(root_text: str, worker_name: str) -> None:
    root = Path(root_text)
    _configure_worker(str(root / "lock-root"), str(root / "profile_state.db"))

    from src.auth_drivers.chatgpt_oauth_login import (
        ChatGPTOAuthLoginError,
        refresh_if_needed,
    )
    from src.auth_drivers.token_store import PlaintextTokenStore

    base_store = PlaintextTokenStore(root / "tokens.json")

    class CoordinatedTokenStore:
        def load(self, **kwargs):
            record = base_store.load(**kwargs)
            if record is not None and record.refresh_token == "rotating-old":
                (root / f"loaded-{worker_name}").write_text("1", encoding="ascii")
                deadline = time.monotonic() + 0.45
                while len(tuple(root.glob("loaded-*"))) < 2 and time.monotonic() < deadline:
                    time.sleep(0.01)
            return record

        def save(self, **kwargs):
            return base_store.save(**kwargs)

    def rotate_once(*, refresh_token: str) -> dict:
        (root / f"grant-attempt-{worker_name}").write_text("1", encoding="ascii")
        assert refresh_token == "rotating-old"
        try:
            fd = os.open(root / "grant-consumed", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise ChatGPTOAuthLoginError("rotating grant already consumed", status_code=400) from None
        else:
            os.close(fd)
        return {"access_token": "test-access-new", "refresh_token": "rotating-new"}

    (root / f"worker-ready-{worker_name}").write_text("1", encoding="ascii")
    _wait_for(lambda: (root / "start-rotating-refresh").exists())
    try:
        record = refresh_if_needed(
            credential_id=_CREDENTIAL_ID,
            token_store=CoordinatedTokenStore(),
            now=datetime(2026, 8, 8, tzinfo=timezone.utc),
            refresh=rotate_once,
        )
    except Exception as exc:  # noqa: BLE001 - result is the assertion input
        _write_json(
            root / f"result-{worker_name}.json",
            {"status": "error", "type": type(exc).__name__, "reauth": getattr(exc, "reauth_required", None)},
        )
    else:
        _write_json(
            root / f"result-{worker_name}.json",
            {"status": "ok", "fresh": record.refresh_token == "rotating-new"},
        )


def _blocked_refresh_worker(root_text: str) -> None:
    root = Path(root_text)
    _configure_worker(str(root / "lock-root"), str(root / "profile_state.db"))

    from src.auth_drivers.chatgpt_oauth_login import refresh_if_needed
    from src.auth_drivers.token_store import PlaintextTokenStore

    store = PlaintextTokenStore(root / "tokens.json")

    def delayed_refresh(*, refresh_token: str) -> dict:
        assert refresh_token == "delete-race-old"
        (root / "refresh-entered").write_text("1", encoding="ascii")
        _wait_for(lambda: (root / "release-refresh").exists())
        return {"access_token": "test-access-after-delete", "refresh_token": "delete-race-new"}

    try:
        refresh_if_needed(
            credential_id=_CREDENTIAL_ID,
            token_store=store,
            force=True,
            refresh=delayed_refresh,
        )
    except Exception as exc:  # noqa: BLE001
        _write_json(root / "refresh-result.json", {"status": "error", "type": type(exc).__name__})
    else:
        _write_json(root / "refresh-result.json", {"status": "ok"})


def _delete_worker(root_text: str) -> None:
    root = Path(root_text)
    _configure_worker(str(root / "lock-root"), str(root / "profile_state.db"))

    from src.api.routes.config_routes import delete_credential
    from src.auth_drivers.token_store import PlaintextTokenStore
    from src.model_credentials import CredentialStore

    base_store = PlaintextTokenStore(root / "tokens.json")

    class ObservedTokenStore:
        def load(self, **kwargs):
            return base_store.load(**kwargs)

        def delete(self, **kwargs):
            removed = base_store.delete(**kwargs)
            (root / "delete-token-finished").write_text("1", encoding="ascii")
            return removed

        def save(self, **kwargs):
            return base_store.save(**kwargs)

    (root / "delete-ready").write_text("1", encoding="ascii")
    _wait_for(lambda: (root / "delete-go").exists())
    try:
        result = delete_credential(
            _CREDENTIAL_ID,
            store=CredentialStore(root / "profile_state.db"),
            token_store=ObservedTokenStore(),
        )
    except Exception as exc:  # noqa: BLE001
        _write_json(root / "delete-result.json", {"status": "error", "type": type(exc).__name__})
    else:
        _write_json(root / "delete-result.json", {"status": "ok", "deleted": result["deleted"]})


def _lock_holder_worker(root_text: str, release_name: str, result_name: str) -> None:
    root = Path(root_text)
    _configure_worker(str(root / "lock-root"), str(root / "profile_state.db"))
    from src.auth_drivers.chatgpt_oauth_login import oauth_credential_lock

    try:
        with oauth_credential_lock(_CREDENTIAL_ID):
            (root / "holder-acquired").write_text("1", encoding="ascii")
            _wait_for(lambda: (root / release_name).exists())
    except Exception as exc:  # noqa: BLE001
        _write_json(root / result_name, {"status": "error", "type": type(exc).__name__})
    else:
        _write_json(root / result_name, {"status": "ok"})


def _lock_contender_worker(root_text: str, result_name: str) -> None:
    root = Path(root_text)
    _configure_worker(str(root / "lock-root"), str(root / "profile_state.db"))
    from src.auth_drivers.chatgpt_oauth_login import oauth_credential_lock

    entered = False
    try:
        with oauth_credential_lock(_CREDENTIAL_ID, timeout=0.15):
            entered = True
    except Exception as exc:  # noqa: BLE001
        _write_json(
            root / result_name,
            {
                "status": "error",
                "type": type(exc).__name__,
                "error_code": getattr(exc, "error_code", None),
                "reauth": getattr(exc, "reauth_required", None),
                "entered": entered,
            },
        )
    else:
        _write_json(root / result_name, {"status": "entered", "entered": entered})


def _fds_for_path(path: Path) -> int:
    count = 0
    for entry in Path("/proc/self/fd").iterdir():
        try:
            if entry.resolve() == path.resolve():
                count += 1
        except FileNotFoundError:
            continue
    return count


def _release_probe_a(root_text: str) -> None:
    root = Path(root_text)
    _configure_worker(str(root / "lock-root"), str(root / "profile_state.db"))
    from src.auth_drivers.chatgpt_oauth_login import oauth_credential_lock

    with oauth_credential_lock(_CREDENTIAL_ID):
        (root / "probe-a-held").write_text("1", encoding="ascii")
        _wait_for(lambda: (root / "probe-release-overlap").exists())

    lock_files = tuple((root / "lock-root" / "oauth_credentials").glob("*.lock"))
    lock_path = lock_files[0] if len(lock_files) == 1 else root / "missing.lock"
    normal_fds = _fds_for_path(lock_path)
    (root / "probe-a-normal-released").write_text("1", encoding="ascii")
    _wait_for(lambda: (root / "probe-b-normal-acquired").exists())

    try:
        with oauth_credential_lock(_CREDENTIAL_ID):
            raise RuntimeError("test sentinel")
    except RuntimeError:
        pass
    failure_fds = _fds_for_path(lock_path)
    (root / "probe-a-failure-released").write_text("1", encoding="ascii")
    _wait_for(lambda: (root / "probe-b-failure-acquired").exists())
    _write_json(
        root / "probe-a-result.json",
        {"normal_fds": normal_fds, "failure_fds": failure_fds, "lock_files": len(lock_files)},
    )


def _release_probe_b(root_text: str) -> None:
    root = Path(root_text)
    _configure_worker(str(root / "lock-root"), str(root / "profile_state.db"))
    from src.auth_drivers.chatgpt_oauth_login import oauth_credential_lock

    _wait_for(lambda: (root / "probe-a-held").exists())
    try:
        with oauth_credential_lock(_CREDENTIAL_ID, timeout=0.15):
            overlap = "entered"
    except Exception as exc:  # noqa: BLE001
        overlap = getattr(exc, "error_code", type(exc).__name__)
    _write_json(root / "probe-b-overlap.json", {"outcome": overlap})

    _wait_for(lambda: (root / "probe-a-normal-released").exists())
    with oauth_credential_lock(_CREDENTIAL_ID):
        (root / "probe-b-normal-acquired").write_text("1", encoding="ascii")
    _wait_for(lambda: (root / "probe-a-failure-released").exists())
    with oauth_credential_lock(_CREDENTIAL_ID):
        (root / "probe-b-failure-acquired").write_text("1", encoding="ascii")


def _spawn(target, *args):
    return multiprocessing.get_context("spawn").Process(target=target, args=args)


def _seed_expired_token(path: Path, *, refresh_token: str) -> None:
    from src.auth_drivers.token_store import PlaintextTokenStore, StoredTokenRecord

    PlaintextTokenStore(path).save(
        provider=_PROVIDER,
        auth_mode=_AUTH_MODE,
        credential_id=_CREDENTIAL_ID,
        record=StoredTokenRecord(
            access_token="test-access-old",
            refresh_token=refresh_token,
            expires_at="2000-01-01T00:00:00+00:00",
        ),
    )


def test_two_processes_consume_one_rotating_refresh_token(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "lock-root"))
    _seed_expired_token(tmp_path / "tokens.json", refresh_token="rotating-old")
    processes = [
        _spawn(_rotating_refresh_worker, str(tmp_path), "a"),
        _spawn(_rotating_refresh_worker, str(tmp_path), "b"),
    ]
    for process in processes:
        process.start()
    _wait_for(lambda: len(tuple(tmp_path.glob("worker-ready-*"))) == 2)
    (tmp_path / "start-rotating-refresh").write_text("1", encoding="ascii")
    _join_processes(processes)

    results = [_read_json(tmp_path / f"result-{name}.json") for name in ("a", "b")]
    assert results == [{"fresh": True, "status": "ok"}] * 2
    assert len(tuple(tmp_path.glob("grant-attempt-*"))) == 1


def test_cross_process_delete_cannot_be_followed_by_refresh_resurrection(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "lock-root"))
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    from src.auth_drivers.token_store import PlaintextTokenStore
    from src.model_credentials import CredentialStore

    credential_store = CredentialStore(tmp_path / "profile_state.db")
    credential = credential_store.add_oauth_credential(
        provider=_PROVIDER,
        auth_mode=_AUTH_MODE,
        alias="test subscription",
        make_active=True,
    )
    assert f"local:{credential.id}" == _CREDENTIAL_ID
    _seed_expired_token(tmp_path / "tokens.json", refresh_token="delete-race-old")

    refresh_process = _spawn(_blocked_refresh_worker, str(tmp_path))
    refresh_process.start()
    _wait_for(lambda: (tmp_path / "refresh-entered").exists())
    delete_process = _spawn(_delete_worker, str(tmp_path))
    delete_process.start()
    _wait_for(lambda: (tmp_path / "delete-ready").exists())
    (tmp_path / "delete-go").write_text("1", encoding="ascii")
    try:
        _wait_for(lambda: (tmp_path / "delete-token-finished").exists(), timeout=0.75)
    except TimeoutError:
        pass
    (tmp_path / "release-refresh").write_text("1", encoding="ascii")
    _join_processes([refresh_process, delete_process])

    assert _read_json(tmp_path / "refresh-result.json") == {"status": "ok"}
    assert _read_json(tmp_path / "delete-result.json") == {"deleted": True, "status": "ok"}
    assert CredentialStore(tmp_path / "profile_state.db").get(_CREDENTIAL_ID) is None
    assert PlaintextTokenStore(tmp_path / "tokens.json").load(
        provider=_PROVIDER, auth_mode=_AUTH_MODE, credential_id=_CREDENTIAL_ID
    ) is None


def test_cross_process_lock_timeout_is_retryable_and_never_runs_unlocked(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "lock-root"))
    holder = _spawn(_lock_holder_worker, str(tmp_path), "release-holder", "holder-result.json")
    holder.start()
    _wait_for(lambda: (tmp_path / "holder-acquired").exists())
    contender = _spawn(_lock_contender_worker, str(tmp_path), "contender-result.json")
    contender.start()
    _join_processes([contender])
    (tmp_path / "release-holder").write_text("1", encoding="ascii")
    _join_processes([holder])

    assert _read_json(tmp_path / "contender-result.json") == {
        "entered": False,
        "error_code": "oauth_lock_busy",
        "reauth": False,
        "status": "error",
        "type": "ChatGPTOAuthLoginError",
    }
    assert _read_json(tmp_path / "holder-result.json") == {"status": "ok"}


def test_cross_process_lock_releases_file_descriptors_on_success_and_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "lock-root"))
    process_a = _spawn(_release_probe_a, str(tmp_path))
    process_b = _spawn(_release_probe_b, str(tmp_path))
    process_a.start()
    process_b.start()
    _wait_for(lambda: (tmp_path / "probe-b-overlap.json").exists())
    (tmp_path / "probe-release-overlap").write_text("1", encoding="ascii")
    _join_processes([process_a, process_b])

    assert _read_json(tmp_path / "probe-b-overlap.json") == {"outcome": "oauth_lock_busy"}
    assert _read_json(tmp_path / "probe-a-result.json") == {
        "failure_fds": 0,
        "lock_files": 1,
        "normal_fds": 0,
    }
    lock_root = tmp_path / "lock-root" / "oauth_credentials"
    lock_files = tuple(lock_root.glob("*.lock"))
    assert len(lock_files) == 1
    assert _CREDENTIAL_ID not in lock_files[0].name
    assert stat.S_IMODE(lock_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(lock_files[0].stat().st_mode) == 0o600
