"""Actual four-channel Web UI; synthetic HTTP fixtures, no App or provider."""

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from urllib.parse import urlparse

from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright, expect

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PREVIOUS = HERE.parents[1] / "2026-09-06-lifecycle-current-review/scripts/run_browser.py"
spec = importlib.util.spec_from_file_location("current_fixture", PREVIOUS)
current = importlib.util.module_from_spec(spec)
spec.loader.exec_module(current)
CONTRACT = current.CONTRACT


def source_hashes():
    return {**current.source_hashes(), str(Path(__file__).relative_to(ROOT)): hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def geometry(page, selector):
    # Scroll-clipped descendants do not overlap a fixed drawer header on screen.
    # Compare rendered intersections; retain horizontal clipping/overflow checks.
    return page.locator(selector).evaluate("""root => {
      const rendered = node => {
        if (!node.getClientRects().length || getComputedStyle(node).visibility === 'hidden') return null;
        const raw = node.getBoundingClientRect();
        const r = {left:raw.left,right:raw.right,top:Math.max(0,raw.top),bottom:Math.min(innerHeight,raw.bottom)};
        for (let parent=node.parentElement; parent; parent=parent.parentElement) {
          const style=getComputedStyle(parent), p=parent.getBoundingClientRect();
          if (/(auto|scroll|hidden|clip)/.test(style.overflowY)) { r.top=Math.max(r.top,p.top); r.bottom=Math.min(r.bottom,p.bottom); }
          if (/(auto|scroll|hidden|clip)/.test(style.overflowX)) { r.left=Math.max(r.left,p.left); r.right=Math.min(r.right,p.right); }
        }
        return r.bottom-r.top>1 && r.right-r.left>1 ? {...r, raw, text:node.textContent || node.getAttribute('aria-label')} : null;
      };
      const controls=[...root.querySelectorAll('button,input,select')].map(rendered).filter(Boolean);
      const overlaps=controls.flatMap((a,i)=>controls.slice(i+1).filter(b=>Math.min(a.right,b.right)-Math.max(a.left,b.left)>1 && Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1).map(b=>[a.text,b.text]));
      const clipped=controls.filter(a=>a.raw.left < -1 || a.raw.right > innerWidth+1).map(a=>a.text);
      const overflow=[...root.querySelectorAll('p,button,strong')].filter(node=>rendered(node) && node.scrollWidth>node.clientWidth+2 && getComputedStyle(node).display!=='inline').map(node=>node.textContent);
      return {overlaps,clipped,overflow,bodyOverflow:document.documentElement.scrollWidth>innerWidth+1};
    }""")


def install_web_routes(page, url, scenario, provider, auth):
    state = current.install_routes(page, url, "success")
    base = CONTRACT["attention"]["items"][0]
    case, ticker = base["next_action"]["case_id"], base["ticker"]
    selection = {"provider": provider, "auth_mode": auth, "model": "gpt-5.6-luna" if provider == "openai" else "claude-sonnet-5"}
    preflight = {
        "version": 1, "case_id": case, "available": True, "reason": None, "preflight_sha256": "a" * 64,
        "public_identity": {"ticker": ticker, "issuer_name": "Issuer Old Inc", "security_class": None, "venue": None,
                            "question": "listing_status", "as_of": "2026-09-06"},
        "execution": selection, "credential_label": "Selected fixture account",
        "limits": {"model_submissions": 2, "search_uses": 4, "search_enforcement": "observed" if auth == "chatgpt_oauth" else "enforced",
                   "source_requests": 8, "sources": 4, "model_timeout_seconds": 180, "source_timeout_seconds": 45,
                   "output_token_limit": 4096 if auth == "api_key" else None, "background_retention": provider == "openai" and auth == "api_key"},
    }
    finding = {
        "source_ticker": ticker, "issuer_name": "Issuer Old Inc", "security_class": "Class A common stock", "venue": "NASDAQ",
        "event_kind": "listing_ended", "timing": "completed", "summary": "Trading has ended according to the cited issuer notice.",
        "successor_ticker": None, "effective_date": "2026-09-01", "announcement_date": None,
        "contradictions": [], "unresolved_conditions": [], "action": "terminal_delisting", "block_reasons": [],
        "unique_passage_count": 1, "independent_source_count": None,
        "citations": [{"url": "https://issuer.example/notices", "quote": "Issuer Old Inc OLD Class A common stock on NASDAQ ceased trading effective September 1, 2026.",
                       "retrieved_at": "2026-09-06T01:01:00Z"}],
    }
    packet = deepcopy(CONTRACT["packet"])
    packet.update(case_id=case, source_ticker=ticker, execute_on=finding["effective_date"])
    packet["options"]["execute_on"] = finding["effective_date"]
    packet["finding"]["effective_date"] = finding["effective_date"]
    if scenario == "rename":
        finding.update(event_kind="symbol_continuation", action="symbol_continuation", successor_ticker="NEW",
                       summary="The same ordinary share continues under the NEW symbol.")
        finding["citations"][0]["quote"] = "Issuer Old Inc OLD Class A common stock on NASDAQ continues as NEW for the same security effective September 1, 2026."
        packet.update(action="symbol_continuation")
        packet["finding"].update(successor_ticker="NEW", outcomes=["symbol_changed"])
        packet["effects"]["watchlists"]["add"] = [{"list_name": "Long-term tracking list", "ticker": "NEW"}]
    if scenario == "blocked":
        finding.update(action=None, block_reasons=["material_contradiction"], contradictions=["The exchange still reports active OTC trading."])
    run = {"version": 1, "run_id": "run-1", "case_id": case, "ticker": ticker, "status": "succeeded", "phase": None,
           "created_at": "2026-09-06T01:00:00Z", "finished_at": "2026-09-06T01:02:00Z", "failure_code": None, "cancel_requested_at": None,
           "execution": selection, "model_submissions": 2, "source_requests": 1, "usage": {"input_tokens": 20, "output_tokens": 100}, "finding": finding}
    state.update(web_posts=[], web_reads=[], run=None if scenario == "start" else run, unknown=False)
    if scenario == "cancel":
        state["run"] = {**run, "status": "searching", "phase": "searching", "finished_at": None, "finding": None, "model_submissions": 1}
    if scenario == "unavailable":
        state["run"] = None
        preflight.update(available=False, reason="model_auth_unverified", preflight_sha256=None, public_identity=None,
                         execution=None, credential_label=None, limits=None)

    def handle(route):
        path = urlparse(route.request.url).path
        if "/web-" not in path:
            route.fallback()
            return
        code = 200
        if route.request.method == "POST":
            state["web_posts"].append(path)
            if path == f"/security-lifecycle/cases/{case}/web-runs":
                assert route.request.post_data_json["preflight_sha256"] == preflight["preflight_sha256"]
                state["run"] = run
                value = {"run_id": run["run_id"], "created": True}
            elif path == "/security-lifecycle/web-runs/run-1/cancel":
                state["run"] = {**state["run"], "status": "cancelling", "cancel_requested_at": "2026-09-06T01:03:00Z"}
                value = state["run"]
            elif path == "/security-lifecycle/web-runs/run-1/confirm":
                assert route.request.post_data_json["action"] == packet["action"]
                assert route.request.post_data_json["packet_sha256"] == packet["packet_sha256"]
                state["applied"] = True
                value = {**CONTRACT["confirmation"], "action": packet["action"], "execute_on": packet["execute_on"],
                         "successor_ticker": packet["finding"]["successor_ticker"]}
                if scenario == "changed":
                    state["applied"] = False
                    code, value = 409, {"detail": {"code": "review_changed"}}
            else:
                raise AssertionError("unexpected_web_write")
        else:
            state["web_reads"].append(path)
            if path.endswith("/web-preflight"):
                value = preflight
            elif path.endswith("/web-runs/latest") or path == "/security-lifecycle/web-runs/run-1":
                if state["unknown"]:
                    state["run"] = {**state["run"], "status": "remote_outcome_unknown", "phase": None,
                                    "failure_code": "stop_requested", "finished_at": "2026-09-06T01:04:00Z"}
                value = state["run"]
            elif path.endswith("/review"):
                value = packet
            else:
                raise AssertionError("unexpected_web_read")
        route.fulfill(status=code, content_type="application/json", body=json.dumps(value), headers={"Access-Control-Allow-Origin": "*"})

    page.route("**/security-lifecycle/**", handle)
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sources = source_hashes()
    metadata = {"source_sha256": sources, "provider_calls": 0, "production_app_started": False}
    results = []
    server = subprocess.Popen(["node", str(PREVIOUS.parent / "serve_preview.mjs")], cwd=ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        line = server.stdout.readline()
        if not line:
            raise RuntimeError(server.stderr.read())
        url = json.loads(line)["url"]
        scenarios = [("start", "openai", "api_key"), ("start", "openai", "chatgpt_oauth"),
                     ("start", "anthropic", "api_key"), ("start", "anthropic", "claude_code_oauth"),
                     ("rename", "openai", "chatgpt_oauth"), ("blocked", "anthropic", "claude_code_oauth"),
                     ("cancel", "openai", "chatgpt_oauth"), ("changed", "openai", "api_key"),
                     ("unavailable", "anthropic", "claude_code_oauth")]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            control = browser.new_page()
            control.set_content('<div id="probe"><button style="position:absolute;top:0;left:0">Visible</button><div style="position:absolute;top:100px;height:100px;width:200px;overflow:hidden"><button style="position:relative;top:-100px">Clipped</button></div></div>')
            assert not geometry(control, "#probe")["overlaps"]
            control.locator("#probe").evaluate("node=>node.insertAdjacentHTML('beforeend','<button style=\"position:absolute;top:0;left:0\">Overlap</button>')")
            assert geometry(control, "#probe")["overlaps"]
            control.close()
            for locale in ("en", "zh-Hant"):
                en = locale == "en"
                for width, height in ((1440, 900), (390, 844), (320, 740)):
                    for scenario, provider, auth in scenarios:
                        context = browser.new_context(viewport={"width": width, "height": height}, service_workers="block")
                        page = context.new_page()
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        state = install_web_routes(page, url, scenario, provider, auth)
                        page.goto(url + "?locale=" + locale)
                        page.get_by_role("button", name="Review OLD" if en else "檢視 OLD", exact=True).click()
                        web = page.locator(".lifecycle-web")
                        launch = "Investigate on the web" if en else "進行網路調查"
                        expect(web).to_be_visible()
                        expect(web.get_by_role("button", name="Reload investigation" if en else "重新讀取調查", exact=True)).to_be_enabled()
                        assert state["web_posts"] == [] and state["posts"] == []
                        name = f"{locale}-{width}-{scenario}-{provider}-{auth}"
                        metrics, pixels = {}, {}

                        def capture(phase, selector=".ui-drawer"):
                            metrics[phase] = geometry(page, selector)
                            path = output / f"{name}-{phase}.png"
                            page.screenshot(path=str(path))
                            with Image.open(path) as picture:
                                pixels[phase] = max(ImageStat.Stat(picture).var)
                            assert pixels[phase] > 5 and not any(metrics[phase].values()), metrics[phase]

                        web.scroll_into_view_if_needed()
                        capture("detail")
                        if scenario == "unavailable":
                            expect(web.get_by_role("button", name=launch, exact=True)).to_be_disabled()
                        elif scenario == "cancel":
                            web.get_by_role("button", name="Stop investigation" if en else "停止調查", exact=True).click()
                            expect(web).to_contain_text("Stopping" if en else "停止中")
                            state["unknown"] = True
                            web.get_by_role("button", name="Reload investigation" if en else "重新讀取調查", exact=True).click()
                            expect(web).to_contain_text("Remote outcome unknown" if en else "遠端結果未知")
                            capture("unknown")
                            assert len(state["web_posts"]) == 1
                        elif scenario == "blocked":
                            expect(web).to_contain_text("exchange still reports active OTC")
                            expect(web.get_by_role("button", name="Review removal" if en else "確認移除範圍", exact=True)).to_have_count(0)
                        else:
                            if scenario == "start":
                                web.get_by_role("button", name=launch, exact=True).click()
                                dialog = page.locator(".ui-confirm-dialog")
                                expect(dialog).to_contain_text("Selected fixture account")
                                assert state["web_posts"] == []
                                capture("launch-confirm", ".ui-confirm-dialog")
                                dialog.get_by_role("button", name=launch, exact=True).click()
                                expect(dialog).not_to_be_visible()
                            expect(web.locator("blockquote")).to_contain_text("Issuer Old Inc")
                            label = ("Review symbol change" if en else "確認改名範圍") if scenario == "rename" else ("Review removal" if en else "確認移除範圍")
                            web.get_by_role("button", name=label, exact=True).click()
                            confirm = web.get_by_role("button", name="Confirm and apply" if en else "確認並套用", exact=True)
                            expect(confirm).to_be_enabled()
                            confirm.scroll_into_view_if_needed()
                            capture("effects")
                            confirm.click()
                            dialog = page.locator(".ui-confirm-dialog")
                            capture("action-confirm", ".ui-confirm-dialog")
                            dialog.get_by_role("button", name="Confirm and apply" if en else "確認並套用", exact=True).click()
                            expect(dialog).not_to_be_visible()
                            if scenario == "changed":
                                expect(web.get_by_role("alert")).to_be_visible()
                                assert state["applied"] is False
                            else:
                                expect(page.locator('[data-action-state="applied"]')).to_be_visible()
                            assert len(state["web_posts"]) == (2 if scenario == "start" else 1)
                        before = list(state["web_posts"])
                        page.reload()
                        page.get_by_role("button", name="Review OLD" if en else "檢視 OLD", exact=True).click()
                        expect(page.locator(".lifecycle-web")).to_be_visible()
                        assert state["web_posts"] == before and state["posts"] == []
                        assert not errors and not state["unexpected"], (errors, state["unexpected"])
                        results.append({"name": name, "geometry": metrics, "pixel_variance": pixels,
                                        "mocked_posts": len(before), "page_errors": errors, "unexpected_requests": state["unexpected"]})
                        (output / "results.json").write_text(json.dumps({**metadata, "complete": False, "scenarios": results}, indent=2) + "\n")
                        print(json.dumps({"passed": name}), flush=True)
                        context.close()
            browser.close()
        assert source_hashes() == sources
        (output / "results.json").write_text(json.dumps({**metadata, "complete": True, "scenarios": results}, indent=2) + "\n")
    finally:
        server.terminate()
        try:
            server.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.communicate()


if __name__ == "__main__":
    main()
