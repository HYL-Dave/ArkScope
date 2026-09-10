"""Actual Settings component with synthetic intercepted data, no sidecar."""

import ast
import copy
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[4]
BASE = "http://127.0.0.1:8543"
OUT = Path("/tmp/arkscope-listing-data-browser")
OUT.mkdir(exist_ok=True)
prior = ROOT / "docs/superpowers/evidence/2026-09-08-settings-handtest-repair/arkscope-settings-handtest-browser.py"
tree = ast.parse(prior.read_text())
fixtures = {}
exec(compile(ast.Module(body=[node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign))],
                        type_ignores=[]), str(prior), "exec"), fixtures)
market = dict(exists=True, market_db="synthetic", fundamentals_mode="local_cache_refetch",
    prices=dict(row_count=0, ticker_count=0, latest_datetime=None),
    news=dict(row_count=0, source_count=0, latest_published=None),
    fundamentals=dict(row_count=0, ticker_count=0, latest_date=None),
    financial_cache=dict(row_count=48, valid_count=24, expired_count=24, latest_fetched_at="2026-09-09T18:38:00Z"))

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    results = []
    for locale in ("en", "zh-Hant"):
        for width, height in ((1280, 960), (390, 844)):
            context = browser.new_context(viewport=dict(width=width, height=height))
            context.add_init_script("window.arkscope={apiBase:" + json.dumps(BASE + "/__mock") + "};")
            page = context.new_page()
            errors, writes = [], []
            state = copy.deepcopy(fixtures["AUTOMATION"])
            page.on("pageerror", lambda error: errors.append(str(error)))

            def route(request):
                url = urlsplit(request.request.url)
                if url.netloc != "127.0.0.1:8543":
                    errors.append("unexpected_network")
                    return request.abort()
                if url.path == "/__settings-preview":
                    return request.fulfill(status=200, content_type="text/html", body=fixtures["HTML"])
                if not url.path.startswith("/__mock/"):
                    return request.continue_()
                path = url.path.removeprefix("/__mock")
                if request.request.method == "PUT" and path == "/security-lifecycle/automation":
                    state["config"] = request.request.post_data_json
                    state["schedule"]["status"] = "scheduled" if state["config"]["enabled"] else "disabled"
                    writes.append(state["config"])
                    value = state
                else:
                    values = {"/market-data/status": market, "/security-lifecycle/cases": fixtures["CASES"],
                        "/security-lifecycle/automation": state, "/market-data/trading-days": fixtures["COVERAGE"],
                        "/market-data/price-repair/operations": dict(version=1, operations=[], total=0, offset=0, has_more=False),
                        "/schedule": {"sources": {}}}
                    if request.request.method != "GET" or path not in values:
                        errors.append("unexpected_api_call")
                    value = values.get(path, {})
                return request.fulfill(status=200, content_type="application/json", body=json.dumps(value))

            page.route("**/*", route)
            page.goto(BASE + "/__settings-preview?locale=" + locale)
            summary = "48 cache entries (24 reusable" if locale == "en" else "48 個快取項目（可重用 24"
            expect(page.get_by_text(summary, exact=False)).to_be_visible()
            label = "Automatic (verified delistings / renames)" if locale == "en" else "自動（已驗證下市／改名）"
            page.get_by_text(label, exact=True).click()
            expect(page.get_by_role("radio", name=label, exact=True)).to_be_checked()
            assert writes == [dict(enabled=True, interval_minutes=5, batch_limit=2, apply_profile_transitions=True)]
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert page.evaluate("""() => [...document.querySelectorAll('.lifecycle-automation-modes label')]
                .every(e => e.scrollWidth <= e.clientWidth + 2 && e.scrollHeight <= e.clientHeight + 2)""")
            page.screenshot(path=str(OUT / f"{locale}-{width}.png"), full_page=True)
            assert not errors, errors
            results.append(dict(locale=locale, viewport=[width, height], writes=len(writes), errors=errors))
            context.close()
    browser.close()
    (OUT / "result.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results))
