"""An acknowledged failure is not a successful Alpha Picks collection."""

import json
from unittest.mock import Mock

import pytest

from tests.sa_acquisition_helpers import ADMITTED_TASK
from tests.test_sa_extension_popup import _run, _run_background_probe
from src.sa.extension_run_protocol import derive_run_result
from src.sa_native_host import _handle_failure


@pytest.mark.parametrize("persisted", [True, False])
def test_native_failure_receipt_requires_durable_record(persisted):
    dal = Mock()
    if not persisted:
        dal.record_sa_refresh_failure.side_effect = RuntimeError("write unavailable")
    result = _handle_failure(dal, "current", "2026-09-26T03:52:23Z", "No table")
    assert result["recorded_failure"] is persisted
    assert result["status"] == ("ok" if persisted else "error")
    dal.record_sa_refresh_failure.assert_called_once()


@pytest.mark.parametrize("failure", ["readiness", "current_script", "closed_script", "details"])
def test_refresh_failure_ack_never_completes_unexecuted_phases(failure):
    result = _run_background_probe(ADMITTED_TASK + "const failure = " + json.dumps(failure) + ";" + r"""
        const recorded = [], scraped = [];
        let readinessCalls = 0;
        chrome.tabs.create = async () => ({id: 1});
        chrome.tabs.update = async () => ({id: 1});
        chrome.tabs.remove = async () => {};
        chrome.runtime.sendNativeMessage = (_host, message, callback) => {
          if (message.action === 'refresh_failure') {
            recorded.push(message.scope);
            callback({status: 'ok', scope: message.scope, recorded_failure: true});
          } else callback({status: 'ok', count: 1});
        };
        waitForAlphaPicksTableReady = async () => {
          readinessCalls++;
          if (failure === 'readiness') return {ok: false, reason_code: 'dom_not_ready', error: 'No table'};
          if (failure === 'current_script' || (failure === 'closed_script' && readinessCalls === 2)) {
            throw new Error('Missing host permission for the tab');
          }
          return {ok: true};
        };
        injectScraper = async () => {scraped.push(readinessCalls); return [{symbol: 'AMD'}];};
        doDetailFetch = async () => {throw new Error('Detail extraction interrupted');};
        const refresh = await doRefresh('quick');
        const stored = (await chrome.storage.local.get('lastRefresh')).lastRefresh;
        return {refresh, stored, recorded, scraped, protocol: buildAlphaPicksProtocolResult('quick', refresh)};
    """)
    protocol = result["protocol"]
    assert protocol["derived_outcome"] == ("degraded" if failure == "details" else "failed")
    assert protocol["healthy_anchor_eligible"] is False
    wire = {key: value for key, value in protocol.items() if key not in {"job_name", "db_status"}}
    assert derive_run_result(wire)["db_status"] == "failed"
    assert protocol["phases"]["article_details"]["state"] == "failed"
    assert protocol["phases"]["reconciliation"]["state"] == "failed"
    expected_complete = 2 if failure == "details" else 1 if failure == "closed_script" else 0
    assert protocol["counts"]["phase_complete"] == expected_complete
    for scope in result["recorded"]:
        assert result["refresh"][scope]["status"] == "error"
        assert result["stored"][scope]["status"] == "error"
        assert result["stored"][scope]["recorded_failure"] is True


def test_old_failure_ack_in_browser_storage_is_not_successful():
    ack = {"status": "ok", "recorded_failure": True}
    protocol = _run_background_probe("""
        return buildAlphaPicksProtocolResult('quick', {
          current: {status: 'ok', recorded_failure: true},
          closed: {status: 'ok', recorded_failure: true}
        });
    """)
    assert protocol["derived_outcome"] == "failed"
    assert protocol["counts"]["phase_complete"] == 0
    popup = _run(storage={"lastRefresh": {"current": ack, "closed": ack, "mode": "quick"}})
    assert "Failed:" in popup["bodyText"]
    assert "undefined picks" not in popup["bodyText"]


def test_successful_empty_refresh_is_a_complete_noop():
    result = _run_background_probe("""
        return buildAlphaPicksProtocolResult('quick', {
          current: {status: 'ok', count: 0}, closed: {status: 'ok', count: 0}
        });
    """)
    assert result["derived_outcome"] == "complete"
    assert result["counts"]["phase_complete"] == 4


def test_article_navigation_capacity_stop_stays_deferred_not_failed():
    result = _run_background_probe(ADMITTED_TASK + r"""
        chrome.tabs.create = async () => ({id: 1});
        chrome.tabs.update = async () => ({id: 1});
        chrome.tabs.remove = async () => {};
        waitForAlphaPicksTableReady = async () => ({ok: true});
        injectScraper = async () => [{symbol: 'AMD'}];
        doDetailFetch = async () => {throw new SAAcquisition.Stop({status: 'deferred', reason: 'capacity_exhausted'});};
        const refresh = await doRefresh('quick');
        return attachExtensionRunProtocol('alpha_picks_sync', 'quick', refresh).extension_run;
    """)
    assert result["derived_outcome"] == "deferred"
    assert result["counts"]["phase_complete"] == 2
    assert result["counts"]["phase_failed"] == 0
    assert result["phases"]["article_details"] == {"state": "deferred", "reason_code": "capacity_exhausted"}
