from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "extensions" / "sa_alpha_picks"
FIXTURES = ROOT / "tests" / "fixtures" / "sa_alpha_picks"
RUNNER = ROOT / "tests" / "js" / "run_sa_extension_fixture.mjs"
IDENTITY = EXTENSION / "article_identity.js"
LIST_SCRAPER = EXTENSION / "scrape_articles_list.js"
DETAIL_SCRAPER = EXTENSION / "scrape_detail.js"


def _run_fixture(fixture: Path, *scripts: Path):
    completed = subprocess.run(
        ["node", str(RUNNER), str(fixture), *(str(path) for path in scripts)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _run_probe(tmp_path: Path, fixture: Path, expression: str):
    probe = tmp_path / "probe.js"
    probe.write_text(expression, encoding="utf-8")
    return _run_fixture(fixture, IDENTITY, probe)


def test_btsg_real_list_fixture_extracts_ticker_after_optional_time_and_separator():
    payload = _run_fixture(
        FIXTURES / "btsg_articles_list_card.html",
        IDENTITY,
        LIST_SCRAPER,
    )
    assert len(payload) == 1
    assert payload[0]["article_id"] == "6316639"
    assert payload[0]["url"].startswith(
        "https://seekingalpha.com/alpha-picks/articles/6316639"
    )
    assert payload[0]["title"] == (
        "Stock Buy: Top Health Care Services Stock Delivers Double-Digit Growth"
    )
    assert payload[0]["ticker"] == payload[0]["list_ticker"] == "BTSG"
    assert payload[0]["date"] == "Jul 15, 2026"
    assert payload[0]["comments_count"] == 265
    assert payload[0]["article_type"] == "analysis"
    assert payload[0]["list_ticker_observed_at"].endswith("Z")


def test_btsg_list_fixture_keeps_date_comments_and_article_id_intact():
    payload = _run_fixture(
        FIXTURES / "btsg_articles_list_card.html", IDENTITY, LIST_SCRAPER
    )[0]
    assert payload["article_id"] == "6316639"
    assert payload["date"] == "Jul 15, 2026"
    assert payload["comments_count"] == 265
    assert payload["list_ticker"] == "BTSG"


def test_list_ticker_bearing_node_wins_over_normalized_text_fallback(tmp_path):
    fixture = tmp_path / "explicit-wins.html"
    fixture.write_text(
        """<article><h3><a href='/alpha-picks/articles/1-test'>A sufficiently long article title</a></h3>
        <span>Jul 15, 2026, 12:00 PM</span><a data-test-id='post-list-ticker'
        href='/symbol/BTSG'>BTSG</a><span>WRONG</span><a>3 Comments</a></article>""",
        encoding="utf-8",
    )
    payload = _run_fixture(fixture, IDENTITY, LIST_SCRAPER)
    assert payload[0]["list_ticker"] == "BTSG"


def test_list_parser_does_not_scan_unrelated_uppercase_page_text(tmp_path):
    fixture = tmp_path / "scoped.html"
    fixture.write_text(
        """<div data-test-id='post-list-ticker'>WRONG</div>
        <article><h3><a href='/alpha-picks/articles/2-test'>Another sufficiently long article title</a></h3>
        <span>Jul 15, 2026, 12:00 PM</span><a>3 Comments</a></article>""",
        encoding="utf-8",
    )
    payload = _run_fixture(fixture, IDENTITY, LIST_SCRAPER)
    assert payload[0]["list_ticker"] is None


def test_btsg_real_detail_fixture_extracts_security_header_ticker(tmp_path):
    payload = _run_probe(
        tmp_path,
        FIXTURES / "btsg_article_detail_header.html",
        "ArkScopeArticleIdentity.extractDetailTicker(document, document.querySelector('h1'))",
    )
    assert payload == "BTSG"


def test_detail_ticker_is_independent_of_generic_title_and_absent_body_mention(tmp_path):
    fixture = FIXTURES / "btsg_article_detail_header.html"
    payload = _run_probe(
        tmp_path,
        fixture,
        "({ticker: ArkScopeArticleIdentity.extractDetailTicker(document, document.querySelector('h1')), "
        "title: document.querySelector('h1').textContent, body: document.body.textContent})",
    )
    assert "BTSG" not in payload["title"]
    assert "Business Overview" not in payload["body"]
    assert payload["ticker"] == "BTSG"


def test_unreviewed_relative_date_shape_returns_null_instead_of_guessing(tmp_path):
    fixture = tmp_path / "relative.html"
    fixture.write_text(
        """<article><h3><a href='/alpha-picks/articles/3-test'>A third sufficiently long article title</a></h3>
        <span>Today, 12:00 PM</span><span>BTSG</span><a>3 Comments</a></article>""",
        encoding="utf-8",
    )
    payload = _run_probe(
        tmp_path,
        fixture,
        "ArkScopeArticleIdentity.extractListTicker(document.querySelector('article'), 'Today')",
    )
    assert payload is None


def test_list_and_detail_scrapers_emit_distinct_observation_fields(tmp_path):
    list_payload = _run_fixture(
        FIXTURES / "btsg_articles_list_card.html", IDENTITY, LIST_SCRAPER
    )[0]
    detail_html = (FIXTURES / "btsg_article_detail_header.html").read_text(
        encoding="utf-8"
    ).replace(
        "</body>",
        "<main><p>" + ("Provider-captured article content. " * 20) + "</p></main></body>",
    )
    detail_fixture = tmp_path / "detail-with-body.html"
    detail_fixture.write_text(detail_html, encoding="utf-8")
    detail_payload = _run_fixture(detail_fixture, IDENTITY, DETAIL_SCRAPER)

    assert list_payload["list_ticker"] == "BTSG"
    assert "detail_ticker" not in list_payload
    assert detail_payload["detail_ticker"] == "BTSG"
    assert detail_payload["detail_ticker_observed_at"].endswith("Z")
    assert "list_ticker" not in detail_payload


def test_detail_scraper_prefers_provider_main_content_over_disclosure_article(tmp_path):
    fixture = tmp_path / "detail-main-content.html"
    fixture.write_text(
        """<!doctype html><html><body>
        <h1>Stock Buy: A Provider Title Without A Ticker</h1>
        <article><p>Analyst's Disclosure: no positions. """
        + ("Disclosure boilerplate. " * 30)
        + """</p></article>
        <div data-test-id="content-container">
          <h2>Business Overview</h2>
          <p>Provider-captured investment analysis. """
        + ("Fundamental operating evidence. " * 30)
        + """</p>
        </div>
        <div data-test-id="content-container">
          <p>Seeking Alpha's Disclosure: informational purposes only.</p>
        </div>
        </body></html>""",
        encoding="utf-8",
    )

    payload = _run_fixture(fixture, IDENTITY, DETAIL_SCRAPER)

    assert "Business Overview" in payload["body_markdown"]
    assert "Fundamental operating evidence" in payload["body_markdown"]
    assert "Analyst's Disclosure" not in payload["body_markdown"]
