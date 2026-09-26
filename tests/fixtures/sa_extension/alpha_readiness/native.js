// Test-package native authority only. Browser tab and scripting APIs stay real.
var readinessNativeCalls = [];
var readinessBrowserApis = {
  executeScript: chrome.scripting.executeScript,
  create: chrome.tabs.create,
  update: chrome.tabs.update,
  get: chrome.tabs.get,
};

chrome.runtime.sendNativeMessage = function (_host, message, callback) {
  readinessNativeCalls.push(message);
  var reply = {status: "error", error_code: "offline_native_action_disabled"};
  if (message.action === "sa_acquisition_control") {
    if (message.operation === "status") reply = {
      status: "ok", is_owner: true, generation: 1, ledger_id: "offline-readiness",
      policy: {hour_limit: null, day_limit: null, hour_reserve: 0, day_reserve: 0},
      capability_pauses: {},
    };
    if (message.operation === "begin_task") reply = {
      status: "ok", generation: 1, token: "a".repeat(32), task_id: "b".repeat(32),
    };
    if (message.operation === "admit_navigation") reply = {
      status: "ok", allowed: true, replayed: false, attempt_id: "c".repeat(32),
    };
    if (message.operation === "finish_task") reply = {status: "ok", acquisition: {status: "ok"}};
  }
  if (message.action === "record_extension_job") reply = {status: "ok", persisted: true, run_id: 1};
  if (callback) Promise.resolve(reply).then(callback);
  else return Promise.resolve(reply);
};
