"""Synthetic component verification. Run in a clean user/network namespace."""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[4]
OWN = Path(__file__).resolve().parent
OUT = ROOT / "tmp/task-3-ui"
BASE = "http://127.0.0.1:8467"
NODE = "/home/hyl/.nvm/versions/node/v22.14.0/bin/node"
DATE = "2026-09-09T00:00:00Z"
EFFORTS = ["low", "medium", "high", "xhigh", "max"]
TASKS = ["card_synthesis", "card_translation", "ai_research", "lifecycle_investigation"]
OPENAI = ["gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.3-codex-spark"]
ANTHROPIC = ["claude-sonnet-5", "claude-fable-5-1"]


def receipt(provider, model, effort, auth_mode):
    return dict(provider=provider, model=model, effort=effort, auth_mode=auth_mode)


ORIGINAL = receipt("openai", "gpt-5.6-luna", "xhigh", "api_key")
TRANSLATION = receipt("openai", "gpt-5.3-codex-spark", "high", "chatgpt_oauth")
REFRESHED = receipt("anthropic", "claude-sonnet-5", "medium", "api_key")
HISTORICAL = receipt("openai", "gpt-5.4-mini", "low", "api_key")
NEXT = receipt("anthropic", "claude-sonnet-5", "xhigh", "claude_code_oauth")
ROUTES = {task: dict(task=task, provider="openai", model="gpt-5.6-luna", effort="xhigh", source="db", custom=False, warning=None) for task in TASKS}
ROUTES["card_translation"].update(provider="openai", model="gpt-5.3-codex-spark", effort="high")
ROUTES["ai_research"].update(model="gpt-5.6-sol", effort="low")
ROUTES["lifecycle_investigation"].update(provider="anthropic", model="claude-sonnet-5")


def catalog():
    def entries(provider, task):
        rows = []
        for model in OPENAI if provider == "openai" else ANTHROPIC:
            reason = "model_task_unsupported" if model.endswith("spark") and task != "card_translation" else None
            if model == "claude-fable-5-1":
                reason = "model_auth_unverified"
            rows.append(dict(id=model, label=model, status="visible", visible_to_credential=True, eligible=reason is None,
                             reason_code=reason, thinking_mode="none", effort_options=EFFORTS))
        return rows
    return dict(
        providers=["openai", "anthropic"],
        tasks=[dict(id=task, label=task, description="", default_provider=ROUTES[task]["provider"], recommended_model=ROUTES[task]["model"]) for task in TASKS],
        models=[dict(id=model, provider=p, label=model, quality="frontier", speed="medium", cost_tier="medium",
                     supports_structured_output=True, supports_tool_calling=True, effort_options=EFFORTS,
                     task_route_status="current", aliases=[], recommended_for=[], source_url="", verified_at="", notes="")
                for p, models in [("openai", OPENAI), ("anthropic", ANTHROPIC)] for model in models],
        current_model_ids=OPENAI + ANTHROPIC, retired_model_ids=["gpt-5.4-mini", "claude-fable-5"],
        effort_options={p: [dict(id=e, provider=p, label=e, description="", applies_to_card_tasks=True) for e in EFFORTS] for p in ["openai", "anthropic"]},
        routes=copy.deepcopy(ROUTES), credentials=dict(openai=[], anthropic=[]), custom_allowed=True,
        effective=dict(
            providers={"openai": dict(credential_id="fixture-openai-identity", auth_mode="chatgpt_oauth", label="Synthetic subscription", plan_type="pro"),
                       "anthropic": dict(credential_id="fixture-anthropic-identity", auth_mode="claude_code_oauth", label="Synthetic subscription")},
            tasks={task: dict(verified=[], advanced=[], cache_state="ok", discovered_at=DATE, current_provider=ROUTES[task]["provider"],
                             providers={p: dict(executable=True, reason_code=None, cache_state="ok", discovered_at=DATE, models=entries(p, task)) for p in ["openai", "anthropic"]}) for task in TASKS}))


