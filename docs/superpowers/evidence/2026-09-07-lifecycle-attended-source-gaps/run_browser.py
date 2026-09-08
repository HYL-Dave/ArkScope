"""Source-bound real UI, intercepted fixture APIs only; no production App."""

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
spec = importlib.util.spec_from_file_location("gap_browser_base", HERE.parent / "2026-09-07-lifecycle-web-runtime/scripts/run_browser.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
URL = "https://financial-news.example.com/investor-relations/2026/ordinary-share-trading-status-and-listing-update"


def install(page, url, scenario):
    state = base.install_web_routes(page, url, "rename" if scenario == "rename" else "blocked" if scenario == "blocked" else "success",
        "openai" if scenario == "rename" else "anthropic", "chatgpt_oauth" if scenario == "rename" else "claude_code_oauth")
    run = state["run"]
    gaps = [{"url": None if scenario == "legacy" else URL, "reason": "source_unavailable"}]
    run["source_gaps"] = gaps
    packet = deepcopy(base.CONTRACT["packet"])
    packet.update(case_id=run["case_id"], source_ticker=run["ticker"], action=run["finding"]["action"],
                  execute_on=run["finding"]["effective_date"], source_gaps=gaps)
    packet["options"]["execute_on"] = packet["execute_on"]
    packet["finding"].update(impact_summary=run["finding"]["summary"], effective_date=packet["execute_on"],
                             successor_ticker=run["finding"]["successor_ticker"])
    if scenario == "rename":
        packet["finding"]["outcomes"] = ["symbol_changed"]
        packet["effects"]["watchlists"]["add"] = [{"list_name": "Long-term tracking list", "ticker": "NEW"}]

    def handle(route):
        path = urlparse(route.request.url).path
        if path.endswith("/review"):
            assert route.request.method == "GET"
            state["web_reads"].append(path)
            value = packet
        elif path.endswith("/confirm"):
            assert route.request.method == "POST"
            body = route.request.post_data_json
            assert body == {"packet_sha256": packet["packet_sha256"], "action": packet["action"],
                            **packet["options"], "acknowledge_source_gaps": True}
            state["web_posts"].append(path)
            state["applied"] = True
            value = {**base.CONTRACT["confirmation"], "packet_sha256": packet["packet_sha256"],
                "action": packet["action"], "execute_on": packet["execute_on"], "successor_ticker": packet["finding"]["successor_ticker"]}
        else:
            route.fallback()
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps(value), headers={"Access-Control-Allow-Origin": "*"})

    page.route("**/security-lifecycle/web-runs/run-1/*", handle)
    return state, packet


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    hashes = base.source_hashes()
    hashes[str(Path(__file__).relative_to(base.ROOT))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    server = subprocess.Popen(["node", str(base.PREVIOUS.parent / "serve_preview.mjs")], cwd=base.ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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
                    for scenario in ("removal", "rename", "blocked", "legacy"):
                        context = browser.new_context(viewport={"width": width, "height": height}, service_workers="block")
                        page, errors = context.new_page(), []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        state, packet = install(page, url, scenario)
                        page.goto(url + "?locale=" + locale)
                        page.get_by_role("button", name="Review OLD" if locale == "en" else "\u6aa2\u8996 OLD", exact=True).click()
                        web = page.locator(".lifecycle-web")
                        expect(web).to_be_visible()
                        disclosure = web.locator(".lifecycle-web-gaps")
                        expect(disclosure).to_contain_text("not used as evidence" if locale == "en" else "\u672a\u5217\u70ba\u5224\u65b7\u4f9d\u64da")
                        expect(disclosure.locator("a")).to_have_count(0 if scenario == "legacy" else 1)
                        if scenario != "legacy":
                            expect(disclosure.locator("a")).to_have_attribute("href", URL)
                            expect(disclosure.locator("a")).to_have_attribute("title", URL)
                            expect(disclosure.locator("a")).to_have_text(urlparse(URL).hostname)
                        metrics, pixels = {}, {}

                        def capture(phase, selector):
                            metrics[phase] = base.geometry(page, selector)
                            path = args.output / f"{locale}-{width}-{scenario}-{phase}.png"
                            page.screenshot(path=str(path))
                            with Image.open(path) as picture:
                                pixels[phase] = max(ImageStat.Stat(picture).var)
                            assert pixels[phase] > 5 and not any(metrics[phase].values()), metrics[phase]

                        disclosure.scroll_into_view_if_needed()
                        capture("finding", ".ui-drawer")
                        if scenario == "blocked":
                            expect(web).to_contain_text("active OTC")
                            expect(web.get_by_role("button", name="Review removal" if locale == "en" else "\u78ba\u8a8d\u79fb\u9664\u7bc4\u570d", exact=True)).to_have_count(0)
                        else:
                            name = ("Review symbol change" if scenario == "rename" else "Review removal") if locale == "en" else (
                                "\u78ba\u8a8d\u6539\u540d\u7bc4\u570d" if scenario == "rename" else "\u78ba\u8a8d\u79fb\u9664\u7bc4\u570d")
                            web.get_by_role("button", name=name, exact=True).click()
                            confirm = "Confirm and apply" if locale == "en" else "\u78ba\u8a8d\u4e26\u5957\u7528"
                            web.get_by_role("button", name=confirm, exact=True).click()
                            dialog = page.locator(".ui-confirm-dialog")
                            expect(dialog).to_be_visible()
                            expect(dialog).to_contain_text(packet["finding"]["impact_summary"])
                            expect(dialog.locator(".lifecycle-web-gaps")).to_contain_text(
                                "not used as evidence" if locale == "en" else "\u672a\u5217\u70ba\u5224\u65b7\u4f9d\u64da")
                            assert state["web_posts"] == []
                            capture("confirm", ".ui-confirm-dialog")
                            dialog.get_by_role("button", name=confirm, exact=True).click()
                            expect(dialog).not_to_be_visible()
                        assert errors == [] and state["unexpected"] == [] and state["posts"] == []
                        assert state["web_posts"] == ([] if scenario == "blocked" else ["/security-lifecycle/web-runs/run-1/confirm"])
                        results.append({"locale": locale, "width": width, "scenario": scenario, "geometry": metrics,
                                        "pixel_variance": pixels, "page_errors": errors, "provider_calls": 0,
                                        "fixture_confirmations": len(state["web_posts"])})
                        context.close()
            browser.close()
        assert all(hashlib.sha256((base.ROOT / name).read_bytes()).hexdigest() == value for name, value in hashes.items())
        with (args.output / "results.json").open("x") as stream:
            json.dump({"source_sha256": hashes, "provider_calls": 0, "production_app_started": False, "cases": results}, stream, indent=2)
            stream.write("\n")
        print(json.dumps({"passed": len(results), "screenshots": sum(len(row["geometry"]) for row in results)}), flush=True)
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


if __name__ == "__main__":
    main()
