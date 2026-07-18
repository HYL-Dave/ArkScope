from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKGROUND = ROOT / "extensions" / "sa_alpha_picks" / "background.js"


_NODE_RUNNER = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const body = Buffer.from(process.argv[2], "base64").toString("utf8");
const listener = { addListener() {} };
const context = {
  URL,
  Date,
  Math,
  Promise,
  Set,
  console: { info() {}, warn() {}, error() {}, log() {} },
  setTimeout,
  clearTimeout,
  chrome: {
    runtime: {
      onMessage: listener,
      onInstalled: listener,
      onStartup: listener,
      sendMessage() { return Promise.resolve(); },
      sendNativeMessage() {},
      lastError: null,
    },
    alarms: { onAlarm: listener },
    tabs: {},
    scripting: {},
    storage: { local: {} },
  },
};
vm.createContext(context);
vm.runInContext(source, context);
Promise.resolve(vm.runInContext("(async function () {" + body + "})()", context))
  .then((value) => process.stdout.write(JSON.stringify(value)))
  .catch((error) => { console.error(error); process.exit(1); });
"""


def _run_background(body: str):
    encoded = base64.b64encode(body.encode("utf-8")).decode("ascii")
    completed = subprocess.run(
        ["node", "-e", _NODE_RUNNER, str(BACKGROUND), encoded],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


_DETAIL_FLOW_SETUP = r"""
var calls = [];
sendProgress = function () {};
sleep = async function () {};
chrome.tabs.update = async function () {};
waitForTabLoad = async function () {};
waitForArticlesReady = async function () { return { ok: true }; };
scrollToLoadAll = async function () {};
injectArticlesListScraper = async function () {
  return [{ article_id: "a1", url: "https://seekingalpha.com/alpha-picks/articles/1-a" }];
};
waitForArticleReady = async function () { return { ok: true }; };
injectDetailScraper = async function () {
  return {
    title: "Provider title",
    body_markdown: "Provider body",
    detail_ticker: "BTSG",
    detail_ticker_observed_at: "2026-07-18T12:00:00Z",
  };
};
scrollToComments = async function () {};
injectCommentsScraper = async function () { return { comments: [] }; };
"""


def test_reconciliation_enrichment_limits_are_quick_4_full_12_backfill_20():
    result = _run_background(
        "return { limits: RECONCILIATION_ENRICHMENT_LIMITS, "
        "fallback: mergeArticleFetchWork([], [{article_id: 'a1'}], 'unknown').length };"
    )
    assert result == {
        "limits": {"quick": 4, "full": 12, "backfill": 20},
        "fallback": 1,
    }


def test_normal_cache_work_and_reconciliation_enrichment_dedupe_by_article_id():
    result = _run_background(
        r"""
        var normal = [{ article_id: "a1" }, { article_id: "a2" }];
        var extra = [
          { article_id: "a2" }, { article_id: "a3" }, { article_id: "a4" },
          { article_id: "a5" }, { article_id: "a6" }, { article_id: "a7" },
        ];
        return mergeArticleFetchWork(normal, extra, "quick").map(function (item) {
          return item.article_id;
        });
        """
    )
    assert result == ["a1", "a2", "a3", "a4", "a5", "a6"]


def test_detail_save_forwards_only_scraped_detail_ticker_observation():
    result = _run_background(
        _DETAIL_FLOW_SETUP
        + r"""
        sendNativeMessage2 = async function (message) {
          calls.push(message);
          if (message.action === "save_articles_meta") {
            return {
              status: "ok", saved: 1,
              need_content: [{ article_id: "a1", url: "https://seekingalpha.com/alpha-picks/articles/1-a" }],
              need_comments: [], unresolved_symbols: [],
              reconciliation: { status: "ok", enrichment: [] },
            };
          }
          if (message.action === "save_article_content") {
            return { ok: true, reconciliation: { status: "ok" } };
          }
          return { status: "ok", unresolved_symbols: [], review_queue: { total: 0, events: [] } };
        };
        await doDetailFetch(1, [], "quick");
        return calls.filter(function (item) { return item.action === "save_article_content"; })[0];
        """
    )
    assert result["detail_ticker"] == "BTSG"
    assert result["detail_ticker_observed_at"] == "2026-07-18T12:00:00Z"
    assert "symbol" not in result
    assert "ticker" not in result


def test_end_of_refresh_audit_reads_queue_and_never_requests_legacy_auto_write():
    result = _run_background(
        _DETAIL_FLOW_SETUP
        + r"""
        sendNativeMessage2 = async function (message) {
          calls.push(message);
          if (message.action === "save_articles_meta") {
            return {
              status: "ok", saved: 1, need_content: [], need_comments: [],
              unresolved_symbols: [], reconciliation: { status: "ok", enrichment: [] },
            };
          }
          if (message.action === "audit_unresolved") {
            return {
              status: "ok", unresolved_symbols: ["BTSG"],
              review_queue: { total: 1, events: [{ symbol: "BTSG" }] },
            };
          }
          return { status: "ok" };
        };
        var summary = await doDetailFetch(1, [], "quick");
        return { calls: calls, summary: summary };
        """
    )
    audit = [item for item in result["calls"] if item["action"] == "audit_unresolved"]
    assert audit == [{"action": "audit_unresolved"}]
    payload = json.dumps(result["calls"]).lower()
    for forbidden in ("force", "sync", "closest", "fulltext"):
        assert forbidden not in payload
    assert result["summary"]["review_required"] == 1


def test_manual_fetch_requires_symbol_role_anchor_and_canonical_article_url():
    result = _run_background(
        r"""
        var opened = 0;
        var calls = [];
        cleanupCollectorTabs = async function () {};
        chrome.tabs.create = async function () { opened += 1; return { id: 1 }; };
        sendNativeMessage2 = async function (message) { calls.push(message); return { status: "ok" }; };
        var summary = await doManualFetch([
          { symbol: "BTSG", url: "https://seekingalpha.com/alpha-picks/articles/6316639-x" },
          { symbol: "BTSG", role: "entry", event_anchor_date: "Today", url: "https://example.com/6316639" },
        ]);
        return { opened: opened, calls: calls, summary: summary };
        """
    )
    assert result["opened"] == 0
    assert result["calls"] == []
    assert result["summary"]["failed"] == 2


def test_manual_fetch_never_copies_user_symbol_into_provider_or_content_evidence():
    result = _run_background(
        r"""
        var calls = [];
        var confirmationMode = false;
        sendProgress = function () {};
        cleanupCollectorTabs = async function () {};
        registerCollectorTab = async function () {};
        unregisterCollectorTab = async function () {};
        safeRemoveTab = async function () {};
        chrome.tabs.create = async function (value) { return { id: 1, value: value }; };
        chrome.tabs.update = async function () {};
        waitForTabLoad = async function () {};
        waitForArticleReady = async function () { return { ok: true }; };
        injectDetailScraper = async function () {
          return {
            title: "Provider title", publish_date: "Jul 15, 2026",
            body_markdown: "Provider body", detail_ticker: "BTSG",
            detail_ticker_observed_at: "2026-07-18T12:00:00Z",
          };
        };
        scrollToComments = async function () {};
        injectCommentsScraper = async function () { return { comments: [] }; };
        sendNativeMessage2 = async function (message) {
          calls.push(message);
          if (message.action === "resolve_reconciliation_event") {
            return { status: "ok", lineage_id: 7 };
          }
          if (message.action === "save_articles_meta") return { status: "ok" };
          if (message.action === "save_article_content") return { ok: true };
          if (message.action === "accept_reconciliation_link") {
            if (confirmationMode) {
              return {
                status: "confirmation_required",
                warnings: ["date_mismatch"],
                candidate: { article_id: "6316639", published_date: "2026-07-12" },
              };
            }
            return { status: "ok" };
          }
          return { status: "error" };
        };
        var item = {
          symbol: "ZZZZ", role: "entry", event_anchor_date: "2026-07-15",
          url: "https://seekingalpha.com/alpha-picks/articles/6316639-stock-buy",
          replace_link_id: null,
        };
        var summary = await doManualFetch([item]);
        confirmationMode = true;
        var warningSummary = await doManualFetch([item]);
        return { calls: calls, summary: summary, warningSummary: warningSummary };
        """
    )
    meta = next(item for item in result["calls"] if item["action"] == "save_articles_meta")
    body = next(item for item in result["calls"] if item["action"] == "save_article_content")
    accept = next(
        item for item in result["calls"] if item["action"] == "accept_reconciliation_link"
    )
    article = meta["articles"][0]
    assert "ticker" not in article
    assert "list_ticker" not in article
    assert "ZZZZ" not in json.dumps(article)
    assert body["detail_ticker"] == "BTSG"
    assert "ZZZZ" not in body["body_markdown"]
    assert accept["lineage_id"] == 7
    assert accept["role"] == "entry"
    assert result["summary"]["fetched"] == 1
    assert result["warningSummary"]["confirmation_required"] == [{
        "symbol": "ZZZZ",
        "role": "entry",
        "event_anchor_date": "2026-07-15",
        "url": (
            "https://seekingalpha.com/alpha-picks/articles/"
            "6316639-stock-buy"
        ),
        "article_id": "6316639",
        "lineage_id": 7,
        "replace_link_id": None,
        "warnings": ["date_mismatch"],
        "candidate": {"article_id": "6316639", "published_date": "2026-07-12"},
    }]


def test_capture_success_survives_nested_reconciliation_failure():
    result = _run_background(
        _DETAIL_FLOW_SETUP
        + r"""
        sendNativeMessage2 = async function (message) {
          if (message.action === "save_articles_meta") {
            return {
              status: "ok", saved: 1,
              need_content: [{ article_id: "a1", url: "https://seekingalpha.com/alpha-picks/articles/1-a" }],
              need_comments: [], unresolved_symbols: [],
              reconciliation: { status: "ok", enrichment: [] },
            };
          }
          if (message.action === "save_article_content") {
            return {
              ok: true,
              reconciliation: { status: "failed", error_code: "reconciliation_failed" },
            };
          }
          return { status: "ok", unresolved_symbols: [], review_queue: { total: 0, events: [] } };
        };
        return await doDetailFetch(1, [], "quick");
        """
    )
    assert result["fetched"] == 1
    assert result["failed"] == 0
    assert result["reconciliation_failed"] == 1
