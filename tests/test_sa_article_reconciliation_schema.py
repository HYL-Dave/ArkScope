from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import src.sa_capture_store as scs


RCL_ROWS = [
    (807, "RCL", "2024-03-15", None, "current", 1, "legacy-entry"),
    (116511, "RCL", "2024-03-15", "2025-10-29", "closed", 0, None),
    (122696, "RCL", "2024-03-15", "2026-06-02", "closed", 0, None),
    (130000, "RCL", "2026-07-01", None, "current", 0, None),
]


_V1_SCHEMA = """
CREATE TABLE sa_alpha_picks (
    id                   INTEGER PRIMARY KEY,
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
);
CREATE UNIQUE INDEX idx_sa_picks_current_unique
    ON sa_alpha_picks(symbol, picked_date, portfolio_status)
    WHERE portfolio_status = 'current';
CREATE UNIQUE INDEX idx_sa_picks_closed_unique
    ON sa_alpha_picks(symbol, picked_date, portfolio_status, closed_date)
    WHERE portfolio_status = 'closed';
CREATE INDEX idx_sa_picks_status ON sa_alpha_picks(portfolio_status);
CREATE INDEX idx_sa_picks_symbol ON sa_alpha_picks(symbol);
CREATE INDEX idx_sa_picks_snapshot ON sa_alpha_picks(last_seen_snapshot);
CREATE INDEX idx_sa_picks_stale ON sa_alpha_picks(is_stale) WHERE is_stale = 1;
CREATE INDEX idx_sa_picks_canonical_article ON sa_alpha_picks(canonical_article_id);

CREATE TABLE sa_articles (
    id                  INTEGER PRIMARY KEY,
    article_id          TEXT NOT NULL UNIQUE,
    url                 TEXT NOT NULL,
    title               TEXT NOT NULL,
    ticker              TEXT,
    author              TEXT,
    published_date      TEXT,
    article_type        TEXT,
    body_markdown       TEXT,
    comments_count      INTEGER DEFAULT 0,
    detail_fetched_at   TEXT,
    comments_fetched_at TEXT,
    raw_data            TEXT,
    fetched_at          TEXT,
    updated_at          TEXT
);
CREATE INDEX idx_sa_articles_ticker ON sa_articles(ticker);
CREATE INDEX idx_sa_articles_published ON sa_articles(published_date DESC);
CREATE INDEX idx_sa_articles_type ON sa_articles(article_type);

CREATE TABLE schema_migrations (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
INSERT INTO schema_migrations(version, applied_at)
VALUES (1, '2026-06-13T00:00:00+00:00');
PRAGMA user_version = 1;
"""


def _create_v1(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_V1_SCHEMA)
        conn.executemany(
            "INSERT INTO sa_alpha_picks "
            "(id, symbol, company, picked_date, closed_date, portfolio_status, "
            "is_stale, canonical_article_id) VALUES (?, ?, 'Royal Caribbean', ?, ?, ?, ?, ?)",
            RCL_ROWS,
        )
        conn.execute(
            "INSERT INTO sa_articles(article_id, url, title, ticker, published_date) "
            "VALUES ('legacy-entry', 'https://sa/legacy-entry', 'Legacy entry', 'RCL', '2024-03-15')"
        )
        conn.commit()
    finally:
        conn.close()


def _lineage_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT p.id, p.closed_date, l.lineage_id, l.symbol_key, l.picked_date "
        "FROM sa_alpha_picks p JOIN sa_pick_lineages l USING(lineage_id) "
        "WHERE p.id IN (807, 116511, 122696) ORDER BY p.id"
    ).fetchall()


