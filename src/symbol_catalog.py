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
import threading
import time
from pathlib import Path
from typing import Optional

_SEC_URL = "https://www.sec.gov/files/company_tickers.json"
_TTL_SECONDS = 30 * 86_400  # refresh monthly
# SEC requires a descriptive User-Agent on automated requests.
_UA = "ArkScope/0.1 research workbench (local single-user)"

_lock = threading.Lock()
_cache: Optional[list[dict]] = None  # in-memory [{ticker, name}], loaded once


def _cache_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "cache" / "sec_company_tickers.json"


def _parse(raw) -> list[dict]:
    """SEC shape: {"0": {"cik_str", "ticker", "title"}, ...}. Tolerant of a list."""
    entries = raw.values() if isinstance(raw, dict) else (raw or [])
    out: list[dict] = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        t = str(e.get("ticker", "")).upper().strip()
        if t:
            out.append({"ticker": t, "name": str(e.get("title", "")).strip()})
    return out


def _fetch_and_store(path: Path) -> list[dict]:
    import requests

    resp = requests.get(_SEC_URL, headers={"User-Agent": _UA}, timeout=30)
    resp.raise_for_status()
    raw = resp.json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw), encoding="utf-8")
    return _parse(raw)


def load_catalog(force: bool = False) -> list[dict]:
    """Return the cached catalog, refreshing from SEC if stale/missing.

    Never raises: on any failure it falls back to a stale cache, then ``[]``.
    """
    global _cache
    with _lock:
        if _cache is not None and not force:
            return _cache
        path = _cache_path()
        fresh = path.exists() and (time.time() - path.stat().st_mtime) < _TTL_SECONDS
        try:
            if fresh and not force:
                _cache = _parse(json.loads(path.read_text(encoding="utf-8")))
            else:
                _cache = _fetch_and_store(path)
        except Exception:
            if path.exists():
                try:
                    _cache = _parse(json.loads(path.read_text(encoding="utf-8")))
                except Exception:
                    _cache = []
            else:
                _cache = []
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
    global _cache
    with _lock:
        _cache = None


def set_catalog_for_tests(entries: list[dict]) -> None:
    """Inject a ``[{ticker, name}]`` catalog directly (avoids network in tests)."""
    global _cache
    with _lock:
        _cache = [{"ticker": str(e["ticker"]).upper(), "name": e.get("name", "")} for e in entries]
