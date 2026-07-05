"""
Data-provider connection settings + API keys, app-managed (the credentials slice).

The user directive (2026-06-11): the app manages each data provider's API key and
connection settings — IB Gateway's host/port is FILLED here (the Gateway itself
runs wherever the user starts it; the app only stores where to connect), key-less
key-free sources (SEC EDGAR) are available by default, and each provider gets a
connection test.

Storage: the local gitignored SQLite (same DB as profile state / LLM credentials),
table ``data_provider_config`` — plain (provider, field) → value. Secrets never
leave the machine; reads return MASKED values only.

Env bridge (why this is now cheap): the sidecar is the parent of every collector
subprocess (the app-owned scheduler spawns them), so injecting a stored value into
``os.environ`` makes it visible to ALL call sites — in-process ``os.getenv`` users
AND child processes — with no per-client plumbing. Effective precedence per var:

    real environment variable  >  app-stored value  >  config/.env

"Real" = present in the environment before ``ensure_env_loaded()`` and not loaded
from the file — the operator escape hatch. An app value OVERWRITES a file-loaded
value (entering a key in Settings must actually take effect); clearing the app
value falls back to config/.env via ``reload_var_from_file``. ``app_applied_keys``
records what the app injected so provider-health can report ``app`` as a key's
effective source.
"""

from __future__ import annotations

import logging
import os
import socket
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS data_provider_config (
    provider   TEXT NOT NULL,
    field      TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (provider, field)
);

CREATE TABLE IF NOT EXISTS profile_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class FieldDef:
    field: str
    env_var: str
    secret: bool
    label: str
    default_value: str | None = None
    defaulted: bool = False
    optional: bool = False
    guarded: bool = False
    guard_reason: str | None = None
    import_aliases: tuple[str, ...] = ()


# What each provider can store here. SEC EDGAR has no key but does have an
# optional app-managed User-Agent field; Seeking Alpha is the extension capture
# path (nothing to configure here).
PROVIDER_FIELDS: Dict[str, List[FieldDef]] = {
    "polygon": [FieldDef("api_key", "POLYGON_API_KEY", True, "API key")],
    "finnhub": [FieldDef("api_key", "FINNHUB_API_KEY", True, "API key")],
    "fred": [FieldDef("api_key", "FRED_API_KEY", True, "API key")],
    "financial_datasets": [
        FieldDef("api_key", "FINANCIAL_DATASETS_API_KEY", True, "API key")],
    "ibkr": [
        FieldDef("host", "IBKR_HOST", False, "Gateway host"),
        FieldDef("port", "IBKR_PORT", False, "Gateway port"),
        # ibkr_source.py reads IBKR_CLIENT_ID (default 1); was env-only. NOTE config/.env
        # historically used the name IBKR_CLIENT (mismatch the code never read) — setting it
        # here injects the correct IBKR_CLIENT_ID via the env bridge.
        FieldDef(
            "client_id",
            "IBKR_CLIENT_ID",
            False,
            "Client ID",
            default_value="1",
            defaulted=True,
            guarded=True,
            guard_reason=(
                "Changing IBKR client_id can disturb active Gateway sessions; this is the "
                "base id — all domains derive from it (options=+10, prices=+20, news=+30, "
                "iv=+40; see data_sources/ibkr_client_id.py)."
            ),
        ),
    ],
    "sec_edgar": [
        FieldDef(
            "user_agent",
            "ARKSCOPE_SEC_USER_AGENT",
            False,
            "聯絡 Email",
            optional=True,
            import_aliases=("SEC_CONTACT_EMAIL", "SEC_USER_AGENT"),
        )
    ],
    "seeking_alpha": [],
}

_FIELD_BY_KEY: Dict[tuple, FieldDef] = {
    (p, f.field): f for p, defs in PROVIDER_FIELDS.items() for f in defs
}


def provider_default_available(provider: str) -> bool:
    defs = PROVIDER_FIELDS.get(provider)
    if defs is None:
        return False
    return provider != "seeking_alpha" and all(f.optional for f in defs)


