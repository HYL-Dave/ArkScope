"""
market_data_admin — lifecycle for the local market_data.db (slices 3a / 3b).

Turns the developer migration script into an app-controllable substrate: status,
bootstrap (full rebuild from PG), validation, and an in-process job runner so the
desktop UI can trigger + poll a bootstrap instead of asking the user to run a CLI
(DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md §3/§4/§8).

Domains migrated:
  - 3a   PRICES        — the OHLCV bars (15min stored; 1h/1d rolled up on read).
  - 3b   NEWS          — article corpus (NO scores; news_scores deferred) + an FTS5
                         index for local full-text search. Scored reads fall back to PG.
  - 3c-A IV_HISTORY    — daily IV/HV/VRP snapshots (id-keyed, id-based incremental).
  - 3c-A FUNDAMENTALS  — ReportSnapshot JSON snapshots (id-keyed, id-based incremental).
  - 3c-C FINANCIAL_CACHE — LOCAL-PRIMARY provider/SEC cache (NOT a PG mirror): set
                 writes local-only, get is local-first w/ PG fallback + read-through
                 promotion. Preserved across rebuilds (carry-over), not validated vs
                 PG, untouched by the incremental updater. See SqliteBackend get/set.

The bootstrap builds ALL domains into a single ``.building`` temp file and
atomically swaps it in only after row-count + checksum validation passes, so a
failed rebuild never destroys an existing good DB. ``scripts/migrate_market_to_sqlite.py``
is a thin CLI over this module; the app uses the API. Incremental (delta) updates
append rows newer than the local max in place to the live WAL DB (no swap).
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
USE_LOCAL_MARKET_KEY = "use_local_market"  # profile_settings key for the persisted toggle
USE_LOCAL_MARKET_STRICT_KEY = "use_local_market_strict"  # modifier: local market on + DB exists → no PG fallback
_TRUTHY = ("1", "true", "yes", "on")

_PRICES_SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    ticker    TEXT NOT NULL,
    datetime  TEXT NOT NULL,   -- UTC 'YYYY-MM-DDTHH:MM:SS+0000' (matches PG TO_CHAR)
    interval  TEXT NOT NULL,   -- '15min' | '1h' | '1d'
    open      REAL,
    high      REAL,
    low       REAL,
    close     REAL,
    volume    INTEGER,
    PRIMARY KEY (ticker, datetime, interval)
);
CREATE INDEX IF NOT EXISTS idx_prices_ticker_interval_dt ON prices(ticker, interval, datetime);
"""

# News: articles only (no scores/embedding/search_vector). id mirrors PG's id so
# it is the rowid the FTS5 external-content index keys on.
_NEWS_SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
    id              INTEGER PRIMARY KEY,
    ticker          TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT,
    url             TEXT,
    publisher       TEXT,
    source          TEXT NOT NULL,   -- 'ibkr' | 'polygon' | 'finnhub'
    published_at    TEXT NOT NULL,   -- UTC 'YYYY-MM-DDTHH:MM:SS+0000'
    article_hash    TEXT,
    -- news_scores RETIRED (DATA_COLLECTION plan §4 decision 2026-06-23): sentiment is
    -- local-first + OPTIONAL. sentiment_score is the 1-5 LLM score written on-demand by
    -- analysis (NULL until then). The CHECK makes the 1-5 scale ENFORCED, not merely
    -- conventional: a provider's native polarity (-1/0/+1) physically CANNOT be written
    -- here, so it can never poison the 1-5 consumers (get_news_sentiment_summary,
    -- min_sentiment). A provider polarity, if ever carried, needs its OWN column.
    sentiment_score  REAL CHECK (sentiment_score IS NULL OR sentiment_score BETWEEN 1 AND 5),
    sentiment_source TEXT,           -- who produced the score: 'llm' | …
    sentiment_scale  TEXT            -- documents the score's scale (currently '1-5')
);
CREATE INDEX IF NOT EXISTS idx_news_ticker_pub ON news(ticker, published_at);
CREATE INDEX IF NOT EXISTS idx_news_pub ON news(published_at);
CREATE VIRTUAL TABLE IF NOT EXISTS news_fts
    USING fts5(title, description, content='news', content_rowid='id',
               tokenize='porter unicode61');
