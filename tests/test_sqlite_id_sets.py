"""Real query regressions for engines without Ubuntu's enlarged bind limit."""

import sqlite3

import pytest

from tests import test_sa_article_reconciliation_backend as sa
from tests import test_security_lifecycle_fact_kernel as lifecycle


@pytest.fixture
def backend(tmp_path):
    return sa.SACaptureBackend(
        sa_db=str(tmp_path / "sa.db"), market_db=str(tmp_path / "market.db"),
    )


@pytest.mark.parametrize("method", [
    "query_sa_market_news_recovery_rows", "query_sa_market_news_body_presence",
])
def test_recovery_large_frozen_target_set(backend, method):
    assert backend.upsert_sa_market_news([
        {"news_id": "1", "url": "https://seekingalpha.com/news/1", "title": "fixture"},
    ]) == 1
    result = getattr(backend, method)([str(value) for value in range(33000)])
    if isinstance(result, dict):
        assert result == {"1": False}
    else:
        assert [row["news_id"] for row in result] == ["1"]


def test_lineage_filter_large_input(backend):
    sa._refresh(backend, "current", [sa._pick()])
    conn = sa._conn(backend)
    try:
        events = sa.reconciliation_store.list_events(conn, lineage_ids=range(1, 33001))
        assert len(events) == 1
        assert events[0]["symbol"] == "BTSG"
    finally:
        conn.close()


def test_article_filter_large_input_keeps_global_limit(backend):
    sa._refresh(backend, "current", [sa._pick()])
    backend.upsert_sa_articles_meta([sa._article(str(value)) for value in range(1, 26)])
    conn = sa._conn(backend)
    try:
        event = sa.reconciliation_store.list_events(conn)[0]
        rows = sa.reconciliation_store._candidate_rows(
            conn, event, article_ids=[str(value) for value in range(33000)],
        )
        assert [row["article_id"] for row in rows] == sorted(
            [str(value) for value in range(1, 26)], reverse=True,
        )[:20]
    finally:
        conn.close()


def test_many_pinned_citations_survive_family_refresh():
    from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION
    from src.security_lifecycle_investigation import create_automation_assessment

    conn, store, kernel, case_id = lifecycle._context()
    try:
        claim = lifecycle._reserve(kernel, case_id, policy_version=AUTOMATION_POLICY_VERSION)
        old = lifecycle._evidence("old")
        decision = lifecycle._symbol_decision("HAPN", readiness="waiting_effective_date")
        kernel.complete_run(
            run_id=claim.run_id, evidence=(old,), facts=(lifecycle._fact(old),), blockers=(),
            decision_tier="verified_automatic", action_readiness="waiting_effective_date",
            retry_at=None, diagnostics={}, at=lifecycle._LATER, terminal_decision=decision,
        )
        assessment_id = create_automation_assessment(
            store=store, run_id=claim.run_id, decision=decision,
            observation_fingerprint_sha256=lifecycle._FINGERPRINT, at=lifecycle._LATER,
        )
        row = dict(conn.execute("SELECT * FROM security_lifecycle_evidence").fetchone())
        columns = list(row)
        evidence = []
        citations = []
        # Structural retention stress, not 33,000 independently verified assessments.
        for index in range(33000):
            item = dict(row, evidence_id=f"historical-{index}", evidence_dedupe_key=f"historical-{index}")
            evidence.append(tuple(item[key] for key in columns))
            citations.append((assessment_id, "evidence", item["evidence_id"], item["content_sha256"]))
        unreferenced = dict(row, evidence_id="uncited", evidence_dedupe_key="uncited")
        evidence.append(tuple(unreferenced[key] for key in columns))
        conn.executemany(
            f"INSERT INTO security_lifecycle_evidence ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            evidence,
        )
        conn.executemany(
            "INSERT INTO security_lifecycle_assessment_evidence "
            "(assessment_id,reference_kind,evidence_id,cited_content_sha256) VALUES (?,?,?,?)",
            citations,
        )
        conn.commit()
        retry = kernel.reserve_readiness_recheck(
            run_id=claim.run_id, due_at="2026-08-26T00:00:00Z", at="2026-08-26T00:00:00Z",
            execution_owner_id="fixture-owner",
        )
        fresh = lifecycle._evidence("fresh")
        kernel.complete_run(
            run_id=retry.run_id, evidence=(fresh,), facts=(lifecycle._fact(fresh),), blockers=(),
            decision_tier="verified_automatic", action_readiness="waiting_effective_date",
            retry_at=None, diagnostics={}, at="2026-08-26T00:01:00Z", terminal_decision=decision,
            refreshed_source_families=("regulator",),
        )
        assert conn.execute("SELECT count(*) FROM security_lifecycle_evidence").fetchone()[0] == 33002
        assert conn.execute("SELECT 1 FROM security_lifecycle_evidence WHERE evidence_id='uncited'").fetchone() is None
        assert conn.execute("SELECT count(*) FROM security_lifecycle_automation_facts").fetchone()[0] == 2
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


