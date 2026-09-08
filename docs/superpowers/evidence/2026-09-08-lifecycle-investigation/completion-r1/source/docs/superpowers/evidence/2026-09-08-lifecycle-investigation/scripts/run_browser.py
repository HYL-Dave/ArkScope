"""Real UI -> runtime-validated DTO -> real temp routes/writer. Zero provider IO."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urlparse

from fastapi.testclient import TestClient
from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright, expect

from fixture_api import fixture_app

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def geometry(page):
    return page.evaluate("""() => {
      const elements = [...document.querySelectorAll('button,input,select,summary')].filter(e => e.getClientRects().length && e.getBoundingClientRect().width > 0);
      const dialog = document.querySelector('[role=dialog]');
      const active = elements.filter(e => !dialog || dialog.contains(e));
      const rects = active.map(e => e.getBoundingClientRect());
      return {
        bodyOverflow: document.documentElement.scrollWidth > innerWidth + 1,
        clipped: active.filter(e => { const r=e.getBoundingClientRect(); return r.left < -1 || r.right > innerWidth+1; }).length,
        overlap: rects.some((a,i)=>rects.slice(i+1).some(b => Math.min(a.right,b.right)-Math.max(a.left,b.left)>1 && Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)),
        textOverflow: [...document.querySelectorAll('button,h2,h3,p')].filter(e => e.getClientRects().length && e.scrollWidth > e.clientWidth+2).length,
      };
    }""")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    server = subprocess.Popen(["node", str(HERE / "serve_preview.mjs")], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    reports = []
    try:
        line = server.stdout.readline()
        if not line:
            raise RuntimeError(server.stderr.read())
        url = json.loads(line)["url"]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for locale in ("en", "zh-Hant"):
                for width, height in ((1440, 1000), (390, 844), (320, 740)):
                    with tempfile.TemporaryDirectory(prefix="lifecycle-browser-") as directory, fixture_app(Path(directory)) as (app, c, state), TestClient(app) as api:
                        context = browser.new_context(viewport={"width": width, "height": height}, service_workers="block")
                        page = context.new_page()
                        page.set_default_timeout(12000)
                        errors, requests, shots = [], [], []
                        page.on("pageerror", lambda error: errors.append(str(error)))

                        def handle(route):
                            parsed = urlparse(route.request.url)
                            if parsed.netloc != urlparse(url).netloc:
                                errors.append("unexpected_external_request:" + parsed.hostname)
                                route.abort()
                            elif parsed.path.startswith("/fixture-api/"):
                                path = parsed.path.removeprefix("/fixture-api") + ("?" + parsed.query if parsed.query else "")
                                response = api.request(route.request.method, path, json=route.request.post_data_json if route.request.post_data else None)
                                requests.append({"path": parsed.path, "method": route.request.method, "status": response.status_code})
                                if response.status_code >= 400:
                                    errors.append(path + ":" + response.text)
                                route.fulfill(status=response.status_code, content_type="application/json", body=response.text)
                            else:
                                route.continue_()

                        page.route("**/*", handle)

                        def shot(name):
                            metrics = geometry(page)
                            assert not any(metrics.values()), (name, metrics)
                            path = args.output / f"{locale}-{width}-{name}.png"
                            page.screenshot(path=str(path), full_page=True)
                            with Image.open(path) as image:
                                assert max(ImageStat.Stat(image).var) > 5
                            shots.append({"name": name, "file": path.name, "geometry": metrics})

                        def label(en, zh):
                            return en if locale == "en" else zh

                        def start():
                            page.get_by_role("button", name=label("Investigate again", "重新調查"), exact=True).click()
                            expect(page.get_by_role("dialog")).to_be_visible()
                            page.get_by_role("dialog").get_by_role("button", name=label("Investigate", "調查"), exact=True).click()

                        page.goto(url + "?locale=" + locale)
                        expect(page.locator(".investigation-result")).to_be_visible()
                        assert state["submissions"] == [] and state["writes"] == []
                        shot("completed")
                        page.locator(".investigation-evidence > summary").click()
                        expect(page.locator(".investigation-evidence blockquote")).to_have_count(2)
                        shot("citations")
                        page.get_by_role("button", name=label("Investigation settings", "調查設定"), exact=True).click()
                        page.locator(".investigation-runtime > summary").click()
                        inputs = page.locator('input[type="number"]')
                        expect(inputs).to_have_count(9)
                        expect(inputs.nth(7)).to_be_disabled()
                        inputs.nth(0).fill("40")
                        page.get_by_role("button", name=label("Save", "儲存"), exact=True).click()
                        expect(page.get_by_role("status")).to_have_text(label("Saved", "已儲存"))
                        assert api.get("/security-lifecycle/investigations/runtime").json()["model_submissions"] == 40
                        shot("settings")
                        page.get_by_role("button", name=label("Investigation", "標的事件調查"), exact=True).click()
                        expect(page.locator(".investigation-result")).to_be_visible()

                        api.post("/fixture/scenario", json={"mode": "slow"})
                        start()
                        expect(page.get_by_role("button", name=label("Stop", "停止"), exact=True)).to_be_visible()
                        shot("running")
                        page.reload()
                        expect(page.get_by_role("button", name=label("Stop", "停止"), exact=True)).to_be_visible()
                        page.get_by_role("button", name=label("Stop", "停止"), exact=True).click()
                        expect(page.get_by_role("button", name=label("Investigate again", "重新調查"), exact=True)).to_be_visible()
                        assert len(state["submissions"]) == 1
                        shot("cancelled")

                        api.post("/fixture/scenario", json={"mode": "incomplete"})
                        start()
                        expect(page.locator(".investigation-result")).to_be_visible()
                        expect(page.locator(".investigation-result")).to_contain_text("OTC")
                        expect(page.locator(".investigation-result").get_by_role("button", name=label("Review removal", "確認移除範圍"), exact=True)).to_have_count(0)
                        shot("incomplete")

                        api.post("/fixture/scenario", json={"mode": "unknown_date"})
                        start()
                        review = page.locator(".investigation-result").get_by_role("button", name=label("Review removal", "確認移除範圍"), exact=True)
                        expect(review).to_be_visible()
                        review.click()
                        expect(page.locator(".investigation-review")).to_be_visible()
                        confirm = page.locator(".investigation-review").get_by_role("button", name=label("Confirm and apply", "確認並套用"), exact=True)
                        expect(confirm).to_be_disabled()
                        page.locator('input[type="date"]').fill("2026-09-07")
                        expect(confirm).to_be_disabled()
                        page.get_by_role("button", name=label("Update preview", "更新預覽"), exact=True).click()
                        expect(page.locator(".investigation-review input[type=checkbox]")).to_have_count(1)
                        expect(confirm).to_be_disabled()
                        page.locator(".investigation-review input[type=checkbox]").check()
                        expect(confirm).to_be_enabled()
                        shot("review-gaps")
                        confirm.click()
                        expect(page.get_by_role("dialog")).to_contain_text("exact trading-end date")
                        assert "OLD" in c["sources"]()
                        shot("confirm")
                        page.get_by_role("dialog").get_by_role("button", name=label("Confirm and apply", "確認並套用"), exact=True).click()
                        expect(page.get_by_text(label("Tracking change recorded", "追蹤變更已記錄"), exact=True)).to_be_visible()
                        assert "OLD" not in c["sources"]() and "LIVE" in c["sources"]()
                        page.reload()
                        expect(page.locator(".investigation-result")).to_be_visible()
                        expect(page.locator(".investigation-result").get_by_role("button", name=label("Review removal", "確認移除範圍"), exact=True)).to_have_count(0)
                        page.locator(".investigation-history > summary").click()
                        expect(page.locator(".lifecycle-activity-band")).to_be_visible()
                        shot("receipt")
                        page.locator(".lifecycle-activity-band").get_by_role("button", name=label("Reverse tracking change", "還原追蹤變更"), exact=True).click()
                        expect(page.get_by_role("dialog")).to_be_visible()
                        assert "OLD" not in c["sources"]()
                        shot("reverse-confirm")
                        page.get_by_role("dialog").get_by_role("button", name=label("Confirm and apply", "確認並套用"), exact=True).click()
                        expect(page.locator(".investigation-targets option[value=OLD]")).to_have_count(1)
                        assert "OLD" in c["sources"]() and "LIVE" in c["sources"]()
                        expect(page.locator(".lifecycle-activity-band").get_by_role("button", name=label("Reverse tracking change", "還原追蹤變更"), exact=True)).to_have_count(0)
                        shot("reverse-receipt")
                        api.post("/fixture/scenario", json={"mode": "provider_only"})
                        page.get_by_role("listbox", name=label("Select a ticker", "選擇標的")).select_option("CACHED")
                        expect(page.get_by_role("button", name=label("Investigate", "調查"), exact=True)).to_be_disabled()
                        provider_review = page.locator(".investigation-listings").get_by_role("button", name=label("Review removal", "確認移除範圍"), exact=True)
                        expect(provider_review).to_be_enabled()
                        shot("provider-decision")
                        provider_review.click()
                        expect(page.locator(".investigation-review")).to_be_visible()
                        assert "CACHED" in c["sources"]()
                        shot("provider-review")
                        page.locator(".investigation-review").get_by_role("button", name=label("Confirm and apply", "確認並套用"), exact=True).click()
                        assert "CACHED" in c["sources"]()
                        page.get_by_role("dialog").get_by_role("button", name=label("Confirm and apply", "確認並套用"), exact=True).click()
                        expect(page.get_by_text(label("Tracking change recorded", "追蹤變更已記錄"), exact=True)).to_be_visible()
                        assert "CACHED" not in c["sources"]() and "LIVE" in c["sources"]()
                        assert state["provider_checks"] == []
                        expect(provider_review).to_be_disabled()
                        shot("provider-receipt")
                        page.locator(".lifecycle-activity-band").get_by_role("button", name=label("Reverse tracking change", "還原追蹤變更"), exact=True).click()
                        expect(page.get_by_role("dialog")).to_be_visible()
                        assert "CACHED" not in c["sources"]()
                        shot("provider-reverse-confirm")
                        page.get_by_role("dialog").get_by_role("button", name=label("Confirm and apply", "確認並套用"), exact=True).click()
                        expect(page.locator(".investigation-targets option[value=CACHED]")).to_have_count(1)
                        assert {"OLD", "LIVE", "CACHED"} <= set(c["sources"]())
                        expect(page.locator(".lifecycle-activity-band").get_by_role("button", name=label("Reverse tracking change", "還原追蹤變更"), exact=True)).to_have_count(0)
                        shot("provider-reverse-receipt")
                        assert errors == [], errors
                        assert len(state["submissions"]) == 3
                        assert all(row == {"provider": "anthropic", "auth_mode": "claude_code_oauth", "model": "claude-sonnet-5"} for row in state["submissions"])
                        reports.append({"locale": locale, "width": width, "provider_calls": 0, "synthetic_model_submissions": len(state["submissions"]), "requests": requests, "screens": shots})
                        context.close()
            browser.close()
        (args.output / "report.json").write_text(json.dumps(reports, indent=2) + "\n")
        print(json.dumps({"scenarios": len(reports), "screenshots": sum(len(row["screens"]) for row in reports), "provider_calls": 0}))
    except BaseException:
        if "page" in locals() and not page.is_closed():
            try:
                page.screenshot(path=str(args.output / "failure.png"), full_page=True)
                (args.output / "failure.json").write_text(json.dumps({"text": page.locator("body").inner_text(), "requests": requests, "errors": errors, "state": state}, indent=2) + "\n")
            except Exception:
                pass
        raise
    finally:
        server.terminate()
        server.wait(timeout=15)


if __name__ == "__main__":
    main()
