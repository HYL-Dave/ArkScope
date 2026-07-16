from __future__ import annotations

from contextlib import contextmanager, nullcontext
import json
import os
from datetime import datetime
import logging
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

from src.news_normalized.models import (
    ArticleCandidate,
    BodyCandidate,
    BodyRetryBacklog,
    BodyRetrySelection,
    BodyStatus,
)
from src.news_normalized.store import NormalizedNewsStore


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


def test_runtime_gateway_discovers_once_and_reuses_provider_filter_for_headlines():
    from src.news_normalized.ibkr_runtime import IBKRRuntimeGateway

    class Source:
        def __init__(self):
            self.provider_calls = 0
            self.fetch_news_calls = []

        def get_news_providers_strict(self):
            self.provider_calls += 1
            return [
                {"code": "DJ-N", "name": "Dow Jones"},
                {"code": " dj-rta ", "name": "Dow Jones RTA"},
                {"code": "DJ-N", "name": "duplicate"},
            ]

        def fetch_news(self, *args, **kwargs):
            self.fetch_news_calls.append((args, kwargs))
            return []

        def disconnect(self):
            pass

    source = Source()
    gateway = IBKRRuntimeGateway(source)

    assert gateway.discover_news_provider_codes() == frozenset(
        {"DJ-N", "DJ-RTA"}
    )
    assert list(gateway.fetch_headlines("AAPL", None)) == []

    assert source.provider_calls == 1
    assert source.fetch_news_calls[0][1]["providers"] == "DJ-N+DJ-RTA"


def test_runtime_gateway_with_successful_empty_provider_set_makes_no_headline_call():
    from src.news_normalized.ibkr_runtime import IBKRRuntimeGateway

    class Source:
        def __init__(self):
            self.fetch_news_calls = []

        def get_news_providers_strict(self):
            return []

        def fetch_news(self, *args, **kwargs):
            self.fetch_news_calls.append((args, kwargs))
            return []

        def disconnect(self):
            pass

    source = Source()
    gateway = IBKRRuntimeGateway(source)

    assert gateway.discover_news_provider_codes() == frozenset()
    assert list(gateway.fetch_headlines("AAPL", None)) == []
    assert source.fetch_news_calls == []


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
        "retry_bodies_attempted",
        "retry_bodies_fetched",
        "tickers_scanned",
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


