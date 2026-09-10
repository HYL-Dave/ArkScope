from __future__ import annotations


def test_sec_cik_lookup_loads_the_official_ticker_map_once(monkeypatch):
    from data_sources.sec_edgar_source import SECEdgarDataSource

    source = SECEdgarDataSource(user_agent="ArkScope test@example.com")
    source._cik_cache = {}
    calls = []
    monkeypatch.setattr(
        source,
        "_make_request",
        lambda url: calls.append(url) or {
            "0": {"cik_str": 712515, "ticker": "EA", "title": "Electronic Arts Inc."},
            "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        },
    )
    try:
        assert source.get_cik("ea") == "0000712515"
        assert source.get_cik("AAPL") == "0000320193"
        assert source.get_cik("MISSING") is None
        assert calls == ["https://www.sec.gov/files/company_tickers.json"]
    finally:
        source.close()


def _clear_sec_env(monkeypatch):
    for name in ("ARKSCOPE_SEC_USER_AGENT", "SEC_CONTACT_EMAIL", "SEC_USER_AGENT"):
        monkeypatch.delenv(name, raising=False)


def test_sec_user_agent_prefers_canonical_var(monkeypatch):
    from data_sources.sec_user_agent import get_sec_user_agent

    _clear_sec_env(monkeypatch)
    monkeypatch.setenv("ARKSCOPE_SEC_USER_AGENT", "ArkScope ops@arkscope.test")
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "legacy@old.test")

    assert get_sec_user_agent() == "ArkScope ops@arkscope.test"


def test_sec_user_agent_preserves_legacy_contact_email(monkeypatch):
    from data_sources.sec_user_agent import get_sec_user_agent

    _clear_sec_env(monkeypatch)
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "legacy@old.test")

    assert get_sec_user_agent() == "ArkScope legacy@old.test"


def test_sec_user_agent_preserves_legacy_raw_user_agent(monkeypatch):
    from data_sources.sec_user_agent import get_sec_user_agent

    _clear_sec_env(monkeypatch)
    monkeypatch.setenv("SEC_USER_AGENT", "LegacyRawUA contact@example.com")

    assert get_sec_user_agent() == "LegacyRawUA contact@example.com"


def test_sec_clients_use_canonical_user_agent(monkeypatch):
    _clear_sec_env(monkeypatch)
    monkeypatch.setenv("ARKSCOPE_SEC_USER_AGENT", "ArkScope ops@arkscope.test")

    from data_sources.sec_edgar_source import SECEdgarDataSource
    import data_sources.sec_edgar_financials as financials
    import data_sources.sec_insider_trades as insider

    source = SECEdgarDataSource()
    assert source.user_agent == "ArkScope ops@arkscope.test"
    assert source.transport.user_agent == "ArkScope ops@arkscope.test"
    assert insider.SECInsiderTrades().transport.user_agent == "ArkScope ops@arkscope.test"
    assert insider._get_sec_user_agent() == "ArkScope ops@arkscope.test"
    assert financials._get_sec_user_agent() == "ArkScope ops@arkscope.test"
