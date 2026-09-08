"""Real UI and runtime parsers, intercepted synthetic API only. No App/provider."""

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright, expect

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CONTRACT = json.loads((ROOT / "tests/fixtures/lifecycle_current_v1.json").read_text())
previous = HERE.parents[1] / "2026-09-06-price-window-and-repair-ui/scripts/run_browser.py"
spec = importlib.util.spec_from_file_location("geometry_owner", previous)
geometry_owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry_owner)


def source_hashes():
    files = set((ROOT / "apps/arkscope-web/src").rglob("*"))
    files.update((ROOT / "apps/arkscope-web").glob("*.json"))
    files.update((ROOT / "apps/arkscope-web").glob("*.config.*"))
    files.update({ROOT / "package.json", ROOT / "package-lock.json",
                  ROOT / "tests/fixtures/lifecycle_current_v1.json", previous,
                  Path(__file__), HERE / "preview.tsx", HERE / "serve_preview.mjs"})
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(files) if path.is_file()}


def install_routes(page, url, scenario):
    state = {"posts": [], "unexpected": [], "audit_reads": 0, "packet_reads": 0, "applied": False}
    base = deepcopy(CONTRACT["attention"]["items"][0])
    base["issuer_name"] = "Synthetic ordinary-share issuer"
    base["source_notices"] = [{"form": "8-K", "filed_on": "2026-09-04", "text": "Synthetic official source. This retained filing is context, not an automatic instruction.",
                               "url": "https://www.sec.gov/Archives/fixture/notice.htm"}]
    if scenario == "scheduled":
        base["next_action"] = {**CONTRACT["applied"]["items"][0]["next_action"], "state": "scheduled", "kind": "none",
                               "execute_on": "2026-09-10", "current_effects_match": None, "can_reverse": False}
        base["reason"] = "action_scheduled"
    if scenario == "changed":
        base["next_action"] = {**CONTRACT["applied"]["items"][0]["next_action"], "state": "applied_state_changed",
                               "current_effects_match": False, "can_reverse": False, "block_reasons": ["reverse_state_changed"]}
        base["reason"] = "applied_state_changed"
    if scenario == "history":
        base.update(bucket="history", finding="active", reason="active_confirmed",
                    listing={"state": "active", "basis": "observation", "ended_on": None})
        base["next_action"]["kind"] = "none"
    def item():
        return {**CONTRACT["applied"]["items"][0], "issuer_name": base["issuer_name"], "source_notices": base["source_notices"]} if state["applied"] else base
    def handle(route):
        parsed = urlparse(route.request.url)
        path = parsed.path
        if parsed.netloc == urlparse(url).netloc and not path.startswith("/security-lifecycle/"):
            route.continue_()
            return
        if parsed.hostname not in {"127.0.0.1", "localhost"}:
            state["unexpected"].append(path)
            route.abort()
            return
        code = 200
        case = base["next_action"]["case_id"]
        if route.request.method == "POST":
            state["posts"].append(path)
            if path == f"/security-lifecycle/cases/{case}/confirm-review" and scenario in {"success", "response_lost"}:
                body = route.request.post_data_json
                assert body == {"assessment_id": CONTRACT["packet"]["assessment_id"], "packet_sha256": CONTRACT["packet"]["packet_sha256"],
                                "action": "terminal_delisting", **CONTRACT["packet"]["options"]}
                state["applied"] = True
                value = CONTRACT["confirmation"]
                if scenario == "response_lost":
                    value, code = {"detail": {"code": "review_unavailable"}}, 503
            else:
                state["unexpected"].append(path)
                value, code = {"detail": {"code": "unexpected_fixture_write"}}, 409
        elif path == "/security-lifecycle/reviews":
            selected = parse_qs(parsed.query).get("view", ["attention"])[0]
            rows = [item()] if selected == item()["bucket"] else []
            value = {**CONTRACT["attention"], "items": rows, "counts": {"attention": int(item()["bucket"] == "attention"), "history": int(item()["bucket"] == "history")},
                     "page": {"offset": 0, "limit": 50, "total": len(rows)}}
            if scenario == "malformed":
                value["items"] = None
        elif path == "/security-lifecycle/reviews/" + base["review_id"]:
            value = {"version": 1, "as_of": CONTRACT["attention"]["as_of"], "item": item()}
        elif path == f"/security-lifecycle/cases/{case}/review":
            state["packet_reads"] += 1
            value = CONTRACT["packet"]
        elif path == f"/security-lifecycle/cases/{case}/audit":
            state["audit_reads"] += 1
            names = ["evidence", "assessment_history", "automation_runs", "automation_facts", "investigation_runs", "acknowledgement_history"]
            value = {"case_id": case, "observation_fingerprint_sha256": None, **{key: [] for key in names},
                     "truncation": {key: {"total": 0, "returned": 0} for key in names}}
        elif path == "/security-lifecycle/automation":
            value = {"config_status": "valid", "config": {"enabled": False, "interval_minutes": 5, "batch_limit": 2, "apply_profile_transitions": False},
                     "schedule": {"status": "disabled", "last_attempt_at": None, "next_scheduled_at": None}, "telemetry_status": "absent",
                     "last_status": None, "last_result": None, "active_incident": None, "latest_failed_runs": [], "current_progress": []}
        elif path == "/security-lifecycle/transition-activity":
            value = {"items": [], "count": 0, "unacknowledged_count": 0}
        else:
            state["unexpected"].append(path)
            value, code = {"detail": {"code": "unexpected_fixture_read"}}, 404
        route.fulfill(status=code, content_type="application/json", body=json.dumps(value), headers={"Access-Control-Allow-Origin": "*"})
    page.route("**/*", handle)
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sources = source_hashes()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert CONTRACT == json.loads((ROOT / "tests/fixtures/lifecycle_current_v1.json").read_text())
    metadata = {"head": head, "source_sha256": sources, "provider_calls": 0, "production_app_started": False}
    server = subprocess.Popen(["node", str(HERE / "serve_preview.mjs")], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    results = []
    try:
        line = server.stdout.readline()
        if not line:
            raise RuntimeError(server.stderr.read())
        url = json.loads(line)["url"]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for locale in ("en", "zh-Hant"):
                for width, height in ((1440, 900), (390, 844), (320, 740)):
                    for scenario in ("success", "response_lost", "scheduled", "changed", "malformed", "history"):
                        context = browser.new_context(viewport={"width": width, "height": height}, service_workers="block")
                        page = context.new_page()
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        state = install_routes(page, url, scenario)
                        page.goto(url + "?locale=" + locale)
                        surface = page.locator(".lifecycle-current")
                        name = f"{locale}-{width}-{scenario}"
                        metrics = {}
                        pixel_variance = {}
                        def capture(phase, selector, full_page=False):
                            metrics[phase] = geometry_owner.geometry(page, selector)
                            path = output / f"{name}-{phase}.png"
                            page.screenshot(path=str(path), full_page=full_page)
                            with Image.open(path) as picture:
                                pixel_variance[phase] = max(ImageStat.Stat(picture).var)
                            assert pixel_variance[phase] > 5
                            assert not any(metrics[phase].values()), metrics[phase]
                        if scenario == "history":
                            surface.get_by_role("button", name="History" if locale == "en" else "歷史", exact=True).click()
                        if scenario == "malformed":
                            expect(surface.get_by_role("alert")).to_be_visible()
                            expect(surface.get_by_text("No reviews in this view." if locale == "en" else "此檢視沒有待列出的調查。", exact=True)).to_have_count(0)
                        else:
                            expect(surface.get_by_role("button", name="Review OLD" if locale == "en" else "檢視 OLD", exact=True)).to_be_visible()
                        assert state["posts"] == [] and state["audit_reads"] == 0 and state["packet_reads"] == 0
                        assert surface.locator('input[type="search"]').evaluate("node => getComputedStyle(node).backgroundColor") != "rgb(255, 255, 255)"
                        capture("list", ".lifecycle-current", True)
                        if scenario != "malformed":
                            surface.get_by_role("button", name="Review OLD" if locale == "en" else "檢視 OLD", exact=True).click()
                            drawer = page.locator(".ui-drawer")
                            expect(drawer).to_contain_text("Synthetic ordinary-share issuer")
                            capture("detail", ".ui-drawer")
                            if scenario in {"success", "response_lost"}:
                                drawer.get_by_role("button", name="Review removal" if locale == "en" else "確認移除範圍", exact=True).click()
                                confirm = drawer.get_by_role("button", name="Confirm and apply" if locale == "en" else "確認並套用", exact=True)
                                expect(confirm).to_be_enabled()
                                confirm.scroll_into_view_if_needed()
                                capture("preview", ".ui-drawer")
                                assert state["posts"] == [] and state["packet_reads"] == 1
                                confirm.click()
                                dialog = page.locator(".ui-confirm-dialog")
                                expect(dialog).to_be_visible()
                                capture("confirm", ".ui-confirm-dialog")
                                dialog.get_by_role("button", name="Confirm and apply" if locale == "en" else "確認並套用", exact=True).click()
                                expect(dialog).not_to_be_visible()
                                if scenario == "response_lost":
                                    expect(drawer.get_by_role("alert")).to_be_visible()
                                    drawer.get_by_role("alert").get_by_role("button").click()
                                expect(drawer.locator('[data-action-state="applied"]')).to_be_visible()
                                expect(drawer).to_contain_text("Not collecting" if locale == "en" else "未收集")
                                assert len(state["posts"]) == 1
                            elif scenario == "scheduled":
                                expect(drawer.locator('[data-action-state="scheduled"]')).to_be_visible()
                                expect(drawer.locator('[data-action-state="applied"]')).to_have_count(0)
                            elif scenario == "changed":
                                expect(drawer.locator('[data-action-state="applied_state_changed"]')).to_be_visible()
                                expect(drawer.locator('[data-action-state="applied"]')).to_have_count(0)
                            audit = drawer.locator("details.lifecycle-audit")
                            assert state["audit_reads"] == 0
                            audit.locator(":scope > summary").click()
                            expect(audit.get_by_text("Synthetic official source.", exact=False)).to_be_visible()
                            expect(audit.locator('a[href="https://www.sec.gov/Archives/fixture/notice.htm"]')).to_be_visible()
                            assert state["audit_reads"] == 1
                            capture("audit", ".ui-drawer")
                        assert not state["unexpected"], state["unexpected"]
                        assert not errors, errors
                        results.append({"name": name, "geometry": metrics, "mocked_posts": len(state["posts"]), "audit_reads": state["audit_reads"],
                                        "pixel_variance": pixel_variance, "unexpected_requests": state["unexpected"], "page_errors": errors})
                        (output / "results.json").write_text(json.dumps({**metadata, "complete": False, "scenarios": results}, indent=2) + "\n")
                        print(json.dumps({"passed": name}), flush=True)
                        context.close()
            browser.close()
        assert source_hashes() == sources
        assert head == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
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
