import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("terminal_fresh_check", Path(__file__).with_name("fresh_check_v2.py"))
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class Clock:
    value = 0.0
    def timer(self):
        return self.value
    def sleep(self, seconds):
        self.value += seconds


class Session:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.calls, self.adapters = [], {}
        self.closed = False
    def mount(self, prefix, adapter):
        self.adapters[prefix] = adapter
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result
    def close(self):
        self.closed = True


def ledger(tmp_path, responses=()):
    clock = Clock()
    session = Session(responses)
    value = runner.RequestLedger(tmp_path, {"massive": "SENSITIVE_MASSIVE", "eodhd": "SENSITIVE_EODHD"},
                                 session=session, timer=clock.timer, sleep=clock.sleep)
    return value, clock, session


def get(value, *, ticker="ARCH", active="true", market="stocks"):
    return value.get(runner.MASSIVE_TICKERS_URL, params={"ticker": ticker, "active": active, "market": market,
                    "limit": 2, "apiKey": "SENSITIVE_MASSIVE"}, timeout=(5, 20), stream=True, allow_redirects=False)


@pytest.mark.parametrize("scenario", ("terminal", "rename", "404"))
def test_actual_scan_and_parsers_are_scoped_measured_and_paced_across_all_cases(tmp_path, scenario):
    from tests.test_lifecycle_provider_census_transport import FakeResponse, json_response
    from tests.test_security_lifecycle_listing_evidence import _fixture
    from src.security_lifecycle_provider_authority import classify_provider_listing
    responses = [FakeResponse(body=_fixture(name).replace(b"File Creation Time: 08282026|120000", b"File Creation Time: 0904202612:00|||||||"), headers={"Content-Type": "text/plain"})
                 for name in ("nasdaqlisted.txt", "otherlisted.txt")]
    responses += [json_response([]), json_response([{"Code": ticker, "Exchange": "NYSE", "Country": "USA", "Type": "Common Stock"}
                                                    for ticker in runner.TARGETS])]
    def listing(ticker, active, figi):
        row = {"ticker": ticker, "active": active, "market": "stocks", "primary_exchange": "XNAS", "type": "CS", "composite_figi": figi}
        if not active:
            row["delisted_utc"] = "2025-01-15"
        return {"status": "OK", "results": [row]}
    for i, ticker in enumerate(runner.TARGETS):
        figi = f"BBG00000000{i}"
        responses += [json_response({"status": "OK", "results": []}), json_response({"status": "OK", "results": []}),
                      json_response(listing(ticker, False, figi))]
        events = [{"type": "ticker_change", "date": "2020-01-01", "ticker_change": {"ticker": ticker}}]
        if scenario == "rename":
            events.append({"type": "ticker_change", "date": "2025-01-15", "ticker_change": {"ticker": ticker + "X"}})
        responses.append(json_response({"status": "OK", "results": {"events": events}}, status_code=404 if scenario == "404" else 200))
        if scenario == "rename":
            responses.append(json_response(listing(ticker + "X", True, figi)))
    value, clock, http = ledger(tmp_path, responses)
    at = "2026-09-05T01:00:00Z"
    def scanner():
        listing_transport = runner.BoundListingTransport(value)
        listing_transport._now = lambda: datetime.fromisoformat(at.replace("Z", "+00:00"))
        return runner.ProviderScanSession(at=at, massive_key=value.keys["massive"], eodhd_key=value.keys["eodhd"],
            listing_transport=listing_transport, event_transport=runner.BoundEventTransport(value), sleep=clock.sleep, monotonic=clock.timer)
    directories, codes = scanner().directories(runner.TARGETS)
    assert codes == ()
    for ticker in runner.TARGETS:
        value.case = ticker
        rows, codes = scanner().exact(ticker)
        result = classify_provider_listing(ticker=ticker, evidence=directories[ticker] + rows, today=datetime(2026, 9, 5).date())
        assert result.state == {"terminal": "terminal", "rename": "continuation", "404": "unresolved"}[scenario]
        assert codes == (("massive_not_found",) if scenario == "404" else ())
    total = 19 if scenario == "rename" else 16
    assert value.dispatched == len(http.calls) == len(value.outcomes) == total
    assert value.counts == {"massive": total - 4, "eodhd": 2, "nasdaq": 2}
    intervals = [row["dispatch_spacing_seconds"] for row in value.outcomes if row.get("dispatch_spacing_seconds") is not None]
    assert intervals == [12.5] * (total - 5)
    assert http.trust_env is False and http.adapters["https://"].max_retries.total == 0
    for path in tmp_path.glob("*.json"):
        assert "SENSITIVE_" not in path.read_text()
    assert len(list(tmp_path.glob("*-reserved.json"))) == len(list(tmp_path.glob("*-outcome.json"))) == total
    assert len(list(tmp_path.glob("private-request-*.body"))) == total - (3 if scenario == "404" else 0)
    assert not http.responses


def test_duplicate_request_cannot_dispatch_twice(tmp_path):
    from tests.test_lifecycle_provider_census_transport import json_response
    value, _, http = ledger(tmp_path, [json_response({})])
    value.case = "ARCH"
    get(value).close()
    with pytest.raises(runner.CheckStopped, match="check_duplicate_request"):
        get(value)
    assert len(http.calls) == 1


