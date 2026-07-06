"""Slice #2a — market_data_direct hermetic core (PG-free, no live Gateway).

Covers: WAL-safe backup, preflight_canonicalize, _normalize_utc (the byte-match
invariant + DST), detect_price_gaps (day-presence, weekend/holiday aware), and the
provider_sync_runs/provider_sync_meta telemetry tables. NO provider fetch, NO
scheduler — those are 2b.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone

import pytest

import src.market_data_admin as mda
import src.market_data_direct as mdd


# --- _normalize_utc: byte-identical to PG TO_CHAR + DST-correct (THE invariant) ----

def test_normalize_utc_edt_summer():
    # naive ET summer (EDT, UTC-4): 09:30 → 13:30Z
    assert mdd._normalize_utc(datetime(2026, 6, 22, 9, 30, 0)) == "2026-06-22T13:30:00+0000"


def test_normalize_utc_est_winter():
    # naive ET winter (EST, UTC-5): 09:30 → 14:30Z (guards a hardcoded -4)
    assert mdd._normalize_utc(datetime(2026, 1, 15, 9, 30, 0)) == "2026-01-15T14:30:00+0000"


def test_normalize_utc_already_aware_utc_idempotent():
    aware = datetime(2026, 6, 22, 13, 30, 0, tzinfo=timezone.utc)
    assert mdd._normalize_utc(aware) == "2026-06-22T13:30:00+0000"


def test_normalize_utc_format_matches_pg_literal():
    # the exact shape PG's TO_CHAR(... 'YYYY-MM-DD"T"HH24:MI:SS+0000') produces:
    # 'T' separator, '+0000' (no colon) offset.
    s = mdd._normalize_utc(datetime(2026, 6, 22, 9, 30, 0))
    assert s[10] == "T" and s.endswith("+0000") and ":" not in s.split("T")[1][8:]


def test_normalize_utc_polygon_epoch_matches_ibkr_path():
    # cross-provider convergence: the SAME instant from Polygon epoch-ms and IBKR
    # naive-ET produce a byte-identical PK string.
    epoch_ms = int(datetime(2026, 6, 22, 13, 30, 0, tzinfo=timezone.utc).timestamp() * 1000)
    poly = mdd._normalize_utc(datetime.fromtimestamp(epoch_ms / 1000, timezone.utc))
    ibkr = mdd._normalize_utc(datetime(2026, 6, 22, 9, 30, 0))
    assert poly == ibkr == "2026-06-22T13:30:00+0000"


# --- preflight_canonicalize: local-only, reuses slice-1 helpers --------------------

def _live_shaped_db(path, news_rows=None):
    conn = sqlite3.connect(path)
    conn.executescript(mda._PRICES_SCHEMA)
    conn.executescript(
        "CREATE TABLE news (id INTEGER PRIMARY KEY, ticker TEXT NOT NULL, title TEXT NOT NULL, "
        "source TEXT NOT NULL, published_at TEXT NOT NULL);"
    )
    conn.execute("INSERT INTO prices (ticker,datetime,interval,open,high,low,close,volume) "
                 "VALUES ('BRK B','2026-06-01T13:30:00+0000','15min',1,1,1,9,100)")
    for nid, tk in (news_rows or [(1, "BRK B"), (2, "AAPL")]):
        conn.execute("INSERT INTO news (id,ticker,title,source,published_at) VALUES (?,?,?,?,?)",
                     (nid, tk, "t", "polygon", "2026-06-01T12:00:00+0000"))
    conn.commit()
    conn.close()


def test_preflight_missing_db_is_noop_success(tmp_path):
    res = mdd.preflight_canonicalize(str(tmp_path / "nope.db"))
    assert res["ok"] is True and res["exists"] is False
    assert not (tmp_path / "nope.db").exists()


def test_preflight_creates_aliases_on_clean_db(tmp_path):
    db = tmp_path / "m.db"
    _live_shaped_db(db)  # canonical-only (mirrors the real live DB today)
    res = mdd.preflight_canonicalize(str(db))
    assert res["ok"] is True and res["created_aliases"] is True
    conn = sqlite3.connect(db)
    aliases = dict(conn.execute("SELECT alias, canonical FROM ticker_aliases").fetchall())
    assert aliases.get("BRK.B") == "BRK B"  # table seeded so read-side _canon works
    assert res["folded"]["prices"] == 0     # clean history → nothing folded
    conn.close()


def test_preflight_folds_pre_canon_news_pk_safe(tmp_path):
    db = tmp_path / "m.db"
    _live_shaped_db(db, news_rows=[(1, "BRK B"), (2, "BRK.B"), (3, "AAPL")])  # both forms (live news)
    res = mdd.preflight_canonicalize(str(db))
    assert res["folded"]["news"] == 1  # BRK.B reconciled
    conn = sqlite3.connect(db)
    tickers = sorted(r[0] for r in conn.execute("SELECT ticker FROM news").fetchall())
    assert tickers == ["AAPL", "BRK B", "BRK B"]  # canonical, none lost
    conn.close()


def test_preflight_idempotent_second_run_noop(tmp_path):
    db = tmp_path / "m.db"
    _live_shaped_db(db, news_rows=[(1, "BRK B"), (2, "BRK.B")])
    mdd.preflight_canonicalize(str(db))
    res2 = mdd.preflight_canonicalize(str(db))
    assert res2["created_aliases"] is False
    assert all(v == 0 for v in res2["folded"].values())  # nothing left to fold


def test_preflight_touches_no_pg(tmp_path, monkeypatch):
    # local-only (lock 8): a PG dial must never happen on this path.
    db = tmp_path / "m.db"
    _live_shaped_db(db)
    monkeypatch.setattr(mda, "_pg_conn", lambda: (_ for _ in ()).throw(AssertionError("PG touched")))
    res = mdd.preflight_canonicalize(str(db))
    assert res["ok"] is True


# --- backup_market_db: WAL-safe (SQLite backup API, not shutil.copyfile) -----------

def test_backup_is_wal_safe_captures_uncheckpointed_rows(tmp_path):
    # rows written in WAL but NOT checkpointed must be in the backup — a raw file copy
    # of the .db would miss them. Uses the SQLite backup API.
    src = tmp_path / "m.db"
    conn = sqlite3.connect(src)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(mda._PRICES_SCHEMA)
    conn.execute("INSERT INTO prices (ticker,datetime,interval,open,high,low,close,volume) "
                 "VALUES ('AAPL','2026-06-01T13:30:00+0000','15min',1,1,1,1,1)")
    conn.commit()  # in WAL, not checkpointed; keep conn OPEN (holds the WAL)
    dest = mdd.backup_market_db(str(src), str(tmp_path / "backup.db"))
    n = sqlite3.connect(dest).execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    assert n == 1  # WAL-safe: the uncheckpointed row is in the backup
    conn.close()


def test_backup_missing_src_returns_none(tmp_path):
    assert mdd.backup_market_db(str(tmp_path / "nope.db"), str(tmp_path / "b.db")) is None


def test_backup_refuses_to_overwrite_existing_destination(tmp_path):
    src = tmp_path / "source.db"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.commit()
    conn.close()
    dest = tmp_path / "protected.db"
    dest.write_bytes(b"do-not-clobber")

    with pytest.raises(FileExistsError):
        mdd.backup_market_db(str(src), str(dest), overwrite=False)

    assert dest.read_bytes() == b"do-not-clobber"


# --- detect_price_gaps: day-presence, weekend/holiday aware (NOT 26-bar count) ------

def _prices_db(tmp_path, rows):
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    conn.executescript(mda._PRICES_SCHEMA)
    mda._ensure_ticker_aliases(conn)
    conn.executemany(
        "INSERT INTO prices (ticker,datetime,interval,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?,?)",
        rows)
    conn.commit()
    conn.close()
    return db


def test_gaps_missing_midweek_day(tmp_path):
    # AAPL has bars Mon 6/15 + Wed 6/17 but NOT Tue 6/16 (all regular trading days)
    db = _prices_db(tmp_path, [
        ("AAPL", "2026-06-15T13:30:00+0000", "15min", 1, 1, 1, 1, 1),
        ("AAPL", "2026-06-17T13:30:00+0000", "15min", 1, 1, 1, 1, 1),
    ])
    gaps = mdd.detect_price_gaps(["AAPL"], lookback_days=10, db_path=str(db), today=date(2026, 6, 18))
    assert date(2026, 6, 16) in gaps["AAPL"]            # the real missing trading day
    assert date(2026, 6, 13) not in gaps["AAPL"]        # Saturday — not a gap
    assert date(2026, 6, 19) not in gaps["AAPL"]        # Juneteenth holiday — not a gap


def test_gaps_one_bar_counts_as_present(tmp_path):
    # lock 3: presence, not a 26-bar count — a single bar on a day means "covered".
    db = _prices_db(tmp_path, [("AAPL", "2026-06-17T13:30:00+0000", "15min", 1, 1, 1, 1, 1)])
    gaps = mdd.detect_price_gaps(["AAPL"], lookback_days=1, db_path=str(db), today=date(2026, 6, 18))
    assert date(2026, 6, 17) not in gaps["AAPL"]


def test_gaps_resolves_alias_ticker(tmp_path):
    # querying 'BRK.B' must look at the canonical 'BRK B' rows. Window = today only
    # (lookback 0) so the single covered day is the whole window → no gaps.
    db = _prices_db(tmp_path, [("BRK B", "2026-06-17T13:30:00+0000", "15min", 1, 1, 1, 1, 1)])
    gaps = mdd.detect_price_gaps(["BRK.B"], lookback_days=0, db_path=str(db), today=date(2026, 6, 17))
    assert gaps["BRK.B"] == []  # resolved to canonical → covered


def test_gaps_missing_table_reports_all_trading_days(tmp_path):
    db = tmp_path / "empty.db"
    sqlite3.connect(db).close()
    gaps = mdd.detect_price_gaps(["AAPL"], lookback_days=3, db_path=str(db), today=date(2026, 6, 18))
    # window 6/15..6/18: 6/15 Mon, 6/16 Tue, 6/17 Wed, 6/18 Thu are all trading days →
    # all missing (no prices table). (6/13-14 weekend excluded by being out of window.)
    assert set(gaps["AAPL"]) == {date(2026, 6, 15), date(2026, 6, 16), date(2026, 6, 17), date(2026, 6, 18)}


def test_gaps_empty_tickers_returns_empty(tmp_path):
    db = _prices_db(tmp_path, [])
    assert mdd.detect_price_gaps([], db_path=str(db), today=date(2026, 6, 18)) == {}


# --- provider_sync tables: NEW, NOT market_sync_meta (lock 5) ----------------------

def test_provider_sync_tables_idempotent(tmp_path):
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    mdd._ensure_provider_sync_tables(conn)
    mdd._ensure_provider_sync_tables(conn)  # second run no error
    tbls = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"provider_sync_runs", "provider_sync_meta"} <= tbls
    assert "market_sync_meta" not in tbls  # must NOT touch the PG-mirror table
    conn.close()


def test_provider_sync_meta_upsert_then_update(tmp_path):
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    mdd._ensure_provider_sync_tables(conn)
    mdd._upsert_provider_meta(conn, provider="ibkr", ticker="AAPL", interval="15min",
                              last_bar_datetime="2026-06-17T13:30:00+0000", rows_added=5, error=None)
    mdd._upsert_provider_meta(conn, provider="ibkr", ticker="AAPL", interval="15min",
                              last_bar_datetime="2026-06-18T13:30:00+0000", rows_added=3, error=None)
    row = conn.execute("SELECT last_bar_datetime, rows_added FROM provider_sync_meta "
                       "WHERE provider='ibkr' AND ticker='AAPL' AND interval='15min'").fetchone()
    assert row == ("2026-06-18T13:30:00+0000", 3)  # upsert, single row
    assert conn.execute("SELECT COUNT(*) FROM provider_sync_meta").fetchone()[0] == 1
    conn.close()


def test_provider_sync_meta_error_preserves_last_success(tmp_path):
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    mdd._ensure_provider_sync_tables(conn)
    mdd._upsert_provider_meta(conn, provider="ibkr", ticker="AAPL", interval="15min",
                              last_bar_datetime="2026-06-17T13:30:00+0000", rows_added=5, error=None)
    s1 = conn.execute("SELECT last_success FROM provider_sync_meta WHERE ticker='AAPL'").fetchone()[0]
    mdd._upsert_provider_meta(conn, provider="ibkr", ticker="AAPL", interval="15min",
                              last_bar_datetime=None, rows_added=0, error="gateway down")
    row = conn.execute("SELECT last_success, last_error FROM provider_sync_meta WHERE ticker='AAPL'").fetchone()
    assert row[0] == s1 and row[1] == "gateway down"  # last_success preserved on error
    conn.close()


def test_provider_sync_run_lifecycle(tmp_path):
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    mdd._ensure_provider_sync_tables(conn)
    rid = mdd._start_provider_run(conn, provider="ibkr", interval="15min")
    assert isinstance(rid, int)
    assert conn.execute("SELECT status FROM provider_sync_runs WHERE id=?", (rid,)).fetchone()[0] == "running"
    mdd._finish_provider_run(conn, rid, status="succeeded", tickers_scanned=10,
                             gaps_found=3, rows_added=42, error=None)
    row = conn.execute("SELECT status, rows_added, finished_at FROM provider_sync_runs WHERE id=?",
                       (rid,)).fetchone()
    assert row[0] == "succeeded" and row[1] == 42 and row[2] is not None
    conn.close()


def test_reconcile_interrupted_provider_runs_marks_stale_running(tmp_path):
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    mdd._ensure_provider_sync_tables(conn)
    stale_id = mdd._start_provider_run(conn, provider="ibkr", interval="news", domain="news")
    fresh_id = mdd._start_provider_run(conn, provider="polygon", interval="news", domain="news")
    conn.execute(
        "UPDATE provider_sync_runs SET started_at=? WHERE id=?",
        ("2026-06-24T10:00:00+00:00", stale_id),
    )
    conn.execute(
        "UPDATE provider_sync_runs SET started_at=? WHERE id=?",
        ("2026-06-24T12:00:00+00:00", fresh_id),
    )
    conn.commit()

    changed = mdd._reconcile_interrupted_provider_runs(
        conn,
        started_before="2026-06-24T11:00:00+00:00",
        error="provider worker interrupted before terminal telemetry",
    )

    assert changed == [stale_id]
    stale = conn.execute(
        "SELECT status,finished_at,error FROM provider_sync_runs WHERE id=?",
        (stale_id,),
    ).fetchone()
    assert stale[0] == "failed"
    assert stale[1] is not None
    assert stale[2] == "provider worker interrupted before terminal telemetry"
    assert conn.execute(
        "SELECT status FROM provider_sync_runs WHERE id=?", (fresh_id,)
    ).fetchone()[0] == "running"
    conn.close()


def test_provider_run_status_constrained_to_valid_set(tmp_path):
    # JobRunsStore only allows running/succeeded/failed — 'partial' is NOT a status here.
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    mdd._ensure_provider_sync_tables(conn)
    rid = mdd._start_provider_run(conn, provider="ibkr", interval="15min")
    with pytest.raises(ValueError):
        mdd._finish_provider_run(conn, rid, status="partial", tickers_scanned=1,
                                 gaps_found=0, rows_added=0, error=None)
    conn.close()


def test_provider_sync_runs_status_check_enforced_at_schema(tmp_path):
    # Defense-in-depth: the SQLite schema itself rejects an invalid status, not only
    # the _finish_provider_run Python guard. A raw INSERT (bypassing the helper) of a
    # bogus status must raise IntegrityError.
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    mdd._ensure_provider_sync_tables(conn)
    # valid statuses insert fine
    for st in ("running", "succeeded", "failed"):
        conn.execute("INSERT INTO provider_sync_runs (provider, interval, started_at, status) "
                     "VALUES ('ibkr','15min','2026-06-24T00:00:00+0000',?)", (st,))
    # an invalid status is rejected by the schema CHECK
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO provider_sync_runs (provider, interval, started_at, status) "
                     "VALUES ('ibkr','15min','2026-06-24T00:00:00+0000','partial')")
    conn.close()


# --- market_write_lock: serializes market_data.db writes vs the PG mirror (2b step 1) ---

def test_market_write_lock_acquires_and_releases(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    with mdd.market_write_lock(timeout=2):
        pass  # acquire + release cleanly, no error
    # after release, re-acquire works
    with mdd.market_write_lock(timeout=2):
        pass


def test_market_write_lock_actually_flocks_the_shared_file(tmp_path, monkeypatch):
    # while held, a raw flock on the SAME lock file must fail — proving the lock is
    # engaged on the file the scheduler's _local_refresh mirror also uses.
    import fcntl
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    with mdd.market_write_lock(timeout=2):
        lockfile = tmp_path / "locks" / "local_refresh.lock"
        assert lockfile.exists()
        fh = open(lockfile, "a+")
        try:
            with pytest.raises(OSError):  # already exclusively locked → EWOULDBLOCK
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            fh.close()


def test_market_write_lock_shares_scheduler_lock_file_path(monkeypatch, tmp_path):
    # the mutex-sharing invariant: market_write_lock must flock the EXACT file the
    # scheduler's _LOCAL_REFRESH_FLOCK ("local_refresh") uses, or they wouldn't serialize.
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    from src.service.data_scheduler import _lock_dir as ds_lock_dir
    assert mdd._market_lock_path() == ds_lock_dir() / "local_refresh.lock"


# --- 2b·2: provider mappers + backfill_prices_direct orchestration (fake providers) ---

from types import SimpleNamespace


def _bar(dt, o=1.0, h=2.0, l=0.5, c=1.5, v=100):
    return SimpleNamespace(ticker="X", datetime=dt, open=o, high=h, low=l, close=c, volume=v)


class _FakeIBKR:
    def __init__(self, bars_by_ticker=None, raises_for=None):
        self._bars = bars_by_ticker or {}
        self._raises = set(raises_for or ())
        self.calls = []

    def fetch_historical_intraday(self, tickers, start_date, end_date, interval="15 mins", **k):
        self.calls.append((tuple(tickers), start_date, end_date, interval))
        out = {}
        for t in tickers:
            if t in self._raises:
                raise RuntimeError(f"gateway error for {t}")
            # faithful to real IBKR: only return bars within the requested [start,end] range
            out[t] = [b for b in self._bars.get(t, []) if start_date <= b.datetime.date() <= end_date]
        return out


class _FakePolygon:
    def __init__(self, results_by_day=None):
        self._r = results_by_day or {}
        self.calls = []

    def fetch_intraday_prices(self, ticker, trade_date, multiplier=15, timespan="minute", **k):
        self.calls.append((ticker, trade_date, multiplier, timespan))
        return self._r.get(trade_date, [])


def test_ibkr_bars_to_rows_canonical_utc_pk():
    rows = mdd._ibkr_bars_to_rows("BRK B", [_bar(datetime(2026, 6, 17, 9, 30, 0))], "15min")
    assert rows == [("BRK B", "2026-06-17T13:30:00+0000", "15min", 1.0, 2.0, 0.5, 1.5, 100)]


def test_ibkr_bars_to_rows_skips_nan_ohlc_coerces_nan_volume():
    nan = float("nan")
    rows = mdd._ibkr_bars_to_rows("AAPL", [
        _bar(datetime(2026, 6, 17, 9, 30, 0), c=nan),          # NaN close → skipped
        _bar(datetime(2026, 6, 17, 9, 45, 0), v=nan),          # NaN volume → coerced to 0
    ], "15min")
    assert len(rows) == 1 and rows[0][1] == "2026-06-17T13:45:00+0000" and rows[0][7] == 0


def test_polygon_results_use_raw_epoch_not_mutated_datetime():
    # the lock-#2 trap: must use raw 't' (epoch-ms UTC), NOT polygon_source's local-naive
    # item['datetime']. Inject a bogus 'datetime' to prove it's ignored.
    epoch_ms = int(datetime(2026, 6, 17, 13, 30, 0, tzinfo=timezone.utc).timestamp() * 1000)
    results = [{"t": epoch_ms, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 9,
                "datetime": datetime(1999, 1, 1)}]  # bogus mutated field — must be ignored
    rows = mdd._polygon_results_to_rows("AAPL", results, "15min")
    assert rows == [("AAPL", "2026-06-17T13:30:00+0000", "15min", 1.0, 2.0, 0.5, 1.5, 9)]


def _backfill_db(tmp_path):
    db = tmp_path / "market_data.db"
    conn = sqlite3.connect(db)
    conn.executescript(mda._PRICES_SCHEMA)
    conn.commit()
    conn.close()
    return db


def test_backfill_inserts_canonical_rows_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    ibkr = _FakeIBKR(bars_by_ticker={"AAPL": [_bar(datetime(2026, 6, 17, 9, 30, 0))]})
    res = mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=2, provider="ibkr",
                                     db_path=str(db), ibkr_src=ibkr, today=date(2026, 6, 18))
    assert res["rows_added"] == 1
    conn = sqlite3.connect(db)
    row = conn.execute("SELECT ticker, datetime, interval FROM prices").fetchone()
    assert row == ("AAPL", "2026-06-17T13:30:00+0000", "15min")
    conn.close()
    # idempotent: a second run inserts 0 (INSERT OR IGNORE on the identical PK)
    res2 = mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=2, provider="ibkr",
                                      db_path=str(db), ibkr_src=ibkr, today=date(2026, 6, 18))
    assert res2["rows_added"] == 0


def test_backfill_canonicalizes_ticker_before_insert(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    # provider keyed by the CANONICAL spelling (the scope is canonicalized before fetch)
    ibkr = _FakeIBKR(bars_by_ticker={"BRK B": [_bar(datetime(2026, 6, 17, 9, 30, 0))]})
    res = mdd.backfill_prices_direct(tickers_arg="BRK.B", lookback_days=2, provider="ibkr",
                                     db_path=str(db), ibkr_src=ibkr, today=date(2026, 6, 18))
    assert res["rows_added"] == 1
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT DISTINCT ticker FROM prices").fetchall() == [("BRK B",)]  # canonical
    conn.close()
    assert ibkr.calls[0][0] == ("BRK B",)  # fetched under canonical, not 'BRK.B'


def test_backfill_dedupes_alias_and_canonical_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    ibkr = _FakeIBKR(bars_by_ticker={"BRK B": [_bar(datetime(2026, 6, 17, 9, 30, 0))]})
    mdd.backfill_prices_direct(tickers_arg="BRK.B,BRK B", lookback_days=2, provider="ibkr",
                               db_path=str(db), ibkr_src=ibkr, today=date(2026, 6, 18))
    # both spellings collapse to ONE canonical fetch
    assert [c[0] for c in ibkr.calls] == [("BRK B",)]


def test_backfill_polygon_fallback_when_ibkr_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    ibkr = _FakeIBKR(bars_by_ticker={})  # IBKR returns nothing
    epoch_ms = int(datetime(2026, 6, 17, 13, 30, 0, tzinfo=timezone.utc).timestamp() * 1000)
    poly = _FakePolygon(results_by_day={date(2026, 6, 17): [
        {"t": epoch_ms, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 9}]})
    res = mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=2, provider="ibkr",
                                     db_path=str(db), ibkr_src=ibkr, polygon_src=poly,
                                     today=date(2026, 6, 18))
    assert res["rows_added"] == 1
    assert poly.calls  # fallback engaged
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT datetime FROM prices").fetchone()[0] == "2026-06-17T13:30:00+0000"
    conn.close()


def test_backfill_per_ticker_exception_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    ibkr = _FakeIBKR(bars_by_ticker={"AAPL": [_bar(datetime(2026, 6, 17, 9, 30, 0))]},
                     raises_for=["BAD"])
    res = mdd.backfill_prices_direct(tickers_arg="AAPL,BAD", lookback_days=2, provider="ibkr",
                                     db_path=str(db), ibkr_src=ibkr, today=date(2026, 6, 18))
    assert res["rows_added"] == 1                 # AAPL succeeded
    assert "BAD" in res["errors"]                 # BAD recorded, not fatal
    conn = sqlite3.connect(db)
    # run recorded succeeded (per-ticker failures don't fail the whole run)
    assert conn.execute("SELECT status FROM provider_sync_runs").fetchone()[0] == "succeeded"
    assert conn.execute("SELECT last_error FROM provider_sync_meta WHERE ticker='BAD'").fetchone()[0]
    conn.close()


def test_backfill_empty_scope_fails_loud(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    with pytest.raises(RuntimeError):
        mdd.backfill_prices_direct(tickers_arg="  ,  ", db_path=str(db), today=date(2026, 6, 18))


def test_backfill_progress_cb_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    ibkr = _FakeIBKR(bars_by_ticker={})
    seen = []
    mdd.backfill_prices_direct(tickers_arg="AAPL,NVDA", lookback_days=1, provider="ibkr",
                               db_path=str(db), ibkr_src=ibkr, progress_cb=lambda d, t, c: seen.append((d, t, c)),
                               today=date(2026, 6, 18))
    assert seen == [(1, 2, "AAPL"), (2, 2, "NVDA")]


def test_backfill_none_provider_constructs_default(tmp_path, monkeypatch):
    # the None→default seam (lazy construct) — monkeypatch the constructor to a fake so
    # the prod branch is exercised without a live Gateway.
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    fake = _FakeIBKR(bars_by_ticker={"AAPL": [_bar(datetime(2026, 6, 17, 9, 30, 0))]})
    monkeypatch.setattr(mdd, "_default_ibkr_src", lambda: fake)
    res = mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=2, provider="ibkr",
                                     db_path=str(db), today=date(2026, 6, 18))  # no ibkr_src injected
    assert res["rows_added"] == 1


def test_backfill_meta_write_failure_in_error_path_does_not_abort_batch(tmp_path, monkeypatch):
    # review #1: if a per-ticker error's recovery meta-write ALSO fails (same conn, disk/
    # lock fault), it must NOT escape to the outer handler and abort the batch — isolation
    # must hold: remaining tickers still process, run stays 'succeeded'.
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    ibkr = _FakeIBKR(bars_by_ticker={"AAPL": [_bar(datetime(2026, 6, 17, 9, 30, 0))]},
                     raises_for=["BAD"])
    real = mdd._upsert_provider_meta
    def flaky(conn, **kw):
        if kw.get("error"):  # the error-path recovery write blows up
            raise sqlite3.OperationalError("disk full during telemetry write")
        return real(conn, **kw)
    monkeypatch.setattr(mdd, "_upsert_provider_meta", flaky)
    res = mdd.backfill_prices_direct(tickers_arg="BAD,AAPL", lookback_days=2, provider="ibkr",
                                     db_path=str(db), ibkr_src=ibkr, today=date(2026, 6, 18))
    assert "BAD" in res["errors"]      # BAD recorded
    assert res["rows_added"] == 1      # AAPL still processed — batch NOT aborted
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT status FROM provider_sync_runs").fetchone()[0] == "succeeded"
    conn.close()


def test_backfill_fatal_path_finish_failure_does_not_mask_original(tmp_path, monkeypatch):
    # review #2: a fatal (non-per-ticker) error → the failed-path _finish_provider_run
    # write also failing must NOT mask the original error; the ORIGINAL propagates.
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    ibkr = _FakeIBKR(bars_by_ticker={})
    def boom_progress(d, t, c):
        raise ValueError("ORIGINAL fatal")  # raised outside the per-ticker try → outer handler
    monkeypatch.setattr(mdd, "_finish_provider_run",
                        lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("finish failed")))
    with pytest.raises(ValueError, match="ORIGINAL fatal"):
        mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=1, provider="ibkr",
                                   db_path=str(db), ibkr_src=ibkr, progress_cb=boom_progress,
                                   today=date(2026, 6, 18))


def test_backfill_default_ibkr_path_builds_polygon_fallback(tmp_path, monkeypatch):
    # 2b·2 residual: the LIVE provider="ibkr" path (no injected polygon_src) must still
    # construct a Polygon fallback so IBKR-empty falls back as designed (not IBKR-only).
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    ibkr = _FakeIBKR(bars_by_ticker={})  # IBKR returns nothing
    epoch_ms = int(datetime(2026, 6, 17, 13, 30, 0, tzinfo=timezone.utc).timestamp() * 1000)
    poly = _FakePolygon(results_by_day={date(2026, 6, 17): [
        {"t": epoch_ms, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 9}]})
    monkeypatch.setattr(mdd, "_default_ibkr_src", lambda: ibkr)
    monkeypatch.setattr(mdd, "_default_polygon_src", lambda: poly)
    res = mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=2, provider="ibkr",
                                     db_path=str(db), today=date(2026, 6, 18))  # NO srcs injected
    assert res["rows_added"] == 1 and poly.calls  # Polygon fallback engaged on the default path


def test_backfill_default_ibkr_path_survives_missing_polygon_key(tmp_path, monkeypatch):
    # reviewer caveat: no Polygon key (construction raises) must NOT break the IBKR path —
    # it just runs IBKR-only without a fallback.
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    ibkr = _FakeIBKR(bars_by_ticker={"AAPL": [_bar(datetime(2026, 6, 17, 9, 30, 0))]})
    monkeypatch.setattr(mdd, "_default_ibkr_src", lambda: ibkr)
    monkeypatch.setattr(mdd, "_default_polygon_src",
                        lambda: (_ for _ in ()).throw(RuntimeError("POLYGON_API_KEY not set")))
    res = mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=2, provider="ibkr",
                                     db_path=str(db), today=date(2026, 6, 18))  # NO srcs injected
    assert res["rows_added"] == 1  # IBKR path works; missing Polygon key didn't break it


# --- 2c: completed-days-only gap rule (NY close-state, not UTC date) ---------------

from datetime import time as _dtime
try:
    from zoneinfo import ZoneInfo as _ZI
    _ET = _ZI("America/New_York")
except Exception:  # pragma: no cover
    _ET = timezone.utc


def test_gaps_intraday_today_not_flagged(tmp_path):
    # NY 11:00 ET on a trading day, table empty: TODAY is in-progress → NOT a gap
    # (even with zero bars), so a future scheduler run can't freeze a partial day.
    db = _prices_db(tmp_path, [])
    gaps = mdd.detect_price_gaps(["AAPL"], lookback_days=0, db_path=str(db),
                                 now_et=datetime(2026, 6, 23, 11, 0, tzinfo=_ET))
    assert date(2026, 6, 23) not in gaps["AAPL"]


def test_gaps_after_close_today_is_complete(tmp_path):
    # NY 17:00 ET (after the 16:30 buffer), empty table → today IS complete → flagged.
    db = _prices_db(tmp_path, [])
    gaps = mdd.detect_price_gaps(["AAPL"], lookback_days=0, db_path=str(db),
                                 now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET))
    assert date(2026, 6, 23) in gaps["AAPL"]


def test_gaps_next_day_flags_prior_trading_day(tmp_path):
    # Next NY morning: the prior trading day (6/23) is complete → flagged if missing.
    db = _prices_db(tmp_path, [])
    gaps = mdd.detect_price_gaps(["AAPL"], lookback_days=2, db_path=str(db),
                                 now_et=datetime(2026, 6, 24, 9, 0, tzinfo=_ET))
    assert date(2026, 6, 23) in gaps["AAPL"]


def test_gaps_intraday_partial_today_does_not_hide_prior_gap(tmp_path):
    # today has partial bars (10 of ~26) AND a prior trading day is missing: the
    # in-progress day is excluded (not healed — that's deferred B), but the prior
    # COMPLETE day is still correctly flagged.
    db = _prices_db(tmp_path, [("AAPL", "2026-06-23T13:30:00+0000", "15min", 1, 1, 1, 1, 1)])
    gaps = mdd.detect_price_gaps(["AAPL"], lookback_days=2, db_path=str(db),
                                 now_et=datetime(2026, 6, 23, 11, 0, tzinfo=_ET))  # intraday
    assert date(2026, 6, 23) not in gaps["AAPL"]   # in-progress today excluded
    assert date(2026, 6, 22) in gaps["AAPL"]       # prior complete day still flagged


def test_gaps_include_incomplete_today_escape_hatch(tmp_path):
    # explicit opt-in restores the old behavior (today counted even mid-session).
    db = _prices_db(tmp_path, [])
    gaps = mdd.detect_price_gaps(["AAPL"], lookback_days=0, db_path=str(db),
                                 now_et=datetime(2026, 6, 23, 11, 0, tzinfo=_ET),
                                 include_incomplete_today=True)
    assert date(2026, 6, 23) in gaps["AAPL"]


def test_gaps_weekend_holiday_still_excluded_with_completeness(tmp_path):
    # the completeness gate must not change the weekend/holiday rule.
    db = _prices_db(tmp_path, [])
    gaps = mdd.detect_price_gaps(["AAPL"], lookback_days=8, db_path=str(db),
                                 now_et=datetime(2026, 6, 24, 9, 0, tzinfo=_ET))
    assert date(2026, 6, 20) not in gaps["AAPL"]   # Sat
    assert date(2026, 6, 21) not in gaps["AAPL"]   # Sun
    assert date(2026, 6, 19) not in gaps["AAPL"]   # Juneteenth


def test_gaps_now_et_aware_utc_is_converted_to_et(tmp_path):
    # a future caller passing an AWARE UTC datetime must be converted to ET, not used
    # as-is (else .date()/.time() are UTC values and misclassify the in-progress day).
    db = _prices_db(tmp_path, [])
    # 2026-06-24 01:00 UTC == 2026-06-23 21:00 ET → ET day is 6/23, AFTER close → complete
    g_after = mdd.detect_price_gaps(["AAPL"], lookback_days=0, db_path=str(db),
                                    now_et=datetime(2026, 6, 24, 1, 0, tzinfo=timezone.utc))
    assert date(2026, 6, 23) in g_after["AAPL"]
    # 2026-06-23 18:00 UTC == 2026-06-23 14:00 ET → mid-session → incomplete → excluded
    g_mid = mdd.detect_price_gaps(["AAPL"], lookback_days=0, db_path=str(db),
                                  now_et=datetime(2026, 6, 23, 18, 0, tzinfo=timezone.utc))
    assert date(2026, 6, 23) not in g_mid["AAPL"]


# --- 2d: full-window top-up (heal sparse/partial days, not just zero-bar) -----------

def test_backfill_tops_up_a_partial_day(tmp_path, monkeypatch):
    # THE canary finding: a day with 1 local bar (day-presence calls it "present") must be
    # TOPPED UP from the provider's full day, not skipped. Pre-seed AAPL 6/22 with 1 bar;
    # provider returns 3 bars for 6/22 → after backfill, 6/22 has all 3 (the dup PK ignored).
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO prices (ticker,datetime,interval,open,high,low,close,volume) "
                 "VALUES ('AAPL','2026-06-22T13:30:00+0000','15min',1,1,1,1,1)")  # the lone sparse bar
    conn.commit(); conn.close()
    ibkr = _FakeIBKR(bars_by_ticker={"AAPL": [
        _bar(datetime(2026, 6, 22, 9, 30, 0)),   # == the pre-seeded 13:30Z bar (dup PK → ignored)
        _bar(datetime(2026, 6, 22, 9, 45, 0)),   # new
        _bar(datetime(2026, 6, 22, 10, 0, 0)),   # new
    ]})
    res = mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=3, provider="ibkr",
                                     db_path=str(db), ibkr_src=ibkr,
                                     now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET))
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM prices WHERE ticker='AAPL' "
                     "AND substr(datetime,1,10)='2026-06-22'").fetchone()[0]
    conn.close()
    assert n == 3                  # topped up 1 → 3 (NOT skipped as "present")
    assert res["rows_added"] == 2  # 2 new bars; the dup-PK 13:30 ignored


def test_backfill_topup_idempotent_on_complete_day(tmp_path, monkeypatch):
    # a 2nd run over an already-complete day adds 0 (INSERT OR IGNORE), even though top-up
    # refetches the full window unconditionally.
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    ibkr = _FakeIBKR(bars_by_ticker={"AAPL": [_bar(datetime(2026, 6, 22, 9, 30, 0))]})
    a = mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=3, provider="ibkr",
                                   db_path=str(db), ibkr_src=ibkr,
                                   now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET))
    b = mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=3, provider="ibkr",
                                   db_path=str(db), ibkr_src=ibkr,
                                   now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET))
    assert a["rows_added"] == 1 and b["rows_added"] == 0


def test_backfill_topup_excludes_in_progress_today(tmp_path, monkeypatch):
    # 2c preserved: mid-session today must NOT be fetched (provider bar for today is not
    # written), so we don't churn the in-progress day every run.
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    ibkr = _FakeIBKR(bars_by_ticker={"AAPL": [_bar(datetime(2026, 6, 23, 9, 30, 0))]})  # a "today" bar
    res = mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=1, provider="ibkr",
                                     db_path=str(db), ibkr_src=ibkr,
                                     now_et=datetime(2026, 6, 23, 11, 0, tzinfo=_ET))  # intraday
    conn = sqlite3.connect(db)
    today_rows = conn.execute("SELECT COUNT(*) FROM prices WHERE substr(datetime,1,10)='2026-06-23'").fetchone()[0]
    conn.close()
    assert today_rows == 0  # in-progress today not fetched/written


def test_backfill_ibkr_empty_from_swallowed_request_error_falls_to_polygon(tmp_path, monkeypatch):
    # 2d review (MED): the real IBKRDataSource SWALLOWS a request-level failure (mid-session
    # disconnect / pacing / timeout) into an EMPTY result (logs+continues, no raise) — it is
    # indistinguishable here from "symbol absent", so it falls through to Polygon. This pins
    # that documented behavior so the contract can't silently drift back to "raises loud".
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    ibkr = _FakeIBKR(bars_by_ticker={})  # empty (models the swallowed-error / absent result)
    epoch_ms = int(datetime(2026, 6, 22, 13, 30, 0, tzinfo=timezone.utc).timestamp() * 1000)
    poly = _FakePolygon(results_by_day={date(2026, 6, 22): [
        {"t": epoch_ms, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 9}]})
    res = mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=3, provider="ibkr",
                                     db_path=str(db), ibkr_src=ibkr, polygon_src=poly,
                                     now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET))
    assert res["rows_added"] == 1 and poly.calls          # silently switched to Polygon
    # masked: NOT recorded as a per-ticker error (the documented MED limitation)
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT last_error FROM provider_sync_meta WHERE ticker='AAPL'").fetchone()[0] is None
    conn.close()


# --- 2e: IBKR preflight connect before the write lock (fail-fast, no churn) ---------

class _FakeIBKRConnect(_FakeIBKR):
    """A fake whose connect() can fail — to exercise the 2e preflight."""
    def __init__(self, *a, connect_ok=True, **k):
        super().__init__(*a, **k)
        self._connect_ok = connect_ok
        self.connect_calls = 0
        self.disconnected = False
    def connect(self):
        self.connect_calls += 1
        return self._connect_ok
    def disconnect(self):
        self.disconnected = True


def test_backfill_preflight_connect_failure_fails_fast_no_lock_no_run(tmp_path, monkeypatch):
    # IBKR cold-connect fails → run must fail FAST: never enter the per-ticker loop, never
    # write prices, never create a provider_sync_runs row, and (critically) never hold the
    # market write lock churning.
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    ibkr = _FakeIBKRConnect(bars_by_ticker={"AAPL": [_bar(datetime(2026, 6, 22, 9, 30, 0))]},
                            connect_ok=False)
    with pytest.raises(RuntimeError, match="IBKR"):
        mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=3, provider="ibkr",
                                   db_path=str(db), ibkr_src=ibkr,
                                   now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET))
    conn = sqlite3.connect(db)
    # no prices written, no run row created
    assert conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == 0
    has_runs = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='provider_sync_runs'").fetchone()
    assert (not has_runs) or conn.execute("SELECT COUNT(*) FROM provider_sync_runs").fetchone()[0] == 0
    conn.close()
    # the lock is free immediately (preflight failed BEFORE acquiring it)
    with mdd.market_write_lock(timeout=2):
        pass


def test_backfill_preflight_connect_ok_proceeds(tmp_path, monkeypatch):
    # connect ok → normal run (preflight is transparent on the happy path).
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    ibkr = _FakeIBKRConnect(bars_by_ticker={"AAPL": [_bar(datetime(2026, 6, 22, 9, 30, 0))]},
                            connect_ok=True)
    res = mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=3, provider="ibkr",
                                     db_path=str(db), ibkr_src=ibkr,
                                     now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET))
    assert res["rows_added"] == 1 and ibkr.connect_calls >= 1


def test_backfill_polygon_provider_skips_ibkr_preflight(tmp_path, monkeypatch):
    # provider='polygon' must NOT require an IBKR connect (no Gateway dependency at all).
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    db = _backfill_db(tmp_path)
    epoch_ms = int(datetime(2026, 6, 22, 13, 30, 0, tzinfo=timezone.utc).timestamp() * 1000)
    poly = _FakePolygon(results_by_day={date(2026, 6, 22): [
        {"t": epoch_ms, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 9}]})
    res = mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=3, provider="polygon",
                                     db_path=str(db), polygon_src=poly,
                                     now_et=datetime(2026, 6, 23, 17, 0, tzinfo=_ET))
    assert res["rows_added"] == 1  # no IBKR involved, no preflight needed


def test_backfill_fetches_provider_rows_outside_market_write_lock(tmp_path, monkeypatch):
    db = _backfill_db(tmp_path)
    in_lock = {"value": False}
    fetch_observed_lock = []

    @contextmanager
    def fake_market_lock(timeout=30.0, poll=0.5):
        in_lock["value"] = True
        try:
            yield
        finally:
            in_lock["value"] = False

    def fake_fetch(*args, **kwargs):
        fetch_observed_lock.append(in_lock["value"])
        return [(
            "AAPL",
            "2026-07-03T13:30:00+0000",
            "15min",
            1.0,
            1.0,
            1.0,
            1.0,
            100,
        )]

    monkeypatch.setattr(mdd, "market_write_lock", fake_market_lock)
    monkeypatch.setattr(mdd, "_fetch_rows_for_gaps", fake_fetch)
    monkeypatch.setattr(mdd, "detect_price_gaps", lambda *a, **k: {"AAPL": ["2026-07-03"]})

    res = mdd.backfill_prices_direct(
        tickers_arg="AAPL",
        db_path=str(db),
        ibkr_src=_FakeIBKR(),
        polygon_src=_FakePolygon(),
        today=date(2026, 7, 4),
        now_et=datetime(2026, 7, 4, 12, 0, tzinfo=_ET),
        acquire_gateway_lock=False,
    )

    assert res["rows_added"] == 1
    assert fetch_observed_lock == [False]


# --- PG-exit: standalone backfill acquires the shared IBKR Gateway lock -------------

def test_backfill_acquires_gateway_lock_by_default(tmp_path, monkeypatch):
    # a standalone backfill must hold the SHARED gateway lock during the IBKR work, so it
    # can't race the scheduler / intraday. Assert the lock is held when the fetch runs.
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    import src.ibkr_gateway_lock as gw
    db = _backfill_db(tmp_path)
    seen = {"held": None}

    class _ObservingIBKR(_FakeIBKR):
        def fetch_historical_intraday(self, *a, **k):
            seen["held"] = gw.IBKR_THREAD_LOCK.locked()   # was the gateway lock held during fetch?
            return super().fetch_historical_intraday(*a, **k)

    ibkr = _ObservingIBKR(bars_by_ticker={"AAPL": [_bar(datetime(2026, 6, 17, 9, 30, 0))]})
    mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=2, provider="ibkr",
                               db_path=str(db), ibkr_src=ibkr, today=date(2026, 6, 18))
    assert seen["held"] is True                              # gateway lock held during the fetch
    assert not gw.IBKR_THREAD_LOCK.locked()                  # released after


def test_backfill_acquire_gateway_lock_false_skips_when_caller_holds_it(tmp_path, monkeypatch):
    # the scheduler path: run_source already holds the gateway lock, so the adapter is called
    # with acquire_gateway_lock=False. Simulate by holding the lock, then calling with the flag
    # off → must NOT deadlock (would hang/timeout if it tried to re-acquire the non-reentrant lock).
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    import src.ibkr_gateway_lock as gw
    db = _backfill_db(tmp_path)
    ibkr = _FakeIBKR(bars_by_ticker={"AAPL": [_bar(datetime(2026, 6, 17, 9, 30, 0))]})
    assert gw.IBKR_THREAD_LOCK.acquire(timeout=2)            # caller (scheduler) holds it
    try:
        res = mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=2, provider="ibkr",
                                         db_path=str(db), ibkr_src=ibkr, today=date(2026, 6, 18),
                                         acquire_gateway_lock=False)
        assert res["rows_added"] == 1                        # completed (no self-deadlock)
    finally:
        gw.IBKR_THREAD_LOCK.release()


def test_backfill_polygon_path_no_gateway_lock(tmp_path, monkeypatch):
    # provider=polygon has no Gateway dependency → must not hold the IBKR gateway lock.
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    import src.ibkr_gateway_lock as gw
    db = _backfill_db(tmp_path)
    epoch_ms = int(datetime(2026, 6, 17, 13, 30, 0, tzinfo=timezone.utc).timestamp() * 1000)
    poly = _FakePolygon(results_by_day={date(2026, 6, 17): [
        {"t": epoch_ms, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 9}]})
    # record whether the gateway lock was ever entered (it must NOT be for the polygon path)
    entered = {"n": 0}
    real_cm = gw.ibkr_gateway_lock

    def _counting_cm(*a, **k):
        entered["n"] += 1
        return real_cm(*a, **k)
    monkeypatch.setattr("src.market_data_direct.ibkr_gateway_lock", _counting_cm, raising=False)
    monkeypatch.setattr(gw, "ibkr_gateway_lock", _counting_cm)
    mdd.backfill_prices_direct(tickers_arg="AAPL", lookback_days=2, provider="polygon",
                               db_path=str(db), polygon_src=poly, today=date(2026, 6, 18))
    assert entered["n"] == 0                                  # polygon path never takes the gateway lock
    assert not gw.IBKR_THREAD_LOCK.locked()


def test_default_ibkr_src_uses_prices_domain_client_id(monkeypatch):
    # Real-shape seam test (seam-mock discipline): the construction itself must carry
    # the partitioned prices client id, not the raw base.
    import src.market_data_direct as mdd

    seen = {}

    class _FakeSrc:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.delenv("IBKR_CLIENT_ID", raising=False)
    monkeypatch.setattr("data_sources.ibkr_source.IBKRDataSource", _FakeSrc)

    mdd._default_ibkr_src()

    assert seen["client_id"] == 21
    assert seen["timeout"] == mdd._IBKR_CONNECT_TIMEOUT_S
