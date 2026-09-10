"""A rename must account for current observations stored under its successor."""

from dataclasses import replace
from datetime import date, datetime
import hashlib
import json
import sqlite3

import pytest

from data_sources.lifecycle_provider_census_transport import LifecycleProviderCensusTransport
from data_sources.listing_authority_transport import ListingAuthorityTransport
from src.security_lifecycle_investigation import observation_fingerprint
from src.security_lifecycle_listing_evidence import _evidence
from src.security_lifecycle_provider_authority import classify_provider_listing, provider_transition_guard
from src.security_lifecycle_provider_scan import ProviderScanSession, refresh_provider_checks
from tests.test_lifecycle_provider_census_transport import FakeSession, FakeResponse, json_response, event_fixture
from tests.test_security_lifecycle_automatic_rename import rename_workflow
from tests.test_security_lifecycle_listing_evidence import _fixture
from tests.test_security_lifecycle_provider_authority import FIGI, NOW, record
from tests.test_security_lifecycle_terminal_workflow import workflow_worker
from tests.test_security_lifecycle_tracking_policy import assessment_rows, transition_rows


def guard(c, *, at=NOW):
    observed = c["checks"].latest()["OLD"]["observation"]
    with sqlite3.connect(c["profile"]) as conn:
        return provider_transition_guard(conn, ticker="OLD",
            observation_fingerprint_sha256=observation_fingerprint(observed),
            transition_kind="symbol_continuation", successor_ticker="NEW",
            effective_date="2026-06-22", at=at, human_accepted=False)


@pytest.mark.parametrize("successor_active", (True, False))
def test_real_scan_carries_the_successor_directory_observation_without_extra_requests(tmp_path, successor_active):
    c = rename_workflow(tmp_path)
    empty = {"status": "OK", "results": []}

    def listing(ticker, active):
        row = {"ticker": ticker, "active": active, "market": "stocks", "composite_figi": FIGI,
               "primary_exchange": "XNAS", "type": "CS"}
        if not active:
            row["delisted_utc"] = "2025-01-15"
        return {"status": "OK", "results": [row]}

    directories = [FakeResponse(body=_fixture(name).replace(b"08282026", b"09042026"),
                               headers={"Content-Type": "text/plain"})
                   for name in ("nasdaqlisted.txt", "otherlisted.txt")]
    listing_http = FakeSession(directories + [json_response(empty), json_response(empty),
        json_response(listing("OLD", False)), json_response(listing("NEW", True))])
    eodhd = lambda ticker: {"Code": ticker, "Exchange": "NYSE", "Country": "USA", "Type": "Common Stock"}
    event_http = FakeSession([
        json_response([eodhd("NEW")] if successor_active else []),
        json_response([eodhd("OLD")] + ([] if successor_active else [eodhd("NEW")])),
        json_response(event_fixture("OLD", "NEW")),
    ])
    ticks = [0.0]

    def sleep(seconds):
        ticks[0] += seconds

    scanner = ProviderScanSession(at=NOW, massive_key="synthetic", eodhd_key="synthetic",
        listing_transport=ListingAuthorityTransport(session=listing_http,
            now=lambda: datetime.fromisoformat(NOW.replace("Z", "+00:00"))),
        event_transport=LifecycleProviderCensusTransport(session=event_http),
        sleep=sleep, monotonic=lambda: ticks[0])
    try:
        refresh_provider_checks(c["checks"], tickers=("OLD", "NEW"), target_ticker="OLD", at=NOW, provider=scanner)
    finally:
        scanner.close()
    latest = c["checks"].latest()["OLD"]
    successor = [row for row in latest["evidence"] if row["adapter"] == "eodhd_symbol_directory"
                 and row["source_locator"].get("candidate_ticker") == "NEW"]
    assert len(successor) == 1
    assert successor[0]["source_locator"]["listing_status"] == ("active" if successor_active else "inactive")
    decision = classify_provider_listing(ticker="OLD", evidence=latest["evidence"], today=date(2026, 9, 5))
    assert (decision.continuation_state == "confirmed") is successor_active
    assert scanner.diagnostics() == {"massive_requests": 5, "nasdaq_requests": 2, "eodhd_requests": 2}
    assert len(listing_http.calls) + len(event_http.calls) == 9


