from dataclasses import replace
import sqlite3
import pytest
from datetime import date, datetime

from src.security_lifecycle_schema import create_profile_schema
from src.security_lifecycle_listing_evidence import _evidence
from tests.test_security_lifecycle_provider_authority import NOW, events, record, terminal_records


class Provider:
    def __init__(self):
        self.directory_calls = []
        self.exact_calls = []

    def directories(self, tickers):
        self.directory_calls.append(tickers)
        return {
            ticker: tuple(_evidence(row) for row in (
                (record("eodhd_symbol_directory", "active", ticker=ticker), record("nasdaq_symbol_directory", "active", ticker=ticker, directory="nasdaq_listed"))
                if ticker == "LIVE" else tuple(replace(row, ticker=ticker) for row in terminal_records()[3:])
            )) for ticker in tickers
        }, ()

    def exact(self, ticker):
        self.exact_calls.append(ticker)
        from src.security_lifecycle_provider_authority import ticker_event_evidence
        from data_sources.lifecycle_provider_census_transport import MassiveTickerEventsResult
        from tests.test_security_lifecycle_provider_authority import FIGI
        timeline = ticker_event_evidence(ticker, MassiveTickerEventsResult(FIGI, (), "https://api.massive.com/vX/reference/tickers/BBG001YKDND6/events", "b" * 64, 100, latest_ticker=ticker), at=NOW)
        return tuple(_evidence(replace(row, ticker=ticker)) for row in terminal_records()[:3]) + (timeline,), ()

    def diagnostics(self):
        return {"massive_requests": len(self.exact_calls) * 4, "eodhd_requests": len(self.directory_calls) * 2}


def test_directory_refresh_finds_new_cases_without_sec_and_exact_pass_is_bounded(tmp_path):
    from src.security_lifecycle_provider_scan import refresh_provider_checks
    from src.security_lifecycle_provider_store import ProviderCheckStore
    profile = tmp_path / "profile.db"
    with sqlite3.connect(profile) as conn:
        create_profile_schema(conn)
    provider = Provider()
    result = refresh_provider_checks(ProviderCheckStore(profile), tickers=("LIVE", "OLD", "SECOND"), at=NOW, provider=provider)
    assert provider.directory_calls == [("LIVE", "OLD", "SECOND")]
    assert provider.exact_calls == ["OLD"]
    assert result["exact_ticker"] == "OLD"
    assert ProviderCheckStore(profile).latest()["LIVE"]["state"] == "active"
    assert ProviderCheckStore(profile).latest()["OLD"]["state"] == "terminal"
    provider2 = Provider()
    refresh_provider_checks(ProviderCheckStore(profile), tickers=("LIVE", "OLD", "SECOND"), at="2026-09-05T01:05:00Z", provider=provider2)
    assert provider2.directory_calls == []
    assert provider2.exact_calls == ["SECOND"]


def test_provider_failure_is_visible_and_cannot_become_terminal_or_repeat_each_tick(tmp_path):
    from src.security_lifecycle_provider_scan import refresh_provider_checks
    from src.security_lifecycle_provider_store import ProviderCheckStore
    profile = tmp_path / "profile.db"
    with sqlite3.connect(profile) as conn:
        create_profile_schema(conn)
    provider = Provider()
    provider.exact = lambda ticker: ((), ("massive_rate_limited",))
    store = ProviderCheckStore(profile)
    refresh_provider_checks(store, tickers=("OLD",), at=NOW, provider=provider)
    assert store.latest()["OLD"]["state"] == "unresolved"
    assert store.latest()["OLD"]["blockers"] == ["massive_rate_limited"]
    next_provider = Provider()
    refresh_provider_checks(store, tickers=("OLD",), at="2026-09-05T01:05:00Z", provider=next_provider)
    assert not next_provider.directory_calls
    assert not next_provider.exact_calls


def test_empty_or_changed_universe_does_not_infer_terminal_from_absence(tmp_path):
    from src.security_lifecycle_provider_scan import refresh_provider_checks
    from src.security_lifecycle_provider_store import ProviderCheckStore
    profile = tmp_path / "profile.db"
    with sqlite3.connect(profile) as conn:
        create_profile_schema(conn)
    store = ProviderCheckStore(profile)
    refresh_provider_checks(store, tickers=("LIVE",), at=NOW, provider=Provider())
    before = store.latest()
    provider = Provider()
    refresh_provider_checks(store, tickers=(), at="2026-09-06T01:00:00Z", provider=provider)
    assert not provider.directory_calls
    assert store.latest() == before