"""

# Per-domain incremental-sync status. Lives in market_data.db; reset on a full
# bootstrap (fresh DB), updated by each incremental run.
_META_SCHEMA = """
CREATE TABLE IF NOT EXISTS market_sync_meta (
    domain       TEXT PRIMARY KEY,   -- 'prices' | 'news' | 'iv' | 'fundamentals'
    last_success TEXT,
    last_error   TEXT,
    rows_added   INTEGER DEFAULT 0,
    updated_at   TEXT NOT NULL
);
"""

def _ensure_news_sentiment_columns(conn) -> None:
    """Idempotent: add the optional local sentiment columns to a pre-sentiment ``news``
    table (CREATE TABLE IF NOT EXISTS won't alter an existing one). No-op when the news
    table is absent or already has them. news_scores is RETIRED — these are the local-first
    home for an on-demand 1-5 LLM score + scale-tagged provider sentiment."""
    if not conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='news'"
    ).fetchone():
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(news)").fetchall()}
    # sentiment_score carries the SAME 1-5 CHECK as a fresh _NEWS_SCHEMA so an upgraded
    # pre-existing DB enforces the scale invariant identically (born NULL → CHECK passes).
    for col, decl in (
        ("sentiment_score", "REAL CHECK (sentiment_score IS NULL OR sentiment_score BETWEEN 1 AND 5)"),
        ("sentiment_source", "TEXT"),
        ("sentiment_scale", "TEXT"),
    ):
        if col not in cols:
            conn.execute(f"ALTER TABLE news ADD COLUMN {col} {decl}")


# Ticker canonicalization (strict-readiness slice #1): one canonical spelling per company
# so prices/news/fundamentals/iv join across domains. ``canonical`` is the spelling the
# prices table already uses (the 2.27M-row history) — space form for class shares — so
# canonicalizing never rewrites prices history. Seeded with the known BRK split; grows as
# more aliases surface. Lives in market_data.db (locked topology). NOT for provider-sync
# state (that is provider_sync_*; this is identity mapping only).
_TICKER_ALIASES_SCHEMA = """
CREATE TABLE IF NOT EXISTS ticker_aliases (
    alias     TEXT PRIMARY KEY,
    canonical TEXT NOT NULL
);
"""
_SEED_TICKER_ALIASES = (
    ("BRK.B", "BRK B"),
    ("BRK-B", "BRK B"),
    # LendingClub → Nasdaq HAPN rename (2026-06-22). Unlike the BRK spelling-variants
    # (canonical == existing-history spelling), this is a true rename: the canonical (HAPN)
    # is the NEW symbol new bars arrive under, so canonicalize stitches LC's history under
    # HAPN. Read paths fold LC→HAPN; the coverage panel shows one HAPN row, not an LC gap.
    ("LC", "HAPN"),
)


def _ensure_ticker_aliases(conn) -> None:
    """Idempotent: create ticker_aliases + seed the known splits (INSERT OR IGNORE so a
    re-run never dups or clobbers an operator-edited mapping)."""
    conn.executescript(_TICKER_ALIASES_SCHEMA)
    conn.executemany(
        "INSERT OR IGNORE INTO ticker_aliases (alias, canonical) VALUES (?, ?)",
        _SEED_TICKER_ALIASES,
    )


# PG-exit 2b — news identity + FTS sync. UNIQUE(article_hash) lets every writer INSERT OR IGNORE
# to dedup; the external-content news_fts is kept in sync by triggers so NO writer needs a manual
# fts insert. Triggers are deliberately NOT in _NEWS_SCHEMA: the bulk bootstrap copy uses a one-shot
# news_fts('rebuild') and would be slowed to a crawl by per-row triggers — bootstrap adds them AFTER
# the rebuild; incremental/direct writers (small batches) get them up front.
_NEWS_HASH_UNIQUE = "CREATE UNIQUE INDEX IF NOT EXISTS idx_news_article_hash ON news(article_hash)"
_NEWS_FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS news_ai AFTER INSERT ON news BEGIN
  INSERT INTO news_fts(rowid, title, description) VALUES (new.id, new.title, new.description);
END;
CREATE TRIGGER IF NOT EXISTS news_ad AFTER DELETE ON news BEGIN
  INSERT INTO news_fts(news_fts, rowid, title, description) VALUES('delete', old.id, old.title, old.description);
END;
CREATE TRIGGER IF NOT EXISTS news_au AFTER UPDATE ON news BEGIN
  INSERT INTO news_fts(news_fts, rowid, title, description) VALUES('delete', old.id, old.title, old.description);
  INSERT INTO news_fts(rowid, title, description) VALUES (new.id, new.title, new.description);
END;
"""


def _ensure_news_hash_unique(conn) -> None:
    """Idempotent UNIQUE index on news.article_hash so INSERT OR IGNORE dedups (PG-exit 2b).
    Safe to add to the live table because it has no dup/null article_hash rows (verified)."""
    conn.execute(_NEWS_HASH_UNIQUE)


def _ensure_news_fts_triggers(conn) -> None:
    """Idempotent AFTER INSERT/DELETE/UPDATE triggers keeping the external-content news_fts in
    sync (PG-exit 2b) — replaces the per-row manual fts inserts in the direct + mirror writers.
    NOT part of _NEWS_SCHEMA (see the note above): apply where per-row sync is wanted, never around
    the bulk bootstrap copy."""
    conn.executescript(_NEWS_FTS_TRIGGERS)


def _canonicalize_table_tickers(conn, table: str) -> int:
    """One-time PK-SAFE reconcile of EXISTING rows in ``table`` whose ticker is an alias →
    its canonical spelling. Returns the number of DISTINCT alias spellings that had ≥1 row
    reconciled (not the row count).

    PK-safe (the load-bearing discipline): an alias row may collide with an already-present
    canonical row (e.g. news has BOTH 'BRK B' and 'BRK.B'; prices may have a same-PK dup).
    So per alias we UPDATE OR IGNORE (rename rows that DON'T collide) then DELETE whatever
    alias rows remain (the collisions — a canonical row already exists, so the dup is
    redundant). Never raises a PK IntegrityError, never loses a canonical row. Read paths
    still resolve through the alias table, so this is cleanup, not a correctness dependency."""
    aliases = conn.execute("SELECT alias, canonical FROM ticker_aliases").fetchall()
    reconciled = 0
    for alias, canonical in aliases:
        if alias == canonical:
            continue
        before = conn.execute(
            "SELECT COUNT(*) FROM {} WHERE ticker = ?".format(table), (alias,)).fetchone()[0]
        if not before:
            continue
        # rename the non-colliding alias rows; OR IGNORE leaves a colliding row untouched
        conn.execute(
            "UPDATE OR IGNORE {} SET ticker = ? WHERE ticker = ?".format(table),
            (canonical, alias))
        # drop any alias rows that survived (they collided → canonical already exists)
        conn.execute("DELETE FROM {} WHERE ticker = ?".format(table), (alias,))
        reconciled += 1
    conn.commit()
    return reconciled


_PRICE_INSERT = ("INSERT OR IGNORE INTO prices "
                 "(ticker, datetime, interval, open, high, low, close, volume) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
_NEWS_INSERT = ("INSERT OR IGNORE INTO news "
                "(id, ticker, title, description, url, publisher, source, published_at, article_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")

_PG_PRICES_COLS = """
    ticker,
    TO_CHAR(datetime AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS+0000') AS datetime,
    interval, open, high, low, close, volume
"""
_PG_NEWS_COLS = """
    id, ticker, title, description, url, publisher, source,
    TO_CHAR(published_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS+0000') AS published_at,
    article_hash
"""
_PG_PRICES_SELECT = f"SELECT {_PG_PRICES_COLS} FROM prices ORDER BY ticker, interval, datetime"
# `p.`-qualified for the group-aware incremental JOIN (disambiguates ticker/interval).
_PG_PRICES_COLS_P = """
    p.ticker,
    TO_CHAR(p.datetime AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS+0000') AS datetime,
    p.interval, p.open, p.high, p.low, p.close, p.volume
"""
_PG_NEWS_SELECT = f"SELECT {_PG_NEWS_COLS} FROM news ORDER BY id"
# Incremental: only articles inserted after the local max id (monotonic PG id =
# ingestion order; catches new articles regardless of published_at backfilling).
_PG_NEWS_SELECT_INCR = f"SELECT {_PG_NEWS_COLS} FROM news WHERE id > %s ORDER BY id"

# 3c-A: IV history + fundamentals (read-mostly snapshots; id-keyed like news, so
# incremental is id-based). financial_cache (3c-C, local-primary) is defined below.
_IV_SCHEMA = """
CREATE TABLE IF NOT EXISTS iv_history (
    id INTEGER PRIMARY KEY, ticker TEXT NOT NULL, date TEXT NOT NULL,  -- 'YYYY-MM-DD'
    atm_iv REAL, hv_30d REAL, vrp REAL, spot_price REAL, num_quotes INTEGER
);
CREATE INDEX IF NOT EXISTS idx_iv_ticker_date ON iv_history(ticker, date);
"""
_FUND_SCHEMA = """
CREATE TABLE IF NOT EXISTS fundamentals (
    id INTEGER PRIMARY KEY, ticker TEXT NOT NULL, snapshot_date TEXT NOT NULL,  -- 'YYYY-MM-DD'
    data TEXT NOT NULL   -- ReportSnapshot JSON (text; JSONB in PG)
);
CREATE INDEX IF NOT EXISTS idx_fund_ticker_date ON fundamentals(ticker, snapshot_date);
"""

_IV_INSERT = ("INSERT OR IGNORE INTO iv_history "
              "(id, ticker, date, atm_iv, hv_30d, vrp, spot_price, num_quotes) "
              "VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
_PG_IV_COLS = ("id, ticker, TO_CHAR(date, 'YYYY-MM-DD') AS date, "
               "atm_iv, hv_30d, vrp, spot_price, num_quotes")
_PG_IV_SELECT = f"SELECT {_PG_IV_COLS} FROM iv_history ORDER BY id"
_PG_IV_SELECT_INCR = f"SELECT {_PG_IV_COLS} FROM iv_history WHERE id > %s ORDER BY id"

_FUND_INSERT = "INSERT OR IGNORE INTO fundamentals (id, ticker, snapshot_date, data) VALUES (?, ?, ?, ?)"
_PG_FUND_COLS = "id, ticker, TO_CHAR(snapshot_date, 'YYYY-MM-DD') AS snapshot_date, data::text"
_PG_FUND_SELECT = f"SELECT {_PG_FUND_COLS} FROM fundamentals ORDER BY id"
_PG_FUND_SELECT_INCR = f"SELECT {_PG_FUND_COLS} FROM fundamentals WHERE id > %s ORDER BY id"

# 3c-C: financial_cache — LOCAL-PRIMARY (NOT a PG mirror). SqliteBackend.set writes
# here; .get is local-first with PG fallback + read-through promotion. cache_key-keyed
# with a TTL via expires_at (UTC ISO 'YYYY-MM-DDTHH:MM:SS+00:00' strings, which are
# lexicographically comparable so expiry is a string compare). Because it is
# local-primary it is PRESERVED across a full rebuild (carry-over), NOT validated
# against PG, and NOT touched by the incremental updater. (financial_datasets_client
# routes its paid-path cache through here via cache_backend — source
# 'financial_datasets'; standalone/no-backend usage keeps its legacy env-PG+file.)
_FIN_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS financial_cache (
    cache_key   TEXT PRIMARY KEY,
    source      TEXT NOT NULL DEFAULT 'financial_datasets',
    ticker      TEXT NOT NULL,
    data        TEXT NOT NULL,        -- JSON (JSONB in PG)
    fetched_at  TEXT NOT NULL,        -- UTC ISO 'YYYY-MM-DDTHH:MM:SS+00:00'
    expires_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fin_cache_ticker ON financial_cache(ticker);
CREATE INDEX IF NOT EXISTS idx_fin_cache_expires ON financial_cache(expires_at);
"""
_FIN_CACHE_INSERT = ("INSERT OR REPLACE INTO financial_cache "
                     "(cache_key, source, ticker, data, fetched_at, expires_at) "
                     "VALUES (?, ?, ?, ?, ?, ?)")

# Serializes the local-primary financial_cache write against a bootstrap's
# read-old → swap → write-carried critical section, so a set_financial_cache that
# races a full rebuild is queued (then writes to the swapped-in DB) instead of being
# silently dropped when the old inode is replaced. Held only across the (fast) swap,
# never the multi-minute build. Same-process (single sidecar): bootstrap runs on a
# daemon thread, set_financial_cache on FastAPI worker threads. See SqliteBackend.
_CACHE_WRITE_LOCK = threading.Lock()


def _now() -> str:
    """UTC ISO-8601 timestamp (seconds). Imported lazily to keep this off the hot path."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def resolve_market_db_path() -> str:
    """``ARKSCOPE_MARKET_DB`` or the default ``<repo>/data/market_data.db``."""
    return os.environ.get("ARKSCOPE_MARKET_DB") or str(_PROJECT_ROOT / "data" / "market_data.db")


def env_routing_enabled() -> bool:
    return os.environ.get("ARKSCOPE_USE_LOCAL_MARKET", "").strip().lower() in _TRUTHY


def env_strict_enabled() -> bool:
    return os.environ.get("ARKSCOPE_LOCAL_MARKET_STRICT", "").strip().lower() in _TRUTHY


# --- PostgreSQL access (source of the migration) ------------------------------

def _pg_conn():
    """Connect to PG using the project's resolved DSN (config/.env)."""
    from src.tools.data_access import DataAccessLayer
    from src.tools.db_config import load_sslmode

    dsn = DataAccessLayer(db_dsn="auto")._load_env_db_dsn()
    if not dsn:
        raise RuntimeError("No DATABASE_URL in config/.env — cannot read PG market data.")
    import psycopg2

    sslmode = load_sslmode(_PROJECT_ROOT / "config" / ".env", dsn)
    return psycopg2.connect(dsn, sslmode=sslmode)


def _pg_group_counts(cur, sql: str) -> Dict[tuple, int]:
    cur.execute(sql)
    return {tuple(row[:-1]): row[-1] for row in cur.fetchall()}


def _sqlite_group_counts(conn, sql: str) -> Dict[tuple, int]:
    return {tuple(row[:-1]): row[-1] for row in conn.execute(sql).fetchall()}


_PG_PRICE_CHECKSUM = "SELECT ticker, interval, COUNT(*) FROM prices GROUP BY ticker, interval"
_SQ_PRICE_CHECKSUM = _PG_PRICE_CHECKSUM

# News integrity fingerprint: per (source, ticker) the row count AND SUM(id). The
# count catches ticker-level drift within a source; SUM(id) (identical integer
# arithmetic on PG + SQLite, since id mirrors PG's id) catches id-set drift —
# missing/extra/shifted articles a bare per-source count would miss.
_NEWS_CHECKSUM_SQL = (
    "SELECT source, ticker, COUNT(*), COALESCE(SUM(id), 0) FROM news GROUP BY source, ticker"
)


def _news_checksum(rows) -> Dict[tuple, tuple]:
    return {(r[0], r[1]): (r[2], r[3]) for r in rows}


def _pg_news_checksum(cur) -> Dict[tuple, tuple]:
    cur.execute(_NEWS_CHECKSUM_SQL)
    return _news_checksum(cur.fetchall())


def _sqlite_news_checksum(conn) -> Dict[tuple, tuple]:
    return _news_checksum(conn.execute(_NEWS_CHECKSUM_SQL).fetchall())


# Per-ticker (count, SUM(id)) fingerprint for id-keyed domains (iv, fundamentals).
# Identical SQL on PG + SQLite.
_IV_CHECKSUM_SQL = "SELECT ticker, COUNT(*), COALESCE(SUM(id), 0) FROM iv_history GROUP BY ticker"
_FUND_CHECKSUM_SQL = "SELECT ticker, COUNT(*), COALESCE(SUM(id), 0) FROM fundamentals GROUP BY ticker"


def _ticker_idsum(rows) -> Dict[str, tuple]:
    return {r[0]: (r[1], r[2]) for r in rows}


def _pg_ticker_idsum(cur, sql: str) -> Dict[str, tuple]:
    cur.execute(sql)
    return _ticker_idsum(cur.fetchall())


def _sqlite_ticker_idsum(conn, sql: str) -> Dict[str, tuple]:
    return _ticker_idsum(conn.execute(sql).fetchall())


def _fold_checksum_aliases(checksum: Dict, aliases: Dict[str, str], ticker_pos: int) -> Dict:
    """Fold a checksum dict into canonical-ticker space so a post-canon LOCAL DB validates
    against PRE-canon PG. ``ticker_pos`` = where the ticker sits in the key (tuple key
    ``(source,ticker)`` → 1; bare ``ticker`` key → None). Colliding entries (e.g. BRK.B +
    BRK B → BRK B) sum their (count, sum_id) component-wise, matching what the canonicalized
    SQLite side produces. Returns a new dict; identity when no alias key is present."""
    out: Dict = {}
    for key, val in checksum.items():
        if ticker_pos is None:
            new_key = aliases.get(key, key)
        else:
            parts = list(key)
            parts[ticker_pos] = aliases.get(parts[ticker_pos], parts[ticker_pos])
            new_key = tuple(parts)
        if new_key in out:
            prev = out[new_key]
            if isinstance(val, tuple):  # (count, sum_id) → component-wise sum
                out[new_key] = tuple(a + b for a, b in zip(prev, val))
            else:  # bare count (prices group) → scalar sum
                out[new_key] = prev + val
        else:
            out[new_key] = val
    return out


def _load_ticker_aliases(conn) -> Dict[str, str]:
    """alias→canonical map from a SQLite conn; {} if the table is absent (pre-canon DB)."""
    try:
        return {a: c for a, c in conn.execute("SELECT alias, canonical FROM ticker_aliases").fetchall()}
    except sqlite3.OperationalError:
        return {}


def pg_market_counts() -> dict:
    """PG-side row + group counts per domain (the validation target / --dry-run)."""
    pg = _pg_conn()
    try:
        cur = pg.cursor()
        cur.execute("SELECT COUNT(*) FROM prices")
        price_rows = cur.fetchone()[0]
        price_groups = len(_pg_group_counts(cur, _PG_PRICE_CHECKSUM))
        cur.execute("SELECT COUNT(*) FROM news")
        news_rows = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT source) FROM news")
        news_sources = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM iv_history")
        iv_rows = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM fundamentals")
        fund_rows = cur.fetchone()[0]
        return {
            "prices": {"rows": price_rows, "groups": price_groups},
            "news": {"rows": news_rows, "groups": news_sources},
            "iv": {"rows": iv_rows},
            "fundamentals": {"rows": fund_rows},
        }
    finally:
        pg.close()


# --- local DB stats (read-only; never needs PG) -------------------------------

def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?", (name,)
    ).fetchone() is not None


def local_market_stats(out_path: Optional[str] = None) -> dict:
    """Read-only per-domain stats for the local market DB (does NOT touch PG)."""
    path = out_path or resolve_market_db_path()
    empty = {
        "exists": False,
        "prices": {"row_count": 0, "ticker_count": 0, "latest_datetime": None},
        "news": {"row_count": 0, "source_count": 0, "latest_published": None},
        "iv": {"row_count": 0, "ticker_count": 0, "latest_date": None},
        "fundamentals": {"row_count": 0, "ticker_count": 0, "latest_date": None},
        # local-primary cache (3c-C): valid vs expired by expires_at, plus latest fetch
        "financial_cache": {"row_count": 0, "valid_count": 0, "expired_count": 0,
                            "latest_fetched_at": None},
    }
    if not Path(path).exists():
        return empty
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return {**empty, "exists": True}
    try:
        out = {**{k: dict(v) for k, v in empty.items() if k != "exists"}, "exists": True}
        if _table_exists(conn, "prices"):
            out["prices"] = {
                "row_count": conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0],
                "ticker_count": conn.execute("SELECT COUNT(DISTINCT ticker) FROM prices").fetchone()[0],
                "latest_datetime": conn.execute("SELECT MAX(datetime) FROM prices").fetchone()[0],
            }
        if _table_exists(conn, "news"):
            out["news"] = {
                "row_count": conn.execute("SELECT COUNT(*) FROM news").fetchone()[0],
                "source_count": conn.execute("SELECT COUNT(DISTINCT source) FROM news").fetchone()[0],
                "latest_published": conn.execute("SELECT MAX(published_at) FROM news").fetchone()[0],
            }
        if _table_exists(conn, "iv_history"):
            out["iv"] = {
                "row_count": conn.execute("SELECT COUNT(*) FROM iv_history").fetchone()[0],
                "ticker_count": conn.execute("SELECT COUNT(DISTINCT ticker) FROM iv_history").fetchone()[0],
                "latest_date": conn.execute("SELECT MAX(date) FROM iv_history").fetchone()[0],
            }
        if _table_exists(conn, "fundamentals"):
            out["fundamentals"] = {
                "row_count": conn.execute("SELECT COUNT(*) FROM fundamentals").fetchone()[0],
                "ticker_count": conn.execute("SELECT COUNT(DISTINCT ticker) FROM fundamentals").fetchone()[0],
                "latest_date": conn.execute("SELECT MAX(snapshot_date) FROM fundamentals").fetchone()[0],
            }
        if _table_exists(conn, "financial_cache"):
            now = _now()  # same UTC ISO-seconds format the cache stores expires_at in
            total = conn.execute("SELECT COUNT(*) FROM financial_cache").fetchone()[0]
            valid = conn.execute(
                "SELECT COUNT(*) FROM financial_cache WHERE expires_at > ?", (now,)
            ).fetchone()[0]
            out["financial_cache"] = {
                "row_count": total,
                "valid_count": valid,
                "expired_count": total - valid,
                "latest_fetched_at": conn.execute("SELECT MAX(fetched_at) FROM financial_cache").fetchone()[0],
            }
        return out
    except sqlite3.OperationalError:
        return {**empty, "exists": True}
    finally:
        conn.close()


def local_ticker_coverage(ticker: str, out_path: Optional[str] = None) -> dict:
    """Whether the LOCAL market DB has any rows for ``ticker`` per domain (read-only,
    routing-independent — a fact about the local DB, NOT a claim about where a given
    read was served from). Powers the detail page's honest "本地覆蓋：有/無" hint;
    per-call provenance (local vs PG-fallback) is a separate future signal."""
    path = out_path or resolve_market_db_path()
    cov = {"exists": False, "prices": False, "news": False, "iv": False, "fundamentals": False}
    if not Path(path).exists():
        return cov
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return cov
    # resolve the alias spelling to canonical so coverage of e.g. 'BRK.B' reports the
    # rows that live under the canonical 'BRK B' (consistent with the read paths' _canon).
    t = _load_ticker_aliases(conn).get(ticker.upper(), ticker.upper())
    try:
        cov["exists"] = True
        for domain, table in (("prices", "prices"), ("news", "news"),
                              ("iv", "iv_history"), ("fundamentals", "fundamentals")):
            if _table_exists(conn, table):
                cov[domain] = conn.execute(
                    f"SELECT 1 FROM {table} WHERE ticker = ? LIMIT 1", (t,)
                ).fetchone() is not None
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()
    return cov


# --- bootstrap (full rebuild of prices + news + iv + fundamentals) + validate -

def _copy_table(cur, sconn, select_sql: str, insert_sql: str, total: int,
                progress_cb, base: int, grand_total: int, batch: int) -> int:
    cur.execute(select_sql)
    written = 0
    while True:
        rows = cur.fetchmany(batch)
        if not rows:
            break
        sconn.executemany(insert_sql, rows)
        sconn.commit()
        written += len(rows)
        if progress_cb:
            progress_cb(base + written, grand_total)
    return written


def _read_fin_cache_rows(path: str) -> list:
    """Read the LOCAL-PRIMARY financial_cache rows from an existing DB (read-only).
    Used to carry the cache over a full rebuild — financial_cache is NOT a PG mirror
    (set writes local-only), so a rebuild must not silently drop locally-cached
    provider/paid data. ``[]`` if the DB / table is absent (first build, pre-3c-C).
    Read + the subsequent swap + re-write run under ``_CACHE_WRITE_LOCK`` so a
    concurrent set_financial_cache cannot be lost in the swap window."""
    if not Path(path).exists():
        return []
    try:
        src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return []
    try:
        if not _table_exists(src, "financial_cache"):
            return []
        return src.execute(
            "SELECT cache_key, source, ticker, data, fetched_at, expires_at FROM financial_cache"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        src.close()


def bootstrap_market(out_path: Optional[str] = None,
                     progress_cb: Optional[Callable[[int, int], None]] = None,
                     batch: int = 20000) -> dict:
    """Full rebuild of the local market DB (prices + news + iv + fundamentals) from
    PG. Builds to a ``.building`` temp and atomically swaps it in ONLY if ALL
    domains validate (row-count + checksum), so a failed rebuild leaves any
    existing DB untouched. Returns a per-domain result dict with overall ``match``."""
    path = out_path or resolve_market_db_path()
    tmp = path + ".building"
    pg = _pg_conn()
    try:
        cur = pg.cursor()
        cur.execute("SELECT COUNT(*) FROM prices")
        price_total = cur.fetchone()[0]
        pg_price_sum = _pg_group_counts(cur, _PG_PRICE_CHECKSUM)
        cur.execute("SELECT COUNT(*) FROM news")
        news_total = cur.fetchone()[0]
        pg_news_sum = _pg_news_checksum(cur)
        cur.execute("SELECT COUNT(*) FROM iv_history")
        iv_total = cur.fetchone()[0]
        pg_iv_sum = _pg_ticker_idsum(cur, _IV_CHECKSUM_SQL)
        cur.execute("SELECT COUNT(*) FROM fundamentals")
        fund_total = cur.fetchone()[0]
        pg_fund_sum = _pg_ticker_idsum(cur, _FUND_CHECKSUM_SQL)
        grand = price_total + news_total + iv_total + fund_total

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(tmp).unlink(missing_ok=True)
        sconn = sqlite3.connect(tmp)
        try:
            for schema in (_PRICES_SCHEMA, _NEWS_SCHEMA, _IV_SCHEMA, _FUND_SCHEMA,
                           _FIN_CACHE_SCHEMA, _META_SCHEMA):
                sconn.executescript(schema)
            _copy_table(cur, sconn, _PG_PRICES_SELECT, _PRICE_INSERT,
                        price_total, progress_cb, 0, grand, batch)
            _copy_table(cur, sconn, _PG_NEWS_SELECT, _NEWS_INSERT,
                        news_total, progress_cb, price_total, grand, batch)
            _copy_table(cur, sconn, _PG_IV_SELECT, _IV_INSERT,
                        iv_total, progress_cb, price_total + news_total, grand, batch)
            _copy_table(cur, sconn, _PG_FUND_SELECT, _FUND_INSERT,
                        fund_total, progress_cb, price_total + news_total + iv_total, grand, batch)
            sconn.execute("INSERT INTO news_fts(news_fts) VALUES('rebuild')")  # build FTS index
            sconn.commit()  # financial_cache is carried over under-lock at swap time
            # NOTE: ticker canonicalization is deliberately deferred to AFTER validation
            # (see the `if match:` block). Canon folds alias spellings (BRK.B → BRK B),
            # which would shift the SQLite (source,ticker) checksum key set away from the
            # pre-canon PG fingerprint and make validation spuriously fail. Validate in the
            # same spelling PG has; canonicalize the VALIDATED temp just before the swap.

            local_prices = sconn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
            sq_price_sum = _sqlite_group_counts(sconn, _SQ_PRICE_CHECKSUM)
            local_news = sconn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
            sq_news_sum = _sqlite_news_checksum(sconn)
            local_iv = sconn.execute("SELECT COUNT(*) FROM iv_history").fetchone()[0]
            sq_iv_sum = _sqlite_ticker_idsum(sconn, _IV_CHECKSUM_SQL)
            local_fund = sconn.execute("SELECT COUNT(*) FROM fundamentals").fetchone()[0]
            sq_fund_sum = _sqlite_ticker_idsum(sconn, _FUND_CHECKSUM_SQL)
        finally:
            sconn.close()
    finally:
        pg.close()

    prices_match = local_prices == price_total and sq_price_sum == pg_price_sum
    news_match = local_news == news_total and sq_news_sum == pg_news_sum
    iv_match = local_iv == iv_total and sq_iv_sum == pg_iv_sum
    fund_match = local_fund == fund_total and sq_fund_sum == pg_fund_sum
    match = prices_match and news_match and iv_match and fund_match
    fin_cache_carried = 0
    if match:
        # Hold _CACHE_WRITE_LOCK across read-old → write-into-tmp → swap (NOT the
        # multi-minute build): financial_cache is local-primary, so the carry-over
        # must capture the OLD cache and land it in the NEW DB atomically w.r.t.
        # set_financial_cache. The lock queues a racing cache write so it lands in the
        # swapped-in DB rather than being dropped with the old inode. Window held is
        # just the swap (small cache + os.replace), ~ms.
        # Canonicalize the VALIDATED temp (post-validation, pre-swap): tmp is private to
        # this build, so reconciling alias spellings here can't race another writer, and
        # validation already compared SQLite↔PG in the pre-canon spelling. PK-safe.
        cnconn = sqlite3.connect(tmp, timeout=10.0)
        try:
            cnconn.execute("PRAGMA busy_timeout = 10000")
            _ensure_ticker_aliases(cnconn)
            for _t in ("prices", "news", "iv_history", "fundamentals"):
                _canonicalize_table_tickers(cnconn, _t)
        finally:
            cnconn.close()
        with _CACHE_WRITE_LOCK:
            carried_rows = _read_fin_cache_rows(path)  # old cache (committed state)
            # Write the carried cache INTO tmp BEFORE the swap. tmp is private to this
            # build (no other connection touches it — unlike the live `path`, which an
            # overlapping incremental_update may write), so there is no SQLITE_BUSY
            # race, and the swap only happens once the cache is safely in the new file.
            # financial_cache is best-effort/TTL'd → a (rare) carry-over failure is
            # logged + reported as carried=0, not allowed to abort a validated rebuild.
            try:
                if carried_rows:
                    cconn = sqlite3.connect(tmp, timeout=10.0)
                    try:
                        cconn.execute("PRAGMA busy_timeout = 10000")
                        cconn.executemany(_FIN_CACHE_INSERT, carried_rows)
                        cconn.commit()
                    finally:
                        cconn.close()
                fin_cache_carried = len(carried_rows)  # only after a successful write
            except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
                logger.warning("financial_cache carry-over failed (%s); cache will "
                               "re-populate via promotion/re-fetch", e)
            os.replace(tmp, path)  # atomic swap-in (cache already inside the new file)
            # CRITICAL: drop the OLD inode's WAL sidecars as part of the swap. ``tmp``
            # was built with a rollback journal (self-contained, no WAL of its own),
            # but a ``market_data.db-wal``/``-shm`` may exist from the live DB's
            # writers (since 3c-C, set_financial_cache opens a WAL connection on the
            # live file). SQLite associates those sidecars by FILENAME, not inode, so a
            # stale WAL left at swap time would be replayed onto the freshly-built NEW
            # inode → silent stale-data corruption escaping the pre-swap validation.
            Path(path + "-wal").unlink(missing_ok=True)
            Path(path + "-shm").unlink(missing_ok=True)
            try:
                wconn = sqlite3.connect(path)
                try:
                    wconn.execute("PRAGMA journal_mode = WAL")
                finally:
                    wconn.close()
            except sqlite3.OperationalError:
                pass
    else:
        Path(tmp).unlink(missing_ok=True)  # keep any existing good DB intact
    return {
        "match": match,
        "prices": {"rows": local_prices, "total": price_total, "match": prices_match},
        "news": {"rows": local_news, "total": news_total, "match": news_match},
        "iv": {"rows": local_iv, "total": iv_total, "match": iv_match},
        "fundamentals": {"rows": local_fund, "total": fund_total, "match": fund_match},
        # local-primary; carried over (not validated against PG, not part of `match`)
        "financial_cache": {"carried_over": fin_cache_carried},
    }


def validate_market(out_path: Optional[str] = None) -> dict:
    """Compare local vs PG per domain (prices + news + iv + fundamentals): row
    count + checksum (prices/news group sums; iv/fundamentals per-ticker id sums)."""
    path = out_path or resolve_market_db_path()
    if not Path(path).exists():
        return {"exists": False, "match": False}
    pg = _pg_conn()
    try:
        cur = pg.cursor()
        cur.execute("SELECT COUNT(*) FROM prices")
        pg_price_rows = cur.fetchone()[0]
        pg_price_sum = _pg_group_counts(cur, _PG_PRICE_CHECKSUM)
        cur.execute("SELECT COUNT(*) FROM news")
        pg_news_rows = cur.fetchone()[0]
        pg_news_sum = _pg_news_checksum(cur)
        cur.execute("SELECT COUNT(*) FROM iv_history")
        pg_iv_rows = cur.fetchone()[0]
        pg_iv_sum = _pg_ticker_idsum(cur, _IV_CHECKSUM_SQL)
        cur.execute("SELECT COUNT(*) FROM fundamentals")
        pg_fund_rows = cur.fetchone()[0]
        pg_fund_sum = _pg_ticker_idsum(cur, _FUND_CHECKSUM_SQL)
    finally:
        pg.close()
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        lp = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0] if _table_exists(conn, "prices") else 0
        sq_price_sum = _sqlite_group_counts(conn, _SQ_PRICE_CHECKSUM) if _table_exists(conn, "prices") else {}
        ln = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0] if _table_exists(conn, "news") else 0
        sq_news_sum = _sqlite_news_checksum(conn) if _table_exists(conn, "news") else {}
        liv = conn.execute("SELECT COUNT(*) FROM iv_history").fetchone()[0] if _table_exists(conn, "iv_history") else 0
        sq_iv_sum = _sqlite_ticker_idsum(conn, _IV_CHECKSUM_SQL) if _table_exists(conn, "iv_history") else {}
        lf = conn.execute("SELECT COUNT(*) FROM fundamentals").fetchone()[0] if _table_exists(conn, "fundamentals") else 0
        sq_fund_sum = _sqlite_ticker_idsum(conn, _FUND_CHECKSUM_SQL) if _table_exists(conn, "fundamentals") else {}
        aliases = _load_ticker_aliases(conn)  # local DB is post-canon; fold PG into the same space
    finally:
        conn.close()
    # The local DB is canonicalized (BRK.B → BRK B); PG is not. Fold the PG-side checksum
    # keys into canonical space before comparing so canon doesn't spuriously fail validation
    # (no-op when PG has no alias spelling). Row totals are unaffected by canon.
    if aliases:
        pg_price_sum = _fold_checksum_aliases(pg_price_sum, aliases, ticker_pos=0)
        pg_news_sum = _fold_checksum_aliases(pg_news_sum, aliases, ticker_pos=1)
        pg_iv_sum = _fold_checksum_aliases(pg_iv_sum, aliases, ticker_pos=None)
        pg_fund_sum = _fold_checksum_aliases(pg_fund_sum, aliases, ticker_pos=None)
    prices_match = lp == pg_price_rows and sq_price_sum == pg_price_sum
    news_match = ln == pg_news_rows and sq_news_sum == pg_news_sum
    iv_match = liv == pg_iv_rows and sq_iv_sum == pg_iv_sum
    fund_match = lf == pg_fund_rows and sq_fund_sum == pg_fund_sum
    return {
        "exists": True,
        "match": prices_match and news_match and iv_match and fund_match,
        "prices": {"local_rows": lp, "pg_rows": pg_price_rows, "match": prices_match},
        "news": {"local_rows": ln, "pg_rows": pg_news_rows, "match": news_match},
        "iv": {"local_rows": liv, "pg_rows": pg_iv_rows, "match": iv_match},
        "fundamentals": {"local_rows": lf, "pg_rows": pg_fund_rows, "match": fund_match},
    }


