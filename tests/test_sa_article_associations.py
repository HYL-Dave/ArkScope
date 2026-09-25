"""Association reads must retain event roles without guessing from body text."""

from datetime import datetime, timezone
import asyncio
import json

import pytest

from src import sa_capture_store as store
from src.sa.article_reader import read_article
from src.tools.backends.sa_capture_backend import SACaptureBackend
from src.tools.sa_digest_tools import _query_articles_local
from src.tools.sa_tools import _sa_feed_local
from src.tools import sa_digest_tools
from types import SimpleNamespace


@pytest.fixture
def capture(tmp_path):
    path = tmp_path / "sa_capture.db"
    conn = store.connect(str(path))
    conn.executemany(
        "INSERT INTO sa_pick_lineages(lineage_id,symbol_key,picked_date,created_at) VALUES(?,?,?,?)",
        [(1, "B", "2026-07-01", "2026-07-01"),
         (2, "B", "2026-07-15", "2026-07-15"),
         (3, "A", "2026-07-01", "2026-07-01")],
    )
    conn.executemany(
        "INSERT INTO sa_alpha_picks(lineage_id,symbol,company,picked_date,closed_date,portfolio_status) "
        "VALUES(?,?,?,?,?,'closed')",
        [(1, "B", "B company", "2026-07-01", "2026-08-01"),
         (2, "B", "B company", "2026-07-15", "2026-08-05"),
         (3, "A", "A company", "2026-07-01", "2026-08-05")],
    )
    for aid, ticker, listed, detail, date in [
        ("buy", "B", "B", None, "2026-07-01"),
        ("sell", None, None, None, "2026-08-01"),
        ("shared", "A", "A", None, "2026-08-05"),
        ("related", "B", "B", None, "2026-08-02"),
        ("prefix", "BA", "BA", None, "2026-08-02"),
        ("text", "X", "X", None, "2026-08-02"),
        ("revoked", None, None, None, "2026-08-03"),
        ("conflict", "B", "B", "BA", "2026-08-02"),
        ("legacy", "B", None, None, "2026-08-02"),
    ]:
        conn.execute(
            "INSERT INTO sa_articles(article_id,url,title,ticker,list_ticker,detail_ticker,"
            "published_date,body_markdown,article_type) VALUES(?,?,?,?,?,?,?,?,'analysis')",
            (aid, f"https://seekingalpha.com/article/{aid}", f"B rebound: {aid}", ticker,
             listed, detail, date, "Body text mentions B and does not establish an association."),
        )
    conn.executemany(
        "INSERT INTO sa_pick_article_links(link_id,lineage_id,article_id,role,event_anchor_date,"
        "link_source,evidence_codes,linked_at,revoked_at) VALUES(?,?,?,?,?,?,?,?,?)",
        [(10, 1, "buy", "entry", "2026-07-01", "auto", '["ticker_list_exact","role_entry_strong"]', "2026-08-10", None),
         (11, 1, "sell", "exit", "2026-08-01", "user", '["user_selected"]', "2026-08-10", None),
         (12, 2, "shared", "exit", "2026-08-05", "auto", '["ticker_text_symbol","role_exit_strong"]', "2026-08-10", None),
         (13, 3, "shared", "exit", "2026-08-05", "auto", '["ticker_text_symbol","role_exit_strong"]', "2026-08-10", None),
         (14, 1, "revoked", "exit", "2026-08-03", "user", '["user_selected"]', "2026-08-10", "2026-08-11")],
    )
    conn.commit()
    conn.close()
    return SACaptureBackend(sa_db=str(path), market_db=str(tmp_path / "market.db"))


def _feed(capture, **kwargs):
    return _sa_feed_local(capture._sa_db, q=None, ticker="B", item_type="article",
                          days=3650, limit=200, offset=0, **kwargs)