def test_worker_applies_provider_config_before_gateway_construction(monkeypatch, capsys):
    import src.news_normalized.ibkr_cli as worker

    order: list[str] = []
    monkeypatch.setattr(worker, "_apply_provider_config", lambda: order.append("apply"))

    def _fake_run_worker(*args, **kwargs):
        order.append("run_worker")
        raise RuntimeError("stop before provider construction")

    monkeypatch.setattr(worker, "_run_worker", _fake_run_worker)
    code = worker.main(["--tickers", "AAPL", "--max-articles", "0", "--max-body-fetches", "0"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert order == ["apply", "run_worker"]


def test_apply_provider_config_passes_a_store(monkeypatch):
    import src.news_normalized.ibkr_cli as worker
    from src.data_provider_config import DataProviderConfigStore

    seen = {}
    monkeypatch.setattr(
        "src.data_provider_config.apply_env",
        lambda store: seen.setdefault("store", store) or frozenset(),
    )
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", "/tmp/claude-1001/nonexistent-profile.db")

    worker._apply_provider_config()

    assert isinstance(seen["store"], DataProviderConfigStore)


def test_ibkr_worker_standalone_acquires_gateway_lock_before_market_lock(
    monkeypatch,
):
    from src.news_normalized import ibkr_cli as worker

    events = []

    class Source:
        def get_news_providers_strict(self):
            events.append("providers")
            return [{"code": "DJ-N", "name": "Dow Jones"}]

        def disconnect(self):
            events.append("disconnect")

    class Conn:
        def close(self):
            events.append("conn_close")

    class Store:
        def __init__(self, conn):
            events.append("store")
            self.conn = conn

        def select_ibkr_body_retries(
            self, *, now, limit, available_provider_codes=None
        ):
            assert available_provider_codes == frozenset({"DJ-N"})
            return BodyRetrySelection((), BodyRetryBacklog(0, 0, 0, None))

        def summarize_ibkr_body_backlog(
            self, *, now, available_provider_codes=None
        ):
            assert available_provider_codes == frozenset({"DJ-N"})
            return BodyRetryBacklog(0, 0, 0, None)

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

    def write_news_batch(store, provider, tickers, budget, *, project_legacy=False, **kwargs):
        events.append("write")
        with provider.operation():
            events.append("provider_operation")
        return {"status": "succeeded", "errors": {}}

    seen_source_kwargs = {}

    def _fake_ibkr_source(**kwargs):
        seen_source_kwargs.update(kwargs)
        return Source()

    monkeypatch.delenv("IBKR_CLIENT_ID", raising=False)
    monkeypatch.setattr("data_sources.ibkr_source.IBKRDataSource", _fake_ibkr_source)
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
        max_retry_body_fetches=25,
        gateway_lock_held=False,
    )

    assert events.count("ibkr_enter") == 1
    assert "provider_operation" in events
    # news domain rides its own partitioned client id (base 1 + 30), never the raw base
    assert seen_source_kwargs.get("client_id") == 31


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
            "--max-retry-body-fetches",
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


def test_ibkr_worker_passes_market_lock_factory_without_outer_write_lock(monkeypatch):
    from src.news_normalized import ibkr_cli

    calls = {}

    class _Source:
        def __init__(self, client_id=None):
            self.client_id = client_id

    class _Gateway:
        def __init__(self, source):
            self.source = source
        def discover_news_provider_codes(self):
            return frozenset({"DJ-N"})
        def close(self):
            calls["closed"] = True

    class _Provider:
        source = "ibkr"
        def __init__(self, gateway, acquire_gateway_lock):
            self.gateway = gateway
            self.acquire_gateway_lock = acquire_gateway_lock

    class _Store:
        def __init__(self, conn):
            self.conn = conn

        def select_ibkr_body_retries(
            self, *, now, limit, available_provider_codes=None
        ):
            assert available_provider_codes == frozenset({"DJ-N"})
            return BodyRetrySelection((), BodyRetryBacklog(0, 0, 0, None))

        def summarize_ibkr_body_backlog(
            self, *, now, available_provider_codes=None
        ):
            assert available_provider_codes == frozenset({"DJ-N"})
            return BodyRetryBacklog(0, 0, 0, None)

    def fake_write_news_batch(store, provider, tickers, budget, **kwargs):
        calls["kwargs"] = kwargs
        return {
            "status": "succeeded",
            "articles_seen": 0,
            "articles_inserted": 0,
            "bodies_fetched": 0,
            "errors": {},
            "continuation": None,
        }

    def forbidden_outer_lock(*args, **kwargs):
        raise AssertionError("outer market_write_lock must not wrap the whole worker")

    monkeypatch.setattr("data_sources.ibkr_source.IBKRDataSource", _Source)
    monkeypatch.setattr("src.news_normalized.ibkr_runtime.IBKRRuntimeGateway", _Gateway)
    monkeypatch.setattr("src.news_normalized.ibkr_adapter.IBKRNormalizedProvider", _Provider)
    monkeypatch.setattr("src.news_normalized.store.NormalizedNewsStore", _Store)
    monkeypatch.setattr("src.news_normalized.writer.write_news_batch", fake_write_news_batch)
    monkeypatch.setattr("src.market_data_direct.market_write_lock", forbidden_outer_lock)
    monkeypatch.setattr("src.market_data_admin.resolve_market_db_path", lambda: ":memory:")

    out = ibkr_cli._run_worker(
        ["AAPL"],
        max_articles=10,
        max_body_fetches=2,
        max_retry_body_fetches=25,
        gateway_lock_held=True,
    )

    assert out["status"] == "succeeded"
    assert "write_lock_factory" in calls["kwargs"]
    assert calls["kwargs"]["project_legacy"] is True
    assert calls["closed"] is True


def test_sanitize_worker_error_marks_market_lock_busy_retryable():
    from src.news_normalized.ibkr_cli import sanitize_worker_error

    payload = sanitize_worker_error(
        TimeoutError("market_data.db write lock busy (timeout)")
    )

    assert payload["status"] == "failed"
    assert payload["error_classes"] == ["TimeoutError"]
    assert payload["retryable"] is True
    assert payload["error"] == "market_data.db write lock busy (timeout)"


def test_sanitize_worker_error_does_not_mark_generic_timeout_retryable():
    from src.news_normalized.ibkr_cli import sanitize_worker_error

    payload = sanitize_worker_error(TimeoutError("provider request timed out"))

    assert payload["status"] == "failed"
    assert payload["error_classes"] == ["TimeoutError"]
    assert payload["retryable"] is False
    assert payload["error"] == ""


class _WorkerSource:
    def __init__(self, client_id=None):
        self.client_id = client_id

    def disconnect(self):
        pass


class _WorkerGateway:
    def __init__(self, source):
        self.source = source

    def discover_news_provider_codes(self):
        return frozenset({"DJ-N"})

    def close(self):
        self.source.disconnect()


class _WorkerProvider:
    source = "ibkr"

    def __init__(self, rows_by_ticker=None, body_results=None):
        self.rows_by_ticker = rows_by_ticker or {}
        self.body_results = body_results or {}
        self.events = []
        self.body_calls = []

    def operation(self):
        return nullcontext()

    def fetch_articles(self, ticker, since_iso):
        self.events.append(("metadata", ticker))
        return list(self.rows_by_ticker.get(ticker, ()))

    def fetch_body(self, candidate):
        local_key = candidate.provider_article_id
        self.events.append(("body", local_key))
        self.body_calls.append(local_key)
        return self.body_results.get(
            local_key,
            BodyCandidate(
                status=BodyStatus.FETCHED,
                raw_body=f"body for {local_key}",
                raw_format="text",
            ),
        )


def _headline(label: str, *, body: BodyCandidate | None = None) -> ArticleCandidate:
    return ArticleCandidate(
        source="ibkr",
        provider_article_id=f"DJ-N${label}",
        title=f"Synthetic {label}",
        publisher="DJ-N",
        published_at="2026-07-15T10:00:00Z",
        related_tickers=("AAPL",),
        body=body or BodyCandidate(status=BodyStatus.PENDING),
    )


def _seed_body_row(
    db_path,
    label: str,
    *,
    status: str = "pending",
    attempts: int = 0,
    next_retry_at: str | None = None,
    provider_id: str | None = None,
    publisher: str = "DJ-N",
) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    store = NormalizedNewsStore(conn)
    article_id = store.upsert(
        ArticleCandidate(
            source="ibkr",
            provider_article_id=provider_id or f"{publisher}${label}",
            title=f"Synthetic {label}",
            publisher=publisher,
            published_at="2026-07-15T10:00:00Z",
            related_tickers=("AAPL",),
            body=BodyCandidate(status=BodyStatus.PENDING),
        )
    ).article_id
    conn.execute(
        "UPDATE news_article_bodies "
        "SET body_status=?,fetch_attempts=?,next_retry_at=? WHERE article_id=?",
        (status, attempts, next_retry_at, article_id),
    )
    conn.commit()
    conn.close()
    return article_id


def _run_real_worker(
    monkeypatch,
    db_path,
    provider,
    *,
    store_cls=NormalizedNewsStore,
    max_articles=10,
    max_body_fetches=10,
    max_retry_body_fetches=25,
    available_provider_codes=frozenset({"DJ-N"}),
):
    from src.news_normalized import ibkr_cli as worker
    from src.news_normalized import writer as writer_module

    real_write = writer_module.write_news_batch

    def write_without_legacy_projection(store, provider, tickers, budget, **kwargs):
        kwargs["project_legacy"] = False
        return real_write(store, provider, tickers, budget, **kwargs)

    monkeypatch.setattr("data_sources.ibkr_source.IBKRDataSource", _WorkerSource)
    class WorkerGateway(_WorkerGateway):
        def discover_news_provider_codes(self):
            return available_provider_codes

    monkeypatch.setattr(
        "src.news_normalized.ibkr_runtime.IBKRRuntimeGateway", WorkerGateway
    )
    monkeypatch.setattr(
        "src.news_normalized.ibkr_adapter.IBKRNormalizedProvider",
        lambda gateway, acquire_gateway_lock: provider,
    )
    monkeypatch.setattr("src.news_normalized.store.NormalizedNewsStore", store_cls)
    monkeypatch.setattr(
        "src.news_normalized.writer.write_news_batch", write_without_legacy_projection
    )
    monkeypatch.setattr(
        "src.market_data_admin.resolve_market_db_path", lambda: str(db_path)
    )
    monkeypatch.setattr(
        "src.market_data_direct.market_write_lock", lambda: nullcontext()
    )
    return worker._run_worker(
        ["AAPL"],
        max_articles=max_articles,
        max_body_fetches=max_body_fetches,
        max_retry_body_fetches=max_retry_body_fetches,
        gateway_lock_held=True,
    )


def test_ibkr_worker_accepts_separate_nonnegative_retry_budget():
    from src.news_normalized import ibkr_cli as worker

    args = worker.parse_args(
        ["--tickers", "AAPL", "--max-retry-body-fetches", "0"]
    )

    assert args.max_retry_body_fetches == 0


def test_ibkr_worker_rejects_negative_retry_budget(capsys):
    from src.news_normalized import ibkr_cli as worker

    with pytest.raises(SystemExit) as caught:
        worker.parse_args(
            ["--tickers", "AAPL", "--max-retry-body-fetches", "-1"]
        )

    assert caught.value.code == 2
    assert "budgets must be non-negative" in capsys.readouterr().err


def test_worker_selects_due_bodies_and_passes_local_ids_separately(
    monkeypatch,
):
    from src.news_normalized import ibkr_cli as worker
    from src.news_normalized.models import WriterResult

    calls = {}

    class Store:
        def __init__(self, conn):
            self.conn = conn

        def select_ibkr_body_retries(
            self, *, now, limit, available_provider_codes=None
        ):
            calls["selection_limit"] = limit
            calls["selection_provider_codes"] = available_provider_codes
            return BodyRetrySelection(
                article_ids=(41, 42),
                backlog=BodyRetryBacklog(2, 0, 2, None),
            )

        def summarize_ibkr_body_backlog(
            self, *, now, available_provider_codes=None
        ):
            calls["summary_provider_codes"] = available_provider_codes
            return BodyRetryBacklog(0, 0, 0, None)

    def fake_write(store, provider, tickers, budget, **kwargs):
        calls["retry_body_ids"] = kwargs["retry_body_ids"]
        calls["tickers"] = tuple(tickers)
        return WriterResult("succeeded", 0, 0, 0, {}, None)

    monkeypatch.setattr("data_sources.ibkr_source.IBKRDataSource", _WorkerSource)
    monkeypatch.setattr(
        "src.news_normalized.ibkr_runtime.IBKRRuntimeGateway", _WorkerGateway
    )
    monkeypatch.setattr(
        "src.news_normalized.ibkr_adapter.IBKRNormalizedProvider",
        lambda gateway, acquire_gateway_lock: _WorkerProvider(),
    )
    monkeypatch.setattr("src.news_normalized.store.NormalizedNewsStore", Store)
    monkeypatch.setattr("src.news_normalized.writer.write_news_batch", fake_write)
    monkeypatch.setattr("src.market_data_admin.resolve_market_db_path", lambda: ":memory:")
    monkeypatch.setattr(
        "src.market_data_direct.market_write_lock", lambda: nullcontext()
    )

    result = worker._run_worker(
        ["AAPL"],
        max_articles=10,
        max_body_fetches=10,
        max_retry_body_fetches=2,
        gateway_lock_held=True,
    )

    assert calls == {
        "selection_limit": 2,
        "selection_provider_codes": frozenset({"DJ-N"}),
        "summary_provider_codes": frozenset({"DJ-N"}),
        "retry_body_ids": (41, 42),
        "tickers": ("AAPL",),
    }
    assert result["body_backlog"]["status"] == "ok"


def test_worker_does_not_call_body_for_unentitled_provider_and_reports_count(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "market_data.db"
    _seed_body_row(
        db_path,
        "blocked",
        provider_id="FLY$blocked",
        publisher="FLY",
    )
    provider = _WorkerProvider({"AAPL": [_headline("fresh")]})

    result = _run_real_worker(
        monkeypatch,
        db_path,
        provider,
        available_provider_codes=frozenset({"DJ-N"}),
    )

    assert "FLY$blocked" not in provider.body_calls
    assert provider.body_calls == ["DJ-N$fresh"]
    assert result["body_backlog"]["provider_not_entitled"] == 1
    assert result["fresh_status"] == "succeeded"


def test_worker_provider_discovery_failure_performs_no_retry_or_fresh_calls(
    monkeypatch,
    capsys,
):
    from src.news_normalized import ibkr_cli as worker

    events = []
    secret = "licensed provider payload FLY"

    class Source:
        def __init__(self, client_id=None):
            self.client_id = client_id

        def disconnect(self):
            events.append("disconnect")

    class Gateway:
        def __init__(self, source):
            self.source = source

        def discover_news_provider_codes(self):
            events.append("discover")
            raise RuntimeError(secret)

        def close(self):
            self.source.disconnect()

    def forbidden(*args, **kwargs):
        raise AssertionError("discovery failure must stop before store/provider work")

    monkeypatch.setattr("data_sources.ibkr_source.IBKRDataSource", Source)
    monkeypatch.setattr(
        "src.news_normalized.ibkr_runtime.IBKRRuntimeGateway", Gateway
    )
    monkeypatch.setattr(
        "src.news_normalized.ibkr_adapter.IBKRNormalizedProvider", forbidden
    )
    monkeypatch.setattr("src.news_normalized.store.NormalizedNewsStore", forbidden)
    monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)

    code = worker.main(["--tickers", "AAPL", "--gateway-lock-held"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["status"] == "failed"
    assert payload["error_classes"] == ["RuntimeError"]
    assert payload["error"] == ""
    assert secret not in repr(payload)
    assert events == ["discover", "disconnect"]


def test_worker_stdout_preserves_only_aggregate_entitlement_block_count():
    from src.news_normalized.ibkr_cli import sanitize_worker_result

    payload = sanitize_worker_result(
        {
            "status": "succeeded",
            "body_backlog": {
                "status": "ok",
                "due_now": 0,
                "scheduled_later": 0,
                "never_attempted": 0,
                "earliest_next_retry_at": None,
                "provider_not_entitled": 78,
            },
        }
    )

    assert payload["body_backlog"]["provider_not_entitled"] == 78
    assert "FLY" not in repr(payload)


def test_worker_stdout_rejects_invalid_entitlement_block_count():
    from src.news_normalized.ibkr_cli import sanitize_worker_result

    for value in (-1, 1.5, True, "78"):
        payload = sanitize_worker_result(
            {
                "status": "succeeded",
                "body_backlog": {
                    "status": "ok",
                    "due_now": 0,
                    "scheduled_later": 0,
                    "never_attempted": 0,
                    "earliest_next_retry_at": None,
                    "provider_not_entitled": value,
                },
            }
        )
        assert payload["body_backlog"] == {"status": "unavailable"}


def test_due_body_older_than_three_hundred_headlines_is_still_attempted(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "market_data.db"
    _seed_body_row(db_path, "old-due")
    provider = _WorkerProvider(
        {"AAPL": [_headline(f"new-{index:03d}") for index in range(300)]}
    )

    result = _run_real_worker(
        monkeypatch,
        db_path,
        provider,
        max_articles=300,
        max_body_fetches=0,
        max_retry_body_fetches=1,
    )

    assert provider.events[0] == ("body", "DJ-N$old-due")
    assert provider.events[1] == ("metadata", "AAPL")
    assert result["retry_bodies_attempted"] == 1
    assert result["articles_seen"] == 300


def test_retry_queue_query_failure_keeps_fresh_scan_and_marks_partial(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "market_data.db"

    class SelectionFailureStore(NormalizedNewsStore):
        def select_ibkr_body_retries(
            self, *, now, limit, available_provider_codes=None
        ):
            raise sqlite3.OperationalError("queue read failed")

    provider = _WorkerProvider({"AAPL": [_headline("fresh")]})

    result = _run_real_worker(
        monkeypatch,
        db_path,
        provider,
        store_cls=SelectionFailureStore,
        max_body_fetches=1,
    )

    assert ("metadata", "AAPL") in provider.events
    assert result["retry_status"] == "failed"
    assert result["fresh_status"] == "succeeded"
    assert result["status"] == "partial"


def test_post_run_backlog_failure_is_unavailable_not_zero(tmp_path, monkeypatch):
    db_path = tmp_path / "market_data.db"

    class SummaryFailureStore(NormalizedNewsStore):
        def summarize_ibkr_body_backlog(
            self, *, now, available_provider_codes=None
        ):
            raise sqlite3.OperationalError("summary read failed")

    result = _run_real_worker(
        monkeypatch,
        db_path,
        _WorkerProvider({"AAPL": []}),
        store_cls=SummaryFailureStore,
    )

    assert result["status"] == "partial"
    assert result["retry_status"] == "failed"
    assert result["fresh_status"] == "succeeded"
    assert result["body_backlog"] == {"status": "unavailable"}


def test_future_due_backlog_keeps_worker_succeeded(tmp_path, monkeypatch):
    db_path = tmp_path / "market_data.db"
    _seed_body_row(
        db_path,
        "future",
        status="failed",
        attempts=1,
        next_retry_at="2099-01-01T00:00:00Z",
    )
    provider = _WorkerProvider({"AAPL": []})

    result = _run_real_worker(monkeypatch, db_path, provider)

    assert provider.body_calls == []
    assert result["status"] == "succeeded"
    assert result["body_backlog"]["scheduled_later"] == 1


def test_retryable_10172_reports_partial_and_scheduled_backlog(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "market_data.db"
    _seed_body_row(db_path, "retry-10172")
    provider = _WorkerProvider(
        {"AAPL": []},
        {
            "DJ-N$retry-10172": BodyCandidate(
                status=BodyStatus.FAILED,
                error="IBKR news article unavailable (10172)",
                error_code=10172,
            )
        },
    )
    monkeypatch.setattr(
        "src.news_normalized.store._now", lambda: "2099-01-01T00:00:00Z"
    )

    result = _run_real_worker(monkeypatch, db_path, provider)

    assert result["status"] == "partial"
    assert result["retry_status"] == "partial"
    assert result["fresh_status"] == "succeeded"
    assert result["body_backlog"]["scheduled_later"] == 1


def test_retry_and_fresh_limits_are_independent(tmp_path, monkeypatch):
    db_path = tmp_path / "market_data.db"
    _seed_body_row(db_path, "old")
    provider = _WorkerProvider(
        {"AAPL": [_headline("fresh-1"), _headline("fresh-2")]}
    )

    result = _run_real_worker(
        monkeypatch,
        db_path,
        provider,
        max_articles=2,
        max_body_fetches=1,
        max_retry_body_fetches=1,
    )

    assert provider.body_calls == ["DJ-N$old", "DJ-N$fresh-1"]
    assert result["retry_bodies_attempted"] == 1
    assert result["retry_bodies_fetched"] == 1
    assert result["bodies_fetched"] == 2
    assert result["fresh_status"] == "partial"


def test_sanitized_retry_result_contains_no_provider_ids_or_body_content():
    from src.news_normalized.ibkr_cli import sanitize_worker_result

    provider_id = "DJ-N$private"
    licensed_body = "licensed body text"
    payload = sanitize_worker_result(
        {
            "status": "partial",
            "articles_seen": 1,
            "articles_inserted": 0,
            "bodies_fetched": 0,
            "retry_bodies_attempted": 1,
            "retry_bodies_fetched": 0,
            "tickers_scanned": 1,
            "retry_status": "partial",
            "fresh_status": "succeeded",
            "errors": {f"retry:{provider_id}": licensed_body},
            "body_backlog": {
                "status": "ok",
                "due_now": 0,
                "scheduled_later": 1,
                "never_attempted": 0,
                "earliest_next_retry_at": "2026-07-15T12:00:00Z",
            },
        }
    )

    rendered = json.dumps(payload, sort_keys=True)
    assert payload["legs"] == {"retry": "partial", "fresh": "succeeded"}
    assert payload["body_backlog"]["scheduled_later"] == 1
    assert provider_id not in rendered
    assert licensed_body not in rendered
