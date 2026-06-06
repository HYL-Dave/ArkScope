"""
Local symbol catalog (US ticker → company name) for add-ticker autocomplete.

Seeded from SEC ``company_tickers.json`` (free, ~10k US tickers with names),
cached on disk so typing a keyword gives instant suggestions + typo-catch with
NO per-keystroke API call. Local-first: the network is touched at most once per
TTL to refresh the cache; if it is unreachable and no cache exists, search just
returns ``[]`` (degrades, never raises).

This is reference data, not user state — it does not live in the profile-state
DB. The on-disk cache is ``data/cache/sec_company_tickers.json`` (gitignored).
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Optional

_SEC_URL = "https://www.sec.gov/files/company_tickers.json"
_TTL_SECONDS = 30 * 86_400  # refresh monthly
# SEC's fair-access policy REJECTS (HTTP 403) a UA without a contact — it must
# include an email-like token. Override with a real contact via the env var.
_DEFAULT_UA = "ArkScope/0.1 (arkscope@example.com)"


def _user_agent() -> str:
    return os.environ.get("ARKSCOPE_SEC_USER_AGENT") or _DEFAULT_UA


_lock = threading.Lock()
_cache: Optional[list[dict]] = None  # in-memory [{ticker, name}]
_cache_built_at: float = 0.0        # when _cache was last (re)built
_cache_sec_ok: bool = False         # did the last build get SEC names?
# If a build's SEC overlay failed (offline/403), let a later call retry rather
# than serving blank names for the whole process — but not on every keystroke.
_RETRY_AFTER_SEC_FAIL = 600.0


def _cache_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "cache" / "sec_company_tickers.json"


def _parse_sec(raw) -> dict[str, str]:
    """SEC shape {"0": {"cik_str","ticker","title"}, ...} → {TICKER: name}."""
    entries = raw.values() if isinstance(raw, dict) else (raw or [])
    out: dict[str, str] = {}
    for e in entries:
        if not isinstance(e, dict):
            continue
        t = str(e.get("ticker", "")).upper().strip()
        if t:
            out[t] = str(e.get("title", "")).strip()
    return out


def _local_seed() -> dict[str, str]:
    """Tickers we track (tickers_core) → name "" (filled by SEC overlay if any).

    The local-first spine: search works offline / when SEC 403s, and always
    covers everything in our universe (e.g. RKLB, MXL)."""
    try:
        from src.universe_config import all_universe_tickers

        return {t: "" for t in all_universe_tickers()}
    except Exception:
        return {}


def _load_sec(force: bool) -> dict[str, str]:
    """SEC ticker→name map from cache (fresh) or network. {} on any failure."""
    path = _cache_path()
    fresh = path.exists() and (time.time() - path.stat().st_mtime) < _TTL_SECONDS
    try:
        if fresh and not force:
            return _parse_sec(json.loads(path.read_text(encoding="utf-8")))
        import requests

        resp = requests.get(
            _SEC_URL,
            headers={"User-Agent": _user_agent(), "Accept-Encoding": "gzip, deflate"},
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw), encoding="utf-8")
        return _parse_sec(raw)
    except Exception:
        # fall back to a stale cache file if present, else nothing (local seed covers)
        if path.exists():
            try:
                return _parse_sec(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                return {}
        return {}


def load_catalog(force: bool = False) -> list[dict]:
    """Catalog = local universe (always) overlaid with SEC names (when reachable).

    Never raises and never ends up empty when we track anything: the local seed
    is always present, so add-ticker works even if SEC is blocked/offline.
    """
    global _cache, _cache_built_at, _cache_sec_ok
    with _lock:
        if _cache is not None and not force:
            age = time.time() - _cache_built_at
            stale = age >= _TTL_SECONDS
            # Self-heal: if the last build couldn't reach SEC (blank names), let
            # a later call retry after a backoff so a long-running server picks
            # up SEC names without a restart.
            retry_after_fail = (not _cache_sec_ok) and age >= _RETRY_AFTER_SEC_FAIL
            if not stale and not retry_after_fail:
                return _cache
        merged = _local_seed()  # {TICKER: ""}
        sec = _load_sec(force)
        for ticker, name in sec.items():
            # SEC name enriches; SEC-only tickers are added too (broad US list).
            merged[ticker] = name or merged.get(ticker, "")
        _cache = [{"ticker": t, "name": n} for t, n in merged.items()]
        _cache_built_at = time.time()
        _cache_sec_ok = bool(sec)
        return _cache


def search(q: str, limit: int = 20) -> list[dict]:
    """Rank matches for ``q``: exact ticker, ticker-prefix, ticker-substring,
    then company-name substring. Returns ``[{ticker, name}]`` (≤ ``limit``)."""
    ql = (q or "").strip().upper()
    if not ql:
        return []
    qn = ql.lower()
    catalog = load_catalog()
    exact: list[dict] = []
    prefix: list[dict] = []
    tsub: list[dict] = []
    nsub: list[dict] = []
    for e in catalog:
        t = e["ticker"]
        if t == ql:
            exact.append(e)
        elif t.startswith(ql):
            prefix.append(e)
        elif ql in t:
            tsub.append(e)
        elif qn and qn in e["name"].lower():
            nsub.append(e)
    prefix.sort(key=lambda e: e["ticker"])
    return (exact + prefix + tsub + nsub)[: max(1, limit)]


def reset_for_tests() -> None:
    global _cache, _cache_built_at, _cache_sec_ok
    with _lock:
        _cache = None
        _cache_built_at = 0.0
        _cache_sec_ok = False


def set_catalog_for_tests(entries: list[dict]) -> None:
    """Inject a ``[{ticker, name}]`` catalog directly (avoids network in tests)."""
    global _cache, _cache_built_at, _cache_sec_ok
    with _lock:
        _cache = [{"ticker": str(e["ticker"]).upper(), "name": e.get("name", "")} for e in entries]
        _cache_built_at = time.time()
        _cache_sec_ok = True
