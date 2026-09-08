"""Real Settings + real route APIs, temporary profiles and synthetic model replies."""

import argparse
from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urlparse
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright, expect

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
TASK = "lifecycle_investigation"


@contextmanager
def fixture_api(auth):
    with tempfile.TemporaryDirectory(prefix="arkscope-task-browser-") as directory, ExitStack() as stack:
        folder = Path(directory)
        stack.enter_context(patch.dict(os.environ, {"ARKSCOPE_PROFILE_DB": str(folder / "profile.db"),
                                                    "ARKSCOPE_DISABLE_SCHEDULER": "1"}))
        from src import env_keys, model_task_canary
        from src.agents import config
        from src.api import dependencies
        from src.api.routes import config_routes
        from src.auth_drivers import lifecycle_web_models, lifecycle_web_codex, lifecycle_web_claude
        from src.auth_drivers.oauth_status import OAuthObservationStore
        from src.auth_drivers.token_store import PlaintextTokenStore, StoredTokenRecord
        from src.model_credentials import CredentialStore, resolve_active_credential
        from src.model_discovery_cache import ModelDiscoveryCache

        for module in (config, env_keys):
            stack.enter_context(patch.object(module, "ensure_env_loaded", lambda: None))
        stack.enter_context(patch.object(config, "_MAIN_CONFIG_PATH", folder / "missing.yaml"))
        stack.enter_context(patch.object(config, "_LOCAL_CONFIG_PATH", folder / "local.yaml"))
        for task in ("card_synthesis", "card_translation", "ai_research", TASK):
            for field in ("provider", "model", "effort"):
                key = f"ARKSCOPE_{task}_{field}".upper()
                if key in os.environ:
                    stack.enter_context(patch.dict(os.environ, {key: ""}))
        config.get_agent_config.cache_clear()
        credentials = CredentialStore(folder / "profile.db")
        tokens = PlaintextTokenStore(folder / "tokens.json")
        observations = OAuthObservationStore(folder / "profile.db")
        cache = ModelDiscoveryCache(folder / "profile.db")
        for provider, oauth in (("anthropic", "claude_code_oauth"), ("openai", "chatgpt_oauth")):
            mode = "api_key" if auth == "api_key" else oauth
            if mode == "api_key":
                credentials.add(provider=provider, auth_type=mode, alias=f"Fixture {provider} API",
                                secret="synthetic-browser-credential")
            else:
                row = credentials.add_oauth_credential(provider=provider, auth_mode=mode, alias=f"Fixture {provider} subscription")
                tokens.save(provider=provider, auth_mode=mode, credential_id=f"local:{row.id}",
                            record=StoredTokenRecord("synthetic-browser-token", expires_at="2099-01-01T00:00:00Z"))
            active = resolve_active_credential(provider, credentials, token_store=tokens, observation_store=observations)
            ids = (["claude-sonnet-5", "claude-opus-5", "claude-fable-5-1"] if provider == "anthropic"
                   else ["gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.3-codex-spark"])
            cache.record_run(provider=provider, auth_mode=mode, credential_id=active.credential_id,
                secret_fingerprint=active.secret_fingerprint, status="seed_only" if mode == "claude_code_oauth" else "ok",
                models=[] if mode == "claude_code_oauth" else [{"id": value, "label": value, "source": "provider_api"} for value in ids])
        state = {"model_calls": [], "writes": []}
        stack.enter_context(patch.object(config_routes, "require_profile_state_write", lambda op, detail: state["writes"].append(op)))

        async def reply(call, credential, control):
            assert call.phase == "analysis" and control.max_model_requests == 1
            assert call.selection == credential.selection
            state["model_calls"].append({"provider": call.selection.provider, "auth_mode": call.selection.auth_mode,
                                         "model": call.selection.model, "effort": call.effort})
            control.reserve_model_request(call.call_id)
            control.bind_remote_id(call.call_id, "fixture-remote")
            control.observe_terminal(call.call_id, response_id="fixture-remote", status="completed", selection=call.selection)
            return lifecycle_web_models.ModelReply("fixture-remote", {"ok": True}, {"input_tokens": 12, "output_tokens": 4})

        for module, name in ((lifecycle_web_models, "call_openai_web"), (lifecycle_web_models, "call_anthropic_web"),
                             (lifecycle_web_codex, "call_codex_web"), (lifecycle_web_claude, "call_claude_web")):
            stack.enter_context(patch.object(module, name, reply))

        def forbidden(*args, **kwargs):
            raise AssertionError("unexpected provider call")

        for module, name in ((model_task_canary, "test_model"), (config_routes, "discover_models"),
                             (config_routes, "test_model"), (model_task_canary, "build_driver")):
            stack.enter_context(patch.object(module, name, forbidden))
        app = FastAPI()
        app.include_router(config_routes.router)
        app.dependency_overrides.update({dependencies.get_credential_store: lambda: credentials,
            dependencies.get_oauth_token_store: lambda: tokens, dependencies.get_oauth_observation_store: lambda: observations})
        with TestClient(app) as client:
            yield client, state
        config.get_agent_config.cache_clear()