@pytest.mark.parametrize("count", (15, 19))
def test_exhausted_budget_cannot_dispatch(tmp_path, count):
    value, _, http = ledger(tmp_path)
    value.case = "ARCH"
    value.counts["massive"] = count
    with pytest.raises(runner.CheckStopped, match="check_request_budget"):
        get(value)
    assert not http.calls


@pytest.mark.parametrize("status", (401, 403, 429, 302))
def test_provider_stop_prevents_every_later_request(tmp_path, status):
    from tests.test_lifecycle_provider_census_transport import json_response
    value, _, http = ledger(tmp_path, [json_response({}, status_code=status)])
    value.case = "ARCH"
    get(value).close()
    value.case = "LTHM"
    with pytest.raises(runner.CheckStopped, match="check_previous_dispatch_stopped"):
        get(value, ticker="LTHM")
    assert len(http.calls) == 1 and value.outcomes[0]["status_code"] == status


def test_unknown_dispatch_outcome_is_persisted_without_retry(tmp_path):
    value, _, http = ledger(tmp_path, [TimeoutError("SENSITIVE_PROVIDER_URL")])
    value.case = "ARCH"
    with pytest.raises(runner.CheckStopped, match="check_dispatch_outcome_unknown"):
        get(value)
    assert value.dispatched == len(http.calls) == 1 and value.halted
    assert value.outcomes[0]["dispatch_outcome_unknown"] is True
    assert "SENSITIVE_PROVIDER_URL" not in (tmp_path / "request-01-outcome.json").read_text()


def test_reservation_failure_is_before_http_dispatch(tmp_path, monkeypatch):
    value, _, http = ledger(tmp_path)
    value.case = "ARCH"
    monkeypatch.setattr(runner, "write", lambda *args: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        get(value)
    assert value.dispatched == 0 and not http.calls


@pytest.mark.parametrize("ticker", ("AAPL", "CNR", "ALTM"))
def test_unobserved_successor_cannot_expand_the_query_scope(tmp_path, ticker):
    value, _, http = ledger(tmp_path)
    value.case = "ARCH"
    with pytest.raises(runner.CheckStopped, match="check_listing_scope"):
        get(value, ticker=ticker)
    assert not http.calls


def test_event_query_requires_current_response_stable_identity(tmp_path):
    value, _, http = ledger(tmp_path)
    value.case = "ARCH"
    with pytest.raises(runner.CheckStopped, match="check_event_scope"):
        value.get(runner.MASSIVE_EVENTS_PREFIX + "BBG000000001/events", params={"apiKey": "SENSITIVE_MASSIVE"},
                  timeout=15, stream=True, allow_redirects=False)
    assert not http.calls


def test_complete_response_is_replayable_but_never_contains_credentials(tmp_path):
    from tests.test_lifecycle_provider_census_transport import json_response
    value, _, http = ledger(tmp_path, [json_response({"answer": "visible"})])
    value.case = "ARCH"
    response = get(value)
    body = b"".join(response.iter_content(1024))
    response.close()
    assert (tmp_path / "private-request-01.body").read_bytes() == body
    assert value.outcomes[0]["body_complete"] is True
    assert value.outcomes[0]["content_type"] == "application/json"


def test_provider_echoed_key_cannot_be_saved_in_replay_data(tmp_path):
    from tests.test_lifecycle_provider_census_transport import json_response
    value, _, http = ledger(tmp_path, [json_response({"echo": "SENSITIVE_MASSIVE"})])
    value.case = "ARCH"
    response = get(value)
    list(response.iter_content(1024))
    with pytest.raises(runner.CheckStopped, match="check_secret_in_response"):
        response.close()
    assert not list(tmp_path.glob("*.body"))


def test_directory_rejection_keeps_its_typed_reason_without_dispatching_exact(tmp_path, monkeypatch):
    directory = tmp_path / "run"
    monkeypatch.setattr(runner, "stopped", lambda: None)
    monkeypatch.setattr(runner, "preflight_provider_upgrade", lambda path: {"schema_version": "v4", "automation": {
        "valid": True, "enabled": False, "apply_profile_transitions": False}})
    monkeypatch.setattr(runner, "source_scope", lambda: {})
    monkeypatch.setattr(runner, "unchanged_state", lambda: {})
    monkeypatch.setattr(runner, "ReadOnlyProviderCredentialStore", lambda path: None)
    monkeypatch.setattr(runner, "resolve_census_credential", lambda store, provider: "SENSITIVE_" + provider.upper())
    real_ledger = runner.RequestLedger
    monkeypatch.setattr(runner, "RequestLedger", lambda path, keys: real_ledger(path, keys, session=Session()))
    class Scan:
        def __init__(self, **kwargs):
            pass
        def directories(self, targets):
            return {ticker: () for ticker in targets}, ("listing_directory_schema_mismatch",)
        def exact(self, ticker):
            raise AssertionError("directory rejection must precede exact checks")
    class Store:
        def __init__(self, path):
            pass
        def latest(self):
            return {}
    monkeypatch.setattr(runner, "ProviderScanSession", Scan)
    monkeypatch.setattr(runner, "ProviderCheckStore", Store)
    assert runner.run(directory) == 2
    result = json.loads((directory / "fresh-check-summary.json").read_text())
    assert result["directory_provider_codes"] == ["listing_directory_schema_mismatch"]
    assert result["total_requests"] == result["completed_targets"] == 0
    preserved = json.loads((directory / "private-directory-material.json").read_text())
    assert preserved["provider_codes"] == result["directory_provider_codes"]
