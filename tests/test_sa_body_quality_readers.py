"""Stored body evidence is not automatically usable or complete article text."""

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from types import SimpleNamespace

import pytest

from src import sa_article_reconciliation_store as reconciliation
from src import sa_capture_store as store
from src.sa.article_associations import pick_articles
from src.sa.article_reader import read_article
from src.sa.comment_signals import RULE_SET_VERSION
from src.tools import sa_digest_tools, sa_tools


TITLE = "Quarterly operating review"
DISCLOSURE = (
    "Analyst's Disclosure: I/we have no stock, option or similar derivative "
    "position in any of the companies mentioned, and no plans to initiate "
    "any such positions within the next 72 hours."
)
COMMENT_UI = (
    "## Comments (2)\n\nSort by Newest\n\nSort replies\n\nReader One\n\n"
    "Stock Buy: ACME is my new position.\n\nLike\nReply\n"
)
METADATA = f"# {TITLE}\n\nAuthor: Alpha Picks"
PROSE = "Operating cash flow rose as customer demand improved."
COMMENT = "Independent reader opinion about ACME valuation."
INVALID_BODIES = [DISCLOSURE, COMMENT_UI, METADATA]


@pytest.fixture
def capture(tmp_path, monkeypatch):
    path = tmp_path / "sa.db"
    stamp = store.now_ts()
    with closing(store.connect(str(path))) as conn:
        conn.execute(
            "INSERT INTO sa_pick_lineages(lineage_id,symbol_key,picked_date,created_at) "
            "VALUES(1,'ACME',?,?)", (stamp[:10], stamp),
        )
        conn.execute(
            "INSERT INTO sa_alpha_picks(lineage_id,symbol,company,picked_date,portfolio_status) "
            "VALUES(1,'ACME','Acme Corporation',?,'current')", (stamp[:10],),
        )
        conn.execute(
            "INSERT INTO sa_articles(article_id,url,title,ticker,list_ticker,published_date,"
            "detail_fetched_at,comments_fetched_at,comments_count,"
            "provider_comments_count_at_last_scan,comment_recovery_state) "
            "VALUES('123','https://seekingalpha.com/alpha-picks/articles/123-review',"
            "?,'ACME','ACME',?,?,?,1,1,'repaired')", (TITLE, stamp[:10], stamp, stamp),
        )
        comment_id = conn.execute(
            "INSERT INTO sa_article_comments(article_id,comment_id,commenter,comment_text,"
            "comment_date) VALUES('123','c1','Reader',?,?)", (COMMENT, stamp),
        ).lastrowid
        conn.execute(
            "INSERT INTO sa_comment_signals(comment_row_id,article_id,comment_id,"
            "high_value_score,rule_set_version,extracted_at) VALUES(?,'123','c1',8.0,?,?)",
            (comment_id, RULE_SET_VERSION, stamp),
        )
        conn.execute(
            "INSERT INTO sa_signal_ticker_mentions(comment_row_id,ticker) VALUES(?,'ACME')",
            (comment_id,),
        )
        conn.commit()
    monkeypatch.setattr(sa_tools, "_is_sa_enabled", lambda: True)
    monkeypatch.setattr(sa_digest_tools, "_is_sa_enabled", lambda: True)
    return path


def _set_body(path, body):
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("UPDATE sa_articles SET body_markdown=? WHERE article_id='123'", (body,))
        conn.commit()


def _dal(path):
    return SimpleNamespace(_backend=SimpleNamespace(_sa_db=str(path)))


@pytest.mark.parametrize("body", INVALID_BODIES, ids=["disclosure", "comments", "metadata"])
def test_invalid_body_is_hidden_before_pagination_and_hashing_but_comments_survive(capture, body):
    _set_body(capture, body)
    result = sa_tools.get_sa_article_detail(_dal(capture), "123", body_limit=7)

    assert result["status"] == "ok"
    assert result["body_markdown"] == ""
    assert result["body_sha256"] == hashlib.sha256(b"").hexdigest()
    assert result["pagination"]["total_body_characters"] == 0
    assert result["pagination"]["next_body_offset"] is None
    quality = result["coverage"]["body"]
    assert quality["status"] == "unusable"
    assert quality["reason_code"].startswith("sa_article_body_")
    assert quality["completeness"] == "not_verified"
    assert quality["assessment_version"] == 1
    assert result["comments"][0]["comment_text"] == COMMENT
    assert result["coverage"]["comments"]["status"] == "captured"
    assert result["coverage"]["comments"]["complete"] is None
    next_body = read_article(capture, "123", body_offset=1, snapshot_id=result["snapshot_id"])
    assert next_body["error_code"] == "sa_article_offset_out_of_range"
    comment = read_article(capture, "123", body_limit=0, comment_id="c1",
                           snapshot_id=result["snapshot_id"])
    assert comment["comments"][0]["comment_text"] == COMMENT


