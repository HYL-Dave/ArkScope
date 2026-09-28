"""Known failed captures must not be counted as article prose or erase it."""

import hashlib
import json
import sqlite3
from unittest.mock import MagicMock

import pytest
from tests.sa_scope_fixtures import accepted_article_scope

from src import sa_capture_store as store
from src.tools.backends.sa_capture_backend import SACaptureBackend


DISCLOSURES = (
    "# Investment update\n\n*Author: Alpha Picks*\n\n"
    "Analyst's Disclosure: I have no stock position.\n\n"
    "Seeking Alpha's Disclosure: Past performance is no guarantee of future results."
)
COMMENTS = "# Investment update\n\n### COMMENTS (42)\n\nSort by\n\nNewest\n\nReader: Stock Buy: ABC"
PROSE = "Margins improved as freight costs fell, despite weaker demand."


@pytest.fixture
def backend(tmp_path):
    backend = SACaptureBackend(sa_db=str(tmp_path / "sa.db"), market_db=str(tmp_path / "market.db"))
    backend.upsert_sa_articles_meta([{
        "article_id": "123", "title": "Investment update", "ticker": "ABC",
        "url": "https://seekingalpha.com/alpha-picks/articles/123-investment-update",
        "published_date": "2026-09-01", "article_type": "analysis",
    }])
    return backend


def test_bad_recapture_does_not_overwrite_body_or_success_timestamp_but_keeps_comments(backend):
    backend.save_article_with_comments("123", PROSE, [])
    with sqlite3.connect(backend._sa_db) as conn:
        before = conn.execute("SELECT body_markdown, detail_fetched_at FROM sa_articles").fetchone()
    result = backend.save_article_with_comments("123", DISCLOSURES, [{
        "comment_id": "c1", "commenter": "Reader", "comment_text": "A recent observation.",
        "comment_date": "2026-09-24T00:00:00Z", "upvotes": 0,
    }])
    with sqlite3.connect(backend._sa_db) as conn:
        assert conn.execute("SELECT body_markdown, detail_fetched_at FROM sa_articles").fetchone() == before
        assert conn.execute("SELECT comment_text FROM sa_article_comments").fetchone()[0] == "A recent observation."
    assert result["ok"] is True  # The independent comment transaction succeeded.
    assert result["body_saved"] is False
    assert result["body_quality"]["reason_code"] == "sa_article_body_disclosure_only"


@pytest.mark.parametrize("body", [DISCLOSURES, COMMENTS, "", "# Investment update\n\n*Author: Alpha Picks*"])
def test_unusable_first_capture_never_sets_a_body_success_time(backend, body):
    result = backend.save_article_with_comments("123", body, [])
    with sqlite3.connect(backend._sa_db) as conn:
        assert conn.execute("SELECT body_markdown, detail_fetched_at FROM sa_articles").fetchone() == (None, None)
    assert result["body_saved"] is False


@pytest.mark.parametrize("body,reason", [
    (None, "sa_article_body_missing"),
    (" \n", "sa_article_body_missing"),
    (DISCLOSURES, "sa_article_body_disclosure_only"),
    (DISCLOSURES.replace("'", "\u2019"), "sa_article_body_disclosure_only"),
    (COMMENTS, "sa_article_body_comment_thread"),
    ("# Investment update\n\n*Author: Alpha Picks*", "sa_article_body_metadata_only"),
])
def test_known_non_body_shapes_are_not_narrative(body, reason):
    from src.sa.article_body_quality import assess_body, usable_body

    quality = assess_body(body, title="Investment update")
    assert quality["status"] != "available"
    assert quality["reason_code"] == reason
    assert usable_body(body, title="Investment update") == ""


def test_copied_pick_report_without_separate_title_still_rejects_comment_thread():
    from src.sa.article_body_quality import assess_body

    assert assess_body(COMMENTS)["reason_code"] == "sa_article_body_comment_thread"


