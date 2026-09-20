"""Stored data and allowed acquisition age are explicit caller choices."""

from datetime import datetime, timedelta, timezone
import json
from unittest.mock import Mock

import pytest

from data_sources import financial_datasets_client as module
from data_sources.financial_datasets_governance import FinancialDatasetsFailure
from tests.test_financial_datasets import MOCK_INCOME_RESPONSE, TEST_POLICY


@pytest.fixture
def fd(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "_FILE_CACHE_DIR", tmp_path / "cache")
    request = Mock()
    request.return_value.status_code = 200
    request.return_value.json.return_value = MOCK_INCOME_RESPONSE
    monkeypatch.setattr(module.requests, "get", request)
    client = module.FinancialDatasetsClient(api_key="offline", request_policy=None)
    return client, request


def old_file(*, age_days=2, data=None, **metadata):
    path = module._FILE_CACHE_DIR / "income_AAPL_annual.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    fetched = datetime.now(timezone.utc) - timedelta(days=age_days)
    path.write_text(json.dumps({
        "ticker": "AAPL", "fetched_at": fetched.isoformat(),
        "expires_at": (fetched + timedelta(days=180)).isoformat(),
        "data": MOCK_INCOME_RESPONSE if data is None else data, **metadata,
    }))
    return path, fetched


def test_default_reuses_recent_financials_and_exposes_the_policy(fd):
    client, request = fd
    old_file()
    assert client.get_income_statements("AAPL", period="annual", limit=1)
    assert client.observations[-1]["max_age_seconds"] == 7 * 86400
    assert client.observations[-1]["within_max_age"] is True
    request.assert_not_called()


def test_stored_is_explicit_offline_and_can_reopen_old_observations(fd):
    client, request = fd
    path, fetched = old_file(age_days=300)
    before = path.read_bytes()
    result = client.get_income_statements("AAPL", period="annual", limit=1, freshness="stored")
    assert result[0].report_period == "2025-09-27"
    assert client.observations[-1]["fetched_at"] == fetched.isoformat()
    assert client.observations[-1]["retrieval"] == "stored"
    assert client.observations[-1]["within_max_age"] is None
    assert "latest_period_verified" not in client.observations[-1]
    assert path.read_bytes() == before
    request.assert_not_called()


@pytest.mark.parametrize("age,limit,uses_cache", [(2, 86400, False), (2, 3*86400, True)])
def test_auto_uses_requested_acquisition_age_not_financial_period(fd, age, limit, uses_cache):
    client, request = fd
    old_file(age_days=age)
    if uses_cache:
        client.get_income_statements("AAPL", period="annual", limit=1, freshness="auto", max_age_seconds=limit)
        assert client.observations[-1]["within_max_age"] is True
    else:
        with pytest.raises(FinancialDatasetsFailure, match="policy_unconfigured"):
            client.get_income_statements("AAPL", period="annual", limit=1, freshness="auto", max_age_seconds=limit)
    request.assert_not_called()


@pytest.mark.parametrize("freshness,age", [("auto", "60"), ("auto", True), ("auto", -1), ("auto", 2.5), ("bad", 10), ("refresh", 10)])
def test_invalid_freshness_contract_never_calls_provider(fd, freshness, age):
    client, request = fd
    with pytest.raises(FinancialDatasetsFailure, match="freshness_invalid"):
        client.get_income_statements("AAPL", freshness=freshness, max_age_seconds=age)
    request.assert_not_called()


def test_stored_miss_never_becomes_paid_dispatch(fd):
    client, request = fd
    client._request_policy = TEST_POLICY
    with pytest.raises(FinancialDatasetsFailure, match="cache_miss"):
        client.get_income_statements("AAPL", freshness="stored")
    request.assert_not_called()