def _schema_snapshot(conn: sqlite3.Connection) -> tuple:
    master = tuple(
        tuple(row)
        for row in conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
    )
    tables = {row[1] for row in master if row[0] == "table"}
    authority = []
    for table in (
        "schema_migrations",
        "sa_pick_lineages",
        "sa_alpha_picks",
        "sa_articles",
        "sa_pick_article_links",
        "sa_pick_article_decisions",
    ):
        if table in tables:
            rows = tuple(tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY 1"))
            authority.append((table, rows))
    return (
        int(conn.execute("PRAGMA user_version").fetchone()[0]),
        master,
        tuple(authority),
    )


def _insert_lineage_and_article(conn: sqlite3.Connection) -> tuple[int, str]:
    conn.execute(
        "INSERT INTO sa_pick_lineages(symbol_key, picked_date, created_at) VALUES ('BTSG', '2026-07-15', ?)",
        (scs.now_ts(),),
    )
    lineage_id = int(conn.execute("SELECT lineage_id FROM sa_pick_lineages").fetchone()[0])
    article_id = "6316639"
    conn.execute(
        "INSERT INTO sa_articles(article_id, url, title) VALUES (?, ?, ?)",
        (article_id, "https://sa/6316639", "BTSG entry"),
    )
    return lineage_id, article_id


def test_fresh_v2_schema_has_lineage_link_decision_and_provider_evidence_contract(tmp_path):
    conn = scs.connect(str(tmp_path / "fresh.db"))
    try:
        assert scs.SCHEMA_VERSION == 2
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"sa_pick_lineages", "sa_pick_article_links", "sa_pick_article_decisions"} <= tables

        pick_columns = {row[1]: row for row in conn.execute("PRAGMA table_info(sa_alpha_picks)")}
        assert pick_columns["lineage_id"][3] == 1
        article_columns = {row[1] for row in conn.execute("PRAGMA table_info(sa_articles)")}
        assert {
            "list_ticker",
            "list_ticker_observed_at",
            "detail_ticker",
            "detail_ticker_observed_at",
        } <= article_columns

        indexes = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
            )
        }
        assert "WHERE role = 'entry' AND revoked_at IS NULL" in indexes["idx_sa_pick_links_active_entry"]
        assert "WHERE role = 'exit' AND revoked_at IS NULL" in indexes["idx_sa_pick_links_active_exit"]
        assert {
            "idx_sa_picks_lineage_status",
            "idx_sa_articles_list_ticker",
            "idx_sa_articles_detail_ticker",
            "idx_sa_pick_links_event",
            "idx_sa_pick_decisions_event",
        } <= indexes.keys()

        for table in ("sa_alpha_picks", "sa_pick_article_links", "sa_pick_article_decisions"):
            fks = list(conn.execute(f"PRAGMA foreign_key_list({table})"))
            assert fks
            assert all(row[6].upper() != "CASCADE" for row in fks)
        link_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='sa_pick_article_links'"
        ).fetchone()[0]
        decision_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='sa_pick_article_decisions'"
        ).fetchone()[0]
        assert "json_valid(evidence_codes)" in link_sql
        assert "'entry', 'exit', 'update'" in link_sql
        assert "decision = 'rejected'" in decision_sql
    finally:
        conn.close()


def test_v1_migration_backfills_one_lineage_for_current_and_closed_rows(tmp_path):
    path = tmp_path / "v1.db"
    _create_v1(path)
    conn = scs.connect(str(path))
    try:
        rows = _lineage_rows(conn)
        assert {row["lineage_id"] for row in rows} == {rows[0]["lineage_id"]}
        assert {row["closed_date"] for row in rows} == {None, "2025-10-29", "2026-06-02"}
        assert all(row["symbol_key"] == "RCL" for row in rows)
        assert all(row["picked_date"] == "2024-03-15" for row in rows)
    finally:
        conn.close()


def test_v1_migration_preserves_distinct_closed_events(tmp_path):
    path = tmp_path / "v1.db"
    _create_v1(path)
    conn = scs.connect(str(path))
    try:
        closed = conn.execute(
            "SELECT id, closed_date FROM sa_alpha_picks "
            "WHERE symbol='RCL' AND portfolio_status='closed' ORDER BY id"
        ).fetchall()
        assert [tuple(row) for row in closed] == [
            (116511, "2025-10-29"),
            (122696, "2026-06-02"),
        ]
    finally:
        conn.close()


def test_v1_migration_creates_distinct_lineage_for_changed_picked_date(tmp_path):
    path = tmp_path / "v1.db"
    _create_v1(path)
    conn = scs.connect(str(path))
    try:
        lineages = conn.execute(
            "SELECT symbol_key, picked_date FROM sa_pick_lineages ORDER BY picked_date"
        ).fetchall()
        assert [tuple(row) for row in lineages] == [
            ("RCL", "2024-03-15"),
            ("RCL", "2026-07-01"),
        ]
        assert conn.execute(
            "SELECT COUNT(DISTINCT lineage_id) FROM sa_alpha_picks WHERE symbol='RCL'"
        ).fetchone()[0] == 2
    finally:
        conn.close()


