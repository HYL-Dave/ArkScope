from datetime import datetime, timezone

from src.collectors.finnhub_news import (
    FinnhubNewsCollector,
    NewsArticle as FinnhubArticle,
)
from src.collectors.polygon_news import NewsArticle as PolygonArticle
from src.news_normalized.models import BodyStatus
from src.news_normalized.provider_adapters import (
    FinnhubNormalizedProvider,
    PolygonNormalizedProvider,
    collector_article_to_candidate,
)


def polygon_article(**overrides):
    values = {
        "article_id": "poly-1",
        "ticker": "AAPL",
        "title": "Apple update",
        "published_at": "2026-06-27T10:00:00Z",
        "description": "Provider summary",
        "content": "Provider summary",
        "url": "https://example.test/poly-1",
        "publisher": "Example Wire",
        "related_tickers": '["AAPL", "MSFT", "AAPL"]',
        "collected_at": "2026-06-27T10:01:00+00:00",
    }
    values.update(overrides)
    return PolygonArticle(**values)


def finnhub_article(**overrides):
    values = {
        "article_id": "77",
        "ticker": "NVDA",
        "title": "Chip update",
        "published_at": "2026-06-27T11:00:00Z",
        "description": "Short summary",
        "content": "Short summary",
        "url": "https://example.test/77",
        "publisher": "Example Wire",
        "related_tickers": '["NVDA", "AMD"]',
        "collected_at": "2026-06-27T11:01:00+00:00",
    }
    values.update(overrides)
    return FinnhubArticle(**values)


def test_polygon_mapping_preserves_provider_id_relations_and_summary_body():
    article = polygon_article()

    candidate = collector_article_to_candidate("polygon", article)

    assert candidate.provider_article_id == "poly-1"
    assert candidate.primary_ticker == "AAPL"
    assert candidate.related_tickers == ("AAPL", "MSFT")
    assert candidate.content_kind == "summary"
    assert candidate.body.status is BodyStatus.FETCHED
    assert candidate.body.raw_body == "Provider summary"
    assert candidate.body.retrieval_source == "polygon"


def test_mapping_uses_description_when_content_is_empty_and_handles_bad_relations():
    article = finnhub_article(
        content="", description="Fallback summary", related_tickers="not-json"
    )

    candidate = collector_article_to_candidate("finnhub", article)

    assert candidate.related_tickers == ()
    assert candidate.content_kind == "summary"
    assert candidate.body.raw_body == "Fallback summary"


def test_mapping_preserves_raw_provider_payload_bytes_as_text():
    article = polygon_article(content="  Provider summary\n", description="ignored")

    candidate = collector_article_to_candidate("polygon", article)

    assert candidate.body.raw_body == "  Provider summary\n"


def test_mapping_marks_missing_rest_body_terminal_empty():
    article = polygon_article(content="", description="")

    candidate = collector_article_to_candidate("polygon", article)

    assert candidate.content_kind == "headline_only"
    assert candidate.body.status is BodyStatus.EMPTY


def test_polygon_provider_uses_exact_inclusive_cursor_without_parquet_save():
    class Collector:
        def __init__(self):
            self.args = None

        def fetch_news_range(
            self, ticker, start_date, end_date, *, start_timestamp=None
        ):
            self.args = (ticker, start_date, end_date, start_timestamp)
            return [{"id": "poly-1"}]

        def parse_article(self, raw, collected_at):
            return polygon_article(article_id=raw["id"], collected_at=collected_at.isoformat())

        def save_articles(self, _rows):
            raise AssertionError("normalized adapter must not write Parquet")

    collector = Collector()
    provider = PolygonNormalizedProvider(
        collector, now_fn=lambda: datetime(2026, 6, 28, tzinfo=timezone.utc)
    )

    rows = list(provider.fetch_articles("AAPL", "2026-06-27T10:00:00+00:00"))

    assert len(rows) == 1
    assert collector.args[0] == "AAPL"
    assert collector.args[1].isoformat() == "2026-06-27"
    assert collector.args[2].isoformat() == "2026-06-28"
    assert collector.args[3].isoformat() == "2026-06-27T10:00:00+00:00"


def test_finnhub_provider_skips_truncated_parse_results_and_uses_date_cursor():
    class Collector:
        def __init__(self):
            self.args = None

        def fetch_news(self, ticker, start_date, end_date):
            self.args = (ticker, start_date, end_date)
            return [{"id": "keep"}, {"id": "skip"}]

        def parse_article(self, raw, ticker, collected_at):
            if raw["id"] == "skip":
                return None
            return finnhub_article(
                article_id=raw["id"], ticker=ticker, collected_at=collected_at.isoformat()
            )

        def save_articles(self, _rows):
            raise AssertionError("normalized adapter must not write Parquet")

    collector = Collector()
    provider = FinnhubNormalizedProvider(
        collector, now_fn=lambda: datetime(2026, 6, 28, tzinfo=timezone.utc)
    )

    rows = list(provider.fetch_articles("NVDA", "2026-06-26T23:59:59Z"))

    assert [row.provider_article_id for row in rows] == ["keep"]
    assert collector.args[0] == "NVDA"
    assert collector.args[1].isoformat() == "2026-06-26"
    assert collector.args[2].isoformat() == "2026-06-28"


def test_finnhub_parser_converts_unix_timestamp_to_real_utc():
    collector = FinnhubNewsCollector.__new__(FinnhubNewsCollector)
    collector.stats = {"by_source": {}}

    parsed = collector.parse_article(
        {
            "id": 1,
            "datetime": 1,
            "headline": "Epoch story",
            "summary": "Summary",
            "source": "Wire",
            "related": ["AAPL"],
        },
        "AAPL",
        datetime(2026, 6, 28, tzinfo=timezone.utc),
    )

    assert parsed is not None
    assert parsed.published_at == "1970-01-01T00:00:01Z"
