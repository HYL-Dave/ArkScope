from __future__ import annotations

import pytest

from src.news_content_availability import (
    RECOVERY_CAPABLE_BODY_SOURCES,
    classify_news_content,
    empty_content_counts,
)


@pytest.mark.parametrize(
    ("body_status", "source", "expected_availability", "expected_recovery"),
    (
        ("fetched", "finnhub", "full", None),
        ("pending", "ibkr", "headline_only", "retryable"),
        ("failed", "ibkr", "headline_only", "retryable"),
        ("pending", "finnhub", "headline_only", "terminal"),
        ("failed", "polygon", "headline_only", "terminal"),
        ("empty", "polygon", "headline_only", "terminal"),
        ("unavailable", "ibkr", "headline_only", "terminal"),
        ("expired", "ibkr", "headline_only", "terminal"),
        (None, None, "unknown", None),
    ),
    ids=(
        "fetched",
        "pending-retryable",
        "failed-retryable",
        "pending-no-recovery",
        "failed-no-recovery",
        "empty",
        "unavailable",
        "expired",
        "unmapped",
    ),
)
def test_classify_news_content(
    body_status: str | None,
    source: str | None,
    expected_availability: str,
    expected_recovery: str | None,
) -> None:
    assert classify_news_content(body_status, source) == (
        expected_availability,
        expected_recovery,
    )


def test_recovery_capable_sources_are_exactly_ibkr() -> None:
    assert RECOVERY_CAPABLE_BODY_SOURCES == frozenset({"ibkr"})

    first = empty_content_counts()
    second = empty_content_counts()
    assert first == second == {"full": 0, "headline_only": 0, "unknown": 0}
    assert first is not second
    first["full"] = 1
    assert second["full"] == 0