# --- incremental update (delta since latest) ----------------------------------

def _record_sync_meta(sconn, domain: str, rows_added: int, error: Optional[str]) -> None:
    now = _now()
    last_success = None if error else now
    sconn.execute(
        "INSERT INTO market_sync_meta (domain, last_success, last_error, rows_added, updated_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(domain) DO UPDATE SET "
        "  last_success = COALESCE(excluded.last_success, market_sync_meta.last_success), "
        "  last_error = excluded.last_error, rows_added = excluded.rows_added, "
        "  updated_at = excluded.updated_at",
        (domain, last_success, error, rows_added, now),
    )
    sconn.commit()


def _incr_domain(sconn, domain: str, local_max_sql: str, pg_select_incr: str,
                 pg_select_full: str, insert_sql: str, batch: int) -> dict:
    """One domain's delta append (PG newer-than-local). Provider failure is NOT
    fatal: it is recorded to market_sync_meta.last_error and returned, not raised."""
    try:
        local_max = sconn.execute(local_max_sql).fetchone()[0]
        pg = _pg_conn()
        try:
            cur = pg.cursor()
            if local_max in (None, 0, ""):
                cur.execute(pg_select_full)
            else:
                cur.execute(pg_select_incr, (local_max,))
            before = sconn.total_changes
            while True:
                rows = cur.fetchmany(batch)
                if not rows:
                    break
                sconn.executemany(insert_sql, rows)
            added = sconn.total_changes - before
            sconn.commit()
        finally:
            pg.close()
        # keep the FTS index in sync for newly-inserted news rows
        if domain == "news" and added:
            sconn.execute(
                "INSERT INTO news_fts(rowid, title, description) "
                "SELECT id, title, description FROM news WHERE id > ?",
                (local_max or 0,),
            )
            sconn.commit()
        _record_sync_meta(sconn, domain, rows_added=added, error=None)
        return {"ok": True, "rows_added": added, "error": None}
    except Exception as e:  # noqa: BLE001 — provider down etc. must not be fatal
        logger.warning(f"incremental {domain} update failed: {e}")
        try:
            _record_sync_meta(sconn, domain, rows_added=0, error=str(e))
        except sqlite3.OperationalError:
            pass
        return {"ok": False, "rows_added": 0, "error": str(e)}


