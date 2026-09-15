"""Exercise an already-running isolated Desktop; explicitly opens one SEC URL."""

import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
from playwright.async_api import Error as PlaywrightError, async_playwright, expect


CIK = "0000320193"


async def check(root, out):
    launch = json.loads((root / "launch.json").read_text())
    assert launch["profile"] == "isolated-handtest"
    assert launch["production_filesystem_readonly"] is True
    assert launch["scheduler_disabled"] is True
    assert Path(launch["data"]).resolve().is_relative_to(root)
    config = json.loads((root / "home/.config/arkscope/sa_native_host.json").read_text())
    assert urlsplit(config["api_base"]).hostname == "127.0.0.1"
    client_options = {"base_url": config["api_base"],
                      "headers": {"x-arkscope-token": config["api_token"]}}

    def stored():
        with httpx.Client(**client_options) as api:
            return [api.get("/sec-research/" + CIK).json(),
                    api.get("/sec-research/config").json()]

    before = stored()
    with httpx.Client(**client_options) as api:
        options = api.get("/sec-research/" + CIK + "/filing-forms").json()
    assert options["status"] in ("ok", "partial")
    assert {"10-K", "10-Q", "DEF 14A"} <= set(options["data"])
    requests, blocked, errors = [], [], []

    async with async_playwright() as p:
        port = int((root / "home/.config/arkscope-handtest/DevToolsActivePort").read_text().splitlines()[0])
        browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        app_url = (Path(launch["repo"]) / "apps/arkscope-web/dist/index.html").as_uri()
        page = next(pg for context in browser.contexts for pg in context.pages if pg.url == app_url)

        async def guard(route):
            request = route.request
            if request.method != "GET":
                blocked.append(request.method + " " + urlsplit(request.url).path)
                await route.abort()
            else:
                await route.continue_()

        def observe(request):
            url = urlsplit(request.url)
            if url.path.startswith("/sec-research/"):
                requests.append({"path": url.path, "query": parse_qs(url.query)})

        page.on("request", observe)
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.route("**/sec-research/**", guard)
        try:
            await page.set_viewport_size({"width": 1440, "height": 900})
            await page.get_by_role("button", name="設定", exact=True).click()
            await page.get_by_role("tab", name="資料與同步", exact=True).click()
            await page.get_by_role("button", name="SEC 結構化資料", exact=True).click()
            panel = page.locator("section.sec-storage")
            await panel.get_by_role("textbox", name="CIK", exact=True).fill(CIK)
            await page.wait_for_timeout(400)
            assert not any(r["path"].endswith(("/filings", "/filing-forms")) for r in requests)
            await panel.get_by_role("button", name="讀取本機", exact=True).click()
            await expect(panel.locator("tbody tr").first).to_be_visible()
            trigger = panel.get_by_role("button", name="申報類型", exact=True)
            await expect(trigger).to_be_enabled()

            async def menu():
                if await trigger.get_attribute("aria-expanded") != "true":
                    await trigger.click()
                popup = panel.get_by_role("menu")
                await expect(popup).to_be_visible()
                return popup

            async def choose(values):
                popup = await menu()
                for form in options["data"]:
                    item = popup.get_by_role("menuitemcheckbox", name=form, exact=True)
                    if (await item.get_attribute("aria-checked") == "true") != (form in values):
                        await item.click()
                await popup.press("Escape")
                await page.wait_for_timeout(650)
                await expect(panel.locator("tbody tr").first).to_be_visible()

            popup = await menu()
            observed_options = await popup.get_by_role("menuitemcheckbox").all_text_contents()
            assert set(observed_options) == {*options["data"], "全部"}
            await popup.press("Escape")
            await trigger.press("ArrowUp")
            last = panel.get_by_role("menuitemcheckbox", name=options["data"][-1], exact=True)
            await expect(last).to_be_focused()
            await page.keyboard.press("Space")
            await expect(last).to_have_attribute("aria-checked", "true")
            await page.keyboard.press("Home")
            all_types = panel.get_by_role("menuitemcheckbox", name="全部", exact=True)
            await expect(all_types).to_be_focused()
            await page.keyboard.press("Enter")
            await expect(all_types).to_have_attribute("aria-checked", "true")
            await page.keyboard.press("Escape")
            await expect(trigger).to_be_focused()
            await trigger.press("Enter")
            await page.keyboard.press("Tab")
            await expect(panel.locator('input[type="date"]').first).to_be_focused()
            await choose({"10-Q"})
            await expect(panel.locator("tbody tr td").first).to_have_text("10-Q")
            await panel.get_by_role("button", name="下一頁", exact=True).click()
            await expect(panel.locator(".sec-pagination")).to_contain_text("第 2 頁")
            await choose({"10-K", "10-Q"})
            await expect(panel.locator(".sec-pagination")).to_contain_text("第 1 頁")
            query = [r for r in requests if r["path"].endswith("/filings")][-1]["query"]
            assert set(query["forms"]) == {"10-K", "10-Q"} and "cursor" not in query
            forms = await panel.locator("tbody tr td:first-child").all_text_contents()
            assert set(forms) <= {"10-K", "10-K/A", "10-Q", "10-Q/A"}
            await choose({"DEF 14A"})
            await expect(panel.locator("tbody tr td").first).to_have_text("DEF 14A")
            query = [r for r in requests if r["path"].endswith("/filings")][-1]["query"]
            assert query["forms"] == ["DEF 14A"]
            popup = await menu()
            await popup.get_by_role("menuitemcheckbox", name="全部", exact=True).click()
            await popup.press("Escape")
            await page.wait_for_timeout(650)
            query = [r for r in requests if r["path"].endswith("/filings")][-1]["query"]
            assert "forms" not in query and "cursor" not in query
            await choose({"10-K"})
            assert len([r for r in requests if r["path"].endswith("/filing-forms")]) == 1
            single_height = (await trigger.bounding_box())["height"]
            await choose(set(options["data"][:8]))
            assert (await trigger.bounding_box())["height"] == single_height

            layouts = []
            for label, width, height in [("desktop", 1440, 900), ("narrow", 390, 844)]:
                await page.set_viewport_size({"width": width, "height": height})
                await trigger.evaluate('(element) => element.scrollIntoView({block: "center"})')
                popup = await menu()
                await page.wait_for_timeout(150)
                box = await popup.bounding_box()
                assert box and box["width"] > 0 and box["x"] >= 0
                assert box["x"] + box["width"] <= width
                assert await page.evaluate("document.documentElement.scrollWidth") <= width
                await page.screenshot(path=str(out / (label + ".png")))
                layouts.append({"viewport": label, "width": width, "menu": box})
                await popup.press("Escape")

            await page.set_viewport_size({"width": 1440, "height": 900})
            await choose({"10-K"})
            link = panel.get_by_role("link", name="SEC 原文", exact=True).first
            url = await link.get_attribute("href")
            assert urlsplit(url).hostname == "www.sec.gov"
            assert url.startswith("https://www.sec.gov/Archives/edgar/")
            await link.click()
            browser_port_file = root / "home/.config/sec-browser/DevToolsActivePort"
            external = None
            for _ in range(50):
                try:
                    port = int(browser_port_file.read_text().splitlines()[0])
                    external = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=1000)
                    break
                except (FileNotFoundError, ValueError, IndexError, PlaywrightError):
                    await asyncio.sleep(.2)
            assert external is not None, "external browser did not start"
            target = None
            for _ in range(50):
                target = next((pg for c in external.contexts for pg in c.pages if pg.url == url), None)
                if target is not None:
                    break
                await asyncio.sleep(.2)
            assert target is not None, "SEC target was not handed to the browser"
            await target.wait_for_load_state("load", timeout=30000)
            await target.bring_to_front()
            await target.wait_for_timeout(2000)
            body = await target.locator("body").inner_text()
            title = await target.title()
            assert "SECURITIES AND EXCHANGE COMMISSION" in body and "FORM 10-K" in body
            await target.screenshot(path=str(out / "official-document.png"))
            assert page.url == app_url
            assert not blocked and not errors
        finally:
            await page.unroute("**/sec-research/**", guard)
            page.remove_listener("request", observe)

    assert before == stored()
    result = {"commit": launch["commit"], "options": options["data"], "options_status": options["status"],
              "coverage": options["coverage"], "option_requests": 1,
              "multi_select": True, "spaced_code": "DEF 14A", "all_clears": True,
              "native_keyboard_activation_and_tab": True, "stable_trigger_height": single_height,
              "pagination_reset": True, "layouts": layouts,
              "sec_non_get_requests": blocked, "page_errors": errors,
              "stored_status_and_capacity_unchanged": True,
              "external_browser": {"url": url, "title": title,
                                   "body_text_chars": len(body), "rendered": True}}
    (out / "browser.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handtest_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    asyncio.run(check(args.handtest_root.resolve(), args.output.resolve()))
