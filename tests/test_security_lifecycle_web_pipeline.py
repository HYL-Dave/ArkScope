import asyncio
from dataclasses import replace
import json
import threading

import pytest

from src.auth_drivers.lifecycle_web_models import ModelReply, WebCredential, WebModelError
from src.auth_drivers.token_store import StoredTokenRecord
from src.lifecycle_public_sources import SourceReadError
from src.security_lifecycle_web_contract import RunControl, validate_selection
from tests.test_security_lifecycle_web_finding import NOTICE, finding_payload, public_input, source_page


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Reader:
    def __init__(self, fail=False, entered=None):
        self.urls = []
        self.fail = fail
        self.entered = entered
        self.stopped = threading.Event()

    @property
    def request_count(self):
        return len(self.urls)

    def read(self, url):
        self.urls.append(url)
        if self.entered is not None:
            self.entered.set()
            assert self.stopped.wait(2)
            raise SourceReadError("source_read_cancelled")
        if self.fail and len(self.urls) == 2:
            raise SourceReadError("source_unavailable")
        return source_page(NOTICE, url)

    def request_stop(self):
        self.stopped.set()


def _options(auth):
    from src.security_lifecycle_web_pipeline import WebInvestigationOptions
    return WebInvestigationOptions(max_sources=2, max_source_requests=4, max_redirects=1, max_source_bytes=65536,
                                    source_timeout_seconds=3, model_timeout_seconds=3, max_search_uses=2,
                                    output_token_limit=4096 if auth == "api_key" else None, effort="high")


def _fake_model(calls, sources=None, fail=False, stop=None):
    async def call(request, credential, control):
        calls.append((request, credential))
        control.reserve_model_request(request.call_id)
        control.bind_remote_id(request.call_id, "remote-" + request.phase)
        if fail:
            control.observe_terminal(request.call_id, response_id="remote-" + request.phase, status="failed", selection=request.selection)
            raise WebModelError("provider_rate_limited")
        output = ({"sources": sources if sources is not None else ["https://ir.example.com/notice"], "unresolved_conditions": []}
                  if request.phase == "search" else finding_payload())
        control.observe_terminal(request.call_id, response_id="remote-" + request.phase, status="completed", selection=request.selection)
        if stop is not None and request.phase == "search":
            stop()
        return ModelReply("remote-" + request.phase, output, {"input_tokens": 10, "output_tokens": 20})
    return call