@pytest.mark.parametrize("metadata", [
    {"fetched_at": "bad"}, {"fetched_at": "2026-01-01T00:00:00"},
    {"fetched_at": "2099-01-01T00:00:00+00:00"}, {"ticker": "OTHER"},
])
def test_unverifiable_cache_is_not_presented_as_dated_data(fd, metadata):
    client, request = fd
    old_file(**metadata)
    with pytest.raises(FinancialDatasetsFailure, match="cache_miss"):
        client.get_income_statements("AAPL", period="annual", limit=1, freshness="stored")
    request.assert_not_called()


def test_old_cache_cannot_claim_more_periods_than_it_contains(fd):
    client, request = fd
    old_file()
    with pytest.raises(FinancialDatasetsFailure, match="cache_miss"):
        client.get_income_statements("AAPL", period="annual", limit=4, freshness="stored")
    request.assert_not_called()


def test_metadata_reader_is_read_only_and_preserves_expired_observation(fd, tmp_path):
    from src.tools.backends.local_market_backend import LocalMarketBackend

    client, request = fd
    db = tmp_path / "market.db"
    backend = LocalMarketBackend(market_db=str(db))
    fetched = datetime.now(timezone.utc) - timedelta(days=300)
    expires = fetched + timedelta(days=180)
    assert backend.set_financial_cache("income_AAPL_annual", "AAPL", MOCK_INCOME_RESPONSE,
        source="financial_datasets", fetched_at=fetched.isoformat(), expires_at=expires.isoformat())
    assert backend.get_financial_cache("income_AAPL_annual") is None
    before = db.read_bytes()
    client._cache_backend = backend
    assert client.get_income_statements("AAPL", period="annual", limit=1, freshness="stored")
    assert client.observations[-1]["fetched_at"] == fetched.isoformat()
    assert db.read_bytes() == before
    request.assert_not_called()


def test_stored_file_read_does_not_promote_or_reset_acquisition_time(fd):
    client, request = fd
    _, fetched = old_file(age_days=30)
    client._cache_backend = Mock()
    client._cache_backend.get_financial_cache_entry.return_value = None
    assert client.get_income_statements("AAPL", period="annual", limit=1, freshness="stored")
    client._cache_backend.set_financial_cache.assert_not_called()
    assert client.observations[-1]["fetched_at"] == fetched.isoformat()
    request.assert_not_called()


def test_new_cache_records_requested_limit_even_for_empty_response(fd):
    client, request = fd
    client._request_policy = TEST_POLICY
    request.return_value.json.return_value = {"income_statements": []}
    assert client.get_income_statements("AAPL", limit=4) == []
    assert client.get_income_statements("AAPL", limit=4, freshness="stored") == []
    with pytest.raises(FinancialDatasetsFailure, match="cache_miss"):
        client.get_income_statements("AAPL", limit=5, freshness="stored")
    assert request.call_count == 1


def test_lowercase_ticker_can_reopen_a_refreshed_file_without_another_request(fd):
    client, request = fd
    client._request_policy = TEST_POLICY
    fresh = client.get_income_statements("aapl", period="annual", limit=1)
    stored = client.get_income_statements("AAPL", period="annual", limit=1, freshness="stored")
    assert stored == fresh
    assert request.call_args.kwargs["params"]["ticker"] == "AAPL"
    assert request.call_count == 1
    assert client.observations[-1]["retrieval"] == "stored"


def test_refresh_failure_does_not_fall_back_to_cache(fd):
    import requests

    client, request = fd
    old_file()
    client._request_policy = TEST_POLICY
    request.side_effect = requests.Timeout("offline timeout")
    with pytest.raises(FinancialDatasetsFailure, match="request_failed"):
        client.get_income_statements("AAPL", period="annual", limit=1, freshness="refresh")
    assert request.call_count == 1
    assert client.observations == []


def test_auto_age_boundary_is_in_seconds_and_inclusive(fd, monkeypatch):
    client, request = fd
    fetched = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)
    _, _ = old_file(fetched_at=fetched.isoformat(), expires_at=(fetched + timedelta(days=180)).isoformat())
    current = [fetched + timedelta(seconds=10)]
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return current[0]
    monkeypatch.setattr(module, "datetime", Clock)
    assert client.get_income_statements("AAPL", period="annual", limit=1, freshness="auto", max_age_seconds=10)
    current[0] += timedelta(microseconds=1)
    with pytest.raises(FinancialDatasetsFailure, match="policy_unconfigured"):
        client.get_income_statements("AAPL", period="annual", limit=1, freshness="auto", max_age_seconds=10)
    request.assert_not_called()