@pytest.mark.parametrize("body", [None, "", " \n\t"])
def test_absent_body_keeps_comments_and_is_not_captured(capture, body):
    _set_body(capture, body)
    result = read_article(capture, "123")
    assert result["body_markdown"] == ""
    assert result["coverage"]["body"]["status"] == "not_captured"
    assert result["coverage"]["body"]["completeness"] == "not_verified"
    assert result["comments"][0]["comment_text"] == COMMENT


@pytest.mark.parametrize("body", INVALID_BODIES, ids=["disclosure", "comments", "metadata"])
@pytest.mark.parametrize("surface", ["feed", "digest", "pick", "reconciliation"])
def test_read_surfaces_do_not_serve_invalid_prose(capture, body, surface):
    _set_body(capture, body)
    with closing(store.connect(str(capture), read_only=True)) as conn:
        before = list(conn.iterdump())

        if surface == "feed":
            feed = sa_tools.get_sa_feed(_dal(capture), ticker="ACME", item_type="article")
            assert feed["total"] == 1
            item = feed["items"][0]
            assert item["snippet"] == ""
            assert item["has_detail"] is True
            assert item["has_content"] is False
            assert item["body_quality"]["status"] == "unusable"
            assert item["stored_comments_count"] == 1
            assert item["detail_route"] == "/sa/articles/123"
            assert item["comments_count"] == 1
            assert "body_markdown" not in item
        elif surface == "digest":
            digest = sa_digest_tools.get_sa_digest(_dal(capture), "ACME")
            assert digest["data_quality"]["errors"] == []
            assert digest["recent_articles"][0]["summary_excerpt"] == TITLE
            assert digest["high_value_comments"]["ticker_mentions"][0]["preview"] == COMMENT
            assert any("body_markdown unavailable for 1 of 1" in note
                       for note in digest["data_quality"]["missing"])
        elif surface == "pick":
            article = pick_articles(conn, 1, "ACME")["related"][0]
            assert article["has_content"] is False
            assert "body_markdown" not in article
        else:
            candidate = reconciliation.list_review_queue(conn, limit=20)["events"][0]["candidates"][0]
            assert candidate["content_state"] == "unusable"
            assert "role_entry_strong" not in candidate["evidence_codes"]
            evidence = reconciliation._article_evidence(conn.execute("SELECT * FROM sa_articles").fetchone())
            assert evidence.body_markdown == ""
            assert evidence.has_content is False
        assert list(conn.iterdump()) == before


@pytest.mark.parametrize("body", [PROSE, PROSE + "\n\n" + DISCLOSURE,
                                  (DISCLOSURE + "\n\n") * 8 + PROSE],
                         ids=["short-prose", "prose-and-disclosure", "prose-after-long-disclosure"])
def test_full_body_is_assessed_before_slicing_and_observed_prose_is_not_certified(capture, body):
    _set_body(capture, body)
    page = read_article(capture, "123", body_limit=7, comment_limit=0)
    quality = page["coverage"]["body"]
    assert quality["status"] == "available"
    assert quality["reason_code"] is None
    assert quality["completeness"] == "not_verified"
    assert page["body_sha256"] == hashlib.sha256(body.encode()).hexdigest()
    assert page["pagination"]["total_body_characters"] == len(body)
    pieces = [page["body_markdown"]]
    while page["pagination"]["next_body_offset"] is not None:
        page = read_article(capture, "123", body_limit=200, comment_limit=0,
                            body_offset=page["pagination"]["next_body_offset"],
                            snapshot_id=page["snapshot_id"])
        pieces.append(page["body_markdown"])
    assert "".join(pieces) == body

    feed = sa_tools.get_sa_feed(_dal(capture), ticker="ACME", item_type="article")
    assert feed["items"][0]["has_detail"] is True
    assert feed["items"][0]["has_content"] is True
    assert feed["items"][0]["body_quality"]["completeness"] == "not_verified"
    assert feed["items"][0]["detail_route"] == "/sa/articles/123"
    rows = sa_digest_tools._query_articles_local(
        str(capture), "ACME", datetime(2020, 1, 1, tzinfo=timezone.utc), 5,
    )
    assert rows[0]["body_missing"] is False
    assert rows[0]["summary_excerpt"] == body[:sa_digest_tools.EXCERPT_LEN]
    assert "body_markdown" not in rows[0]
    with closing(store.connect(str(capture), read_only=True)) as conn:
        article = pick_articles(conn, 1, "ACME")["related"][0]
        assert article["has_content"] is True
        assert "body_markdown" not in article
        candidate = reconciliation.list_review_queue(conn, limit=20)["events"][0]["candidates"][0]
        assert candidate["content_state"] == "available"