def _incr_prices(sconn, batch: int) -> dict:
    """Prices delta, PER (ticker, interval) — NOT a single global datetime>max.

    A global max would skip a newly-added ticker entirely (its historical bars are
    older than other tickers' current max) — the hole this fixes. We pass each
    local group's max into PG via a VALUES join: groups present locally pull only
    ``datetime > their max``; groups absent locally (new ticker/interval) pull all
    their rows (``v.maxdt IS NULL``). Provider failure is recorded, not fatal."""
    try:
        groups = sconn.execute(
            "SELECT ticker, interval, MAX(datetime) FROM prices GROUP BY ticker, interval"
        ).fetchall()
        pg = _pg_conn()
        try:
            cur = pg.cursor()
            if not groups:
                cur.execute(_PG_PRICES_SELECT)  # empty local prices → full pull
            else:
                values = ",".join(["(%s,%s,%s::timestamptz)"] * len(groups))
                params: list = []
                for ticker, interval, maxdt in groups:
                    params += [ticker, interval, maxdt]
                cur.execute(
                    f"SELECT {_PG_PRICES_COLS_P} FROM prices p "
                    f"LEFT JOIN (VALUES {values}) AS v(ticker, interval, maxdt) "
                    "  ON p.ticker = v.ticker AND p.interval = v.interval "
                    "WHERE v.maxdt IS NULL OR p.datetime > v.maxdt "
                    "ORDER BY p.ticker, p.interval, p.datetime",
                    params,
                )
            before = sconn.total_changes
            while True:
                rows = cur.fetchmany(batch)
                if not rows:
                    break
                sconn.executemany(_PRICE_INSERT, rows)
            added = sconn.total_changes - before
            sconn.commit()
        finally:
            pg.close()
        _record_sync_meta(sconn, "prices", rows_added=added, error=None)
        return {"ok": True, "rows_added": added, "error": None}
    except Exception as e:  # noqa: BLE001 — provider down etc. must not be fatal
        logger.warning(f"incremental prices update failed: {e}")
        try:
            _record_sync_meta(sconn, "prices", rows_added=0, error=str(e))
        except sqlite3.OperationalError:
            pass
        return {"ok": False, "rows_added": 0, "error": str(e)}


