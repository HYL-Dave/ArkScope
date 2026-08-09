"""Deterministic analytics over raw news articles."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from math import sqrt
from statistics import pstdev
from typing import Any, Iterable


_EVENT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "POLICY_POSITIVE",
        (
            "executive order",
            "legislation",
            "subsidy",
            "approve",
            "funding boost",
            "tax credit",
            "incentive",
            "support",
        ),
    ),
    (
        "POLICY_NEGATIVE",
        ("ban", "restriction", "tariff", "sanction", "regulation", "crackdown"),
    ),
    (
        "TECH_MILESTONE",
        ("launch", "breakthrough", "patent", "successful test", "milestone", "achievement"),
    ),
    ("EARNINGS_BEAT", ("beat", "exceed", "strong quarter", "raises guidance", "tops")),
    ("EARNINGS_MISS", ("miss", "disappoint", "weak quarter", "lowers guidance", "falls short")),
    ("FUNDING", ("ipo", "fundraise", "acquisition", "merger", "investment round")),
    ("ANALYST_UPGRADE", ("upgrade", "raise target", "overweight", "buy rating")),
    ("ANALYST_DOWNGRADE", ("downgrade", "lower target", "underweight", "sell rating")),
    ("PRODUCT_LAUNCH", ("launch", "release", "unveil", "new product", "rollout")),
    ("PARTNERSHIP", ("partner", "collaborate", "agreement", "alliance", "joint venture")),
)

_CHAIN_PATTERNS: tuple[tuple[str, tuple[str, str]], ...] = (
    ("POLICY_TECH_CONFIRMATION", ("POLICY_POSITIVE", "TECH_MILESTONE")),
    ("UPGRADE_EARNINGS_CONFIRMATION", ("ANALYST_UPGRADE", "EARNINGS_BEAT")),
    ("FUNDING_MILESTONE", ("FUNDING", "TECH_MILESTONE")),
    ("EARNINGS_MOMENTUM", ("EARNINGS_BEAT", "ANALYST_UPGRADE")),
    ("PARTNERSHIP_LAUNCH", ("PARTNERSHIP", "PRODUCT_LAUNCH")),
    ("NEGATIVE_SPIRAL", ("EARNINGS_MISS", "ANALYST_DOWNGRADE")),
)


def _value(article: Any, field: str, default: Any = None) -> Any:
    if isinstance(article, dict):
        return article.get(field, default)
    return getattr(article, field, default)


def _date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().replace("Z", "+00:00")
    return datetime.fromisoformat(text).date()


def tag_news_title(title: str) -> str:
    """Return one deterministic event type for a raw news title."""
    normalized = title.casefold()
    for event_type, keywords in _EVENT_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return event_type
    return "GENERAL"


def detect_event_sequences(
    articles: Iterable[Any],
    *,
    ticker: str,
    window_days: int = 14,
) -> list[dict[str, Any]]:
    """Detect known ordered event pairs without assigning numeric impact."""
    events = sorted(
        (
            {
                "date": _date(_value(article, "date")),
                "event_type": tag_news_title(str(_value(article, "title", ""))),
                "title": str(_value(article, "title", "")),
            }
            for article in articles
        ),
        key=lambda item: (item["date"], item["title"]),
    )
    chains: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()
    for pattern, sequence in _CHAIN_PATTERNS:
        for first_index, first in enumerate(events):
            if first["event_type"] != sequence[0]:
                continue
            for second_index in range(first_index + 1, len(events)):
                second = events[second_index]
                delta = (second["date"] - first["date"]).days
                if delta > window_days:
                    break
                if second["event_type"] != sequence[1]:
                    continue
                key = (first_index, second_index, pattern)
                if key in seen:
                    continue
                seen.add(key)
                selected = (first, second)
                chains.append({
                    "pattern": pattern,
                    "event_count": 2,
                    "start_date": first["date"].isoformat(),
                    "end_date": second["date"].isoformat(),
                    "ticker": ticker.upper(),
                    "impact": {
                        "status": "unavailable",
                        "reason": "legacy_score_retired",
                    },
                    "events": [
                        {
                            "date": event["date"].isoformat(),
                            "event_type": event["event_type"],
                            "title": event["title"],
                        }
                        for event in selected
                    ],
                })
                break
    return sorted(chains, key=lambda item: (item["start_date"], item["end_date"], item["pattern"]))


def detect_raw_news_volume_anomaly(
    articles: Iterable[Any],
    *,
    ticker: str,
    as_of_date: str | date | None = None,
) -> dict[str, Any]:
    """Compare one day's raw article count with prior observed daily counts."""
    counts = Counter(_date(_value(article, "date")) for article in articles)
    target = _date(as_of_date) if as_of_date is not None else max(counts, default=date.today())
    current_count = counts.get(target, 0)
    history = [count for day, count in sorted(counts.items()) if day < target]
    historical_mean = sum(history) / len(history) if history else 0.0
    observed_std = pstdev(history) if len(history) > 1 else 0.0
    scale = max(observed_std, sqrt(historical_mean) if historical_mean > 0 else 0.0, 1.0)
    z_score = (current_count - historical_mean) / scale
    is_anomaly = z_score >= 2.0
    return {
        "ticker": ticker.upper(),
        "date": target.isoformat(),
        "is_anomaly": is_anomaly,
        "z_score": round(z_score, 4),
        "current_count": current_count,
        "historical_mean": round(historical_mean, 4),
        "reason": "VOLUME_SPIKE" if is_anomaly else "WITHIN_BASELINE",
    }
