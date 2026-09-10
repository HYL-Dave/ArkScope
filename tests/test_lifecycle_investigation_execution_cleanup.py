"""Live agent owners for behavior formerly tested through an abandoned pipeline."""

import ast
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading

import pytest

from src.auth_drivers.lifecycle_web_models import WebCredential, WebModelError
from src.auth_drivers.token_store import StoredTokenRecord
from src.lifecycle_investigation.news import LocalNews
from src.lifecycle_investigation.runtime import InvestigationRuntime
from src.lifecycle_investigation.target import Target
from src.lifecycle_public_sources import SourceReadError
from tests.test_lifecycle_investigation_agent import choose, completed, setup
from tests.test_lifecycle_investigation_findings import NOTICE, payload
from tests.test_lifecycle_public_sources import Response, _reader
from tests.test_security_lifecycle_web_finding import source_page


ROOT = Path(__file__).resolve().parents[1]
URL = "https://issuer.example/notice"
CHANNELS = [("openai", "api_key"), ("openai", "chatgpt_oauth"),
            ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_fixed_investigation_pipeline_is_physically_absent():
    assert not (ROOT / "src/security_lifecycle_web_pipeline.py").exists()


def test_current_source_never_imports_fixed_investigation_pipeline():
    hits = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            names = ([node.module or "", *(alias.name for alias in node.names)]
                     if isinstance(node, ast.ImportFrom) else
                     [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
            if any("security_lifecycle_web_pipeline" in name.split(".") for name in names):
                hits.append((str(path.relative_to(ROOT)), node.lineno))
    assert hits == []


class Reader:
    def __init__(self, text, reads):
        self.text = text
        self.reads = reads
        self.request_count = 0
        self.stopped = False

    def read(self, url):
        self.reads.append(url)
        self.request_count += 1
        return source_page(self.text, url)

    def request_stop(self):
        self.stopped = True


@pytest.mark.anyio
@pytest.mark.parametrize("provider,auth", CHANNELS)
async def test_current_agent_web_path_keeps_selected_channel_and_full_capture(provider, auth):
    from src.lifecycle_investigation.agent import run_agent

    selected, _, control = setup(auth, provider)
    credential = (WebCredential(selected, api_key="chosen-private-key") if auth == "api_key" else
                  WebCredential(selected, token_record=StoredTokenRecord("chosen-private-token")))
    calls, reads, saved = [], [], []
    body = ("Public appendix \U00020000.\n" * 15000) + NOTICE
    reader = Reader(body, reads)

    async def model(call, actual, current):
        calls.append(call)
        assert actual is credential and call.selection == selected and current is control
        assert call.effort == "high"
        assert call.output_token_limit == (InvestigationRuntime().api_output_tokens if auth == "api_key" else None)
        assert "chosen-private" not in call.prompt and "local:7" not in call.prompt
        if len(calls) == 1:
            assert "SEC is optional low-priority supplementation" in call.prompt
            assert "a bond's redemption/delisting" in call.prompt
            return completed(call, current, choose("search_web", query="OLD listing notice"))
        if call.phase == "search":
            assert "SEC is optional" in call.prompt and call.max_search_uses == 6
            return completed(call, current, {"sources": [URL], "unresolved_conditions": []})
        if len(calls) == 3:
            return completed(call, current, choose("read_url", url=URL, query="Trading in"))
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        source = material["sources"][0]
        assert source["input_coverage"] == "selected_passages"
        assert len(call.prompt) < len(body) / 3
        assert "\\ud840\\udc00" not in call.prompt
        assert any("Issuer Old Inc" in p["text"] for p in source["passages"])
        identity = next(p for p in source["passages"] if "Issuer Old Inc" in p["text"])
        event = next(p for p in source["passages"] if "Trading in" in p["text"])
        return completed(call, current, choose("conclude", finding=payload([identity, event])))

    result = await run_agent(Target(ticker="OLD", as_of="2026-09-08"), credential, control,
        runtime=InvestigationRuntime(), effort="high", news=LocalNews(None, None), model=model,
        reader_factory=lambda limits: reader, on_source=lambda key, value: saved.append(value))
    assert result["status"] == "succeeded", result
    assert result["validated"]["action"] == "terminal_delisting"
    assert result["stats"]["model_submissions"] == 4 and control.all_requests_terminal
    assert result["stats"]["http_requests"] == 1 and reads == [URL]
    assert len(saved) == 1 and saved[0]["text"] == body and reader.stopped


@pytest.mark.anyio
async def test_current_agent_source_failures_keep_measured_gaps_without_retry(monkeypatch):
    from src.lifecycle_investigation.agent import run_agent
    from src.lifecycle_public_sources import PublicSourceReader

    _, credential, control = setup()
    urls = [URL, "https://issuer.example/second"]
    _, connections, _, _ = _reader(monkeypatch, [
        Response(b"short", headers={"Content-Length": "1000"}),
        Response(status=403, headers={"Set-Cookie": "private-cookie"}),
    ])
    calls, events = [], []

    async def model(call, actual, current):
        calls.append(call)
        if len(calls) == 1:
            return completed(call, current, choose("search_web", query="OLD status"))
        if call.phase == "search":
            return completed(call, current, {"sources": urls, "unresolved_conditions": []})
        if len(calls) <= 4:
            return completed(call, current, choose("read_url", url=urls[len(calls) - 3]))
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        assert material["sources"] == []
        finding = {**payload([{"passage_id": "source-1:p1"}]), "event_kind": "unresolved",
            "timing": "unknown", "citations": [], "effective_date": None, "effective_date_text": None,
            "summary": "No readable listing evidence.", "unresolved_conditions": ["Trading status is unknown."]}
        return completed(call, current, choose("conclude", finding=finding))

    result = await run_agent(Target(ticker="OLD", as_of="2026-09-08"), credential, control,
        runtime=InvestigationRuntime(), effort="high", news=LocalNews(None, None), model=model,
        reader_factory=PublicSourceReader, on_step=lambda kind, value: events.append((kind, value)))
    assert result["status"] == "incomplete" and result["validated"]["action"] is None
    assert len(calls) == 5 and len(connections) == result["stats"]["http_requests"] == 2
    assert all(c.closed for c in connections)
    reports = [value for kind, value in events if kind == "source_read"]
    assert [r["url"] for r in reports] == urls
    first, second = [r["observations"][0] for r in reports]
    assert first["declared_body_bytes"] == 1000 and first["received_body_bytes"] == 5
    assert second["status"] == 403
    assert {(g["url"], g["reason"]) for g in result["gaps"] if g["url"]} == {
        (urls[0], "source_body_incomplete"), (urls[1], "source_unavailable")}
    assert "private-cookie" not in json.dumps(events)


@pytest.mark.anyio
@pytest.mark.parametrize("provider,auth", CHANNELS)
async def test_current_agent_can_conclude_with_disclosed_unread_supplement(provider, auth):
    from src.lifecycle_investigation.agent import run_agent

    _, credential, control = setup(auth, provider)
    unread = "https://issuer.example/supplement"
    calls, reads, captures = [], [], []

    class MixedReader(Reader):
        def read(self, url):
            page = super().read(url)
            if url == unread:
                raise SourceReadError("source_unavailable")
            return page

    async def model(call, actual, current):
        assert actual is credential
        calls.append(call)
        if len(calls) == 1:
            return completed(call, current, choose("search_web", query="OLD listing"))
        if call.phase == "search":
            return completed(call, current, {"sources": [URL, unread], "unresolved_conditions": []})
        if len(calls) <= 4:
            return completed(call, current, choose("read_url", url=[URL, unread][len(calls) - 3]))
        assert len(calls) == 5
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        assert material["source_gaps"] == [{"url": unread, "reason": "source_unavailable", "corpus": None}]
        assert len(material["sources"]) == 1 and material["sources"][0]["url"] == URL
        assert material["sources"][0]["source_id"] == "source-1"
        return completed(call, current, choose("conclude", finding=payload(material["sources"][0]["passages"])))

    result = await run_agent(Target(ticker="OLD", as_of="2026-09-08"), credential, control,
        runtime=InvestigationRuntime(), effort="high", news=LocalNews(None, None), model=model,
        reader_factory=lambda limits: MixedReader(NOTICE, reads), on_source=lambda key, value: captures.append(value))
    assert result["status"] == "succeeded" and result["validated"]["action"] == "terminal_delisting"
    assert result["gaps"] == [{"url": unread, "reason": "source_unavailable", "corpus": None}]
    assert result["validated"]["block_reasons"] == []
    assert {p["source_id"] for p in result["validated"]["passages"]} == {"source-1"}
    assert reads == [URL, unread] and result["stats"]["http_requests"] == 2
    assert len(captures) == 1 and captures[0]["url"] == URL and len(calls) == 5


@pytest.mark.anyio
@pytest.mark.parametrize("stop_mode", ["cooperative", "task_cancel"])
async def test_current_agent_pending_read_stops_before_any_further_dispatch(stop_mode):
    from src.lifecycle_investigation.agent import AgentFailure, run_agent

    _, credential, control = setup()
    entered, stopped, exited = (threading.Event() for _ in range(3))
    calls, reads, saved = [], [], []

    class BlockingReader(Reader):
        def read(self, url):
            self.request_count += 1
            reads.append(url)
            entered.set()
            try:
                assert stopped.wait(3)
                raise SourceReadError("source_read_cancelled")
            finally:
                exited.set()

        def request_stop(self):
            stopped.set()

    async def model(call, actual, current):
        calls.append(call)
        assert len(calls) <= 3, "model submitted after source cancellation"
        if len(calls) == 1:
            return completed(call, current, choose("search_web", query="OLD listing"))
        if call.phase == "search":
            return completed(call, current, {"sources": [URL], "unresolved_conditions": []})
        return completed(call, current, choose("read_url", url=URL))

    task = asyncio.create_task(run_agent(Target(ticker="OLD", as_of="2026-09-08"), credential, control,
        runtime=InvestigationRuntime(), effort="high", news=LocalNews(None, None), model=model,
        reader_factory=lambda limits: BlockingReader("", reads), on_source=lambda key, value: saved.append(value)))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        task.cancel() if stop_mode == "task_cancel" else control.request_stop()
        with pytest.raises(AgentFailure, match="^stop_requested$") as caught:
            await asyncio.wait_for(task, 3)
        assert caught.value.result["status"] == "failed"
        assert stopped.is_set() and exited.is_set() and control.stop_state != "running"
        assert len(calls) == control.model_requests == 3 and reads == [URL] and saved == []
    finally:
        stopped.set()
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, AgentFailure):
                pass


@pytest.mark.anyio
@pytest.mark.parametrize("provider,auth", CHANNELS)
async def test_current_agent_context_rejection_never_clips_or_retries(provider, auth):
    from src.lifecycle_investigation.agent import AgentFailure, run_agent

    _, credential, control = setup(auth, provider)
    calls, reads, captures = [], [], []
    body = "Public evidence \U00020000.\n" * 10000 + NOTICE

    async def model(call, actual, current):
        calls.append(call)
        if len(calls) == 1:
            return completed(call, current, choose("search_web", query="OLD listing"))
        if call.phase == "search":
            return completed(call, current, {"sources": [URL], "unresolved_conditions": []})
        if len(calls) == 3:
            return completed(call, current, choose("read_url", url=URL))
        raise WebModelError("context_limit_exceeded")

    with pytest.raises(AgentFailure, match="^context_limit_exceeded$"):
        await run_agent(Target(ticker="OLD", as_of="2026-09-08"), credential, control,
            runtime=InvestigationRuntime(), effort="high", news=LocalNews(None, None), model=model,
            reader_factory=lambda limits: Reader(body, reads), on_source=lambda key, value: captures.append(value))
    assert len(calls) == 4 and reads == [URL]
    assert len(captures) == 1 and captures[0]["text"] == body


@pytest.mark.anyio
@pytest.mark.parametrize("stop_mode", ["before_read", "cooperative", "task_cancel"])
async def test_agent_owned_read_stops_and_awaits_worker(stop_mode):
    from src.lifecycle_investigation import agent

    read_one = getattr(agent, "_read_one", None)
    assert callable(read_one) and read_one.__module__ == agent.__name__
    _, _, control = setup()
    entered, stopped, release, exited = (threading.Event() for _ in range(4))

    class BlockingReader:
        def read(self, url):
            entered.set()
            try:
                assert stopped.wait(3)
                assert release.wait(3)
                raise SourceReadError("source_read_cancelled")
            finally:
                exited.set()

        def request_stop(self):
            stopped.set()

    pool = ThreadPoolExecutor(max_workers=1)
    task = None
    try:
        if stop_mode == "before_read":
            control.request_stop()
            with pytest.raises(WebModelError, match="^stop_requested$"):
                await read_one(BlockingReader(), URL, control, pool)
            assert not entered.is_set()
            return
        task = asyncio.create_task(read_one(BlockingReader(), URL, control, pool))
        assert await asyncio.to_thread(entered.wait, 3)
        task.cancel() if stop_mode == "task_cancel" else control.request_stop()
        assert await asyncio.to_thread(stopped.wait, 3)
        await asyncio.sleep(0)
        assert not task.done() and not exited.is_set()
        release.set()
        with pytest.raises(asyncio.CancelledError if stop_mode == "task_cancel" else SourceReadError):
            await asyncio.wait_for(task, 3)
        assert exited.is_set() and control.stop_state != "running"
    finally:
        stopped.set()
        release.set()
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, SourceReadError):
                pass
        pool.shutdown(wait=True, cancel_futures=True)
