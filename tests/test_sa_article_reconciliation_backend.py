from __future__ import annotations

import json
import sqlite3

import pytest

import src.sa_article_reconciliation_store as reconciliation_store
import src.sa_capture_store as capture_store
from src.tools.backends.db_backend import DatabaseBackend
from src.tools.backends.sa_capture_backend import SACaptureDatabaseBackend


FAKE_DSN = "postgresql://disabled"
NOW = "2026-07-18T01:00:00Z"


@pytest.fixture()
def backend(tmp_path, monkeypatch):
    monkeypatch.setattr(
        DatabaseBackend,
        "_get_conn",
        lambda self: (_ for _ in ()).throw(AssertionError("PG touched")),
    )
    return SACaptureDatabaseBackend(FAKE_DSN, sa_db=str(tmp_path / "sa_capture.db"))


def _pick(
    symbol: str = "BTSG",
    *,
    picked: str = "2026-07-15",
    closed: str | None = None,
    company: str = "BrightSpring Health Services, Inc.",
) -> dict:
    return {
        "symbol": symbol,
        "company": company,
        "picked_date": picked,
        "closed_date": closed,
        "raw_data": {"source": "fixture"},
    }


def _article(
    article_id: str = "6316639",
    *,
    title: str = "Stock Buy: Top Health Care Services Stock Delivers Double-Digit Growth",
    ticker: str | None = "BTSG",
    published: str = "2026-07-15",
    list_ticker: str | None = "BTSG",
) -> dict:
    return {
        "article_id": article_id,
        "url": f"https://seekingalpha.com/alpha-picks/articles/{article_id}-fixture",
        "title": title,
        "ticker": ticker,
        "published_date": published,
        "article_type": "analysis",
        "comments_count": 0,
        "list_ticker": list_ticker,
        "list_ticker_observed_at": NOW,
    }


def _refresh(backend, scope: str, picks: list[dict]) -> None:
    assert backend.apply_sa_refresh(scope, picks, NOW, NOW) == len(picks)


def _conn(backend) -> sqlite3.Connection:
    return capture_store.connect(backend._sa_db)


def _links(backend) -> list[dict]:
    conn = _conn(backend)
    try:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM sa_pick_article_links ORDER BY link_id"
            ).fetchall()
        ]
    finally:
        conn.close()


def _authority_digest(backend) -> str:
    conn = _conn(backend)
    try:
        payload = {}
        for table in (
            "sa_pick_lineages",
            "sa_alpha_picks",
            "sa_articles",
            "sa_article_comments",
            "sa_pick_article_links",
            "sa_pick_article_decisions",
        ):
            payload[table] = [
                tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY 1")
            ]
        return json.dumps(payload, sort_keys=True, default=str)
    finally:
        conn.close()


def test_article_list_and_detail_ticker_observations_persist_independently(backend):
    backend.upsert_sa_articles_meta([_article()])
    backend.save_article_with_comments(
        "6316639",
        "captured body",
        [],
        detail_ticker="BTSG",
        detail_ticker_observed_at="2026-07-18T01:05:00Z",
    )
    article = backend.get_sa_article_with_comments("6316639")
    assert article["list_ticker"] == "BTSG"
    assert article["detail_ticker"] == "BTSG"
    assert article["list_ticker_observed_at"] == "2026-07-18T01:00:00+00:00"
    assert article["detail_ticker_observed_at"] == "2026-07-18T01:05:00+00:00"


def test_list_detail_conflict_keeps_both_values_and_legacy_projection_is_not_evidence(backend):
    _refresh(backend, "current", [_pick()])
    backend.upsert_sa_articles_meta([_article(ticker="BTSG")])
    backend.save_article_with_comments(
        "6316639", "body", [], detail_ticker="AGX", detail_ticker_observed_at=NOW
    )
    out = backend.reconcile_sa_articles(
        pick_keys=[("BTSG", "2026-07-15")], max_events=100, enrichment_limit=4
    )
    article = backend.get_sa_article_with_comments("6316639")
    assert (article["list_ticker"], article["detail_ticker"], article["ticker"]) == (
        "BTSG", "AGX", "BTSG"
    )
    assert out["auto_linked"] == 0
    event = backend.query_sa_article_review_queue(limit=20)["events"][0]
    assert event["candidates"][0]["reason_code"] == "ticker_metadata_conflict"