@pytest.mark.parametrize("change", ("inactive", "identity", "provider_error"))
def test_independently_stored_successor_conflict_blocks_automatic_rename(tmp_path, monkeypatch, change):
    c = rename_workflow(tmp_path)
    material = (_evidence(record("eodhd_symbol_directory", "inactive", ticker="NEW", expected=False)),)
    if change == "identity":
        material = (_evidence(record("massive_reference", "active", ticker="NEW", figi="BBG00HC114X0")),)
    c["checks"].record(ticker="NEW", at=NOW, evidence=() if change == "provider_error" else material,
        blockers=("massive_rate_limited",) if change == "provider_error" else (), diagnostics={})
    assert guard(c)
    result = workflow_worker(c, monkeypatch).run(limit=2, mode="live")
    assert result["failed"] == 0, result
    assert all(row["kind"] != "symbol_continuation" for row in transition_rows(c))
    assert assessment_rows(c)[0]["outcomes"] == ["listing_ended"]


def test_successor_observation_is_rechecked_inside_the_apply_transaction(tmp_path, monkeypatch):
    c = rename_workflow(tmp_path)
    assert workflow_worker(c, monkeypatch).run(limit=1, mode="live")["accepted"] == 1
    transition = transition_rows(c)[0]
    original = c["checks"].latest()["OLD"]
    c["now"][0] = "2026-09-05T01:01:00Z"
    negative = replace(record("eodhd_symbol_directory", "inactive", ticker="NEW", expected=False), retrieved_at=c["now"][0])
    c["checks"].record(ticker="NEW", at=c["now"][0], evidence=(_evidence(negative),), diagnostics={})
    assert c["checks"].latest()["OLD"] == original
    applied = c["service"].execute_transition(transition["transition_id"],
        preview_sha256=transition["approved_preview_sha256"], trigger="scheduler", before_write=lambda: None)
    assert applied["status"] == "blocked", applied
    assert "OLD" in c["sources"]() and "NEW" not in c["sources"]()


@pytest.mark.parametrize("scenario", ("duplicate", "newer_active", "stale_negative", "unrelated"))
def test_successor_evidence_merge_does_not_invent_conflicts(tmp_path, scenario):
    c = rename_workflow(tmp_path)
    at, ticker = NOW, "NEW"
    value = record("massive_reference", "active", ticker="NEW", figi=FIGI)
    if scenario == "newer_active":
        at = "2026-09-05T01:01:00Z"
        value = replace(value, retrieved_at=at, source_as_of=at)
    elif scenario == "stale_negative":
        at = "2026-08-01T00:00:00Z"
        value = replace(record("eodhd_symbol_directory", "inactive", ticker="NEW", expected=False), retrieved_at=at)
    elif scenario == "unrelated":
        ticker = "OTHER"
        value = record("eodhd_symbol_directory", "inactive", ticker=ticker, expected=False)
    c["checks"].record(ticker=ticker, at=at, evidence=(_evidence(value),), diagnostics={})
    assert guard(c, at=at if scenario == "newer_active" else NOW) == ()


def test_newer_successor_snapshot_can_resolve_a_previously_captured_conflict(tmp_path):
    c = rename_workflow(tmp_path)
    negative = _evidence(record("eodhd_symbol_directory", "inactive", ticker="NEW", expected=False))
    c["checks"].record(ticker="OLD", at=NOW, evidence=(*c["material"], negative), diagnostics={})
    assert guard(c)
    at = "2026-09-05T01:01:00Z"
    positive = replace(record("eodhd_symbol_directory", "active", ticker="NEW"), retrieved_at=at, source_as_of=at)
    c["checks"].record(ticker="NEW", at=at, evidence=(_evidence(positive),), diagnostics={})
    assert guard(c, at=at) == ()


def test_malformed_timeline_is_a_typed_gap_not_an_exception_in_related_lookup(tmp_path):
    from src.security_lifecycle_provider_authority import evidence_dict

    c = rename_workflow(tmp_path)
    event = evidence_dict(c["material"][-1])
    event["source_locator"]["events"] = None
    event["excerpt"] = json.dumps(event["source_locator"], sort_keys=True, separators=(",", ":"))
    event["content_sha256"] = hashlib.sha256(event["excerpt"].encode()).hexdigest()
    c["checks"].record(ticker="OLD", at=NOW, evidence=(*c["material"][:-1], event), diagnostics={})
    assert guard(c) == ("provider_continuation_review",)


