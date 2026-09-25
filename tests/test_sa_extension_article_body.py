"""Synthetic body/comment layouts, not snapshots of the live acceptance page."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "extensions" / "sa_alpha_picks"
RUNNER = ROOT / "tests" / "js" / "run_sa_extension_fixture.mjs"
PARAGRAPHS = tuple(
    f"Article paragraph {i}: the operating evidence describes cash flows, "
    "capital investment and changes in customer demand."
    for i in range(10)
)
BODY = "<h2>Business Overview</h2>" + "".join(f"<p>{p}</p>" for p in PARAGRAPHS)
COMMENT_ROW = (
    '<div class="border-t-share-separator-thin"><div class="break-words">'
    + "Reader reply, not company analysis. " * 100
    + "</div></div>"
)
COMMENTS = (
    "<section><h3>COMMENTS (68)</h3><button>Sort replies</button>"
    + COMMENT_ROW
    + "</section>"
)
ANALYST_DISCLOSURE = (
    "I/we have no stock, option or similar derivative position in any of the "
    "companies mentioned, and no plans to initiate any such positions within "
    "the next 72 hours. I wrote this article myself, and it expresses my own opinions."
)
SA_DISCLOSURE = (
    "Past performance is no guarantee of future results. No recommendation or "
    "advice is being given as to whether any investment is suitable for a "
    "particular investor. Any views or opinions expressed above may not reflect "
    "those of Seeking Alpha as a whole."
)
DISCLOSURES = (
    "<p><strong>Analyst's Disclosure:</strong> " + ANALYST_DISCLOSURE + "</p>"
    "<p>Seeking Alpha's Disclosure: " + SA_DISCLOSURE + "</p>"
)
SHORT_PROSE = (
    "Revenue increased as customers renewed multi-year service contracts, while "
    "operating margins improved through lower distribution costs. Cash generated "
    "by operations covered capital spending and reduced net debt, leaving room "
    "to fund the next stage of expansion."
)
PROVIDER_SHORT_PROSE = (
    "Revenue grew as customers renewed annual contracts. Cash flow covered "
    "new equipment and left room to reduce outstanding debt."
)


def _scrape(tmp_path, html, *, news=False, after=None):
    fixture = tmp_path / "article.html"
    fixture.write_text(
        "<!doctype html><html><body><h1>Provider article</h1>" + html + "</body></html>",
        encoding="utf-8",
    )
    scripts = [EXTENSION / "article_identity.js", EXTENSION / "scrape_detail.js"]
    if after:
        probe = tmp_path / "after.js"
        probe.write_text(after, encoding="utf-8")
        scripts.append(probe)
    env = dict(os.environ)
    env["ARKSCOPE_FIXTURE_URL"] = (
        "https://seekingalpha.com/news/123456-provider-article"
        if news
        else "https://seekingalpha.com/alpha-picks/articles/123456-provider-article"
    )
    result = subprocess.run(
        ["node", str(RUNNER), str(fixture), *map(str, scripts)],
        cwd=ROOT, env=env, check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def _assert_article(payload):
    assert "error" not in payload, payload
    markdown = payload["body_markdown"]
    assert markdown.count("## Business Overview") == 1
    for paragraph in PARAGRAPHS:
        assert markdown.count(paragraph) == 1
    assert "Reader reply" not in markdown
    assert "COMMENTS (68)" not in markdown
    assert "Sort replies" not in markdown


@pytest.mark.parametrize("comments_first", [False, True])
@pytest.mark.parametrize(
    "comment_attributes",
    ['class="paywall-full-content"', 'data-test-id="content-container"'],
)
def test_larger_comment_container_cannot_outvote_article(
    tmp_path, comments_first, comment_attributes
):
    article = '<div data-test-id="content-container">' + BODY + "</div>"
    comments = f"<div {comment_attributes}>" + COMMENTS + "</div>"
    html = comments + article if comments_first else article + comments
    _assert_article(_scrape(tmp_path, html))


@pytest.mark.parametrize(
    "opening,closing",
    [
        ("<main>", "</main>"),
        ("<article>", "</article>"),
        ('<div class="paywall-full-content">', "</div>"),
        ('<div data-test-id="content-container">', "</div>"),
    ],
)
@pytest.mark.parametrize("clean_body_selector", [False, True])
def test_mixed_wrapper_keeps_article_and_excludes_comment_section(
    tmp_path, opening, closing, clean_body_selector
):
    attributes = ' data-testid="article-body"' if clean_body_selector else ""
    html = opening + f"<article{attributes}>" + BODY + "</article>" + COMMENTS + closing
    _assert_article(_scrape(tmp_path, html))


@pytest.mark.parametrize("nested_wrapper", ["main", "article", "section"])
def test_nested_structure_cannot_bypass_comment_exclusion(tmp_path, nested_wrapper):
    html = (
        '<div data-test-id="content-container">'
        + f"<{nested_wrapper}>" + BODY + COMMENTS + f"</{nested_wrapper}></div>"
    )
    _assert_article(_scrape(tmp_path, html))


@pytest.mark.parametrize(
    "html",
    [
        '<main><div class="paywall-full-content">' + COMMENTS + "</div></main>",
        '<main class="comments"><div data-test-id="article-body">' + BODY + "</div></main>",
        '<main><div class="border-t-share-separator-thin" data-test-id="content-container">'
        + BODY + "</div></main>",
        '<main><div class="border-t-share-separator-thin"><section><div id="content-body">'
        + BODY + "</div></section></div></main>",
        '<main><h3>COMMENTS (68)</h3><button>' + "Sort replies " * 100
        + "</button>" + COMMENT_ROW + "</main>",
    ],
    ids=["comments-only", "excluded-ancestor", "row-is-candidate", "inside-row", "long-controls"],
)
def test_comment_only_page_does_not_produce_an_article(tmp_path, html):
    payload = _scrape(tmp_path, html)
    assert payload.get("error"), payload
    assert not payload.get("body_markdown")


def test_comment_text_does_not_count_toward_body_threshold_or_ranking(tmp_path):
    html = (
        '<div data-test-id="content-container"><p>Short placeholder.</p>' + COMMENTS + "</div>"
        + '<div data-test-id="content-container">' + BODY + "</div>"
    )
    payload = _scrape(tmp_path, html)
    _assert_article(payload)
    assert "Short placeholder" not in payload["body_markdown"]


def test_comment_text_cannot_make_short_body_eligible(tmp_path):
    payload = _scrape(
        tmp_path, '<main><p>Short placeholder.</p>' + COMMENTS + "</main>"
    )
    assert payload.get("error"), payload
    assert not payload.get("body_markdown")


@pytest.mark.parametrize("wrapped", [False, True])
def test_row_anchored_group_does_not_consume_prose_on_either_side(tmp_path, wrapped):
    heading = "<h3>COMMENTS (68)</h3>"
    control = '<div role="button">' + "Sort replies " * 100 + "</div>"
    if wrapped:
        heading = "<div><section>" + heading + "</section></div>"
        control = "<section><div>" + control + "</div></section>"
    html = (
        '<main><div data-test-id="content-container">' + BODY
        + heading + control + COMMENT_ROW
        + "<p>Final independently retained operating evidence.</p></div></main>"
    )
    payload = _scrape(tmp_path, html)
    _assert_article(payload)
    assert payload["body_markdown"].count("Final independently retained operating evidence.") == 1


def test_unmarked_text_breaks_comment_heading_group(tmp_path):
    html = (
        '<main><h3>Comments</h3>' + BODY + COMMENTS
        + "<p>Concluding management comments remain article prose.</p></main>"
    )
    payload = _scrape(tmp_path, html)
    _assert_article(payload)
    assert "### Comments" in payload["body_markdown"]
    assert "Concluding management comments remain article prose." in payload["body_markdown"]


def test_unclassified_comment_ui_without_narrative_is_not_an_article(tmp_path):
    html = (
        '<div class="paywall-full-content"><h3>COMMENTS (68)</h3><span>'
        + "Unclassified interface wording. " * 100 + "</span>" + COMMENT_ROW + "</div>"
    )
    payload = _scrape(tmp_path, html)
    assert payload.get("error"), payload
    assert not payload.get("body_markdown")


def test_nested_candidate_cannot_escape_comment_only_context(tmp_path):
    html = (
        '<div class="paywall-full-content"><h3>COMMENTS (68)</h3>'
        '<div data-test-id="content-container"><span>'
        + "Unclassified interface wording. " * 100 + "</span></div>" + COMMENT_ROW + "</div>"
    )
    payload = _scrape(tmp_path, html)
    assert payload.get("error"), payload
    assert not payload.get("body_markdown")


@pytest.mark.parametrize("tag", ["main", "article", 'div data-test-id="content-container"'])
def test_unrelated_comment_section_does_not_disqualify_clean_div_only_body(tmp_path, tag):
    prose = "Independently bounded article prose. " * 20
    html = (
        '<div class="page-layout"><' + tag + "><div>" + prose
        + "</div></" + tag.split()[0] + ">" + COMMENTS + "</div>"
    )
    payload = _scrape(tmp_path, html)
    assert "error" not in payload, payload
    assert payload["body_markdown"] == prose.strip()


def test_html_comment_does_not_split_direct_prose(tmp_path):
    payload = _scrape(
        tmp_path, '<main>' + BODY + '<div>Opening<!-- marker --> continued.</div></main>'
    )
    assert "Opening continued." in payload["body_markdown"]


def test_block_styled_spans_keep_a_markdown_boundary(tmp_path):
    payload = _scrape(
        tmp_path, '<main>' + BODY + '<div><span style="display:block">First styled block</span>'
        '<span style="display:block">Second styled block</span></div></main>'
    )
    assert "First styled block\n\nSecond styled block" in payload["body_markdown"]


@pytest.mark.parametrize("css_class", ["no-sidebar", "commentary-layout"])
def test_incidental_class_substring_does_not_hide_clean_provider_body(tmp_path, css_class):
    html = (
        f'<div class="{css_class}"><div data-test-id="content-container">'
        + BODY + COMMENTS + "</div></div>"
    )
    _assert_article(_scrape(tmp_path, html))


@pytest.mark.parametrize("wrapper", ["main", "article", "div"])
def test_direct_and_inline_prose_survives_recursive_wrapper(tmp_path, wrapper):
    html = (
        '<div data-test-id="content-container">'
        + f"<{wrapper}>Opening <strong>operating evidence</strong> remains intact."
        + BODY + COMMENTS + "Concluding prose remains intact."
        + f"</{wrapper}></div>"
    )
    payload = _scrape(tmp_path, html)
    _assert_article(payload)
    assert "Opening operating evidence remains intact." in payload["body_markdown"]
    assert "Concluding prose remains intact." in payload["body_markdown"]


def test_nested_comment_table_cannot_add_cells_to_article_table(tmp_path):
    html = (
        '<main>' + BODY + '<table><tr><th>Period</th><th>Value</th></tr>'
        '<tr><td>2026</td><td>42<div class="border-t-share-separator-thin">'
        '<table><tr><td>Reader reply hidden in a nested table.</td></tr></table>'
        '</div></td></tr></table></main>'
    )
    payload = _scrape(tmp_path, html)
    _assert_article(payload)
    assert "| 2026 | 42 |" in payload["body_markdown"]
    assert payload["body_markdown"].count("| --- | --- |") == 1


def test_first_retained_table_row_gets_markdown_separator(tmp_path):
    html = (
        '<main>' + BODY + '<table><tr class="comment"><td>Reader reply</td></tr>'
        '<tr><th>Period</th><th>Value</th></tr><tr><td>2026</td><td>42</td></tr></table></main>'
    )
    payload = _scrape(tmp_path, html)
    _assert_article(payload)
    assert [line.strip() for line in payload["body_markdown"].splitlines() if line.startswith("|")] == [
        "| Period | Value |", "| --- | --- |", "| 2026 | 42 |",
    ]


@pytest.mark.parametrize("wrapper", ["blockquote", "ul", "table"])
def test_pruning_preserves_line_breaks_in_flattened_body_elements(tmp_path, wrapper):
    text = 'First line<br>Second line<span class="comment">Reader reply</span><br>Third line'
    if wrapper == "ul":
        text = "<li>" + text + "</li>"
    elif wrapper == "table":
        text = "<tr><td>" + text + "</td></tr>"
    payload = _scrape(tmp_path, "<main>" + BODY + f"<{wrapper}>" + text + f"</{wrapper}></main>")
    _assert_article(payload)
    expected = "First line\n> Second line\n> Third line" if wrapper == "blockquote" else "First line\nSecond line\nThird line"
    assert expected in payload["body_markdown"]


def test_pruning_does_not_expose_display_none_content(tmp_path):
    html = (
        "<main>" + BODY + '<blockquote><div>Shown first.</div>'
        '<div style="display:none">Hidden interface text.</div>'
        '<span class="comment">Reader reply</span><div>Shown last.</div></blockquote></main>'
    )
    payload = _scrape(tmp_path, html)
    _assert_article(payload)
    assert "Hidden interface text" not in payload["body_markdown"]
    assert "Shown first." in payload["body_markdown"]
    assert "Shown last." in payload["body_markdown"]


def test_pruned_block_separators_are_not_dropped_or_duplicated(tmp_path):
    html = (
        "<main>" + BODY + '<blockquote><div>First block</div>'
        '<span class="comment">Reader reply</span><div>Second block</div></blockquote></main>'
    )
    payload = _scrape(tmp_path, html)
    _assert_article(payload)
    assert "> First block\n> Second block" in payload["body_markdown"]


@pytest.mark.parametrize("tag", ['div class="paywall-full-content"', "main", "article"])
def test_clean_fallback_preserves_article_and_legitimate_comments_prose(tmp_path, tag):
    html = (
        "<" + tag + ">" + BODY
        + "<h3>Comments</h3><p>Management comments on the investment outlook.</p>"
        + "</" + tag.split()[0] + ">"
    )
    payload = _scrape(tmp_path, html)
    _assert_article(payload)
    assert "### Comments" in payload["body_markdown"]
    assert "Management comments on the investment outlook." in payload["body_markdown"]


def test_provider_article_still_wins_over_larger_generic_disclosure(tmp_path):
    html = (
        "<article><p>" + "Disclosure boilerplate. " * 200 + "</p></article>"
        + '<div data-test-id="content-container">' + BODY + "</div>"
    )
    payload = _scrape(tmp_path, html)
    _assert_article(payload)
    assert "Disclosure boilerplate" not in payload["body_markdown"]


@pytest.mark.parametrize("tag", ["main", "article", 'div data-test-id="content-container"'])
def test_disclosure_only_container_does_not_produce_an_article(tmp_path, tag):
    payload = _scrape(tmp_path, "<" + tag + ">" + DISCLOSURES + "</" + tag.split()[0] + ">")
    assert payload.get("error"), payload
    assert not payload.get("body_markdown")


@pytest.mark.parametrize(
    "metadata",
    [
        '<div data-test-id="post-page-meta"><span data-test-id="post-date">'
        'Jul 15, 2026, 12:00 PM ET</span><span data-test-id="post-primary-tickers">'
        + "Provider Company (PROV) Stock " * 12 + "</span></div>",
        '<div data-testid="author-name">' + "Provider Analyst " * 20 + "</div>",
        "<p>By: Provider Analyst</p><time datetime='2026-07-15'>Jul 15, 2026</time>",
    ],
    ids=["provider-metadata", "author-name", "plain-byline"],
)
def test_metadata_and_disclosures_do_not_produce_an_article(tmp_path, metadata):
    payload = _scrape(tmp_path, "<main>" + metadata + DISCLOSURES + "</main>")
    assert payload.get("error"), payload
    assert not payload.get("body_markdown")


@pytest.mark.parametrize("include_disclosures", [False, True])
def test_headings_do_not_make_a_body_eligible(tmp_path, include_disclosures):
    html = "<main><h1>" + "Provider headline " * 20 + "</h1><h2>Business Overview</h2>"
    html += "<p>Short placeholder.</p>" + (DISCLOSURES if include_disclosures else "") + "</main>"
    payload = _scrape(tmp_path, html)
    assert payload.get("error"), payload
    assert not payload.get("body_markdown")


@pytest.mark.parametrize("disclosure_first", [False, True])
@pytest.mark.parametrize("tag", ["article", 'div data-testid="article-body"'])
def test_larger_disclosure_card_cannot_outvote_genuine_article(tmp_path, disclosure_first, tag):
    article = "<" + tag + ">" + BODY + "</" + tag.split()[0] + ">"
    disclosure = "<" + tag + ">" + DISCLOSURES * 10 + "</" + tag.split()[0] + ">"
    html = disclosure + article if disclosure_first else article + disclosure
    payload = _scrape(tmp_path, html)
    _assert_article(payload)
    assert "Analyst's Disclosure" not in payload["body_markdown"]


def test_disclosures_do_not_inflate_mixed_candidate_ranking(tmp_path):
    html = (
        '<div data-test-id="content-container"><p>' + SHORT_PROSE + "</p>"
        + DISCLOSURES * 10 + '</div><div data-test-id="content-container">' + BODY + "</div>"
    )
    payload = _scrape(tmp_path, html)
    _assert_article(payload)
    assert SHORT_PROSE not in payload["body_markdown"]


def test_disclosure_only_provider_card_does_not_hide_generic_body(tmp_path):
    html = '<div data-test-id="content-container">' + DISCLOSURES + "</div><main>" + BODY + "</main>"
    _assert_article(_scrape(tmp_path, html))


@pytest.mark.parametrize("with_comments", [False, True])
def test_short_genuine_prose_survives_disclosures_and_comments(tmp_path, with_comments):
    assert 200 < len(SHORT_PROSE) < 300
    html = (
        "<main><h2>Investment Outlook</h2><p>" + SHORT_PROSE + "</p>" + DISCLOSURES
        + (COMMENTS if with_comments else "") + "</main>"
    )
    payload = _scrape(tmp_path, html)
    assert "error" not in payload, payload
    assert payload["body_markdown"] == "## Investment Outlook\n\n" + SHORT_PROSE


@pytest.mark.parametrize(
    "attributes",
    [
        'data-test-id="article-body"', 'data-testid="article-body"',
        'data-test-id="content-container"', 'data-testid="content-container"',
    ],
)
@pytest.mark.parametrize("with_comments", [False, True])
def test_provider_short_prose_survives_removal_of_long_disclosures(
    tmp_path, attributes, with_comments
):
    assert len(PROVIDER_SHORT_PROSE) == 125
    html = (
        "<main><div " + attributes + "><h2>Investment Outlook</h2><p>"
        + PROVIDER_SHORT_PROSE + "</p>" + DISCLOSURES
        + (COMMENTS if with_comments else "") + "</div></main>"
    )
    payload = _scrape(tmp_path, html)
    assert "error" not in payload, payload
    assert payload["body_markdown"] == "## Investment Outlook\n\n" + PROVIDER_SHORT_PROSE


@pytest.mark.parametrize(
    "prose",
    [
        PROVIDER_SHORT_PROSE,
        "Sales grew as contracts renewed. Cash flow funded equipment and reduced debt.",
    ],
)
def test_provider_short_prose_does_not_require_disclosure_padding(tmp_path, prose):
    payload = _scrape(
        tmp_path, '<div data-testid="article-body"><p>' + prose + "</p></div>"
    )
    assert "error" not in payload, payload
    assert payload["body_markdown"] == prose


@pytest.mark.parametrize(
    "tag",
    ["main", "article", 'div class="paywall-full-content"', 'div id="content-body"'],
)
def test_short_prose_exception_requires_exact_provider_marker(tmp_path, tag):
    html = "<" + tag + "><p>" + PROVIDER_SHORT_PROSE + "</p>" + DISCLOSURES + "</" + tag.split()[0] + ">"
    payload = _scrape(tmp_path, html)
    assert payload.get("error"), payload
    assert not payload.get("body_markdown")


@pytest.mark.parametrize(
    "body",
    [
        "",
        "<p>Short placeholder.</p>",
        "<p>Revenue increased.</p>",
        "<p>Margins improved. Debt declined.</p>",
        "<p>Content is temporarily unavailable while we retrieve this article. "
        "Please check back later to read the complete investment analysis.</p>",
        "<p>Subscribe to read the full investment analysis for this company. "
        "Our members receive all research updates and related reports.</p>",
        "<p>Revenue increased as customers renewed annual contracts and cash flow "
        "covered new equipment while leaving room to reduce outstanding debt.</p>",
        "<span>" + PROVIDER_SHORT_PROSE + "</span>",
        '<div data-testid="author-name"><p>' + PROVIDER_SHORT_PROSE + "</p></div>",
        '<div class="border-t-share-separator-thin"><p>' + PROVIDER_SHORT_PROSE + "</p></div>",
    ],
    ids=[
        "title-and-legal-only", "placeholder", "two-words", "tiny-sentences", "unavailable",
        "subscribe", "one-sentence", "no-paragraph", "author-metadata", "comment-row",
    ],
)
def test_provider_short_body_exception_does_not_admit_non_narrative(tmp_path, body):
    html = (
        '<div data-testid="content-container"><h1>' + "Provider headline " * 20 + "</h1>"
        + body + DISCLOSURES + "</div>"
    )
    payload = _scrape(tmp_path, html)
    assert payload.get("error"), payload
    assert not payload.get("body_markdown")


def test_provider_short_body_exception_does_not_escape_author_context(tmp_path):
    html = (
        '<div data-testid="author-name"><div data-testid="article-body"><p>'
        + PROVIDER_SHORT_PROSE + "</p>" + DISCLOSURES + "</div></div>"
    )
    payload = _scrape(tmp_path, html)
    assert payload.get("error"), payload
    assert not payload.get("body_markdown")


def test_provider_short_body_exception_does_not_apply_to_market_news(tmp_path):
    payload = _scrape(
        tmp_path, '<div data-testid="article-body"><p>' + PROVIDER_SHORT_PROSE + "</p></div>",
        news=True,
    )
    assert payload.get("error"), payload
    assert not payload.get("body_markdown")


@pytest.mark.parametrize("body", ["", "<p>Short placeholder.</p>"])
def test_disclosures_cannot_make_a_short_body_eligible(tmp_path, body):
    payload = _scrape(tmp_path, "<main>" + body + DISCLOSURES + COMMENTS + "</main>")
    assert payload.get("error"), payload
    assert not payload.get("body_markdown")


@pytest.mark.parametrize("label", ["Analyst's Disclosure", "Analyst&#8217;s Disclosure"])
def test_split_disclosure_heading_does_not_consume_following_analysis(tmp_path, label):
    html = (
        "<main><h3>" + label + "</h3><p>" + ANALYST_DISCLOSURE + "</p>"
        "<p>" + SHORT_PROSE + "</p><h3>Seeking Alpha's Disclosure</h3><p>"
        + SA_DISCLOSURE + "</p></main>"
    )
    payload = _scrape(tmp_path, html)
    assert "error" not in payload, payload
    assert payload["body_markdown"] == SHORT_PROSE


def test_split_disclosure_heading_only_page_is_rejected(tmp_path):
    html = (
        "<main><h3>Analyst's Disclosure</h3><p>" + ANALYST_DISCLOSURE + "</p>"
        "<h3>Seeking Alpha's Disclosure</h3><p>" + SA_DISCLOSURE + "</p></main>"
    )
    payload = _scrape(tmp_path, html)
    assert payload.get("error"), payload
    assert not payload.get("body_markdown")


@pytest.mark.parametrize(
    "prose",
    [
        ANALYST_DISCLOSURE + " I am not receiving compensation for it (other than from "
        "Seeking Alpha). I have no business relationship with any company whose stock "
        "is mentioned in this article.",
        SA_DISCLOSURE + " Seeking Alpha is not a licensed securities dealer, broker or "
        "US investment adviser or investment bank. Our analysts are third party authors "
        "that include both professional investors and individual investors who may not "
        "be licensed or certified by any institute or regulatory body.",
    ],
    ids=["author-compensation", "platform-licensing"],
)
def test_unlabelled_legal_only_paragraph_is_not_a_body(tmp_path, prose):
    payload = _scrape(tmp_path, "<main><p>" + prose + "</p></main>")
    assert payload.get("error"), payload
    assert not payload.get("body_markdown")


@pytest.mark.parametrize("wrapper", ["div", "blockquote", "ul", "table"])
def test_nested_disclosure_pruning_preserves_other_prose(tmp_path, wrapper):
    text = "<span>" + SHORT_PROSE + "</span><div>" + DISCLOSURES + "</div>"
    if wrapper == "ul":
        text = "<li>" + text + "</li>"
    elif wrapper == "table":
        text = "<tr><td>" + text + "</td></tr>"
    payload = _scrape(tmp_path, "<main><" + wrapper + ">" + text + "</" + wrapper + "></main>")
    assert "error" not in payload, payload
    assert payload["body_markdown"].count(SHORT_PROSE) == 1
    assert ANALYST_DISCLOSURE not in payload["body_markdown"]
    assert SA_DISCLOSURE not in payload["body_markdown"]


def test_discussing_disclosure_and_legal_risk_is_retained(tmp_path):
    prose = (
        "Disclosure requirements affect the company's reporting costs. Management "
        "expanded its risk disclosure after regulators requested additional detail. "
        "The Analyst's Disclosure: label on a research note is not a substitute for "
        "evaluating operating cash flow. Past performance is no guarantee of future "
        "results, so our forecast relies on contracted revenue and current margins."
    )
    payload = _scrape(tmp_path, "<main><h2>Disclosure</h2><p>" + prose + "</p>" + DISCLOSURES + "</main>")
    assert "error" not in payload, payload
    assert payload["body_markdown"] == "## Disclosure\n\n" + prose


def test_boilerplate_sentence_does_not_discard_mixed_paragraph(tmp_path):
    prose = "Past performance is no guarantee of future results. " + SHORT_PROSE
    payload = _scrape(tmp_path, "<main><p>" + prose + "</p>" + DISCLOSURES + "</main>")
    assert "error" not in payload, payload
    assert payload["body_markdown"] == prose


def test_inline_disclosure_mention_is_not_removed(tmp_path):
    payload = _scrape(
        tmp_path, "<main><p>" + SHORT_PROSE + " The <strong>Analyst's Disclosure:</strong> "
        "label identifies potential conflicts.</p>" + DISCLOSURES + "</main>",
    )
    assert "error" not in payload, payload
    assert payload["body_markdown"] == (
        SHORT_PROSE + " The Analyst's Disclosure: label identifies potential conflicts."
    )


@pytest.mark.parametrize("tag", ["div", 'span style="display:block"'])
def test_leaf_disclosure_blocks_cannot_hide_mixed_parent(tmp_path, tag):
    html = (
        "<main><div><" + tag + "><strong>Analyst's Disclosure:</strong> "
        + ANALYST_DISCLOSURE + "</" + tag.split()[0] + "><p>" + SHORT_PROSE + "</p></div></main>"
    )
    payload = _scrape(tmp_path, html)
    assert "error" not in payload, payload
    assert payload["body_markdown"] == SHORT_PROSE


def test_plain_byline_does_not_count_toward_body_eligibility(tmp_path):
    prose = "Operating margins increased as service contracts renewed. " * 3
    assert len(prose) < 200
    html = "<main><p>By: Provider Analyst and Research Team</p><p>" + prose + "</p></main>"
    payload = _scrape(tmp_path, html)
    assert payload.get("error"), payload
    assert not payload.get("body_markdown")


def test_metadata_pruning_does_not_change_article_identity(tmp_path):
    html = (
        '<main><div data-test-id="post-page-meta"><span data-test-id="post-date">'
        'Jul 15, 2026, 12:00 PM ET</span><span data-test-id="post-primary-tickers">'
        '<a>Provider Company (PROV) Stock</a></span></div> <div data-testid="author-name">'
        '<a href="/author/provider-analyst">Provider Analyst</a></div>'
        '<time datetime="2026-07-15">Jul 15, 2026</time>' + BODY + DISCLOSURES + "</main>"
    )
    payload = _scrape(tmp_path, html)
    _assert_article(payload)
    assert payload["title"] == "Provider article"
    assert payload["author"] == "Provider Analyst"
    assert payload["publish_date"] == "2026-07-15"
    assert payload["detail_ticker"] == "PROV"
    assert payload["detail_ticker_observed_at"].endswith("Z")
    assert "Provider Analyst" not in payload["body_markdown"]
    assert "Jul 15, 2026" not in payload["body_markdown"]
    assert "Analyst's Disclosure" not in payload["body_markdown"]


@pytest.mark.parametrize("wrapper", ["p", "main", "span"])
def test_time_inside_genuine_prose_is_not_metadata(tmp_path, wrapper):
    html = (
        "<main><" + wrapper + '>As of <time datetime="2026-07-15">July 15, 2026</time>, '
        + SHORT_PROSE + "</" + wrapper + "></main>"
    )
    payload = _scrape(tmp_path, html)
    assert "error" not in payload, payload
    assert payload["body_markdown"].count("July 15, 2026") == 1
    assert payload["body_markdown"].count(SHORT_PROSE) == 1


def test_disclosure_classification_leaves_dom_intact(tmp_path):
    payload = _scrape(
        tmp_path, "<main>" + BODY + DISCLOSURES + "</main>",
        after='({labels: Array.from(document.querySelectorAll("main > p")).filter('
        'node => node.textContent.includes("Disclosure:")).length})',
    )
    assert payload == {"labels": 2}


def test_article_semantic_filter_does_not_change_market_news_disclosures(tmp_path):
    payload = _scrape(tmp_path, "<main><p>" + SHORT_PROSE + "</p>" + DISCLOSURES + "</main>", news=True)
    assert "error" not in payload, payload
    assert SHORT_PROSE in payload["body_markdown"]
    assert "Analyst's Disclosure: " + ANALYST_DISCLOSURE in payload["body_markdown"]
    assert "Seeking Alpha's Disclosure: " + SA_DISCLOSURE in payload["body_markdown"]


def test_body_extraction_leaves_live_comment_dom_intact(tmp_path):
    payload = _scrape(
        tmp_path, '<main>' + BODY + COMMENTS + "</main>",
        after='({rows: document.querySelectorAll(".border-t-share-separator-thin").length, '
        'heading: document.querySelector("h3").textContent})',
    )
    assert payload == {"rows": 1, "heading": "COMMENTS (68)"}


def test_news_cleaning_and_markdown_structure_survive_comment_exclusion(tmp_path):
    html = (
        '<main><div data-test-id="content-container">' + BODY
        + "<ul><li>Reported operating cash flow.</li><li>Reported debt levels.</li></ul>"
        + "<table><tr><th>Period</th><th>Value</th></tr><tr><td>2026</td><td>42</td></tr></table>"
        + "<h2>More on Provider</h2><p>Related recommendations.</p>"
        + "</div>" + COMMENTS + "</main>"
    )
    payload = _scrape(tmp_path, html, news=True)
    markdown = payload["body_markdown"]
    for paragraph in PARAGRAPHS:
        assert markdown.count(paragraph) == 1
    assert "- Reported operating cash flow." in markdown
    assert "| 2026 | 42 |" in markdown
    assert "Related recommendations" not in markdown
    assert "Reader reply" not in markdown