def test_null_observation_does_not_erase_prior_explicit_provider_ticker(backend):
    backend.upsert_sa_articles_meta([_article()])
    backend.upsert_sa_articles_meta([
        _article(list_ticker=None, ticker=None),
    ])
    backend.save_article_with_comments(
        "6316639", "body", [], detail_ticker="BTSG", detail_ticker_observed_at=NOW
    )
    backend.save_article_with_comments(
        "6316639", "body 2", [], detail_ticker=None, detail_ticker_observed_at=None
    )
    article = backend.get_sa_article_with_comments("6316639")
    assert article["list_ticker"] == article["detail_ticker"] == "BTSG"


def test_refresh_current_and_closed_rows_resolve_one_lineage(backend):
    _refresh(backend, "current", [_pick()])
    _refresh(backend, "closed", [_pick(closed="2026-08-01")])
    conn = _conn(backend)
    try:
        assert conn.execute("SELECT COUNT(*) FROM sa_pick_lineages").fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(DISTINCT lineage_id) FROM sa_alpha_picks"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_refresh_changed_picked_date_resolves_new_lineage(backend):
    _refresh(backend, "current", [_pick(picked="2026-07-15")])
    _refresh(backend, "current", [_pick(picked="2026-07-16")])
    conn = _conn(backend)
    try:
        assert conn.execute("SELECT COUNT(*) FROM sa_pick_lineages").fetchone()[0] == 2
    finally:
        conn.close()


def test_exact_unique_entry_auto_link_projects_to_every_lineage_row(backend):
    _refresh(backend, "current", [_pick()])
    _refresh(backend, "closed", [_pick(closed="2026-08-01")])
    backend.upsert_sa_articles_meta([_article()])
    backend.save_article_with_comments("6316639", "entry body", [])
    result = backend.reconcile_sa_articles(
        pick_keys=[("BTSG", "2026-07-15")], max_events=100, enrichment_limit=4
    )
    assert result["auto_linked"] == 1
    conn = _conn(backend)
    try:
        rows = conn.execute(
            "SELECT canonical_article_id, detail_report FROM sa_alpha_picks ORDER BY id"
        ).fetchall()
        assert [tuple(row) for row in rows] == [
            ("6316639", "entry body"),
            ("6316639", "entry body"),
        ]
    finally:
        conn.close()


def test_exit_auto_link_uses_closed_date_and_never_overwrites_entry_projection(backend):
    _refresh(backend, "current", [_pick()])
    _refresh(backend, "closed", [_pick(closed="2026-08-01")])
    backend.upsert_sa_articles_meta([
        _article("entry"),
        _article(
            "exit",
            title="Stock Sell: BrightSpring exits Alpha Picks",
            published="2026-08-01",
        ),
    ])
    backend.save_article_with_comments("entry", "entry body", [])
    backend.save_article_with_comments("exit", "exit body", [])
    result = backend.reconcile_sa_articles(
        pick_keys=[("BTSG", "2026-07-15")], max_events=100, enrichment_limit=4
    )
    assert result["auto_linked"] == 2
    assert {(row["role"], row["article_id"]) for row in _links(backend)} == {
        ("entry", "entry"), ("exit", "exit")
    }
    assert backend.get_sa_pick_detail("BTSG")["canonical_article_id"] == "entry"


def test_multiple_closed_dates_receive_distinct_exit_links(backend):
    _refresh(backend, "closed", [
        _pick(closed="2026-08-01"),
        _pick(closed="2026-09-01"),
    ])
    backend.upsert_sa_articles_meta([
        _article("exit-1", title="Stock Sell: BTSG", published="2026-08-01"),
        _article("exit-2", title="Stock Sell: BTSG", published="2026-09-01"),
    ])
    result = backend.reconcile_sa_articles(
        pick_keys=[("BTSG", "2026-07-15")], max_events=100, enrichment_limit=4
    )
    assert result["auto_linked"] == 2
    assert {(row["event_anchor_date"], row["article_id"]) for row in _links(backend)} == {
        ("2026-08-01", "exit-1"), ("2026-09-01", "exit-2")
    }


