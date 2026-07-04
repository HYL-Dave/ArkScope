import json

import pytest


def test_prices_worker_requires_source_and_tickers():
    from src import prices_runtime as worker

    with pytest.raises(SystemExit) as caught:
        worker.parse_args([])

    assert caught.value.code == 2


def test_prices_worker_prints_sanitized_success_json(monkeypatch, capsys):
    from src import prices_runtime as worker

    monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)
    monkeypatch.setattr(
        worker,
        "_run_worker",
        lambda **kwargs: {
            "provider": "ibkr",
            "tickers_scanned": 2,
            "gaps_found": 1,
            "rows_added": 26,
            "errors": {"AAPL": "raw provider response should be bounded"},
        },
    )

    code = worker.main([
        "--source", "ibkr_prices",
        "--tickers", "AAPL,NVDA",
        "--gateway-lock-held",
    ])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "succeeded"
    assert payload["provider"] == "ibkr"
    assert payload["tickers_scanned"] == 2
    assert payload["rows_added"] == 26
    assert payload["error_count"] == 1
    assert "raw provider response" not in json.dumps(payload)


def test_prices_worker_prints_sanitized_error_json(monkeypatch, capsys):
    from src import prices_runtime as worker

    monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)

    def boom(**kwargs):
        raise RuntimeError("market_data.db write lock busy (timeout)")

    monkeypatch.setattr(worker, "_run_worker", boom)

    code = worker.main(["--source", "ibkr_prices", "--tickers", "AAPL"])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["error_class"] == "RuntimeError"
    assert payload["retryable"] is True
    assert payload["error"] == "market_data.db write lock busy (timeout)"


def test_apply_provider_config_passes_a_store(monkeypatch):
    # Regression: the worker called apply_env() with no store and died at startup
    # with TypeError on every real run (tests had mocked _apply_provider_config away).
    import src.prices_runtime as worker
    from src.data_provider_config import DataProviderConfigStore

    seen = {}
    monkeypatch.setattr(
        "src.data_provider_config.apply_env",
        lambda store: seen.setdefault("store", store) or frozenset(),
    )
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", "/tmp/claude-1001/nonexistent-profile.db")

    worker._apply_provider_config()

    assert isinstance(seen["store"], DataProviderConfigStore)
