"""SA feed display-text contract — `markdown_to_plain_snippet` (Layer C-1 polish).

Pure READ-TIME cleanup of body_markdown/summary into a clean plain-text list
snippet. Raw markdown stays in the DB (FTS / detail / agent evidence are untouched);
this only governs what the feed list shows. No markdown renderer, no HTML render:
headings/emphasis/links/images/code/lists/tables/HTML are flattened to text, known
SA boilerplate (Author / Disclosure) lines are dropped, whitespace is compressed,
and truncation lands on a word boundary.
"""
from __future__ import annotations

from src.text_snippet import markdown_to_plain_snippet as plain


def test_empty_and_none():
    assert plain("") == ""
    assert plain(None) == ""
    assert plain("   \n\n  ") == ""


def test_heading_marker_stripped():
    assert plain("# Datacenter momentum\n\nThe quarter was strong.") == \
        "Datacenter momentum The quarter was strong."
    assert plain("### Sub head") == "Sub head"


def test_emphasis_markers_removed():
    assert plain("This is **bold** and *italic* and ~~struck~~.") == \
        "This is bold and italic and struck."
    assert plain("Mix __b__ and _i_ here") == "Mix b and i here"


def test_underscore_inside_word_preserved():
    # only emphasis PAIRS are stripped; snake_case / mid-word underscores survive
    assert plain("call func_name now") == "call func_name now"


def test_links_and_images():
    assert plain("See [the report](https://x.com/a?b=1) today") == "See the report today"
    assert plain("![NVDA chart](https://x/img.png) Revenue grew") == "NVDA chart Revenue grew"
    assert plain("![](https://x/i.png) Only caption") == "Only caption"
    assert plain("ref [link][1] style") == "ref link style"


def test_code_inline_and_fenced():
    assert plain("Use `pip install pkg` now") == "Use pip install pkg now"
    assert plain("```python\nx = 1\n```\nthen prose") == "x = 1 then prose"


def test_lists_and_blockquote():
    assert plain("- one\n- two\n- three") == "one two three"
    assert plain("1. first\n2. second") == "first second"
    assert plain("> quoted\nplain") == "quoted plain"


def test_table_flattened():
    assert plain("| Metric | Q1 |\n|---|---|\n| Rev | 10 |") == "Metric Q1 Rev 10"


def test_html_tags_removed_not_rendered():
    # never render or trust external HTML — strip tags, keep text
    assert plain("<div class='x'>hello</div> <b>world</b>") == "hello world"
    assert plain("safe <script>alert(1)</script> text") == "safe alert(1) text"


def test_sa_boilerplate_byline_and_disclosure_dropped():
    # the EXACT real sa_articles.body_markdown shape (curly apostrophe included)
    raw = ("# Alpha Picks Market Recap & Portfolio Review\n\n"
           "*Author: Seeking Alpha*\n\n"
           "Analyst’s Disclosure: I/we have a beneficial long position in the shares of MU.")
    assert plain(raw) == "Alpha Picks Market Recap & Portfolio Review"


def test_disclosure_then_prose_keeps_prose():
    raw = ("# Headline\n\n*Author: Seeking Alpha*\n\n"
           "Analyst's Disclosure: none.\n\nNVIDIA reported record revenue.")
    out = plain(raw)
    assert "Author" not in out and "Disclosure" not in out
    assert out == "Headline NVIDIA reported record revenue."


def test_whitespace_and_repeated_punct_collapsed():
    assert plain("a\n\n\n  b\t\tc") == "a b c"
    assert plain("Wow!!!! Really???") == "Wow! Really?"


def test_word_boundary_truncation():
    long = "alpha beta gamma delta " * 20  # well over the limit
    out = plain(long, limit=40)
    assert out.endswith("…")            # ellipsis appended
    body = out[:-1].rstrip()
    assert len(body) <= 40
    assert body.split()[-1] in {"alpha", "beta", "gamma", "delta"}  # no mid-token cut


def test_no_truncation_when_under_limit():
    assert plain("short and clean") == "short and clean"


def test_no_raw_markdown_leaks():
    raw = "## **Title** with [a](u) and `c` and ![i](p)\n- bullet"
    out = plain(raw)
    for marker in ("#", "*", "`", "](", "!["):
        assert marker not in out
