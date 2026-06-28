from dataclasses import FrozenInstanceError

import pytest

from src.news_normalized.identity import (
    IDENTITY_VERSION,
    build_identity_keys,
    fallback_identity_hash,
    normalize_identity_text,
    normalize_stable_url,
    normalize_timestamp,
)
from src.news_normalized.models import (
    ArticleCandidate,
    ArticleKey,
    BodyCandidate,
    BodyStatus,
    KeyKind,
)


def test_models_have_stable_values_defaults_and_are_immutable():
    assert [kind.value for kind in KeyKind] == ["provider_id", "url", "fallback"]
    assert [status.value for status in BodyStatus] == [
        "pending",
        "fetched",
        "empty",
        "failed",
        "expired",
    ]

    key = ArticleKey("ibkr", KeyKind.PROVIDER_ID, "123", True)
    body = BodyCandidate()
    article = ArticleCandidate(source="ibkr", title="Title", published_at="2026-06-27")

    assert body == BodyCandidate(
        status=BodyStatus.PENDING,
        raw_body=None,
        raw_format=None,
        retrieval_method=None,
        retrieval_source=None,
        source_url=None,
        fetched_at=None,
        error=None,
    )
    assert article == ArticleCandidate(
        source="ibkr",
        title="Title",
        published_at="2026-06-27",
        provider_article_id=None,
        publisher="",
        url="",
        primary_ticker=None,
        related_tickers=(),
        observed_at=None,
        content_kind="unknown",
        body=BodyCandidate(),
    )
    with pytest.raises(FrozenInstanceError):
        key.value = "456"
    with pytest.raises(FrozenInstanceError):
        body.status = BodyStatus.FETCHED
    with pytest.raises(FrozenInstanceError):
        article.title = "Revised"


def test_identity_text_decodes_nfkc_collapses_whitespace_and_casefolds():
    assert normalize_identity_text("  Stra&szlig;e\t\uff21\uff34\uff06\uff34\n") == "strasse at&t"


@pytest.mark.parametrize(
    "value",
    [
        "2026-06-27T10:11:12Z",
        "2026-06-27T10:11:12+00:00",
        "2026-06-27T10:11:12+0000",
    ],
)
def test_timestamp_normalizes_equivalent_utc_suffixes(value):
    assert normalize_timestamp(value) == "2026-06-27T10:11:12Z"


def test_timestamp_preserves_available_precision_and_date_only_values():
    assert normalize_timestamp("2026-06-27T10:11:12.1200+00:00") == (
        "2026-06-27T10:11:12.1200Z"
    )
    assert normalize_timestamp("2026-06-27") == "2026-06-27"


def test_fallback_excludes_ticker_and_has_a_deterministic_64_char_value():
    first = ArticleCandidate(
        source="ibkr",
        publisher="DJ-N",
        title="AT&amp;T   Rises",
        published_at="2026-06-27T10:11:12+0000",
        primary_ticker="T",
    )
    second = ArticleCandidate(
        source="ibkr",
        publisher="dj-n",
        title="at&t rises",
        published_at="2026-06-27T10:11:12Z",
        primary_ticker="VZ",
    )

    def candidate_hash(candidate):
        return fallback_identity_hash(
            source=candidate.source,
            publisher=candidate.publisher,
            title=candidate.title,
            published_at=candidate.published_at,
        )

    expected = "25632239a38bff69229e3f3742d784d66552287091bc0e2ac4690a851539bb3d"
    assert IDENTITY_VERSION == "news-id-v1"
    assert candidate_hash(first) == candidate_hash(second) == expected
    assert len(expected) == 64


def test_stable_url_normalizes_host_and_removes_fragment_slash_and_all_utm_keys():
    value = (
        "HTTPS://Example.TEST/Story///?z=&UTM_Source=x&utm_custom=y&a=1"
        "#section"
    )

    assert normalize_stable_url(value) == "https://example.test/Story?a=1&z="


def test_stable_url_preserves_userinfo_case_while_normalizing_host():
    value = "HTTPS://User:Pass@Example.TEST:443/story/"

    assert normalize_stable_url(value) == (
        "https://User:Pass@example.test:443/story"
    )


def test_provider_and_url_are_strong_in_order_but_fallback_is_weak():
    keys = build_identity_keys(
        source="polygon",
        provider_article_id=" abc-123 ",
        url="https://EXAMPLE.test/story/?utm_source=x",
        publisher="Reuters",
        title="Title",
        published_at="2026-06-27T10:11:12Z",
    )

    assert [(key.kind, key.strong) for key in keys] == [
        (KeyKind.PROVIDER_ID, True),
        (KeyKind.URL, True),
        (KeyKind.FALLBACK, False),
    ]
    assert keys[0] == ArticleKey("polygon", KeyKind.PROVIDER_ID, "abc-123", True)
    assert keys[1] == ArticleKey(
        "polygon", KeyKind.URL, "https://example.test/story", True
    )


def test_blank_provider_and_url_do_not_create_empty_strong_keys():
    keys = build_identity_keys(
        source="finnhub",
        provider_article_id="   ",
        url=" \t",
        publisher="",
        title="Title",
        published_at="2026-06-27",
    )

    assert len(keys) == 1
    assert keys[0].kind is KeyKind.FALLBACK
    assert keys[0].strong is False
