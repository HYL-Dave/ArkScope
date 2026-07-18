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
safe (PRAGMA user_version fast-path; first-run DDL is fully idempotent, while
versioned rebuilds are serialized and transactional — see ensure_schema).

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

import json
import logging
import os
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCHEMA_VERSION = 2
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
CREATE TABLE IF NOT EXISTS sa_pick_lineages (
    lineage_id   INTEGER PRIMARY KEY,
    symbol_key   TEXT NOT NULL CHECK(symbol_key <> '' AND symbol_key = UPPER(TRIM(symbol_key))),
    picked_date  TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    UNIQUE(symbol_key, picked_date)
);

CREATE TABLE IF NOT EXISTS sa_alpha_picks (
    id                  INTEGER PRIMARY KEY,
    lineage_id          INTEGER NOT NULL
                        REFERENCES sa_pick_lineages(lineage_id) ON DELETE RESTRICT,
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
CREATE INDEX IF NOT EXISTS idx_sa_picks_lineage_status
    ON sa_alpha_picks(lineage_id, portfolio_status, is_stale);

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
    updated_at          TEXT,
    list_ticker                TEXT,
    list_ticker_observed_at    TEXT,
    detail_ticker              TEXT,
    detail_ticker_observed_at  TEXT,
    comments_count_observed_at TEXT,
    provider_comments_count_at_last_scan INTEGER
        CHECK(provider_comments_count_at_last_scan IS NULL
              OR provider_comments_count_at_last_scan >= 0),
    comment_recovery_state TEXT NOT NULL DEFAULT 'repaired'
        CHECK(comment_recovery_state IN
              ('repaired', 'pending', 'unreachable_terminal')),
    comment_recovery_started_at TEXT,
    comment_recovery_baseline_max_row_id INTEGER
        CHECK(comment_recovery_baseline_max_row_id IS NULL
              OR comment_recovery_baseline_max_row_id >= 0),
    comment_recovery_full_miss_count INTEGER NOT NULL DEFAULT 0
        CHECK(comment_recovery_full_miss_count >= 0),
    comment_recovery_parked_at TEXT,
    comment_recovery_last_terminal_at TEXT,
    comment_recovery_last_terminal_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_sa_articles_ticker ON sa_articles(ticker);
CREATE INDEX IF NOT EXISTS idx_sa_articles_published ON sa_articles(published_date DESC);
CREATE INDEX IF NOT EXISTS idx_sa_articles_type ON sa_articles(article_type);
CREATE INDEX IF NOT EXISTS idx_sa_articles_list_ticker ON sa_articles(list_ticker);
CREATE INDEX IF NOT EXISTS idx_sa_articles_detail_ticker ON sa_articles(detail_ticker);

CREATE TABLE IF NOT EXISTS sa_pick_article_links (
    link_id             INTEGER PRIMARY KEY,
    lineage_id          INTEGER NOT NULL
                        REFERENCES sa_pick_lineages(lineage_id) ON DELETE RESTRICT,
    article_id          TEXT NOT NULL
                        REFERENCES sa_articles(article_id) ON DELETE RESTRICT,
    role                TEXT NOT NULL CHECK(role IN ('entry', 'exit', 'update')),
    event_anchor_date   TEXT,
    link_source         TEXT NOT NULL CHECK(link_source IN ('auto', 'user')),
    evidence_codes      TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(evidence_codes)),
    supersedes_link_id  INTEGER
                        REFERENCES sa_pick_article_links(link_id) ON DELETE RESTRICT,
    linked_at           TEXT NOT NULL,
    revoked_at          TEXT,
    CHECK(role = 'update' OR event_anchor_date IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sa_pick_links_active_entry
    ON sa_pick_article_links(lineage_id)
    WHERE role = 'entry' AND revoked_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_sa_pick_links_active_exit
    ON sa_pick_article_links(lineage_id, event_anchor_date)
    WHERE role = 'exit' AND revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_sa_pick_links_event
    ON sa_pick_article_links(lineage_id, role, event_anchor_date, revoked_at);

CREATE TABLE IF NOT EXISTS sa_pick_article_decisions (
    decision_id        INTEGER PRIMARY KEY,
    lineage_id         INTEGER NOT NULL
                       REFERENCES sa_pick_lineages(lineage_id) ON DELETE RESTRICT,
    article_id         TEXT NOT NULL
                       REFERENCES sa_articles(article_id) ON DELETE RESTRICT,
    role               TEXT NOT NULL CHECK(role IN ('entry', 'exit')),
    event_anchor_date  TEXT NOT NULL,
    decision           TEXT NOT NULL CHECK(decision = 'rejected'),
    reason_code        TEXT NOT NULL,
    decided_at         TEXT NOT NULL,
    UNIQUE(lineage_id, role, event_anchor_date, article_id)
);
CREATE INDEX IF NOT EXISTS idx_sa_pick_decisions_event
    ON sa_pick_article_decisions(lineage_id, role, event_anchor_date);

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


_V1_TO_V2_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE sa_pick_lineages (
        lineage_id   INTEGER PRIMARY KEY,
        symbol_key   TEXT NOT NULL
                     CHECK(symbol_key <> '' AND symbol_key = UPPER(TRIM(symbol_key))),
        picked_date  TEXT NOT NULL,
        created_at   TEXT NOT NULL,
        UNIQUE(symbol_key, picked_date)
    )
    """,
    """
    INSERT INTO sa_pick_lineages(symbol_key, picked_date, created_at)
    SELECT UPPER(TRIM(symbol)), picked_date,
           COALESCE(MIN(updated_at), MIN(fetched_at), MIN(last_seen_snapshot),
                    strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now'))
    FROM sa_alpha_picks
    GROUP BY UPPER(TRIM(symbol)), picked_date
    """,
    "DROP INDEX IF EXISTS idx_sa_picks_current_unique",
    "DROP INDEX IF EXISTS idx_sa_picks_closed_unique",
    "DROP INDEX IF EXISTS idx_sa_picks_status",
    "DROP INDEX IF EXISTS idx_sa_picks_symbol",
    "DROP INDEX IF EXISTS idx_sa_picks_snapshot",
    "DROP INDEX IF EXISTS idx_sa_picks_stale",
    "DROP INDEX IF EXISTS idx_sa_picks_canonical_article",
    "ALTER TABLE sa_alpha_picks RENAME TO sa_alpha_picks_v1",
    """
    CREATE TABLE sa_alpha_picks (
        id                   INTEGER PRIMARY KEY,
        lineage_id           INTEGER NOT NULL
                             REFERENCES sa_pick_lineages(lineage_id) ON DELETE RESTRICT,
        symbol               TEXT NOT NULL,
        company              TEXT NOT NULL,
        picked_date          TEXT NOT NULL,
        closed_date          TEXT,
        portfolio_status     TEXT NOT NULL DEFAULT 'current',
        is_stale             INTEGER NOT NULL DEFAULT 0,
        return_pct           REAL,
        sector               TEXT,
        sa_rating            TEXT,
        holding_pct          REAL,
        detail_report        TEXT,
        detail_fetched_at    TEXT,
        raw_data             TEXT,
        last_seen_snapshot   TEXT,
        canonical_article_id TEXT,
        fetched_at           TEXT,
        updated_at           TEXT
    )
    """,
    """
    INSERT INTO sa_alpha_picks(
        id, lineage_id, symbol, company, picked_date, closed_date,
        portfolio_status, is_stale, return_pct, sector, sa_rating,
        holding_pct, detail_report, detail_fetched_at, raw_data,
        last_seen_snapshot, canonical_article_id, fetched_at, updated_at
    )
    SELECT p.id, l.lineage_id, p.symbol, p.company, p.picked_date, p.closed_date,
           p.portfolio_status, p.is_stale, p.return_pct, p.sector, p.sa_rating,
           p.holding_pct, p.detail_report, p.detail_fetched_at, p.raw_data,
           p.last_seen_snapshot, p.canonical_article_id, p.fetched_at, p.updated_at
    FROM sa_alpha_picks_v1 p
    JOIN sa_pick_lineages l
      ON l.symbol_key = UPPER(TRIM(p.symbol))
     AND l.picked_date = p.picked_date
    """,
    "DROP TABLE sa_alpha_picks_v1",
    """
    CREATE UNIQUE INDEX idx_sa_picks_current_unique
        ON sa_alpha_picks(symbol, picked_date, portfolio_status)
        WHERE portfolio_status = 'current'
    """,
    """
    CREATE UNIQUE INDEX idx_sa_picks_closed_unique
        ON sa_alpha_picks(symbol, picked_date, portfolio_status, closed_date)
        WHERE portfolio_status = 'closed'
    """,
    "CREATE INDEX idx_sa_picks_status ON sa_alpha_picks(portfolio_status)",
    "CREATE INDEX idx_sa_picks_symbol ON sa_alpha_picks(symbol)",
    "CREATE INDEX idx_sa_picks_snapshot ON sa_alpha_picks(last_seen_snapshot)",
    "CREATE INDEX idx_sa_picks_stale ON sa_alpha_picks(is_stale) WHERE is_stale = 1",
    "CREATE INDEX idx_sa_picks_canonical_article ON sa_alpha_picks(canonical_article_id)",
    """
    CREATE INDEX idx_sa_picks_lineage_status
        ON sa_alpha_picks(lineage_id, portfolio_status, is_stale)
    """,
    "ALTER TABLE sa_articles ADD COLUMN list_ticker TEXT",
    "ALTER TABLE sa_articles ADD COLUMN list_ticker_observed_at TEXT",
    "ALTER TABLE sa_articles ADD COLUMN detail_ticker TEXT",
    "ALTER TABLE sa_articles ADD COLUMN detail_ticker_observed_at TEXT",
    "ALTER TABLE sa_articles ADD COLUMN comments_count_observed_at TEXT",
    """
    ALTER TABLE sa_articles ADD COLUMN provider_comments_count_at_last_scan INTEGER
        CHECK(provider_comments_count_at_last_scan IS NULL
              OR provider_comments_count_at_last_scan >= 0)
    """,
    """
    ALTER TABLE sa_articles ADD COLUMN comment_recovery_state TEXT NOT NULL
        DEFAULT 'repaired' CHECK(comment_recovery_state IN
            ('repaired', 'pending', 'unreachable_terminal'))
    """,
    "ALTER TABLE sa_articles ADD COLUMN comment_recovery_started_at TEXT",
    """
    ALTER TABLE sa_articles ADD COLUMN comment_recovery_baseline_max_row_id INTEGER
        CHECK(comment_recovery_baseline_max_row_id IS NULL
              OR comment_recovery_baseline_max_row_id >= 0)
    """,
    """
    ALTER TABLE sa_articles ADD COLUMN comment_recovery_full_miss_count INTEGER
        NOT NULL DEFAULT 0 CHECK(comment_recovery_full_miss_count >= 0)
    """,
    "ALTER TABLE sa_articles ADD COLUMN comment_recovery_parked_at TEXT",
    "ALTER TABLE sa_articles ADD COLUMN comment_recovery_last_terminal_at TEXT",
    "ALTER TABLE sa_articles ADD COLUMN comment_recovery_last_terminal_reason TEXT",
    """
    UPDATE sa_articles
    SET provider_comments_count_at_last_scan = COALESCE(comments_count, 0)
    WHERE comments_fetched_at IS NOT NULL
    """,
    "CREATE INDEX idx_sa_articles_list_ticker ON sa_articles(list_ticker)",
    "CREATE INDEX idx_sa_articles_detail_ticker ON sa_articles(detail_ticker)",
    """
    CREATE TABLE sa_pick_article_links (
        link_id             INTEGER PRIMARY KEY,
        lineage_id          INTEGER NOT NULL
                            REFERENCES sa_pick_lineages(lineage_id) ON DELETE RESTRICT,
        article_id          TEXT NOT NULL
                            REFERENCES sa_articles(article_id) ON DELETE RESTRICT,
        role                TEXT NOT NULL CHECK(role IN ('entry', 'exit', 'update')),
        event_anchor_date   TEXT,
        link_source         TEXT NOT NULL CHECK(link_source IN ('auto', 'user')),
        evidence_codes      TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(evidence_codes)),
        supersedes_link_id  INTEGER
                            REFERENCES sa_pick_article_links(link_id) ON DELETE RESTRICT,
        linked_at           TEXT NOT NULL,
        revoked_at          TEXT,
        CHECK(role = 'update' OR event_anchor_date IS NOT NULL)
    )
    """,
    """
    CREATE UNIQUE INDEX idx_sa_pick_links_active_entry
        ON sa_pick_article_links(lineage_id)
        WHERE role = 'entry' AND revoked_at IS NULL
    """,
    """
    CREATE UNIQUE INDEX idx_sa_pick_links_active_exit
        ON sa_pick_article_links(lineage_id, event_anchor_date)
        WHERE role = 'exit' AND revoked_at IS NULL
    """,
    """
    CREATE INDEX idx_sa_pick_links_event
        ON sa_pick_article_links(lineage_id, role, event_anchor_date, revoked_at)
    """,
    """
    CREATE TABLE sa_pick_article_decisions (
        decision_id        INTEGER PRIMARY KEY,
        lineage_id         INTEGER NOT NULL
                           REFERENCES sa_pick_lineages(lineage_id) ON DELETE RESTRICT,
        article_id         TEXT NOT NULL
                           REFERENCES sa_articles(article_id) ON DELETE RESTRICT,
        role               TEXT NOT NULL CHECK(role IN ('entry', 'exit')),
        event_anchor_date  TEXT NOT NULL,
        decision           TEXT NOT NULL CHECK(decision = 'rejected'),
        reason_code        TEXT NOT NULL,
        decided_at         TEXT NOT NULL,
        UNIQUE(lineage_id, role, event_anchor_date, article_id)
    )
    """,
    """
    CREATE INDEX idx_sa_pick_decisions_event
        ON sa_pick_article_decisions(lineage_id, role, event_anchor_date)
    """,
)


def connect(db_path: Optional[str] = None, *, read_only: bool = False) -> sqlite3.Connection:
    """Open sa_capture.db with the per-connection discipline EVERY caller needs
    (fresh-per-message host processes get no help from in-process state):
    WAL + busy_timeout + foreign_keys=ON, schema ensured (rw only), Row factory.
    """
    path = db_path or resolve_sa_db_path()
    if read_only:
        if not Path(path).exists():
            # Fresh profile: the capture DB does not exist yet. Serve an empty
            # in-memory schema so readers get honest-empty rows without creating
            # the file or falling back to the dropped PG sa_* tables.
            conn = sqlite3.connect(":memory:", timeout=10.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 10000")
            ensure_schema(conn)
            return conn
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


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Serialize and atomically migrate one existing v1 capture database."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if version == SCHEMA_VERSION:
            conn.commit()
            return
        if version != 1:
            raise RuntimeError(f"unsupported sa_capture schema version: {version}")
        has_v2_table = conn.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='sa_pick_lineages'"
        ).fetchone() is not None
        article_columns = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(sa_articles)")
        }
        continuity_columns = {
            "comments_count_observed_at",
            "provider_comments_count_at_last_scan",
            "comment_recovery_state",
            "comment_recovery_started_at",
            "comment_recovery_baseline_max_row_id",
            "comment_recovery_full_miss_count",
            "comment_recovery_parked_at",
            "comment_recovery_last_terminal_at",
            "comment_recovery_last_terminal_reason",
        }
        if has_v2_table or article_columns & continuity_columns:
            raise RuntimeError(
                "sa_capture schema marker mismatch: v1 marker with v2 artifacts"
            )

        expected_pick_count = int(
            conn.execute("SELECT COUNT(*) FROM sa_alpha_picks").fetchone()[0]
        )
        for statement in _V1_TO_V2_STATEMENTS:
            conn.execute(statement)

        actual_pick_count = int(
            conn.execute("SELECT COUNT(*) FROM sa_alpha_picks").fetchone()[0]
        )
        null_lineage_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM sa_alpha_picks WHERE lineage_id IS NULL"
            ).fetchone()[0]
        )
        if actual_pick_count != expected_pick_count or null_lineage_count:
            raise RuntimeError(
                "sa_capture v1-to-v2 migration did not preserve every pick lineage"
            )

        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, now_ts()),
        )
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Ensure a fresh v2 schema or migrate v1 under the correct lock boundary.

    Current databases take one cheap ``PRAGMA user_version`` fast path. Fresh
    version-0 creation retains the established idempotent ``executescript``
    guarantee: its implicit commit means concurrent creators may interleave, so
    every statement in ``_SCHEMA`` remains idempotent. The non-idempotent v1-to-v2
    rebuild is different: every statement, marker update, and preservation check
    runs inside one ``BEGIN IMMEDIATE`` transaction with a version re-check, so
    two native-host processes cannot interleave the migration.
    """
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if version == SCHEMA_VERSION:
        return
    if version == 1:
        _migrate_v1_to_v2(conn)
        return
    if version != 0:
        raise RuntimeError(f"unsupported sa_capture schema version: {version}")

    conn.execute("BEGIN IMMEDIATE")
    try:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if version == SCHEMA_VERSION:
            conn.commit()
            return
        if version == 1:
            conn.commit()
            _migrate_v1_to_v2(conn)
            return
        if version != 0:
            raise RuntimeError(f"unsupported sa_capture schema version: {version}")
        conn.executescript(_SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, now_ts()),
        )
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise


# ---------------------------------------------------------------------------
# Comment-signal extraction API (the SQLite write CHOKE-POINT, slice follow-up #1)
#
# All sa_comment_signals writes for sa_capture.db go through upsert_comment_signal
# so rule re-runs, the scheduler/job trigger, and tests share ONE path (instead of
# SQL scattered through comment_signal_backfill). The PG equivalents stay in
# comment_signal_backfill (raw psycopg2) for non-local mode; this is the local twin.
# ---------------------------------------------------------------------------


def count_pending_signals(conn: sqlite3.Connection, rule_set_version: str) -> int:
    """Comments with NO signal at THIS rule_set_version (re-extractable on a bump)."""
    return int(conn.execute(
        "SELECT COUNT(*) FROM sa_article_comments c WHERE NOT EXISTS ("
        " SELECT 1 FROM sa_comment_signals s"
        " WHERE s.comment_row_id = c.id AND s.rule_set_version = ?)",
        (rule_set_version,)).fetchone()[0])


def fetch_pending_comments(conn: sqlite3.Connection, *, last_id: int, limit: int,
                           rule_set_version: str) -> list:
    """Keyset page (id > last_id) of comments pending at this rule_set_version.
    Returns rows of (id, article_id, comment_id, comment_text, upvotes)."""
    return conn.execute(
        "SELECT c.id, c.article_id, c.comment_id, c.comment_text, c.upvotes"
        " FROM sa_article_comments c WHERE c.id > ? AND NOT EXISTS ("
        " SELECT 1 FROM sa_comment_signals s"
        " WHERE s.comment_row_id = c.id AND s.rule_set_version = ?)"
        " ORDER BY c.id LIMIT ?",
        (last_id, rule_set_version, limit)).fetchall()


def upsert_comment_signal(conn: sqlite3.Connection, *, row_id: int, article_id: str,
                          comment_id: str, signals) -> None:
    """Write one comment's signal: scalar row + BOTH mention junctions.

    ⚠️ Runs inside the CALLER's transaction (caller wraps a batch in ``with conn:``)
    so the scalar upsert and the junction delete/reinsert commit together — a crash
    can never leave a half-updated comment (scalar without its mentions). Does NOT
    commit. ``keyword_buckets`` → JSON TEXT; TEXT[]→junction (ON CONFLICT DO UPDATE
    on the scalar does NOT cascade, so mentions are explicitly delete-then-reinsert).
    """
    conn.execute(
        "INSERT INTO sa_comment_signals"
        " (comment_row_id, article_id, comment_id, keyword_buckets, high_value_score,"
        "  needs_verification, rule_set_version, extracted_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(comment_row_id) DO UPDATE SET"
        "  article_id=excluded.article_id, comment_id=excluded.comment_id,"
        "  keyword_buckets=excluded.keyword_buckets, high_value_score=excluded.high_value_score,"
        "  needs_verification=excluded.needs_verification, rule_set_version=excluded.rule_set_version,"
        "  extracted_at=excluded.extracted_at",
        (row_id, article_id, comment_id, json.dumps(signals.keyword_buckets),
         float(signals.high_value_score), 1 if signals.needs_verification else 0,
         signals.rule_set_version, now_ts()))
    conn.execute("DELETE FROM sa_signal_ticker_mentions WHERE comment_row_id = ?", (row_id,))
    if signals.ticker_mentions:
        conn.executemany(
            "INSERT OR IGNORE INTO sa_signal_ticker_mentions (comment_row_id, ticker) VALUES (?, ?)",
            [(row_id, t) for t in signals.ticker_mentions])
    conn.execute("DELETE FROM sa_signal_candidate_mentions WHERE comment_row_id = ?", (row_id,))
    if signals.candidate_mentions:
        conn.executemany(
            "INSERT OR IGNORE INTO sa_signal_candidate_mentions (comment_row_id, ticker) VALUES (?, ?)",
            [(row_id, t) for t in signals.candidate_mentions])
