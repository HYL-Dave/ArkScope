from __future__ import annotations

import base64
import json
import re
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "extensions" / "sa_alpha_picks"
UI = EXTENSION / "reconciliation_ui.js"
POPUP_HTML = EXTENSION / "popup.html"
POPUP_JS = EXTENSION / "popup.js"
POPUP_ACTION_CATALOG = EXTENSION / "popup_action_catalog.js"


_NODE_RUNNER = r"""
const fs = require("node:fs");
const { JSDOM } = require("jsdom");
const source = fs.readFileSync(process.argv[1], "utf8");
const body = Buffer.from(process.argv[2], "base64").toString("utf8");
const dom = new JSDOM("<!doctype html><body></body>", {
  runScripts: "outside-only",
  url: "https://extension.test/",
});
dom.window.eval(source);
Promise.resolve(dom.window.eval("(async function () {" + body + "})()"))
  .then((value) => process.stdout.write(JSON.stringify(value)))
  .catch((error) => { console.error(error); process.exit(1); });
"""


_EVENT = """
{
  lineage_id: 777,
  symbol: "BTSG",
  company: "BrightSpring Health Services",
  role: "entry",
  event_anchor_date: "2026-07-15",
  reason_code: "ambiguous_candidates",
  current_link: null,
  candidates: [{
    article_id: "6316639",
    url: "https://seekingalpha.com/alpha-picks/articles/6316639-stock-buy",
    published_date: "2026-07-15",
    title: "Stock Buy: Top Health Care Services Stock Delivers Double-Digit Growth",
    evidence_codes: ["ticker_list_exact", "date_near"],
    reason_code: "review_required",
    content_state: "complete",
    requires_confirmation: false,
    replace_link_id: 999,
  }],
}
"""