@pytest.mark.parametrize("metadata", [{"source": "sec_edgar"}, {"period": "quarterly"}, {"ticker": "OTHER"}])
def test_other_source_or_query_cannot_serve_the_requested_cache(fd, metadata):
    client, request = fd
    response = {"income_statements": [{**MOCK_INCOME_RESPONSE["income_statements"][0], **metadata}]}
    old_file(data=response, source=metadata.get("source", "financial_datasets"))
    with pytest.raises(FinancialDatasetsFailure, match="cache_miss"):
        client.get_income_statements("AAPL", period="annual", limit=1, freshness="stored")
    request.assert_not_called()


@pytest.mark.parametrize("change", [{"ticker": "OTHER"}, {"period": "quarterly"}, {"report_period": "bad"}, {"currency": None}])
def test_provider_identity_or_period_mismatch_is_never_cached(fd, change):
    client, request = fd
    client._request_policy = TEST_POLICY
    request.return_value.json.return_value = {"income_statements": [{**MOCK_INCOME_RESPONSE["income_statements"][0], **change}]}
    with pytest.raises(FinancialDatasetsFailure, match="response_invalid"):
        client.get_income_statements("AAPL", period="annual", limit=1)
    assert request.call_count == 1
    assert not module._FILE_CACHE_DIR.exists()


@pytest.mark.parametrize("prefix,dataset,result_field", [
    ("balance", "balance_sheets", "balance_sheet"),
    ("cashflow", "cash_flow_statements", "cash_flow_statements"),
])
def test_stored_partial_data_survives_another_missing_dataset(fd, tmp_path, monkeypatch, prefix, dataset, result_field):
    from types import SimpleNamespace
    from src.fundamentals.cache import fundamentals_analysis_cache_key
    from src.tools.analysis_tools import get_fundamentals_analysis
    from src.tools.backends.local_market_backend import LocalMarketBackend

    client, request = fd
    monkeypatch.delenv("FINANCIAL_DATASETS_API_KEY", raising=False)
    backend = LocalMarketBackend(market_db=str(tmp_path / "market.db"))
    assert backend.set_financial_cache(fundamentals_analysis_cache_key("AAPL", "annual"), "AAPL", {"_negative": True})
    row = {key: MOCK_INCOME_RESPONSE["income_statements"][0][key]
           for key in ("ticker", "period", "report_period", "fiscal_period", "currency")}
    limit = 1 if prefix == "balance" else 2
    data = client._envelope({dataset: [row]}, "AAPL", "annual", limit)
    assert backend.set_financial_cache(f"fd_v1_{prefix}_AAPL_annual_{limit}", "AAPL", data, source="financial_datasets")
    dal = SimpleNamespace(_backend=backend, get_user_profile=lambda: {})
    result = get_fundamentals_analysis(dal, "AAPL", freshness="stored")
    assert result.data_source == "financial_datasets"
    assert len(getattr(result, result_field)) == 1
    assert result.snapshot_date == row["report_period"]
    assert result.source_observations[0]["dataset"] == dataset
    assert len(result.acquisition_gaps) == 2
    assert all(gap["dataset"] != dataset for gap in result.acquisition_gaps)
    request.assert_not_called()


@pytest.mark.parametrize("retention", [None, True, -1, 10**100])
def test_invalid_storage_policy_is_rejected_before_spending(fd, retention):
    client, request = fd
    client._request_policy = TEST_POLICY
    client._cache_days["annual"] = retention
    with pytest.raises(FinancialDatasetsFailure, match="cache_policy_invalid"):
        client.get_income_statements("AAPL", period="annual", limit=1)
    request.assert_not_called()
