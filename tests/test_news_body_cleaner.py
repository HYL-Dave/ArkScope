import hashlib
import json
from pathlib import Path

import pytest

from src.news_normalized.cleaner import (
    CLEANER_VERSION,
    clean_news_body,
    looks_like_html,
)


FIXTURES = Path(__file__).parent / "fixtures" / "news_cleaner"


@pytest.mark.parametrize(
    "fixture_name",
    ["dj_html.json", "table_and_entities.json", "plain_alert.json"],
)
def test_cleaner_golden_fixture(fixture_name):
    case = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))
    result = clean_news_body(
        case["raw"], raw_format=case["format"], source=case["source"]
    )
    assert result.text == case["expected"]
    assert result.version == CLEANER_VERSION


def test_cleaner_removes_non_content_elements_and_markup():
    result = clean_news_body(
        "<style>x</style><h1>Title</h1><script>alert(1)</script>"
        "<noscript>fallback</noscript><svg><text>shape</text></svg><p>Body&nbsp;text</p>",
        raw_format="html",
        source="ibkr",
    )
    assert result.text == "Title\n\nBody text"
    assert "<" not in result.text
    assert "alert" not in result.text
    assert "fallback" not in result.text


def test_cleaner_is_deterministic_and_does_not_mutate_raw():
    raw = "<p>A &amp; B</p><p>Next</p>"
    first = clean_news_body(raw, raw_format="html", source="finnhub")
    second = clean_news_body(raw, raw_format="html", source="finnhub")
    assert first == second
    assert raw == "<p>A &amp; B</p><p>Next</p>"
    assert hashlib.sha256(first.text.encode()).hexdigest() == hashlib.sha256(
        second.text.encode()
    ).hexdigest()


def test_cleaner_tolerates_malformed_html_and_preserves_blocks():
    result = clean_news_body(
        "<h2>Heading<p>One<br>Two<div>Three",
        raw_format="html",
        source="ibkr",
    )
    assert result.text == "Heading\n\nOne\n\nTwo\n\nThree"


def test_plain_text_is_not_treated_as_markup():
    raw = "2 < 3 and 5 > 4\nnext"
    assert not looks_like_html(raw)
    result = clean_news_body(raw, raw_format="text", source="polygon")
    assert result.text == "2 < 3 and 5 > 4\n\nnext"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("<p>body</p>", True),
        ("<DIV class='x'>body</DIV>", True),
        ("market < estimate", False),
        (None, False),
        ("", False),
    ],
)
def test_looks_like_html(value, expected):
    assert looks_like_html(value) is expected


def test_empty_body_returns_empty_clean_text():
    result = clean_news_body("", raw_format=None, source="ibkr")
    assert result.text == ""
