"""Agent-facing tools for score-free raw news analytics."""

from __future__ import annotations

from typing import Any

from src.news_analytics import detect_event_sequences, detect_raw_news_volume_anomaly


def detect_event_chains(dal, ticker: str, days: int = 30) -> list[dict[str, Any]]:
    normalized = ticker.strip().upper()
    result = dal.get_news(ticker=normalized, days=days, source="auto")
    return detect_event_sequences(result.articles, ticker=normalized)


def detect_news_volume_anomaly(
    dal,
    ticker: str,
    days: int = 30,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    normalized = ticker.strip().upper()
    result = dal.get_news(ticker=normalized, days=days, source="auto")
    return detect_raw_news_volume_anomaly(
        result.articles,
        ticker=normalized,
        as_of_date=as_of_date,
    )
