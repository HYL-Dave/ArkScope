"""Mounted contracts for the bounded SA extension controls and repair UI."""

from __future__ import annotations

import base64
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "extensions" / "sa_alpha_picks"
RUNNER = ROOT / "tests" / "js" / "run_sa_extension_popup_fixture.mjs"
BACKGROUND = EXTENSION / "background.js"
POPUP_HTML = EXTENSION / "popup.html"
POPUP_JS = EXTENSION / "popup.js"
CATALOG = EXTENSION / "popup_action_catalog.js"


_BACKGROUND_PROBE = r"""
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const sourcePath = process.argv[1];
const body = Buffer.from(process.argv[2], "base64").toString("utf8");
const listener = {addListener() {}, removeListener() {}};
const storage = {};
const context = {
  URL, Date, Math, Promise, Set, TextEncoder, crypto: require("node:crypto").webcrypto,
  console: {info() {}, warn() {}, error() {}, log() {}},
  setTimeout, clearTimeout,
  chrome: {
    runtime: {
      onMessage: listener, onInstalled: listener, onStartup: listener,
      sendMessage() { return Promise.resolve(); },
      sendNativeMessage(_host, message, callback) {
        if (message.action === "get_extension_action_limits") {
          callback({status: "ok", limits: {
            alpha_picks_full_comment_recovery_batch: 10,
            alpha_picks_deep_comment_recovery_batch: 50,
          }});
          return;
        }
        callback({status: "ok", persisted: true});
      },
      lastError: null,
    },
    alarms: {onAlarm: listener},
    tabs: {onUpdated: listener, onRemoved: listener},
    scripting: {},
    storage: {local: {
      async get(keys) {
        const names = Array.isArray(keys) ? keys : [keys];
        return Object.fromEntries(names.map((key) => [key, storage[key]]));
      },
      async set(values) { Object.assign(storage, values); },
    }},
  },
};
vm.createContext(context);
context.importScripts = (...names) => names.forEach((name) => {
  const dependency = path.join(path.dirname(sourcePath), name);
  vm.runInContext(fs.readFileSync(dependency, "utf8"), context, {filename: dependency});
});
vm.runInContext(fs.readFileSync(sourcePath, "utf8"), context, {filename: sourcePath});
Promise.resolve(vm.runInContext("(async function () {" + body + "})()", context))
  .then((value) => process.stdout.write(JSON.stringify(value)))
  .catch((error) => { console.error(error); process.exit(1); });
"""


ACTION_LIMITS = {
    "status": "ok",
    "limits": {
        "alpha_picks": {
            "quick": {
                "article_list_rounds": 5,
                "detail_enrichment_limit": 4,
                "comment_scroll_rounds": 12,
                "comment_scroll_ms": 12000,
                "comment_stable_rounds": 2,
                "configured_comment_recovery_batch": 0,
            },
            "full": {
                "article_list_rounds": 200,
                "detail_enrichment_limit": 12,
                "comment_scroll_rounds": 80,
                "comment_scroll_ms": 60000,
                "comment_stable_rounds": 4,
                "configured_comment_recovery_batch": 10,
            },
            "backfill": {
                "article_list_rounds": 200,
                "detail_enrichment_limit": 20,
                "comment_scroll_rounds": 140,
                "comment_scroll_ms": 120000,
                "comment_stable_rounds": 5,
                "configured_comment_recovery_batch": 50,
            },
        },
        "market_news": {
            "quick": {"list_rounds": 3, "detail_attempts": 18},
            "catchup": {
                "list_rounds": 3,
                "current_detail_attempts": 12,
                "backlog_detail_attempts": 6,
                "total_detail_attempts": 18,
                "window_hours": 24,
            },
        },
        "recovery": {
            "max_window_hours": 168,
            "max_list_rounds": 60,
            "max_elapsed_ms": 600000,
            "stable_rounds": 5,
            "detail_attempts_per_pass": 80,
        },
    },
}


