"""Tests for the slice 3e-A provider-health read model (+ route)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.service.provider_health import compute_provider_health

# Fixed clocks: 2026-06-10 = Wednesday; 2026-06-13 = Saturday (NY weekend).
_WEDNESDAY = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
_SATURDAY = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)


class _FakeBackend:
    """Health-signal stub: query_health_stats + get_sa_refresh_meta only.
    Deliberately has NO _get_conn → JobRunsStore.is_available() is False, so
    job_runs degrade to {} without monkeypatching."""

    def __init__(self, stats=None, sa=None):
        self._stats = stats or {}
        self._sa = sa or {}

    def query_health_stats(self):
        if isinstance(self._stats, Exception):
            raise self._stats
        return self._stats

    def get_sa_refresh_meta(self):
        return self._sa


class _FakeDAL:
    def __init__(self, backend):
        self._backend = backend


def _stats(news_rows=(), prices_latest=None, iv_latest=None, fin_rows=()):
    return {
        "news": {"rows": list(news_rows), "error": None},
        "prices": {"rows": [(prices_latest,)] if prices_latest else [], "error": None},
        "iv_history": {"rows": [(iv_latest,)] if iv_latest else [], "error": None},
        "financial_cache": {"rows": list(fin_rows), "error": None},
    }


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    """Isolate from the real machine: env keys, config/.env scan, local market DB."""
    # ensure_env_loaded is set-if-absent from the REAL config/.env — neutralize it
    # (mark already-loaded, empty loader-tracking) so the delenv below cannot be
    # undone mid-test and key_source defaults to "env" for setenv'd keys.
    monkeypatch.setattr("src.env_keys._loaded", True)
    monkeypatch.setattr("src.env_keys._loaded_keys", set())
    for var in ("POLYGON_API_KEY", "FINNHUB_API_KEY", "FRED_API_KEY",
                "FINANCIAL_DATASETS_API_KEY", "IBKR_HOST", "IBKR_PORT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("src.market_data_admin.read_sync_meta", lambda *a, **k: {})
    monkeypatch.setattr("src.tools.analysis_tools._is_fd_enabled", lambda dal: False)


def _by_id(out, pid):
    return next(p for p in out["providers"] if p["id"] == pid)


def test_connected_when_signal_recent(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "k")
    dal = _FakeDAL(_FakeBackend(stats=_stats(
        news_rows=[("polygon", _WEDNESDAY - timedelta(hours=2), 50)])))
    p = _by_id(compute_provider_health(dal, now=_WEDNESDAY), "polygon")
    assert p["status"] == "connected"
    assert p["last_success_at"] is not None and p["signals"]["news_recent_7d"] == 50


def test_stale_when_signal_old_on_weekday(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "k")
    dal = _FakeDAL(_FakeBackend(stats=_stats(
        news_rows=[("polygon", _WEDNESDAY - timedelta(hours=100), 0)])))
    assert _by_id(compute_provider_health(dal, now=_WEDNESDAY), "polygon")["status"] == "stale"


def test_ibkr_weekend_is_maintenance_not_stale(monkeypatch):
    # The SAME old-signal condition: IBKR on a NY weekend → maintenance (gateway
    # weekend maintenance ≠ error, per the locked F1+F2 directive); a non-IBKR
    # provider stays stale.
    monkeypatch.setenv("IBKR_HOST", "192.168.0.153")
    monkeypatch.setenv("IBKR_PORT", "4001")
    monkeypatch.setenv("POLYGON_API_KEY", "k")
    old = _SATURDAY - timedelta(hours=100)
    dal = _FakeDAL(_FakeBackend(stats=_stats(
        news_rows=[("polygon", old, 0)], prices_latest=old)))
    out = compute_provider_health(dal, now=_SATURDAY)
    assert _by_id(out, "ibkr")["status"] == "maintenance"
    assert _by_id(out, "polygon")["status"] == "stale"
    # an equally-old signal relative to a WEEKDAY → ibkr reads stale (no weekend cover)
    old2 = _WEDNESDAY - timedelta(hours=100)
    dal2 = _FakeDAL(_FakeBackend(stats=_stats(prices_latest=old2)))
    out2 = compute_provider_health(dal2, now=_WEDNESDAY)
    assert _by_id(out2, "ibkr")["status"] == "stale"


def test_missing_key_wins_over_signal():
    # no POLYGON_API_KEY in env (hermetic fixture) — even with a fresh signal
    dal = _FakeDAL(_FakeBackend(stats=_stats(
        news_rows=[("polygon", _WEDNESDAY - timedelta(hours=1), 9)])))
    assert _by_id(compute_provider_health(dal, now=_WEDNESDAY), "polygon")["status"] == "missing_key"


def test_fd_disabled_is_a_state(monkeypatch):
    monkeypatch.setenv("FINANCIAL_DATASETS_API_KEY", "k")
    dal = _FakeDAL(_FakeBackend(stats=_stats(
        fin_rows=[("financial_datasets", 5, 1, _WEDNESDAY - timedelta(days=3))])))
    p = _by_id(compute_provider_health(dal, now=_WEDNESDAY), "financial_datasets")
    assert p["status"] == "disabled" and p["enabled"] is False


def test_no_signal_when_nothing_recorded(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "k")
    dal = _FakeDAL(_FakeBackend())  # no job_runs (fake backend has no _get_conn)
    assert _by_id(compute_provider_health(dal, now=_WEDNESDAY), "fred")["status"] == "no_signal"


def test_sec_edgar_ttl_governed_never_stale():
    # sec_edgar: no key required; valid cached rows → connected even with an old
    # latest_fetched (threshold None — cache TTL governs validity, not age).
    dal = _FakeDAL(_FakeBackend(stats=_stats(
        fin_rows=[("sec_edgar", 12, 30, _WEDNESDAY - timedelta(days=80))])))
    p = _by_id(compute_provider_health(dal, now=_WEDNESDAY), "sec_edgar")
    assert p["status"] == "connected"
    assert p["key_source"] == "not_required"
    assert "12 valid" in p["detail"]


def test_key_source_reports_effective_origin(monkeypatch):
    # The loader is set-if-absent, so the EFFECTIVE source of a present key is:
    # loaded-by-the-loader → config/.env; otherwise → real env (env wins even when
    # the file also names it). Multi-var keys spanning both → mixed.
    monkeypatch.setenv("POLYGON_API_KEY", "k")    # real env (not loader-set)
    monkeypatch.setenv("FINNHUB_API_KEY", "k")    # below: marked loader-set
    monkeypatch.setenv("IBKR_HOST", "h")          # env...
    monkeypatch.setenv("IBKR_PORT", "4001")       # ...but PORT marked loader-set → mixed
    monkeypatch.setattr("src.env_keys._loaded_keys", {"FINNHUB_API_KEY", "IBKR_PORT"})
    out = compute_provider_health(_FakeDAL(_FakeBackend()), now=_WEDNESDAY)
    assert _by_id(out, "polygon")["key_source"] == "env"
    assert _by_id(out, "finnhub")["key_source"] == "config/.env"
    assert _by_id(out, "ibkr")["key_source"] == "mixed"
    assert _by_id(out, "fred")["key_source"] == "missing"


def test_disabled_outranks_missing_key(monkeypatch):
    # FD disabled AND key missing → product semantics say "disabled" (the user
    # turned it off; nagging missing_key for an unwanted provider is wrong).
    monkeypatch.delenv("FINANCIAL_DATASETS_API_KEY", raising=False)
    p = _by_id(compute_provider_health(_FakeDAL(_FakeBackend()), now=_WEDNESDAY),
               "financial_datasets")
    assert p["key_present"] is False
    assert p["status"] == "disabled"


def test_sa_capture_error_and_success_merge():
    sa = {
        "current": {"last_success_at": (_WEDNESDAY - timedelta(hours=3)).isoformat(),
                    "last_attempt_at": (_WEDNESDAY - timedelta(hours=1)).isoformat(),
                    "ok": False, "last_error": "parse failed"},
        "closed": {"last_success_at": (_WEDNESDAY - timedelta(hours=30)).isoformat(),
                   "last_attempt_at": (_WEDNESDAY - timedelta(hours=30)).isoformat(),
                   "ok": True, "last_error": None},
    }
    p = _by_id(compute_provider_health(_FakeDAL(_FakeBackend(sa=sa)), now=_WEDNESDAY),
               "seeking_alpha")
    assert p["status"] == "connected"            # newest success 3h ago
    assert p["last_error"] == "parse failed"     # non-ok scope surfaces its error
    assert "FAILED" in p["detail"]


def test_section_failure_degrades_not_raises():
    dal = _FakeDAL(_FakeBackend(stats=RuntimeError("PG down")))
    out = compute_provider_health(dal, now=_WEDNESDAY)
    assert any("query_health_stats failed" in n for n in out["notes"])
    assert len(out["providers"]) == 7            # all providers still listed
    assert _by_id(out, "sec_edgar")["status"] == "no_signal"


def test_route_returns_aggregation(monkeypatch):
    from src.api.routes.health import providers_health
    dal = _FakeDAL(_FakeBackend())
    out = providers_health(dal=dal)
    assert {p["id"] for p in out["providers"]} == {
        "ibkr", "polygon", "finnhub", "fred", "sec_edgar",
        "financial_datasets", "seeking_alpha"}
    assert "local_market" in out and "jobs" in out