def incremental_update(out_path: Optional[str] = None, batch: int = 20000) -> dict:
    """Append-only delta refresh of the local market DB (prices + news + iv +
    fundamentals) from PG — only rows newer than the local max (prices: per
    (ticker,interval) datetime; news/iv/fundamentals: id). Writes in place to the
    live WAL DB (no atomic swap), so routing can stay active. A provider/PG failure
    in one domain is recorded, not fatal to the others.

    Requires an existing local DB (bootstrap first). Returns per-domain results."""
    path = out_path or resolve_market_db_path()
    if not Path(path).exists():
        return {"ok": False, "error": "local market DB does not exist — run a bootstrap first",
                "prices": None, "news": None, "iv": None, "fundamentals": None}
    sconn = sqlite3.connect(path, timeout=10.0)
    try:
        try:
            sconn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError:
            pass
        sconn.execute("PRAGMA busy_timeout = 10000")
        sconn.executescript(_META_SCHEMA)  # tolerate a pre-meta DB
        sconn.executescript(_IV_SCHEMA)    # tolerate a pre-iv/fundamentals DB
        sconn.executescript(_FUND_SCHEMA)
        _ensure_news_sentiment_columns(sconn)  # tolerate a pre-sentiment news table
        prices = _incr_prices(sconn, batch)  # per-(ticker,interval); catches new tickers
        news = _incr_domain(sconn, "news", "SELECT COALESCE(MAX(id), 0) FROM news",
                            _PG_NEWS_SELECT_INCR, _PG_NEWS_SELECT, _NEWS_INSERT, batch)
        iv = _incr_domain(sconn, "iv", "SELECT COALESCE(MAX(id), 0) FROM iv_history",
                          _PG_IV_SELECT_INCR, _PG_IV_SELECT, _IV_INSERT, batch)
        fundamentals = _incr_domain(sconn, "fundamentals", "SELECT COALESCE(MAX(id), 0) FROM fundamentals",
                                    _PG_FUND_SELECT_INCR, _PG_FUND_SELECT, _FUND_INSERT, batch)
        # Canonicalize tickers AFTER the mirror so newly-pulled alias rows (e.g. a PG
        # 'BRK.B') are reconciled to the canonical spelling across all domains. PK-safe.
        _ensure_ticker_aliases(sconn)
        for _t in ("prices", "news", "iv_history", "fundamentals"):
            try:
                _canonicalize_table_tickers(sconn, _t)
            except sqlite3.OperationalError:
                pass  # table absent on a pre-domain DB — tolerate
    finally:
        sconn.close()
    return {"ok": prices["ok"] and news["ok"] and iv["ok"] and fundamentals["ok"],
            "prices": prices, "news": news, "iv": iv, "fundamentals": fundamentals}


