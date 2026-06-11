"""
sa_capture_store — schema + connection discipline for data/sa_capture.db (slice 3d).

The local WRITE-TARGET store for the Seeking-Alpha capture domain (sql/007-015
ported). Unlike market_data.db (a PG read mirror), sa_capture.db becomes the
AUTHORITY at cutover: captures land here first and PG never sees them again —
so there is deliberately NO "rebuild from PG" affordance anywhere (it would
destroy post-cutover captures), no PG read fallback, and validation against PG
is one-shot at migration time only (locked runbook L1/L5).

Writer process model: the native messaging host is a FRESH OS process per
browser message, and the sidecar/CLI may read concurrently — so in-process
locks provide zero exclusion here. Every connection therefore self-arms:
WAL + busy_timeout + PRAGMA foreign_keys=ON (the sa_comment_signals ON DELETE
CASCADE is load-bearing for comment dedupe), and schema setup is cross-process
safe (PRAGMA user_version fast-path; first-run DDL is fully idempotent — see
the precise guarantee in ensure_schema's docstring: it is NOT serialized).

Type conventions (runbook §1 / SPEC §4.1.4):
  - TIMESTAMPTZ → TEXT, ONE canonical format: UTC ISO-8601 seconds
    'YYYY-MM-DDTHH:MM:SS+00:00' (mark-stale becomes a lexicographic TEXT
    compare — format uniformity is correctness-critical; see canon_ts()).
  - DATE → TEXT 'YYYY-MM-DD'; BOOLEAN → INTEGER 0/1; NUMERIC → REAL;
    JSONB → TEXT (json.dumps); BIGSERIAL → INTEGER PRIMARY KEY (ids preserved
    verbatim by the migration; AUTOINCREMENT-free rowid continues past max).
  - TEXT[] → JUNCTION TABLES (locked L8 — queryable fields are never JSON
    arrays): sa_market_news.tickers → sa_market_news_tickers;
    sa_comment_signals.ticker_mentions/candidate_mentions →
    sa_signal_ticker_mentions / sa_signal_candidate_mentions.
  - PG tsvector GIN search → FTS5 external-content mirrors kept in sync by
    triggers (porter+unicode61, the shipped 3b news precedent).
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCHEMA_VERSION = 1
USE_LOCAL_SA_KEY = "use_local_sa"  # profile_settings key for the persisted flip toggle


def resolve_sa_db_path() -> str:
    """``ARKSCOPE_SA_DB`` or the default ``<repo>/data/sa_capture.db`` (runbook L1:
    plan naming; absolute — the native host chdir's, but never rely on cwd)."""
    return os.environ.get("ARKSCOPE_SA_DB") or str(_PROJECT_ROOT / "data" / "sa_capture.db")


# --- canonical value encoding ---------------------------------------------------

def canon_ts(value) -> Optional[str]:
    """Canonicalize ANY timestamp-ish value to the ONE on-disk format:
    'YYYY-MM-DDTHH:MM:SS+00:00' (UTC, seconds). Lexicographic order == time order,
    which apply_sa_refresh's mark-stale comparison depends on. None passes through."""
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip().replace("Z", "+00:00")
        if not s:
            return None
        # PG text dumps use short offsets ('+00', '+0530'); Python 3.10's
        # fromisoformat needs '+HH:MM' — normalize before parsing.
        if len(s) >= 3 and s[-3] in "+-" and s[-2:].isdigit():
            s += ":00"
        elif len(s) >= 5 and s[-5] in "+-" and s[-4:].isdigit():
            s = s[:-2] + ":" + s[-2:]
        try:
            value = datetime.fromisoformat(s)
        except ValueError:
            logger.warning(f"canon_ts: unparseable timestamp {value!r}")
            return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)  # treat naive as UTC
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")
    logger.warning(f"canon_ts: unsupported type {type(value).__name__}")
    return None


