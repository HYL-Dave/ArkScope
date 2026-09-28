"""Bounded Quick work uses only isolated SQLite capture stores."""

from unittest.mock import Mock

import pytest

from src import sa_capture_store as store
from src import sa_native_host as host
from src.tools.backends.sa_capture_backend import SACaptureBackend
from src.tools.data_access import DataAccessLayer
from tests.test_sa_article_reconciliation_backend import _article, _pick, _refresh
from tests.sa_scope_fixtures import accepted_article_scope


@pytest.fixture
def dal(tmp_path, accepted_article_scope):
    backend = SACaptureBackend(
        sa_db=str(tmp_path / "sa.db"), market_db=str(tmp_path / "market.db")
    )
    return DataAccessLayer(base_path=tmp_path, backend=backend)


def meta(article_id, day, *, count=2):
    return dict(article_id=article_id, title=article_id,
                url=f"https://seekingalpha.com/article/{article_id}",
                published_date=f"2026-09-{day:02d}", comments_count=count,
                comments_count_observed_at="2026-09-26T00:00:00Z")


def work_ids(result):
    return {item["article_id"] for item in (
        result["need_content"] + result["need_comments"]
        + result["reconciliation"]["enrichment"]
    )}


def test_empty_corpus_stays_quick_and_persists_all_metadata(dal):
    result = dal.save_sa_articles_meta([meta(str(day), day) for day in range(1, 8)])
    assert result["auto_upgrade"] is False
    assert result["saved"] == 7
    assert len(dal._backend.query_sa_articles(limit=20)) == 7
    assert work_ids(result) == {"4", "5", "6", "7"}
    assert result["quick_workload"] == {
        "navigation_budget": 4, "selected_count": 4, "eligible_count": 7,
        "deferred_count": 3, "backlog_scope": "eligible_candidates",
        "selected_article_ids": ["7", "6", "5", "4"],
    }


def test_quick_shares_budget_across_body_comments_and_enrichment(dal, monkeypatch):
    incoming = [meta("old-body", 1), meta("new-body", 20),
                meta("comments", 24), meta("enrichment", 23),
                meta("tie-comments", 20), meta("older-comments", 2)]
    dal._backend.upsert_sa_articles_meta(incoming)
    with store.connect(dal._backend._sa_db) as conn:
        conn.execute("""UPDATE sa_articles SET body_markdown='retained body',
            comments_fetched_at='2026-09-25T00:00:00Z',
            provider_comments_count_at_last_scan=1 WHERE article_id != 'old-body'
            AND article_id != 'new-body'""")
    # Exercise the selector with a reconciliation proposal that overlaps both
    # queues; persistence and all scheduling eligibility remain real.
    monkeypatch.setattr(dal._backend, "reconcile_sa_articles", lambda **kwargs: {
        "status": "ok", "enrichment": [
            {"article_id": key, "url": f"https://seekingalpha.com/article/{key}"}
            for key in ["enrichment", "new-body"]
        ],
    })
    result = dal.save_sa_articles_meta(incoming)
    assert result["quick_workload"]["selected_article_ids"] == [
        "comments", "enrichment", "new-body", "tie-comments"
    ]
    assert result["quick_workload"]["eligible_count"] == 6
    assert result["quick_workload"]["deferred_count"] == 2
    assert work_ids(result) == {"comments", "enrichment", "new-body", "tie-comments"}
    assert len(result["need_content"]) == 1
    assert len(result["need_comments"]) == 2
    assert {a["article_id"] for a in result["reconciliation"]["enrichment"]} == {
        "enrichment", "new-body"
    }


def test_deferred_bodies_remain_eligible_without_an_attempt_or_time_quota(dal):
    incoming = [meta(str(day), day, count=0) for day in range(1, 8)]
    dal._backend.upsert_sa_articles_meta(incoming)
    first = dal.save_sa_articles_meta(incoming)
    assert work_ids(first) == {"4", "5", "6", "7"}
    for article_id in work_ids(first):
        dal._backend.save_article_with_comments(
            article_id, "retained body", [], provider_comments_count=0,
            comment_scan_mode="backfill", comment_scan_stop_reason="stable_bottom",
            comment_scan_stable_bottom_rounds=5,
        )
    for article_id in ("1", "2", "3"):
        article = dal._backend.get_sa_article_with_comments(article_id)
        assert article["detail_fetched_at"] is None
        assert article["comment_scan_attempted_at"] is None
    second = dal.save_sa_articles_meta(incoming)
    assert work_ids(second) == {"1", "2", "3"}
    assert second["quick_workload"]["deferred_count"] == 0