@pytest.mark.parametrize("lineage_id", [2**53 + 1, 2**63 - 1])
def test_lineage_int64_values_are_exact(backend, lineage_id):
    sa._refresh(backend, "current", [sa._pick()])
    conn = sa._conn(backend)
    try:
        conn.execute(
            "INSERT INTO sa_pick_lineages(lineage_id,symbol_key,picked_date,created_at) VALUES (?,?,?,?)",
            (lineage_id, "LARGE", "2026-07-16", sa.NOW),
        )
        conn.execute("UPDATE sa_alpha_picks SET lineage_id=?", (lineage_id,))
        events = sa.reconciliation_store.list_events(conn, lineage_ids=[str(lineage_id), lineage_id, lineage_id - 1])
        assert [event["lineage_id"] for event in events] == [lineage_id]
    finally:
        conn.close()


@pytest.mark.parametrize("value", [2**63, 2**64 + 1, str(2**64 + 1)])
def test_lineage_overflow_still_raises(backend, value):
    sa._refresh(backend, "current", [sa._pick()])
    conn = sa._conn(backend)
    try:
        with pytest.raises(OverflowError):
            sa.reconciliation_store.list_events(conn, lineage_ids=[1, value])
    finally:
        conn.close()


def test_empty_filters_and_filtered_negative_lineages(backend):
    sa._refresh(backend, "current", [sa._pick()])
    conn = sa._conn(backend)
    try:
        events = sa.reconciliation_store.list_events(conn)
        assert len(events) == 1
        assert sa.reconciliation_store.list_events(conn, lineage_ids=[]) == []
        assert sa.reconciliation_store.list_events(conn, lineage_ids=[0, -(2**64)]) == []
        assert sa.reconciliation_store.list_events(conn, lineage_ids=[1, 1, "1", 0, -(2**64)]) == events
        assert sa.reconciliation_store._candidate_rows(conn, events[0], article_ids=[]) == []
    finally:
        conn.close()
    assert backend.query_sa_market_news_recovery_rows([]) == []
    assert backend.query_sa_market_news_body_presence([]) == {}


@pytest.mark.parametrize("identifier", ['quote"id', "slash\\id", "\u4e2d\u6587", "nul\0suffix"])
def test_text_filters_preserve_exact_ids_and_order(backend, identifier):
    backend.upsert_sa_market_news([
        {"news_id": value, "url": "https://seekingalpha.com/news/1", "title": "fixture"}
        for value in [identifier, "other", "nul"]
    ])
    assert [row["news_id"] for row in backend.query_sa_market_news_recovery_rows(
        [identifier, "missing", "other", identifier, ""],
    )] == [identifier, "other"]
    result = backend.query_sa_market_news_body_presence([identifier, "other", identifier])
    assert list(result) == sorted([identifier, "other"])
    assert not any(result.values())
    sa._refresh(backend, "current", [sa._pick()])
    backend.upsert_sa_articles_meta([sa._article(value) for value in [identifier, "nul"]])
    conn = sa._conn(backend)
    try:
        event = sa.reconciliation_store.list_events(conn)[0]
        rows = sa.reconciliation_store._candidate_rows(conn, event, article_ids=[identifier, identifier])
        assert [row["article_id"] for row in rows] == [identifier]
    finally:
        conn.close()


def test_json_set_transport_preserves_binding_types_and_readonly_connection():
    from src.sqlite_id_sets import integer_ids_json, text_ids_query

    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("PRAGMA query_only=ON")
        values = ["a\0b", 'quote"id', "", "\u4e2d\u6587", "slash\\id"]
        query, params = text_ids_query(conn, values)
        assert conn.execute(query, params).fetchall() == [(value,) for value in values]
        for value in [-2**63, 2**53 + 1, 2**63 - 1]:
            assert conn.execute("SELECT value,typeof(value) FROM json_each(?)", (integer_ids_json([value]),)).fetchone() == (value, "integer")
        for value in [-2**63 - 1, 2**63]:
            with pytest.raises(OverflowError):
                integer_ids_json([value])
        with pytest.raises(UnicodeEncodeError):
            text_ids_query(conn, ["\ud800"])
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        assert conn.execute("SELECT name FROM sqlite_temp_schema").fetchall() == []
    finally:
        conn.close()


@pytest.mark.parametrize("nul", [False, True])
def test_text_set_matches_direct_binding_and_uses_the_identifier_index(nul):
    from src.sqlite_id_sets import text_ids_query

    values = ["1", "01", "1e3", str(2**64 + 1), "", "quote'\"id", "\\u0000", "\u4e2d\u6587"]
    if nul:
        values += ["prefix", "prefix\0suffix", "\0"]
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE items(id TEXT PRIMARY KEY)")
        conn.executemany("INSERT INTO items VALUES (?)", [(value,) for value in values])
        conn.commit()
        conn.execute("PRAGMA query_only=ON")
        wanted = values[::2] + ["missing", values[0]]
        reference = conn.execute(
            f"SELECT id FROM items WHERE id IN ({','.join('?' for _ in wanted)}) ORDER BY id", wanted,
        ).fetchall()
        query, params = text_ids_query(conn, wanted)
        sql = f"SELECT id FROM items WHERE id IN ({query}) ORDER BY id"
        assert conn.execute(sql, params).fetchall() == reference
        plan = conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
        assert any("SEARCH items USING" in row[3] for row in plan)
    finally:
        conn.close()
