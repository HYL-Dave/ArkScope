"""Real Settings components, intercepted fixtures only; no production sidecar."""

import ast
import copy
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect


ROOT = Path(__file__).resolve().parents[4]
prior = ROOT / "docs/superpowers/evidence/2026-09-08-settings-handtest-repair/arkscope-settings-handtest-browser.py"
# Reuse only fixture imports/assignments, never the previous browser workflow.
tree = ast.parse(prior.read_text())
fixtures = {}
exec(compile(ast.Module(body=[node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign))],
                        type_ignores=[]), str(prior), "exec"), fixtures)
BASE = "http://127.0.0.1:8447"
OUT = Path("/tmp/arkscope-automation-gpt6-browser")
OUT.mkdir(exist_ok=True)
catalog = fixtures["CATALOG"]
astra = {**catalog["models"][0], "id": "gpt-6-astra", "provider": "openai", "label": "GPT-6 Astra"}
catalog["models"].append(astra)
for task in fixtures["TASKS"]:
    catalog["effective"]["tasks"][task]["providers"]["openai"]["models"].append(dict(
        id="gpt-6-astra", label="GPT-6 Astra", status="seed", visible_to_credential=None,
        eligible=True, reason_code=None, thinking_mode="none", effort_options=fixtures["EFFORTS"]))

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    results = []
    for locale in ("en", "zh-Hant"):
        for width, height in ((1280, 960), (390, 844)):
            context = browser.new_context(viewport={"width": width, "height": height})
            context.add_init_script("window.arkscope={apiBase:" + json.dumps(BASE + "/__mock") + "}; window.requestIdleCallback=()=>1; window.cancelIdleCallback=()=>{};")
            page = context.new_page()
            state = {"catalog": copy.deepcopy(catalog), "automation": copy.deepcopy(fixtures["AUTOMATION"])}
            errors, writes = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def route(request):
                url = urlsplit(request.request.url)
                if url.netloc != "127.0.0.1:8447":
                    errors.append("Unexpected network")
                    return request.abort()
                if url.path == "/__settings-preview":
                    return request.fulfill(status=200, content_type="text/html", body=fixtures["HTML"])
                if not url.path.startswith("/__mock/"):
                    return request.continue_()
                path = url.path.removeprefix("/__mock")
                if request.request.method == "PUT":
                    body = request.request.post_data_json
                    writes.append({"path": path, "body": body})
                    if path == "/security-lifecycle/automation":
                        state["automation"]["config"] = body
                        state["automation"]["schedule"]["status"] = "scheduled" if body["enabled"] else "disabled"
                        value = state["automation"]
                    elif path == "/config/model-routes":
                        rows = {task: dict(task=task, **row, source="db", custom=False, warning=None)
                                for task, row in body["routes"].items()}
                        state["catalog"]["routes"].update(rows)
                        value = {"routes": rows}
                    else:
                        errors.append("Unexpected write: " + path)
                        value = {}
                elif path == "/config/model-catalog":
                    value = state["catalog"]
                elif path == "/security-lifecycle/automation":
                    value = state["automation"]
                else:
                    values = {"/market-data/status": {"exists": False}, "/security-lifecycle/cases": fixtures["CASES"],
                              "/market-data/trading-days": fixtures["COVERAGE"],
                              "/market-data/price-repair/operations": {"version": 1, "operations": [], "total": 0, "offset": 0, "has_more": False},
                              "/schedule": {"sources": {}}}
                    if path not in values:
                        errors.append("Unexpected read: " + path)
                    value = values.get(path, {})
                request.fulfill(status=200, content_type="application/json", body=json.dumps(value))

            page.route("**/*", route)

            def layout(name):
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), name
                assert not page.evaluate("""() => [...document.querySelectorAll('button,select,[role=radio],.model-route-card')]
                    .filter(e=>e.getBoundingClientRect().width && e.scrollWidth>e.clientWidth+2)
                    .map(e=>e.className)"""), name
                page.screenshot(path=str(OUT / f"{locale}-{width}-{name}.png"), full_page=True)

            page.goto(BASE + "/__settings-preview?locale=" + locale)
            panel = page.locator(".lifecycle-settings")
            expect(panel.locator('[role="radiogroup"]')).to_be_visible()
            expect(panel.get_by_role("radio")).to_have_count(3)
            panel.locator(".lifecycle-automation-modes label").nth(1).click()
            expect(panel.get_by_role("radio").nth(1)).to_be_checked()
            assert state["automation"]["config"]["enabled"] is True
            assert state["automation"]["config"]["apply_profile_transitions"] is False
            panel.locator(".lifecycle-automation-modes label").nth(2).click()
            expect(panel.get_by_role("radio").nth(2)).to_be_checked()
            assert state["automation"]["config"]["apply_profile_transitions"] is True
            panel.locator(".lifecycle-automation-advanced > summary").click()
            expect(panel.locator("select")).to_have_count(1)
            layout("automatic")
            panel.locator(".lifecycle-automation-modes label").nth(0).click()
            expect(panel.get_by_role("radio").nth(0)).to_be_checked()
            assert state["automation"]["config"]["enabled"] is False
            assert state["automation"]["config"]["apply_profile_transitions"] is False

            state["automation"]["config"]["apply_profile_transitions"] = True
            page.reload()
            expect(panel.get_by_role("radio").nth(0)).to_be_checked()
            expect(panel.locator('[data-automation-state="legacy_conflict"]')).to_be_visible()
            panel.locator(".lifecycle-automation-modes label").nth(0).click()
            expect(panel.locator('[data-automation-state="legacy_conflict"]')).to_have_count(0)
            assert state["automation"]["config"]["apply_profile_transitions"] is False

            page.goto(BASE + "/__settings-preview?mode=discovery&locale=" + locale)
            expect(page.locator(".model-discovery-row")).to_have_count(3)
            assert "models returned by the provider" not in page.locator("body").inner_text()
            assert "provider 回傳模型" not in page.locator("body").inner_text()
            layout("discovery")

            page.goto(BASE + "/__settings-preview?mode=models&locale=" + locale)
            group = page.locator('[aria-labelledby="model-route-card_translation-task-label model-route-card_translation-provider-label"]')
            group.get_by_role("button", name="OpenAI", exact=True).click()
            model = page.locator('[aria-labelledby="model-route-card_translation-task-label model-route-card_translation-model-label"]')
            model.select_option("gpt-6-astra")
            effort = page.locator('[aria-labelledby="model-route-card_translation-task-label model-route-card_translation-effort-label"]')
            effort.select_option("max")
            page.get_by_role("button", name="Save" if locale == "en" else "儲存", exact=True).click()
            expect(page.locator(".ok-text")).to_contain_text("saved" if locale == "en" else "已儲存")
            assert state["catalog"]["routes"]["card_translation"]["model"] == "gpt-6-astra"
            assert state["catalog"]["routes"]["card_translation"]["effort"] == "max"
            expect(model).to_have_value("gpt-6-astra")
            layout("astra-saved")
            assert not errors, errors
            assert len(writes) == 5, writes
            results.append({"locale": locale, "viewport": [width, height], "writes": writes, "errors": errors})
            context.close()
    browser.close()
    (OUT / "result.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results))
