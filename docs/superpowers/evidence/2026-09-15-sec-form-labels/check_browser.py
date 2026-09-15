"""Check named form choices in the explicitly supplied isolated Desktop only."""

import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
from playwright.async_api import async_playwright, expect


CIK = "0000320193"


async def check(root, out):
    launch = json.loads((root / "launch.json").read_text())
    assert launch["profile"] == "isolated-handtest"
    assert launch["production_filesystem_readonly"] is True
    assert launch["scheduler_disabled"] is True
    assert Path(launch["data"]).resolve().is_relative_to(root)
    config = json.loads((root / "home/.config/arkscope/sa_native_host.json").read_text())
    assert urlsplit(config["api_base"]).hostname == "127.0.0.1"
    with httpx.Client(base_url=config["api_base"], headers={"x-arkscope-token": config["api_token"]}) as api:
        def stored():
            responses = [api.get("/sec-research/" + CIK), api.get("/sec-research/config")]
            for response in responses:
                response.raise_for_status()
            return [response.json() for response in responses]

        before = stored()
        response = api.get("/sec-research/" + CIK + "/filing-forms")
        response.raise_for_status()
        observed = response.json()
        codes = observed["data"]
        assert observed["status"] in ("ok", "partial") and len(codes) == 52
        requests, blocked, errors = [], [], []
        async with async_playwright() as p:
            port = int((root / "home/.config/arkscope-handtest/DevToolsActivePort").read_text().splitlines()[0])
            browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            app_url = (Path(launch["repo"]) / "apps/arkscope-web/dist/index.html").as_uri()
            page = next(pg for ctx in browser.contexts for pg in ctx.pages if pg.url == app_url)
            await page.evaluate("title => {document.title = title}",
                                "ArkScope - SEC Hand Test A - " + launch["commit"][:8] + " - Isolated Data")

            async def guard(route):
                if route.request.method != "GET":
                    blocked.append(route.request.method + " " + urlsplit(route.request.url).path)
                    await route.abort()
                else:
                    await route.continue_()

            def observe(request):
                url = urlsplit(request.url)
                if url.path.startswith("/sec-research/"):
                    requests.append({"path": url.path, "query": parse_qs(url.query)})

            def page_error(error):
                errors.append(str(error))

            page.on("request", observe)
            page.on("pageerror", page_error)
            await page.route("**/sec-research/**", guard)
            try:
                await page.set_viewport_size({"width": 1440, "height": 900})
                await page.get_by_role("button", name="設定", exact=True).click()
                await page.get_by_role("tab", name="資料與同步", exact=True).click()
                await page.get_by_role("button", name="SEC 結構化資料", exact=True).click()
                panel = page.locator("section.sec-storage")
                await panel.get_by_role("textbox", name="CIK", exact=True).fill(CIK)
                await panel.get_by_role("button", name="讀取本機", exact=True).click()
                await expect(panel.locator("tbody tr").first).to_be_visible()
                trigger = panel.get_by_role("button", name="申報類型", exact=True)

                async def menu():
                    if await trigger.get_attribute("aria-expanded") != "true":
                        await trigger.click()
                    popup = panel.get_by_role("menu")
                    await expect(popup).to_be_visible()
                    return popup

                popup = await menu()
                items = popup.get_by_role("menuitemcheckbox").filter(has=page.locator(".sec-form-option-text"))
                names = dict(await items.evaluate_all("els => els.map(el => [el.value, el.textContent])"))
                assert set(names) == set(codes)
                assert all("未分類" not in name and "secResearch." not in name for name in names.values())
                for code, meaning in [("144", "擬出售證券通知"), ("25", "撤銷證券上市及／或註冊通知"), ("3", "初始持股申報")]:
                    await expect(popup.get_by_role("menuitemcheckbox", name=code + " " + meaning, exact=True)).to_have_count(1)
                assert list(names)[:4] == ["10-K", "10-K/A", "10-Q", "10-Q/A"]
                groups = await popup.get_by_role("group").evaluate_all("els => els.map(el => el.getAttribute('aria-label'))")

                await popup.press("End")
                for _ in range(len(codes) + 1):
                    visible = await popup.evaluate("""menu => {
                        const item = document.activeElement;
                        const row = item.getBoundingClientRect(), box = menu.getBoundingClientRect();
                        const x = Math.max(row.left, box.left) + 20;
                        const y = (Math.max(row.top, box.top + 1) + Math.min(row.bottom, box.bottom - 1)) / 2;
                        return item.getAttribute('role') === 'menuitemcheckbox'
                            && item.contains(document.elementFromPoint(x, y));
                    }""")
                    assert visible, "keyboard-focused choice is covered"
                    await page.keyboard.press("ArrowUp")

                await popup.press("Home")
                await expect(popup.get_by_role("menuitemcheckbox", name="全部", exact=True)).to_be_focused()
                await page.keyboard.press("ArrowDown")
                annual = popup.get_by_role("menuitemcheckbox", name="10-K 年報", exact=True)
                await expect(annual).to_be_focused()
                await page.keyboard.press("Space")
                await expect(annual).to_have_attribute("aria-checked", "true")
                for code in ["144", "25", "3", "DEF 14A"]:
                    await popup.get_by_role("menuitemcheckbox", name=names[code], exact=True).click()
                await popup.press("Escape")
                await expect(trigger).to_be_focused()
                await page.wait_for_timeout(700)
                query = [req for req in requests if req["path"].endswith("/filings")][-1]["query"]
                assert set(query["forms"]) == {"10-K", "144", "25", "3", "DEF 14A"}
                assert "cursor" not in query
                layouts = []
                for label, width, height in [("desktop", 1440, 900), ("medium", 840, 900), ("narrow", 390, 844)]:
                    await page.set_viewport_size({"width": width, "height": height})
                    await trigger.evaluate("el => el.scrollIntoView({block:'center'})")
                    popup = await menu()
                    await popup.evaluate("el => {el.scrollTop = 0}")
                    await page.wait_for_timeout(150)
                    box = await popup.bounding_box()
                    assert box and box["x"] >= 0 and box["x"] + box["width"] <= width, box
                    assert await page.evaluate("document.documentElement.scrollWidth") <= width
                    assert await popup.evaluate("el => el.scrollWidth <= el.clientWidth")
                    assert (await trigger.bounding_box())["height"] == 32
                    await page.screenshot(path=str(out / (label + ".png")))
                    await popup.get_by_role("menuitemcheckbox", name=names["25"], exact=True).scroll_into_view_if_needed()
                    await page.screenshot(path=str(out / (label + "-listing.png")))
                    layouts.append({"viewport": label, "menu": box})
                    await popup.press("Escape")
                await page.set_viewport_size({"width": 1440, "height": 900})
                popup = await menu()
                await popup.get_by_role("menuitemcheckbox", name="全部", exact=True).click()
                await popup.press("Escape")
                await page.wait_for_timeout(700)
                assert "forms" not in [req for req in requests if req["path"].endswith("/filings")][-1]["query"]
                popup = await menu()
                await popup.get_by_role("menuitemcheckbox", name="10-K 年報", exact=True).click()
                await popup.press("Escape")
                await page.wait_for_timeout(700)
                await expect(panel.locator("tbody tr td").first).to_have_text("10-K")
                await trigger.evaluate("el => el.scrollIntoView({block:'center'})")
                assert len([req for req in requests if req["path"].endswith("/filing-forms")]) == 1
                assert not blocked and not errors
            finally:
                await page.unroute("**/sec-research/**", guard)
                page.remove_listener("request", observe)
                page.remove_listener("pageerror", page_error)
        assert before == stored()
    result = {"commit": launch["commit"], "names": names, "groups": groups, "layouts": layouts,
              "exact_filters": True, "all_clears": True, "keyboard": True, "option_requests": 1,
              "sec_non_get_requests": blocked, "page_errors": errors, "stored_status_and_capacity_unchanged": True}
    (out / "browser.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"options": len(names), "groups": groups, "layouts": layouts}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handtest_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    asyncio.run(check(args.handtest_root.resolve(), args.output.resolve()))