def read_sync_meta(out_path: Optional[str] = None) -> dict:
    """Per-domain incremental-sync status (read-only). {} entries if never run."""
    path = out_path or resolve_market_db_path()
    out = {"prices": None, "news": None, "iv": None, "fundamentals": None}
    if not Path(path).exists():
        return out
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return out
    try:
        if not _table_exists(conn, "market_sync_meta"):
            return out
        for r in conn.execute(
            "SELECT domain, last_success, last_error, rows_added, updated_at FROM market_sync_meta"
        ).fetchall():
            out[r[0]] = {"last_success": r[1], "last_error": r[2],
                         "rows_added": r[3], "updated_at": r[4]}
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()
    return out


# --- in-process job runner (single sidecar) -----------------------------------

_JOBS: Dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def start_bootstrap_job(out_path: Optional[str] = None) -> dict:
    """Start a background market bootstrap (idempotent while running). Returns the job."""
    path = out_path or resolve_market_db_path()
    with _JOBS_LOCK:
        for j in _JOBS.values():
            if j["kind"] == "bootstrap_market" and j["status"] == "running":
                return dict(j)  # already running → return it (don't double-run)
        job_id = uuid.uuid4().hex[:12]
        job = {"id": job_id, "kind": "bootstrap_market", "status": "running",
               "progress": {"written": 0, "total": 0}, "result": None, "error": None}
        _JOBS[job_id] = job

    def _run():
        try:
            def cb(written, total):
                _JOBS[job_id]["progress"] = {"written": written, "total": total}
            res = bootstrap_market(path, progress_cb=cb)
            _JOBS[job_id]["result"] = res
            if res.get("match"):
                _JOBS[job_id]["status"] = "done"
            else:
                _JOBS[job_id]["status"] = "error"
                _JOBS[job_id]["error"] = "validation mismatch (rebuild discarded; existing DB kept)"
        except Exception as e:  # noqa: BLE001 — surface any failure to the UI
            _JOBS[job_id]["status"] = "error"
            _JOBS[job_id]["error"] = str(e)

    threading.Thread(target=_run, name=f"bootstrap-{job_id}", daemon=True).start()
    return dict(_JOBS[job_id])


