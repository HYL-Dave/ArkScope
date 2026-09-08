"""Actual UI and closed mock APIs, no production App or provider traffic."""

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageStat
from playwright.sync_api import expect, sync_playwright


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("usage_browser_base", HERE.parent / "2026-09-07-lifecycle-web-runtime/scripts/run_browser.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def install(page, url, scenario, provider, auth):
    state = base.install_web_routes(page, url, "success", provider, auth)
    run = state["run"]
    basis = "claude_model_usage" if auth == "claude_code_oauth" else "adapter_report"
    phases = [
        {"phase": "search", "basis": basis, "input_tokens": 29706, "output_tokens": 3228,
         "cache_creation_input_tokens": 3976 if basis == "claude_model_usage" else None,
         "cache_read_input_tokens": 3354 if basis == "claude_model_usage" else None,
         "web_search_requests": 2 if basis == "claude_model_usage" else None},
        {"phase": "analysis", "basis": basis, "input_tokens": 300, "output_tokens": 400,
         "cache_creation_input_tokens": 0 if basis == "claude_model_usage" else None,
         "cache_read_input_tokens": 0 if basis == "claude_model_usage" else None,
         "web_search_requests": 0 if basis == "claude_model_usage" else None},
    ]
    report = {"version": 1, "coverage": "complete", "recorded_submissions": 2, "phases": phases,
              "totals": {"input_tokens": 30006, "output_tokens": 3628}, "known_subtotal": {"input_tokens": 30006, "output_tokens": 3628}}
    if scenario == "large_counters":
        phases[0].update(input_tokens=9007199254740991, output_tokens=128000)
        phases[1].update(input_tokens=0, output_tokens=0)
        report["totals"] = report["known_subtotal"] = {"input_tokens": 9007199254740991, "output_tokens": 128000}
    if scenario in {"source_failed", "partial", "unknown"}:
        run.update(status="failed", failure_code="source_read_incomplete" if scenario == "source_failed" else "provider_call_failed", finding=None)
        report.update(recorded_submissions=1, phases=phases[:1])
        report["known_subtotal"] = {"input_tokens": 29706, "output_tokens": 3228}
        if scenario == "source_failed":
            run["model_submissions"] = 1
            report["totals"] = dict(report["known_subtotal"])
        else:
            report.update(coverage="partial", totals={"input_tokens": None, "output_tokens": None})
        if scenario == "unknown":
            report.update(coverage="unknown", known_subtotal={"input_tokens": None, "output_tokens": None})
            phases[0].update(input_tokens=None, output_tokens=None, cache_creation_input_tokens=0, cache_read_input_tokens=None, web_search_requests=0)
    if scenario == "legacy":
        run["usage_report"] = None
    else:
        run.update(usage_report=report, usage=report["totals"])
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sources = base.source_hashes()
    sources[str(Path(__file__).relative_to(base.ROOT))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    server = subprocess.Popen(["node", str(base.PREVIOUS.parent / "serve_preview.mjs")], cwd=base.ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    results = []
    try:
        line = server.stdout.readline()
        if not line:
            raise RuntimeError(server.stderr.read())
        url = json.loads(line)["url"]
        scenarios = [(name, "anthropic", "claude_code_oauth") for name in (
            "complete", "source_failed", "partial", "unknown", "legacy", "large_counters")]
        scenarios += [("complete", "openai", "api_key"), ("complete", "openai", "chatgpt_oauth"), ("complete", "anthropic", "api_key")]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for locale in ("en", "zh-Hant"):
                for width, height in ((1440, 900), (390, 844), (320, 740)):
                    for scenario, provider, auth in scenarios:
                        context = browser.new_context(viewport={"width": width, "height": height}, service_workers="block")
                        page, errors = context.new_page(), []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        state = install(page, url, scenario, provider, auth)
                        page.goto(url + "?locale=" + locale)
                        page.get_by_role("button", name="Review OLD" if locale == "en" else "\u6aa2\u8996 OLD", exact=True).click()
                        details = page.locator(".lifecycle-web-usage")
                        expect(details).to_be_visible()
                        assert details.get_attribute("open") is None
                        metrics, pixels = {}, {}

                        def capture(phase):
                            metrics[phase] = base.geometry(page, ".ui-drawer")
                            metrics[phase]["usage_overflow"] = details.evaluate("""root => [...root.querySelectorAll('dt,dd,summary')]
                              .filter(node => node.getClientRects().length && node.scrollWidth > node.clientWidth + 2)
                              .map(node => node.textContent)""")
                            path = args.output / f"{locale}-{width}-{scenario}-{provider}-{auth}-{phase}.png"
                            page.screenshot(path=str(path))
                            with Image.open(path) as picture:
                                pixels[phase] = max(ImageStat.Stat(picture).var)
                            assert pixels[phase] > 5 and not any(metrics[phase].values()), metrics[phase]

                        details.scroll_into_view_if_needed()
                        capture("collapsed")
                        details.locator("summary").click()
                        assert details.get_attribute("open") is not None
                        expect(details).to_contain_text("Reported counters, not a bill" if locale == "en" else "\u56de\u5831\u8a08\u6578\uff0c\u975e\u5e33\u55ae")
                        if scenario == "legacy":
                            expect(details).to_contain_text("Counter source was not recorded" if locale == "en" else "\u672a\u8a18\u9304\u8a08\u6578\u4f86\u6e90")
                        elif scenario == "unknown":
                            expect(details).to_contain_text("Token counts not reported" if locale == "en" else "Token \u8a08\u6578\u672a\u56de\u5831")
                            expect(details.locator(".lifecycle-web-usage-phase dd").nth(2)).to_have_text("0")
                        else:
                            expect(details).to_contain_text("9,007,199,254,740,991" if scenario == "large_counters" else "29,706")
                            if scenario == "partial":
                                expect(details).to_contain_text("Known subtotal" if locale == "en" else "\u5df2\u77e5\u5c0f\u8a08")
                                expect(details).not_to_contain_text("Reported total" if locale == "en" else "\u56de\u5831\u7e3d\u8a08")
                        if scenario in {"source_failed", "partial", "unknown"}:
                            expect(page.locator(".lifecycle-web")).to_contain_text("Investigation failed" if locale == "en" else "\u8abf\u67e5\u5931\u6557")
                        if scenario == "complete":
                            expect(page.locator(".lifecycle-web-result")).not_to_contain_text("29,706")
                        details.locator("summary").scroll_into_view_if_needed()
                        capture("expanded")
                        assert errors == [] and state["unexpected"] == [] and state["posts"] == [] and state["web_posts"] == []
                        results.append({"locale": locale, "width": width, "scenario": scenario, "provider": provider, "auth_mode": auth,
                                        "geometry": metrics, "pixel_variance": pixels, "page_errors": errors,
                                        "provider_calls": 0, "fixture_writes": 0})
                        context.close()
            browser.close()
        assert all(hashlib.sha256((base.ROOT / name).read_bytes()).hexdigest() == expected for name, expected in sources.items())
        with (args.output / "results.json").open("x") as stream:
            json.dump({"source_sha256": sources, "provider_calls": 0, "production_app_started": False, "cases": results}, stream, indent=2)
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
