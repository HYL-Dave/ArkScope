"""Tests for the slice 3e-A provider-health read model (+ route)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from src.service.provider_health import compute_provider_health
from src.market_data_direct import _ensure_provider_sync_tables
from src.market_data_admin import read_sync_meta as _read_sync_meta

# Fixed clocks: 2026-06-10 = Wednesday; 2026-06-13 = Saturday (NY weekend).
_WEDNESDAY = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
_SATURDAY = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)


class _FakeBackend:
    """Health-signal stub exposing current health and refresh capabilities."""

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


def _stats(news_rows=(), prices_latest=None, fin_rows=()):
    return {
        "news": {"rows": list(news_rows), "error": None},
        "prices": {"rows": [(prices_latest,)] if prices_latest else [], "error": None},
        "financial_cache": {"rows": list(fin_rows), "error": None},
    }


@pytest.fixture(autouse=True)
def hermetic(monkeypatch, tmp_path):
    """Isolate from the real machine: env keys, config/.env scan, local market DB."""
    # ensure_env_loaded is set-if-absent from the REAL config/.env — neutralize it
    # (mark already-loaded, empty loader-tracking) so the delenv below cannot be
    # undone mid-test and key_source defaults to "env" for setenv'd keys.
    monkeypatch.setattr("src.env_keys._loaded", True)
    monkeypatch.setattr("src.env_keys._loaded_keys", set())
    for var in ("MASSIVE_API_KEY", "POLYGON_API_KEY", "FINNHUB_API_KEY", "FRED_API_KEY",
                "FINANCIAL_DATASETS_API_KEY", "IBKR_HOST", "IBKR_PORT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "market.db"))
    monkeypatch.setattr("src.market_data_admin.read_sync_meta", lambda *a, **k: {})
    monkeypatch.setattr("src.tools.analysis_tools._is_fd_enabled", lambda dal: False)


@pytest.fixture
def news_runs(tmp_path):
    def record(provider, finished_at, *, status="succeeded", error=None,
               rows_added=0, tickers_scanned=1):
        if isinstance(finished_at, datetime):
            finished_at = finished_at.isoformat()
        conn = sqlite3.connect(tmp_path / "market.db")
        try:
            _ensure_provider_sync_tables(conn)
            conn.execute(
                "INSERT INTO provider_sync_runs "
                "(provider,domain,interval,started_at,finished_at,status,error,rows_added,tickers_scanned) "
                "VALUES (?,'news','news',?,?,?,?,?,?)",
                (provider, finished_at, finished_at, status, error, rows_added, tickers_scanned),
            )
            conn.commit()
        finally:
            conn.close()
    return record


def _by_id(out, pid):
    return next(p for p in out["providers"] if p["id"] == pid)


def test_connected_when_signal_recent(monkeypatch, news_runs):
    monkeypatch.setenv("MASSIVE_API_KEY", "k")
    news_runs("polygon", _WEDNESDAY - timedelta(hours=2))
    dal = _FakeDAL(_FakeBackend(stats=_stats(
        news_rows=[("polygon", _WEDNESDAY - timedelta(hours=2), 50)])))
    p = _by_id(compute_provider_health(dal, now=_WEDNESDAY), "massive")
    assert p["status"] == "connected"
    assert p["last_success_at"] is not None and p["signals"]["news_recent_7d"] == 50


def test_massive_health_uses_primary_name_and_rejects_legacy_fallback(monkeypatch, news_runs):
    monkeypatch.setenv("MASSIVE_API_KEY", "massive-primary")
    news_runs("polygon", _WEDNESDAY - timedelta(hours=2))
    dal = _FakeDAL(_FakeBackend(stats=_stats(
        news_rows=[("polygon", _WEDNESDAY - timedelta(hours=2), 50)])))

    primary = _by_id(compute_provider_health(dal, now=_WEDNESDAY), "massive")

    assert primary["label"] == "Massive"
    assert primary["status"] == "connected"
    assert primary["key_vars"] == ["MASSIVE_API_KEY"]

    monkeypatch.delenv("MASSIVE_API_KEY")
    monkeypatch.setenv("POLYGON_API_KEY", "polygon-legacy")
    legacy = _by_id(compute_provider_health(dal, now=_WEDNESDAY), "massive")
    assert legacy["status"] == "not_configured"


def test_connected_when_local_sqlite_timestamp_uses_compact_utc_offset(monkeypatch, news_runs):
    monkeypatch.setenv("FINNHUB_API_KEY", "k")
    news_runs("finnhub", "2026-06-10T10:30:00+0000")
    dal = _FakeDAL(_FakeBackend(stats=_stats(
        news_rows=[("finnhub", "2026-06-10T10:30:00+0000", 12)])))
    p = _by_id(compute_provider_health(dal, now=_WEDNESDAY), "finnhub")
    assert p["status"] == "connected"
    assert p["last_success_at"] == "2026-06-10T10:30:00+00:00"


def test_stale_when_signal_old_on_weekday(monkeypatch, news_runs):
    monkeypatch.setenv("MASSIVE_API_KEY", "k")
    news_runs("polygon", _WEDNESDAY - timedelta(hours=100))
    dal = _FakeDAL(_FakeBackend(stats=_stats(
        news_rows=[("polygon", _WEDNESDAY - timedelta(hours=100), 0)])))
    assert _by_id(compute_provider_health(dal, now=_WEDNESDAY), "massive")["status"] == "stale"


def test_ibkr_weekend_is_maintenance_not_stale(monkeypatch, news_runs):
    # The SAME old-signal condition: IBKR on a NY weekend → maintenance (gateway
    # weekend maintenance ≠ error, per the locked F1+F2 directive); a non-IBKR
    # provider stays stale.
    monkeypatch.setenv("IBKR_HOST", "192.168.0.153")
    monkeypatch.setenv("IBKR_PORT", "4001")
    monkeypatch.setenv("MASSIVE_API_KEY", "k")
    old = _SATURDAY - timedelta(hours=100)
    news_runs("polygon", old)
    dal = _FakeDAL(_FakeBackend(stats=_stats(
        news_rows=[("polygon", old, 0)], prices_latest=old)))
    out = compute_provider_health(dal, now=_SATURDAY)
    assert _by_id(out, "ibkr")["status"] == "maintenance"
    assert _by_id(out, "massive")["status"] == "stale"
    # an equally-old signal relative to a WEEKDAY → ibkr reads stale (no weekend cover)
    old2 = _WEDNESDAY - timedelta(hours=100)
    dal2 = _FakeDAL(_FakeBackend(stats=_stats(prices_latest=old2)))
    out2 = compute_provider_health(dal2, now=_WEDNESDAY)
    assert _by_id(out2, "ibkr")["status"] == "stale"


def test_provider_health_missing_managed_key_is_not_configured(news_runs):
    # no MASSIVE_API_KEY in env (hermetic fixture) — even with a fresh signal
    news_runs("polygon", _WEDNESDAY - timedelta(hours=1))
    dal = _FakeDAL(_FakeBackend(stats=_stats(
        news_rows=[("polygon", _WEDNESDAY - timedelta(hours=1), 9)])))
    p = _by_id(compute_provider_health(dal, now=_WEDNESDAY), "massive")
    assert p["status"] == "not_configured"
    assert p["config_error"] == {
        "code": "provider_config_missing",
        "status": "not_configured",
        "provider": "massive",
        "field": "api_key",
    }


def test_fd_disabled_is_a_state(monkeypatch):
    monkeypatch.setenv("FINANCIAL_DATASETS_API_KEY", "k")
    dal = _FakeDAL(_FakeBackend(stats=_stats(
        fin_rows=[("financial_datasets", 5, 1, _WEDNESDAY - timedelta(days=3))])))
    p = _by_id(compute_provider_health(dal, now=_WEDNESDAY), "financial_datasets")
    assert p["status"] == "disabled" and p["enabled"] is False


def test_no_signal_when_nothing_recorded(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "k")
    monkeypatch.setattr(
        "src.service.provider_health.read_macro_schedule_automation",
        lambda: None,
    )
    dal = _FakeDAL(_FakeBackend())
    p = _by_id(compute_provider_health(dal, now=_WEDNESDAY), "fred")
    assert p["status"] == "no_signal"
    assert p["signals"]["auto_refresh_enabled"] is None
    assert p["signals"]["enabled_schedule_source_count"] is None
    assert "scheduled-source state unknown" in p["detail"]


def test_fred_snapshot_available_when_refresh_is_off(monkeypatch, tmp_path):
    monkeypatch.setenv("FRED_API_KEY", "k")
    monkeypatch.setattr(
        "src.service.provider_health.read_macro_schedule_automation",
        lambda: {
            "fred_series": False,
            "fred_release_dates": False,
        },
    )
    monkeypatch.setattr(
        "src.service.provider_health.resolve_macro_calendar_db_path",
        lambda: str(tmp_path / "macro_calendar.db"),
        raising=False,
    )
    monkeypatch.setattr(
        "src.service.provider_health.read_macro_table_stats",
        lambda path: {
            "macro_series": {"row_count": 11, "last_fetched_at": "2026-06-25T01:09:52Z"},
            "macro_observations": {"row_count": 29571, "last_fetched_at": "2026-06-25T01:09:52Z"},
            "macro_release_dates": {"row_count": 4659, "last_fetched_at": "2026-06-25T01:09:52Z"},
        },
        raising=False,
    )
    now = datetime(2026, 7, 5, tzinfo=timezone.utc)
    p = _by_id(compute_provider_health(_FakeDAL(_FakeBackend()), now=now), "fred")
    assert p["status"] == "connected"
    assert p["disabled_reason"] is None
    assert p["enabled"] is None
    assert p["signals"]["auto_refresh_enabled"] is False
    assert p["signals"]["local_snapshot"]["observation_count"] == 29571
    assert "local snapshot" in p["detail"].lower()
    assert "0 scheduled source(s) enabled" in p["detail"].lower()


def test_fred_refresh_off_without_snapshot_is_no_signal(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "k")
    monkeypatch.setattr(
        "src.service.provider_health.read_macro_schedule_automation",
        lambda: {
            "fred_series": False,
            "fred_release_dates": False,
        },
    )
    monkeypatch.setattr(
        "src.service.provider_health.read_macro_table_stats",
        lambda path: {},
        raising=False,
    )
    p = _by_id(compute_provider_health(_FakeDAL(_FakeBackend()), now=_WEDNESDAY), "fred")
    assert p["status"] == "no_signal"
    assert p["disabled_reason"] is None
    assert p["enabled"] is None
    assert p["signals"]["auto_refresh_enabled"] is False
    assert p["signals"]["local_snapshot"]["observation_count"] == 0


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
    monkeypatch.setenv("MASSIVE_API_KEY", "k")    # real env (not loader-set)
    monkeypatch.setenv("FINNHUB_API_KEY", "k")    # below: marked loader-set
    monkeypatch.setenv("IBKR_HOST", "h")          # env...
    monkeypatch.setenv("IBKR_PORT", "4001")       # ...but PORT marked loader-set → mixed
    monkeypatch.setattr("src.env_keys._loaded_keys", {"FINNHUB_API_KEY", "IBKR_PORT"})
    out = compute_provider_health(_FakeDAL(_FakeBackend()), now=_WEDNESDAY)
    assert _by_id(out, "massive")["key_source"] == "env"
    assert _by_id(out, "finnhub")["key_source"] == "config/.env"
    assert _by_id(out, "finnhub")["status"] == "not_configured"
    assert _by_id(out, "finnhub")["config_error"]["field"] == "api_key"
    assert _by_id(out, "ibkr")["key_source"] == "mixed"
    assert _by_id(out, "fred")["key_source"] == "missing"


def test_retired_polygon_file_key_is_not_a_massive_import_suggestion(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "pk_from_file")
    monkeypatch.setattr("src.env_keys._loaded_keys", {"POLYGON_API_KEY"})
    out = compute_provider_health(_FakeDAL(_FakeBackend()), now=_WEDNESDAY)
    p = _by_id(out, "massive")
    assert p["key_source"] == "missing"
    assert p["status"] == "not_configured"
    assert p["key_import_suggested"] is False
    assert p["config_error"]["code"] == "provider_config_missing"


def test_disabled_outranks_missing_key(monkeypatch):
    # FD disabled AND key missing → product semantics say "disabled" (the user
    # turned it off; nagging missing_key for an unwanted provider is wrong).
    monkeypatch.delenv("FINANCIAL_DATASETS_API_KEY", raising=False)
    p = _by_id(compute_provider_health(_FakeDAL(_FakeBackend()), now=_WEDNESDAY),
               "financial_datasets")
    assert p["key_present"] is False
    assert p["status"] == "disabled"
    assert p["config_error"]["code"] == "provider_config_missing"


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


def test_sa_provider_uses_derived_complete_success_and_latest_attempt_separately(monkeypatch):
    complete = {
        "id": 301,
        "status": "succeeded",
        "started_at": "2026-06-10T08:00:00+00:00",
        "finished_at": "2026-06-10T08:01:00+00:00",
        "result": {
            "derived_outcome": "complete",
            "healthy_anchor_eligible": True,
            "counts": {"failed_retryable": 0},
        },
    }
    degraded = {
        "id": 302,
        "status": "failed",
        "started_at": "2026-06-10T10:00:00+00:00",
        "finished_at": "2026-06-10T10:01:00+00:00",
        "result": {
            "derived_outcome": "degraded",
            "healthy_anchor_eligible": False,
            "counts": {"failed_retryable": 4},
        },
    }

    class _Store:
        def latest_runs_by_name(self):
            return {"sa_market_news_refresh": degraded}

        def structured_extension_summary_by_name(self, job_names):
            assert job_names == ["sa_market_news_refresh"]
            return {
                "sa_market_news_refresh": {
                    "latest_attempt": degraded,
                    "latest_derived_complete": complete,
                }
            }

    monkeypatch.setattr(
        "src.service.job_runs_store.get_job_runs_store",
        lambda dal: _Store(),
    )

    p = _by_id(
        compute_provider_health(_FakeDAL(_FakeBackend()), now=_WEDNESDAY),
        "seeking_alpha",
    )

    assert p["last_success_at"] == "2026-06-10T08:01:00+00:00"
    assert p["last_attempt_at"] == "2026-06-10T10:01:00+00:00"
    assert p["last_error"] == "market_news_extension_degraded"
    assert "FAILED" in p["detail"]
    assert p["signals"]["market_news_extension"] == {
        "latest_attempt_run_id": 302,
        "latest_attempt_outcome": "degraded",
        "latest_attempt_counts": {"failed_retryable": 4},
        "latest_complete_run_id": 301,
    }


def test_sa_provider_ignores_legacy_and_skipped_success_rows(monkeypatch):
    legacy = {
        "id": 311,
        "status": "succeeded",
        "started_at": "2026-06-10T09:00:00+00:00",
        "finished_at": "2026-06-10T09:01:00+00:00",
        "payload": {},
        "result": {"detail_failed": 18},
    }
    skipped = {
        "id": 312,
        "status": "succeeded",
        "started_at": "2026-06-10T10:00:00+00:00",
        "finished_at": "2026-06-10T10:01:00+00:00",
        "result": {
            "derived_outcome": "skipped",
            "healthy_anchor_eligible": False,
            "counts": {},
        },
    }

    class _Store:
        def latest_runs_by_name(self):
            return {"sa_market_news_refresh": legacy}

        def structured_extension_summary_by_name(self, job_names):
            return {
                "sa_market_news_refresh": {
                    "latest_attempt": skipped,
                    "latest_derived_complete": None,
                }
            }

    monkeypatch.setattr(
        "src.service.job_runs_store.get_job_runs_store",
        lambda dal: _Store(),
    )

    p = _by_id(
        compute_provider_health(_FakeDAL(_FakeBackend()), now=_WEDNESDAY),
        "seeking_alpha",
    )

    assert p["last_success_at"] is None
    assert p["last_attempt_at"] == "2026-06-10T10:01:00+00:00"
    assert p["status"] == "no_signal"
    assert p["signals"]["market_news_extension"]["latest_attempt_outcome"] == "skipped"


def test_section_failure_degrades_not_raises():
    dal = _FakeDAL(_FakeBackend(stats=RuntimeError("health query unavailable")))
    out = compute_provider_health(dal, now=_WEDNESDAY)
    assert any("query_health_stats failed" in n for n in out["notes"])
    assert len(out["providers"]) == 7            # all providers still listed
    assert _by_id(out, "sec_edgar")["status"] == "no_signal"


@pytest.mark.parametrize(("later_failure", "expected_status", "expected_attempt"), [
    (False, "partial", "2026-06-10T10:00:00+00:00"),
    (True, "failed", "2026-06-10T11:00:00+00:00"),
])
def test_direct_news_health_uses_provider_runs_and_current_ticker_errors(
    monkeypatch, tmp_path, news_runs, later_failure, expected_status, expected_attempt,
):
    monkeypatch.setenv("MASSIVE_API_KEY", "k")
    monkeypatch.setenv("FINNHUB_API_KEY", "k")
    news_runs("polygon", "2026-06-10T10:00:00+00:00", tickers_scanned=2)
    if later_failure:
        news_runs("polygon", "2026-06-10T11:00:00+00:00", status="failed", tickers_scanned=2)
    conn = sqlite3.connect(tmp_path / "market.db")
    try:
        conn.execute(
            "INSERT INTO provider_sync_meta (provider,ticker,interval,last_error,rows_added,updated_at) "
            "VALUES ('polygon','BAD','news','403',0,'2026-06-10T11:00:00+00:00')"
        )
        conn.commit()
    finally:
        conn.close()
    dal = _FakeDAL(_FakeBackend(stats=_stats(news_rows=[
        ("polygon", _WEDNESDAY - timedelta(hours=1), 50),
        ("finnhub", _WEDNESDAY - timedelta(hours=1), 50),
    ])))

    out = compute_provider_health(dal, now=_WEDNESDAY)

    massive = _by_id(out, "massive")
    assert massive["status"] == "connected"
    assert massive["last_success_at"] == "2026-06-10T10:00:00+00:00"
    assert massive["last_attempt_at"] == expected_attempt
    assert massive["last_error"] == "BAD: 403"
    assert _by_id(out, "finnhub")["status"] == "no_signal"
    direct = out["local_market"]["sync"]["news"]
    assert direct["status"] == expected_status
    assert direct["last_success"] == "2026-06-10T10:00:00+00:00"
    assert direct["last_attempt"] == expected_attempt
    assert direct["last_error"] == "polygon: BAD: 403"
    assert direct["rows_added"] == 0
    assert direct["providers"]["polygon"]["tickers_scanned"] == 2
    assert direct["providers"]["polygon"]["ticker_errors"] == [{
        "ticker": "BAD", "error": "403", "updated_at": "2026-06-10T11:00:00+00:00",
    }]


@pytest.mark.parametrize(("pid", "source", "key"), [
    ("massive", "polygon", "MASSIVE_API_KEY"),
    ("finnhub", "finnhub", "FINNHUB_API_KEY"),
])
def test_recent_publication_without_ingest_telemetry_is_no_signal(monkeypatch, tmp_path, pid, source, key):
    monkeypatch.setenv(key, "disposable-key")
    dal = _FakeDAL(_FakeBackend(stats=_stats(
        news_rows=[(source, _WEDNESDAY - timedelta(hours=1), 50)])))

    out = compute_provider_health(dal, now=_WEDNESDAY)
    provider = _by_id(out, pid)

    assert provider["status"] == "no_signal"
    assert provider["last_success_at"] is None
    assert provider["last_attempt_at"] is None
    assert provider["signals"]["news_recent_7d"] == 50
    assert provider["signals"]["news_latest"] == "2026-06-10T11:00:00+00:00"
    assert provider["signals"]["direct_sync"] is None
    assert out["local_market"]["sync"]["news"] is None
    assert not (tmp_path / "market.db").exists()


@pytest.mark.parametrize("legacy_news_present", [
    pytest.param(True, id="legacy-news-present"),
    pytest.param(False, id="legacy-news-absent"),
])
def test_health_clears_legacy_news_when_current_telemetry_read_fails(
    monkeypatch, tmp_path, legacy_news_present,
):
    from src.market_data_admin import _NEWS_SCHEMA, _PRICES_SCHEMA
    from src.tools.backends.sqlite_backend import SqliteBackend

    db = tmp_path / "market.db"
    conn = sqlite3.connect(db)
    try:
        conn.executescript(_NEWS_SCHEMA)
        conn.executescript(_PRICES_SCHEMA)
        conn.executescript(
            "CREATE TABLE market_sync_meta (domain TEXT PRIMARY KEY, last_success TEXT, "
            "last_error TEXT, rows_added INTEGER, updated_at TEXT);"
            "CREATE TABLE provider_sync_runs (provider TEXT, domain TEXT);"
            "INSERT INTO provider_sync_runs VALUES ('polygon','news');"
        )
        conn.execute(
            "INSERT INTO market_sync_meta VALUES (?,?,?,?,?)",
            ("prices", "2026-06-10T10:15:00Z", "price pacing", 26, "2026-06-10T10:16:00Z"),
        )
        if legacy_news_present:
            conn.execute(
                "INSERT INTO market_sync_meta VALUES (?,?,?,?,?)",
                ("news", "2001-01-01T01:00:00Z", "legacy news error", 7654321, "2001-01-01T02:00:00Z"),
            )
        conn.executemany(
            "INSERT INTO news (ticker,title,source,published_at,article_hash) VALUES (?,?,?,?,?)",
            [("AAPL", "Stored article", source, "2026-06-10T11:30:00+0000", source)
             for source in ("polygon", "finnhub")],
        )
        conn.execute(
            "INSERT INTO prices (ticker,datetime,interval,open,high,low,close,volume) "
            "VALUES ('AAPL','2026-06-10T11:45:00+0000','15min',10,12,9,11,100)"
        )
        conn.commit()
    finally:
        conn.close()
    before = db.read_bytes()
    monkeypatch.setattr("src.market_data_admin.read_sync_meta", _read_sync_meta)
    for key in ("MASSIVE_API_KEY", "FINNHUB_API_KEY"):
        monkeypatch.setenv(key, "disposable-key")
    monkeypatch.setenv("IBKR_HOST", "127.0.0.1")
    monkeypatch.setenv("IBKR_PORT", "4001")
    legacy = _read_sync_meta(str(db))
    if legacy_news_present:
        assert legacy["news"]["last_success"] == "2001-01-01T01:00:00Z"
        assert legacy["news"]["rows_added"] == 7654321
    else:
        assert legacy["news"] is None

    out = compute_provider_health(_FakeDAL(SqliteBackend(db)), now=_WEDNESDAY)

    assert out["local_market"]["db_exists"] is True
    assert any(note.startswith("market sync meta failed:") and "no such column" in note
               for note in out["notes"])
    sync = out["local_market"]["sync"]
    assert set(sync) == {"prices", "news", "fundamentals"}
    assert sync["prices"] == {
        "last_success": "2026-06-10T10:15:00Z", "last_error": "price pacing",
        "rows_added": 26, "updated_at": "2026-06-10T10:16:00Z",
        "authority": "local", "message": "Prices are served from local market_data.db.",
    }
    assert sync["fundamentals"] is None
    for pid in ("massive", "finnhub"):
        provider = _by_id(out, pid)
        assert provider["status"] == "no_signal"
        assert provider["last_success_at"] is None
        assert provider["last_attempt_at"] is None
        assert provider["signals"]["direct_sync"] is None
        assert provider["signals"]["news_latest"] == "2026-06-10T11:30:00+00:00"
    ibkr = _by_id(out, "ibkr")
    assert ibkr["status"] == "connected"
    assert ibkr["last_success_at"] == "2026-06-10T11:45:00+00:00"
    assert _read_sync_meta(str(db)) == legacy
    assert db.read_bytes() == before
    assert sync["news"] is None


def test_health_clears_legacy_news_when_db_exists_check_fails(monkeypatch, tmp_path):
    db = tmp_path / "market.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "CREATE TABLE market_sync_meta (domain TEXT PRIMARY KEY, last_success TEXT, "
            "last_error TEXT, rows_added INTEGER, updated_at TEXT)"
        )
        conn.executemany(
            "INSERT INTO market_sync_meta VALUES (?,?,?,?,?)",
            [
                ("news", "2001-01-01T01:00:00Z", "legacy news error", 7654321, "2001-01-01T02:00:00Z"),
                ("prices", "2026-06-10T10:15:00Z", "price pacing", 26, "2026-06-10T10:16:00Z"),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    before = db.read_bytes()
    monkeypatch.setattr("src.market_data_admin.read_sync_meta", _read_sync_meta)
    for key in ("MASSIVE_API_KEY", "FINNHUB_API_KEY"):
        monkeypatch.setenv(key, "disposable-key")

    class _UnreadablePath:
        def __init__(self, path):
            self.path = path

        def exists(self):
            raise PermissionError(f"cannot stat {self.path}")

    # Fail only health's probe, after the real legacy reader has returned.
    monkeypatch.setattr("src.service.provider_health.Path", _UnreadablePath)
    dal = _FakeDAL(_FakeBackend(stats=_stats(news_rows=[
        ("polygon", "2026-06-10T11:30:00+0000", 2),
        ("finnhub", "2026-06-10T11:30:00+0000", 3),
    ])))

    out = compute_provider_health(dal, now=_WEDNESDAY)

    assert out["local_market"]["db_exists"] is False
    assert f"market sync meta failed: cannot stat {db}" in out["notes"]
    sync = out["local_market"]["sync"]
    assert sync["prices"] == {
        "last_success": "2026-06-10T10:15:00Z", "last_error": "price pacing",
        "rows_added": 26, "updated_at": "2026-06-10T10:16:00Z",
        "authority": "local", "message": "Prices are served from local market_data.db.",
    }
    assert sync["fundamentals"] is None
    for pid in ("massive", "finnhub"):
        provider = _by_id(out, pid)
        assert provider["status"] == "no_signal"
        assert provider["last_success_at"] is None
        assert provider["last_attempt_at"] is None
        assert provider["signals"]["direct_sync"] is None
        assert provider["signals"]["news_latest"] == "2026-06-10T11:30:00+00:00"
    assert db.read_bytes() == before
    assert sync["news"] is None


def test_p0c_provider_health_marks_price_sync_retired(monkeypatch):
    monkeypatch.setattr("src.market_data_admin.read_sync_meta", lambda *a, **k: {
        "prices": {"last_success": "old", "last_error": None, "rows_added": 1, "updated_at": "old"}
    })

    out = compute_provider_health(_FakeDAL(_FakeBackend()), now=_WEDNESDAY)

    prices = out["local_market"]["sync"]["prices"]
    assert prices["authority"] == "local"
    assert prices["message"] == "Prices are served from local market_data.db."


def test_route_returns_aggregation(monkeypatch):
    from src.api.routes.health import providers_health
    dal = _FakeDAL(_FakeBackend())
    out = providers_health(dal=dal)
    assert {p["id"] for p in out["providers"]} == {
        "ibkr", "massive", "finnhub", "fred", "sec_edgar",
        "financial_datasets", "seeking_alpha"}
    assert "local_market" in out and "jobs" in out