def test_missing_closed_date_is_unmatchable_and_visible(backend):
    _refresh(backend, "closed", [_pick(closed=None)])
    queue = backend.query_sa_article_review_queue(limit=20)
    exit_events = [event for event in queue["events"] if event["role"] == "exit"]
    assert len(exit_events) == 1
    assert exit_events[0]["event_anchor_date"] is None
    assert exit_events[0]["reason_code"] == "missing_event_anchor"
    assert exit_events[0]["candidates"] == []


def test_same_strength_tie_stays_in_review_queue(backend):
    _refresh(backend, "current", [_pick()])
    backend.upsert_sa_articles_meta([_article("10"), _article("20")])
    result = backend.reconcile_sa_articles(
        pick_keys=[("BTSG", "2026-07-15")], max_events=100, enrichment_limit=4
    )
    assert result["auto_linked"] == 0
    assert result["review_required"] == 1
    event = backend.query_sa_article_review_queue(limit=20)["events"][0]
    assert event["reason_code"] == "ambiguous_candidates"
    assert [candidate["article_id"] for candidate in event["candidates"]] == ["10", "20"]


def test_outside_window_legacy_projection_is_reported_not_grandfathered(backend):
    _refresh(backend, "current", [_pick()])
    backend.upsert_sa_articles_meta([
        _article("legacy", published="2024-01-01", title="Stock Buy: BTSG")
    ])
    conn = _conn(backend)
    conn.execute(
        "UPDATE sa_alpha_picks SET canonical_article_id='legacy' WHERE symbol='BTSG'"
    )
    conn.commit()
    conn.close()
    preview = backend.preview_sa_legacy_article_links(limit=20)
    assert preview["items"][0]["article_id"] == "legacy"
    assert preview["items"][0]["reason_code"] == "outside_date_window"
    assert _links(backend) == []


def test_repeated_symbol_lineages_reconcile_independently(backend):
    _refresh(backend, "current", [
        _pick(picked="2025-01-01"),
        _pick(picked="2026-07-15"),
    ])
    backend.upsert_sa_articles_meta([
        _article("old", published="2025-01-01", title="Stock Buy: BTSG"),
        _article("new", published="2026-07-15", title="Stock Buy: BTSG"),
    ])
    result = backend.reconcile_sa_articles(
        pick_keys=[("BTSG", "2025-01-01"), ("BTSG", "2026-07-15")],
        max_events=100,
        enrichment_limit=4,
    )
    assert result["auto_linked"] == 2
    assert {row["article_id"] for row in _links(backend)} == {"old", "new"}


def test_reconciliation_rerun_is_idempotent(backend):
    _refresh(backend, "current", [_pick()])
    backend.upsert_sa_articles_meta([_article()])
    first = backend.reconcile_sa_articles(
        pick_keys=[("BTSG", "2026-07-15")], max_events=100, enrichment_limit=4
    )
    first_digest = _authority_digest(backend)
    second = backend.reconcile_sa_articles(
        pick_keys=[("BTSG", "2026-07-15")], max_events=100, enrichment_limit=4
    )
    assert first["auto_linked"] == 1
    assert second["auto_linked"] == 0
    assert _authority_digest(backend) == first_digest


def test_rejected_candidate_is_durable_and_not_reproposed(backend):
    _refresh(backend, "current", [_pick()])
    backend.upsert_sa_articles_meta([_article("10"), _article("20"), _article("30")])
    event = backend.resolve_sa_reconciliation_event(
        symbol="BTSG", role="entry", event_anchor_date="2026-07-15"
    )
    backend.reject_sa_article_candidate(
        lineage_id=event["lineage_id"],
        role="entry",
        event_anchor_date="2026-07-15",
        article_id="10",
        reason_code="operator_rejected",
    )
    backend.reject_sa_article_candidate(
        lineage_id=event["lineage_id"],
        role="entry",
        event_anchor_date="2026-07-15",
        article_id="10",
        reason_code="operator_rejected",
    )
    queue = backend.query_sa_article_review_queue(limit=20)
    assert [row["article_id"] for row in queue["events"][0]["candidates"]] == ["20", "30"]
    conn = _conn(backend)
    try:
        assert conn.execute("SELECT COUNT(*) FROM sa_pick_article_decisions").fetchone()[0] == 1
    finally:
        conn.close()


