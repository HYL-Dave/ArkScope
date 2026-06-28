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
        "unavailable",
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
        error_code=None,
        fetch_attempts=0,
        next_retry_at=None,
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


@pytest.mark.parametrize(
    ("kind", "strong"),
    [
        (KeyKind.PROVIDER_ID, False),
        (KeyKind.URL, False),
        (KeyKind.FALLBACK, True),
    ],
)
def test_article_key_rejects_strength_inconsistent_with_kind(kind, strong):
    with pytest.raises(ValueError, match="strength"):
        ArticleKey("ibkr", kind, "value", strong)


def test_article_candidate_coerces_related_tickers_to_an_immutable_tuple():
    related_tickers = ["AAPL", "MSFT"]

    article = ArticleCandidate(
        source="polygon",
        title="Title",
        published_at="2026-06-27",
        related_tickers=related_tickers,
    )
    related_tickers.append("NVDA")

    assert article.related_tickers == ("AAPL", "MSFT")
    assert isinstance(article.related_tickers, tuple)


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
    assert normalize_timestamp("2026-06-27T11:11:12.1200+01:00") == (
        "2026-06-27T10:11:12.1200Z"
    )
    assert normalize_timestamp("2026-06-27") == "2026-06-27"


@pytest.mark.parametrize(
    "value",
    [
        "2026-06-27T11:11:12+01:00",
        "2026-06-27T05:11:12-0500",
    ],
)
def test_timestamp_converts_nonzero_offsets_to_utc(value):
    assert normalize_timestamp(value) == "2026-06-27T10:11:12Z"


def test_invalid_timestamp_is_trimmed_but_otherwise_preserved():
    assert normalize_timestamp("  not-a-time+00:00  ") == "not-a-time+00:00"


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


@pytest.mark.parametrize(
    "value",
    [
        "ftp://example.test/story",
        "/relative/story",
        "https:///missing-host",
        "https://example.test:/story",
        "https://example.test:not-a-port/story",
        "https://example.test:99999/story",
        "https://[not-an-ipv6]/story",
        "https://[::1/story",
    ],
)
def test_stable_url_rejects_non_http_relative_and_malformed_values(value):
    assert normalize_stable_url(value) == ""


def test_stable_url_lowercases_scheme_and_host_and_drops_fragment():
    value = "HTTPS://Example.TEST/Story/#section"

    assert normalize_stable_url(value) == "https://example.test/Story/"


def test_stable_url_removes_only_known_utm_tracking_parameters():
    value = (
        "https://example.test/story?"
        "utm_source=s&utm_medium=m&utm_campaign=c&utm_term=t&utm_content=x&"
        "utm_custom=keep&ref=home"
    )

    assert normalize_stable_url(value) == (
        "https://example.test/story?utm_custom=keep&ref=home"
    )


def test_stable_url_preserves_query_order_duplicates_and_blank_values():
    value = "https://example.test/story?b=2&a=1&a=2&empty=&a=3"

    assert normalize_stable_url(value) == value


def test_stable_url_preserves_trailing_slash_as_part_of_path_identity():
    without_slash = normalize_stable_url("https://example.test/a")
    with_slash = normalize_stable_url("https://example.test/a/")

    assert without_slash == "https://example.test/a"
    assert with_slash == "https://example.test/a/"
    assert without_slash != with_slash


def test_stable_url_preserves_userinfo_case_while_normalizing_host():
    value = "HTTPS://User:Pass@Example.TEST:443/story/"

    assert normalize_stable_url(value) == (
        "https://User:Pass@example.test:443/story/"
    )


def test_polygon_url_is_metadata_not_an_identity_key():
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
        (KeyKind.FALLBACK, False),
    ]
    assert keys[0] == ArticleKey("polygon", KeyKind.PROVIDER_ID, "abc-123", True)


def test_finnhub_provider_and_url_are_strong_but_fallback_is_weak():
    keys = build_identity_keys(
        source="finnhub",
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
    assert keys[1] == ArticleKey(
        "finnhub", KeyKind.URL, "https://example.test/story/", True
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


def test_source_is_canonicalized_once_for_all_keys_and_fallback_identity():
    arguments = {
        "provider_article_id": "article-1",
        "url": "https://example.test/story",
        "publisher": "Reuters",
        "title": "Title",
        "published_at": "2026-06-27T10:11:12Z",
    }

    padded = build_identity_keys(source=" IBKR ", **arguments)
    canonical = build_identity_keys(source="ibkr", **arguments)

    assert padded == canonical
    assert {key.source for key in padded} == {"ibkr"}