@pytest.mark.parametrize("body", [
    PROSE,
    DISCLOSURES + "\n\n" + PROSE,
    "## Disclosure risks\n\nThe company omitted a material customer concentration disclosure.",
    "The reader comments about margins do not change our thesis.",
    "| Year | Revenue |\n| --- | --- |\n| 2026 | 123 |",
])
def test_valid_short_or_mixed_text_is_preserved_but_not_certified_complete(body):
    from src.sa.article_body_quality import assess_body, usable_body

    quality = assess_body(body, title="Investment update")
    assert quality["status"] == "available"
    assert quality["completeness"] == "not_verified"
    assert usable_body(body, title="Investment update") == body


def test_legacy_bad_body_is_not_returned_by_backend_readers_and_is_not_deleted(backend):
    with store.connect(backend._sa_db) as conn:
        conn.execute("UPDATE sa_articles SET body_markdown=?, detail_fetched_at='2026-03-01'", (DISCLOSURES,))
    listing = backend.query_sa_articles(limit=10)[0]
    assert listing["has_content"] is False
    assert listing["body_quality"]["status"] == "unusable"
    detail = backend.get_sa_article_with_comments("123")
    assert not detail["body_markdown"]
    with sqlite3.connect(backend._sa_db) as conn:
        assert conn.execute("SELECT body_markdown FROM sa_articles").fetchone()[0] == DISCLOSURES


def test_bad_pick_report_is_not_cached_or_written(backend):
    backend.apply_sa_refresh("current", [{"symbol": "ABC", "company": "ABC", "picked_date": "2026-09-01"}],
                             "2026-09-25T00:00:00Z", "2026-09-25T00:00:00Z")
    assert backend.update_sa_pick_detail("ABC", "2026-09-01", PROSE)
    assert not backend.update_sa_pick_detail("ABC", "2026-09-01", DISCLOSURES)
    assert backend.get_sa_pick_detail("ABC")["detail_report"] == PROSE
    with store.connect(backend._sa_db) as conn:
        conn.execute("UPDATE sa_alpha_picks SET detail_report=?", (DISCLOSURES,))
    assert not backend.get_sa_pick_detail("ABC")["detail_report"]


def test_title_only_canonical_pick_copy_uses_article_context_and_is_repaired(backend):
    backend.apply_sa_refresh("current", [{"symbol": "ABC", "company": "ABC", "picked_date": "2026-09-01"}],
                             "2026-09-25T00:00:00Z", "2026-09-25T00:00:00Z")
    title = "Investment update"
    with store.connect(backend._sa_db) as conn:
        conn.execute("UPDATE sa_articles SET body_markdown=?", (title,))
        conn.execute("UPDATE sa_alpha_picks SET canonical_article_id='123', detail_report=?", (title,))
    detail = backend.get_sa_pick_detail("ABC")
    assert detail["body_quality"]["reason_code"] == "sa_article_body_metadata_only"
    assert detail["detail_report"] is None
    result = backend.repair_article_body("123", PROSE, expected_body_sha256=hashlib.sha256(title.encode()).hexdigest())
    assert result["body_saved"] is True
    assert backend.get_sa_pick_detail("ABC")["detail_report"] == PROSE


def test_body_repair_keeps_valid_and_unrelated_pick_copies(backend):
    backend.apply_sa_refresh("current", [
        {"symbol": "ABC", "company": "ABC", "picked_date": "2026-09-01"},
        {"symbol": "XYZ", "company": "XYZ", "picked_date": "2026-09-01"},
    ], "2026-09-25T00:00:00Z", "2026-09-25T00:00:00Z")
    with store.connect(backend._sa_db) as conn:
        conn.execute("UPDATE sa_articles SET body_markdown=?", (DISCLOSURES,))
        conn.execute("UPDATE sa_alpha_picks SET canonical_article_id='123', detail_report=? WHERE symbol='ABC'", (PROSE,))
        conn.execute("UPDATE sa_alpha_picks SET canonical_article_id='456', detail_report=? WHERE symbol='XYZ'", (DISCLOSURES,))
        before = [tuple(row) for row in conn.execute("SELECT * FROM sa_alpha_picks ORDER BY id")]
    assert backend.repair_article_body("123", "New genuine company analysis.",
        expected_body_sha256=hashlib.sha256(DISCLOSURES.encode()).hexdigest())["body_saved"]
    with store.connect(backend._sa_db) as conn:
        assert [tuple(row) for row in conn.execute("SELECT * FROM sa_alpha_picks ORDER BY id")] == before


