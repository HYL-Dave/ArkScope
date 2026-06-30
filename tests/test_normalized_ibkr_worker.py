from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest


def test_ibkr_runtime_disconnects_after_worker_failure():
    from src.news_normalized.ibkr_runtime import IBKRRuntimeGateway

    events = []

    class Source:
        def disconnect(self):
            events.append("disconnect")

    gateway = IBKRRuntimeGateway(Source())

    with pytest.raises(RuntimeError, match="boom"):
        with gateway:
            raise RuntimeError("boom")

    assert events == ["disconnect"]


def test_ibkr_runtime_rejects_malformed_provider_article_id():
    from src.news_normalized.ibkr_runtime import IBKRRuntimeGateway

    class Source:
        def fetch_news(self, *args, **kwargs):
            return [
                SimpleNamespace(
                    ticker="AAPL",
                    title="Secret title",
                    source="DJ-N",
                    description="[Article ID: malformed-id]",
                    published_date=datetime(2026, 6, 29, 9, 30),
                    url="",
                )
            ]

        def disconnect(self):
            pass

    gateway = IBKRRuntimeGateway(Source())

    with pytest.raises(ValueError, match="malformed IBKR article ID"):
        list(gateway.fetch_headlines("AAPL", None))


def test_ibkr_worker_requires_explicit_tickers():
    from scripts.collection import collect_ibkr_news_normalized as worker

    with pytest.raises(SystemExit) as caught:
        worker.parse_args([])

    assert caught.value.code == 2


def test_ibkr_worker_prints_sanitized_json_without_provider_payload(
    monkeypatch,
    capsys,
):
    from scripts.collection import collect_ibkr_news_normalized as worker

    forbidden_title = "Secret merger title"
    forbidden_url = "https://provider.example.test/article"
    forbidden_article_id = "DJ-N$secret-article-id"
    forbidden_provider_text = "licensed provider payload"
    forbidden_body = "<p>raw body text</p>"

    def fake_run_worker(*args, **kwargs):
        return {
            "status": "partial",
            "articles_seen": 3,
            "articles_inserted": 2,
            "bodies_fetched": 1,
            "legacy_rows_inserted": 2,
            "legacy_rows_updated": 1,
            "projection_skipped_no_ticker": 0,
            "errors": {
                f"body:{forbidden_article_id}": (
                    f"{forbidden_provider_text} {forbidden_title} "
                    f"{forbidden_url} {forbidden_body}"
                )
            },
            "continuation": {
                "deferred_tickers": ["AAPL"],
                "deferred_body_ids": [forbidden_article_id],
                "cursor": forbidden_article_id,
            },
        }

    monkeypatch.setattr(worker, "_run_worker", fake_run_worker)
    monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)

    code = worker.main(["--tickers", "AAPL", "--gateway-lock-held"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    rendered = json.dumps(payload, sort_keys=True)
    assert set(payload) <= {
        "status",
        "articles_seen",
        "articles_inserted",
        "bodies_fetched",
        "legacy_rows_inserted",
        "legacy_rows_updated",
        "projection_skipped_no_ticker",
        "error_count",
        "error_classes",
        "continuation",
    }
    assert payload["status"] == "partial"
    assert payload["error_count"] == 1
    assert payload["error_classes"] == ["ProviderError"]
    assert payload["continuation"] == {
        "deferred_ticker_count": 1,
        "deferred_body_count": 1,
        "has_cursor": True,
    }
    for forbidden in (
        forbidden_title,
        forbidden_url,
        forbidden_article_id,
        forbidden_provider_text,
        forbidden_body,
    ):
        assert forbidden not in rendered