@pytest.mark.parametrize("configured", (True, False))
def test_runtime_scan_uses_only_the_selected_profile_credentials(tmp_path, monkeypatch, configured):
    from src.data_provider_config import DataProviderConfigStore
    from src import security_lifecycle_provider_scan as scan
    path = tmp_path / "profile.db"
    config = DataProviderConfigStore(path)
    with sqlite3.connect(path) as conn:
        create_profile_schema(conn)
    if configured:
        config.set_field("massive", "api_key", "profile-massive")
        config.set_field("eodhd", "api_key", "profile-eodhd")
    for name in ("MASSIVE_API_KEY", "POLYGON_API_KEY", "EODHD_API_KEY"):
        monkeypatch.setenv(name, "must-not-be-used")
    seen = []
    class Session(Provider):
        def __init__(self, **kwargs):
            super().__init__()
            seen.append(kwargs)
        def close(self):
            pass
    monkeypatch.setattr(scan, "ProviderScanSession", Session)
    scan.run_provider_scan(profile_path=path, tickers=(), at=NOW)
    assert seen == [{"at": NOW, "massive_key": "profile-massive" if configured else None,
                     "eodhd_key": "profile-eodhd" if configured else None}]


def test_owned_transport_construction_and_close_do_not_require_a_provider_call(monkeypatch):
    import requests
    from tests.test_lifecycle_provider_census_transport import FakeSession
    from src.security_lifecycle_provider_scan import ProviderScanSession
    sessions = []
    def session():
        value = FakeSession()
        sessions.append(value)
        return value
    monkeypatch.setattr(requests, "Session", session)
    scanner = ProviderScanSession(at=NOW, massive_key=None, eodhd_key=None)
    assert scanner.exact("ARCH") == ((), ("massive_credential_missing",))
    scanner.close()
    assert len(sessions) == 2
    assert all(session.closed and not session.calls for session in sessions)


@pytest.mark.parametrize("scenario,expected,count", [("terminal", "terminal", 4), ("rename", "continuation", 5),
                                                     ("404", "unresolved", 4), ("429", "unresolved", 4), ("otc", "unresolved", 2)])
def test_real_http_parsers_and_scan_obey_one_attempt_pacing_and_terminal_vetoes(scenario, expected, count):
    from tests.test_lifecycle_provider_census_transport import FakeSession, FakeResponse, json_response, event_fixture
    from tests.test_security_lifecycle_listing_evidence import _fixture
    from data_sources.listing_authority_transport import ListingAuthorityTransport
    from data_sources.lifecycle_provider_census_transport import LifecycleProviderCensusTransport
    from src.security_lifecycle_provider_scan import ProviderScanSession
    from src.security_lifecycle_provider_authority import classify_provider_listing
    from tests.test_security_lifecycle_provider_authority import FIGI
    empty = {"status": "OK", "results": []}
    def listing(ticker, active, market="stocks"):
        row = {"ticker": ticker, "active": active, "market": market, "composite_figi": FIGI, "primary_exchange": "XNAS", "type": "CS"}
        if not active:
            row["delisted_utc"] = "2025-01-15"
        return {"status": "OK", "results": [row]}
    directory_responses = [FakeResponse(body=_fixture(name).replace(b"08282026", b"09042026"), headers={"Content-Type": "text/plain"})
                           for name in ("nasdaqlisted.txt", "otherlisted.txt")]
    listing_responses = [json_response(empty), json_response(listing("OLD", True, "otc") if scenario == "otc" else empty)]
    if scenario != "otc":
        listing_responses.append(json_response(listing("OLD", False)))
    if scenario == "rename":
        listing_responses.append(json_response(listing("NEW", True)))
    timeline = event_fixture("OLD", "NEW") if scenario == "rename" else {
        "status": "OK", "results": {"events": [{"type": "ticker_change", "date": "2020-01-01", "ticker_change": {"ticker": "OLD"}}]}}
    http_listing = FakeSession(directory_responses + listing_responses)
    http_events = FakeSession([json_response([]), json_response([{"Code": "OLD", "Exchange": "NYSE", "Country": "USA", "Type": "Common Stock"}]),
                              json_response(timeline, status_code=int(scenario) if scenario in {"404", "429"} else 200)])
    ticks, sleeps = [0.0], []
    def sleep(seconds):
        sleeps.append(seconds)
        ticks[0] += seconds
    scanner = ProviderScanSession(at=NOW, massive_key="massive-test", eodhd_key="eodhd-test",
        listing_transport=ListingAuthorityTransport(session=http_listing, now=lambda: datetime.fromisoformat(NOW.replace("Z", "+00:00"))),
        event_transport=LifecycleProviderCensusTransport(session=http_events), sleep=sleep, monotonic=lambda: ticks[0])
    directories, directory_codes = scanner.directories(("OLD", "UNREPORTED"))
    material, codes = scanner.exact("OLD")
    assert directory_codes == ()
    result = classify_provider_listing(ticker="OLD", evidence=directories["OLD"] + material, today=date(2026, 9, 5))
    assert result.state == expected, result
    assert len(http_listing.calls) + len(http_events.calls) == count + 4
    assert scanner.diagnostics() == {"massive_requests": count, "nasdaq_requests": 2, "eodhd_requests": 2}
    assert sleeps == [12.5] * (count - 1)
    assert codes == ((f"massive_{'not_found' if scenario == '404' else 'rate_limited'}",) if scenario in {"404", "429"} else ())
    eodhd = next(row for row in directories["OLD"] if row.adapter == "eodhd_symbol_directory")
    assert "delisted=1" in eodhd.source_url
    scanner.close()
    assert http_listing.closed and http_events.closed
