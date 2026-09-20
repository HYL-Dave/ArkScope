"""Same-query joins and failed-owner behavior use real process/thread locks."""

from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import threading
from unittest.mock import Mock

import pytest

from data_sources import financial_datasets_client as module
from data_sources.financial_datasets_governance import FinancialDatasetsFailure
from src.fundamentals import reuse
from tests.test_financial_datasets import MOCK_INCOME_RESPONSE, TEST_POLICY


@pytest.mark.parametrize("freshness", ["auto", "refresh"])
@pytest.mark.parametrize("outcome", ["success", "failure", "unsaved"])
@pytest.mark.parametrize("storage", ["file", "sqlite"])
def test_same_query_across_processes_never_repeats_an_inflight_request(
    freshness, outcome, storage, tmp_path, monkeypatch,
):
    from src.tools.backends.local_market_backend import LocalMarketBackend

    context = multiprocessing.get_context("fork")
    entered, release, waited = context.Event(), context.Event(), context.Event()
    results = context.Queue()
    requests = context.Value("i", 0)
    monkeypatch.setattr(module, "_FILE_CACHE_DIR", tmp_path / "cache")
    real_sleep = reuse.time.sleep

    def sleep(seconds):
        waited.set()
        real_sleep(seconds)

    def request(*args, **kwargs):
        with requests.get_lock():
            requests.value += 1
        entered.set()
        assert release.wait(10)
        if outcome == "failure":
            raise FinancialDatasetsFailure("financial_datasets_response_invalid")
        return Mock(status_code=200, json=lambda: MOCK_INCOME_RESPONSE)

    monkeypatch.setattr(reuse.time, "sleep", sleep)
    monkeypatch.setattr(module.requests, "get", request)
    if outcome == "unsaved":
        monkeypatch.setattr(module.FinancialDatasetsClient, "_write_file_cache", lambda *args: False)
        monkeypatch.setattr(LocalMarketBackend, "set_financial_cache", lambda *args, **kwargs: False)

    def worker(number):
        backend = None
        if storage == "sqlite":
            backend = LocalMarketBackend(market_db=str(tmp_path / "market.db"))
            module._FILE_CACHE_DIR = tmp_path / f"separate-process-{number}-fallback"
        client = module.FinancialDatasetsClient(api_key="offline-only", request_policy=TEST_POLICY, cache_backend=backend)
        try:
            rows = client.get_income_statements("AAPL", period="annual", limit=2, freshness=freshness)
            results.put(("ok", rows[0].revenue, client.observations[-1]))
        except FinancialDatasetsFailure as exc:
            results.put(("error", exc.code))

    processes = [context.Process(target=worker, args=(0,)), context.Process(target=worker, args=(1,))]
    try:
        processes[0].start()
        assert entered.wait(10)
        processes[1].start()
        assert waited.wait(10)
        release.set()
        values = [results.get(timeout=10), results.get(timeout=10)]
        for process in processes:
            process.join(10)
            assert process.exitcode == 0
    finally:
        release.set()
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(10)
        results.close()
        results.join_thread()
    assert requests.value == 1
    if outcome == "success":
        assert all(value[:2] == ("ok", MOCK_INCOME_RESPONSE["income_statements"][0]["revenue"]) for value in values)
        assert {value[2]["retrieval"] for value in values} == {"refreshed", "coalesced"}
        assert len({value[2]["fetched_at"] for value in values}) == 1
    else:
        assert ("error", "financial_datasets_refresh_result_unavailable") in values
        if outcome == "failure":
            assert ("error", "financial_datasets_response_invalid") in values
        else:
            assert next(value[2] for value in values if value[0] == "ok")["persisted"] is False


@pytest.mark.parametrize("difference", ["ticker", "period", "limit"])
def test_distinct_queries_do_not_join_or_block_each_other(difference, tmp_path, monkeypatch):
    monkeypatch.setattr(module, "_FILE_CACHE_DIR", tmp_path / "cache")
    entered, release = threading.Event(), threading.Event()

    def request(url, *, params, **kwargs):
        if params == {"ticker": "AAPL", "period": "annual", "limit": 2}:
            entered.set()
            assert release.wait(10)
        row = {**MOCK_INCOME_RESPONSE["income_statements"][0],
               "ticker": params["ticker"], "period": params["period"]}
        return Mock(status_code=200, json=lambda: {"income_statements": [row]})

    http = Mock(side_effect=request)
    monkeypatch.setattr(module.requests, "get", http)
    first = module.FinancialDatasetsClient(api_key="offline-only", request_policy=TEST_POLICY)
    second = module.FinancialDatasetsClient(api_key="offline-only", request_policy=TEST_POLICY)
    arguments = {"ticker": "AAPL", "period": "annual", "limit": 2}
    other = {**arguments, difference: {"ticker": "MSFT", "period": "quarterly", "limit": 4}[difference]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(first.get_income_statements, **arguments)
        try:
            assert entered.wait(10)
            unrelated = pool.submit(second.get_income_statements, **other)
            assert unrelated.result(timeout=5)
            assert not pending.done()
        finally:
            release.set()
        assert pending.result(timeout=5)
    assert http.call_count == 2


def test_lock_failure_never_dispatches(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "_FILE_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(reuse, "lock_dir", lambda: tmp_path)
    (tmp_path / "financial_acquisitions").write_text("not a directory")
    http = Mock(side_effect=AssertionError("missing lock is not permission to spend"))
    monkeypatch.setattr(module.requests, "get", http)
    client = module.FinancialDatasetsClient(api_key="offline-only", request_policy=TEST_POLICY)
    with pytest.raises(FinancialDatasetsFailure, match="refresh_lock_unavailable"):
        client.get_income_statements("AAPL")
    http.assert_not_called()


def test_busy_scope_returns_in_progress_without_new_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "_FILE_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(reuse, "_WAIT_SECONDS", 0)
    http = Mock(side_effect=AssertionError("a busy scope must not dispatch"))
    monkeypatch.setattr(module.requests, "get", http)
    client = module.FinancialDatasetsClient(api_key="offline-only", request_policy=TEST_POLICY)
    with reuse.acquisition_lock([str(module._FILE_CACHE_DIR.resolve()), "financial_datasets", "fd_v1_income_AAPL_annual_2"]):
        with pytest.raises(FinancialDatasetsFailure, match="refresh_in_progress"):
            client.get_income_statements("AAPL", period="annual", limit=2)
    http.assert_not_called()
