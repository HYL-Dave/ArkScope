from __future__ import annotations


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
    import data_sources.sec_earnings_releases as earnings
    import data_sources.sec_edgar_financials as financials
    import data_sources.sec_filings as filings
    import data_sources.sec_insider_trades as insider

    assert SECEdgarDataSource().user_agent == "ArkScope ops@arkscope.test"
    assert filings._get_sec_user_agent() == "ArkScope ops@arkscope.test"
    assert earnings._get_sec_user_agent() == "ArkScope ops@arkscope.test"
    assert insider._get_sec_user_agent() == "ArkScope ops@arkscope.test"
    assert financials._get_sec_user_agent() == "ArkScope ops@arkscope.test"