def _preview(kind: str, *, targets: int, can_start: bool = True):
    interval = (
        {
            "start_at": "2026-07-19T11:45:38+00:00",
            "end_at": "2026-07-20T14:02:20+00:00",
            "anchor_verified": False,
        }
        if kind == "incident_window"
        else None
    )
    return {
        "status": "ready" if targets else "discovery_only" if can_start else "no_work",
        "kind": kind,
        "target_count": targets,
        "can_start": can_start,
        "manifest": {
            "schema_version": 1,
            "hash_algorithm": "sha256",
            "kind": kind,
            "interval": interval,
            "targets": [
                {
                    "news_id": f"opaque-{index}",
                    "pathname": f"/news/{index}",
                    "published_at": "2026-07-19T12:00:00+00:00",
                    "body_present": False,
                }
                for index in range(targets)
            ],
            "source_run_ids": [17] if kind == "recorded_failures" else [],
            "bounds": {"detail_attempts_per_pass": 80},
        },
        "manifest_hash": "a" * 64,
        "discovery": {
            "enabled": kind == "incident_window" and can_start,
            "missing_metadata_count": None,
            "max_list_scroll_rounds": 60,
            "max_elapsed_ms": 600000,
            "stable_rounds": 5,
        },
    }


def _run(scenario: str = "snapshot", **fixture):
    fixture.setdefault("actionLimits", ACTION_LIMITS)
    fixture.setdefault(
        "previews",
        {
            "recorded_failures": _preview(
                "recorded_failures", targets=0, can_start=False
            ),
            "incident_window": _preview("incident_window", targets=0),
        },
    )
    completed = subprocess.run(
        [
            "node",
            str(RUNNER),
            str(EXTENSION),
            scenario,
            json.dumps(fixture, separators=(",", ":")),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _run_background_probe(body: str):
    completed = subprocess.run(
        [
            "node",
            "-e",
            _BACKGROUND_PROBE,
            str(BACKGROUND),
            base64.b64encode(body.encode("utf-8")).decode("ascii"),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_popup_groups_exactly_five_normal_actions_as_three_plus_two():
    result = _run()
    actions = result["actions"]
    assert [action["label"] for action in actions] == [
        "Quick Update",
        "Full Article Scan",
        "Deep Repair Scan",
        "Sync Latest News",
        "Catch Up News (24h)",
    ]
    assert [action["group"] for action in actions] == [
        "alpha-picks",
        "alpha-picks",
        "alpha-picks",
        "market-news",
        "market-news",
    ]
    assert result["autoSyncGroups"] == {
        "alpha": "alpha-picks",
        "market": "market-news",
    }
    install_copy = (EXTENSION / "install_firefox.sh").read_text(encoding="utf-8")
    firefox_guide = (EXTENSION / "FIREFOX.md").read_text(encoding="utf-8")
    assert "Quick Update" in install_copy
    assert "Quick Update" in firefox_guide
    assert "Quick Refresh" not in install_copy
    assert "Quick Refresh" not in firefox_guide


def test_each_normal_action_has_one_hover_focus_and_aria_description_owner():
    result = _run("focus_descriptions")
    description_ids = [action["descriptionId"] for action in result["actions"]]
    assert len(description_ids) == len(set(description_ids)) == 5
    assert all(action["description"] for action in result["actions"])
    assert all(action["title"] is None for action in result["actions"])
    html = POPUP_HTML.read_text(encoding="utf-8")
    assert ".action-control:hover .action-description" in html
    assert ".action-control:focus-within .action-description" in html


def test_action_disclosure_has_scope_when_to_use_and_non_guarantee_for_every_action():
    result = _run()
    assert len(result["disclosure"]) == 5
    assert all(len(row["cells"]) == 4 for row in result["disclosure"])
    assert all(all(cell for cell in row["cells"]) for row in result["disclosure"])
    assert "What these actions do" in result["bodyText"]
    assert not (EXTENSION / "help.html").exists()


def test_alpha_rows_show_exact_deep_bounds_and_never_use_market_18_30_80_limits():
    result = _run()
    rows = {row["id"]: " ".join(row["cells"]) for row in result["disclosure"]}
    assert "5 article-list rounds" in rows["quick"]
    assert "200 article-list rounds" in rows["full"]
    assert "80 comment-scroll rounds" in rows["full"]
    assert "200 article-list rounds" in rows["backfill"]
    assert "140 comment-scroll rounds" in rows["backfill"]
    assert "120 seconds" in rows["backfill"]
    assert all(
        "no separate global Alpha detail cap" in rows[action]
        for action in ("quick", "full", "backfill")
    )
    assert "4 additional reconciliation enrichments" in rows["quick"]
    assert "12 additional reconciliation enrichments" in rows["full"]
    assert "20 additional reconciliation enrichments" in rows["backfill"]
    assert "80 Market News details" not in rows["backfill"]
    assert "30 Market News details" not in rows["full"]
    assert "18 Market News details" not in rows["quick"]


def test_configured_comment_limits_render_or_report_configured_limit_unavailable():
    available = _run()
    assert "10 configured pending comment rows" in available["bodyText"]
    assert "50 configured pending comment rows, including parked rows" in available["bodyText"]

    unavailable_limits = json.loads(json.dumps(ACTION_LIMITS))
    unavailable_limits["limits"]["alpha_picks"]["full"][
        "configured_comment_recovery_batch"
    ] = None
    unavailable_limits["limits"]["alpha_picks"]["backfill"][
        "configured_comment_recovery_batch"
    ] = None
    unavailable = _run(actionLimits=unavailable_limits)
    assert unavailable["bodyText"].count("configured limit unavailable") >= 2


def test_retry_recorded_failures_exists_only_for_real_retryable_ids():
    no_work = _run()
    assert no_work["retry"]["hidden"] is True

    previews = {
        "recorded_failures": _preview("recorded_failures", targets=3),
        "incident_window": _preview("incident_window", targets=0),
    }
    retryable_preview = _run(previews=previews)
    assert "3 recorded IDs; no time-window cutoff" in retryable_preview[
        "recoveryStatus"
    ]
    assert retryable_preview["recoveryStatusRole"] == "status"

    retryable = _run("click_retry", previews=previews)
    assert retryable["retry"] == {
        "hidden": False,
        "text": "Retry Recorded Failures (3)",
    }
    assert any(
        message.get("action") == "market_news_recovery_start"
        and message.get("kind") == "recorded_failures"
        for message in retryable["sent"]
    )


def test_advanced_recovery_is_collapsed_normally_and_promoted_by_a_real_gap():
    normal = _run(
        previews={
            "recorded_failures": _preview(
                "recorded_failures", targets=0, can_start=False
            ),
            "incident_window": {
                **_preview("incident_window", targets=0, can_start=False),
                "status": "no_work",
            },
        }
    )
    assert normal["advanced"] == {"open": False, "hidden": False}

    promoted = _run()
    assert promoted["advanced"]["open"] is True
    assert promoted["activeId"] == "incidentRecoveryBtn"
    assert "2026-07-19 11:45 UTC" in promoted["recoveryStatus"]
    assert "2026-07-20 14:02 UTC" in promoted["recoveryStatus"]
    assert "26h 16m" in promoted["recoveryStatus"]
    assert promoted["reviewScope"] == {
        "hidden": False,
        "text": "Review recovery scope",
    }
    assert "0 known detail IDs" in promoted["advancedPreview"]
    assert "Missing metadata cannot be counted before discovery" in promoted[
        "advancedPreview"
    ]


def test_recovery_confirmation_repeats_actual_interval_known_ids_and_discovery_scope():
    preview = _preview("incident_window", targets=2)
    result = _run(
        "click_incident",
        previews={
            "recorded_failures": _preview(
                "recorded_failures", targets=0, can_start=False
            ),
            "incident_window": preview,
        },
    )
    confirmation = result["confirmation"]
    assert confirmation["hidden"] is False
    assert "2026-07-19 11:45 UTC" in confirmation["text"]
    assert "2026-07-20 14:02 UTC" in confirmation["text"]
    assert "2 known detail IDs" in confirmation["text"]
    assert "metadata discovery" in confirmation["text"]
    assert "up to 60 list rounds" in confirmation["text"]

    escaped = _run(
        "escape_confirmation",
        previews={
            "recorded_failures": _preview(
                "recorded_failures", targets=0, can_start=False
            ),
            "incident_window": preview,
        },
    )
    assert escaped["confirmation"]["hidden"] is True
    assert escaped["activeId"] == "incidentRecoveryBtn"


def test_zero_executable_scope_starts_no_job_but_zero_known_ids_can_start_discovery():
    no_work = _run(
        "click_retry",
        previews={
            "recorded_failures": _preview(
                "recorded_failures", targets=0, can_start=False
            ),
            "incident_window": {
                **_preview("incident_window", targets=0, can_start=False),
                "status": "no_work",
            },
        },
    )
    assert not any(
        message.get("action") == "market_news_recovery_start"
        for message in no_work["sent"]
    )
    assert "No recovery work found" in no_work["recoveryStatus"]

    discovery = _run("confirm_recovery")
    assert any(
        message.get("action") == "market_news_recovery_start"
        and message.get("kind") == "incident_window"
        for message in discovery["sent"]
    )


def test_active_repair_resumes_the_same_run_id_and_manifest_hash_after_popup_reopen():
    state = {
        "status": "running",
        "run_id": 412,
        "manifest_hash": "b" * 64,
        "manifest": _preview("recorded_failures", targets=1)["manifest"],
        "progress": {"attempts": []},
        "resumable": True,
    }
    result = _run("click_resume", state=state, resumeResult=state)
    assert "Run 412" in result["recoveryStatus"]
    assert "bbbbbbbbbbbb" in result["recoveryStatus"]
    assert any(
        message == {
            "action": "market_news_recovery_resume",
            "run_id": 412,
            "manifest_hash": "b" * 64,
        }
        for message in result["sent"]
    )

    stale_terminal = _run(
        state={
            **state,
            "status": "failed",
            "counts": {
                "repaired": 0,
                "already_present": 0,
                "unavailable_at_source": 0,
                "failed_retryable": 1,
            },
            "resumable": False,
        }
    )
    assert stale_terminal["recoveryStatusRole"] == "status"


def test_recorded_and_incident_runtime_use_exact_ids_bounds_mutex_and_reach_evidence():
    source = BACKGROUND.read_text(encoding="utf-8")
    for literal in (
        "MARKET_NEWS_INCIDENT_RECOVERY_MAX_HOURS = 168",
        "MARKET_NEWS_INCIDENT_MAX_LIST_SCROLL_ROUNDS = 60",
        "MARKET_NEWS_INCIDENT_MAX_LIST_ELAPSED_MS = 600000",
        "MARKET_NEWS_INCIDENT_STABLE_ROUNDS = 5",
        "MARKET_NEWS_REPAIR_DETAIL_ATTEMPTS_PER_PASS = 80",
        "market_news_recovery_checkpoint",
        "newly_discovered_metadata_count",
        "newly_discovered_detail_saved_count",
        "reached_interval_start",
        "unresolved_interval",
    ):
        assert literal in source
    assert re.search(
        r"function enqueueMarketNewsRecovery.*?saSyncJobChain",
        source,
        re.DOTALL,
    )
    assert "target.news_id" in source
    assert "target.pathname" in source
    assert "Date.now() - startedAt" in source
    assert "typeof performance" in source
    assert "metadata_save_failed" in source
    probe = _run_background_probe(
        r"""
        var limits = await getExtensionActionLimits();
        var active = 0;
        var maxActive = 0;
        var order = [];
        executeMarketNewsRecovery = async function (request) {
          active++;
          maxActive = Math.max(maxActive, active);
          order.push("repair:" + request.kind);
          await new Promise(function (resolve) { setTimeout(resolve, 5); });
          active--;
          return { status: "succeeded" };
        };
        var routine = enqueueSaSyncJob({ displayName: "fixture routine" }, async function () {
          active++;
          maxActive = Math.max(maxActive, active);
          order.push("routine");
          await new Promise(function (resolve) { setTimeout(resolve, 5); });
          active--;
          return { status: "ok" };
        });
        var repair = enqueueMarketNewsRecovery({ kind: "recorded_failures" });
        await Promise.all([routine, repair]);
        var latest = latestRecoveryAttempts({ progress: { attempts: [
          { news_id: "opaque-a", state: "failed_retryable", attempt_count: 1 },
          { news_id: "opaque-a", state: "repaired", attempt_count: 2 },
          { news_id: "opaque-c", state: "failed_retryable", attempt_count: 1 },
        ] } });
        return {
          limits: limits,
          maxActive: maxActive,
          order: order,
          repairedNeedsRetry: targetNeedsAttempt(
            { news_id: "opaque-a", pathname: "/news/1", body_present: false }, latest
          ),
          unseenNeedsRetry: targetNeedsAttempt(
            { news_id: "opaque-b", pathname: "/news/2", body_present: false }, latest
          ),
          failedNeedsRetry: targetNeedsAttempt(
            { news_id: "opaque-c", pathname: "/news/3", body_present: false }, latest
          ),
        };
        """
    )
    assert probe["limits"] == ACTION_LIMITS
    assert probe["maxActive"] == 1
    assert probe["order"] == ["routine", "repair:recorded_failures"]
    assert probe["repairedNeedsRetry"] is False
    assert probe["unseenNeedsRetry"] is True
    assert probe["failedNeedsRetry"] is False


def test_popup_stays_english_keyboard_coherent_and_free_of_true_text_clipping():
    result = _run(
        "focus_descriptions",
        storage={
            "lastRefresh": {
                "batch_ts": "2026-07-20T14:02:20+00:00",
                "mode": "quick",
                "current": {"status": "ok", "count": 10},
                "closed": {
                    "status": "error",
                    "error": "PLANTED_RAW_BACKEND_DETAIL /home/operator/secret.db",
                },
                "details": {
                    "error": "PLANTED_RAW_ARTICLE_DETAIL sqlite3 traceback"
                },
            },
            "arkscope.sa.lastRun.v1": {
                "client_event_id": "opaque-event",
                "operation": "market_news_sync",
                "mode": "quick",
                "derived_outcome": "degraded",
                "counts": {
                    "phase_complete": 4,
                    "phase_failed": 1,
                    "phase_skipped": 0,
                    "item_total": 3,
                    "repaired": 1,
                    "already_present": 0,
                    "unavailable_at_source": 0,
                    "failed_retryable": 2,
                },
                "started_at": "2026-07-20T14:00:00+00:00",
                "finished_at": "2026-07-20T14:02:20+00:00",
                "audit_state": "pending",
                "audit_reason_code": "telemetry_unavailable",
                "run_id": None,
            }
        },
    )
    product = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (POPUP_HTML, POPUP_JS, CATALOG)
    )
    assert re.search(r"[\u3400-\u9fff]", product) is None
    assert all(action["description"] for action in result["actions"])
    assert "overflow: hidden" not in POPUP_HTML.read_text(encoding="utf-8")
    assert "text-overflow: ellipsis" not in POPUP_HTML.read_text(encoding="utf-8")
    assert "aria-describedby" in result["bodyHtml"]
    assert "Market News (quick): Needs attention" in result["lastRunStatus"]
    assert "2026-07-20 14:02 UTC" in result["lastRunStatus"]
    assert "4/5 phases complete" in result["lastRunStatus"]
    assert "3 items" in result["lastRunStatus"]
    assert "2 detail failures recorded" in result["lastRunStatus"]
    assert "Audit pending" in result["lastRunStatus"]
    assert "Audit recording is unavailable" in result["lastRunStatus"]
    assert "PLANTED_RAW_BACKEND_DETAIL" not in result["bodyText"]
    assert "PLANTED_RAW_ARTICLE_DETAIL" not in result["bodyText"]
