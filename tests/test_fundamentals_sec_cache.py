"""Retired SEC projections do not become common-read observations or authority."""

import pytest
from unittest.mock import Mock

from tests.financial_read_fixtures import financial_local
from src.tools.analysis_tools import get_fundamentals_analysis
from src.fundamentals.cache import fundamentals_analysis_cache_key


@pytest.mark.parametrize("freshness", ["stored", "auto", "refresh"])
@pytest.mark.parametrize("payload", [{"_negative": True},
    {"ticker": "AAPL", "data_source": "sec_edgar", "roe": 0.44, "snapshot_date": "2025-12-31"},
    {"ticker": "AAPL", "data_source": "ibkr", "market_cap": 999}])
def test_retired_projection_never_wins_or_triggers_sec(financial_local, monkeypatch, freshness, payload):
    dal, http, sec = financial_local
    key = fundamentals_analysis_cache_key("AAPL", "annual")
    assert dal._backend.set_financial_cache(key, "AAPL", payload, source="sec_edgar")
    before = dal._backend.get_financial_cache_entry(key)
    write = Mock(side_effect=AssertionError("retired cache may not be rewritten"))
    monkeypatch.setattr(dal._backend, "set_financial_cache", write)
    result = get_fundamentals_analysis(dal, "AAPL", freshness=freshness)
    assert result.status == "unavailable" and result.data_source == "none"
    assert result.roe is None and result.market_cap is None
    assert dal._backend.get_financial_cache_entry(key) == before
    http.assert_not_called()
    sec.assert_not_called()
    write.assert_not_called()


def test_user_agent_prefers_canonical_arkscope_var(monkeypatch):
    import data_sources.sec_edgar_financials as sec
    monkeypatch.setenv("ARKSCOPE_SEC_USER_AGENT", "ArkScope ops@arkscope.test")
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "legacy@old.test")
    assert sec._get_sec_user_agent() == "ArkScope ops@arkscope.test"  # canonical wins


def test_user_agent_back_compat_legacy_vars(monkeypatch):
    import data_sources.sec_edgar_financials as sec
    monkeypatch.delenv("ARKSCOPE_SEC_USER_AGENT", raising=False)
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "legacy@old.test")
    assert "legacy@old.test" in sec._get_sec_user_agent()  # legacy still honored