def test_v1_migration_does_not_grandfather_legacy_canonical_values(tmp_path):
    path = tmp_path / "v1.db"
    _create_v1(path)
    conn = scs.connect(str(path))
    try:
        assert conn.execute(
            "SELECT canonical_article_id FROM sa_alpha_picks WHERE id=807"
        ).fetchone()[0] == "legacy-entry"
        assert conn.execute("SELECT COUNT(*) FROM sa_pick_article_links").fetchone()[0] == 0
    finally:
        conn.close()


def test_v1_migration_seeds_comment_checkpoint_without_recovery_flag(tmp_path):
    path = tmp_path / "comments-v1.db"
    _create_v1(path)
    raw = sqlite3.connect(path)
    raw.execute(
        "UPDATE sa_articles SET comments_count=41, comments_fetched_at=? "
        "WHERE article_id='legacy-entry'",
        ("2026-07-18T00:00:00+00:00",),
    )
    raw.execute(
        "INSERT INTO sa_articles(article_id,url,title,comments_count) "
        "VALUES ('never-scanned','https://sa/never','Never scanned article',18)"
    )
    raw.commit()
    raw.close()

    conn = scs.connect(str(path))
    rows = {
        row["article_id"]: dict(row)
        for row in conn.execute(
            "SELECT article_id, comments_count_observed_at, "
            "provider_comments_count_at_last_scan, comment_recovery_state, "
            "comment_recovery_started_at, "
            "comment_recovery_baseline_max_row_id, "
            "comment_recovery_full_miss_count, comment_recovery_parked_at, "
            "comment_recovery_last_terminal_at, "
            "comment_recovery_last_terminal_reason FROM sa_articles"
        )
    }
    assert rows["legacy-entry"] == {
        "article_id": "legacy-entry",
        "comments_count_observed_at": None,
        "provider_comments_count_at_last_scan": 41,
        "comment_recovery_state": "repaired",
        "comment_recovery_started_at": None,
        "comment_recovery_baseline_max_row_id": None,
        "comment_recovery_full_miss_count": 0,
        "comment_recovery_parked_at": None,
        "comment_recovery_last_terminal_at": None,
        "comment_recovery_last_terminal_reason": None,
    }
    assert rows["never-scanned"] == {
        "article_id": "never-scanned",
        "comments_count_observed_at": None,
        "provider_comments_count_at_last_scan": None,
        "comment_recovery_state": "repaired",
        "comment_recovery_started_at": None,
        "comment_recovery_baseline_max_row_id": None,
        "comment_recovery_full_miss_count": 0,
        "comment_recovery_parked_at": None,
        "comment_recovery_last_terminal_at": None,
        "comment_recovery_last_terminal_reason": None,
    }
    assert conn.execute("SELECT COUNT(*) FROM sa_articles").fetchone()[0] == 2
    conn.close()


def test_active_entry_and_exit_uniqueness_retains_revoked_history(tmp_path):
    conn = scs.connect(str(tmp_path / "fresh.db"))
    try:
        lineage_id, article_id = _insert_lineage_and_article(conn)
        values = (lineage_id, article_id, "entry", "2026-07-15", "auto", "[]", scs.now_ts())
        conn.execute(
            "INSERT INTO sa_pick_article_links "
            "(lineage_id, article_id, role, event_anchor_date, link_source, evidence_codes, linked_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            values,
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO sa_pick_article_links "
                "(lineage_id, article_id, role, event_anchor_date, link_source, evidence_codes, linked_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                values,
            )
        conn.rollback()
        first_id = int(conn.execute("SELECT link_id FROM sa_pick_article_links").fetchone()[0])
        conn.execute(
            "UPDATE sa_pick_article_links SET revoked_at=? WHERE link_id=?",
            (scs.now_ts(), first_id),
        )
        conn.commit()
        conn.execute(
            "INSERT INTO sa_pick_article_links "
            "(lineage_id, article_id, role, event_anchor_date, link_source, evidence_codes, "
            "supersedes_link_id, linked_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (*values[:6], first_id, values[6]),
        )
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM sa_pick_article_links").fetchone()[0] == 2
    finally:
        conn.close()