CARD = dict(ticker="AAPL", question="What changed?", horizon=None, card_type="analysis", analysis_time=DATE,
            conclusion="Original synthetic result: demand remains steady.", primary_reasons=["Orders held steady in this fixture."],
            counter_thesis=["Demand could weaken."], key_assumptions=[], trigger_conditions=[], invalidation_conditions=[], risks=[],
            watch_list=[], market_narrative=None, divergence=None, confidence_level="medium", confidence_rationale=None,
            traceability=dict(data_sources=[], is_single_model_inference=True, claims=[], completeness=dict(news=False, fundamentals=False, technicals=False, note=None)))
TRANSLATED_CARD = dict(CARD, conclusion="Synthetic cached translation / \u7ffb\u8b6f\u7d50\u679c", primary_reasons=["Synthetic translated reason"])
DETAIL = dict(run_id=1, ticker="AAPL", status="saved", provider="openai", model="gpt-5.6-luna", generated_at=DATE,
              saved_report_id=10, question=None, horizon=None, card_type="analysis", as_of=None, card=CARD, evidence_packet=None,
              execution_receipt=ORIGINAL)
PROFILE = dict(profile=dict(enabled=False, primary_preset="balanced", risk_appetite=None, risk_capacity=None, risk_mismatch="none",
                            holding_horizon="", drawdown_tolerance_pct=None, concentration_limit_pct=None, preferred_edge=[], avoidances=[],
                            behavioral_flags=[], freeform_notes="", default_stance="off", skill_mode="off", last_reviewed_at=None, updated_at=None),
               effective_stance="off", trace=dict(profile_active=False, assistant_stance="off", skill_mode="off", suggested_skills=[], applied_skills=[]), context_preview="")
THREADS = [dict(id=name, title=title, ticker="AAPL", provider="openai", model="gpt-5.4-mini", created_at=DATE, updated_at=DATE, active_run=None)
           for name, title in [("history-a", "Historical conversation"), ("history-b", "Another conversation")]]
MESSAGE = dict(role="assistant", content="Historical synthetic answer", provider="openai", model="gpt-5.4-mini", effort="default",
               tools_used=[], tool_calls=[], token_usage=None, tickers=None, elapsed_seconds=2, is_error=False, created_at=DATE, personalization=None)
LIMITS = dict(model_submissions=24, web_actions=24, source_reads=32, http_requests=64, local_queries=16, deadline_seconds=900,
              model_timeout_seconds=300, api_output_tokens=8192, retained_source_mib=256, output_control="provider", search_enforcement="enforced")
TARGET = dict(ticker="TA", issuer_name="Synthetic issuer", security_class="common stock", venue="NASDAQ", issuer_cik=None,
              composite_figi=None, identity_status="needs_lookup", as_of="2026-09-09")
PREFLIGHT = dict(version=2, ticker="TA", available=True, reason=None, preflight_sha256="a" * 64, target=TARGET, execution=NEXT,
                 credential_label="Synthetic subscription", limits=LIMITS)
LIFECYCLE = dict(version=2, run_id="synthetic-investigation", ticker="TA", status="succeeded", phase="finished", created_at=DATE,
                 finished_at=DATE, cancel_requested=False, failure_code=None, stop_reason=None, target=TARGET, execution=HISTORICAL,
                 stats=dict(model_submissions=2, web_actions=1, sources=1, http_requests=1, source_reads=1, local_queries=1,
                            retained_source_bytes=100, elapsed_seconds=12, input_tokens=400, output_tokens=100),
                 finding=dict(version=2, source_ticker="TA", issuer_name="Synthetic issuer", security_class="common stock", venue="NASDAQ",
                              event_kind="active_listing", timing="completed", successor_ticker=None, effective_date=None,
                              summary="Previous synthetic result: listing remains active.", contradictions=[], unresolved_conditions=[], limitations=[], citations=[]),
                 action=None, block_reasons=[], passages=[], gaps=[], steps=[])

HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Task 3 synthetic verification</title></head><body><div id="root"></div>
<script type="module">import RefreshRuntime from '/@react-refresh'; RefreshRuntime.injectIntoGlobalHook(window); window.$RefreshReg$=()=>{}; window.$RefreshSig$=()=>type=>type; window.__vite_plugin_react_preamble_installed__=true;</script>
<script type="module" src="/@fs/ENTRY"></script></body></html>""".replace("ENTRY", str(OWN / "task-3-preview.tsx"))


def verify(browser, locale, width, height):
    context = browser.new_context(viewport=dict(width=width, height=height), service_workers="block")
    context.add_init_script("window.arkscope={apiBase:" + json.dumps(BASE + "/__mock") + "}; window.requestIdleCallback=()=>1; window.cancelIdleCallback=()=>{}; "
                            "sessionStorage.setItem('arkscope.aiResearch.activeThreadId','history-a');"
                            "localStorage.setItem('arkscope.aiResearch.explicitSelection.v1', JSON.stringify({version:1,tuple:{provider:'openai',model:'gpt-5.6-luna',effort:'max'}}));")
    page = context.new_page()
    page.set_default_timeout(8000)
    errors, requests, screenshots, layouts, pending = [], [], [], [], []
    state = dict(catalog=catalog(), translation="cached", detail="receipt", runs={})
    page.on("pageerror", lambda error: errors.append(str(error)))

    def route(request):
        url = urlsplit(request.request.url)
        if url.netloc != "127.0.0.1:8467":
            errors.append("external request denied: " + url.netloc)
            request.abort()
            return
        if url.path == "/__task3":
            request.fulfill(status=200, content_type="text/html", body=HTML)
            return
        if not url.path.startswith("/__mock/"):
            if any(part in url.path for part in [".env", "/config/", ".db", "credentials"]):
                errors.append("private path denied: " + url.path)
                request.abort()
            else:
                request.continue_()
            return
        path, method = url.path.removeprefix("/__mock"), request.request.method
        body = request.request.post_data_json if request.request.post_data else None
        requests.append(dict(path=path, method=method, body=body))
        status = 200
        if path == "/config/model-catalog":
            value = state["catalog"]
        elif path == "/config/model-routes" and method == "PUT":
            assert set(body["routes"]) == {"ai_research"}, body
            changes = {task: dict(row, task=task, source="db", custom=False, warning=None) for task, row in body["routes"].items()}
            state["catalog"]["routes"].update(changes)
            value = dict(routes=changes)
        elif path == "/query/providers":
            value = dict(providers={"openai": dict(available=True, model="gpt-5.6-luna"),
                                    "anthropic": dict(available=True, model="claude-fable-5-1")})
        elif path == "/profile/investor":
            value = PROFILE
        elif path == "/analysis/cards":
            value = dict(cards=[dict(DETAIL, conclusion=CARD["conclusion"], confidence_level="medium")])
        elif path == "/analysis/card/AAPL":
            assert "provider" not in body and "model" not in body and "effort" not in body, body
            value = dict(DETAIL, status="generated")
        elif path == "/analysis/cards/1":
            value = copy.deepcopy(DETAIL)
            if state["detail"] == "legacy":
                del value["execution_receipt"]
                value["model"] = "gpt-5.4-mini"
            elif state["detail"] == "malformed":
                value["execution_receipt"] = dict(ORIGINAL, credential_id="fixture-private-identity")
        elif path == "/analysis/cards/1/save":
            value = dict(run_id=1, status="saved", saved_report_id=10)
        elif path == "/analysis/cards/1/translate":
            assert body == dict(lang="zh-Hant") or body == dict(lang="zh-Hant", refresh=True), body
            if body.get("refresh") and state["translation"] == "pending":
                pending.append(request)
                return
            value = dict(run_id=1, lang="zh-Hant", card=TRANSLATED_CARD, cached=True, execution_receipt=TRANSLATION)
            if body.get("refresh"):
                value.update(card=dict(TRANSLATED_CARD, conclusion="Synthetic refreshed translation"), cached=False, execution_receipt=REFRESHED)
            elif state["translation"] == "legacy":
                value["execution_receipt"] = receipt(None, None, None, None)
            elif state["translation"] == "no_op":
                value.update(card=dict(ticker="AAPL"), cached=False, no_op=True, execution_receipt=None)
        elif path == "/research/threads":
            value = dict(threads=THREADS, total=2, limit=50, offset=0)
        elif path.endswith("/messages") and path.startswith("/research/threads/"):
            value = dict(thread_id=path.split("/")[3], messages=[MESSAGE])
        elif path.startswith("/research/threads/") and path.endswith("/selection"):
            errors.append("historical selection used as authority")
            value = dict(provider="openai", model="gpt-5.4-mini", effort="default")
        elif path.startswith("/research/threads/"):
            value = dict(thread=next(row for row in THREADS if row["id"] == path.split("/")[3]))
        elif path == "/research/runs" and method == "POST":
            run_id = "synthetic-run-" + str(len(state["runs"]) + 1)
            completed_at = datetime.now(timezone.utc).isoformat()
            run = dict(id=run_id, thread_id=body["thread_id"], question=body["question"], ticker=body.get("ticker"), status="succeeded",
                       provider=body["provider"], model=body["model"], effort=body["effort"], auth_mode=state["catalog"]["effective"]["providers"][body["provider"]]["auth_mode"],
                       credential_id="fixture-run-identity", started_at=completed_at, completed_at=completed_at,
                       created_at=completed_at, updated_at=completed_at, error=None, token_usage=None)
            state["runs"][run_id] = run
            value = dict(run=run)
        elif path.startswith("/research/runs/"):
            run = state["runs"][path.split("/")[3]]
            value = dict(run=run)
            if path.endswith("/events"):
                value.update(events=[dict(run_id=run["id"], seq=1, type="done", created_at=run["completed_at"],
                                          data=dict(answer="Synthetic completed answer: " + run["question"],
                                                    provider=run["provider"], model=run["model"], tools_used=[], token_usage=None))], has_more=False)
        elif path == "/security-lifecycle/investigations/targets":
            value = dict(version=2, targets=[dict(ticker="TA")])
        elif path.endswith("/preflight"):
            value = PREFLIGHT
        elif path.endswith("/latest"):
            value = LIFECYCLE
        elif path.endswith("/providers"):
            value = dict(version=2, ticker="TA", decision=None, observations=dict(observed_at=None, listings=[], gaps=[]))
        elif path == "/security-lifecycle/investigations/actions":
            value = dict(version=2, actions=[])
        elif path == "/security-lifecycle/transition-activity":
            value = dict(items=[], count=0, unacknowledged_count=0)
        else:
            errors.append("unexpected synthetic API: " + method + " " + path)
            status, value = 500, dict(detail=dict(code="unexpected_fixture_request"))
        request.fulfill(status=status, content_type="application/json", body=json.dumps(value))

    page.route("**/*", route)

    def shot(name):
        path = OUT / f"{locale}-{width}-{name}.png"
        page.screenshot(path=str(path), full_page=True)
        screenshots.append(str(path))
        overflow = page.evaluate("""() => [...document.querySelectorAll('button,select,.execution-source,.research-bubble-meta,.ui-page-header-context,.cardview-head')]
          .filter(e=>e.getBoundingClientRect().width && e.scrollWidth>e.clientWidth+2)
          .map(e=>({tag:e.tagName,cls:e.className,width:e.clientWidth,scroll:e.scrollWidth}))""")
        assert not overflow, (name, overflow)
        narrow_prose = page.evaluate("""() => [...document.querySelectorAll('.ui-inline-alert-detail')]
          .filter(e=>e.getBoundingClientRect().width && e.clientWidth<Math.min(180,e.parentElement.clientWidth/2))
          .map(e=>({cls:e.className,width:e.clientWidth,height:e.clientHeight}))""")
        assert not narrow_prose, (name, narrow_prose)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), name
        assert not page.get_by_text("fixture-private-identity").count()
        assert not page.get_by_text("fixture-openai-identity").count()
        assert not page.get_by_text("fixture-run-identity").count()
        if page.locator(".research-providerbar").count():
            provider_text = page.locator(".research-providerbar").inner_text()
            assert not any(model in provider_text for model in OPENAI + ANTHROPIC), provider_text
            assert page.locator(".research-bubble-meta").evaluate_all("rows => rows.every(e=> !/-\\d+(\\.\\d+)?s/.test(e.textContent))")
        layouts.append(dict(view=name, overflow=overflow, narrow_prose=narrow_prose))
        print(f"{locale}-{width}: {name}", flush=True)

    def nav(name):
        page.get_by_role("navigation", name="Fixture views").get_by_role("button", name=name, exact=True).click()

    def translations():
        return [row for row in requests if row["path"].endswith("/translate")]

    page.goto(BASE + "/__task3?locale=" + locale)
    expect(page.locator(".aicard-recent li")).to_have_count(1)
    assert not translations()
    page.get_by_role("button", name="Generate Card" if locale == "en" else "\u7522\u751f\u5361\u7247").click()
    expect(page.locator('[data-execution-source="original"]')).to_contain_text("openai \u00b7 gpt-5.6-luna")
    shot("card-original")
    page.get_by_role("button", name="\u7e41\u4e2d", exact=True).click()
    expect(page.locator(".cardview-concl")).to_have_text(TRANSLATED_CARD["conclusion"])
    expect(page.locator('[data-execution-source="translation"]')).to_contain_text("gpt-5.3-codex-spark")
    shot("card-cached")
    page.get_by_role("button", name="EN", exact=True).click()
    page.get_by_role("button", name="\u7e41\u4e2d", exact=True).click()
    assert len(translations()) == 1 and "refresh" not in translations()[0]["body"]
    state["translation"] = "pending"
    page.get_by_role("button", name="Retranslate" if locale == "en" else "\u91cd\u65b0\u7ffb\u8b6f", exact=True).click()
    expect(page.locator('.cardview button[aria-busy="true"]')).to_be_disabled()
    expect(page.locator(".cardview-concl")).to_have_text(TRANSLATED_CARD["conclusion"])
    expect(page.locator('[data-execution-source="translation"]')).to_contain_text("gpt-5.3-codex-spark")
    shot("card-refresh-pending")
    assert len(pending) == 1
    pending.pop().fulfill(status=502, content_type="application/json", body=json.dumps(dict(detail=dict(code="translation_auth_rejected", retryable=False))))
    expect(page.locator('[role="alert"]')).to_be_visible()
    expect(page.locator(".cardview-concl")).to_have_text(TRANSLATED_CARD["conclusion"])
    expect(page.locator('[data-execution-source="translation"]')).to_contain_text("gpt-5.3-codex-spark")
    shot("card-refresh-failed")
    state["translation"] = "success"
    page.get_by_role("button", name="Retry" if locale == "en" else "\u91cd\u8a66", exact=True).click()
    expect(page.locator(".cardview-concl")).to_have_text("Synthetic refreshed translation")
    expect(page.locator('[data-execution-source="translation"]')).to_contain_text("anthropic \u00b7 claude-sonnet-5")
    assert translations()[-1]["body"] == dict(lang="zh-Hant", refresh=True)
    shot("card-refreshed")

    state.update(detail="legacy", translation="legacy")
    page.get_by_role("button", name="Saved card", exact=True).click()
    modal = page.get_by_role("dialog")
    expect(modal.locator('[data-execution-source="original"]')).to_contain_text("gpt-5.4-mini")
    assert modal.locator('[data-execution-source="original"]').inner_text().count("Unknown" if locale == "en" else "\u672a\u77e5") == 2
    modal.get_by_role("button", name="\u7e41\u4e2d", exact=True).click()
    expect(modal.locator('[data-execution-source="translation"]')).to_be_visible()
    assert modal.locator('[data-execution-source="translation"]').inner_text().count("Unknown" if locale == "en" else "\u672a\u77e5") == 4
    shot("card-legacy-saved")
    state["translation"] = "pending"
    modal.get_by_role("button", name="Retranslate" if locale == "en" else "\u91cd\u65b0\u7ffb\u8b6f", exact=True).click()
    expect(modal.locator('button[aria-busy="true"]')).to_be_disabled()
    assert len(pending) == 1
    pending.pop().fulfill(status=502, content_type="application/json", body=json.dumps(dict(detail=dict(code="translation_auth_rejected", retryable=False))))
    expect(modal.get_by_role("alert")).to_be_visible()
    expect(modal.locator(".cardview-concl")).to_have_text(TRANSLATED_CARD["conclusion"])
    assert modal.locator('[data-execution-source="translation"]').inner_text().count("Unknown" if locale == "en" else "\u672a\u77e5") == 4
    shot("card-saved-refresh-failed")
    modal.get_by_role("button", name="Close" if locale == "en" else "\u95dc\u9589").click()
    state["detail"] = "malformed"
    page.get_by_role("button", name="Saved card", exact=True).click()
    expect(page.get_by_role("dialog").get_by_role("alert")).to_be_visible()
    assert not page.get_by_role("dialog").locator(".cardview").count()
    shot("card-malformed-safe-error")
    page.get_by_role("dialog").get_by_role("button", name="Close" if locale == "en" else "\u95dc\u9589").click()
    state.update(detail="receipt", translation="no_op")
    page.get_by_role("button", name="Saved card", exact=True).click()
    modal = page.get_by_role("dialog")
    modal.get_by_role("button", name="\u7e41\u4e2d", exact=True).click()
    expect(modal.get_by_role("status")).to_have_text("No text to translate" if locale == "en" else "\u6c92\u6709\u53ef\u7ffb\u8b6f\u7684\u6587\u5b57")
    expect(modal.locator(".cardview-concl")).to_have_text(CARD["conclusion"])
    shot("card-no-op")
    modal.get_by_role("button", name="Close" if locale == "en" else "\u95dc\u9589").click()

    nav("research")
    model = page.locator(".research-pickerbar select").nth(0)
    effort = page.locator(".research-pickerbar select").nth(1)
    expect(page.get_by_text("Historical synthetic answer", exact=True)).to_be_visible()
    expect(model).to_have_value("gpt-5.6-sol")
    expect(effort).to_have_value("low")
    expect(page.locator(".research-bubble-meta").first).to_contain_text("gpt-5.4-mini")
    shot("research-openai-settings")
    nav("settings")
    provider = page.locator('[aria-labelledby="model-route-ai_research-task-label model-route-ai_research-provider-label"]')
    expect(provider).to_be_visible()
    provider.get_by_role("button", name="Anthropic", exact=True).click()
    page.locator('[aria-labelledby="model-route-ai_research-task-label model-route-ai_research-model-label"]').select_option("claude-sonnet-5")
    page.locator('[aria-labelledby="model-route-ai_research-task-label model-route-ai_research-effort-label"]').select_option("medium")
    page.get_by_role("button", name="Save" if locale == "en" else "\u5132\u5b58", exact=True).click()
    page.wait_for_function("document.querySelector('[aria-labelledby=\"model-route-ai_research-task-label model-route-ai_research-effort-label\"]').value === 'medium'")
    assert state["catalog"]["routes"]["ai_research"]["provider"] == "anthropic"
    assert state["catalog"]["routes"]["ai_research"]["effort"] == "medium"
    shot("settings-research-route")
    nav("research")
    expect(model).to_have_value("claude-sonnet-5")
    expect(effort).to_have_value("medium")
    expect(page.locator(".research-bubble-meta").first).to_contain_text("gpt-5.4-mini")
    page.locator("textarea").fill("Next historical-conversation turn")
    page.get_by_role("button", name="Send" if locale == "en" else "\u9001\u51fa", exact=True).click()
    expect(page.locator("textarea")).to_have_value("")
    page.wait_for_timeout(100)
    shot("research-anthropic-settings")
    page.get_by_role("button", name="New Research" if locale == "en" else "\u65b0\u7814\u7a76", exact=True).click()
    expect(model).to_have_value("claude-sonnet-5")
    page.locator(".research-providerbar button").filter(has_text="OpenAI").click()
    model.select_option("gpt-5.6-sol")
    expect(effort).to_have_value("")
    effort.select_option("high")
    page.locator("textarea").fill("Explicit first turn")
    page.get_by_role("button", name="Send" if locale == "en" else "\u9001\u51fa", exact=True).click()
    expect(page.locator("textarea")).to_have_value("")
    page.wait_for_timeout(100)
    expect(model).to_have_value("gpt-5.6-sol")
    expect(effort).to_have_value("high")
    page.locator("textarea").fill("Explicit second turn")
    page.get_by_role("button", name="Send" if locale == "en" else "\u9001\u51fa", exact=True).click()
    page.wait_for_timeout(100)
    expect(page.get_by_text("Synthetic completed answer: Explicit second turn", exact=True)).to_be_visible()
    runs = [row["body"] for row in requests if row["path"] == "/research/runs" and row["method"] == "POST"]
    assert len(runs) == 3, runs
    assert (runs[0]["provider"], runs[0]["model"], runs[0]["effort"]) == ("anthropic", "claude-sonnet-5", "medium")
    assert runs[1]["thread_id"] == runs[2]["thread_id"]
    for run in runs[1:]:
        assert (run["provider"], run["model"], run["effort"]) == ("openai", "gpt-5.6-sol", "high")
    shot("research-current-override")
    page.get_by_role("button", name="History" if locale == "en" else "\u6b77\u53f2", exact=True).click()
    page.locator(".research-history-select").filter(has_text="Another conversation").click()
    expect(model).to_have_value("claude-sonnet-5")
    expect(effort).to_have_value("medium")
    shot("research-open-other-reset")

    nav("lifecycle")
    expect(page.locator('[data-execution-source="previous"]')).to_contain_text("openai \u00b7 gpt-5.4-mini")
    expect(page.get_by_text(LIFECYCLE["finding"]["summary"], exact=True)).to_be_visible()
    shot("lifecycle-previous")
    page.get_by_role("button", name="Investigate again" if locale == "en" else "\u91cd\u65b0\u8abf\u67e5", exact=True).click()
    next_source = page.get_by_role("dialog").locator('[data-execution-source="next"]')
    expect(next_source).to_contain_text("anthropic \u00b7 claude-sonnet-5")
    expect(next_source).to_contain_text("xhigh")
    expect(next_source).to_contain_text("Claude subscription sign-in" if locale == "en" else "Claude \u8a02\u95b1\u767b\u5165")
    shot("lifecycle-next-confirmation")
    assert not [row for row in requests if row["method"] == "POST" and row["path"].startswith("/security-lifecycle/")]
    assert not errors, errors
    context.close()
    return dict(locale=locale, width=width, screenshots=screenshots, layouts=layouts, requests=requests, errors=errors)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # Only loopback is enabled in the caller's isolated network namespace.
    subprocess.run(["/usr/sbin/ip", "link", "set", "lo", "up"], check=True)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 8467))
    with (OUT / "vite.log").open("w") as log:
        server = subprocess.Popen([NODE, str(OWN / "task-3-vite.mjs")], cwd=ROOT / "apps/arkscope-web", stdout=log, stderr=log, start_new_session=True)
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("isolated Vite exited; inspect " + str(OUT / "vite.log"))
                try:
                    with socket.create_connection(("127.0.0.1", 8467), timeout=0.1):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("isolated Vite did not start")
            with sync_playwright() as pw:
                browser = pw.chromium.launch(args=["--disable-extensions"])
                try:
                    results = [verify(browser, locale, width, height) for locale in ["en", "zh-Hant"] for width, height in [(1280, 960), (390, 844)]]
                    (OUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
                    print(json.dumps(dict(status="passed", contexts=len(results), screenshots=sum(len(row["screenshots"]) for row in results), output=str(OUT))))
                except Exception:
                    for context in browser.contexts:
                        for page in context.pages:
                            page.screenshot(path=str(OUT / "failure.png"), full_page=True)
                            print(page.locator("body").inner_text()[:4000], flush=True)
                    raise
                finally:
                    browser.close()
        finally:
            os.killpg(server.pid, signal.SIGTERM)
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(server.pid, signal.SIGKILL)
                server.wait(timeout=10)


if __name__ == "__main__":
    main()