def test_replacement_revokes_old_link_and_requires_expected_link_id(backend):
    _refresh(backend, "current", [_pick()])
    backend.upsert_sa_articles_meta([_article("first"), _article("second")])
    event = backend.resolve_sa_reconciliation_event(
        symbol="BTSG", role="entry", event_anchor_date="2026-07-15"
    )
    first = backend.accept_sa_article_link(
        lineage_id=event["lineage_id"], role="entry", event_anchor_date="2026-07-15",
        article_id="first", link_source="user", evidence_codes=[], replace_link_id=None,
    )
    with pytest.raises(ValueError, match="replace_link_id"):
        backend.accept_sa_article_link(
            lineage_id=event["lineage_id"], role="entry", event_anchor_date="2026-07-15",
            article_id="second", link_source="user", evidence_codes=[], replace_link_id=None,
        )
    second = backend.accept_sa_article_link(
        lineage_id=event["lineage_id"], role="entry", event_anchor_date="2026-07-15",
        article_id="second", link_source="user", evidence_codes=[],
        replace_link_id=first["link_id"],
    )
    links = _links(backend)
    assert second["link_id"] != first["link_id"]
    assert links[0]["revoked_at"] is not None
    assert links[1]["supersedes_link_id"] == first["link_id"]


def test_manual_link_never_populates_provider_ticker_observations(backend):
    _refresh(backend, "current", [_pick()])
    backend.upsert_sa_articles_meta([
        _article("manual", ticker="BTSG", list_ticker=None, title="General health care note")
    ])
    event = backend.resolve_sa_reconciliation_event(
        symbol="BTSG", role="entry", event_anchor_date="2026-07-15"
    )
    backend.accept_sa_article_link(
        lineage_id=event["lineage_id"], role="entry", event_anchor_date="2026-07-15",
        article_id="manual", link_source="user", evidence_codes=[], replace_link_id=None,
    )
    article = backend.get_sa_article_with_comments("manual")
    assert article["list_ticker"] is None
    assert article["detail_ticker"] is None


def test_article_body_capture_survives_reconciliation_failure_byte_for_byte(backend, monkeypatch):
    _refresh(backend, "current", [_pick()])
    backend.upsert_sa_articles_meta([_article()])
    before = _authority_digest(backend)
    backend.save_article_with_comments("6316639", "captured body", [])
    captured = _authority_digest(backend)
    assert captured != before
    monkeypatch.setattr(
        reconciliation_store,
        "decide_reconciliation",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("matcher failed")),
    )
    with pytest.raises(RuntimeError, match="matcher failed"):
        backend.reconcile_sa_articles(
            article_ids=["6316639"], max_events=100, enrichment_limit=4
        )
    assert _authority_digest(backend) == captured


def test_pick_capture_survives_reconciliation_failure_byte_for_byte(backend, monkeypatch):
    _refresh(backend, "current", [_pick()])
    captured = _authority_digest(backend)
    monkeypatch.setattr(
        reconciliation_store,
        "decide_reconciliation",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("matcher failed")),
    )
    with pytest.raises(RuntimeError, match="matcher failed"):
        backend.reconcile_sa_articles(
            pick_keys=[("BTSG", "2026-07-15")], max_events=100, enrichment_limit=4
        )
    assert _authority_digest(backend) == captured


def test_matcher_requested_enrichment_is_deduped_and_bounded(backend):
    _refresh(backend, "current", [
        _pick("AAA", company="Alpha A", picked="2026-07-15"),
        _pick("BBB", company="Beta B", picked="2026-07-15"),
    ])
    backend.upsert_sa_articles_meta([
        _article(
            "bodyless",
            title="Stock Buy: a new portfolio position",
            ticker=None,
            list_ticker=None,
        )
    ])
    result = backend.reconcile_sa_articles(
        pick_keys=[("AAA", "2026-07-15"), ("BBB", "2026-07-15")],
        max_events=100,
        enrichment_limit=1,
    )
    assert result["enrichment"] == [{
        "article_id": "bodyless",
        "url": "https://seekingalpha.com/alpha-picks/articles/bodyless-fixture",
    }]


def test_legacy_preview_and_review_queue_are_read_only(backend):
    _refresh(backend, "current", [_pick()])
    backend.upsert_sa_articles_meta([_article("10"), _article("20")])
    before = _authority_digest(backend)
    preview = backend.preview_sa_legacy_article_links(limit=20)
    queue = backend.query_sa_article_review_queue(limit=20)
    assert preview == {"items": [], "total": 0}
    assert queue["total"] == 1
    assert _authority_digest(backend) == before