def test_link_and_decision_foreign_keys_restrict_history_deletion(tmp_path):
    conn = scs.connect(str(tmp_path / "fresh.db"))
    try:
        lineage_id, article_id = _insert_lineage_and_article(conn)
        conn.execute(
            "INSERT INTO sa_pick_article_links "
            "(lineage_id, article_id, role, event_anchor_date, link_source, linked_at) "
            "VALUES (?, ?, 'entry', '2026-07-15', 'auto', ?)",
            (lineage_id, article_id, scs.now_ts()),
        )
        conn.execute(
            "INSERT INTO sa_pick_article_decisions "
            "(lineage_id, article_id, role, event_anchor_date, decision, reason_code, decided_at) "
            "VALUES (?, ?, 'entry', '2026-07-15', 'rejected', 'operator_rejected', ?)",
            (lineage_id, article_id, scs.now_ts()),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM sa_articles WHERE article_id=?", (article_id,))
        conn.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM sa_pick_lineages WHERE lineage_id=?", (lineage_id,))
        conn.rollback()
    finally:
        conn.close()


def test_future_pick_rows_require_lineage(tmp_path):
    conn = scs.connect(str(tmp_path / "fresh.db"))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO sa_alpha_picks "
                "(lineage_id, symbol, company, picked_date, portfolio_status) "
                "VALUES (NULL, 'BTSG', 'BrightSpring', '2026-07-15', 'current')"
            )
    finally:
        conn.close()


def test_v1_to_v2_migration_is_idempotent(tmp_path):
    migrated_path = tmp_path / "migrated.db"
    _create_v1(migrated_path)
    conn = scs.connect(str(migrated_path))
    expected = _schema_snapshot(conn)
    conn.close()
    for _ in range(2):
        reopened = scs.connect(str(migrated_path))
        assert _schema_snapshot(reopened) == expected
        reopened.close()

    mismatch_path = tmp_path / "marker-mismatch.db"
    valid = scs.connect(str(mismatch_path))
    valid.close()
    raw = sqlite3.connect(mismatch_path)
    raw.execute("PRAGMA user_version = 1")
    raw.commit()
    before = _schema_snapshot(raw)
    raw.close()
    with pytest.raises(RuntimeError, match="marker mismatch"):
        scs.connect(str(mismatch_path))
    after_conn = sqlite3.connect(mismatch_path)
    try:
        assert _schema_snapshot(after_conn) == before
    finally:
        after_conn.close()


def test_v1_to_v2_migration_is_serialized_across_two_real_processes(tmp_path):
    path = tmp_path / "race.db"
    _create_v1(path)
    code = (
        "import sys; sys.path.insert(0, '.'); "
        "import src.sa_capture_store as s; "
        f"c=s.connect({str(path)!r}); print(c.execute('PRAGMA user_version').fetchone()[0]); c.close()"
    )
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", code],
            cwd=str(scs._PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    outputs = [proc.communicate(timeout=60) for proc in procs]
    assert all(proc.returncode == 0 for proc in procs), outputs
    assert all(stdout.strip() == "2" for stdout, _ in outputs)
    conn = sqlite3.connect(path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute(
            "SELECT COUNT(*) FROM sa_alpha_picks WHERE lineage_id IS NULL"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM ("
            "SELECT symbol_key, picked_date FROM sa_pick_lineages "
            "GROUP BY symbol_key, picked_date HAVING COUNT(*) > 1)"
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_v1_to_v2_migration_failure_rolls_back_v1_byte_state(tmp_path, monkeypatch):
    path = tmp_path / "rollback.db"
    _create_v1(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    before = _schema_snapshot(conn)
    statements = scs._V1_TO_V2_STATEMENTS
    monkeypatch.setattr(
        scs,
        "_V1_TO_V2_STATEMENTS",
        (statements[0], "THIS IS NOT VALID SQL", *statements[1:]),
    )
    with pytest.raises(sqlite3.OperationalError):
        scs.ensure_schema(conn)
    assert _schema_snapshot(conn) == before
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='sa_pick_lineages'"
    ).fetchone() is None
    conn.close()