def test_enrichment_backlog_is_counted_before_the_quick_cap(dal):
    _refresh(dal._backend, "current", [_pick()])
    incoming = [_article(str(i), ticker=None, list_ticker=None) for i in range(7)]
    dal._backend.upsert_sa_articles_meta(incoming)
    result = dal.save_sa_articles_meta(incoming)
    assert result["quick_workload"]["eligible_count"] == 7
    assert result["quick_workload"]["deferred_count"] == 3
    assert len(result["reconciliation"]["enrichment"]) == 4
    assert work_ids(result) == {"3", "4", "5", "6"}


def test_two_changed_comments_are_not_a_historical_body_refill(dal):
    from tests.test_sa_article_body_quality import DISCLOSURES

    incoming = [meta(str(day), 1) for day in range(100)]
    dal._backend.upsert_sa_articles_meta(incoming)
    with store.connect(dal._backend._sa_db) as conn:
        conn.execute("""UPDATE sa_articles SET body_markdown=?,
            detail_fetched_at='2026-09-01T00:00:00Z',
            comments_fetched_at='2026-09-25T00:00:00Z',
            provider_comments_count_at_last_scan=2""", (DISCLOSURES,))
    incoming[0]["comments_count"] = 3
    incoming[1]["comments_count"] = 3
    result = host._handle_save_articles_meta(dal, {"articles": incoming, "mode": "quick"})
    assert result["need_content"] == []
    assert result["reconciliation"]["enrichment"] == []
    assert {a["article_id"] for a in result["need_comments"]} == {"0", "1"}
    assert result["body_recovery_pending"] == 100
    assert result["quick_workload"]["selected_count"] == 2
    assert result["quick_workload"]["deferred_count"] == 0


def test_quick_comment_backlog_retains_checkpoint_until_selected(dal):
    incoming = [meta(str(day), day) for day in range(1, 8)]
    dal._backend.upsert_sa_articles_meta(incoming)
    with store.connect(dal._backend._sa_db) as conn:
        conn.execute("""UPDATE sa_articles SET body_markdown='retained body',
            comments_fetched_at='2026-09-25T00:00:00Z',
            provider_comments_count_at_last_scan=1""")
    result = dal.save_sa_articles_meta(incoming)
    assert result["need_content"] == []
    assert [a["article_id"] for a in result["need_comments"]] == ["7", "6", "5", "4"]
    assert result["quick_workload"]["deferred_count"] == 3
    for article_id in ("4", "5", "6", "7"):
        dal._backend.update_article_comments(
            article_id, [], provider_comments_count=2, comment_scan_mode="quick",
        )
    for article_id in ("1", "2", "3"):
        assert dal._backend.get_sa_article_with_comments(article_id)[
            "provider_comments_count_at_last_scan"
        ] == 1
    assert work_ids(dal.save_sa_articles_meta(incoming)) == {"1", "2", "3"}


def test_empty_quick_has_an_explicit_zero_work_receipt(dal):
    result = dal.save_sa_articles_meta([])
    assert result["auto_upgrade"] is False
    assert result["saved"] == 0
    assert result["quick_workload"]["navigation_budget"] == 4
    assert result["quick_workload"]["eligible_count"] == 0
    assert result["quick_workload"]["selected_count"] == 0
    assert result["quick_workload"]["deferred_count"] == 0
    assert result["quick_workload"]["selected_article_ids"] == []


@pytest.mark.parametrize("mode", ["full", "backfill"])
def test_explicit_deeper_modes_keep_their_existing_selection(dal, mode):
    result = dal.save_sa_articles_meta([meta(str(day), day) for day in range(1, 8)], mode=mode)
    assert len(work_ids(result)) == 7
    assert "quick_workload" not in result


@pytest.mark.parametrize("symbol,ticker", [("B", "BA"), ("B", "BAC"), ("C", "CL"),
                                            ("CLS", "CLSX"), ("KGC", "KGCX")])
def test_legacy_detail_cache_rejects_unproven_prefixes(symbol, ticker):
    result = host._handle_check_detail_cache(
        Mock(get_sa_pick_detail=Mock(return_value=None)),
        [{"symbol": symbol}], [{"ticker": ticker, "url": "wrong"}],
    )
    assert result["need_detail"] == []
    assert result["no_article"] == [symbol]


@pytest.mark.parametrize("symbol,ticker", [("KGC", "KGCK"), ("CLS", "CLSCLS"),
                                            ("SSRM", "SSRMSSRM")])
def test_legacy_detail_cache_retains_only_documented_scraper_aliases(symbol, ticker):
    dal = Mock(get_sa_pick_detail=Mock(return_value=None))
    picks = [{"symbol": symbol}]
    articles = [{"ticker": ticker, "url": "alias"}]
    assert host._handle_check_detail_cache(dal, picks, articles)["need_detail"][0]["article_url"] == "alias"
    articles.append({"ticker": symbol, "url": "exact"})
    assert host._handle_check_detail_cache(dal, picks, articles)["need_detail"][0]["article_url"] == "exact"
