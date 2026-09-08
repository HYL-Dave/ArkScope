import copy
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect

BASE = "http://127.0.0.1:8447"
OUT = Path("/tmp/arkscope-settings-handtest-check")
OUT.mkdir(exist_ok=True)
TASKS = ("card_synthesis", "card_translation", "ai_research", "lifecycle_investigation")
MODELS = ("claude-sonnet-5", "gpt-5.3-codex-spark", "gpt-5.6-luna", "claude-sonnet-5")
EFFORTS = ["low", "medium", "high", "xhigh", "max"]
ROUTES = {task: dict(task=task, provider="anthropic" if model.startswith("claude") else "openai", model=model,
                    effort="high", source="db", custom=False, warning=None) for task, model in zip(TASKS, MODELS)}
CATALOG = dict(
    providers=["anthropic", "openai"],
    tasks=[dict(id=task, label=task, description="", default_provider=ROUTES[task]["provider"], recommended_model=ROUTES[task]["model"]) for task in TASKS],
    models=[dict(id=model, provider="anthropic" if model.startswith("claude") else "openai", label=model,
                 quality="frontier", speed="medium", cost_tier="medium", supports_structured_output=True,
                 supports_tool_calling=True, effort_options=EFFORTS, task_route_status="current", aliases=[],
                 recommended_for=[], source_url="", verified_at="", notes="") for model in sorted(set(MODELS))],
    effort_options={p: [dict(id=e, provider=p, label=e, description="", applies_to_card_tasks=True) for e in EFFORTS] for p in ("openai", "anthropic")},
    routes=ROUTES, credentials={"anthropic": [], "openai": []}, custom_allowed=True,
    effective=dict(providers={p: dict(credential_id="local:8" if p == "anthropic" else "local:7", auth_mode="claude_code_oauth" if p == "anthropic" else "chatgpt_oauth", label="Claude subscription" if p == "anthropic" else "ChatGPT subscription", plan_type=None if p == "anthropic" else "prolite") for p in ("anthropic", "openai")},
                   tasks={task: dict(verified=[], advanced=[], cache_state="ok", discovered_at=None, current_provider=ROUTES[task]["provider"],
                                    providers={p: dict(executable=True, reason_code=None, cache_state="seed_only" if p == "anthropic" else "ok", discovered_at="2026-09-08T05:00:00Z" if p == "openai" else None,
                                                       models=[dict(id=model, label=model, status="seed" if p == "anthropic" else "visible", visible_to_credential=True, eligible=True, reason_code=None, thinking_mode="none", effort_options=EFFORTS)])
                                               for p, model in [("anthropic", "claude-sonnet-5"), ("openai", "gpt-5.3-codex-spark" if task == "card_translation" else "gpt-5.6-luna")]}) for task in TASKS}),
)
AUTOMATION = dict(config_status="valid", config=dict(enabled=False, interval_minutes=5, batch_limit=2, apply_profile_transitions=False),
                  schedule=dict(status="disabled", last_attempt_at=None, next_scheduled_at=None), telemetry_status="absent",
                  last_status=None, last_result=None, active_incident=None, latest_failed_runs=[], current_progress=[])
CASES = dict(cases=[], count=3, queue_counts=dict(attention=0, monitoring=0, history=3), admission_counts=dict(admitted=3, needs_review=0, pending=0, screened_out=0), data_integrity=dict(source_missing_count=0))
COVERAGE = dict(version=2, market_scope="us_listed_equity_proxy", coverage_session="rth", interval="15min", lookback_days=15,
                universe_count=183, generated_at_et="2026-09-08T01:12:00-04:00",
                calendar_health=dict(status="ok", reason_codes=[], reviewed_through="2027-12-31", forward_horizon_months=15),
                observation_health=dict(status="ok", reason_code=None), history_gaps=[],
                days=[dict(date="2026-09-04", coverage_status="complete", status_reason_code=None, closure_reason_code=None, session_kind="regular",
                           expected_slot_count=26, complete_ticker_count=183, partial_ticker_count=0, unknown_ticker_count=0,
                           partial_tickers=[], unknown_tickers=[], unmatched_rth_row_count=0)],
                provider_errors=[dict(ticker="ZETA", interval="15min", last_error="ibkr_contract_qualification_failed", reason_code="provider_request_failed", updated_at="2026-09-08T04:00:00Z")])
