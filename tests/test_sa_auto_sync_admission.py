"""Automatic triggers cannot outlive the operator intent that queued them."""

import pytest

from tests.test_sa_extension_popup import _run_background_probe


SETUP = r"""
await companyCollectorIdentity;
extensionTelemetryController.flush = async () => ({});
extensionTelemetryController.submit = async () => ({});
chrome.alarms.clear = async () => true;
chrome.alarms.create = async () => {};
"""


@pytest.mark.parametrize("key", ["alphaPicks", "marketNews"])
@pytest.mark.parametrize("reenable", [False, True])
def test_queued_intent_does_not_survive_disabling(key, reenable):
    setter = "setAlphaPicksAutoSyncEnabled" if key == "alphaPicks" else "setMarketNewsAutoSyncEnabled"
    result = _run_background_probe(SETUP + f"""
      await {setter}(true, 30);
      let release, start;
      const ready = new Promise(resolve => {{ start = resolve; }});
      const blocker = enqueueSaSyncJob({{}}, async () => {{
        start(); await new Promise(resolve => {{ release = resolve; }}); return {{}};
      }});
      await ready;
      let calls = 0;
      const pending = enqueueAutoSaSyncJob('{key}', {{}}, async () => {{ calls++; return {{}}; }});
      await {setter}(false, 30);
      {f'await {setter}(true, 30);' if reenable else ''}
      release(); await blocker; await pending;
      return {{ calls }};
    """)
    assert result["calls"] == 0


@pytest.mark.parametrize("key", ["alphaPicks", "marketNews"])
def test_disabled_late_trigger_is_skipped_but_manual_still_runs(key):
    result = _run_background_probe(SETUP + f"""
      let automatic = 0, manual = 0;
      await enqueueAutoSaSyncJob('{key}', {{}}, async () => {{ automatic++; return {{}}; }});
      await enqueueSaSyncJob({{}}, async () => {{ manual++; return {{}}; }});
      return {{ automatic, manual }};
    """)
    assert result == {"automatic": 0, "manual": 1}


def test_concurrent_triggers_coalesce_during_storage_read():
    result = _run_background_probe(SETUP + r"""
      await setAlphaPicksAutoSyncEnabled(true, 30);
      const get = chrome.storage.local.get;
      chrome.storage.local.get = async (...args) => { await Promise.resolve(); return get(...args); };
      let calls = 0;
      const run = () => enqueueAutoSaSyncJob('alphaPicks', {}, async () => { calls++; return {}; });
      await Promise.all([run(), run(), run()]);
      await run();
      return { calls };
    """)
    assert result == {"calls": 2}


def test_failed_intent_read_does_not_acquire_and_releases_coalescing():
    result = _run_background_probe(SETUP + r"""
      await setAlphaPicksAutoSyncEnabled(true, 30);
      const get = chrome.storage.local.get;
      let calls = 0;
      chrome.storage.local.get = async () => { throw new Error('storage unavailable'); };
      await enqueueAutoSaSyncJob('alphaPicks', {}, async () => { calls++; return {}; });
      chrome.storage.local.get = get;
      await enqueueAutoSaSyncJob('alphaPicks', {}, async () => { calls++; return {}; });
      return { calls };
    """)
    assert result == {"calls": 1}
