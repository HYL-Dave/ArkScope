"""Firefox pages share native-host admission, including pending consent."""

import json
import subprocess
from pathlib import Path

import pytest

from tests.test_sa_extension_popup import _run, _run_background_probe

ROOT = Path(__file__).resolve().parents[1]


def _probe(scenario):
    script = r"""
const fs = require('fs'), vm = require('vm');
const source = fs.readFileSync('extensions/sa_alpha_picks/compat_firefox.js', 'utf8');
const queues = new Map(), calls = [], lockNames = [];
let active = 0, peak = 0;
const locks = {request(name, work) {
  lockNames.push(name);
  const run = (queues.get(name) || Promise.resolve()).then(work);
  queues.set(name, run.catch(() => {}));
  return run;
}};
function context() {
  const sandbox = {setTimeout, navigator: {locks}, browser: {runtime: {
    async sendNativeMessage(host, message) {
      active++; peak = Math.max(peak, active); calls.push({host, message});
      await new Promise(resolve => setTimeout(resolve, 5));
      active--;
      if (message.fail) throw new Error('consent_rejected');
      return {id: message.id};
    },
  }}};
  if (process.argv[1] === 'missing_locks') delete sandbox.navigator.locks;
  vm.createContext(sandbox); vm.runInContext(source, sandbox);
  return sandbox;
}
(async () => {
  const background = context(), popup = context();
  const host = 'com.example.arkscope_test';
  const first = background.chrome.runtime.sendNativeMessage(host, {id: 1, fail: process.argv[1] === 'failure'});
  const second = new Promise(resolve => popup.chrome.runtime.sendNativeMessage(host, {id: 2}, result => {
    resolve({result, error: popup.chrome.runtime.lastError?.message || null});
  }));
  const third = popup.chrome.runtime.sendNativeMessage(host, {id: 3});
  const results = await Promise.allSettled([first, second, third]);
  process.stdout.write(JSON.stringify({peak, calls, lockNames, results: results.map(value =>
    value.status === 'fulfilled' ? value : {status: value.status, error: value.reason.message})}));
})();
"""
    result = subprocess.run(["node", "-e", script, scenario], cwd=ROOT,
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


@pytest.mark.parametrize("scenario", ["success", "failure"])
def test_native_launches_are_serialized_across_popup_and_background(scenario):
    result = _probe(scenario)
    assert result["peak"] == 1
    assert [item["message"]["id"] for item in result["calls"]] == [1, 2, 3]
    assert len(result["lockNames"]) == 3
    assert len(set(result["lockNames"])) == 1
    assert result["results"][1]["value"] == {"result": {"id": 2}, "error": None}
    assert result["results"][2]["value"] == {"id": 3}
    if scenario == "failure":
        assert result["results"][0] == {"status": "rejected", "error": "consent_rejected"}


def test_missing_lock_api_never_silently_launches_concurrent_native_requests():
    result = _probe("missing_locks")
    assert result["calls"] == []
    assert result["results"][0]["error"] == "native_messaging_lock_unavailable"
    assert result["results"][1]["value"]["error"] == "native_messaging_lock_unavailable"


def test_popup_routes_reconciliation_through_the_background_owner():
    result = _run()
    requests = [message for message in result["sent"]
                if message["action"] == "reconciliation_native_request"]
    assert requests == [{"action": "reconciliation_native_request",
                         "payload": {"action": "get_reconciliation_queue", "limit": 50}}]
    assert "chrome.runtime.sendNativeMessage" not in (
        ROOT / "extensions/sa_alpha_picks/popup.js").read_text()


@pytest.mark.parametrize("action", ["get_reconciliation_queue", "accept_reconciliation_link",
                                     "reject_reconciliation_candidate"])
def test_reconciliation_bridge_accepts_only_its_existing_actions(action):
    result = _run_background_probe("""
      chrome.runtime.id = 'test-extension';
      chrome.runtime.getURL = path => 'moz-extension://test/' + path;
      const calls = [];
      sendNativeMessage2 = async message => { calls.push(message); return {status:'ok'}; };
      const sender = {id:chrome.runtime.id, url:chrome.runtime.getURL('popup.html')};
      const result = await forwardReconciliationNative({action:""" + json.dumps(action) + """, limit:50}, sender);
      return {calls,result};
    """)
    assert result == {"calls": [{"action": action, "limit": 50}], "result": {"status": "ok"}}


@pytest.mark.parametrize("mutation", ["wrong_id", "web_page", "other_extension_page", "other_action", "array_payload"])
def test_reconciliation_bridge_rejects_other_senders_and_actions(mutation):
    result = _run_background_probe("""
      chrome.runtime.id = 'test-extension';
      chrome.runtime.getURL = path => 'moz-extension://test/' + path;
      let calls = 0;
      sendNativeMessage2 = async () => { calls++; return {status:'ok'}; };
      const sender = {id:chrome.runtime.id, url:chrome.runtime.getURL('popup.html')};
      let payload = {action:'get_reconciliation_queue', limit:50};
      const mutation = """ + json.dumps(mutation) + """;
      if (mutation === 'wrong_id') sender.id = 'other';
      if (mutation === 'web_page') sender.url = 'https://seekingalpha.com/';
      if (mutation === 'other_extension_page') sender.url = chrome.runtime.getURL('other.html');
      if (mutation === 'other_action') payload.action = 'save_company_data';
      if (mutation === 'array_payload') payload = [payload];
      return {result:await forwardReconciliationNative(payload, sender), calls};
    """)
    assert result == {"calls": 0, "result": {"status": "error", "error_code": "extension_request_rejected"}}