def geometry(card):
    return card.evaluate("""root => {
      const visible = [...root.querySelectorAll('button, input, select')].filter(e => e.getClientRects().length);
      const controls = visible.map(e => ({r: e.getBoundingClientRect(), label: e.textContent}));
      return {
        bodyOverflow: document.documentElement.scrollWidth > innerWidth + 1,
        clipped: controls.filter(({r}) => r.left < -1 || r.right > innerWidth + 1).length,
        overlap: controls.some(({r:a},i) => controls.slice(i+1).some(({r:b}) =>
          Math.min(a.right,b.right)-Math.max(a.left,b.left)>1 && Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)),
        overflow: [...root.querySelectorAll('button, h2, p')].filter(e => e.getClientRects().length && e.scrollWidth > e.clientWidth + 2).length,
      };
    }""")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    server = subprocess.Popen(["node", str(HERE / "serve_preview.mjs")], cwd=ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    results = []
    try:
        line = server.stdout.readline()
        if not line:
            raise RuntimeError(server.stderr.read())
        url = json.loads(line)["url"]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for locale in ("en", "zh-Hant"):
                for width, height in ((1440, 1000), (390, 844), (320, 740)):
                    for auth in ("api_key", "oauth"):
                        with fixture_api(auth) as (api, state):
                            initial = api.get("/config/runtime").json()
                            context = browser.new_context(viewport={"width": width, "height": height}, service_workers="block")
                            page = context.new_page()
                            errors, unexpected, requests = [], [], []
                            page.on("pageerror", lambda error: errors.append(str(error)))

                            def handle(route):
                                parsed = urlparse(route.request.url)
                                if parsed.netloc == urlparse(url).netloc:
                                    route.continue_()
                                    return
                                if parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.path.startswith("/config/"):
                                    unexpected.append(parsed.path)
                                    route.abort()
                                    return
                                if route.request.method == "OPTIONS":
                                    route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*",
                                        "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*"})
                                    return
                                response = api.request(route.request.method, parsed.path,
                                    json=route.request.post_data_json if route.request.post_data else None)
                                requests.append({"method": route.request.method, "path": parsed.path,
                                                 "status": response.status_code})
                                assert response.status_code < 400, (parsed.path, response.text)
                                route.fulfill(status=response.status_code, content_type="application/json",
                                              body=response.text, headers={"Access-Control-Allow-Origin": "*"})

                            page.route("**/*", handle)
                            page.goto(url + "?locale=" + locale)
                            card = page.get_by_test_id("route-lifecycle_investigation")
                            expect(card.locator("h2")).to_have_text("Lifecycle Investigation" if locale == "en" else "標的事件調查")
                            expect(card.locator(".model-custom-toggle")).to_have_count(0)
                            assert state["model_calls"] == [] and state["writes"] == []
                            metrics = []
                            for provider, model in (("anthropic", "claude-opus-5"), ("openai", "gpt-5.6-luna")):
                                card.get_by_role("button", name="Anthropic" if provider == "anthropic" else "OpenAI", exact=True).click()
                                card.locator('select[aria-labelledby$="-model-label"]').select_option(model)
                                card.locator('select[aria-labelledby$="-effort-label"]').select_option("medium")
                                button = card.get_by_role("button", name="Test connection and format" if locale == "en" else "連線與格式測試", exact=True)
                                button.scroll_into_view_if_needed()
                                metrics.append(geometry(card))
                                assert not any(metrics[-1].values()), metrics[-1]
                                shot = args.output / f"{locale}-{width}-{auth}-{provider}.png"
                                page.screenshot(path=str(shot))
                                with Image.open(shot) as picture:
                                    assert max(ImageStat.Stat(picture).var) > 5
                                button.click()
                                expect(card.locator(".test-status strong")).to_have_text(
                                    "Connection and format check passed" if locale == "en" else "連線與格式檢查通過")
                            assert len(state["model_calls"]) == 2
                            page.locator(".settings-model-actions").get_by_role("button", name="Save" if locale == "en" else "儲存", exact=True).click()
                            try:
                                expect(card.locator(".route-source")).to_contain_text("DB")
                            except AssertionError:
                                prefix = args.output / f"{locale}-{width}-{auth}-save-failure"
                                page.screenshot(path=str(prefix.with_suffix(".png")))
                                prefix.with_suffix(".json").write_text(json.dumps({
                                    "requests": requests, "errors": errors, "unexpected": unexpected,
                                    "page_text": page.locator("body").inner_text(),
                                    "runtime": api.get("/config/runtime").json(),
                                    "state": state,
                                }, indent=2) + "\n")
                                raise
                            effective = api.get("/config/runtime").json()
                            assert effective[TASK]["model"] == "gpt-5.6-luna" and effective[TASK]["effort"] == "medium"
                            for other in ("card_synthesis", "card_translation", "ai_research"):
                                assert all(effective[other][field] == initial[other][field] for field in ("provider", "model", "effort"))
                            assert not errors and not unexpected, (errors, unexpected)
                            results.append({"locale": locale, "width": width, "auth": auth, "metrics": metrics,
                                            "synthetic_model_calls": state["model_calls"], "actual_provider_calls": 0})
                            context.close()
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=15)
        (args.output / "results.json").write_text(json.dumps({"scenarios": results,
            "actual_provider_calls": 0, "production_app_started": False}, indent=2) + "\n")
    assert len(results) == 12
    print(json.dumps({"scenarios": len(results), "screenshots": len(list(args.output.glob("*.png"))), "actual_provider_calls": 0}))


if __name__ == "__main__":
    main()
