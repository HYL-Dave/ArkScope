"""Read-only source disclosure/diagnostic UI, with synthetic intercepted APIs."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright, expect


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("capacity_browser", HERE.parent / "2026-09-07-lifecycle-web-runtime/scripts/run_browser.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    hashes = base.source_hashes()
    hashes[str(Path(__file__).relative_to(base.ROOT))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    results = []
    server = subprocess.Popen(["node", str(base.PREVIOUS.parent / "serve_preview.mjs")], cwd=base.ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        line = server.stdout.readline()
        if not line:
            raise RuntimeError(server.stderr.read())
        url = json.loads(line)["url"]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for locale in ("en", "zh-Hant"):
                for width, height in ((1440, 900), (390, 844), (320, 740)):
                    for scenario in ("selected", "read_failure"):
                        context = browser.new_context(viewport={"width": width, "height": height}, service_workers="block")
                        page, errors = context.new_page(), []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        state = base.install_web_routes(page, url, "blocked", "anthropic", "claude_code_oauth")
                        run = state["run"]
                        run["source_requests"] = 4
                        run["source_reading"] = {"sources": 4, "selected_sources": 4,
                                                 "retained_text_bytes": 536634160, "model_text_bytes": 192796}
                        run["source_reads"] = [{"request_index": index, "status": 200, "framing": "content_length",
                            "content_encoding": "gzip", "declared_body_bytes": 145597, "received_body_bytes": 145597,
                            "decoded_body_bytes": 134208836, "result_code": "complete"} for index in range(1, 5)]
                        if scenario == "read_failure":
                            run.update(status="failed", model_submissions=1, finding=None, source_reading=None,
                                       failure_code="source_read_incomplete")
                            run["source_reads"][0].update(status=403, result_code="source_unavailable", received_body_bytes=0,
                                                         decoded_body_bytes=0, declared_body_bytes=None, framing=None,
                                                         content_encoding=None)
                            for item in run["source_reads"][1:]:
                                item.update(result_code="source_body_incomplete", received_body_bytes=400,
                                            decoded_body_bytes=400, declared_body_bytes=1000, content_encoding="identity")
                        page.goto(url + "?locale=" + locale)
                        page.get_by_role("button", name="Review OLD" if locale == "en" else "\u6aa2\u8996 OLD", exact=True).click()
                        web = page.locator(".lifecycle-web")
                        web.scroll_into_view_if_needed()
                        expect(web).to_be_visible()
                        if scenario == "selected":
                            expect(web).to_contain_text("Full source text retained" if locale == "en" else "\u4fdd\u7559\u5b8c\u6574\u4f86\u6e90\u6587\u5b57")
                        else:
                            expect(web).to_contain_text("Investigation failed" if locale == "en" else "\u8abf\u67e5\u5931\u6557")
                            expect(web.locator("blockquote")).to_have_count(0)
                        metrics = {}
                        for phase in ("closed", "expanded"):
                            if phase == "expanded":
                                web.locator("summary").click()
                                expect(web).to_contain_text("HTTP 403" if scenario == "read_failure" else "HTTP 200")
                            web.scroll_into_view_if_needed()
                            metrics[phase] = base.geometry(page, ".ui-drawer")
                            path = args.output / f"{locale}-{width}-{scenario}-{phase}.png"
                            page.screenshot(path=str(path))
                            with Image.open(path) as picture:
                                variance = max(ImageStat.Stat(picture).var)
                            assert variance > 5 and not any(metrics[phase].values()), metrics[phase]
                        assert errors == [] and state["unexpected"] == [] and state["posts"] == [] and state["web_posts"] == []
                        results.append({"locale": locale, "width": width, "scenario": scenario, "geometry": metrics,
                                        "page_errors": errors, "provider_calls": 0, "writes": 0})
                        context.close()
            browser.close()
        assert all(hashlib.sha256((base.ROOT / name).read_bytes()).hexdigest() == value for name, value in hashes.items())
        with (args.output / "results.json").open("x") as stream:
            json.dump({"source_sha256": hashes, "production_app_started": False, "provider_calls": 0, "cases": results}, stream, indent=2)
            stream.write("\n")
        print(json.dumps({"passed": len(results), "screenshots": len(results) * 2, "provider_calls": 0}), flush=True)
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


if __name__ == "__main__":
    main()
