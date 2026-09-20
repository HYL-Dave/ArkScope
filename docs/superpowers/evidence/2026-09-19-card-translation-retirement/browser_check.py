"""Verify preserved translation controls with a synthetic, intercepted API."""

import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


URL = "http://127.0.0.1:8437"
OUTPUT = Path("/tmp/arkscope-card-translation-preserved-browser")
HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>main{padding:16px;max-width:1060px;margin:auto}section{margin-top:24px}</style>
</head><body><main id="root"></main><script type="module">
import RefreshRuntime from '/@react-refresh';
RefreshRuntime.injectIntoGlobalHook(window);
window.$RefreshReg$ = () => {}; window.$RefreshSig$ = () => type => type;
window.__vite_plugin_react_preamble_installed__ = true;
window.arkscope = {apiBase:location.origin};
const React = (await import('/node_modules/.vite/deps/react.js')).default;
const {createRoot} = (await import('/node_modules/.vite/deps/react-dom_client.js')).default;
const i18n = (await import('/node_modules/.vite/deps/i18next.js')).default;
const {initializeI18n} = await import('/src/i18n/resources.ts');
const {CardView} = await import('/src/AICard.tsx');
const {FixedTaskRuntimeSection} = await import('/src/settings/RuntimeLimitSections.tsx');
await import('/src/styles.css');
initializeI18n(i18n, new URLSearchParams(location.search).get('locale'));
window.cardSaves = 0; window.runtimeSave = null; window.i18n = i18n;
const card = window.originalCard = {
 ticker:'TEST', question:'What changed after earnings?', horizon:'event observation',
 card_type:'analysis', analysis_time:'2026-09-19T12:00:00Z',
 conclusion:'Original analysis remains unchanged when the interface language changes.',
 primary_reasons:['Compare the observed reaction with the pre-announcement price.'],
 counter_thesis:['The price observation may be delayed.'], key_assumptions:[],
 trigger_conditions:[], invalidation_conditions:[], risks:[], watch_list:[],
 market_narrative:null, divergence:null, confidence_level:'low', confidence_rationale:null,
 traceability:{data_sources:[], claims:[], completeness:{news:false,fundamentals:false,technical:false,notes:[]},
 single_model_inference:true}
};
createRoot(document.getElementById('root')).render(React.createElement(React.Fragment,null,
 React.createElement(CardView,{card,runId:1,saved:false,onSave:()=>{window.cardSaves++;},
 developerMode:false,onNavigateTarget:()=>{},
 executionReceipt:{provider:'openai',model:'historical-model',effort:'high',auth_mode:'api_key'}}),
 React.createElement(FixedTaskRuntimeSection,{
 settings:{card_synthesis:{task:'card_synthesis',model_timeout_s:900,source:'db',db_saved:true,warning:null},
 card_translation:{task:'card_translation',model_timeout_s:600,source:'db',db_saved:true,warning:null}},
 saving:false,onSave:body=>{window.runtimeSave=body;},onReset:()=>{},developerMode:false})))
</script></body></html>"""


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width, height in [(1440, 1000), (390, 844)]:
            for locale in ("en", "zh-Hant"):
                page = browser.new_page(viewport={"width": width, "height": height})
                errors, blocked, translations = [], [], []
                page.on("pageerror", lambda error: errors.append(str(error)))

                def route(request):
                    parsed = urlparse(request.request.url)
                    if parsed.netloc != "127.0.0.1:8437":
                        blocked.append(parsed.netloc)
                        request.abort()
                    elif parsed.path == "/__translation_check":
                        request.fulfill(status=200, content_type="text/html", body=HTML)
                    elif parsed.path == "/analysis/cards/1/translate":
                        assert request.request.method == "POST"
                        translations.append(request.request.post_data_json)
                        translated = page.evaluate("window.originalCard")
                        translated["conclusion"] = "Translated analysis from the selected supported model."
                        request.fulfill(status=200, json={
                            "run_id": 1, "lang": "zh-Hant", "card": translated, "cached": False,
                            "execution_receipt": {"provider": "anthropic", "model": "claude-sonnet-5",
                                                  "effort": "medium", "auth_mode": "api_key"},
                        })
                    else:
                        request.continue_()

                page.route("**/*", route)
                page.goto(f"{URL}/__translation_check?locale={locale}")
                page.locator(".cardview-concl").wait_for()
                original = page.locator(".cardview-concl").inner_text()
                assert page.locator(".lang-toggle button").count() == 2
                assert page.locator('input[type="number"]').count() == 2
                assert not translations
                page.locator(".cardview-head > button").last.click()
                assert page.evaluate("window.cardSaves") == 1
                page.locator('input[name="card_synthesis_model_timeout_s"]').fill("1200")
                page.locator(".settings-actions button").first.click()
                assert page.evaluate("window.runtimeSave") == {"tasks": {
                    "card_synthesis": {"model_timeout_s": 1200},
                    "card_translation": {"model_timeout_s": 600}}}
                page.evaluate("locale => window.i18n.changeLanguage(locale)", "zh-Hant" if locale == "en" else "en")
                assert page.locator(".cardview-concl").inner_text() == original
                page.evaluate("locale => window.i18n.changeLanguage(locale)", locale)
                assert not translations
                page.locator(".lang-toggle button").nth(1).click()
                page.wait_for_function("document.querySelector('.cardview-concl').textContent.includes('Translated analysis')")
                assert translations == [{"lang": "zh-Hant"}]
                assert "claude-sonnet-5" in page.locator(".cardview").inner_text()
                page.locator(".lang-toggle button").first.click()
                assert page.locator(".cardview-concl").inner_text() == original
                page.locator(".lang-toggle button").nth(1).click()
                assert len(translations) == 1
                page.locator(".cardview-head button[aria-label]").click()
                page.wait_for_function("!document.querySelector('.lang-toggle button').disabled")
                assert translations == [{"lang": "zh-Hant"}, {"lang": "zh-Hant", "refresh": True}]
                geometry = page.evaluate("""() => ({
                    viewport:innerWidth,width:document.documentElement.scrollWidth,
                    controls:[...document.querySelectorAll('button,input')].map(e=>{
                      const r=e.getBoundingClientRect();return {left:r.left,right:r.right,width:r.width,height:r.height};})
                })""")
                assert geometry["width"] <= width
                assert all(0 <= c["left"] < c["right"] <= width and c["height"] > 0 for c in geometry["controls"])
                assert not errors, errors
                assert not blocked, blocked
                screenshot = OUTPUT / f"{width}-{locale}.png"
                page.screenshot(path=str(screenshot), full_page=True)
                results.append({"width": width, "locale": locale, "screenshot": str(screenshot),
                                "translation_controls_present": True, "original_unchanged": True,
                                "translate_cache_refresh_work": True,
                                "save_commands_work": True, "no_external_requests": True,
                                "geometry": geometry})
                page.close()
        browser.close()
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