def test_all_article_read_paths_find_exact_associations_once(capture):
    expected = {"buy", "sell", "shared", "related", "legacy"}
    queries = [
        capture.query_sa_articles(ticker="b", limit=200),
        _feed(capture)["items"],
        _query_articles_local(capture._sa_db, "B", datetime(2020, 1, 1, tzinfo=timezone.utc), 200),
    ]
    for rows in queries:
        ids = [r.get("article_id", r.get("id")) for r in rows]
        assert set(ids) == expected
        assert len(ids) == len(expected)


def test_entry_exit_and_related_provenance_is_not_flattened(capture):
    rows = {r["article_id"]: r for r in capture.query_sa_articles(ticker="B", limit=200)}
    buy = next(a for a in rows["buy"]["associations"] if a["role"] == "entry")
    assert (buy["symbol"], buy["picked_date"], buy["event_anchor_date"], buy["link_source"]) == (
        "B", "2026-07-01", "2026-07-01", "auto")
    sell = rows["sell"]["associations"][0]
    assert (sell["role"], sell["event_anchor_date"], sell["link_source"], sell["evidence_codes"]) == (
        "exit", "2026-08-01", "user", ["user_selected"])
    assert rows["related"]["associations"] == [{
        "symbol": "B", "role": "related", "link_source": "provider",
        "evidence_codes": ["ticker_list_exact"], "picked_date": None,
        "event_anchor_date": None, "link_id": None,
    }]
    assert rows["legacy"]["associations"][0]["link_source"] == "legacy"
    shared = next(r for r in _feed(capture)["items"] if r["id"] == "shared")
    assert shared["tickers"] == ["A", "B"]
    assert {(a["symbol"], a["role"]) for a in shared["associations"]} == {
        ("A", "exit"), ("B", "exit")}


def test_pick_detail_keeps_entry_and_exit_for_the_requested_investment(capture):
    detail = capture.get_sa_pick_detail("B", "2026-07-01")
    assert [a["article_id"] for a in detail["articles"]["entry"]] == ["buy"]
    assert [a["article_id"] for a in detail["articles"]["exit"]] == ["sell"]
    assert {a["article_id"] for a in detail["articles"]["related"]} == {"related", "legacy"}
    assert "shared" not in json.dumps(detail["articles"])
    second = capture.get_sa_pick_detail("B", "2026-07-15")
    assert second["articles"]["entry"] == []
    assert [a["article_id"] for a in second["articles"]["exit"]] == ["shared"]


@pytest.mark.parametrize("q", ["B", "b", "$B"])
def test_known_symbol_search_is_association_lookup_not_substring(capture, q):
    result = _sa_feed_local(capture._sa_db, q=q, ticker=None, item_type=None,
                            days=3650, limit=200, offset=0)
    assert result["query_mode"] == "ticker"
    assert result["resolved_ticker"] == "B"
    assert {r["id"] for r in result["items"]} == {"buy", "sell", "shared", "related", "legacy"}
    assert result["total"] == 5
    assert sum(result["by_type"].values()) == sum(result["by_day"].values()) == 5


def test_explicit_phrase_remains_text_search_even_for_known_symbol(capture):
    result = _sa_feed_local(capture._sa_db, q='"B"', ticker=None, item_type="article",
                            days=3650, limit=200, offset=0)
    assert result["query_mode"] == "text"
    assert result["resolved_ticker"] is None
    assert "text" in {r["id"] for r in result["items"]}


def test_explicit_ticker_plus_keyword_remains_an_intersection(capture):
    result = _sa_feed_local(capture._sa_db, q="shared", ticker="B", item_type="article",
                            days=3650, limit=200, offset=0)
    assert [r["id"] for r in result["items"]] == ["shared"]


