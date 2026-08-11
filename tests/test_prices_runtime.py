import json

import pytest


def _collector_result(*, status="succeeded", scanned=2, errors=None, unresolved=None):
    errors = errors or {}
    unresolved = unresolved or []
    return {
        "status": status,
        "provider": "ibkr",
        "tickers_scanned": scanned,
        "succeeded_ticker_count": scanned - len(errors),
        "gaps_found": len(unresolved),
        "rows_added": 26 if status == "succeeded" else 1,
        "errors": errors,
        "unresolved_after_fetch_count": len(unresolved),
        "unresolved_after_fetch_tickers": unresolved,
    }


def test_prices_worker_requires_tickers_without_source_selector():
    from src import prices_runtime as worker

    with pytest.raises(SystemExit) as caught:
        worker.parse_args([])

    assert caught.value.code == 2

    parsed = worker.parse_args(["--tickers", "AAPL,MSFT"])
    assert parsed.tickers == "AAPL,MSFT"
    assert parsed.provider == "ibkr"
    assert not hasattr(parsed, "source")

    with pytest.raises(SystemExit) as retired:
        worker.parse_args(["--source", "ibkr_prices", "--tickers", "AAPL"])
    assert retired.value.code == 2


def test_prices_worker_prints_sanitized_success_json(monkeypatch, capsys):
    from src import prices_runtime as worker

    monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)
    monkeypatch.setattr(
        worker,
        "_run_worker",
        lambda **kwargs: _collector_result(
            status="succeeded", errors={}, unresolved=[],
        ),
    )

    code = worker.main([
        "--tickers", "AAPL,NVDA",
        "--gateway-lock-held",
    ])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "succeeded"
    assert payload["provider"] == "ibkr"
    assert payload["tickers_scanned"] == 2
    assert payload["succeeded_ticker_count"] == 2
    assert payload["gaps_found"] == 0
    assert payload["rows_added"] == 26
    assert payload["error_count"] == 0
    assert payload["error_tickers"] == []
    assert payload["unresolved_after_fetch_count"] == 0
    assert payload["unresolved_after_fetch_tickers"] == []
    assert "raw provider response" not in json.dumps(payload)


def test_prices_worker_prints_sanitized_error_json(monkeypatch, capsys):
    from src import prices_runtime as worker

    monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)

    def boom(**kwargs):
        raise RuntimeError("market_data.db write lock busy (timeout)")

    monkeypatch.setattr(worker, "_run_worker", boom)

    code = worker.main(["--tickers", "AAPL"])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["error_class"] == "RuntimeError"
    assert payload["retryable"] is True
    assert payload["error"] == "market_data.db write lock busy (timeout)"

    def private_boom(**kwargs):
        raise RuntimeError("PRIVATE_PROVIDER_PATH")

    monkeypatch.setattr(worker, "_run_worker", private_boom)
    assert worker.main(["--tickers", "AAPL"]) == 1
    private_payload = json.loads(capsys.readouterr().out)
    assert private_payload["status"] == "failed"
    assert private_payload["error_class"] == "RuntimeError"
    assert private_payload["retryable"] is False
    assert private_payload["error"] == ""
    assert "PRIVATE_PROVIDER_PATH" not in json.dumps(private_payload)


def test_prices_worker_preserves_allowlisted_gateway_error_code_only():
    from src import prices_runtime as worker

    class GatewayUnavailable(RuntimeError):
        error_code = "ibkr_gateway_unavailable"

    payload = worker.sanitize_error(GatewayUnavailable("PRIVATE_PROVIDER_TEXT"))

    assert payload == {
        "status": "failed",
        "error_class": "GatewayUnavailable",
        "error": "",
        "error_code": "ibkr_gateway_unavailable",
        "retryable": False,
    }
    assert "PRIVATE_PROVIDER_TEXT" not in json.dumps(payload)


def test_prices_worker_prints_sanitized_partial_json_and_exits_zero(monkeypatch, capsys):
    from src import prices_runtime as worker

    monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)
    monkeypatch.setattr(
        worker, "_run_worker",
        lambda **kwargs: _collector_result(
            status="partial", errors={"LCID": "PRIVATE_PROVIDER_TEXT"},
            unresolved=["LCID"],
        ),
    )
    assert worker.main(["--tickers", "AAPL,LCID"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "status": "partial", "provider": "ibkr", "tickers_scanned": 2,
        "succeeded_ticker_count": 1, "gaps_found": 1, "rows_added": 1,
        "error_count": 1, "error_tickers": ["LCID"],
        "unresolved_after_fetch_count": 1,
        "unresolved_after_fetch_tickers": ["LCID"],
    }
    assert "PRIVATE_PROVIDER_TEXT" not in json.dumps(payload)


def test_prices_worker_prints_sanitized_failed_result_json_and_exits_nonzero(
    monkeypatch, capsys,
):
    from src import prices_runtime as worker

    monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)
    monkeypatch.setattr(
        worker, "_run_worker",
        lambda **kwargs: _collector_result(
            status="failed", scanned=2,
            errors={"BAD": "PRIVATE_A", "LCID": "PRIVATE_B"},
            unresolved=["LCID"],
        ),
    )
    assert worker.main(["--tickers", "BAD,LCID"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["error_count"] == 2
    assert payload["succeeded_ticker_count"] == 0
    assert payload["error_tickers"] == ["BAD", "LCID"]
    assert "PRIVATE_" not in json.dumps(payload)


def test_prices_worker_rejects_unknown_status_and_malformed_counts(monkeypatch, capsys):
    from src import prices_runtime as worker

    invalid = _collector_result()
    invalid["status"] = "complete"
    with pytest.raises(ValueError, match="status"):
        worker.sanitize_result(invalid)
    for value in (-1, 1.5, True, "2"):
        invalid = _collector_result()
        invalid["rows_added"] = value
        with pytest.raises(ValueError, match="rows_added"):
            worker.sanitize_result(invalid)
    monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)
    monkeypatch.setattr(
        worker, "_run_worker",
        lambda **kwargs: {**_collector_result(), "status": "PRIVATE_STATUS"},
    )
    assert worker.main(["--tickers", "AAPL,NVDA"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["error_class"] == "ValueError"
    assert "PRIVATE_STATUS" not in json.dumps(payload)


def test_prices_worker_bounds_sorts_and_sanitizes_ticker_lists():
    from src import prices_runtime as worker

    tickers = [f"T{i:02d}" for i in range(30)]
    result = _collector_result(
        status="failed", scanned=30,
        errors={ticker: "PRIVATE" for ticker in reversed(tickers)},
        unresolved=list(reversed(tickers)),
    )
    payload = worker.sanitize_result(result)
    assert payload["error_count"] == 30
    assert payload["unresolved_after_fetch_count"] == 30
    assert payload["error_tickers"] == tickers[:25]
    assert payload["unresolved_after_fetch_tickers"] == tickers[:25]
    for malformed_ids in (["AAPL\nPRIVATE"], [123]):
        malformed = {
            **result,
            "unresolved_after_fetch_tickers": malformed_ids,
            "unresolved_after_fetch_count": len(malformed_ids),
        }
        with pytest.raises(ValueError, match="unresolved_after_fetch_tickers"):
            worker.sanitize_result(malformed)


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
