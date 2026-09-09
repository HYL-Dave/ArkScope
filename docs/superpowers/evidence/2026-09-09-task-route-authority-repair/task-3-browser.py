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
OUT = ROOT / os.environ.get("ARKSCOPE_UI_EVIDENCE_DIR", "tmp/task-3-ui")
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


def verify(browser, locale, width, height, shell_provider=None, cold_case=None):
    context = browser.new_context(viewport=dict(width=width, height=height), service_workers="block")
    context.add_init_script("window.arkscope={apiBase:" + json.dumps(BASE + "/__mock") + "}; window.requestIdleCallback=()=>1; window.cancelIdleCallback=()=>{}; "
                            "sessionStorage.setItem('arkscope.aiResearch.activeThreadId','history-a');"
                            "localStorage.setItem('arkscope.settings.activeGroup.v1','models');"
                            "localStorage.setItem('arkscope.aiResearch.explicitSelection.v1', JSON.stringify({version:1,tuple:{provider:'openai',model:'gpt-5.6-luna',effort:'max'}}));")
    page = context.new_page()
    page.set_default_timeout(8000)
    errors, requests, screenshots, layouts, pending = [], [], [], [], []
    state = dict(catalog=catalog(), translation="cached", detail="receipt", runs={}, threads=copy.deepcopy(THREADS))
    cold_messages = {"history-a": [copy.deepcopy(MESSAGE)], "history-b": []}
    cold_pending = []
    held = {"list", "messages"} if cold_case in {"complete", "incomplete", "new"} else set()
    failure = cold_case if cold_case and cold_case.startswith("failed-") else None
    if shell_provider:
        state["catalog"]["routes"]["ai_research"].update(
            provider=shell_provider,
            model="gpt-5.6-luna" if shell_provider == "openai" else "claude-sonnet-5",
            effort="xhigh" if shell_provider == "openai" else "medium",
        )
    if cold_case == "incomplete":
        next_provider = "anthropic" if shell_provider == "openai" else "openai"
        entries = state["catalog"]["effective"]["tasks"]["ai_research"]["providers"][next_provider]["models"]
        entries.append(dict(entries[0], id="synthetic-custom-model", label="synthetic-custom-model"))
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
        phase = "list" if path == "/research/threads" else "messages" if path == "/research/threads/history-a/messages" else None
        if phase in held:
            cold_pending.append((phase, request))
            return
        failed_path = {
            "failed-list": "/research/threads", "failed-detail": "/research/threads/history-a",
            "failed-messages": "/research/threads/history-a/messages", "failed-missing": "/research/threads/history-a",
        }.get(failure)
        if failed_path == path:
            detail = "thread not found" if failure == "failed-missing" else dict(code="synthetic_restoration_failure")
            request.fulfill(status=404 if failure == "failed-missing" else 500,
                            content_type="application/json", body=json.dumps(dict(detail=detail)))
            return
        status = 200
        if path == "/status":
            value = dict(status="ok", timestamp=DATE, tools_registered=0, tool_categories={}, data_sources={})
        elif path == "/config/runtime":
            value = dict(
                anthropic=dict(model="claude-sonnet-5", model_advanced="claude-fable-5-1", effort=None, thinking=False, key_set=True, credentials=[]),
                openai=dict(model="gpt-5.6-luna", model_advanced="gpt-5.6-sol", reasoning_effort="xhigh", key_set=True, credentials=[]),
                **{task: row for task, row in state["catalog"]["routes"].items()},
                research_runtime=dict(max_tool_calls=60, session_timeout_s=900, per_tool_timeout_s=45, source="db", db_saved=True, warning=None),
                data_keys={},
            )
        elif path == "/profile/universe":
            value = dict(rows=[], as_of=DATE)
        elif path == "/profile/lists":
            value = dict(lists=[])
        elif path == "/config/model-catalog":
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
            rows = state["threads"][1:] if failure in {"failed-detail", "failed-missing"} else state["threads"]
            value = dict(threads=rows, total=len(rows), limit=50, offset=0)
        elif path.endswith("/messages") and path.startswith("/research/threads/"):
            thread_id = path.split("/")[3]
            value = dict(thread_id=thread_id, messages=cold_messages.get(thread_id, []) if cold_case else [MESSAGE])
        elif path.startswith("/research/threads/") and path.endswith("/selection"):
            errors.append("historical selection used as authority")
            value = dict(provider="openai", model="gpt-5.4-mini", effort="default")
        elif path.startswith("/research/threads/"):
            value = dict(thread=next(row for row in state["threads"] if row["id"] == path.split("/")[3]))
        elif path == "/research/runs" and method == "POST":
            run_id = "synthetic-run-" + str(len(state["runs"]) + 1)
            completed_at = datetime.now(timezone.utc).isoformat()
            run = dict(id=run_id, thread_id=body["thread_id"], question=body["question"], ticker=body.get("ticker"), status="succeeded",
                       provider=body["provider"], model=body["model"], effort=body["effort"], auth_mode=state["catalog"]["effective"]["providers"][body["provider"]]["auth_mode"],
                       credential_id="fixture-run-identity", started_at=completed_at, completed_at=completed_at,
                       created_at=completed_at, updated_at=completed_at, error=None, token_usage=None)
            state["runs"][run_id] = run
            if not any(row["id"] == run["thread_id"] for row in state["threads"]):
                state["threads"].append(dict(THREADS[0], id=run["thread_id"], title="Created conversation"))
            if cold_case:
                cold_messages.setdefault(run["thread_id"], []).extend([
                    dict(MESSAGE, role="user", content=run["question"], provider=run["provider"], model=run["model"], effort=run["effort"], elapsed_seconds=None),
                    dict(MESSAGE, content="Synthetic completed answer: " + run["question"], provider=run["provider"], model=run["model"], effort=run["effort"], elapsed_seconds=0),
                ])
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

    def shot(name, answer=None):
        answer_visibility = None
        if answer:
            expect(page.locator(".research-run-progress")).to_have_attribute("data-stage", "succeeded")
            bubble = page.locator(".research-bubble.assistant").filter(has=page.get_by_text("Synthetic completed answer: " + answer, exact=True))
            expect(bubble).to_have_count(1)
            before_scroll = page.locator(".research-messages").evaluate("e => e.scrollTop")
            bubble.evaluate("e => e.scrollIntoView({block: 'start'})")
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
            answer_visibility = bubble.evaluate("""e => {
              const panel = e.closest('.research-messages'), viewport = panel.getBoundingClientRect();
              const bounds = selector => {
                const box = e.querySelector(selector).getBoundingClientRect();
                return {top: box.top, bottom: box.bottom, left: box.left, right: box.right};
              };
              return {scrollTop: panel.scrollTop, viewport: {top: Math.max(0, viewport.top),
                bottom: Math.min(innerHeight, viewport.bottom), left: Math.max(0, viewport.left),
                right: Math.min(innerWidth, viewport.right)}, meta: bounds('.research-bubble-meta'),
                body: bounds('.research-bubble-body')};
            }""")
            answer_visibility["before_scroll"] = before_scroll
            viewport = answer_visibility["viewport"]
            for part in ["meta", "body"]:
                box = answer_visibility[part]
                assert box["top"] >= viewport["top"] - 1 and box["bottom"] <= viewport["bottom"] + 1, (name, answer_visibility)
                assert box["left"] >= viewport["left"] - 1 and box["right"] <= viewport["right"] + 1, (name, answer_visibility)
        if cold_case:
            name = f"cold-{cold_case}-{name}"
        if shell_provider:
            name = f"shell-{shell_provider}-{name}"
            assert page.locator(".app-shell-layout").evaluate("e => getComputedStyle(e).display") == "grid"
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
        layouts.append(dict(view=name, overflow=overflow, narrow_prose=narrow_prose, answer_visibility=answer_visibility))
        print(f"{locale}-{width}: {name}", flush=True)

    def nav(name):
        page.get_by_role("navigation", name="Fixture views").get_by_role("button", name=name, exact=True).click()

    def translations():
        return [row for row in requests if row["path"].endswith("/translate")]

    if shell_provider:
        def shell_nav(name):
            if not page.locator(".app-shell-nav-item:visible").count():
                page.get_by_role("button", name="Open navigation" if locale == "en" else "\u958b\u555f\u5c0e\u89bd", exact=True).click()
            labels = {"Home": "\u5de5\u4f5c\u53f0", "Settings": "\u8a2d\u5b9a", "Research": "AI \u7814\u7a76"}
            label = ("AI Research" if name == "Research" else name) if locale == "en" else labels[name]
            page.locator(".app-shell-nav-item:visible").filter(has_text=label).click()

        def round_trip(destination):
            old = page.locator("textarea").element_handle()
            shell_nav(destination)
            expect(page.locator("textarea")).to_have_count(0)
            assert old.evaluate("e => !e.isConnected")
            shell_nav("Research")

        def send(question):
            page.locator("textarea").fill(question)
            page.get_by_role("button", name="Send" if locale == "en" else "\u9001\u51fa", exact=True).click()
            expect(page.get_by_text("Synthetic completed answer: " + question, exact=True)).to_be_visible()

        def captions(provider=None):
            muted = page.locator(".research-pickerbar > span.muted")
            if provider is None:
                expect(muted).to_have_count(0)
                required = "Choose an effort for this provider and model before submitting." if locale == "en" else "\u8acb\u5148\u70ba\u9019\u500b provider \u8207\u6a21\u578b\u9078\u64c7 effort\uff0c\u624d\u80fd\u9001\u51fa\u3002"
                expect(page.locator(".research-pickerbar > span.warn-text")).to_have_text([required])
            else:
                auth = "ChatGPT" if provider == "openai" else "Claude"
                auth += " subscription sign-in" if locale == "en" else " \u8a02\u95b1\u767b\u5165"
                quota = "Uses subscription quota, not API billing" if locale == "en" else "\u4f7f\u7528\u8a02\u95b1\u984d\u5ea6\uff0c\u975e API \u5e33\u55ae"
                expect(muted).to_have_text([auth, quota])

        if cold_case:
            def runs():
                return [row["body"] for row in requests if row["path"] == "/research/runs" and row["method"] == "POST"]

            def release(phase):
                held.remove(phase)
                waiting = [item for item in cold_pending if item[0] == phase]
                assert waiting, (phase, requests)
                cold_pending[:] = [item for item in cold_pending if item[0] != phase]
                value = (dict(threads=state["threads"], total=len(state["threads"]), limit=50, offset=0)
                         if phase == "list" else dict(thread_id="history-a", messages=cold_messages["history-a"]))
                for _, request in waiting:
                    request.fulfill(status=200, content_type="application/json", body=json.dumps(value))

            page.goto(BASE + "/__task3?view=shell&cold=1&locale=" + locale)
            shell_nav("Research")
            model = page.locator(".research-pickerbar select").nth(0)
            effort = page.locator(".research-pickerbar select").nth(1)
            submit = page.get_by_role("button", name="Send" if locale == "en" else "\u9001\u51fa", exact=True)
            default = state["catalog"]["routes"]["ai_research"]
            expect(model).to_have_value(default["model"])
            next_provider = "anthropic" if shell_provider == "openai" else "openai"
            next_model = "claude-sonnet-5" if next_provider == "anthropic" else "gpt-5.6-sol"
            if cold_case == "incomplete":
                next_model = "synthetic-custom-model"
            page.locator(".research-providerbar button").filter(has_text="Anthropic" if next_provider == "anthropic" else "OpenAI").click()
            model.select_option(next_model)
            if cold_case != "incomplete":
                effort.select_option("low")
            draft = "Cold restoration draft"
            page.locator("textarea").fill(draft)
            assert page.evaluate("sessionStorage.getItem('arkscope.aiResearch.activeThreadId')") == "history-a"
            expect(submit).to_be_disabled()
            assert not runs()

            if failure:
                error_key = "activeThreadLoadFailed" if failure == "failed-messages" else "threadNotFound" if failure == "failed-missing" else "threadLoadFailed"
                labels = {
                    "activeThreadLoadFailed": ("This Research conversation could not be loaded. Select it again from History.", "\u7121\u6cd5\u8f09\u5165\u9019\u500b\u7814\u7a76\u5c0d\u8a71\uff0c\u8acb\u5f9e\u6b77\u53f2\u91cd\u65b0\u9078\u53d6\u3002"),
                    "threadNotFound": ("The requested Research conversation was not found and may have been deleted.", "\u627e\u4e0d\u5230\u6307\u5b9a\u7684\u7814\u7a76\u5c0d\u8a71\uff0c\u53ef\u80fd\u5df2\u88ab\u522a\u9664\u3002"),
                    "threadLoadFailed": ("The requested Research conversation could not be loaded. Try again later.", "\u66ab\u6642\u7121\u6cd5\u8f09\u5165\u6307\u5b9a\u7684\u7814\u7a76\u5c0d\u8a71\uff0c\u8acb\u7a0d\u5f8c\u518d\u8a66\u3002"),
                }
                expect(page.locator(".research-convo > .error-text")).to_have_text(labels[error_key][locale != "en"])
                expect(page.locator(".research-conversation-title")).to_have_text(
                    "Historical conversation" if failure == "failed-messages" else
                    "Could not load Research history" if locale == "en" else "\u7121\u6cd5\u8f09\u5165\u7814\u7a76\u6b77\u53f2")
                captions(next_provider)
                shot("blocked")
                failure = None
                page.get_by_role("button", name="Retry" if locale == "en" else "\u91cd\u8a66", exact=True).click()
                expect(page.locator(".research-convo > .error-text")).to_have_count(0)
            else:
                for destination in ["Home", "Settings"]:
                    round_trip(destination)
                    expect(model).to_have_value(next_model)
                    expect(effort).to_have_value("" if cold_case == "incomplete" else "low")
                    expect(page.locator("textarea")).to_have_value(draft)
                    expect(page.locator(".research-conversation-title")).to_have_text(
                        "Loading Research history" if locale == "en" else "\u8f09\u5165\u7814\u7a76\u6b77\u53f2")
                    expect(submit).to_be_disabled()
                    assert not runs()
                    captions(None if cold_case == "incomplete" else next_provider)
                    shot("list-pending-after-" + destination.lower())
                release("list")
                expect(page.locator(".research-conversation-title")).to_have_text("Historical conversation")
                expect(page.get_by_text(MESSAGE["content"], exact=True)).to_have_count(0)
                expect(submit).to_be_disabled()
                assert not runs()
                shot("messages-pending")
                if cold_case == "new":
                    page.get_by_role("button", name="New Research" if locale == "en" else "\u65b0\u7814\u7a76", exact=True).click()
                release("messages")

            if cold_case == "new":
                page.wait_for_timeout(100)
                expect(page.locator(".research-conversation-title")).to_have_text("New conversation" if locale == "en" else "\u65b0\u5c0d\u8a71")
                expect(page.get_by_text(MESSAGE["content"], exact=True)).to_have_count(0)
                assert page.evaluate("sessionStorage.getItem('arkscope.aiResearch.activeThreadId')") is None
                next_provider, next_model, next_effort = (default[key] for key in ("provider", "model", "effort"))
                expect(model).to_have_value(next_model)
                expect(effort).to_have_value(next_effort)
            else:
                next_effort = "low"
                expect(page.get_by_text(MESSAGE["content"], exact=True)).to_be_visible()
                expect(page.locator(".research-bubble-meta").first).to_contain_text("openai/gpt-5.4-mini \u00b7 default")
                if cold_case == "incomplete":
                    expect(submit).to_be_disabled()
                    captions()
                    shot("restored-effort-required")
                    effort.select_option(next_effort)
            captions(next_provider)
            expect(page.locator("textarea")).to_have_value(draft)
            expect(submit).to_be_enabled()
            assert not runs()
            submit.click()
            expect(page.get_by_text("Synthetic completed answer: " + draft, exact=True)).to_be_visible()
            assert len(runs()) == 1
            expected_id = runs()[0]["thread_id"] if cold_case == "new" else "history-a"
            if cold_case == "new":
                assert expected_id not in {"history-a", "history-b"}
            assert {key: runs()[0][key] for key in ("thread_id", "question", "provider", "model", "effort")} == dict(
                thread_id=expected_id, question=draft, provider=next_provider, model=next_model, effort=next_effort,
            )
            shot("completed-exact-context", draft)
            if cold_case == "new":
                round_trip("Settings")
                expect(page.get_by_text("Synthetic completed answer: " + draft, exact=True)).to_be_visible()
                expect(page.get_by_text(MESSAGE["content"], exact=True)).to_have_count(0)
                send("After new accepted ID")
                assert len(runs()) == 2 and runs()[1]["thread_id"] == expected_id
                assert (runs()[1]["provider"], runs()[1]["model"], runs()[1]["effort"]) == (next_provider, next_model, next_effort)
                shot("new-first-id-retained", "After new accepted ID")
            assert not cold_pending and not errors, (cold_pending, errors)
            context.close()
            return dict(locale=locale, width=width, shell_provider=shell_provider, cold_case=cold_case,
                        screenshots=screenshots, layouts=layouts, requests=requests, errors=errors)

        page.goto(BASE + "/__task3?view=shell&locale=" + locale)
        shell_nav("Research")
        model = page.locator(".research-pickerbar select").nth(0)
        effort = page.locator(".research-pickerbar select").nth(1)
        default = state["catalog"]["routes"]["ai_research"]
        expect(model).to_have_value(default["model"])
        expect(effort).to_have_value(default["effort"])
        captions(shell_provider)
        shot("settings-default")
        page.locator(".research-providerbar button").filter(has_text="OpenAI").click()
        model.select_option("gpt-5.6-sol")
        for destination in ["Home", "Settings"]:
            round_trip(destination)
            expect(model).to_have_value("gpt-5.6-sol")
            expect(effort).to_have_value("")
            page.locator("textarea").fill("Effort still required")
            expect(page.get_by_role("button", name="Send" if locale == "en" else "\u9001\u51fa", exact=True)).to_be_disabled()
            assert not [row for row in requests if row["path"] == "/research/runs" and row["method"] == "POST"]
            captions()
            shot("incomplete-after-" + destination.lower())
        effort.select_option("low")
        round_trip("Home")
        expect(model).to_have_value("gpt-5.6-sol")
        expect(effort).to_have_value("low")
        captions("openai")
        send("Retained existing conversation")
        shot("complete-after-home")
        round_trip("Settings")
        expect(model).to_have_value("gpt-5.6-sol")
        expect(effort).to_have_value("low")
        captions("openai")
        send("Retained second existing turn")
        shot("complete-after-settings")

        page.get_by_role("button", name="New Research" if locale == "en" else "\u65b0\u7814\u7a76", exact=True).click()
        expect(model).to_have_value(default["model"])
        expect(effort).to_have_value(default["effort"])
        captions(shell_provider)
        shot("new-reset")
        page.locator(".research-providerbar button").filter(has_text="OpenAI").click()
        model.select_option("gpt-5.6-sol")
        round_trip("Home")
        expect(page.locator(".research-conversation-title")).to_have_text("New conversation" if locale == "en" else "\u65b0\u5c0d\u8a71")
        expect(effort).to_have_value("")
        captions()
        shot("new-incomplete-after-home")
        effort.select_option("high")
        send("First assigned conversation")
        round_trip("Settings")
        expect(model).to_have_value("gpt-5.6-sol")
        expect(effort).to_have_value("high")
        captions("openai")
        send("After first ID assignment")
        shot("first-id-retained")
        runs = [row["body"] for row in requests if row["path"] == "/research/runs" and row["method"] == "POST"]
        assert len(runs) == 4, runs
        assert runs[0]["thread_id"] == runs[1]["thread_id"] == "history-a"
        assert runs[2]["thread_id"] == runs[3]["thread_id"] != "history-a"
        assert [(row["provider"], row["model"], row["effort"]) for row in runs] == [
            ("openai", "gpt-5.6-sol", "low"), ("openai", "gpt-5.6-sol", "low"),
            ("openai", "gpt-5.6-sol", "high"), ("openai", "gpt-5.6-sol", "high"),
        ]
        page.get_by_role("button", name="History" if locale == "en" else "\u6b77\u53f2", exact=True).click()
        page.locator(".research-history-select").filter(has_text="Another conversation").click()
        expect(model).to_have_value(default["model"])
        expect(effort).to_have_value(default["effort"])
        captions(shell_provider)
        shot("other-reset")

        page.locator(".research-providerbar button").filter(has_text="OpenAI").click()
        model.select_option("gpt-5.6-sol")
        effort.select_option("low")
        captions("openai")
        page.locator(".research-providerbar button").filter(has_text="Anthropic").click()
        model.select_option("claude-sonnet-5")
        for destination in ["Home", "Settings"]:
            round_trip(destination)
            expect(model).to_have_value("claude-sonnet-5")
            expect(effort).to_have_value("")
            expect(page.locator(".research-providerbar .ui-button-primary")).to_contain_text("Anthropic")
            page.locator("textarea").fill("Claude effort still required")
            expect(page.get_by_role("button", name="Send" if locale == "en" else "\u9001\u51fa", exact=True)).to_be_disabled()
            captions()
            shot("reverse-incomplete-after-" + destination.lower())
        assert len([row for row in requests if row["path"] == "/research/runs" and row["method"] == "POST"]) == 4
        effort.select_option("medium")
        round_trip("Settings")
        expect(model).to_have_value("claude-sonnet-5")
        expect(effort).to_have_value("medium")
        captions("anthropic")
        send("Completed reverse-provider choice")
        shot("reverse-complete-after-settings")
        runs = [row["body"] for row in requests if row["path"] == "/research/runs" and row["method"] == "POST"]
        assert len(runs) == 5
        assert (runs[-1]["thread_id"], runs[-1]["provider"], runs[-1]["model"], runs[-1]["effort"]) == (
            "history-b", "anthropic", "claude-sonnet-5", "medium",
        )
        assert not errors, errors
        context.close()
        return dict(locale=locale, width=width, shell_provider=shell_provider, screenshots=screenshots,
                    layouts=layouts, requests=requests, errors=errors)

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
                    cold = os.environ.get("ARKSCOPE_COLD_RESTORATION_ONLY") == "1"
                    providers = ["openai", "anthropic"] if cold or os.environ.get("ARKSCOPE_SHELL_NAVIGATION_ONLY") == "1" else [None]
                    cases = ["complete", "incomplete", "new", "failed-list", "failed-detail", "failed-messages", "failed-missing"] if cold else [None]
                    results = [verify(browser, locale, width, height, provider, case) for provider in providers
                               for locale in ["en", "zh-Hant"] for width, height in [(1280, 960), (390, 844)] for case in cases]
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
