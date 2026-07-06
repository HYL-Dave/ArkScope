"""SA extension/native-host health surface.

This is a read-only diagnostic service: it reports where the browser extension
chain is broken without writing synthetic rows into the SA capture store.
"""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from src.sa_capture_store import connect as connect_sa_capture
from src.sa_capture_store import resolve_sa_db_path
from src.service.job_runs_store import get_job_runs_store

HOST_ID = "com.mindfulrl.sa_alpha_picks"


@dataclass(frozen=True)
class SAExtensionHealthPaths:
    project_root: Path
    config_path: Path
    firefox_manifest_path: Path
    chrome_manifest_path: Path
    launcher_path: Path
    sa_db_path: Path
    host_script: Path


def default_paths() -> SAExtensionHealthPaths:
    root = Path(__file__).resolve().parents[2]
    home = Path.home()
    config_path = Path(
        os.environ.get(
            "ARKSCOPE_SA_NATIVE_HOST_CONFIG",
            str(home / ".config" / "arkscope" / "sa_native_host.json"),
        )
    )
    return SAExtensionHealthPaths(
        project_root=root,
        config_path=config_path,
        firefox_manifest_path=home / ".mozilla" / "native-messaging-hosts" / f"{HOST_ID}.json",
        chrome_manifest_path=home / ".config" / "google-chrome" / "NativeMessagingHosts" / f"{HOST_ID}.json",
        launcher_path=home / ".local" / "share" / "arkscope" / "native-hosts" / "sa_alpha_picks_host.sh",
        sa_db_path=Path(resolve_sa_db_path()),
        host_script=root / "src" / "sa_native_host.py",
    )


def _seg(key: str, state: str, detail: str) -> dict[str, str]:
    return {"key": key, "state": state, "detail": detail}


def _load_json(path: Path) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _current_api_base(env: Mapping[str, str]) -> str:
    if env.get("ARKSCOPE_API_BASE_URL"):
        return str(env["ARKSCOPE_API_BASE_URL"]).rstrip("/")
    host = env.get("ARKSCOPE_API_HOST", "127.0.0.1")
    port = env.get("ARKSCOPE_API_PORT", "8420")
    return f"http://{host}:{port}"


def _config_segment(paths: SAExtensionHealthPaths) -> tuple[dict[str, str], dict[str, Any]]:
    if not paths.config_path.exists():
        return _seg("config", "fail", f"設定檔不存在: {paths.config_path}"), {}
    cfg, error = _load_json(paths.config_path)
    if cfg is None:
        return _seg("config", "fail", f"設定檔無法解析: {error}"), {}

    problems: list[str] = []
    project_root = Path(str(cfg.get("project_root") or paths.project_root))
    python_path = Path(str(cfg.get("python_path") or ""))
    host_script = Path(str(cfg.get("host_script") or paths.host_script))
    if not project_root.exists():
        problems.append("project_root 不存在")
    if not python_path.exists() or not os.access(python_path, os.X_OK):
        problems.append("python_path 不可執行")
    if not host_script.exists():
        problems.append("host_script 不存在")
    elif not _is_relative_to(host_script, project_root):
        problems.append("host_script 不在 project_root 之下")
    if problems:
        return _seg("config", "fail", "；".join(problems)), cfg
    return _seg("config", "ok", "native host 設定檔有效"), cfg


def _manifest_segment(paths: SAExtensionHealthPaths) -> dict[str, str]:
    found = []
    mismatches = []
    for browser, path in (
        ("Firefox", paths.firefox_manifest_path),
        ("Chrome", paths.chrome_manifest_path),
    ):
        if not path.exists():
            continue
        payload, error = _load_json(path)
        if payload is None:
            mismatches.append(f"{browser} manifest 無法解析: {error}")
            continue
        found.append(browser)
        if Path(str(payload.get("path") or "")) != paths.launcher_path:
            mismatches.append(f"{browser} manifest path 不指向 launcher")
    if not found:
        return _seg("manifests", "fail", "未找到 Firefox/Chrome native messaging manifest")
    if mismatches:
        return _seg("manifests", "fail", "；".join(mismatches))
    return _seg("manifests", "ok", " / ".join(found) + " manifest 指向 stable launcher")


def _launcher_segment(paths: SAExtensionHealthPaths) -> dict[str, str]:
    if not paths.launcher_path.exists():
        return _seg("launcher", "fail", f"launcher 不存在: {paths.launcher_path}")
    if not os.access(paths.launcher_path, os.X_OK):
        return _seg("launcher", "fail", "launcher 不可執行")
    return _seg("launcher", "ok", "stable launcher 可執行")


def _host_ping_segment(paths: SAExtensionHealthPaths, spawn_ping: Callable[[SAExtensionHealthPaths], dict[str, Any]]) -> dict[str, str]:
    try:
        reply = spawn_ping(paths)
    except Exception as exc:
        return _seg("host_ping", "fail", f"主機測試失敗: {exc}")
    if reply.get("status") != "ok":
        return _seg("host_ping", "fail", f"主機回覆非 ok: {reply.get('status')}")
    target = reply.get("telemetry_target") or "未知 target"
    source = reply.get("telemetry_source") or "未知來源"
    return _seg("host_ping", "ok", f"native host ping ok；telemetry={target} ({source})")