@pytest.mark.anyio
@pytest.mark.parametrize("provider,auth", [("openai", "api_key"), ("openai", "chatgpt_oauth"),
                                          ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")])
async def test_all_four_channels_share_source_reading_and_finding_validation(monkeypatch, provider, auth):
    from src import security_lifecycle_web_pipeline as mod

    selection = validate_selection(provider, auth, "gpt-5.6-luna" if provider == "openai" else "claude-opus-5", "local:7")
    credential = WebCredential(selection, api_key="private-key") if auth == "api_key" else WebCredential(selection, token_record=StoredTokenRecord("private-token"))
    control = RunControl(selection=selection, max_model_requests=2)
    calls, stages = [], []
    reader = Reader()
    monkeypatch.setattr(mod, "call_lifecycle_web_model", _fake_model(calls))
    result = await mod.investigate(public_input(), credential, control, options=_options(auth), reader_factory=lambda limits: reader, on_stage=stages.append)
    assert result.finding.action == "terminal_delisting" and result.finding.block_reasons == ()
    assert [call.phase for call, _ in calls] == ["search", "analysis"]
    assert all(actual is credential for _, actual in calls)
    assert all("private-key" not in call.prompt and "private-token" not in call.prompt and "local:7" not in call.prompt for call, _ in calls)
    assert NOTICE in calls[1][0].prompt
    assert "SEC is supplementary, not a required source" in calls[1][0].prompt
    assert "financial reporting" in calls[1][0].prompt
    assert "filing date is not an effective date" in calls[1][0].prompt
    assert "completed, scheduled, conditional or cancelled" in calls[1][0].prompt
    assert reader.urls == ["https://ir.example.com/notice"]
    assert result.usage == {"input_tokens": 20, "output_tokens": 40}
    assert control.model_requests == 2 and control.all_requests_terminal
    assert stages == ["searching", "reading_sources", "analyzing", "completed"]


@pytest.mark.anyio
@pytest.mark.parametrize("provider,auth", [("openai", "api_key"), ("openai", "chatgpt_oauth"),
                                          ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")])
async def test_source_read_failure_remains_visible_and_never_retries(monkeypatch, provider, auth):
    from src import security_lifecycle_web_pipeline as mod

    selection = validate_selection(provider, auth, "gpt-5.6-luna" if provider == "openai" else "claude-sonnet-5", "local:7")
    credential = WebCredential(selection, api_key="selected") if auth == "api_key" else WebCredential(selection, token_record=StoredTokenRecord("selected"))
    control = RunControl(selection=selection, max_model_requests=2)
    calls = []
    reader = Reader(fail=True)
    urls = ["https://ir.example.com/notice", "https://news.example.com/unavailable"]
    monkeypatch.setattr(mod, "call_lifecycle_web_model", _fake_model(calls, sources=urls))
    result = await mod.investigate(public_input(), credential, control,
                                    options=_options(auth), reader_factory=lambda limits: reader)
    assert result.finding.action == "terminal_delisting" and result.finding.block_reasons == ()
    assert result.source_failures == {"source-2": "source_unavailable"}
    assert result.source_failure_urls == {"source-2": urls[1]}
    material = json.loads(calls[1][0].prompt.split("\n", 1)[1])
    assert material["unread_sources"] == [{"source_id": "source-2", "url": urls[1], "reason": "source_unavailable"}]
    assert "Do not treat an unread supplement alone as a material unresolved condition" in calls[1][0].prompt
    assert "Never claim an unread source was reviewed" in calls[1][0].prompt
    assert "missing conditions" in calls[1][0].prompt
    assert reader.urls == urls and len(calls) == 2


@pytest.mark.anyio
@pytest.mark.parametrize("sources,reason", [
    ([], "search_no_sources"), (["https://127.0.0.1/private"], "unsafe_source_url"),
    (["https://a.example.com", "https://b.example.com", "https://c.example.com"], "search_output_invalid"),
])
async def test_invalid_or_empty_search_does_not_fetch_or_submit_analysis(monkeypatch, sources, reason):
    from src import security_lifecycle_web_pipeline as mod

    selection = validate_selection("openai", "api_key", "gpt-5.6-luna", "local:7")
    control = RunControl(selection=selection, max_model_requests=2)
    calls = []
    reader = Reader()
    monkeypatch.setattr(mod, "call_lifecycle_web_model", _fake_model(calls, sources=sources))
    with pytest.raises((ValueError, WebModelError), match=reason):
        await mod.investigate(public_input(), WebCredential(selection, api_key="selected"), control,
                             options=_options("api_key"), reader_factory=lambda limits: reader)
    assert len(calls) == 1 and reader.urls == []


@pytest.mark.anyio
async def test_failed_search_or_stop_never_dispatches_more_work(monkeypatch):
    from src import security_lifecycle_web_pipeline as mod

    selection = validate_selection("openai", "api_key", "gpt-5.6-luna", "local:7")
    for failure in (True, False):
        control = RunControl(selection=selection, max_model_requests=2)
        calls = []
        reader = Reader()
        monkeypatch.setattr(mod, "call_lifecycle_web_model", _fake_model(calls, fail=failure, stop=None if failure else control.request_stop))
        with pytest.raises((ValueError, WebModelError), match="provider_rate_limited" if failure else "stop_requested"):
            await mod.investigate(public_input(), WebCredential(selection, api_key="selected"), control,
                                 options=_options("api_key"), reader_factory=lambda limits: reader)
        assert len(calls) == 1 and reader.urls == []


@pytest.mark.anyio
async def test_stop_during_source_read_joins_worker_and_never_dispatches_analysis(monkeypatch):
    from src import security_lifecycle_web_pipeline as mod

    selection = validate_selection("anthropic", "claude_code_oauth", "claude-opus-5", "local:7")
    control = RunControl(selection=selection, max_model_requests=2)
    entered = threading.Event()
    reader = Reader(entered=entered)
    calls = []
    monkeypatch.setattr(mod, "call_lifecycle_web_model", _fake_model(calls))
    task = asyncio.create_task(mod.investigate(public_input(), WebCredential(selection, token_record=StoredTokenRecord("selected")), control,
                                              options=_options("claude_code_oauth"), reader_factory=lambda limits: reader))
    for _ in range(50):
        if entered.is_set():
            break
        await asyncio.sleep(0.01)
    assert entered.is_set()
    control.request_stop()
    with pytest.raises((ValueError, WebModelError), match="stop_requested|source_read_cancelled"):
        await asyncio.wait_for(task, 1)
    assert reader.stopped.is_set() and len(calls) == 1


@pytest.mark.anyio
async def test_large_source_is_saved_whole_but_analysis_receives_traceable_passages(monkeypatch):
    from src import security_lifecycle_web_pipeline as mod
    from tests.test_lifecycle_source_context import long_source

    selection = validate_selection("openai", "api_key", "gpt-5.6-luna", "local:7")
    control = RunControl(selection=selection, max_model_requests=2)
    reader, calls, saved = Reader(), [], []
    page = source_page(long_source())
    monkeypatch.setattr(reader, "read", lambda url: page)
    monkeypatch.setattr(mod, "call_lifecycle_web_model", _fake_model(calls))
    result = await mod.investigate(public_input(), WebCredential(selection, api_key="selected"), control,
                                    options=_options("api_key"), reader_factory=lambda limits: reader,
                                    on_source=lambda identity, value: saved.append(value))
    assert saved == [page] and result.pages["source-1"].text == long_source()
    prompt = calls[1][0].prompt
    assert NOTICE in prompt and "remain actively traded OTC" in prompt
    assert len(prompt) < len(page.text) / 10
    assert "selected_passages" in prompt
    assert result.source_context["source-1"]["source_text_sha256"] == page.text_sha256


@pytest.mark.anyio
@pytest.mark.parametrize("provider,auth", [("openai", "api_key"), ("openai", "chatgpt_oauth"),
                                          ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")])
async def test_unicode_analysis_keeps_exact_text_without_ascii_escape_expansion(monkeypatch, provider, auth):
    from src import security_lifecycle_web_pipeline as mod

    selected = validate_selection(provider, auth, "gpt-5.6-luna" if provider == "openai" else "claude-sonnet-5", "local:7")
    credential = WebCredential(selected, api_key="chosen") if auth == "api_key" else WebCredential(selected, token_record=StoredTokenRecord("chosen"))
    control, calls, reader = RunControl(selection=selected, max_model_requests=2), [], Reader()
    text = ("Shares remain active: " + "\U00020000" * 400 + "\n") * 100 + NOTICE
    page = source_page(text)
    monkeypatch.setattr(reader, "read", lambda url: page)
    monkeypatch.setattr(mod, "call_lifecycle_web_model", _fake_model(calls))
    result = await mod.investigate(public_input(), credential, control, options=_options(auth), reader_factory=lambda limits: reader)
    prompt = calls[1][0].prompt
    material = json.loads(prompt.split("\n", 1)[1])
    assert material["sources"][0]["passages"][0]["text"] == text
    assert "\U00020000" in prompt and "\\ud840\\udc00" not in prompt
    assert len(prompt.encode()) < len(text.encode()) * 1.1
    assert result.pages["source-1"].text == text and len(calls) == 2


@pytest.mark.anyio
@pytest.mark.parametrize("provider,auth", [("openai", "api_key"), ("openai", "chatgpt_oauth"),
                                          ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")])
async def test_model_context_rejection_never_clips_relevant_input_or_retries(monkeypatch, provider, auth):
    from src import security_lifecycle_web_pipeline as mod
    selected = validate_selection(provider, auth, "gpt-5.6-luna" if provider == "openai" else "claude-sonnet-5", "local:7")
    credential = WebCredential(selected, api_key="chosen") if auth == "api_key" else WebCredential(selected, token_record=StoredTokenRecord("chosen"))
    control = RunControl(selection=selected, max_model_requests=2)
    calls, reader = [], Reader()
    text = "Trading remains active. " * 20000 + "The final source sentence must remain present."
    monkeypatch.setattr(reader, "read", lambda url: source_page(text))
    ordinary = _fake_model(calls)

    async def model(call, actual, state):
        assert actual is credential
        if call.phase == "search":
            return await ordinary(call, actual, state)
        calls.append((call, actual))
        assert text in call.prompt
        state.reserve_model_request(call.call_id)
        state.bind_remote_id(call.call_id, "remote-analysis")
        state.observe_terminal(call.call_id, response_id="remote-analysis", status="failed", selection=call.selection)
        raise WebModelError("context_window_exceeded")

    monkeypatch.setattr(mod, "call_lifecycle_web_model", model)
    with pytest.raises(WebModelError, match="^context_window_exceeded$"):
        await mod.investigate(public_input(), credential, control, options=_options(auth), reader_factory=lambda limits: reader)
    assert [value.phase for value, _ in calls] == ["search", "analysis"]
    assert control.all_requests_terminal and control.model_requests == 2