PROVIDER_ENV_FALLBACK_KEY = "provider_env_fallback"
ENV_PROVIDER_ENV_FALLBACK = "ARKSCOPE_PROVIDER_ENV_FALLBACK"
_TRUTHY = ("1", "true", "yes", "on")
_FALSY = ("0", "false", "no", "off")


def parse_provider_env_fallback(value: Any) -> Optional[bool]:
    text = str(value).strip().lower() if value is not None else ""
    if text in _TRUTHY:
        return True
    if text in _FALSY:
        return False
    return None


def provider_env_fallback_enabled(store: DataProviderConfigStore | None = None) -> bool:
    env_value = parse_provider_env_fallback(os.environ.get(ENV_PROVIDER_ENV_FALLBACK))
    if env_value is not None:
        return env_value
    if store is not None:
        try:
            profile_value = parse_provider_env_fallback(
                store.get_setting(PROVIDER_ENV_FALLBACK_KEY)
            )
            if profile_value is not None:
                return profile_value
        except Exception:  # noqa: BLE001 - fail strict on settings read failure
            logger.warning(
                "provider_env_fallback setting read failed; defaulting strict",
                exc_info=True,
            )
    return False


def provider_env_fallback_source(store: DataProviderConfigStore | None = None) -> str:
    if parse_provider_env_fallback(os.environ.get(ENV_PROVIDER_ENV_FALLBACK)) is not None:
        return "env"
    if store is not None:
        try:
            if parse_provider_env_fallback(
                store.get_setting(PROVIDER_ENV_FALLBACK_KEY)
            ) is not None:
                return "profile"
        except Exception:  # noqa: BLE001
            return "default"
    return "default"

# env-var names the APP injected this process (effective source = 'app')
_APP_APPLIED: set = set()


def mask_value(value: str, secret: bool) -> str:
    if not secret:
        return value
    if len(value) <= 10:
        return "••••"
    return f"{value[:4]}…{value[-4:]}"


def importable_env_vars(fdef: FieldDef) -> tuple[str, ...]:
    return (fdef.env_var, *fdef.import_aliases)


def normalize_provider_config_value(fdef: FieldDef, value: str) -> str:
    value = value.strip()
    if fdef.env_var == "ARKSCOPE_SEC_USER_AGENT" and "@" in value and not any(
        ch.isspace() for ch in value
    ):
        return value if value.startswith("ArkScope ") else f"ArkScope {value}"
    if fdef.env_var == "IBKR_CLIENT_ID":
        # Every domain id derives from this base (data_sources/ibkr_client_id.py); a
        # bad base would crash every IBKR connect long after the save. isdecimal (not
        # isdigit: '²'.isdigit() is True but int() rejects it) + int32 headroom for
        # the largest offset, canonicalized to ASCII (int('７')==7, '007'→'7').
        if not value.isdecimal():
            raise ValueError("IBKR client_id must be a non-negative integer")
        base = int(value)
        if base > 2**31 - 1 - 40:
            raise ValueError("IBKR client_id too large for a Gateway client id")
        return str(base)
    return value


def normalize_import_value(fdef: FieldDef, source_env_var: str, value: str) -> str:
    return normalize_provider_config_value(fdef, value)


def guarded_change_detail(provider: str, field: str, fdef: FieldDef) -> dict[str, str]:
    return {
        "code": "provider_config_change_guard",
        "status": "confirmation_required",
        "provider": provider,
        "field": field,
        "message": fdef.guard_reason or "Changing this provider setting requires confirmation.",
    }