def _run_ui(body: str):
    encoded = base64.b64encode(body.encode("utf-8")).decode("ascii")
    completed = subprocess.run(
        ["node", "-e", _NODE_RUNNER, str(UI), encoded],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_review_queue_renders_event_role_anchor_title_and_provenance():
    result = _run_ui(
        f"""
        const container = document.createElement("section");
        ArkScopeReconciliationUI.renderQueue(
          container, {{ events: [{_EVENT}], total: 1 }}, {{}}
        );
        return {{ text: container.textContent, html: container.innerHTML }};
        """
    )
    for text in (
        "BTSG",
        "Entry",
        "2026-07-15",
        "Stock Buy: Top Health Care Services Stock Delivers Double-Digit Growth",
        "List ticker match",
        "Article date within 3 days of event",
    ):
        assert text in result["text"]
    assert "777" not in result["text"]
    assert "999" not in result["text"]


def test_review_queue_renders_ticker_conflict_and_content_state_honestly():
    result = _run_ui(
        f"""
        const event = {_EVENT};
        event.reason_code = "ticker_metadata_conflict";
        event.candidates[0].reason_code = "ticker_metadata_conflict";
        event.candidates[0].content_state = "missing";
        event.candidates[0].evidence_codes = ["ticker_list_exact", "ticker_detail_exact"];
        const container = document.createElement("section");
        ArkScopeReconciliationUI.renderQueue(container, {{ events: [event], total: 1 }}, {{}});
        return container.textContent;
        """
    )
    assert "List and article tickers conflict" in result
    assert "Body unavailable" in result
    assert "List ticker" in result
    assert "Article ticker" in result


def test_review_queue_labels_actual_reconciliation_evidence_codes():
    labels = {
        "date_exact": "Article date matches event",
        "date_near": "Article date within 3 days of event",
        "date_outside": "Article date outside matching window",
        "date_missing": "Article or event date missing",
        "ticker_list_exact": "List ticker match",
        "ticker_detail_exact": "Article ticker match",
        "ticker_text_symbol": "Ticker mentioned in article",
        "ticker_text_company": "Company mentioned in article",
        "role_entry_strong": "Selection wording in article",
        "role_exit_strong": "Sale or removal wording in article",
        "ticker_metadata_conflict": "List and article tickers conflict",
        "user_selected": "User selected",
        "user_confirmed": "User confirmed",
        "legacy_ticker_projection": "Legacy ticker metadata",
        "date_mismatch": "Article date differs from event",
        "replacement": "Replaced previous link",
    }
    result = _run_ui(
        f"""
        const event = {_EVENT};
        event.candidates[0].evidence_codes = {json.dumps(list(labels))};
        const container = document.createElement("section");
        ArkScopeReconciliationUI.renderQueue(container, {{ events: [event], total: 1 }}, {{}});
        return container.querySelector(".reconciliation-evidence")?.textContent || "";
        """
    )
    for code, label in labels.items():
        assert label in result
        assert code not in result


@pytest.mark.parametrize("reason", ["role_phrase_missing", "review_required", "future_reason"])
def test_unassigned_article_role_does_not_demand_manual_review(reason):
    result = _run_ui(
        f"""
        const event = {_EVENT};
        event.reason_code = {json.dumps(reason)};
        event.candidates[0].reason_code = {json.dumps(reason)};
        const container = document.createElement("section");
        ArkScopeReconciliationUI.renderQueue(container, {{ events: [event], total: 1 }}, {{}});
        return container.textContent;
        """
    )
    assert "manual review required" not in result.lower()
    assert "optional" in result.lower()
    if reason == "role_phrase_missing":
        assert "Role unassigned" in result


@pytest.mark.parametrize(("reason", "label"), [
    ("no_candidates", "No candidate articles"),
    ("date_missing", "Article or event date missing"),
    ("outside_date_window", "Article date outside matching window"),
    ("ticker_mismatch", "Article ticker does not match event"),
    ("explicit_ticker_required", "Explicit ticker missing for nearby article date"),
    ("needs_enrichment", "Article content needed to identify ticker"),
    ("ticker_identity_missing", "Ticker identity not established"),
])
def test_review_queue_preserves_known_reconciliation_reasons(reason, label):
    result = _run_ui(
        f"""
        const event = {_EVENT};
        event.reason_code = {json.dumps(reason)};
        event.candidates[0].reason_code = {json.dumps(reason)};
        const container = document.createElement("section");
        ArkScopeReconciliationUI.renderQueue(container, {{ events: [event], total: 1 }}, {{}});
        return {{
          eventReason: container.querySelector(".reconciliation-event-reason").textContent,
          candidateReason: container.querySelector(".reconciliation-candidate-reason").textContent,
        }};
        """
    )
    assert result == {"eventReason": label, "candidateReason": label}


def test_review_queue_does_not_hide_unrecognized_evidence_or_interpret_it_as_html():
    result = _run_ui(
        f"""
        const event = {_EVENT};
        event.candidates[0].evidence_codes = ['future_<img src=x onerror="alert(1)">'];
        const container = document.createElement("section");
        ArkScopeReconciliationUI.renderQueue(container, {{ events: [event], total: 1 }}, {{}});
        return {{ text: container.textContent, imageCount: container.querySelectorAll("img").length }};
        """
    )
    assert 'Unrecognized evidence: future_<img src=x onerror="alert(1)">' in result["text"]
    assert result["imageCount"] == 0


def test_article_link_review_is_optional_collapsed_and_keeps_existing_controls():
    result = _run_ui(
        f"""
        const popup = new DOMParser().parseFromString(
          {json.dumps(POPUP_HTML.read_text(encoding="utf-8"))}, "text/html"
        );
        const review = popup.getElementById("reconciliationSection");
        const controls = [
          "reconciliationError", "reconciliationQueue", "manualConfirmation",
          "manualAdvanced", "manualInput", "manualBtn"
        ];
        return {{
          tag: review.tagName,
          open: review.open,
          summary: review.querySelector(":scope > summary")?.textContent || "",
          controls: controls.filter((id) => review.contains(popup.getElementById(id))),
          nestedManualOpen: popup.getElementById("manualAdvanced").open,
          inputLabel: popup.querySelector('label[for="manualInput"]').textContent,
          button: popup.getElementById("manualBtn").textContent,
        }};
        """
    )
    assert result["tag"] == "DETAILS"
    assert result["open"] is False
    assert "Article link review" in result["summary"]
    assert "advanced" in result["summary"].lower()
    assert "optional" in result["summary"].lower()
    assert result["controls"] == [
        "reconciliationError", "reconciliationQueue", "manualConfirmation",
        "manualAdvanced", "manualInput", "manualBtn",
    ]
    assert result["nestedManualOpen"] is False
    assert result["inputLabel"] == "One per line: TICKER ROLE DATE ARTICLE_URL"
    assert result["button"] == "Fetch and review"


def test_use_candidate_action_sends_exact_stable_event_key_without_displaying_ids():
    result = _run_ui(
        f"""
        const calls = [];
        const container = document.createElement("section");
        ArkScopeReconciliationUI.renderQueue(
          container,
          {{ events: [{_EVENT}], total: 1 }},
          {{ onUseCandidate: async (payload) => {{ calls.push(payload); return {{ status: "ok" }}; }} }}
        );
        container.querySelector('[data-action="use-candidate"]').click();
        await new Promise((resolve) => setTimeout(resolve, 0));
        return {{ calls, text: container.textContent }};
        """
    )
    assert result["calls"] == [{
        "lineage_id": 777,
        "role": "entry",
        "event_anchor_date": "2026-07-15",
        "article_id": "6316639",
        "article_url": (
            "https://seekingalpha.com/alpha-picks/articles/6316639-stock-buy"
        ),
        "replace_link_id": 999,
        "confirm_warnings": False,
    }]
    assert "777" not in result["text"]
    assert "999" not in result["text"]


def test_reject_action_removes_only_the_exact_event_candidate():
    result = _run_ui(
        f"""
        const calls = [];
        const container = document.createElement("section");
        ArkScopeReconciliationUI.renderQueue(
          container,
          {{ events: [{_EVENT}], total: 1 }},
          {{ onRejectCandidate: async (payload) => {{ calls.push(payload); return {{ status: "ok" }}; }} }}
        );
        container.querySelector('[data-action="reject-candidate"]').click();
        await new Promise((resolve) => setTimeout(resolve, 0));
        return calls;
        """
    )
    assert result == [{
        "lineage_id": 777,
        "role": "entry",
        "event_anchor_date": "2026-07-15",
        "article_id": "6316639",
        "reason_code": "user_rejected",
    }]


def test_mismatch_or_replacement_uses_inline_second_confirmation_not_window_confirm():
    result = _run_ui(
        f"""
        let nativeConfirmCalls = 0;
        window.confirm = () => {{ nativeConfirmCalls += 1; return true; }};
        const calls = [];
        const event = {_EVENT};
        event.candidates[0].requires_confirmation = true;
        const container = document.createElement("section");
        ArkScopeReconciliationUI.renderQueue(
          container,
          {{ events: [event], total: 1 }},
          {{
            onUseCandidate: async (payload) => {{
              calls.push(payload);
              return payload.confirm_warnings
                ? {{ status: "ok" }}
                : {{
                    status: "confirmation_required",
                    warnings: ["date_mismatch", "replacement"],
                    candidate: {{ article_id: "6316639", published_date: "2026-07-12" }},
                  }};
            }},
          }}
        );
        container.querySelector('[data-action="use-candidate"]').click();
        await new Promise((resolve) => setTimeout(resolve, 0));
        const warningText = container.querySelector('[data-confirmation]').textContent;
        container.querySelector('[data-action="confirm-candidate"]').click();
        await new Promise((resolve) => setTimeout(resolve, 0));
        return {{ calls, warningText, nativeConfirmCalls }};
        """
    )
    assert result["nativeConfirmCalls"] == 0
    assert "Article date differs from event" in result["warningText"]
    assert "Replaces current link" in result["warningText"]
    assert "Use anyway" in result["warningText"]
    assert [call["confirm_warnings"] for call in result["calls"]] == [False, True]


def test_unrecognized_confirmation_warning_does_not_present_confirmation_as_optional():
    result = _run_ui(
        f"""
        const container = document.createElement("section");
        ArkScopeReconciliationUI.renderQueue(
          container, {{ events: [{_EVENT}], total: 1 }},
          {{ onUseCandidate: async () => ({{
            status: "confirmation_required", warnings: ["future_warning"]
          }}) }}
        );
        container.querySelector('[data-action="use-candidate"]').click();
        await new Promise((resolve) => setTimeout(resolve, 0));
        return container.querySelector('[data-confirmation]').textContent;
        """
    )
    assert "optional" not in result.lower()
    assert "This link requires another confirmation" in result
    assert "Use anyway" in result
    assert "Cancel" in result


def test_advanced_manual_section_is_collapsed_by_default():
    html = POPUP_HTML.read_text(encoding="utf-8")
    assert '<details id="manualAdvanced">' in html
    assert '<summary>Advanced: specify article URLs</summary>' in html
    assert "<details id=\"manualAdvanced\" open" not in html
    assert html.index('src="reconciliation_ui.js"') < html.index('src="popup.js"')


def test_manual_parser_requires_symbol_role_iso_date_and_canonical_sa_url():
    result = _run_ui(
        r"""
        const ui = ArkScopeReconciliationUI;
        const good = ui.parseAdvancedLines(
          "BTSG entry 2026-07-15 https://seekingalpha.com/alpha-picks/articles/6316639-stock-buy"
        );
        const bad = [
          "BTSG https://seekingalpha.com/alpha-picks/articles/6316639-x",
          "BTSG update 2026-07-15 https://seekingalpha.com/alpha-picks/articles/6316639-x",
          "BTSG entry Today https://seekingalpha.com/alpha-picks/articles/6316639-x",
          "BTSG entry 2026-07-15 https://example.com/alpha-picks/articles/6316639-x",
        ].map((line) => ui.parseAdvancedLines(line));
        return { good, bad };
        """
    )
    assert result["good"]["errors"] == []
    assert result["good"]["items"] == [{
        "symbol": "BTSG",
        "role": "entry",
        "event_anchor_date": "2026-07-15",
        "url": (
            "https://seekingalpha.com/alpha-picks/articles/6316639-stock-buy"
        ),
    }]
    assert all(parsed["items"] == [] for parsed in result["bad"])


def test_unresolved_queue_does_not_prefill_legacy_ticker_url_lines():
    html = POPUP_HTML.read_text(encoding="utf-8")
    source = POPUP_JS.read_text(encoding="utf-8")
    assert "Paste missing article URLs" not in html
    assert "Missing:" not in source
    assert "unresolved.map" not in source
    assert 'action: "get_reconciliation_queue"' in source


@pytest.mark.parametrize("review_count", [0, 3])
def test_completed_quick_update_marks_unlinked_roles_as_optional(review_count):
    fixture = {"storage": {"lastRefresh": {
        "batch_ts": "2026-09-25T00:00:00Z",
        "mode": "quick",
        "current": {"status": "ok", "count": 20},
        "closed": {"status": "ok", "count": 10},
        "details": {"articles_saved": 2, "review_required": review_count},
    }}}
    completed = subprocess.run(
        ["node", str(ROOT / "tests/js/run_sa_extension_popup_fixture.mjs"),
         str(EXTENSION), "snapshot", json.dumps(fixture)],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    result = json.loads(completed.stdout)
    assert "(quick)" in result["bodyText"]
    assert "2 recent articles scanned" in result["bodyText"]
    if review_count:
        assert "Article links: 3 unlinked event roles; review optional" in result["bodyText"]
        assert "3 events to review" not in result["bodyText"]
    else:
        assert "Article links:" not in result["bodyText"]


def test_reconciliation_surface_copy_remains_english():
    production_copy = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (POPUP_HTML, UI, POPUP_JS, POPUP_ACTION_CATALOG)
    )
    assert re.search(r"[\u3400-\u9fff]", production_copy) is None