def test_detail_has_same_associations_and_snapshot_detects_changed_links(capture):
    result = read_article(capture._sa_db, "sell")
    assert result["status"] == "ok"
    assert result["associations"][0]["role"] == "exit"
    assert result["associations"][0]["link_source"] == "user"
    conn = store.connect(capture._sa_db)
    conn.execute("UPDATE sa_pick_article_links SET revoked_at='2026-08-12' WHERE link_id=11")
    conn.commit()
    conn.close()
    changed = read_article(capture._sa_db, "sell", snapshot_id=result["snapshot_id"])
    assert changed["error_code"] == "sa_article_snapshot_changed"


def test_reads_leave_all_capture_facts_and_link_decisions_unchanged(capture):
    conn = store.connect(capture._sa_db, read_only=True)
    before = list(conn.iterdump())
    capture.query_sa_articles(ticker="B", limit=200)
    _feed(capture)
    _query_articles_local(capture._sa_db, "B", datetime(2020, 1, 1, tzinfo=timezone.utc), 200)
    capture.get_sa_pick_detail("B", "2026-07-01")
    read_article(capture._sa_db, "sell")
    assert list(conn.iterdump()) == before
    conn.close()


def test_public_digest_preserves_role_and_source_in_normalization(capture, monkeypatch):
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 1, tzinfo=timezone.utc)

    monkeypatch.setattr(sa_digest_tools, "datetime", FrozenDatetime)
    monkeypatch.setattr(sa_digest_tools, "_is_sa_enabled", lambda: True)
    result = sa_digest_tools.get_sa_digest(SimpleNamespace(_backend=capture), "B", days=90)
    sell = next(a for a in result["recent_articles"] if a["article_id"] == "sell")
    assert sell["associations"][0]["role"] == "exit"
    assert sell["associations"][0]["link_source"] == "user"


def test_query_rows_and_associations_share_one_read_snapshot(capture, monkeypatch):
    conn = store.connect(capture._sa_db, read_only=True)
    fired = False

    def change_link(sql):
        nonlocal fired
        if "SELECT * FROM article_associations" in sql and not fired:
            fired = True
            writer = store.connect(capture._sa_db)
            writer.execute("UPDATE sa_pick_article_links SET revoked_at='2026-08-12' WHERE link_id=11")
            writer.commit()
            writer.close()

    conn.set_trace_callback(change_link)
    monkeypatch.setattr(capture, "_sa_read", lambda: conn)
    rows = capture.query_sa_articles(ticker="B", limit=200)
    assert fired
    sell = next(row for row in rows if row["article_id"] == "sell")
    assert sell["associations"][0]["link_id"] == 11


@pytest.mark.parametrize("channel", ["openai", "anthropic"])
def test_api_channels_keep_pick_entry_exit_and_link_evidence(capture, channel, monkeypatch):
    from src.tools import sa_tools
    from tests.test_freshness_tool_channels import invoke
    from tests.test_sec_research_tool_adapters import unwrap

    monkeypatch.setattr(sa_tools, "_is_sa_enabled", lambda: True)
    dal = SimpleNamespace(_backend=capture, get_sa_pick_detail=capture.get_sa_pick_detail,
                          get_sa_articles=capture.query_sa_articles)
    pick = unwrap(asyncio.run(invoke(channel, "get_sa_pick_detail",
        {"symbol": "B", "picked_date": "2026-07-01"}, dal)))
    assert [a["article_id"] for a in pick["articles"]["entry"]] == ["buy"]
    assert [a["article_id"] for a in pick["articles"]["exit"]] == ["sell"]
    assert pick["articles"]["exit"][0]["associations"][0]["evidence_codes"] == ["user_selected"]
    articles = unwrap(asyncio.run(invoke(channel, "get_sa_articles", {"ticker": "B"}, dal)))
    assert {a["article_id"] for a in articles["articles"]} == {"buy", "sell", "shared", "related", "legacy"}