def canon_date(value) -> Optional[str]:
    """Canonicalize a date-ish value to 'YYYY-MM-DD' TEXT (or None)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    s = str(value).strip()
    return s[:10] if s else None


def now_ts() -> str:
    """The canonical 'now' string (replaces SQL NOW())."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- schema ----------------------------------------------------------------------

# Ports sql/007 + 014/015 final state: the original UNIQUE(symbol,picked_date[,status])
# constraints are GONE — identity is the two PARTIAL unique indexes only.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS sa_alpha_picks (
    id                  INTEGER PRIMARY KEY,
    symbol              TEXT NOT NULL,
    company             TEXT NOT NULL,
    picked_date         TEXT NOT NULL,             -- 'YYYY-MM-DD'
    closed_date         TEXT,                      -- 'YYYY-MM-DD'
    portfolio_status    TEXT NOT NULL DEFAULT 'current',
    is_stale            INTEGER NOT NULL DEFAULT 0,
    return_pct          REAL,
    sector              TEXT,
    sa_rating           TEXT,
    holding_pct         REAL,
    detail_report       TEXT,
    detail_fetched_at   TEXT,
    raw_data            TEXT,                      -- JSON
    last_seen_snapshot  TEXT,                      -- canonical UTC ISO (mark-stale compares!)
    canonical_article_id TEXT,
    fetched_at          TEXT,
    updated_at          TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sa_picks_current_unique
    ON sa_alpha_picks(symbol, picked_date, portfolio_status)
    WHERE portfolio_status = 'current';
CREATE UNIQUE INDEX IF NOT EXISTS idx_sa_picks_closed_unique
    ON sa_alpha_picks(symbol, picked_date, portfolio_status, closed_date)
    WHERE portfolio_status = 'closed';
CREATE INDEX IF NOT EXISTS idx_sa_picks_status ON sa_alpha_picks(portfolio_status);
CREATE INDEX IF NOT EXISTS idx_sa_picks_symbol ON sa_alpha_picks(symbol);
CREATE INDEX IF NOT EXISTS idx_sa_picks_snapshot ON sa_alpha_picks(last_seen_snapshot);
CREATE INDEX IF NOT EXISTS idx_sa_picks_stale ON sa_alpha_picks(is_stale) WHERE is_stale = 1;
CREATE INDEX IF NOT EXISTS idx_sa_picks_canonical_article ON sa_alpha_picks(canonical_article_id);

CREATE TABLE IF NOT EXISTS sa_refresh_meta (
    scope            TEXT PRIMARY KEY,             -- 'current' / 'closed'
    last_attempt_at  TEXT,
    last_success_at  TEXT,
    snapshot_ts      TEXT,
    row_count        INTEGER DEFAULT 0,
    ok               INTEGER NOT NULL DEFAULT 0,
    last_error       TEXT,
    updated_at       TEXT
);

CREATE TABLE IF NOT EXISTS sa_articles (
    id                  INTEGER PRIMARY KEY,
    article_id          TEXT NOT NULL UNIQUE,
    url                 TEXT NOT NULL,
    title               TEXT NOT NULL,
    ticker              TEXT,
    author              TEXT,
    published_date      TEXT,                      -- 'YYYY-MM-DD'
    article_type        TEXT,
    body_markdown       TEXT,
    comments_count      INTEGER DEFAULT 0,
    detail_fetched_at   TEXT,
    comments_fetched_at TEXT,
    raw_data            TEXT,                      -- JSON
    fetched_at          TEXT,
    updated_at          TEXT
);
CREATE INDEX IF NOT EXISTS idx_sa_articles_ticker ON sa_articles(ticker);
CREATE INDEX IF NOT EXISTS idx_sa_articles_published ON sa_articles(published_date DESC);
CREATE INDEX IF NOT EXISTS idx_sa_articles_type ON sa_articles(article_type);