def test_pick_writer_rejects_bare_canonical_title_without_overwriting_prose(backend):
    backend.apply_sa_refresh("current", [{"symbol": "ABC", "company": "ABC", "picked_date": "2026-09-01"}],
                             "2026-09-25T00:00:00Z", "2026-09-25T00:00:00Z")
    with store.connect(backend._sa_db) as conn:
        conn.execute("UPDATE sa_alpha_picks SET canonical_article_id='123', detail_report=?", (PROSE,))
        before = tuple(conn.execute("SELECT detail_report, detail_fetched_at FROM sa_alpha_picks").fetchone())
    assert not backend.update_sa_pick_detail("ABC", "2026-09-01", "Investment update")
    with store.connect(backend._sa_db) as conn:
        assert tuple(conn.execute("SELECT detail_report, detail_fetched_at FROM sa_alpha_picks").fetchone()) == before


def test_dal_cannot_write_rejected_body_to_its_file_fallback(backend, tmp_path):
    from src.tools.data_access import DataAccessLayer

    backend.apply_sa_refresh("current", [{"symbol": "ABC", "company": "ABC", "picked_date": "2026-09-01"}],
                             "2026-09-25T00:00:00Z", "2026-09-25T00:00:00Z")
    dal = DataAccessLayer.__new__(DataAccessLayer)
    dal._backend = backend
    dal._SA_CACHE_DIR = tmp_path / "cache"
    assert dal.save_sa_pick_detail("ABC", "2026-09-01", PROSE)
    path = dal._SA_CACHE_DIR / "details" / "ABC_2026-09-01.json"
    before = path.read_bytes()
    assert not dal.save_sa_pick_detail("ABC", "2026-09-01", DISCLOSURES)
    assert path.read_bytes() == before


@pytest.mark.parametrize("picked_date", ["2026-09-01", None])
def test_dal_file_fallback_hides_unusable_body_and_preserves_raw_evidence(tmp_path, picked_date):
    from src.tools.data_access import DataAccessLayer

    dal = DataAccessLayer.__new__(DataAccessLayer)
    dal._backend = MagicMock()
    dal._backend.get_sa_pick_detail.return_value = None
    dal._SA_CACHE_DIR = tmp_path / "cache"
    dal._SA_CACHE_DIR.mkdir()
    (dal._SA_CACHE_DIR / "details").mkdir()
    path = dal._SA_CACHE_DIR / "details" / "ABC_2026-09-01.json"
    path.write_text(json.dumps({"detail_report": DISCLOSURES, "detail_fetched_at": "2026-03-01"}))
    (dal._SA_CACHE_DIR / "portfolio_current.json").write_text(json.dumps([
        {"symbol": "ABC", "picked_date": "2026-09-01", "company": "ABC Company"},
    ]))
    before = path.read_bytes()
    result = dal.get_sa_pick_detail("ABC", picked_date)
    assert result["body_quality"]["status"] == "unusable"
    assert result["detail_report"] is None
    assert result["company"] == "ABC Company"
    assert path.read_bytes() == before


