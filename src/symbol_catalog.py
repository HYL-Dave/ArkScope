"""
Local symbol catalog (US ticker → company name) for add-ticker autocomplete.

Seeded from SEC ``company_tickers.json`` (free, ~10k US tickers with names),
cached on disk so typing a keyword gives instant suggestions + typo-catch with
NO per-keystroke API call. Local-first: the network is touched at most once per
TTL to refresh the cache; if it is unreachable and no cache exists, search just
returns the accepted active-universe seed when available.

This is reference data, not user state — it does not live in the profile-state
DB. The on-disk cache is ``data/cache/sec_company_tickers.json`` (gitignored).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Optional

from src.active_universe import ActiveUniverseUnavailable, build_active_universe_snapshot

_SEC_URL = "https://www.sec.gov/files/company_tickers.json"
_TTL_SECONDS = 30 * 86_400  # refresh monthly
# SEC's fair-access policy REJECTS (HTTP 403) a UA without a contact — it must
# include an email-like token. Override with a real contact via the env var.
_DEFAULT_UA = "ArkScope/0.1 (arkscope@example.com)"
logger = logging.getLogger(__name__)


def _user_agent() -> str:
    return os.environ.get("ARKSCOPE_SEC_USER_AGENT") or _DEFAULT_UA


_lock = threading.Lock()
_cache: Optional[list[dict]] = None  # in-memory [{ticker, name}]
_cache_seed_key: tuple[str, ...] | None = None
_sec_cache: dict[str, str] | None = None
_sec_checked_at: float = 0.0
_sec_ok: bool = False
_test_catalog_override: bool = False
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


def _normalized_tickers(tickers: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                normalized
                for raw in tickers
                if (normalized := str(raw or "").strip().upper())
            }
        )
    )


def _local_seed(active_tickers: Iterable[str] | None = None) -> dict[str, str]:
    """Accepted active tickers with blank names for the SEC overlay to enrich."""
    if active_tickers is None:
        try:
            active_tickers = build_active_universe_snapshot().tickers
        except ActiveUniverseUnavailable as exc:
            logger.warning("symbol catalog active seed unavailable: %s", exc.code)
            active_tickers = ()
    return {ticker: "" for ticker in _normalized_tickers(active_tickers)}


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


def load_catalog(
    force: bool = False,
    active_tickers: Iterable[str] | None = None,
) -> list[dict]:
    """Catalog = accepted active tickers overlaid with SEC reference names.

    When ``active_tickers`` is omitted, one complete local snapshot supplies the
    seed. A typed snapshot outage contributes no seed, while SEC data remains
    available for autocomplete.
    """
    global _cache, _cache_seed_key, _sec_cache, _sec_checked_at, _sec_ok
    with _lock:
        if _test_catalog_override and _cache is not None and not force:
            return _cache

    seed = _local_seed() if active_tickers is None else _local_seed(active_tickers)
    seed_key = tuple(sorted(seed))

    with _lock:
        sec_age = time.time() - _sec_checked_at
        sec_stale = _sec_cache is None or sec_age >= _TTL_SECONDS
        # Self-heal after an empty/failed SEC load without coupling retry timing
        # to active-universe changes.
        retry_after_fail = (not _sec_ok) and sec_age >= _RETRY_AFTER_SEC_FAIL
        refresh_sec = force or sec_stale or retry_after_fail
        seed_changed = _cache_seed_key != seed_key
        if _cache is not None and not seed_changed and not refresh_sec:
            return _cache

        if refresh_sec:
            _sec_cache = _load_sec(force)
            _sec_checked_at = time.time()
            _sec_ok = bool(_sec_cache)

        merged = dict(seed)
        sec = _sec_cache or {}
        for ticker, name in sec.items():
            # SEC name enriches; SEC-only tickers are added too (broad US list).
            merged[ticker] = name or merged.get(ticker, "")
        _cache = [{"ticker": t, "name": n} for t, n in merged.items()]
        _cache_seed_key = seed_key
        return _cache


def search(
    q: str,
    limit: int = 20,
    active_tickers: Iterable[str] | None = None,
) -> list[dict]:
    """Rank matches for ``q``: exact ticker, ticker-prefix, ticker-substring,
    then company-name substring. Returns ``[{ticker, name}]`` (≤ ``limit``)."""
    ql = (q or "").strip().upper()
    if not ql:
        return []
    qn = ql.lower()
    catalog = load_catalog(active_tickers=active_tickers)
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
    global _cache, _cache_seed_key, _sec_cache, _sec_checked_at, _sec_ok
    global _test_catalog_override
    with _lock:
        _cache = None
        _cache_seed_key = None
        _sec_cache = None
        _sec_checked_at = 0.0
        _sec_ok = False
        _test_catalog_override = False


def set_catalog_for_tests(entries: list[dict]) -> None:
    """Inject a ``[{ticker, name}]`` catalog directly (avoids network in tests)."""
    global _cache, _cache_seed_key, _sec_cache, _sec_checked_at, _sec_ok
    global _test_catalog_override
    with _lock:
        _cache = [{"ticker": str(e["ticker"]).upper(), "name": e.get("name", "")} for e in entries]
        _cache_seed_key = tuple(sorted(e["ticker"] for e in _cache))
        _sec_cache = {e["ticker"]: e["name"] for e in _cache}
        _sec_checked_at = time.time()
        _sec_ok = True
        _test_catalog_override = True