DISCOVERY = dict(provider="anthropic", credential_id="local:8", status="ok", error=None, source_url=None,
                 models=[dict(id=model, provider="anthropic", label=model, source="seed", effort_options=EFFORTS, default_effort="high", task_route_tasks=list(TASKS)) for model in ("claude-fable-5-1", "claude-sonnet-5", "claude-opus-5")])
HTML = '''<!doctype html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Settings hand-test fixture</title></head><body><div id="root"></div>
<script type="module">import RefreshRuntime from '/@react-refresh'; RefreshRuntime.injectIntoGlobalHook(window); window.$RefreshReg$=()=>{}; window.$RefreshSig$=()=>type=>type; window.__vite_plugin_react_preamble_installed__=true;</script><script type="module" src="/@vite/client"></script>
<script type="module">
import React from '/node_modules/.vite/deps/react.js'; import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
import i18n from '/node_modules/.vite/deps/i18next.js'; import {initializeI18n} from '/src/i18n/resources.ts';
import {installUiTokens} from '/src/ui/tokens.ts'; import {DataStorageSection} from '/src/settings/DataStorageSection.tsx';
import {SettingsView} from '/src/Settings.tsx'; import {DiscoveryResultView} from '/src/settings/ProviderSection.tsx';
import {withTestUiLocale} from '/src/test/testUiLocale.tsx';
import {createSettingsReadCache} from '/src/settings/settingsReadCache.ts'; import '/src/styles.css'; import '/src/ui/primitives.css';
const params=new URL(location.href).searchParams; const locale=params.get('locale') || 'zh-Hant';
await initializeI18n(i18n,locale); document.documentElement.lang=locale; installUiTokens(document.documentElement);
const root=ReactDOM.createRoot(document.getElementById('root')); const cache=createSettingsReadCache();
const mode=params.get('mode');
root.render(mode==='models' ? withTestUiLocale(React.createElement(SettingsView,{runtime:null,developerMode:false,onRuntimeChanged:async()=>{},settingsReadCache:cache,navigationRequest:{sequence:1,target:{kind:'settings_section',section:'models'}}})) :
React.createElement('main',{style:{maxWidth:'1120px',margin:'24px auto',padding:'0 16px'}},
  mode==='discovery' ? React.createElement(DiscoveryResultView,{result:DISCOVERY,authMode:'claude_code_oauth',credentialLabel:'Claude subscription'}) :
  React.createElement(DataStorageSection,{settingsReadCache:cache,onNavigateTarget:(target)=>window.__navigated=target})));
</script></body></html>'''.replace('result:DISCOVERY', 'result:' + json.dumps(DISCOVERY))

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    results = []
    for locale in ("zh-Hant", "en"):
        for width, height in ((1280, 960), (390, 844)):
            context = browser.new_context(viewport=dict(width=width, height=height))
            context.add_init_script("window.arkscope={apiBase:" + json.dumps(BASE + "/__mock") + "}; window.requestIdleCallback=()=>1; window.cancelIdleCallback=()=>{};")
            page = context.new_page()
            errors, requests = [], []
            state = dict(catalog=copy.deepcopy(CATALOG), saved=False, fail_catalog=False)
            page.on("pageerror", lambda error: (errors.append(str(error)), print("PAGE ERROR", str(error), flush=True)))

            def route(request):
                u = urlsplit(request.request.url)
                if u.netloc != "127.0.0.1:8447":
                    errors.append("unexpected network: " + u.netloc)
                    request.abort()
                elif u.path == "/__settings-preview":
                    request.fulfill(status=200, content_type="text/html", body=HTML)
                elif u.path.startswith("/__mock/"):
                    requests.append((request.request.method, u.path))
                    path = u.path.removeprefix("/__mock")
                    if path == "/config/model-routes":
                        assert request.request.method == "PUT"
                        changed = request.request.post_data_json["routes"]
                        assert list(changed) == ["lifecycle_investigation"], changed
                        saved = {task: dict(task=task, **row, source="db", custom=False, warning=None) for task, row in changed.items()}
                        state["catalog"]["routes"].update(saved)
                        state.update(saved=True, fail_catalog=True)
                        value = dict(routes=saved)
                    elif path == "/config/model-catalog":
                        if state["fail_catalog"]:
                            request.fulfill(status=503, content_type="application/json", body='{"detail":{"code":"unavailable"}}')
                            return
                        value = state["catalog"]
                    elif path == "/market-data/status":
                        value = dict(exists=False)
                    elif path == "/security-lifecycle/automation":
                        value = AUTOMATION
                    elif path == "/security-lifecycle/cases":
                        value = CASES
                    elif path == "/market-data/trading-days":
                        value = COVERAGE
                    elif path == "/market-data/price-repair/operations":
                        value = dict(version=1, operations=[], total=0, offset=0, has_more=False)
                    elif path == "/schedule":
                        value = dict(sources={})
                    else:
                        errors.append("unexpected API: " + path)
                        value = {}
                    request.fulfill(status=200, content_type="application/json", body=json.dumps(value))
                else:
                    request.continue_()

            page.route("**/*", route)
            layout_checks = []

            def check_layout(mode):
                overflow = page.evaluate("""() => [...document.querySelectorAll('button,select,.model-route-card,.model-discovery-row,.lifecycle-settings')].filter(e=>e.getBoundingClientRect().width && e.scrollWidth>e.clientWidth+2).map(e=>({tag:e.tagName,cls:e.className,width:e.clientWidth,scroll:e.scrollWidth}))""")
                assert not overflow, (mode, overflow)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), mode
                layout_checks.append(dict(mode=mode, overflow=overflow))

            prefix = f"{locale}-{width}"
            page.goto(BASE + "/__settings-preview?locale=" + locale)
            panel = page.locator(".lifecycle-settings")
            expect(panel.locator('[data-automation-schedule="disabled"]')).to_be_visible()
            assert not panel.locator(".lifecycle-automation-advanced").evaluate("e=>e.open")
            panel.screenshot(path=str(OUT / f"{prefix}-lifecycle.png"))
            panel.locator(".lifecycle-automation-advanced > summary").click()
            expect(panel.locator('select')).to_have_count(2)
            panel.screenshot(path=str(OUT / f"{prefix}-lifecycle-expanded.png"))
            expect(page.get_by_text("ZETA", exact=False)).to_be_visible()
            page.screenshot(path=str(OUT / f"{prefix}-data-storage.png"), full_page=True)
            check_layout("lifecycle-and-coverage")
            page.goto(BASE + "/__settings-preview?mode=discovery&locale=" + locale)
            expect(page.locator(".model-discovery-row")).to_have_count(3)
            expect(page.locator(".model-discovery-row button")).to_have_count(0)
            page.locator("input").fill("sonnet")
            expect(page.locator(".model-discovery-row")).to_have_count(1)
            page.locator("input").fill("")
            page.screenshot(path=str(OUT / f"{prefix}-discovery.png"), full_page=True)
            check_layout("discovery")
            page.goto(BASE + "/__settings-preview?mode=models&locale=" + locale)
            effort = page.locator('[aria-labelledby="model-route-lifecycle_investigation-task-label model-route-lifecycle_investigation-effort-label"]')
            effort.select_option("xhigh")
            page.get_by_role("button", name="儲存" if locale == "zh-Hant" else "Save", exact=True).click()
            expect(page.get_by_text("已儲存，但狀態更新失敗。" if locale == "zh-Hant" else "Saved, but the status refresh failed.", exact=True)).to_be_visible()
            expect(effort).to_have_value("xhigh")
            page.screenshot(path=str(OUT / f"{prefix}-save-warning.png"), full_page=True)
            state["fail_catalog"] = False
            page.get_by_role("button", name="重新讀取儲存狀態" if locale == "zh-Hant" else "Check saved settings", exact=True).click()
            expect(page.locator(".ok-text")).to_contain_text("已儲存" if locale == "zh-Hant" else "saved")
            expect(effort).to_have_value("xhigh")
            assert len([r for r in requests if r[0] == "PUT"]) == 1, requests
            check_layout("model-save")
            assert not errors, errors
            results.append(dict(locale=locale, viewport=[width, height], requests=requests, layout_checks=layout_checks, errors=errors))
            context.close()
    browser.close()
    (OUT / "result.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))
