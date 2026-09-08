import json

import pytest

from src.auth_drivers.lifecycle_web_models import ModelReply, WebCredential, WebModelError
from src.lifecycle_investigation.runtime import InvestigationRuntime
from src.lifecycle_investigation.target import Target
from src.security_lifecycle_web_contract import RunControl, validate_selection
from tests.test_lifecycle_investigation_findings import NOTICE, payload
from tests.test_lifecycle_investigation_news import corpus
from tests.test_security_lifecycle_web_finding import source_page


@pytest.fixture
def anyio_backend():
    return "asyncio"


def choose(action, **kwargs):
    return {"action": action, "reason": "Resolve the listing question.", "query": None, "candidate_id": None,
        "source_id": None, "url": None, "offset": 0, "since": None, "until": None, "finding": None, **kwargs}


def setup(auth="claude_code_oauth", provider="anthropic"):
    selection = validate_selection(provider, auth, "claude-sonnet-5" if provider == "anthropic" else "gpt-5.6-luna", "local:7")
    return selection, WebCredential(selection), RunControl(selection=selection, max_model_requests=24)


def completed(call, control, output, *, error=None):
    control.reserve_model_request(call.call_id)
    control.bind_remote_id(call.call_id, call.call_id)
    control.observe_terminal(call.call_id, response_id=call.call_id, status="completed", selection=call.selection)
    return ModelReply(call.call_id, output, {"input_tokens": 10, "output_tokens": 20}, output_error=error)


@pytest.mark.anyio
@pytest.mark.parametrize("language,label", [("en", "English"), ("zh-Hant", "Traditional Chinese (zh-Hant)")])
async def test_requested_language_is_explicit_before_source_material(tmp_path, language, label):
    from src.lifecycle_investigation.agent import run_agent
    from src.lifecycle_investigation.news import LocalNews
    _, credential, control = setup()
    async def model(call, credential, control):
        assert call.prompt.startswith("USER-FACING LANGUAGE: " + label + ".")
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        return completed(call, control, choose("conclude", finding=payload(material["sources"][0]["passages"])))
    result = await run_agent(Target(ticker="OLD", as_of="2026-09-08"), credential, control,
        runtime=InvestigationRuntime(), effort="high", news=LocalNews(corpus(tmp_path, body=NOTICE), None), model=model, language=language)
    assert result["status"] == "succeeded" and result["stats"]["model_submissions"] == 1


@pytest.mark.anyio
@pytest.mark.parametrize("provider,auth", [("anthropic", "api_key"), ("anthropic", "claude_code_oauth"), ("openai", "api_key"), ("openai", "chatgpt_oauth")])
async def test_local_news_full_body_supports_finding_without_web_or_sec_requests(tmp_path, provider, auth):
    from src.lifecycle_investigation.agent import run_agent
    from src.lifecycle_investigation.news import LocalNews
    selected, credential, control = setup(auth, provider)
    calls = []
    async def model(call, credential, control):
        calls.append(call)
        assert call.phase == "analysis"
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        result = payload(material["sources"][0]["passages"])
        return completed(call, control, choose("conclude", finding=result))
    result = await run_agent(Target(ticker="OLD", as_of="2026-09-08"), credential, control,
        runtime=InvestigationRuntime(), effort="high", news=LocalNews(corpus(tmp_path, body=NOTICE), None), model=model)
    assert result["status"] == "succeeded", result
    assert result["validated"]["action"] == "terminal_delisting"
    assert len(calls) == result["stats"]["model_submissions"] == 1
    assert result["stats"]["http_requests"] == result["stats"]["web_actions"] == 0
    assert result["stats"]["output_tokens"] == 20


@pytest.mark.anyio
async def test_owned_invalid_output_is_recorded_then_corrected_without_new_search(tmp_path):
    from src.lifecycle_investigation.agent import run_agent
    from src.lifecycle_investigation.news import LocalNews
    _, credential, control = setup()
    events, calls = [], []
    async def model(call, credential, control):
        calls.append(call)
        if len(calls) == 1:
            return completed(call, control, "not JSON", error="model_output_invalid")
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        assert material["last_feedback"]["code"] == "model_output_invalid"
        return completed(call, control, choose("conclude", finding=payload(material["sources"][0]["passages"])))
    result = await run_agent(Target(ticker="OLD", as_of="2026-09-08"), credential, control,
        runtime=InvestigationRuntime(), effort="high", news=LocalNews(corpus(tmp_path, body=NOTICE), None), model=model,
        on_step=lambda kind, value: events.append((kind, value)))
    assert result["status"] == "succeeded"
    assert result["stats"]["model_submissions"] == 2
    assert any(kind == "rejected_output" and value["output"] == "not JSON" for kind, value in events)


