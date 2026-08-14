import fs from "node:fs";
import vm from "node:vm";


const [protocolPath, diagnosticsPath, telemetryPath, backgroundPath, scenario] =
  process.argv.slice(2);

function source(path) {
  return fs.readFileSync(path, "utf8");
}

function createStorage(initial = {}) {
  const data = structuredClone(initial);
  return {
    data,
    async get(keys) {
      const result = {};
      for (const key of keys) {
        if (Object.hasOwn(data, key)) result[key] = structuredClone(data[key]);
      }
      return result;
    },
    async set(values) {
      for (const [key, value] of Object.entries(values)) {
        data[key] = structuredClone(value);
      }
    },
  };
}

function loadCore() {
  const context = vm.createContext({
    console,
    Date,
    TextEncoder,
    URL,
    setTimeout,
    clearTimeout,
    structuredClone,
  });
  vm.runInContext(source(protocolPath), context, {filename: protocolPath});
  vm.runInContext(source(diagnosticsPath), context, {filename: diagnosticsPath});
  vm.runInContext(source(telemetryPath), context, {filename: telemetryPath});
  return context;
}

function validEntry(index = 1) {
  return {
    stage: "content_parse",
    reason_code: "parser_empty",
    target_kind: "article_detail",
    target_ref: `alpha-opaque-${index}`,
    retryable: true,
    attempt_count: 1,
    message: "Article detail could not be parsed.",
  };
}

function completeProtocol(context) {
  return context.SAExtensionRunProtocol.deriveRunResult({
    schema_version: 1,
    operation: "alpha_picks_sync",
    mode: "quick",
    phases: {
      current_picks: {state: "complete", reason_code: null},
      closed_picks: {state: "complete", reason_code: null},
      article_details: {state: "complete", reason_code: null},
      reconciliation: {state: "complete", reason_code: null},
    },
    item_outcomes: [],
  });
}

function createChrome(storage) {
  const listener = {addListener() {}};
  return {
    runtime: {
      lastError: null,
      onMessage: listener,
      onInstalled: listener,
      onStartup: listener,
      sendMessage() { return Promise.resolve(); },
      sendNativeMessage(_host, _message, callback) {
        callback({status: "ok", persisted: true, run_id: 1});
      },
    },
    alarms: {onAlarm: listener},
    storage: {local: storage},
    tabs: {
      async create() { return {id: 7}; },
      async update() { return {}; },
      async remove() {},
      async reload() {},
    },
    scripting: {async executeScript() { return [{result: {}}]; }},
  };
}

function loadBackground() {
  const storage = createStorage();
  const imports = [];
  const context = vm.createContext({
    console,
    crypto: {randomUUID: () => "00000000-0000-4000-8000-000000000001"},
    Date,
    Math,
    Promise,
    TextEncoder,
    URL,
    setTimeout,
    clearTimeout,
    structuredClone,
    chrome: createChrome(storage),
  });
  context.importScripts = (...names) => {
    for (const name of names) {
      imports.push(name);
      const path = new URL(name, `file://${backgroundPath}`).pathname;
      vm.runInContext(source(path), context, {filename: path});
    }
  };
  vm.runInContext(source(backgroundPath), context, {filename: backgroundPath});
  return {context, imports, storage};
}

function projection(entry) {
  return {
    stage: entry.stage,
    reason_code: entry.reason_code,
    target_kind: entry.target_kind,
    target_ref: entry.target_ref,
    retryable: entry.retryable,
  };
}

async function runAlphaFailureBranch(context, kind) {
  const collector = context.SAExtensionDiagnostics.createCollector({
    now: () => Date.UTC(2026, 7, 14, 2),
  });
  context.sendProgress = function () {};
  context.sleep = async function () {};
  context.chrome.tabs.update = async function () {};
  context.waitForTabLoad = async function () {};
  context.waitForArticlesReady = async function () { return {ok: true}; };
  context.scrollToLoadAll = async function () {};
  context.injectArticlesListScraper = async function () {
    return [{
      article_id: "alpha-opaque-1",
      url: "https://seekingalpha.com/alpha-picks/articles/alpha-opaque-1",
    }];
  };
  context.waitForArticleReady = async function () {
    return kind === "readiness"
      ? {ok: false, reason_code: "login_required"}
      : {ok: true};
  };
  context.settleArticleBeforeScroll = async function () {};
  context.injectDetailScraper = async function () {
    if (kind === "unknown") throw new Error("private article body");
    if (kind === "parser") return {error: "private article body"};
    return {title: "Fixture", body_markdown: "Fixture body"};
  };
  context.scrollToComments = async function () { return {}; };
  context.injectCommentsScraper = async function () { return {comments: []}; };
  context.sendNativeMessage2 = async function (message) {
    if (message.action === "save_articles_meta") {
      return {
        status: "ok",
        saved: 1,
        need_content: [{
          article_id: "alpha-opaque-1",
          url: "https://seekingalpha.com/alpha-picks/articles/alpha-opaque-1",
        }],
        need_comments: [],
        unresolved_symbols: [],
        reconciliation: {status: "ok", enrichment: []},
      };
    }
    if (message.action === "save_article_content") {
      return kind === "database"
        ? {status: "error", error_code: "database_busy", retryable: true}
        : {status: "ok", ok: true, reconciliation: {status: "ok"}};
    }
    return {status: "ok", unresolved_symbols: [], review_queue: {total: 0, events: []}};
  };
  const summary = await context.doDetailFetch(1, [], "quick", collector);
  return {failed: summary.failed, diagnostics: collector.freeze()};
}

