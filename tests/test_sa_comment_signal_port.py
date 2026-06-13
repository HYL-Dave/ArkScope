"""Layer A of follow-up #1: SA comment-signal extraction ported to sa_capture.db.

Verifies the SQLite twin of run_backfill (routed when backend._sa_db is set):
writes the scalar row + BOTH mention junctions through the sa_capture_store
choke-point, never touches PG, is idempotent, respects rule_set_version, and
re-extraction replaces a comment's mention set (delete/reinsert, no stale rows).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src import sa_capture_store as store
from src.sa import comment_signal_backfill as bf


def _seed(db_path) -> None:
    conn = store.connect(str(db_path))  # creates schema
    try:
        conn.execute(
            "INSERT INTO sa_articles (id, article_id, url, title) "
            "VALUES (1, 'A1', 'http://x/1', 'T1')"
        )
        conn.executemany(
            "INSERT INTO sa_article_comments "
            "(id, article_id, comment_id, comment_text, upvotes) VALUES (?, ?, ?, ?, ?)",
            [
                (1, "A1", "c1", "Very bullish on NVDA, earnings beat consensus estimate", 12),
                (2, "A1", "c2", "Looking at XYZ for a swing trade", 1),
                (3, "A1", "c3", "", 0),
                (4, "A1", "c4", "AMD downgrade, hold rating from analyst", 5),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _dal(db_path, tickers=("NVDA", "AMD")):
    dal = MagicMock()
    backend = MagicMock()
    backend._sa_db = str(db_path)
    # Proof of no split-brain: the SA-local path must NEVER open a PG connection.
    backend._get_conn.side_effect = AssertionError("PG must not be touched in SA-local mode")
    dal._backend = backend
    wl = MagicMock()
    wl.tickers = list(tickers)
    dal.get_watchlist.return_value = wl
    return dal, backend


def _ro(db_path):
    return store.connect(str(db_path), read_only=True)


def test_writes_signals_and_junctions_to_sqlite(tmp_path):
    db = tmp_path / "sa.db"
    _seed(db)
    dal, backend = _dal(db)

    res = bf.run_backfill(dal, batch_size=2)  # batch_size<comments → exercises >1 batch

    assert res["extracted_count"] == 4
    assert res["total_pending"] == 4
    assert res["batch_count"] >= 2
    assert res["sample_high_score"] > 0
    backend._get_conn.assert_not_called()  # NEVER touched PG

    conn = _ro(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM sa_comment_signals").fetchone()[0] == 4
        tickers = {tuple(r) for r in conn.execute(
            "SELECT comment_row_id, ticker FROM sa_signal_ticker_mentions").fetchall()}
        cands = {tuple(r) for r in conn.execute(
            "SELECT comment_row_id, ticker FROM sa_signal_candidate_mentions").fetchall()}
        assert (1, "NVDA") in tickers and (4, "AMD") in tickers
        assert (2, "XYZ") in cands
        score, buckets = conn.execute(
            "SELECT high_value_score, keyword_buckets FROM sa_comment_signals "
            "WHERE comment_row_id = 1").fetchone()
        assert score > 0 and "earnings" in buckets  # JSON TEXT
        # integrity holds with FK on
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_idempotent_rerun_no_growth(tmp_path):
    db = tmp_path / "sa.db"
    _seed(db)
    dal, _ = _dal(db)

    bf.run_backfill(dal)
    res2 = bf.run_backfill(dal)  # same rule_set_version → nothing pending

    assert res2["extracted_count"] == 0
    assert res2["total_pending"] == 0
    conn = _ro(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM sa_comment_signals").fetchone()[0] == 4
        assert conn.execute("SELECT COUNT(*) FROM sa_signal_ticker_mentions").fetchone()[0] == 2
    finally:
        conn.close()


def test_rule_set_version_gates_pending(tmp_path):
    db = tmp_path / "sa.db"
    _seed(db)
    dal, _ = _dal(db)

    bf.run_backfill(dal, rule_set_version="v1.1")
    # a NEW rule set makes every comment pending again (no row at v2.0)
    res = bf.run_backfill(dal, rule_set_version="v2.0")

    assert res["extracted_count"] == 4
    conn = _ro(db)
    try:
        versions = {r[0] for r in conn.execute(
            "SELECT DISTINCT rule_set_version FROM sa_comment_signals")}
        assert versions == {"v2.0"}  # ON CONFLICT updated the rows in place
        assert conn.execute("SELECT COUNT(*) FROM sa_comment_signals").fetchone()[0] == 4
    finally:
        conn.close()


def test_reextraction_replaces_mention_set(tmp_path):
    db = tmp_path / "sa.db"
    _seed(db)

    # first pass: AMD is in the universe → c4 AMD is a ticker_mention
    bf.run_backfill(_dal(db, tickers=("NVDA", "AMD"))[0], rule_set_version="v1.1")
    conn = _ro(db)
    try:
        assert (4, "AMD") in {tuple(r) for r in conn.execute(
            "SELECT comment_row_id, ticker FROM sa_signal_ticker_mentions").fetchall()}
    finally:
        conn.close()

    # re-extract at a new version with AMD OUT of the universe → must MOVE to candidate,
    # and the stale ticker-junction row must be gone (delete/reinsert, same txn).
    bf.run_backfill(_dal(db, tickers=("NVDA",))[0], rule_set_version="v2.0")
    conn = _ro(db)
    try:
        tickers = {tuple(r) for r in conn.execute(
            "SELECT comment_row_id, ticker FROM sa_signal_ticker_mentions").fetchall()}
        cands = {tuple(r) for r in conn.execute(
            "SELECT comment_row_id, ticker FROM sa_signal_candidate_mentions").fetchall()}
        assert (4, "AMD") not in tickers   # stale ticker row removed
        assert (4, "AMD") in cands         # now a candidate
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_guard_lifted_runs_in_sa_local_mode(tmp_path):
    """The locked-3d RuntimeError guard is gone: SA-local run returns a result."""
    db = tmp_path / "sa.db"
    _seed(db)
    dal, _ = _dal(db)
    res = bf.run_backfill(dal)  # must NOT raise
    assert isinstance(res, dict) and res["rule_set_version"] == bf.RULE_SET_VERSION


def test_max_extracted_caps_run(tmp_path):
    db = tmp_path / "sa.db"
    _seed(db)
    dal, _ = _dal(db)
    res = bf.run_backfill(dal, batch_size=10, max_extracted=2)
    assert res["extracted_count"] == 2
    conn = _ro(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM sa_comment_signals").fetchone()[0] == 2
    finally:
        conn.close()


def test_max_extracted_spans_batch_boundary(tmp_path):
    """Cap that fires in batch 2 — proves keyset last_id carries across a COMMITTED
    batch boundary (batch 1's rows stay durable; the partial batch 2 commits too)."""
    db = tmp_path / "sa.db"
    _seed(db)
    dal, _ = _dal(db)
    res = bf.run_backfill(dal, batch_size=2, max_extracted=3)  # ids 1,2 | 3,(4)
    assert res["extracted_count"] == 3
    assert res["batch_count"] == 2
    conn = _ro(db)
    try:
        ids = {r[0] for r in conn.execute("SELECT comment_row_id FROM sa_comment_signals")}
        assert ids == {1, 2, 3}  # batch1 committed + batch2's first row; id 4 not reached
    finally:
        conn.close()


def test_mid_batch_failure_rolls_back_whole_batch(monkeypatch, tmp_path):
    """Refinement #3 crash path: a failure on the 2nd row of a batch rolls back the
    ENTIRE batch (incl. the 1st row already written) — never a half-updated comment.
    A clean rerun then recovers."""
    db = tmp_path / "sa.db"
    _seed(db)
    dal, _ = _dal(db)

    real = store.upsert_comment_signal
    calls = {"n": 0}

    def flaky(conn, **kw):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom on 2nd row")
        return real(conn, **kw)

    monkeypatch.setattr(store, "upsert_comment_signal", flaky)
    with pytest.raises(RuntimeError, match="boom"):
        bf.run_backfill(dal, batch_size=10)  # one batch of all 4 → fails on row 2

    conn = _ro(db)
    try:
        # whole batch rolled back — even the 1st row's write is gone
        assert conn.execute("SELECT COUNT(*) FROM sa_comment_signals").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM sa_signal_ticker_mentions").fetchone()[0] == 0
    finally:
        conn.close()

    monkeypatch.setattr(store, "upsert_comment_signal", real)  # recover
    res = bf.run_backfill(dal, batch_size=10)
    assert res["extracted_count"] == 4
    conn = _ro(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM sa_comment_signals").fetchone()[0] == 4
    finally:
        conn.close()


def test_empty_text_comment_gets_zero_signal_and_resolves_pending(tmp_path):
    """The blank comment (row 3) must still get a signal row (score 0, no mentions) —
    this is what makes the rerun idempotent (otherwise it would be perpetually pending)."""
    db = tmp_path / "sa.db"
    _seed(db)
    dal, _ = _dal(db)
    bf.run_backfill(dal)
    conn = _ro(db)
    try:
        row = conn.execute(
            "SELECT high_value_score FROM sa_comment_signals WHERE comment_row_id = 3").fetchone()
        assert row is not None and row[0] == 0.0
        assert conn.execute(
            "SELECT COUNT(*) FROM sa_signal_ticker_mentions WHERE comment_row_id = 3").fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM sa_signal_candidate_mentions WHERE comment_row_id = 3").fetchone()[0] == 0
        assert store.count_pending_signals(conn, bf.RULE_SET_VERSION) == 0  # nothing left pending
    finally:
        conn.close()
