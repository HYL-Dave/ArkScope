"""Slice #2a — market_data_direct hermetic core (PG-free, no live Gateway).

Covers: WAL-safe backup, preflight_canonicalize, _normalize_utc (the byte-match
invariant + DST), detect_price_gaps (day-presence, weekend/holiday aware), and the
provider_sync_runs/provider_sync_meta telemetry tables. NO provider fetch, NO
scheduler — those are 2b.
"""

from __future__ import annotations

import sqlite3
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