class DataProviderConfigStore:
    """(provider, field) → value in the local state DB. Values returned by
    ``get_all`` are RAW — only the route layer masks; never log them."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = os.environ.get("ARKSCOPE_PROFILE_DB") or str(
                Path(__file__).resolve().parents[1] / "data" / "profile_state.db")
        self._db_path = str(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def get_all(self) -> Dict[str, Dict[str, str]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT provider, field, value FROM data_provider_config").fetchall()
        finally:
            conn.close()
        out: Dict[str, Dict[str, str]] = {}
        for provider, field, value in rows:
            out.setdefault(provider, {})[field] = value
        return out

    def set_field(self, provider: str, field: str, value: Optional[str]) -> None:
        """Set or clear (None/empty) one field. Unknown (provider, field) raises."""
        if (provider, field) not in _FIELD_BY_KEY:
            raise KeyError(f"unknown provider field {provider}.{field}")
        conn = self._connect()
        try:
            if value:
                conn.execute(
                    "INSERT INTO data_provider_config (provider, field, value, updated_at) "
                    "VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(provider, field) DO UPDATE SET "
                    "  value = excluded.value, updated_at = excluded.updated_at",
                    (provider, field, value,
                     datetime.now(timezone.utc).isoformat(timespec="seconds")),
                )
            else:
                conn.execute(
                    "DELETE FROM data_provider_config WHERE provider = ? AND field = ?",
                    (provider, field),
                )
            conn.commit()
        finally:
            conn.close()

    def get_setting(self, key: str) -> Optional[str]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT value FROM profile_settings WHERE key = ?", (key,)
            ).fetchone()
        finally:
            conn.close()
        return row[0] if row else None

    def set_setting(self, key: str, value: Optional[str]) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO profile_settings (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                "updated_at = excluded.updated_at",
                (key, value, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
            conn.commit()
        finally:
            conn.close()

    def seed_defaults(self) -> list[tuple[str, str]]:
        """Persist app-owned defaults so Settings can show their app authority."""
        seeded: list[tuple[str, str]] = []
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn = self._connect()
        try:
            for provider, defs in PROVIDER_FIELDS.items():
                for fdef in defs:
                    if fdef.default_value is None:
                        continue
                    before = conn.execute(
                        "SELECT 1 FROM data_provider_config WHERE provider = ? AND field = ?",
                        (provider, fdef.field),
                    ).fetchone()
                    conn.execute(
                        "INSERT OR IGNORE INTO data_provider_config "
                        "(provider, field, value, updated_at) VALUES (?, ?, ?, ?)",
                        (provider, fdef.field, fdef.default_value, now),
                    )
                    if before is None:
                        seeded.append((provider, fdef.field))
            conn.commit()
            return seeded
        finally:
            conn.close()


# --- env bridge -----------------------------------------------------------------

def apply_env(store: DataProviderConfigStore) -> frozenset:
    """Inject stored values into os.environ (precedence in the module docstring).
    Idempotent; call at sidecar startup and after every save."""
    from src.env_keys import ensure_env_loaded, keys_loaded_from_file

    store.seed_defaults()
    ensure_env_loaded()
    file_keys = keys_loaded_from_file()
    stored = store.get_all()
    for provider, fields in stored.items():
        for field, value in fields.items():
            fdef = _FIELD_BY_KEY.get((provider, field))
            if fdef is None or not value:
                continue
            var = fdef.env_var
            # a REAL env var (pre-existing, not file-loaded, not ours) wins
            if var in os.environ and var not in file_keys and var not in _APP_APPLIED:
                continue
            os.environ[var] = value
            _APP_APPLIED.add(var)
    return frozenset(_APP_APPLIED)


def unapply_env(env_var: str) -> None:
    """After clearing an app value: drop our injection and fall back to the
    config/.env value (or unset entirely)."""
    if env_var not in _APP_APPLIED:
        return
    _APP_APPLIED.discard(env_var)
    from src.env_keys import reload_var_from_file

    reload_var_from_file(env_var)


def app_applied_keys() -> frozenset:
    """Env-var names whose CURRENT process value came from the app store."""
    return frozenset(_APP_APPLIED)


def effective_source(env_var: str) -> str:
    """'app' | 'env' | 'config/.env' | 'missing' for one var, by the same
    bookkeeping provider-health uses."""
    from src.env_keys import keys_loaded_from_file

    if not os.getenv(env_var):
        return "missing"
    if env_var in _APP_APPLIED:
        return "app"
    if env_var in keys_loaded_from_file():
        return "config/.env"
    return "env"


# --- connection tests -------------------------------------------------------------

_TEST_TIMEOUT_S = 8


def _http_probe(url: str, *, headers: Optional[dict] = None,
                ok_statuses: tuple = (200,),
                auth_hint: str = "金鑰無效或無權限") -> Dict[str, Any]:
    import requests

    t0 = time.monotonic()
    try:
        resp = requests.get(url, headers=headers, timeout=_TEST_TIMEOUT_S)
        ms = int((time.monotonic() - t0) * 1000)
        if resp.status_code in ok_statuses:
            return {"ok": True, "latency_ms": ms, "detail": f"HTTP {resp.status_code}"}
        if resp.status_code in (401, 403):
            return {"ok": False, "latency_ms": ms,
                    "detail": f"HTTP {resp.status_code} — {auth_hint}"}
        return {"ok": False, "latency_ms": ms, "detail": f"HTTP {resp.status_code}"}
    except Exception as e:  # noqa: BLE001 — surfaced verbatim to the UI
        return {"ok": False, "latency_ms": None, "detail": str(e)[:200]}


def run_connection_test(provider: str) -> Dict[str, Any]:
    """One explicit, cheap, timeout-bounded probe per provider (user-triggered).
    ok=None means 'no live test offered' (paid-per-call or extension path)."""
    if provider == "ibkr":
        host = os.getenv("IBKR_HOST")
        port = os.getenv("IBKR_PORT")
        if not host or not port:
            return {"ok": False, "latency_ms": None, "detail": "host/port 未設定"}
        t0 = time.monotonic()
        try:
            with socket.create_connection((host, int(port)), timeout=3):
                pass
            ms = int((time.monotonic() - t0) * 1000)
            return {"ok": True, "latency_ms": ms,
                    "detail": f"TCP {host}:{port} 可連線（Gateway socket）"}
        except (OSError, ValueError) as e:
            return {"ok": False, "latency_ms": None, "detail": f"{host}:{port} — {e}"}

    if provider == "polygon":
        key = os.getenv("POLYGON_API_KEY")
        if not key:
            return {"ok": False, "latency_ms": None, "detail": "缺 API key"}
        return _http_probe(
            f"https://api.polygon.io/v3/reference/tickers?limit=1&apiKey={key}")

    if provider == "finnhub":
        key = os.getenv("FINNHUB_API_KEY")
        if not key:
            return {"ok": False, "latency_ms": None, "detail": "缺 API key"}
        return _http_probe(
            f"https://finnhub.io/api/v1/stock/profile2?symbol=AAPL&token={key}")

    if provider == "fred":
        key = os.getenv("FRED_API_KEY")
        if not key:
            return {"ok": False, "latency_ms": None, "detail": "缺 API key"}
        return _http_probe(
            "https://api.stlouisfed.org/fred/series?series_id=GNPCA"
            f"&api_key={key}&file_type=json",
            ok_statuses=(200,))

    if provider == "sec_edgar":
        # free + key-less, but SEC rejects generic User-Agents — reuse the SEC
        # client's own UA builder (SEC_CONTACT_EMAIL from config/.env) and probe
        # the same endpoint the client actually uses.
        from data_sources.sec_edgar_financials import _get_sec_user_agent

        return _http_probe(
            "https://www.sec.gov/files/company_tickers.json",
            headers={"User-Agent": _get_sec_user_agent(), "Accept": "application/json"},
            auth_hint="被 SEC 拒絕 — User-Agent 需含聯絡 email（設定 SEC_CONTACT_EMAIL）")

    if provider == "financial_datasets":
        key = os.getenv("FINANCIAL_DATASETS_API_KEY")
        return {"ok": None, "latency_ms": None,
                "detail": ("metered（按次計費）— 不提供測試呼叫；key "
                           + ("已設定" if key else "未設定"))}

    if provider == "seeking_alpha":
        return {"ok": None, "latency_ms": None,
                "detail": "extension 擷取路徑 — 無外部連線可測"}

    return {"ok": False, "latency_ms": None, "detail": f"unknown provider {provider!r}"}
