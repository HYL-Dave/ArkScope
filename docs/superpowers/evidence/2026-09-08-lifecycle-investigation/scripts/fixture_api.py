"""Real routes/controller/writer, temporary stores, synthetic model completions only."""

import asyncio
from contextlib import contextmanager, ExitStack
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import socket
import sqlite3
import sys
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@contextmanager
def fixture_app(folder):
    from src.api.routes import lifecycle_investigation as api, ticker_identity as transition_api
    from src.auth_drivers.lifecycle_web_models import WebCredential, WebModelError, credential_generation
    from src.lifecycle_investigation.agent import run_agent
    from src.lifecycle_investigation.controller import InvestigationController
    from src.lifecycle_investigation.news import LocalNews
    from tests.test_lifecycle_investigation_agent import completed, choose
    from tests.test_lifecycle_investigation_findings import payload
    from tests.test_lifecycle_investigation_review import context
    from src.profile_state import ProfileStateStore
    from src.security_lifecycle_listing_evidence import _evidence
    from tests.test_security_lifecycle_provider_authority import terminal_records

    # Playwright's sync harness owns an event loop on its main thread.
    with ThreadPoolExecutor(max_workers=1) as worker:
        c = worker.submit(context, folder, provider="anthropic", auth="claude_code_oauth").result()
    state = {"mode": "success", "submissions": [], "provider_checks": [], "writes": []}
    ProfileStateStore(c["profile"]).import_lists([{"name": "Structured source review", "kind": "custom", "tickers": ["CACHED"]}])
    c["checks"].record(ticker="CACHED", at=c["now"][0],
        evidence=tuple(_evidence(replace(row, ticker="CACHED", retrieved_at=c["now"][0])) for row in terminal_records()), diagnostics={})
    selected_route = c["preflight"].route_loader
    def route():
        if state["mode"] == "provider_only":
            raise ValueError("selected_credential_unavailable")
        return selected_route()
    c["preflight"].route_loader = route
    news_path = folder / "news.db"
    with sqlite3.connect(news_path) as conn:
        conn.execute("INSERT INTO news_articles(id,source,canonical_title,publisher,url,published_at,content_kind,created_at,updated_at) "
            "VALUES(2,'fixture','LIVE current listing','Issuer Live','https://issuer.example/live','2026-09-08','full_text','2026-09-08','2026-09-08')")
        conn.execute("INSERT INTO news_article_tickers VALUES(2,'LIVE','primary','2026-09-08','2026-09-08')")
        conn.execute("INSERT INTO news_article_bodies(article_id,body_status,body_text,fetched_at) VALUES(2,'fetched',?,'2026-09-08')",
            ("Issuer Live Inc LIVE common stock remains actively listed and trading on NASDAQ.",))

    async def model(call, credential, control):
        state["submissions"].append({"provider": call.selection.provider, "auth_mode": call.selection.auth_mode, "model": call.selection.model})
        for _ in range(80 if state["mode"] == "slow" else 4):
            await asyncio.sleep(.1)
            if control.stop_state != "running":
                raise WebModelError("stop_requested")
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        passages = material["sources"][0]["passages"]
        result = payload(passages)
        if material["target"]["ticker"] == "LIVE":
            result.update(source_ticker="LIVE", issuer_name="Issuer Live Inc", event_kind="active_listing", effective_date=None,
                effective_date_text=None, summary="The common stock remains actively listed; keep tracking it.",
                citations=[{"passage_id": passages[0]["passage_id"], "supports": ["security_identity", "active_listing"]}])
        elif state["mode"] == "unknown_date":
            result.update(effective_date=None, effective_date_text=None, limitations=["The exact trading-end date has not been established."])
        elif state["mode"] == "incomplete":
            result.update(event_kind="unresolved", timing="unknown", effective_date=None, effective_date_text=None,
                summary="The available information does not establish current trading status.", unresolved_conditions=["Current OTC trading has not been resolved."])
        if material["language"] == "zh-Hant":
            result["summary"] = {"listing_ended": "普通股已停止交易，建議停止主動追蹤；歷史資料會保留。",
                "active_listing": "普通股仍在交易，維持追蹤。", "unresolved": "目前資料仍不足以確認是否繼續交易。"}[result["event_kind"]]
        return completed(call, control, choose("conclude", finding=result))

    async def runner(*args, **kwargs):
        return await run_agent(*args, **kwargs, model=model)

    def load(selection):
        row, = c["preflight"].credential_store.list(selection.provider)
        return WebCredential(selection, generation=credential_generation(row))

    controller = InvestigationController(c["investigation"], credential_loader=load,
        news_factory=lambda: LocalNews(news_path, folder / "missing-corpus.db", clock=lambda: c["now"][0]), runner=runner, heartbeat_seconds=.1)
    app = FastAPI()
    app.include_router(api.router)
    app.include_router(transition_api.router)
    app.dependency_overrides.update({api.get_controller: lambda: controller, api.get_preflight: lambda: c["preflight"],
        api.get_ticker_identity_service: lambda: c["service"]})

    @app.post("/fixture/scenario")
    def scenario(body: dict):
        if body.get("mode") not in {"success", "unknown_date", "incomplete", "slow", "provider_only"}:
            raise HTTPException(422)
        state["mode"] = body["mode"]
        return {"mode": state["mode"]}

    @app.get("/fixture/state")
    def inspect():
        return state

    @app.post("/fixture/seed-unknown-date")
    def unknown_date():
        state["mode"] = "unknown_date"
        request = c["preflight"].prepare("OLD", language="en")
        return controller.start(**c["preflight"].validate_start("OLD", preflight_sha256=request["preflight_sha256"], language="en"),
            request_key="fixture-unknown-date")

    def no_provider(**kwargs):
        state["provider_checks"].append({"tickers": kwargs["tickers"], "target_ticker": kwargs["target_ticker"]})

    with ExitStack() as stack:
        for module in (api, transition_api):
            for name in ("require_db_write", "require_profile_state_write"):
                stack.enter_context(patch.object(module, name, lambda *args: state["writes"].append(args[0])))
        stack.enter_context(patch.object(api, "run_provider_scan", no_provider))
        try:
            yield app, c, state
        finally:
            controller.close()


def main():
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", required=True, type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=False)
    with fixture_app(args.work) as (app, _, _):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        print(json.dumps({"api": f"http://127.0.0.1:{listener.getsockname()[1]}"}), flush=True)
        asyncio.run(uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False)).serve(sockets=[listener]))


if __name__ == "__main__":
    main()
