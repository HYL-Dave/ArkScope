from __future__ import annotations

from types import SimpleNamespace


def _article(date: str, title: str, ticker: str = "NVDA"):
    return SimpleNamespace(
        date=date,
        ticker=ticker,
        title=title,
        source="polygon",
        url=None,
        publisher=None,
        description=None,
    )


def test_detect_event_chains_returns_typed_unavailable_impact():
    from src.tools.news_event_tools import detect_event_chains

    dal = SimpleNamespace()
    dal.get_news = lambda **_kwargs: SimpleNamespace(articles=[
        _article("2026-08-01", "Government subsidy support approved"),
        _article("2026-08-05", "Successful test reaches technical milestone"),
    ])

    assert detect_event_chains(dal, ticker="nvda", days=30) == [{
        "pattern": "POLICY_TECH_CONFIRMATION",
        "event_count": 2,
        "start_date": "2026-08-01",
        "end_date": "2026-08-05",
        "ticker": "NVDA",
        "impact": {
            "status": "unavailable",
            "reason": "legacy_score_retired",
        },
        "events": [
            {
                "date": "2026-08-01",
                "event_type": "POLICY_POSITIVE",
                "title": "Government subsidy support approved",
            },
            {
                "date": "2026-08-05",
                "event_type": "TECH_MILESTONE",
                "title": "Successful test reaches technical milestone",
            },
        ],
    }]


def test_detect_news_volume_anomaly():
    from src.tools.news_event_tools import detect_news_volume_anomaly

    articles = [
        _article(f"2026-07-{day:02d}", f"Baseline {day}")
        for day in range(18, 32)
    ]
    articles.extend(_article("2026-08-01", f"Spike {index}") for index in range(4))
    dal = SimpleNamespace()
    dal.get_news = lambda **_kwargs: SimpleNamespace(articles=articles)

    assert detect_news_volume_anomaly(
        dal, ticker="nvda", days=30, as_of_date="2026-08-01"
    ) == {
        "ticker": "NVDA",
        "date": "2026-08-01",
        "is_anomaly": True,
        "z_score": 3.0,
        "current_count": 4,
        "historical_mean": 1.0,
        "reason": "VOLUME_SPIKE",
    }
