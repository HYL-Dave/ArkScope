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