def test_provider_observation_describes_continuity_without_a_human_only_policy(tmp_path):
    c = rename_workflow(tmp_path)
    assert c["checks"].latest()["OLD"]["observation"]["description"] == (
        "Listing sources confirm a same-security ticker change."
    )


def _capture_successor_failure(c):
    c["checks"].record(ticker="NEW", at=NOW, evidence=(), blockers=("massive_rate_limited",), diagnostics={})
    material, codes = c["checks"].material(ticker="OLD", evidence=c["material"], blockers=(), at=NOW)
    c["checks"].record(ticker="OLD", at=NOW, evidence=material, blockers=codes, diagnostics={})
    assert guard(c)
    return c["checks"].latest()["OLD"]


def test_successor_recovery_clears_derived_error_without_rewriting_old_receipt(tmp_path, monkeypatch):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    c = rename_workflow(tmp_path)
    old = _capture_successor_failure(c)
    at = "2026-09-05T01:01:00Z"
    positive = replace(record("massive_reference", "active", ticker="NEW", figi=FIGI), retrieved_at=at, source_as_of=at)
    c["checks"].record(ticker="NEW", at=at, evidence=(_evidence(positive),), diagnostics={})
    assert guard(c, at=at) == ()
    assert c["checks"].latest()["OLD"] == old
    epoch = int(datetime.fromisoformat(NOW.replace("Z", "+00:00")).timestamp())
    c["checks"].record(ticker="OLD", at=NOW, evidence=old["evidence"], blockers=old["blockers"],
        diagnostics={"directory_checked_epoch_s": epoch})
    with sqlite3.connect(c["profile"]) as conn:
        history = conn.execute("SELECT * FROM security_lifecycle_provider_checks").fetchall()

    class ExactRefresh:
        def directories(self, tickers):
            raise AssertionError("fresh_directories_must_not_be_requested_again")

        def exact(self, ticker):
            assert ticker == "OLD"
            return tuple(item for item in c["material"] if item.adapter in {"massive_reference", "massive_ticker_events"}), ()

        def diagnostics(self):
            return {}

    refresh_provider_checks(c["checks"], tickers=("OLD",), target_ticker="OLD", at=at, provider=ExactRefresh())
    assert "successor_listing_provider_error" not in c["checks"].latest()["OLD"]["blockers"]
    c["now"][0] = at
    worker = workflow_worker(c, monkeypatch)
    monkeypatch.setattr(worker, "_clock", lambda: at)
    monkeypatch.setattr(scheduler, "_clock", lambda: at)
    result = worker.run(limit=2, mode="live")
    assert result["failed"] == 0, result
    transitions = transition_rows(c)
    assert len(transitions) == 1, assessment_rows(c)
    transition = transitions[0]
    assert transition["kind"] == "symbol_continuation"
    applied = c["service"].execute_transition(transition["transition_id"],
        preview_sha256=transition["approved_preview_sha256"], trigger="scheduler", before_write=lambda: None)
    assert applied["status"] == "applied", applied
    assert "OLD" not in c["sources"]() and "NEW" in c["sources"]()
    with sqlite3.connect(c["profile"]) as conn:
        assert all(row in conn.execute("SELECT * FROM security_lifecycle_provider_checks").fetchall() for row in history)


@pytest.mark.parametrize("recovery", ("still_failed", "unobserved", "stale"))
def test_derived_successor_error_needs_a_fresh_observation_to_clear(tmp_path, recovery):
    c = rename_workflow(tmp_path)
    old = _capture_successor_failure(c)
    at = "2026-09-05T01:01:00Z"
    if recovery == "unobserved":
        c["checks"].record(ticker="NEW", at=at, evidence=(), diagnostics={})
    elif recovery == "stale":
        positive = replace(record("massive_reference", "active", ticker="NEW", figi=FIGI),
                           retrieved_at="2026-08-01T00:00:00Z")
        c["checks"].record(ticker="NEW", at=at, evidence=(_evidence(positive),), diagnostics={})
    assert guard(c, at=at)
    assert c["checks"].latest()["OLD"] == old