def test_body_only_repair_does_not_change_comments_or_unrelated_pick_copies(backend):
    backend.apply_sa_refresh("current", [{"symbol": "ABC", "company": "ABC", "picked_date": "2026-09-01"}],
                             "2026-09-25T00:00:00Z", "2026-09-25T00:00:00Z")
    backend.save_article_with_comments("123", PROSE, [{
        "comment_id": "c1", "commenter": "Reader", "comment_text": "Keep me.",
        "comment_date": "2026-09-24T00:00:00Z", "upvotes": 2,
    }])
    with store.connect(backend._sa_db) as conn:
        conn.execute("UPDATE sa_articles SET body_markdown=?", (DISCLOSURES,))
        conn.execute("UPDATE sa_alpha_picks SET canonical_article_id='123', detail_report=?", (DISCLOSURES,))
        before_comments = [tuple(row) for row in conn.execute("SELECT * FROM sa_article_comments")]
        before_links = [tuple(row) for row in conn.execute("SELECT * FROM sa_pick_article_links")]
        before_scan = tuple(conn.execute("SELECT comments_fetched_at, comment_scan_attempted_at, comment_scan_policy FROM sa_articles").fetchone())
    result = backend.repair_article_body("123", PROSE, expected_body_sha256=hashlib.sha256(DISCLOSURES.encode()).hexdigest())
    assert result["body_saved"] is True
    with store.connect(backend._sa_db) as conn:
        assert [tuple(row) for row in conn.execute("SELECT * FROM sa_article_comments")] == before_comments
        assert [tuple(row) for row in conn.execute("SELECT * FROM sa_pick_article_links")] == before_links
        assert tuple(conn.execute("SELECT comments_fetched_at, comment_scan_attempted_at, comment_scan_policy FROM sa_articles").fetchone()) == before_scan
        assert conn.execute("SELECT detail_report FROM sa_alpha_picks").fetchone()[0] == PROSE


def test_repair_cannot_overwrite_another_capture_after_preview(backend):
    empty_hash = hashlib.sha256(b"").hexdigest()
    backend.save_article_with_comments("123", PROSE, [])
    result = backend.repair_article_body("123", "Different body", expected_body_sha256=empty_hash)
    assert result["status"] == "skipped"
    assert result["body_saved"] is False
    assert backend.get_sa_article_with_comments("123")["body_markdown"] == PROSE


def test_repair_rejects_disclosures_without_setting_success(backend):
    result = backend.repair_article_body("123", DISCLOSURES, expected_body_sha256=hashlib.sha256(b"").hexdigest())
    assert result["status"] == "error"
    assert result["body_saved"] is False
    assert backend.query_sa_articles(limit=1)[0]["detail_fetched_at"] is None


@pytest.mark.parametrize("old_body", [DISCLOSURES, "", None])
def test_regular_sync_does_not_turn_new_quality_detection_into_mass_backfill(backend, old_body, accepted_article_scope):
    from src.tools.data_access import DataAccessLayer

    with store.connect(backend._sa_db) as conn:
        conn.execute("UPDATE sa_articles SET body_markdown=?, detail_fetched_at='2026-03-01'", (old_body,))
    dal = DataAccessLayer.__new__(DataAccessLayer)
    dal._backend = backend
    result = dal.save_sa_articles_meta([{
        "article_id": "123", "url": "https://seekingalpha.com/alpha-picks/articles/123-investment-update",
        "title": "Investment update", "published_date": "2026-09-01",
    }], mode="full")
    assert result["need_content"] == []
    if old_body in (None, ""):
        assert result["need_comments"] == []
    assert result["reconciliation"]["enrichment"] == []
    assert result["body_recovery_pending"] == 1


def test_legacy_blank_body_does_not_disable_existing_comment_updates(backend, accepted_article_scope):
    from src.tools.data_access import DataAccessLayer

    backend.save_article_with_comments("123", PROSE, [{
        "comment_id": "c1", "commenter": "Reader", "comment_text": "Keep updating these comments.",
        "comment_date": "2026-09-24T00:00:00Z", "upvotes": 1,
    }], provider_comments_count=1, comment_scan_stop_reason="stable_bottom", comment_scan_stable_bottom_rounds=2)
    with store.connect(backend._sa_db) as conn:
        conn.execute("UPDATE sa_articles SET body_markdown='', detail_fetched_at='2026-03-01'")
    dal = DataAccessLayer.__new__(DataAccessLayer)
    dal._backend = backend
    result = dal.save_sa_articles_meta([{
        "article_id": "123", "url": "https://seekingalpha.com/alpha-picks/articles/123-investment-update",
        "title": "Investment update", "published_date": "2026-09-01", "comments_count": 2,
        "comments_count_observed_at": "2026-09-25T00:00:00Z",
    }], mode="quick")
    assert result["need_content"] == []
    assert [item["article_id"] for item in result["need_comments"]] == ["123"]