def test_snapshot_uses_projected_body_not_hidden_raw_disclosure(capture):
    _set_body(capture, DISCLOSURE)
    first = read_article(capture, "123")
    _set_body(capture, DISCLOSURE.replace("72 hours", "48 hours"))
    again = read_article(capture, "123", snapshot_id=first["snapshot_id"])
    assert again["status"] == "ok"
    assert again["snapshot_id"] == first["snapshot_id"]
    _set_body(capture, PROSE)
    changed = read_article(capture, "123", snapshot_id=first["snapshot_id"])
    assert changed["error_code"] == "sa_article_snapshot_changed"


@pytest.mark.parametrize("body", INVALID_BODIES, ids=["disclosure", "comments", "metadata"])
def test_accept_link_does_not_copy_invalid_body_into_pick_report(capture, body):
    _set_body(capture, body)
    with closing(store.connect(str(capture))) as conn:
        picked_date = conn.execute("SELECT picked_date FROM sa_pick_lineages").fetchone()[0]
        result = reconciliation.accept_link(
            conn, lineage_id=1, role="entry", event_anchor_date=picked_date,
            article_id="123", link_source="user", evidence_codes=["user_selected"],
        )
        assert result["status"] == "ok"
        pick = conn.execute("SELECT * FROM sa_alpha_picks").fetchone()
        assert pick["canonical_article_id"] == "123"
        assert pick["detail_report"] is None
        assert conn.execute("SELECT body_markdown FROM sa_articles").fetchone()[0] == body


def test_text_search_discloses_raw_evidence_matching_without_exposing_invalid_body(capture):
    _set_body(capture, COMMENT_UI)
    feed = sa_tools.get_sa_feed(_dal(capture), q="position", item_type="article")
    assert feed["total"] == 1
    assert feed["items"][0]["snippet"] == ""
    assert feed["items"][0]["has_content"] is False
    assert "article_text_search_matches_raw_capture" in feed["limitations"]


@pytest.mark.parametrize("body,status", [(None, "not_captured"), (COMMENT_UI, "unusable")])
@pytest.mark.parametrize("stored_comments", [False, True])
def test_feed_detail_route_uses_stored_comments_not_provider_count(capture, body, status, stored_comments):
    _set_body(capture, body)
    with closing(sqlite3.connect(capture)) as conn:
        conn.execute("UPDATE sa_articles SET comments_count=?", (0 if stored_comments else 999,))
        if not stored_comments:
            conn.execute("DELETE FROM sa_article_comments")
        conn.commit()
    item = sa_tools.get_sa_feed(_dal(capture), ticker="ACME", item_type="article")["items"][0]
    assert item["has_detail"] is stored_comments
    assert item["stored_comments_count"] == int(stored_comments)
    assert item["detail_route"] == ("/sa/articles/123" if stored_comments else None)
    assert item["has_content"] is False
    assert item["body_quality"]["status"] == status
    assert item["snippet"] == ""
    if stored_comments:
        detail = sa_tools.get_sa_article_detail(_dal(capture), item["id"])
        assert detail["comments"][0]["comment_text"] == COMMENT
        assert detail["body_markdown"] == ""


@pytest.mark.parametrize("state,label", [("available", "Article text"),
                                        ("complete", "Article text"),
                                        ("missing", "Body unavailable"),
                                        ("unusable", "Body unavailable")])
def test_reconciliation_ui_does_not_claim_full_text_even_for_legacy_complete(state, label):
    from tests.test_sa_extension_reconciliation_ui import _EVENT, _run_ui

    text = _run_ui(f"""
        const event = {_EVENT};
        event.candidates[0].content_state = {json.dumps(state)};
        const container = document.createElement("section");
        ArkScopeReconciliationUI.renderQueue(container, {{events: [event], total: 1}}, {{}});
        return container.querySelector(".reconciliation-content-state").textContent;
    """)
    assert text == label
    assert "Full text" not in text