async function runCommentFailure(context) {
  const collector = context.SAExtensionDiagnostics.createCollector({
    now: () => Date.UTC(2026, 7, 14, 2),
  });
  context.sendProgress = function () {};
  context.sleep = async function () {};
  context.chrome.tabs.update = async function () {};
  context.waitForTabLoad = async function () {};
  context.waitForArticlesReady = async function () { return {ok: true}; };
  context.scrollToLoadAll = async function () {};
  context.injectArticlesListScraper = async function () {
    return [{
      article_id: "alpha-opaque-1",
      url: "https://seekingalpha.com/alpha-picks/articles/alpha-opaque-1",
    }];
  };
  context.waitForArticleReady = async function () { return {ok: true}; };
  context.settleArticleBeforeScroll = async function () {};
  context.scrollToComments = async function () { return {}; };
  context.injectCommentsScraper = async function () { return {comments: []}; };
  context.sendNativeMessage2 = async function (message) {
    if (message.action === "save_articles_meta") {
      return {
        status: "ok",
        saved: 1,
        need_content: [],
        need_comments: [{
          article_id: "alpha-opaque-1",
          url: "https://seekingalpha.com/alpha-picks/articles/alpha-opaque-1",
        }],
        unresolved_symbols: [],
        reconciliation: {status: "ok", enrichment: []},
      };
    }
    if (message.action === "save_comments_only") {
      return {status: "ok", comment_scan_usable: false};
    }
    return {status: "ok", unresolved_symbols: [], review_queue: {total: 0, events: []}};
  };
  await context.doDetailFetch(1, [], "quick", collector);
  return collector.freeze().entries[0];
}