@pytest.mark.anyio
async def test_malformed_action_shape_has_safe_field_feedback(tmp_path):
    from src.lifecycle_investigation.agent import run_agent
    from src.lifecycle_investigation.news import LocalNews
    _, credential, control = setup()
    calls = []
    async def model(call, credential, control):
        calls.append(call)
        if len(calls) == 1:
            return completed(call, control, choose([]))
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        assert material["last_feedback"]["action"] is None
        assert material["last_feedback"]["issues"] == [{"code": "literal_error", "field": "action"}]
        return completed(call, control, choose("conclude", finding=payload(material["sources"][0]["passages"])))
    result = await run_agent(Target(ticker="OLD", as_of="2026-09-08"), credential, control,
        runtime=InvestigationRuntime(), effort="high", news=LocalNews(corpus(tmp_path, body=NOTICE), None), model=model)
    assert result["status"] == "succeeded" and len(calls) == 2


@pytest.mark.anyio
async def test_grounding_feedback_preserves_candidate_for_targeted_correction(tmp_path):
    from src.lifecycle_investigation.agent import run_agent
    from src.lifecycle_investigation.news import LocalNews
    _, credential, control = setup()
    rejected, calls = {}, []
    async def model(call, credential, control):
        calls.append(call)
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        if len(calls) == 1:
            rejected.update(payload(material["sources"][0]["passages"]), effective_date="2026-09-02", effective_date_text="September 2, 2026")
            return completed(call, control, choose("conclude", finding=rejected))
        feedback = material["last_feedback"]
        assert feedback["block_reasons"] == ["effective_date_not_supported"]
        assert feedback["candidate"] == rejected
        corrected = {**feedback["candidate"], "effective_date": "2026-09-01", "effective_date_text": "September 1, 2026"}
        return completed(call, control, choose("conclude", finding=corrected))
    result = await run_agent(Target(ticker="OLD", as_of="2026-09-08"), credential, control,
        runtime=InvestigationRuntime(), effort="high", news=LocalNews(corpus(tmp_path, body=NOTICE), None), model=model)
    assert result["status"] == "succeeded" and len(calls) == 2
    assert result["validated"]["finding"]["citations"] == rejected["citations"]


@pytest.mark.anyio
async def test_fatal_transport_failure_never_retries_or_changes_billing(tmp_path):
    from src.lifecycle_investigation.agent import run_agent, AgentFailure
    from src.lifecycle_investigation.news import LocalNews
    selected, credential, control = setup()
    calls = []
    async def model(call, actual, control):
        calls.append(call)
        assert actual is credential and call.selection == selected
        raise WebModelError("provider_rate_limited")
    with pytest.raises(AgentFailure, match="provider_rate_limited"):
        await run_agent(Target(ticker="OLD", as_of="2026-09-08"), credential, control,
            runtime=InvestigationRuntime(), effort="high", news=LocalNews(None, None), model=model)
    assert len(calls) == 1


@pytest.mark.anyio
async def test_repeated_nonprogress_stops_without_fabricated_success():
    from src.lifecycle_investigation.agent import run_agent
    from src.lifecycle_investigation.news import LocalNews
    _, credential, control = setup()
    async def model(call, credential, control):
        return completed(call, control, choose("read_local", candidate_id="invented"))
    result = await run_agent(Target(ticker="OLD", as_of="2026-09-08"), credential, control,
        runtime=InvestigationRuntime(), effort="high", news=LocalNews(None, None), model=model)
    assert result["status"] == "incomplete"
    assert result["stop_reason"] == "investigation_no_progress"
    assert result["stats"]["model_submissions"] <= 4


