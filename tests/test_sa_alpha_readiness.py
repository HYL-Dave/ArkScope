"""Navigation readiness and access restrictions are distinct states."""

import json

import pytest

from tests.sa_acquisition_helpers import ADMITTED_TASK
from tests.test_sa_extension_popup import _run_background_probe


def readiness_probe(scenario):
    return _run_background_probe(ADMITTED_TASK + "const scenario = " + json.dumps(scenario) + ";" + r"""
        let clock = 0;
        const injections = [];
        const target = 'https://seekingalpha.com/alpha-picks/picks/current';
        Date.now = () => clock;
        sleep = async ms => {clock += ms;};
        function tab() {
          if (scenario === 'blank' && clock === 0) return {url: 'about:blank', pendingUrl: target, status: 'loading'};
          if (scenario === 'other_origin') return {url: 'https://example.org/', status: 'complete'};
          return {url: target, status: scenario === 'denied' ? 'complete' : 'loading'};
        }
        chrome.tabs.get = async () => tab();
        chrome.scripting.executeScript = async request => {
          injections.push({url: tab().url, clock, access: request.func === readSaAccessMarkers});
          if (tab().url === 'about:blank' || scenario === 'denied' || scenario === 'stuck' ||
              (scenario === 'commit_race' && clock === 0)) {
            throw new Error('Missing host permission for the tab');
          }
          if (scenario === 'code_error') throw new Error('Unexpected extractor bug');
          if (request.func === readSaAccessMarkers) {
            return [{result: scenario === 'login' ? 'login_required' : null}];
          }
          return [{result: {status: 'ready', url: target}}];
        };
        try {
          const ready = await waitForAlphaPicksTableReady(1, target, 'current picks', 1500);
          return {ready, injections, elapsed: clock};
        } catch (err) {
          return {error: err.message, stop: err.detail || null, injections, elapsed: clock};
        }
    """)


@pytest.mark.parametrize("scenario", ["blank", "commit_race"])
def test_initial_document_waits_then_reads_table_while_tab_is_still_loading(scenario):
    result = readiness_probe(scenario)
    assert result.get("ready") == {"ok": True}, result
    assert result["elapsed"] == 500
    assert all(item["url"] != "about:blank" for item in result["injections"])


def test_wrong_origin_is_never_probed_or_accepted_as_a_picks_table():
    result = readiness_probe("other_origin")
    assert result["ready"]["ok"] is False
    assert result["injections"] == []


def test_persistent_injection_denial_has_bounded_readiness_timeout():
    result = readiness_probe("stuck")
    assert result.get("ready", {}).get("reason_code") == "dom_not_ready", result
    assert "Missing host permission" in result["ready"]["error"]
    assert result["elapsed"] == 1500


@pytest.mark.parametrize("scenario,message", [
    ("denied", "Missing host permission"), ("code_error", "Unexpected extractor bug")
])
def test_ready_document_denial_and_programming_error_are_not_retried(scenario, message):
    result = readiness_probe(scenario)
    assert message in result["error"]
    assert result["elapsed"] == 0


def test_loading_page_still_enforces_login_pause_immediately():
    result = readiness_probe("login")
    assert result["stop"]["error_code"] == "login_required"
    assert result["elapsed"] == 0
    assert len(result["injections"]) == 1
