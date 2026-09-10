"""Synthetic current credentials and real target-agent worker fixtures."""

import json
import time
from types import SimpleNamespace

from src.auth_drivers.lifecycle_web_models import WebCredential
from src.lifecycle_investigation.agent import run_agent
from src.lifecycle_investigation.controller import InvestigationController
from src.lifecycle_investigation.news import LocalNews
from tests.test_lifecycle_investigation_agent import choose, completed
from tests.test_lifecycle_investigation_findings import NOTICE, payload
from tests.test_lifecycle_investigation_news import corpus
from tests.test_lifecycle_investigation_store import running


CHANNELS = [("openai", "api_key"), ("openai", "chatgpt_oauth"),
            ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")]


def synthetic_credentials(*, provider="openai", auth="api_key"):
    model = "gpt-5.6-luna" if provider == "openai" else "claude-sonnet-5"
    rows = [SimpleNamespace(id=7, provider=provider, auth_type=auth, active=True, alias="Selected account",
        secret="do-not-export-this-secret" if auth == "api_key" else None, updated_at="2026-09-06T01:00:00Z")]
    credentials = SimpleNamespace(list=lambda requested: [row for row in rows if row.provider == requested])
    return credentials, rows, SimpleNamespace(provider=provider, model=model, effort="high")


async def completed_runner(*args, **kwargs):
    async def model(call, credential, control):
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        return completed(call, control, choose("conclude", finding=payload(material["sources"][0]["passages"])))
    return await run_agent(*args, **kwargs, model=model)


def controller(tmp_path, *, loader=None, runner=completed_runner, **kwargs):
    c, store, initial, binding = running(tmp_path)
    store.finish(initial, owner="worker", status="failed")
    calls = []

    def load(selected):
        calls.append(selected)
        return loader(selected) if loader else WebCredential(selected, api_key="synthetic-private-key", generation="generation-1")

    news_path = corpus(tmp_path, body=NOTICE)
    service = InvestigationController(store, credential_loader=load, runner=runner,
        news_factory=lambda: LocalNews(news_path, None, clock=lambda: c["now"][0]), **kwargs)
    return service, store, calls, binding


def wait_done(service, identity):
    deadline = time.monotonic() + 5
    while service.is_local_running(identity) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not service.is_local_running(identity), "local worker did not terminate"
    return service.read(identity)
