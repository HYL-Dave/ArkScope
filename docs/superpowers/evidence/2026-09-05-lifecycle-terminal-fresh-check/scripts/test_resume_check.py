import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

from tests.test_lifecycle_provider_census_transport import json_response
from tests.test_security_lifecycle_listing_evidence import _fixture


spec = importlib.util.spec_from_file_location("resume_check", Path(__file__).with_name("resume_check.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
base = runner.base
AT = "2026-09-05T10:33:44+00:00"
NOW = "2026-09-05T11:00:00+00:00"


def captured_directories(tmp_path):
    source = tmp_path / "source"
    source.mkdir(mode=0o700)
    base.write(source, "authorization.json", {
        "at": AT, "targets": list(base.TARGETS), "limits": base.LIMITS, "max_total": 19,
        "retry": False, "fallback": False, "terminal_application_authorized": False,
        "backfill_authorized": False,
    })
    base.write(source, "fresh-check-summary.json", {
        "at": AT, "completed_targets": 0, "stopped_code": "check_directories_incomplete",
        "observed_requests": {"nasdaq": 2, "eodhd": 2}, "total_requests": 4,
        "http_status_counts": {"200": 4}, "results": [],
    })
    bodies = []
    for i, name in enumerate(("nasdaqlisted.txt", "otherlisted.txt")):
        lines = _fixture(name).splitlines()
        lines[-1] = b"File Creation Time: 0904202621:31" + b"|" * (7 - i)
        if i:
            lines.insert(1, b"PFD$A|Preferred fixture|N|PFDpA|N|100|N|PFD-A")
            lines.insert(2, b"TESTM|Test fixture|M|TESTM|N|100|Y|TESTM")
        bodies.append(b"\n".join(lines) + b"\n")
    bodies.extend((b"[]", base.encoded([
        {"Code": ticker, "Exchange": "NYSE", "Country": "USA", "Type": "Common Stock"}
        for ticker in base.TARGETS])))
    for i, (provider, identity, content_type) in enumerate(runner.EXPECTED, 1):
        row = {"request": i, "provider": provider, "kind": "directory", "target": None,
               "identity": identity, "attempts": 1, "reserved_at": AT}
        base.write(source, f"request-{i:02d}-reserved.json", row)
        base.write(source, f"request-{i:02d}-outcome.json", {
            **row, "status_code": 200, "body_complete": True, "content_type": content_type,
            "read_bytes": len(bodies[i - 1]), "response_sha256": hashlib.sha256(bodies[i - 1]).hexdigest(),
        })
        base.write_bytes(source, f"private-request-{i:02d}.body", bodies[i - 1])
    return source


def change_json(source, name, **changes):
    path = source / name
    value = json.loads(path.read_bytes())
    path.write_bytes(base.encoded({**value, **changes}))


def test_saved_response_replay_uses_real_parsers_without_network_or_credentials(tmp_path, monkeypatch):
    source = captured_directories(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError("replay must not create a network session or read credentials")
    monkeypatch.setattr(base.requests, "Session", forbidden)
    monkeypatch.setattr(base, "resolve_census_credential", forbidden)
    replay = runner.load_directory_replay(source, at=NOW)
    assert replay["at"] == AT and len(replay["bindings"]) == 14
    for ticker, rows in replay["material"].items():
        assert ticker in base.TARGETS
        assert [row.source_locator["listing_status"] for row in rows] == ["not_found", "not_found", "inactive"]
        assert all(runner.instant(row.retrieved_at) == runner.instant(AT) for row in rows)
    assert not (source / "massive-remainder-claim.json").exists()


@pytest.mark.parametrize(("scenario", "code"), (
    ("body", "resume_response_digest_mismatch"),
    ("byte_count", "resume_response_digest_mismatch"),
    ("incomplete", "resume_response_incomplete"),
    ("redirect", "resume_response_incomplete"),
    ("unknown_dispatch", "resume_response_incomplete"),
    ("identity", "resume_request_identity_mismatch"),
    ("attempts", "resume_request_identity_mismatch"),
    ("extra_request", "resume_request_ledger_mismatch"),
    ("missing_outcome", "resume_request_ledger_mismatch"),
    ("spent_massive", "resume_remainder_not_unused"),
    ("wrong_target", "resume_authorization_mismatch"),
    ("retry", "resume_authorization_mismatch"),
    ("world_readable", "resume_private_file_invalid"),
))
def test_bad_replay_material_stops_before_credential_lookup_or_dispatch(tmp_path, monkeypatch, scenario, code):
    source = captured_directories(tmp_path)
    if scenario == "body":
        path = source / "private-request-01.body"
        path.write_bytes(path.read_bytes().replace(b"AAPL", b"ZAPL", 1))
    elif scenario == "byte_count":
        change_json(source, "request-01-outcome.json", read_bytes=1)
    elif scenario == "incomplete":
        change_json(source, "request-01-outcome.json", body_complete=False)
    elif scenario == "redirect":
        change_json(source, "request-01-outcome.json", status_code=302)
    elif scenario == "unknown_dispatch":
        change_json(source, "request-01-outcome.json", dispatch_outcome_unknown=True)
    elif scenario == "identity":
        change_json(source, "request-01-reserved.json", identity="unrelated")
    elif scenario == "attempts":
        change_json(source, "request-01-reserved.json", attempts=2)
    elif scenario == "extra_request":
        base.write(source, "request-05-reserved.json", {})
    elif scenario == "missing_outcome":
        (source / "request-04-outcome.json").unlink()
    elif scenario == "spent_massive":
        change_json(source, "fresh-check-summary.json", observed_requests={"massive": 1, "nasdaq": 2, "eodhd": 2})
    elif scenario == "wrong_target":
        change_json(source, "authorization.json", targets=["AAPL"])
    elif scenario == "retry":
        change_json(source, "authorization.json", retry=True)
    elif scenario == "world_readable":
        (source / "private-request-01.body").chmod(0o644)
    monkeypatch.setattr(runner, "preflight", lambda: ({}, {}))
    monkeypatch.setattr(base, "now", lambda: NOW)
    monkeypatch.setattr(base, "resolve_census_credential", lambda *args: pytest.fail("credential lookup"))
    with pytest.raises(runner.CheckStopped, match=code):
        runner.run(source, tmp_path / "destination")
    assert not (source / "massive-remainder-claim.json").exists()


@pytest.mark.parametrize("at", ("2026-09-05T10:00:00+00:00", "2026-09-06T11:00:00+00:00"))
def test_replay_never_retimestamps_future_or_expired_observations(tmp_path, at):
    source = captured_directories(tmp_path)
    with pytest.raises(runner.CheckStopped, match="resume_directory_expired"):
        runner.load_directory_replay(source, at=at)


def test_claim_is_exclusive_even_with_a_different_destination(tmp_path):
    source = captured_directories(tmp_path)
    replay = runner.load_directory_replay(source, at=NOW)
    runner.claim_remainder(source, tmp_path / "one", replay=replay, at=NOW)
    with pytest.raises(runner.CheckStopped, match="resume_remainder_already_claimed"):
        runner.claim_remainder(source, tmp_path / "two", replay=replay, at=NOW)


class Clock:
    value = 0.0
    def timer(self):
        return self.value
    def sleep(self, seconds):
        self.value += seconds


class Session:
    def __init__(self, responses=()):
        self.responses, self.calls = list(responses), []
    def mount(self, *args):
        pass
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)
    def close(self):
        pass


def test_remainder_ledger_cannot_spend_again_on_directories(tmp_path):
    http = Session()
    ledger = runner.MassiveRemainderLedger(tmp_path, {"massive": "SENSITIVE_MASSIVE"}, session=http)
    for url in (base.NASDAQ_LISTED_URL, base.OTHER_LISTED_URL, base.EODHD_EXCHANGE_SYMBOL_LIST_URL):
        with pytest.raises(runner.CheckStopped, match="resume_directory_network_forbidden"):
            ledger.get(url, timeout=15, stream=True, allow_redirects=False)
    assert not http.calls and ledger.dispatched == 0


def test_remainder_budget_cannot_use_unspent_directory_allowances(tmp_path):
    http = Session()
    ledger = runner.MassiveRemainderLedger(tmp_path, {"massive": "SENSITIVE_MASSIVE"}, session=http)
    ledger.counts["massive"] = 15
    ledger.case = "TA"
    with pytest.raises(runner.CheckStopped, match="check_request_budget"):
        ledger.get(base.MASSIVE_TICKERS_URL, params={"ticker": "TA", "active": "true", "market": "stocks",
                   "limit": 2, "apiKey": "SENSITIVE_MASSIVE"}, timeout=(5, 20), stream=True, allow_redirects=False)
    assert not http.calls


@pytest.mark.parametrize("scenario", ("terminal", "rename", "404", "429"))
def test_resume_runs_real_scanner_and_store_with_no_directory_http_or_automatic_disposition(tmp_path, monkeypatch, scenario):
    from tests.test_security_lifecycle_provider_store import _paths
    source = captured_directories(tmp_path)
    profile, _ = _paths(tmp_path)
    monkeypatch.setattr(base, "PROFILE", profile)
    monkeypatch.setattr(base, "now", lambda: NOW)
    def domain_digest():
        with sqlite3.connect(profile) as conn:
            names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                     if row[0] != "security_lifecycle_provider_checks"]
            return {name: hashlib.sha256(base.encoded(conn.execute(f'SELECT * FROM "{name}"').fetchall())).hexdigest()
                    for name in names}
    original = domain_digest()
    monkeypatch.setattr(runner, "preflight", lambda: ({ticker: ("sa_alpha_picks_former",) for ticker in base.TARGETS}, domain_digest()))
    keys = []
    monkeypatch.setattr(base, "ReadOnlyProviderCredentialStore", lambda path: None)
    def credential(store, provider):
        assert provider == "massive"
        keys.append(provider)
        return "SENSITIVE_MASSIVE"
    monkeypatch.setattr(base, "resolve_census_credential", credential)
    responses = []
    def listing(ticker, active, figi):
        row = {"ticker": ticker, "active": active, "market": "stocks", "primary_exchange": "XNYS",
               "type": "CS", "composite_figi": figi}
        if not active:
            row["delisted_utc"] = "2025-01-15"
        return {"status": "OK", "results": [row]}
    for i, ticker in enumerate(base.TARGETS):
        figi = f"BBG00000000{i}"
        responses += [json_response({"status": "OK", "results": []}), json_response({"status": "OK", "results": []}),
                      json_response(listing(ticker, False, figi))]
        events = [{"type": "ticker_change", "date": "2020-01-01", "ticker_change": {"ticker": ticker}}]
        if scenario == "rename":
            events.append({"type": "ticker_change", "date": "2025-01-15", "ticker_change": {"ticker": ticker + "X"}})
        responses.append(json_response({"status": "OK", "results": {"events": events}}, status_code=404 if scenario == "404" else 200))
        if scenario == "rename":
            responses.append(json_response(listing(ticker + "X", True, figi)))
    if scenario == "429":
        responses = [json_response({}, status_code=429)]
    clock, http = Clock(), Session(responses)
    ledger_type, scanner_type, listing_type = runner.MassiveRemainderLedger, base.ProviderScanSession, base.BoundListingTransport
    monkeypatch.setattr(runner, "MassiveRemainderLedger", lambda path, keys: ledger_type(path, keys, session=http, timer=clock.timer, sleep=clock.sleep))
    monkeypatch.setattr(base, "ProviderScanSession", lambda **kwargs: scanner_type(**kwargs, sleep=clock.sleep, monotonic=clock.timer))
    def listing_transport(ledger):
        value = listing_type(ledger)
        value._now = lambda: runner.instant(NOW)
        return value
    monkeypatch.setattr(base, "BoundListingTransport", listing_transport)
    destination = tmp_path / "destination"
    assert runner.run(source, destination) == (2 if scenario == "429" else 0)
    summary = json.loads((destination / "fresh-check-summary.json").read_bytes())
    expected_count = {"terminal": 12, "rename": 15, "404": 12, "429": 1}[scenario]
    assert len(http.calls) == summary["new_http_requests"] == expected_count
    assert summary["authorization_requests_including_saved_directories"] == expected_count + 4
    assert summary["observed_new_requests"] == {"massive": expected_count}
    assert summary["completed_targets"] == (1 if scenario == "429" else 3)
    assert {row["state"] for row in summary["results"]} == {
        {"terminal": "terminal", "rename": "continuation", "404": "unresolved", "429": "unresolved"}[scenario]}
    assert all(row["attended_review_available"] == (scenario == "404") for row in summary["results"])
    assert summary["terminal_dispositions_applied"] == summary["ibkr_requests"] == summary["price_writes"] == 0
    assert summary["minimum_observed_massive_spacing_seconds"] == (None if scenario == "429" else 12.5)
    assert domain_digest() == original
    assert keys == ["massive"]
    assert not http.responses
    for path in destination.glob("*.json"):
        assert "SENSITIVE_MASSIVE" not in path.read_text()
    with pytest.raises(runner.CheckStopped, match="resume_remainder_already_claimed"):
        runner.run(source, tmp_path / "second_destination")
    assert keys == ["massive"] and len(http.calls) == expected_count
