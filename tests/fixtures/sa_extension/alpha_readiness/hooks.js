// Runs after the unmodified production background, in its actual extension realm.
async function readinessRun(message) {
  const origin = message.origin;
  const scenario = message.scenario;
  const url = origin + "/alpha-picks/picks/current?case=" + scenario;
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  const control = action => fetch(origin + "/" + action + "?case=" + scenario,
    {signal: AbortSignal.timeout(3000)}).then(r => r.json());
  const snapshot = tab => ({id: tab.id, url: tab.url || "", pendingUrl: tab.pendingUrl || "", status: tab.status});
  const report = {scenario, events: [], createdTabs: [], nativeStart: readinessNativeCalls.length,
    helper: scenario === "news_control" ? "waitForTabLoad" : "waitForAlphaPicksTableReady",
    accessInspector: "inspectSaAccess", readinessTimeoutMs: 6000};
  let navigation;
  let timer;
  let tab;
  let waiting;
  const updated = (id, change, current) => {
    if (tab && id === tab.id) report.events.push({change, tab: snapshot(current)});
  };
  const created = current => report.createdTabs.push(snapshot(current));
  report.apisUntouched = Object.entries(readinessBrowserApis).every(([name, original]) =>
    original === (name === "executeScript" ? chrome.scripting.executeScript : chrome.tabs[name]));
  report.hostPermissions = chrome.runtime.getManifest().host_permissions;
  report.grantedPermissions = await chrome.permissions.getAll();
  report.backgroundUrl = globalThis.location.href;
  report.browser = navigator.userAgent;
  report.originalTabIds = (await chrome.tabs.query({})).map(current => current.id);
  chrome.tabs.onUpdated.addListener(updated);
  chrome.tabs.onCreated.addListener(created);

  const result = await saAcquisition.runTask({operation: "alpha_picks_sync", mode: "quick"}, async task => {
    saAcquisitionTask = task;
    try {
      tab = await task.navigate({kind: "create", destinationClass: "picks"}, () =>
        chrome.tabs.create({url: scenario === "fresh_blank" ? "about:blank" : url, active: false}));
      report.created = snapshot(tab);
      if (scenario === "response_started") {
        const deadline = Date.now() + 3000;
        while (!(await control("state")).header_sent) {
          if (Date.now() > deadline) throw new Error("fixture response never started");
          await pause(30);
        }
        // Observe URL publication before HTML bytes, without claiming that the
        // browser has not already committed an empty document at response headers.
        report.beforeHtmlSamples = [];
        for (let index = 0; index < 10; index++) {
          report.beforeHtmlSamples.push(snapshot(await chrome.tabs.get(tab.id)));
          await pause(30);
        }
      }
      if (scenario === "table_loading") {
        const deadline = Date.now() + 5000;
        while (!(await control("state")).rendered) {
          if (Date.now() > deadline) throw new Error("fixture table never rendered");
          await pause(30);
        }
      }
      report.initial = snapshot(await chrome.tabs.get(tab.id));
      report.serverBeforeWait = await control("state");
      report.expectedUrlAlreadyPublished = report.initial.url === url;
      const start = Date.now();
      // Timers release only fixture gates. Readiness itself never gets replaced.
      navigation = new Promise((resolve, reject) => {
        timer = setTimeout(async () => {
          try {
            if (scenario === "fresh_blank") {
              await task.navigate({kind: "update", destinationClass: "picks"}, () => chrome.tabs.update(tab.id, {url}));
            }
            await control("release_headers");
            if (scenario === "response_started") await control("release_document");
            if (scenario === "news_control") {
              await pause(1200);
              await control("release_body");
            }
            resolve();
          } catch (error) { reject(error); }
        }, 750);
      });
      // Attach a rejection handler immediately, including when readiness fails early.
      navigation.catch(() => {});
      waiting = (scenario === "news_control"
        ? waitForTabLoad(tab.id, 6000, "/alpha-picks/picks/current").then(() => ({ok: true}))
        : waitForAlphaPicksTableReady(tab.id, url, "offline current picks", 6000))
        .then(value => ({kind: "resolved", value}), error => ({kind: "rejected", error: String(error), stack: error.stack || ""}));
      let watchdog;
      report.outcome = await Promise.race([
        waiting,
        new Promise(resolve => { watchdog = setTimeout(() => resolve({kind: "fixture_watchdog"}), 8500); }),
      ]);
      clearTimeout(watchdog);
      report.elapsedMs = Date.now() - start;
      report.atOutcome = snapshot(await chrome.tabs.get(tab.id));
      report.serverAtOutcome = await control("state");
      await navigation;
      // Independently establish the page is usable even if the old helper rejected.
      const deadline = Date.now() + 3500;
      while (!(await control("state")).rendered) {
        if (Date.now() > deadline) throw new Error("fixture table never rendered after navigation");
        await pause(30);
      }
      report.table = await inspectAlphaPicksReadiness(tab.id, "/alpha-picks/picks/current");
      report.document = (await chrome.scripting.executeScript({target: {tabId: tab.id}, func: () => ({
        url: location.href, readyState: document.readyState, rows: document.querySelectorAll("table tbody tr").length,
      })}))[0].result;
      return {status: report.outcome.kind === "resolved" && report.outcome.value.ok ? "ok" : "error"};
    } catch (error) {
      report.fixtureError = String(error);
      report.fixtureStack = error.stack || "";
      return {status: "error"};
    } finally {
      try {
        await control("release_headers");
        if (scenario === "response_started") await control("release_document");
        await control("release_body");
        if (navigation) await navigation.catch(() => {});
      } finally {
        clearTimeout(timer);
        if (tab) await safeRemoveTab(tab.id);
        if (waiting) await waiting;
        saAcquisitionTask = null;
      }
    }
  }).finally(() => {
    chrome.tabs.onUpdated.removeListener(updated);
    chrome.tabs.onCreated.removeListener(created);
  });
  report.acquisitionResult = result;
  report.nativeCalls = readinessNativeCalls.slice(report.nativeStart);
  report.remainingTabs = (await chrome.tabs.query({})).map(snapshot);
  report.serverFinal = await control("state");
  return report;
}

chrome.runtime.onMessage.addListener((message, _sender, respond) => {
  if (message.action !== "offline_alpha_readiness") return;
  readinessRun(message).then(respond, error => respond({fixtureError: String(error), stack: error.stack || ""}));
  return true;
});