async function run() {
  if (scenario === "collector_cap") {
    const context = loadCore();
    let timestampReads = 0;
    const collector = context.SAExtensionDiagnostics.createCollector({
      now() {
        timestampReads += 1;
        return Date.UTC(2026, 7, 14, 2, 0, 0, timestampReads);
      },
    });
    const accepted = [];
    for (let index = 1; index <= 34; index += 1) {
      accepted.push(collector.record(validEntry(index)));
    }
    const envelope = collector.freeze();
    return {
      accepted_count: accepted.filter(Boolean).length,
      rejected_count: collector.rejectedCount(),
      timestamp_reads: timestampReads,
      envelope,
      deep_frozen: Object.isFrozen(envelope)
        && Object.isFrozen(envelope.entries)
        && envelope.entries.every(Object.isFrozen),
    };
  }

  if (scenario === "collector_rejection") {
    const context = loadCore();
    const collector = context.SAExtensionDiagnostics.createCollector({
      now: () => Date.UTC(2026, 7, 14, 2),
    });
    const accepted = [
      collector.record({...validEntry(), stage: "provider_guess"}),
      collector.record({...validEntry(), target_ref: "https://seekingalpha.com/private"}),
      collector.record({...validEntry(), message: "secret@example.com"}),
      collector.record({...validEntry(), message: "Bearer secret-token"}),
      collector.record({...validEntry(), message: "/home/operator/private.db"}),
    ];
    return {accepted, envelope: collector.freeze()};
  }

  if (scenario === "alpha_failure_branches") {
    const {context} = loadBackground();
    const background = source(backgroundPath);
    const branches = [];
    for (const kind of ["readiness", "parser", "database", "unknown"]) {
      const branch = await runAlphaFailureBranch(context, kind);
      branch.recorded_before_increment = branch.failed === branch.diagnostics.entries.length;
      branches.push(branch);
    }
    return {
      branches,
      raw_increment_sites: background.match(/\b(?:failed|detailFailed)\s*\+\+/g) || [],
      recording_increment_sites: (
        background.match(/\+=\s*record(?:Native)?ExtensionFailure\s*\(/g) || []
      ).length,
    };
  }

  if (scenario === "market_news_failures") {
    const {context} = loadBackground();
    const collector = context.SAExtensionDiagnostics.createCollector({
      now: () => Date.UTC(2026, 7, 14, 2),
    });
    context.sendProgress = function () {};
    context.sleep = async function () {};
    context.withTimeout = async function (promise) { return await promise; };
    context.cleanupCollectorTabs = async function () {};
    context.registerCollectorTab = async function () {};
    context.unregisterCollectorTab = async function () {};
    context.safeRemoveTab = async function () {};
    context.waitForMarketNewsPageLoad = async function () {};
    context.waitForTabLoad = async function () {};
    context.waitForMarketNewsReady = async function () { return {ok: true}; };
    context.getMarketNewsRecentIds = async function () { return []; };
    context.scrollMarketNews = async function () {};
    context.injectMarketNewsScraper = async function () { return []; };
    context.saveMarketNewsState = async function () {};
    context.fetchMarketNewsDetailWithRetry = async function (_tab, item) {
      if (item.news_id === "news-opaque-2") throw new Error("private article body");
      return {ok: false, reason_code: "access_restricted"};
    };
    context.sendNativeMessage2 = async function (message) {
      if (message.action === "save_market_news") {
        return {
          status: "ok",
          need_detail: [
            {news_id: "news-opaque-1", url: "https://seekingalpha.com/news/1"},
            {news_id: "news-opaque-2", url: "https://seekingalpha.com/news/2"},
          ],
        };
      }
      return {status: "ok"};
    };
    const summary = await context.doMarketNewsRefresh("quick", {
      diagnostics: collector,
    });
    return {detail_failed: summary.detail_failed, diagnostics: collector.freeze()};
  }

  if (scenario === "comment_and_unknown") {
    const {context} = loadBackground();
    const comment = await runCommentFailure(context);
    const unknown = (await runAlphaFailureBranch(context, "unknown"))
      .diagnostics.entries[0];
    return {comment: projection(comment), unknown: projection(unknown)};
  }

  if (scenario === "native_failure_mapping") {
    const {context} = loadBackground();
    const inputs = {
      transport: null,
      invalid: {status: "error", error_code: "invalid_native_response"},
      busy: {status: "error", error_code: "database_busy", retryable: true},
      integrity: {
        status: "error",
        error_code: "database_integrity_failed",
        retryable: false,
      },
      write: {status: "error", error_code: "database_write_failed", retryable: true},
    };
    return Object.fromEntries(Object.entries(inputs).map(([key, value]) => {
      const mapped = context.extensionNativeFailure(value);
      return [key, {
        stage: mapped.stage,
        reason_code: mapped.reason_code,
        retryable: mapped.retryable,
      }];
    }));
  }

  if (scenario === "successful_job") {
    const {context} = loadBackground();
    const submissions = [];
    context.extensionTelemetryController = {
      async flush() { return []; },
      async submit(event) {
        submissions.push(structuredClone(event));
        return {delivery: "persisted", run_id: submissions.length};
      },
    };
    const jobResult = await context.enqueueSaSyncJob({
      displayName: "fixture",
      operation: "alpha_picks_sync",
      mode: "quick",
    }, async () => ({
      current: {status: "ok"},
      closed: {status: "ok"},
      details: {failed: 0},
    }));
    let thrown = false;
    try {
      await context.enqueueSaSyncJob({
        displayName: "failing fixture",
        operation: "alpha_picks_sync",
        mode: "quick",
      }, async () => {
        throw new Error("private article body");
      });
    } catch (_) {
      thrown = true;
    }
    return {
      job_result: jobResult,
      submitted: submissions[0],
      thrown,
      failed_submitted: submissions[1],
    };
  }

  if (scenario === "telemetry_freeze") {
    const context = loadCore();
    const storage = createStorage();
    let delivered = null;
    const controller = context.SAExtensionTelemetry.createController({
      storage,
      now: () => Date.UTC(2026, 7, 14, 2),
      uuid: () => "evt-diagnostics",
      deliver: async (record) => {
        delivered = structuredClone(record);
        return {persisted: false, error_code: "sidecar_unavailable"};
      },
    });
    const collector = context.SAExtensionDiagnostics.createCollector({
      now: () => Date.UTC(2026, 7, 14, 2),
    });
    collector.record(validEntry());
    const extensionDiagnostics = collector.freeze();
    await controller.submit({
      client_event_id: "evt-diagnostics",
      started_at: "2026-08-14T02:00:00.000Z",
      finished_at: "2026-08-14T02:00:01.000Z",
      result: completeProtocol(context),
      extension_diagnostics: extensionDiagnostics,
    });
    let mutationChangedRecord = false;
    try {
      extensionDiagnostics.entries[0].reason_code = "unknown_failure";
    } catch (_) {}
    const queued = storage.data[context.SAExtensionTelemetry.OUTBOX_STORAGE_KEY][0];
    mutationChangedRecord = queued.extension_diagnostics.entries[0].reason_code
      !== "parser_empty";
    return {
      queued_diagnostics: queued.extension_diagnostics,
      delivered_diagnostics: delivered.extension_diagnostics,
      mutation_changed_record: mutationChangedRecord,
      immutable_includes_diagnostics: JSON.stringify(queued).includes("extension_diagnostics"),
    };
  }

  throw new Error(`unknown scenario: ${scenario}`);
}

process.stdout.write(JSON.stringify(await run()));
