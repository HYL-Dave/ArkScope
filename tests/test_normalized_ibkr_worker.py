from __future__ import annotations

from contextlib import contextmanager
import json
import os
from datetime import datetime
import logging
from pathlib import Path
import subprocess
import sys
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
    from src.news_normalized import ibkr_cli as worker

    with pytest.raises(SystemExit) as caught:
        worker.parse_args([])

    assert caught.value.code == 2


def test_ibkr_worker_prints_sanitized_json_without_provider_payload(
    monkeypatch,
    capsys,
):
    from src.news_normalized import ibkr_cli as worker

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


def test_ibkr_worker_suppresses_provider_stderr_and_logging(monkeypatch, capsys):
    from src.news_normalized import ibkr_cli as worker

    secret = "licensed provider payload DJ-N$raw-id body text"

    def fake_run_worker(*args, **kwargs):
        print(secret, file=sys.stderr)
        logging.warning(secret)
        raise RuntimeError(secret)

    monkeypatch.setattr(worker, "_run_worker", fake_run_worker)
    monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)

    code = worker.main(["--tickers", "AAPL"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 1
    assert payload["status"] == "failed"
    assert secret not in captured.out
    assert secret not in captured.err


def test_ibkr_worker_standalone_acquires_gateway_lock_before_market_lock(
    monkeypatch,
):
    from src.news_normalized import ibkr_cli as worker

    events = []

    class Source:
        def disconnect(self):
            events.append("disconnect")

    class Conn:
        def close(self):
            events.append("conn_close")

    class Store:
        def __init__(self, conn):
            events.append("store")
            self.conn = conn

    @contextmanager
    def ibkr_lock():
        events.append("ibkr_enter")
        yield
        events.append("ibkr_exit")

    @contextmanager
    def market_lock():
        events.append("market_enter")
        yield
        events.append("market_exit")

    def write_news_batch(store, provider, tickers, budget, *, project_legacy=False):
        events.append("write")
        with provider.operation():
            events.append("provider_operation")
        return {"status": "succeeded", "errors": {}}

    monkeypatch.setattr("data_sources.ibkr_source.IBKRDataSource", lambda: Source())
    monkeypatch.setattr("src.ibkr_gateway_lock.ibkr_gateway_lock", ibkr_lock)
    monkeypatch.setattr("src.news_normalized.ibkr_adapter.ibkr_gateway_lock", ibkr_lock)
    monkeypatch.setattr(worker.sqlite3, "connect", lambda *a, **k: Conn())
    monkeypatch.setattr("src.market_data_admin.resolve_market_db_path", lambda: "market.db")
    monkeypatch.setattr("src.market_data_direct.market_write_lock", lambda: market_lock())
    monkeypatch.setattr("src.news_normalized.store.NormalizedNewsStore", Store)
    monkeypatch.setattr("src.news_normalized.writer.write_news_batch", write_news_batch)

    worker._run_worker(
        ["AAPL"],
        max_articles=1,
        max_body_fetches=1,
        gateway_lock_held=False,
    )

    assert events.count("ibkr_enter") == 1
    assert events.index("ibkr_enter") < events.index("market_enter")
    assert events.index("market_enter") < events.index("write")
    assert events.index("write") < events.index("market_exit")
    assert events.index("market_exit") < events.index("ibkr_exit")
    assert "provider_operation" in events


def test_legacy_ibkr_worker_script_delegates_to_src_module(monkeypatch):
    import scripts.collection.collect_ibkr_news_normalized as legacy
    import src.news_normalized.ibkr_cli as worker

    calls = []

    def fake_main(argv=None):
        calls.append(argv)
        return 17

    monkeypatch.setattr(worker, "main", fake_main)

    assert legacy.main(["--tickers", "AAPL"]) == 17
    assert calls == [["--tickers", "AAPL"]]


def test_ibkr_worker_module_startup_emits_only_sanitized_json(tmp_path):
    env = os.environ.copy()
    env["ARKSCOPE_MARKET_DB"] = str(tmp_path / "market_data.db")
    env["ARKSCOPE_PROFILE_DB"] = str(tmp_path / "profile_state.db")
    repo_root = Path(__file__).resolve().parents[1]

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.news_normalized.ibkr_cli",
            "--tickers",
            "FAKE",
            "--max-articles",
            "0",
            "--max-body-fetches",
            "0",
            "--gateway-lock-held",
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert proc.stdout.strip() == json.dumps(payload, sort_keys=True)
    assert payload["status"] in {"partial", "failed"}
    assert payload["articles_seen"] == 0
    assert payload["error_count"] == 0
    assert "FAKE" not in proc.stderr