@pytest.mark.parametrize("action,arguments", [
    ("read_url", {"url": "https://issuer.example/notice", "query": "common stock ceased"}),
    ("search_web", {"query": "OLD listing notice", "since": "2026-09-01", "until": "2026-09-08"}),
])
def test_action_schema_accepts_meaningful_read_queries_and_search_date_hints(action, arguments):
    from src.lifecycle_investigation.agent import Step
    step = Step.model_validate(choose(action, **arguments))
    for key, value in arguments.items():
        assert getattr(step, key) == value


@pytest.mark.parametrize("arguments,error", [
    ({"since": "yesterday"}, "action_date_invalid"),
    ({"until": "2026-9-8"}, "action_date_invalid"),
    ({"since": "2026-09-08", "until": "2026-09-01"}, "action_date_range_invalid"),
    ({"candidate_id": "irrelevant"}, "action_argument_unexpected"),
])
def test_action_date_hints_and_irrelevant_arguments_remain_validated(arguments, error):
    from src.lifecycle_investigation.agent import Step
    with pytest.raises(ValueError, match=error):
        Step.model_validate(choose("search_web", query="OLD listing", **arguments))


@pytest.mark.anyio
async def test_search_candidates_survive_rejected_action_and_read_query_is_consumed():
    from src.lifecycle_investigation.agent import run_agent
    from src.lifecycle_investigation.news import LocalNews
    _, credential, control = setup()
    url, unread = "https://issuer.example/notice", "https://issuer.example/other"
    calls, events, reads = [], [], []
    body = "\n".join(["OLD NASDAQ common stock navigation" for _ in range(1000)]) + "\n" + NOTICE.replace(
        "Trading in", "decisive_completion: Trading in")

    class Reader:
        request_count = 0
        def read(self, actual_url):
            self.request_count += 1
            reads.append(actual_url)
            return source_page(body, actual_url)
        def request_stop(self):
            pass

    async def model(call, actual, control):
        assert actual is credential
        calls.append(call)
        if len(calls) == 1:
            assert "read_url: required=url; optional=query" in call.prompt
            return completed(call, control, choose("search_web", query="OLD listing", since="2026-09-01", until="2026-09-08"))
        if call.phase == "search":
            hints = json.loads(call.prompt.split("\nMATERIAL\n")[1])
            if len(calls) == 2:
                assert hints["publication_window_hint"] == {"since": "2026-09-01", "until": "2026-09-08"}
                assert hints["already_read"] == []
                return completed(call, control, {"sources": [url, unread], "unresolved_conditions": []})
            assert hints["already_read"] == [url]
            assert {p["url"] for p in hints["observed_candidates"]} == {url, unread}
            return completed(call, control, {"sources": [], "unresolved_conditions": []})
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        assert {p["url"] for p in material["web_candidates"]} == {url, unread}
        if len(calls) == 3:
            return completed(call, control, choose("read_url", url=url, candidate_id="wrong_argument"))
        if len(calls) == 4:
            assert material["last_feedback"]["action"] == "read_url"
            assert material["last_feedback"]["issues"] == [{"code": "action_argument_unexpected", "field": "candidate_id"}]
            return completed(call, control, choose("read_url", url=url, query="decisive_completion"))
        passages = material["sources"][0]["passages"]
        assert all(set(p) == {"passage_id", "text"} for p in passages)
        assert any("decisive_completion" in p["text"] for p in passages)
        if len(calls) == 5:
            return completed(call, control, choose("search_web", query="OLD other notice"))
        assert len(calls) == 7
        identity = next(p for p in passages if "Issuer Old Inc" in p["text"])
        event = next(p for p in passages if "decisive_completion" in p["text"])
        return completed(call, control, choose("conclude", finding=payload([identity, event])))

    result = await run_agent(Target(ticker="OLD", as_of="2026-09-08"), credential, control,
        runtime=InvestigationRuntime(), effort="high", news=LocalNews(None, None), model=model,
        reader_factory=lambda limits: Reader(), on_step=lambda kind, value: events.append((kind, value)))
    assert result["status"] == "succeeded" and result["validated"]["action"] == "terminal_delisting", result
    assert len(calls) == result["stats"]["model_submissions"] == 7
    assert result["stats"]["http_requests"] == 1 and reads == [url]
    assert any(kind == "web_search" and value["sources"] == [url, unread] for kind, value in events)
