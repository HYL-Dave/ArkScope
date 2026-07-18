from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "extensions" / "sa_alpha_picks"
UI = EXTENSION / "reconciliation_ui.js"
POPUP_HTML = EXTENSION / "popup.html"
POPUP_JS = EXTENSION / "popup.js"


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
    evidence_codes: ["list_ticker", "date_within_window"],
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
        "建倉",
        "2026-07-15",
        "Stock Buy: Top Health Care Services Stock Delivers Double-Digit Growth",
        "清單標的",
        "日期接近",
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
        event.candidates[0].evidence_codes = ["list_ticker", "detail_ticker"];
        const container = document.createElement("section");
        ArkScopeReconciliationUI.renderQueue(container, {{ events: [event], total: 1 }}, {{}});
        return container.textContent;
        """
    )
    assert "清單與文章標的衝突" in result
    assert "僅標題" in result
    assert "清單標的" in result
    assert "文章標的" in result


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
    assert "文章日期與事件不一致" in result["warningText"]
    assert "取代目前連結" in result["warningText"]
    assert "仍要使用" in result["warningText"]
    assert [call["confirm_warnings"] for call in result["calls"]] == [False, True]


def test_advanced_manual_section_is_collapsed_by_default():
    html = POPUP_HTML.read_text(encoding="utf-8")
    assert '<details id="manualAdvanced">' in html
    assert '<summary>進階：指定文章網址</summary>' in html
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
    assert "待檢視" in source