def start_update_job(out_path: Optional[str] = None) -> dict:
    """Start a background incremental update (idempotent while running)."""
    path = out_path or resolve_market_db_path()
    with _JOBS_LOCK:
        for j in _JOBS.values():
            if j["kind"] == "update_market" and j["status"] == "running":
                return dict(j)
        job_id = uuid.uuid4().hex[:12]
        job = {"id": job_id, "kind": "update_market", "status": "running",
               "progress": {"written": 0, "total": 0}, "result": None, "error": None}
        _JOBS[job_id] = job

    def _run():
        try:
            res = incremental_update(path)
            _JOBS[job_id]["result"] = res
            # incremental is best-effort PER DOMAIN (provider down ≠ fatal); the job
            # is "error" only if NO domain succeeded (e.g. missing DB / PG fully
            # down), else "done". Consider all 4 domains, not just prices/news, so an
            # iv/fundamentals failure is surfaced in job["error"] too.
            domains = [res.get("prices"), res.get("news"), res.get("iv"), res.get("fundamentals")]
            any_ok = any((d or {}).get("ok") for d in domains)
            _JOBS[job_id]["status"] = "done" if res.get("ok") or any_ok else "error"
            if not res.get("ok"):
                errs = [(d or {}).get("error") for d in domains]
                _JOBS[job_id]["error"] = res.get("error") or "; ".join(e for e in errs if e) or None
        except Exception as e:  # noqa: BLE001
            _JOBS[job_id]["status"] = "error"
            _JOBS[job_id]["error"] = str(e)

    threading.Thread(target=_run, name=f"update-{job_id}", daemon=True).start()
    return dict(_JOBS[job_id])


def get_job(job_id: str) -> Optional[dict]:
    j = _JOBS.get(job_id)
    return dict(j) if j else None