@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
def test_all_channels_can_follow_event_evidence_from_feed_to_article(capture, channel, monkeypatch):
    from src.tools import sa_tools
    from tests.test_freshness_tool_channels import invoke
    from tests.test_sec_research_tool_adapters import unwrap

    monkeypatch.setattr(sa_tools, "_is_sa_enabled", lambda: True)
    dal = SimpleNamespace(_backend=capture)
    feed = unwrap(asyncio.run(invoke(channel, "get_sa_feed",
        {"q": "B", "days": 3650, "item_type": "article"}, dal)))
    assert feed["query_mode"] == "ticker"
    assert {a["id"] for a in feed["items"]} == {"buy", "sell", "shared", "related", "legacy"}
    sell = next(a for a in feed["items"] if a["id"] == "sell")
    detail = unwrap(asyncio.run(invoke(channel, "get_sa_article_detail",
        {"article_id": sell["id"]}, dal)))
    assert detail["associations"] == sell["associations"]
    assert detail["associations"][0]["role"] == "exit"
    assert detail["associations"][0]["link_source"] == "user"


def test_known_symbol_q_uses_news_membership_not_title_mentions(capture):
    conn = store.connect(capture._sa_db)
    conn.executemany(
        "INSERT INTO sa_market_news(id,news_id,url,title,published_at) VALUES(?,?,?,?,?)",
        [(1, "associated", "https://seekingalpha.com/news/1", "Company results", "2026-08-01T00:00:00Z"),
         (2, "substring", "https://seekingalpha.com/news/2", "B stock rebound", "2026-08-01T00:00:00Z")],
    )
    conn.executemany("INSERT INTO sa_market_news_tickers(news_row_id,ticker) VALUES(?,?)", [(1,"B"),(2,"BA")])
    conn.commit()
    conn.close()
    result = _sa_feed_local(capture._sa_db, q="B", ticker=None, item_type="market_news",
                            days=3650, limit=200, offset=0)
    assert [a["id"] for a in result["items"]] == ["associated"]
    assert result["total"] == 1


@pytest.mark.parametrize("query", ["articles", "pick", "article_detail"])
def test_missing_association_schema_is_unavailable_not_empty(capture, monkeypatch, query):
    from src.tools import sa_tools
    from src.api.routes.seeking_alpha import _unwrap_sa_result
    from fastapi import HTTPException

    conn = store.connect(capture._sa_db)
    conn.execute("DROP TABLE sa_pick_article_links")
    conn.commit()
    conn.close()
    monkeypatch.setattr(sa_tools, "_is_sa_enabled", lambda: True)
    dal = SimpleNamespace(_backend=capture, get_sa_pick_detail=capture.get_sa_pick_detail,
                          get_sa_articles=capture.query_sa_articles,
                          get_sa_portfolio=lambda **_: [{"picked_date": "2026-07-01"}])
    if query == "articles":
        result = sa_tools.get_sa_articles(dal, ticker="B")
    elif query == "pick":
        result = sa_tools.get_sa_pick_detail(dal, "B", "2026-07-01")
    else:
        result = sa_tools.get_sa_article_detail(dal, "buy")
    assert result["status"] == "unavailable"
    assert result["error_code"] == "sa_article_associations_unavailable"
    assert "hint" not in result and "articles" not in result
    with pytest.raises(HTTPException) as error:
        _unwrap_sa_result(result)
    assert error.value.status_code == 503


def test_legacy_article_detail_does_not_hide_missing_associations(capture):
    from src.tools.retained_read_results import RetainedReadFailure

    conn = store.connect(capture._sa_db)
    conn.execute("DROP TABLE sa_pick_article_links")
    conn.commit()
    conn.close()
    with pytest.raises(RetainedReadFailure) as error:
        capture.get_sa_article_with_comments("buy")
    assert error.value.code == "sa_article_associations_unavailable"


