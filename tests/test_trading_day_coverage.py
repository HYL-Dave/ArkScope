"""Slice A — read-only trading-day / price-coverage diagnostics (no PG, no provider, no write).

Per-day universe transpose of the per-ticker coverage: for each calendar day in the window,
classify weekend/holiday/trading-day, session-complete, and count universe tickers full /
partial / missing — plus a provider_sync_meta error summary (the LC-style contract-unresolved
signal). Full/partial is measured against the per-day max bar count (self-calibrating for
half-days), so no brittle hardcoded session length.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from src.market_data_admin import _PRICES_SCHEMA
from src.market_data_direct import _ensure_provider_sync_tables, summarize_trading_day_coverage

_ET = ZoneInfo("America/New_York")


def _bars(conn, ticker, day, n, interval="15min"):
    for i in range(n):
        dt = f"{day}T{13 + i // 4:02d}:{(i % 4) * 15:02d}:00+0000"
        conn.execute(
            "INSERT OR IGNORE INTO prices(ticker,datetime,interval,open,high,low,close,volume) "
            "VALUES(?,?,?,?,?,?,?,?)", (ticker, dt, interval, 1, 1, 1, 1, 1))


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "market_data.db"
    conn = sqlite3.connect(path)
    conn.executescript(_PRICES_SCHEMA)
    _ensure_provider_sync_tables(conn)
    conn.execute("CREATE TABLE ticker_aliases (alias TEXT PRIMARY KEY, canonical TEXT NOT NULL)")
    conn.execute("INSERT INTO ticker_aliases VALUES ('BRK.B', 'BRK B')")
    # 6/17 Wed (complete trading): AAPL 26 full, BRK B 26 full, LC 0 missing
    _bars(conn, "AAPL", "2026-06-17", 26); _bars(conn, "BRK B", "2026-06-17", 26)
    # 6/18 Thu (complete): AAPL 26 full, BRK B 3 partial, LC 0 missing
    _bars(conn, "AAPL", "2026-06-18", 26); _bars(conn, "BRK B", "2026-06-18", 3)
    # 6/19 Fri = Juneteenth holiday · 6/20-21 weekend  → no bars
    # 6/22 Mon (complete): AAPL 26, BRK B 26, LC 0
    _bars(conn, "AAPL", "2026-06-22", 26); _bars(conn, "BRK B", "2026-06-22", 26)
    # 6/23 Tue (IN-PROGRESS): AAPL 10, BRK B 10  → session not complete
    _bars(conn, "AAPL", "2026-06-23", 10); _bars(conn, "BRK B", "2026-06-23", 10)
    # provider error for LC (recent IBKR contract unresolved)
    conn.execute(
        "INSERT INTO provider_sync_meta(provider,ticker,interval,last_success,last_bar_datetime,"
        "last_error,rows_added,updated_at) VALUES('ibkr','LC','15min',NULL,NULL,?,0,?)",
        ("contract not found (error 200)", "2026-06-23T16:00:00+0000"))
    conn.commit()
    conn.close()
    return str(path)


_UNIVERSE = ["AAPL", "BRK.B", "LC"]   # BRK.B alias → BRK B; LC has no bars


def _summary(db):
    # now_et 6/23 11:45 ET → 6/23 session in-progress (< 16:30); 6/17/18/22 complete.
    return summarize_trading_day_coverage(
        _UNIVERSE, interval="15min", lookback_days=6, db_path=db,
        today=date(2026, 6, 23), now_et=datetime(2026, 6, 23, 11, 45, tzinfo=_ET))


def _day(summary, d):
    return next(x for x in summary["days"] if x["date"] == d)


def test_universe_count_dedupes_aliases(db):
    # BRK.B canonicalises to BRK B → 3 distinct tickers, not 4.
    assert _summary(db)["universe_count"] == 3


def test_days_newest_first_and_window(db):
    days = [d["date"] for d in _summary(db)["days"]]
    assert days == ["2026-06-23", "2026-06-22", "2026-06-21", "2026-06-20",
                    "2026-06-19", "2026-06-18", "2026-06-17"]


def test_weekend_and_holiday_marked_non_trading(db):
    s = _summary(db)
    assert _day(s, "2026-06-20")["is_trading_day"] is False
    assert _day(s, "2026-06-20")["reason"] == "weekend"
    jun = _day(s, "2026-06-19")
    assert jun["is_trading_day"] is False and jun["reason"] == "us_market_holiday"
    assert jun["holiday"] == "Juneteenth National Independence Day"


def test_complete_trading_day_full_missing_counts(db):
    d = _day(_summary(db), "2026-06-22")
    assert d["is_trading_day"] and d["session_complete"] is True
    assert d["max_observed_bar_count"] == 26  # per-day max (renamed from full_bar_count)
    assert "full_bar_count" not in d
    assert d["full"] == 2 and d["partial"] == 0 and d["missing"] == 1
    assert d["missing_tickers"] == ["LC"]     # 0 bars on a complete trading day
    assert d["coverage_status"] == "partial"  # A.2: covered 2/3 < 0.9 (LC perma-missing) → not falsely complete


def test_coverage_status_non_trading_and_in_progress(db):
    s = _summary(db)
    assert _day(s, "2026-06-20")["coverage_status"] == "non_trading"   # weekend
    assert _day(s, "2026-06-19")["coverage_status"] == "non_trading"   # holiday
    assert _day(s, "2026-06-23")["coverage_status"] == "in_progress"   # < 16:30 ET → not judged thin


def test_uniformly_thin_day_not_read_as_complete(tmp_path):
    # THE TRAP (A.1): every universe ticker has only 3 bars on a complete trading day. The
    # per-day-max design would make full=all/partial=0 — looking complete. coverage_status
    # must flag it 'thin' and max_observed_bar_count must be the honest 3.
    path = tmp_path / "market_data.db"
    conn = sqlite3.connect(path)
    conn.executescript(_PRICES_SCHEMA)
    _ensure_provider_sync_tables(conn)
    for t in ("AAPL", "BRK B", "LC"):
        _bars(conn, t, "2026-06-22", 3)
    conn.commit()
    conn.close()
    out = summarize_trading_day_coverage(
        ["AAPL", "BRK B", "LC"], interval="15min", lookback_days=2, db_path=str(path),
        today=date(2026, 6, 23), now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET))
    d = next(x for x in out["days"] if x["date"] == "2026-06-22")
    assert d["max_observed_bar_count"] == 3
    assert d["coverage_status"] == "thin"     # NOT complete_like, despite full==all
    assert d["missing"] == 0                  # all present, just thin


def test_outlier_full_does_not_mask_thin_universe(tmp_path):
    # THE 6/25 TRAP: one freshly-synced ticker is fully covered (26 bars) while the rest of the
    # universe is thin (5 bars). day_max=26 ≥ threshold would read complete_like off the MAX
    # alone — but only 1/5 present tickers is well-covered, so the day is PARTIAL, not complete.
    path = tmp_path / "market_data.db"
    conn = sqlite3.connect(path)
    conn.executescript(_PRICES_SCHEMA); _ensure_provider_sync_tables(conn)
    _bars(conn, "HAPN", "2026-06-22", 26)                 # outlier: fully covered
    for t in ("AAPL", "BRK B", "NVDA", "MSFT"):
        _bars(conn, t, "2026-06-22", 5)                   # the rest: thin
    conn.commit(); conn.close()
    out = summarize_trading_day_coverage(
        ["HAPN", "AAPL", "BRK B", "NVDA", "MSFT"], interval="15min", lookback_days=2,
        db_path=str(path), today=date(2026, 6, 23), now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET))
    d = next(x for x in out["days"] if x["date"] == "2026-06-22")
    assert d["max_observed_bar_count"] == 26
    assert d["coverage_status"] == "partial"              # NOT complete_like — 1/5 well-covered
    assert d["well_covered"] == 1                         # new distribution signal
    assert d["missing"] == 0                              # all present, just uneven


def test_complete_when_most_present_well_covered_despite_one_laggard(tmp_path):
    # inverse: a lone thin ticker among many full ones does NOT downgrade the day — it shows up
    # as partial_tickers but the day stays complete_like (≥ the well-covered ratio threshold).
    path = tmp_path / "market_data.db"
    conn = sqlite3.connect(path)
    conn.executescript(_PRICES_SCHEMA); _ensure_provider_sync_tables(conn)
    full = ["AAPL", "BRK B", "NVDA", "MSFT", "TSLA", "AMD", "GOOG", "META", "AMZN"]
    for t in full:
        _bars(conn, t, "2026-06-22", 26)                  # 9 full
    _bars(conn, "LAG", "2026-06-22", 4)                   # 1 thin → 9/10 well-covered = 0.9
    conn.commit(); conn.close()
    out = summarize_trading_day_coverage(
        full + ["LAG"], interval="15min", lookback_days=2, db_path=str(path),
        today=date(2026, 6, 23), now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET))
    d = next(x for x in out["days"] if x["date"] == "2026-06-22")
    assert d["coverage_status"] == "complete_like"        # 9/10 well-covered ≥ ratio
    assert d["well_covered"] == 9 and d["partial"] == 1


def test_large_missing_fraction_is_partial_not_complete(tmp_path):
    # A.2: most of the universe is MISSING (8/10) though the 2 present are fully covered.
    # well-ratio alone (2/2 = 100%) would read complete — the covered-ratio gate must catch the
    # large-scale missing and flag the day 'partial' (too optimistic to call it complete).
    path = tmp_path / "market_data.db"
    conn = sqlite3.connect(path)
    conn.executescript(_PRICES_SCHEMA); _ensure_provider_sync_tables(conn)
    _bars(conn, "AAPL", "2026-06-22", 26); _bars(conn, "MSFT", "2026-06-22", 26)
    universe = ["AAPL", "MSFT"] + [f"T{i}" for i in range(8)]   # 8 never get bars → missing
    conn.commit(); conn.close()
    out = summarize_trading_day_coverage(
        universe, interval="15min", lookback_days=2, db_path=str(path),
        today=date(2026, 6, 23), now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET))
    d = next(x for x in out["days"] if x["date"] == "2026-06-22")
    assert d["covered"] == 2 and d["missing"] == 8
    assert d["well_covered"] == 2                          # present ones are full
    assert d["coverage_status"] == "partial"              # covered 2/10 < 0.9 → NOT complete


def test_single_gap_in_large_universe_stays_complete(tmp_path):
    # A.2 intent: a lone LC-type gap must NOT downgrade a large, otherwise-full universe.
    path = tmp_path / "market_data.db"
    conn = sqlite3.connect(path)
    conn.executescript(_PRICES_SCHEMA); _ensure_provider_sync_tables(conn)
    universe = [f"T{i}" for i in range(20)]
    for t in universe[:19]:
        _bars(conn, t, "2026-06-22", 26)                  # 19 full, universe[19] missing
    conn.commit(); conn.close()
    out = summarize_trading_day_coverage(
        universe, interval="15min", lookback_days=2, db_path=str(path),
        today=date(2026, 6, 23), now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET))
    d = next(x for x in out["days"] if x["date"] == "2026-06-22")
    assert d["covered"] == 19 and d["missing"] == 1
    assert d["coverage_status"] == "complete_like"        # covered 19/20 = 0.95 ≥ 0.9 → still complete


def test_partial_day_lists_thin_ticker(db):
    d = _day(_summary(db), "2026-06-18")
    assert d["full"] == 1 and d["missing"] == 1
    assert d["partial"] == 1
    assert d["partial_tickers"] == [{"ticker": "BRK B", "bars": 3}]


def test_in_progress_today_flagged_incomplete(db):
    d = _day(_summary(db), "2026-06-23")
    assert d["is_trading_day"] is True
    assert d["session_complete"] is False     # before 16:30 ET → in-progress, not a gap


def test_provider_errors_surface_lc(db):
    errs = _summary(db)["provider_errors"]
    lc = next(e for e in errs if e["ticker"] == "LC")
    assert "contract not found" in lc["last_error"] and lc["interval"] == "15min"


def test_thin_threshold_uses_normalized_interval(tmp_path):
    # caller passes the provider label "15 mins" → data reads as the normalized "15min"
    # (_INTERVAL_DB), so the thin threshold must also normalize — else a thin day on a
    # "15 mins" query silently never flags. Stored interval is the normalized "15min".
    path = tmp_path / "market_data.db"
    conn = sqlite3.connect(path)
    conn.executescript(_PRICES_SCHEMA)
    _ensure_provider_sync_tables(conn)
    for t in ("AAPL", "BRK B"):
        _bars(conn, t, "2026-06-22", 3, interval="15min")   # stored normalized
    conn.commit()
    conn.close()
    out = summarize_trading_day_coverage(
        ["AAPL", "BRK B"], interval="15 mins", lookback_days=2, db_path=str(path),
        today=date(2026, 6, 23), now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET))
    d = next(x for x in out["days"] if x["date"] == "2026-06-22")
    assert d["max_observed_bar_count"] == 3        # data WAS read (interval normalized)
    assert d["coverage_status"] == "thin"          # and the thin check fired (threshold normalized too)


def test_route_wires_universe_and_db(db, monkeypatch):
    # the route resolves the active universe + market DB path and returns the summary shape.
    import src.api.routes.market_data as mroutes
    import src.universe_scope as us
    monkeypatch.setattr(us, "resolve_active_universe", lambda: list(_UNIVERSE))
    monkeypatch.setattr(mroutes, "resolve_market_db_path", lambda: db)
    monkeypatch.setattr(
        mroutes,
        "summarize_trading_day_coverage",
        lambda universe, **kwargs: summarize_trading_day_coverage(
            universe,
            **kwargs,
            today=date(2026, 6, 23),
            now_et=datetime(2026, 6, 23, 11, 45, tzinfo=_ET),
        ),
    )
    out = mroutes.market_data_trading_days(lookback_days=6, interval="15min")
    assert out["universe_count"] == 3 and out["interval"] == "15min"
    assert any(d["date"] == "2026-06-22" for d in out["days"])
    assert any(e["ticker"] == "LC" for e in out["provider_errors"])


def test_route_unavailable_returns_sanitized_503(monkeypatch):
    from fastapi import HTTPException

    import src.api.routes.market_data as mroutes
    import src.universe_scope as universe_scope
    from src.active_universe import ActiveUniverseUnavailable

    calls = {"scope": 0, "db": 0, "summary": 0}
    unavailable = ActiveUniverseUnavailable({
        "manual_lists": "source_db_unreadable",
        "sa_alpha_picks_current": "source_db_missing",
    })

    def _unavailable():
        calls["scope"] += 1
        raise unavailable

    def _db_path():
        calls["db"] += 1
        return "/unused/market_data.db"

    def _summary(*args, **kwargs):
        calls["summary"] += 1
        return {"universe_count": -1}

    monkeypatch.setattr(universe_scope, "resolve_active_universe", _unavailable)
    monkeypatch.setattr(mroutes, "resolve_market_db_path", _db_path)
    monkeypatch.setattr(mroutes, "summarize_trading_day_coverage", _summary)

    with pytest.raises(HTTPException) as caught:
        mroutes.market_data_trading_days(lookback_days=6, interval="15min")

    assert caught.value.status_code == 503
    assert caught.value.detail == unavailable.as_dict()
    assert calls == {"scope": 1, "db": 0, "summary": 0}


def test_route_complete_empty_is_not_unavailable(tmp_path, monkeypatch):
    import src.api.routes.market_data as mroutes
    import src.universe_scope as universe_scope

    calls = {"scope": 0, "db": 0, "summary": 0}
    def _complete_empty():
        calls["scope"] += 1
        return []

    def _db_path():
        calls["db"] += 1
        return str(tmp_path / "complete-empty-market-data.db")

    def _summary(universe, **kwargs):
        calls["summary"] += 1
        assert universe == []
        return summarize_trading_day_coverage(
            universe,
            **kwargs,
            today=date(2026, 6, 23),
            now_et=datetime(2026, 6, 23, 11, 45, tzinfo=_ET),
        )

    monkeypatch.setattr(universe_scope, "resolve_active_universe", _complete_empty)
    monkeypatch.setattr(mroutes, "resolve_market_db_path", _db_path)
    monkeypatch.setattr(mroutes, "summarize_trading_day_coverage", _summary)

    result = mroutes.market_data_trading_days(lookback_days=6, interval="15min")
    assert result["universe_count"] == 0
    assert result["provider_errors"] == []
    assert calls == {"scope": 1, "db": 1, "summary": 1}


def test_route_registered():
    import src.api.routes.market_data as mroutes
    assert "/market-data/trading-days" in {r.path for r in mroutes.router.routes}


def test_read_only_absent_db_is_honest(tmp_path):
    out = summarize_trading_day_coverage(
        _UNIVERSE, db_path=str(tmp_path / "nope.db"), lookback_days=3,
        today=date(2026, 6, 23), now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET))
    assert out["universe_count"] == 3
    # absent DB → trading days show all-missing, non-trading days still marked
    tradeday = next(d for d in out["days"] if d["is_trading_day"] and d["session_complete"])
    assert tradeday["missing"] == 3 and tradeday["full"] == 0
    assert tradeday["coverage_status"] == "missing"   # complete trading day, zero coverage
    assert out["provider_errors"] == []