CREATE TABLE IF NOT EXISTS sa_article_comments (
    id                INTEGER PRIMARY KEY,
    article_id        TEXT NOT NULL REFERENCES sa_articles(article_id),
    comment_id        TEXT NOT NULL,
    parent_comment_id TEXT,
    commenter         TEXT,
    comment_text      TEXT NOT NULL,
    upvotes           INTEGER DEFAULT 0,
    comment_date      TEXT,
    fetched_at        TEXT,
    UNIQUE(article_id, comment_id)
);
CREATE INDEX IF NOT EXISTS idx_sa_comments_article ON sa_article_comments(article_id);

CREATE TABLE IF NOT EXISTS sa_market_news (
    id                INTEGER PRIMARY KEY,
    news_id           TEXT NOT NULL UNIQUE,
    url               TEXT NOT NULL,
    title             TEXT NOT NULL,
    published_at      TEXT,
    published_text    TEXT,
    category          TEXT,
    summary           TEXT,
    comments_count    INTEGER DEFAULT 0,
    raw_data          TEXT,                        -- JSON
    body_markdown     TEXT,
    detail_fetched_at TEXT,
    fetched_at        TEXT,
    updated_at        TEXT
);
CREATE INDEX IF NOT EXISTS idx_sa_market_news_published ON sa_market_news(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_sa_market_news_detail_fetched ON sa_market_news(detail_fetched_at DESC);

-- TEXT[] tickers → junction (locked L8). Row-deletes cascade; the writer replaces
-- a news row's set with delete+insert inside its upsert transaction.
CREATE TABLE IF NOT EXISTS sa_market_news_tickers (
    news_row_id INTEGER NOT NULL REFERENCES sa_market_news(id) ON DELETE CASCADE,
    ticker      TEXT NOT NULL,
    PRIMARY KEY (news_row_id, ticker)
);
CREATE INDEX IF NOT EXISTS idx_sa_mn_tickers_ticker ON sa_market_news_tickers(ticker);

CREATE TABLE IF NOT EXISTS sa_comment_signals (
    comment_row_id     INTEGER PRIMARY KEY
                       REFERENCES sa_article_comments(id) ON DELETE CASCADE,
    article_id         TEXT NOT NULL,
    comment_id         TEXT NOT NULL,
    keyword_buckets    TEXT NOT NULL DEFAULT '{}', -- JSON
    high_value_score   REAL NOT NULL DEFAULT 0.0,
    needs_verification INTEGER NOT NULL DEFAULT 0,
    rule_set_version   TEXT NOT NULL,
    extracted_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sa_comment_signals_score ON sa_comment_signals(high_value_score DESC);
CREATE INDEX IF NOT EXISTS idx_sa_comment_signals_extracted
    ON sa_comment_signals(extracted_at DESC, rule_set_version);
CREATE INDEX IF NOT EXISTS idx_sa_comment_signals_article ON sa_comment_signals(article_id);

CREATE TABLE IF NOT EXISTS sa_signal_ticker_mentions (
    comment_row_id INTEGER NOT NULL REFERENCES sa_comment_signals(comment_row_id) ON DELETE CASCADE,
    ticker         TEXT NOT NULL,
    PRIMARY KEY (comment_row_id, ticker)
);
CREATE INDEX IF NOT EXISTS idx_sa_sig_tm_ticker ON sa_signal_ticker_mentions(ticker);

CREATE TABLE IF NOT EXISTS sa_signal_candidate_mentions (
    comment_row_id INTEGER NOT NULL REFERENCES sa_comment_signals(comment_row_id) ON DELETE CASCADE,
    ticker         TEXT NOT NULL,
    PRIMARY KEY (comment_row_id, ticker)
);

-- FTS5 mirrors (3b news precedent: porter+unicode61), kept in sync by triggers so
-- every writer — fresh host processes included — maintains them automatically.
CREATE VIRTUAL TABLE IF NOT EXISTS sa_articles_fts
    USING fts5(title, body_markdown, content='sa_articles', content_rowid='id',
               tokenize='porter unicode61');
CREATE TRIGGER IF NOT EXISTS sa_articles_fts_ai AFTER INSERT ON sa_articles BEGIN
    INSERT INTO sa_articles_fts(rowid, title, body_markdown)
        VALUES (new.id, new.title, new.body_markdown);
END;
CREATE TRIGGER IF NOT EXISTS sa_articles_fts_ad AFTER DELETE ON sa_articles BEGIN
    INSERT INTO sa_articles_fts(sa_articles_fts, rowid, title, body_markdown)
        VALUES ('delete', old.id, old.title, old.body_markdown);
END;
CREATE TRIGGER IF NOT EXISTS sa_articles_fts_au AFTER UPDATE ON sa_articles BEGIN
    INSERT INTO sa_articles_fts(sa_articles_fts, rowid, title, body_markdown)
        VALUES ('delete', old.id, old.title, old.body_markdown);
    INSERT INTO sa_articles_fts(rowid, title, body_markdown)
        VALUES (new.id, new.title, new.body_markdown);
END;

CREATE VIRTUAL TABLE IF NOT EXISTS sa_market_news_fts
    USING fts5(title, summary, content='sa_market_news', content_rowid='id',
               tokenize='porter unicode61');
CREATE TRIGGER IF NOT EXISTS sa_mn_fts_ai AFTER INSERT ON sa_market_news BEGIN
    INSERT INTO sa_market_news_fts(rowid, title, summary)
        VALUES (new.id, new.title, new.summary);
END;
CREATE TRIGGER IF NOT EXISTS sa_mn_fts_ad AFTER DELETE ON sa_market_news BEGIN
    INSERT INTO sa_market_news_fts(sa_market_news_fts, rowid, title, summary)
        VALUES ('delete', old.id, old.title, old.summary);
END;
CREATE TRIGGER IF NOT EXISTS sa_mn_fts_au AFTER UPDATE ON sa_market_news BEGIN
    INSERT INTO sa_market_news_fts(sa_market_news_fts, rowid, title, summary)
        VALUES ('delete', old.id, old.title, old.summary);
    INSERT INTO sa_market_news_fts(rowid, title, summary)
        VALUES (new.id, new.title, new.summary);
END;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""


def connect(db_path: Optional[str] = None, *, read_only: bool = False) -> sqlite3.Connection:
    """Open sa_capture.db with the per-connection discipline EVERY caller needs
    (fresh-per-message host processes get no help from in-process state):
    WAL + busy_timeout + foreign_keys=ON, schema ensured (rw only), Row factory.
    """
    path = db_path or resolve_sa_db_path()
    if read_only:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        pass
    conn.execute("PRAGMA foreign_keys = ON")  # CASCADE is load-bearing (signals dedupe)
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Cross-process-safe, cheap-when-current schema setup.

    Fast path: PRAGMA user_version == SCHEMA_VERSION → return (one pragma read per
    message — keeps the fresh-process host under the extension's 2s telemetry
    budget).

    Slow path — PRECISE guarantee (do not overstate): BEGIN IMMEDIATE only
    serializes the version RE-CHECK; sqlite3's executescript() COMMITS that open
    transaction before running the script (empirically verified), so the DDL
    itself executes statement-by-statement OUTSIDE any explicit transaction and
    two processes MAY interleave it. Safety therefore comes from the DDL being
    fully IDEMPOTENT (CREATE IF NOT EXISTS / INSERT OR IGNORE / PRAGMA), which the
    two-real-process race test exercises. ⚠️ A future SCHEMA_VERSION bump with
    NON-idempotent migration statements must add real cross-process exclusion
    (flock, like data_scheduler._FileLock) — this function does not provide it."""
    if conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION:
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        if conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION:
            conn.execute("COMMIT")
            return
        conn.executescript(_SCHEMA)  # executescript implicitly commits the txn above
        conn.execute("INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                     (SCHEMA_VERSION, now_ts()))
        conn.execute(f"PRAGMA user_version = {int(SCHEMA_VERSION)}")
        conn.commit()
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass
        raise