def test_v1_pick_store_is_unavailable_without_migration_or_closed_pick_hint(tmp_path, monkeypatch):
    from tests.test_sa_article_reconciliation_schema import _create_v1
    from src.tools import sa_tools
    from src.api.routes.seeking_alpha import _unwrap_sa_result
    from fastapi import HTTPException

    path = tmp_path / "v1.db"
    _create_v1(path)
    before = path.read_bytes()
    backend = object.__new__(SACaptureBackend)
    backend._sa_db = path
    dal = SimpleNamespace(get_sa_pick_detail=backend.get_sa_pick_detail,
                          get_sa_portfolio=lambda **_: [{"picked_date": "2024-03-15"}])
    monkeypatch.setattr(sa_tools, "_is_sa_enabled", lambda: True)
    result = sa_tools.get_sa_pick_detail(dal, "RCL", "2024-03-15")
    assert result == {"status": "unavailable", "error_code": "sa_article_associations_unavailable"}
    with pytest.raises(HTTPException) as error:
        _unwrap_sa_result(result)
    assert error.value.status_code == 503
    assert path.read_bytes() == before


def test_pick_related_articles_are_paged_without_hiding_event_links(capture):
    conn = store.connect(capture._sa_db)
    conn.executemany(
        "INSERT INTO sa_articles(article_id,url,title,ticker,list_ticker,published_date) VALUES(?,?,?,'B','B','2026-08-04')",
        [(f"r-{i:04d}", f"https://seekingalpha.com/article/r-{i}", f"Related {i}") for i in range(1000)],
    )
    conn.commit()
    conn.close()
    first = capture.get_sa_pick_detail("B", "2026-07-01")
    assert len(first["articles"]["related"]) == 20
    assert first["articles"]["related_pagination"] == {
        "offset": 0, "limit": 20, "total": 1002, "next_offset": 20,
    }
    assert len(json.dumps(first).encode()) < 20000
    second = capture.get_sa_pick_detail("B", "2026-07-01", related_offset=20)
    assert not ({a["article_id"] for a in first["articles"]["related"]}
                & {a["article_id"] for a in second["articles"]["related"]})
    for detail in (first, second):
        assert [a["article_id"] for a in detail["articles"]["entry"]] == ["buy"]
        assert [a["article_id"] for a in detail["articles"]["exit"]] == ["sell"]


def test_pick_detail_retains_other_symbols_evidence_and_identifies_its_match(capture):
    detail = capture.get_sa_pick_detail("B", "2026-07-15")
    shared = detail["articles"]["exit"][0]
    assert shared["tickers"] == ["A", "B"]
    assert {(a["symbol"], a["link_id"]) for a in shared["associations"]} == {("A", 13), ("B", 12)}
    assert shared["matching_link_ids"] == [12]


@pytest.mark.parametrize("channel", ["openai", "anthropic"])
def test_related_offset_survives_api_adapters(capture, channel, monkeypatch):
    from src.tools import sa_tools
    from tests.test_freshness_tool_channels import invoke
    from tests.test_sec_research_tool_adapters import unwrap

    monkeypatch.setattr(sa_tools, "_is_sa_enabled", lambda: True)
    dal = SimpleNamespace(_backend=capture, get_sa_pick_detail=capture.get_sa_pick_detail)
    result = unwrap(asyncio.run(invoke(channel, "get_sa_pick_detail",
        {"symbol": "B", "picked_date": "2026-07-01", "related_offset": 1}, dal)))
    assert result["articles"]["related_pagination"] == {"offset": 1, "limit": 20, "total": 2, "next_offset": None}
    assert [a["article_id"] for a in result["articles"]["related"]] == ["legacy"]
    assert [a["article_id"] for a in result["articles"]["exit"]] == ["sell"]


@pytest.mark.parametrize("offset", [-1, True, 0.5, "1", 2**63])
def test_invalid_related_offset_is_explicit_not_missing_pick(capture, monkeypatch, offset):
    from src.tools import sa_tools
    monkeypatch.setattr(sa_tools, "_is_sa_enabled", lambda: True)
    result = sa_tools.get_sa_pick_detail(object(), "B", "2026-07-01", related_offset=offset)
    assert result == {"status": "invalid_request", "error_code": "sa_pick_related_offset_invalid"}