def _telemetry_binding_segment(cfg: Mapping[str, Any], env: Mapping[str, str]) -> dict[str, str]:
    cfg_base = str(cfg.get("api_base") or "").rstrip("/")
    cfg_has_token = bool(cfg.get("api_token"))
    if not cfg_base:
        return _seg("telemetry_binding", "warn", "config 尚未綁定本次 sidecar")
    current_base = _current_api_base(env)
    current_has_token = bool(env.get("ARKSCOPE_API_TOKEN"))
    if cfg_base == current_base and cfg_has_token == current_has_token:
        return _seg("telemetry_binding", "ok", "config 綁定本次 sidecar")
    return _seg("telemetry_binding", "fail", "config 與本次 sidecar API base/token 狀態不一致")


def _row_ts(row: Mapping[str, Any]) -> str:
    return str(row.get("finished_at") or row.get("started_at") or row.get("updated_at") or "")


def _telemetry_last_segment(job_store: Any) -> dict[str, str]:
    try:
        rows = job_store.list_runs(trigger_source="extension", limit=200)
    except Exception as exc:
        return _seg("telemetry_last", "fail", f"讀取 extension telemetry 失敗: {exc}")
    rows = [row for row in rows if row.get("status") in {"succeeded", "failed"}]
    if not rows:
        return _seg("telemetry_last", "warn", "尚未有第一次 extension telemetry")
    latest = max(rows, key=_row_ts)
    return _seg(
        "telemetry_last",
        "ok",
        f"{latest.get('job_name')} {latest.get('status')} @ {_row_ts(latest)}",
    )


def _capture_readback_segment(paths: SAExtensionHealthPaths) -> dict[str, str]:
    try:
        with connect_sa_capture(str(paths.sa_db_path), read_only=True) as conn:
            refresh = conn.execute("SELECT MAX(last_success_at) FROM sa_refresh_meta").fetchone()[0]
            articles = conn.execute("SELECT MAX(fetched_at) FROM sa_articles").fetchone()[0]
            market_news = conn.execute("SELECT MAX(fetched_at) FROM sa_market_news").fetchone()[0]
    except Exception as exc:
        return _seg("capture_readback", "fail", f"讀取 sa_capture.db 失敗: {exc}")
    latest = max([v for v in (refresh, articles, market_news) if v], default=None)
    if not latest:
        return _seg("capture_readback", "warn", "尚未有第一次擷取")
    return _seg("capture_readback", "ok", f"本地 SA DB 可讀；latest={latest}")


def collect_sa_extension_health(
    *,
    paths: Optional[SAExtensionHealthPaths] = None,
    env: Optional[Mapping[str, str]] = None,
    dal: Any = None,
    job_store: Any = None,
    spawn_ping: Callable[[SAExtensionHealthPaths], dict[str, Any]] = None,
) -> dict[str, Any]:
    paths = paths or default_paths()
    env = env or os.environ
    spawn_ping = spawn_ping or run_host_ping
    if job_store is None:
        job_store = get_job_runs_store(dal)

    config_segment, cfg = _config_segment(paths)
    segments = [
        config_segment,
        _manifest_segment(paths),
        _launcher_segment(paths),
        _host_ping_segment(paths, spawn_ping),
        _telemetry_binding_segment(cfg, env),
        _telemetry_last_segment(job_store),
        _capture_readback_segment(paths),
    ]
    return {
        "ok": all(segment["state"] != "fail" for segment in segments),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "segments": segments,
    }


def run_host_ping(paths: SAExtensionHealthPaths, *, timeout_seconds: int = 15) -> dict[str, Any]:
    msg = json.dumps({"action": "ping"}).encode("utf-8")
    wire = struct.pack("=I", len(msg)) + msg
    env = dict(os.environ)
    # Simulate the browser environment: a real browser-spawned host never sees
    # the Electron-injected ARKSCOPE_API_* vars that live in the sidecar's own
    # env, so the probe must not leak them or it reports source=env for a host
    # that would actually resolve source=config.
    for key in (
        "ARKSCOPE_API_BASE_URL",
        "ARKSCOPE_API_HOST",
        "ARKSCOPE_API_PORT",
        "ARKSCOPE_API_TOKEN",
    ):
        env.pop(key, None)
    env["ARKSCOPE_SA_NATIVE_HOST_CONFIG"] = str(paths.config_path)
    proc = subprocess.run(
        [sys.executable, str(paths.host_script)],
        input=wire,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(paths.project_root),
        env=env,
        timeout=timeout_seconds,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace")[-500:])
    if len(proc.stdout) < 4:
        raise RuntimeError("native host returned no framed response")
    length = struct.unpack("=I", proc.stdout[:4])[0]
    payload = proc.stdout[4:4 + length]
    return json.loads(payload.decode("utf-8"))
