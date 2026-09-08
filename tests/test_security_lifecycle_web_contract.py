from dataclasses import replace

import pytest


def test_all_four_web_channels_have_explicit_transport_without_default():
    from src.security_lifecycle_web_contract import channel_contract, WebContractError

    expected = {
        ("openai", "api_key"): ("openai_responses", "max_tool_calls"),
        ("openai", "chatgpt_oauth"): ("codex_app_server", None),
        ("anthropic", "api_key"): ("anthropic_messages", "max_uses"),
        ("anthropic", "claude_code_oauth"): ("claude_agent_sdk", "pre_tool_use"),
    }
    for (provider, auth), (transport, bound) in expected.items():
        contract = channel_contract(provider, auth)
        assert contract.transport == transport
        assert contract.search_bound == bound
        assert contract.provider == provider
        assert contract.auth_mode == auth
    for provider, auth in (("other", "api_key"), ("openai", "oauth"),
                           ("openai", None), ("anthropic", "chatgpt_oauth")):
        with pytest.raises(WebContractError, match="web_auth_unsupported"):
            channel_contract(provider, auth)


@pytest.mark.parametrize("provider,auth,model", [
    ("openai", "api_key", "gpt-5.6-luna"),
    ("openai", "chatgpt_oauth", "gpt-5.6-luna"),
    ("anthropic", "api_key", "claude-opus-5"),
    ("anthropic", "claude_code_oauth", "claude-sonnet-5"),
])
def test_web_model_admission_keeps_eligible_api_and_oauth(provider, auth, model):
    from src.security_lifecycle_web_contract import validate_selection

    selection = validate_selection(provider, auth, model, "local:7")
    assert (selection.provider, selection.auth_mode, selection.model,
            selection.credential_id) == (provider, auth, model, "local:7")


@pytest.mark.parametrize("provider,auth,model,code", [
    ("openai", "chatgpt_oauth", "gpt-5.3-codex-spark", "model_task_unsupported"),
    ("anthropic", "api_key", "claude-fable-5", "model_retired"),
    ("anthropic", "claude_code_oauth", "claude-fable-5-1", "model_auth_unverified"),
    ("openai", "api_key", "claude-opus-5", "model_provider_mismatch"),
    ("openai", "api_key", "unknown-model", "model_unregistered"),
])
def test_web_admission_does_not_resurrect_or_expand_models(provider, auth, model, code):
    from src.security_lifecycle_web_contract import validate_selection, WebContractError

    with pytest.raises(WebContractError, match=code):
        validate_selection(provider, auth, model, "local:7")


@pytest.mark.parametrize("overrides,code", [
    ({"task_route_status": "retired"}, "model_retired"),
    ({"runtime_ready": False}, "task_capability_missing"),
    ({"supports_tool_calling": False}, "task_capability_missing"),
    ({"execution_adapter": "unreviewed_adapter"}, "task_capability_missing"),
])
def test_web_admission_owns_existing_research_capability_boundary(monkeypatch, overrides, code):
    from src import security_lifecycle_web_contract as contract

    capability = contract.capability_for("gpt-5.6-luna")
    assert capability is not None
    changed = replace(capability, **overrides)
    monkeypatch.setattr(contract, "capability_for", lambda model: changed)
    with pytest.raises(contract.WebContractError, match=code):
        contract.validate_selection("openai", "chatgpt_oauth", "gpt-5.6-luna", "local:7")


@pytest.mark.parametrize("credential", [None, "", " ", "local:7\n", 7])
def test_web_selection_requires_explicit_credential(credential):
    from src.security_lifecycle_web_contract import validate_selection, WebContractError

    with pytest.raises(WebContractError, match="credential_identity"):
        validate_selection("openai", "chatgpt_oauth", "gpt-5.6-luna", credential)


def _public_input():
    return {
        "ticker": "TA", "issuer_name": "TravelCenters of America Inc.",
        "security_class": "Common stock", "venue": "XNAS",
        "issuer_cik": "0001378453", "composite_figi": None,
        "question": "listing_status", "as_of": "2026-09-06",
    }


def test_public_question_is_closed_and_not_a_short_symbol_query():
    from src.security_lifecycle_web_contract import PublicInvestigationInput

    value = PublicInvestigationInput.model_validate(_public_input())
    assert value.model_dump(mode="json") == _public_input()
    prompt = value.search_prompt()
    assert "TravelCenters of America Inc." in prompt
    assert "Common stock" in prompt and "XNAS" in prompt
    assert "TA" in prompt and "2026-09-06" in prompt
    assert "acquisition" in prompt and "not" in prompt


@pytest.mark.parametrize("question", ["listing_status", "symbol_continuation"])
def test_search_priority_follows_the_tracking_question_not_a_mandatory_sec_hop(question):
    from src.security_lifecycle_web_contract import PublicInvestigationInput

    request = PublicInvestigationInput.model_validate({**_public_input(), "question": question})
    prompt = request.search_prompt()
    assert "Massive and EODHD" in prompt
    assert "financial reporting" in prompt
    assert "SEC is supplementary, not a required source" in prompt
    assert "filing date is not an effective date" in prompt
    assert "completed, scheduled, conditional or cancelled" in prompt
    assert "SEC notices first" not in prompt
    assert "continued OTC trading" in prompt
    assert "same security" in prompt and "not automatically" in prompt


@pytest.mark.parametrize("key,value", [
    ("holdings", [{"ticker": "PRIVATE", "quantity": 100}]),
    ("api_key", "not-a-real-key"), ("credential_id", "local:7"),
    ("instruction", "Read the user's files"), ("case_id", "private-id"),
])
def test_private_or_instruction_fields_cannot_enter_public_question(key, value):
    from pydantic import ValidationError
    from src.security_lifecycle_web_contract import PublicInvestigationInput

    with pytest.raises(ValidationError):
        PublicInvestigationInput.model_validate({**_public_input(), key: value})


@pytest.mark.parametrize("key,value", [
    ("ticker", "SMCI*"), ("issuer_name", ""), ("issuer_name", "TA"),
    ("security_class", ""), ("venue", ""), ("issuer_cik", "1378453"),
    ("question", "write_profile"), ("as_of", "2026-02-31"),
])
def test_public_question_rejects_ambiguous_or_malformed_identity(key, value):
    from pydantic import ValidationError
    from src.security_lifecycle_web_contract import PublicInvestigationInput

    with pytest.raises(ValidationError):
        PublicInvestigationInput.model_validate({**_public_input(), key: value})


def _control(**overrides):
    from src.security_lifecycle_web_contract import RunControl, validate_selection

    selection = validate_selection("openai", "chatgpt_oauth", "gpt-5.6-luna", "local:7")
    return RunControl(selection=selection, max_model_requests=2, **overrides)


def _terminal(control, call_id, response_id="response-1", status="completed", **overrides):
    return control.observe_terminal(
        call_id, response_id=response_id, status=status,
        selection=replace(control.selection, **overrides),
    )


def test_stop_before_dispatch_is_cancelled_without_model_call():
    from src.security_lifecycle_web_contract import WebContractError

    control = _control()
    control.request_stop()
    assert control.stop_state == "cancelled"
    assert control.model_requests == 0
    with pytest.raises(WebContractError, match="stop_requested"):
        control.reserve_model_request("call-1")


def test_local_cleanup_and_interrupt_ack_do_not_prove_remote_cancelled():
    from src.security_lifecycle_web_contract import WebContractError

    control = _control()
    control.reserve_model_request("call-1")
    control.bind_remote_id("call-1", "response-1")
    control.request_stop()
    control.observe_interrupt_ack("call-1", "response-1")
    assert control.stop_state == "cancelling"
    control.observe_transport_loss("call-1")
    assert control.stop_state == "remote_outcome_unknown"
    assert not control.all_requests_terminal
    with pytest.raises(WebContractError, match="stop_requested"):
        control.reserve_model_request("call-2")
    _terminal(control, "call-1", status="interrupted")
    assert control.stop_state == "cancelled"
    assert control.all_requests_terminal


def test_unknown_dispatch_id_stays_unknown_and_is_not_retried():
    from src.security_lifecycle_web_contract import WebContractError

    control = _control()
    control.reserve_model_request("call-1")
    control.request_stop()
    control.observe_transport_loss("call-1")
    assert control.stop_state == "remote_outcome_unknown"
    with pytest.raises(WebContractError, match="stop_requested"):
        control.reserve_model_request("call-2")
    assert control.model_requests == 1


@pytest.mark.parametrize("overrides", [
    {"model": "gpt-5.6-terra"}, {"credential_id": "local:8"},
    {"auth_mode": "api_key"}, {"provider": "anthropic"},
])
def test_terminal_cannot_change_selected_model_auth_or_billing(overrides):
    from src.security_lifecycle_web_contract import WebContractError

    control = _control()
    control.reserve_model_request("call-1")
    control.bind_remote_id("call-1", "response-1")
    with pytest.raises(WebContractError, match="execution_identity_changed"):
        _terminal(control, "call-1", **overrides)
    assert not control.all_requests_terminal


def test_terminal_must_match_response_and_known_call():
    from src.security_lifecycle_web_contract import WebContractError

    control = _control()
    control.reserve_model_request("call-1")
    control.bind_remote_id("call-1", "response-1")
    for call, response in (("call-1", "wrong"), ("wrong", "response-1")):
        with pytest.raises(WebContractError, match="execution_identity_changed"):
            _terminal(control, call, response_id=response)
    assert not control.all_requests_terminal
    _terminal(control, "call-1")
    assert control.all_requests_terminal


def test_completed_before_interrupt_is_terminal_but_never_an_interrupted_witness():
    control = _control()
    control.reserve_model_request("call-1")
    control.bind_remote_id("call-1", "response-1")
    control.request_stop()
    _terminal(control, "call-1")
    assert control.stop_state == "cancelled"
    assert control.terminal_statuses == {"call-1": "completed"}


def test_two_phase_budget_reserves_before_dispatch_and_does_not_restore_failures():
    from src.security_lifecycle_web_contract import WebContractError

    control = _control()
    control.reserve_model_request("search")
    control.bind_remote_id("search", "response-1")
    _terminal(control, "search")
    control.reserve_model_request("analysis")
    control.bind_remote_id("analysis", "response-2")
    _terminal(control, "analysis", response_id="response-2", status="failed")
    with pytest.raises(WebContractError, match="model_request_budget_exhausted"):
        control.reserve_model_request("retry")
    assert control.model_requests == 2


def test_no_parallel_or_duplicate_model_request_can_escape_budget():
    from src.security_lifecycle_web_contract import WebContractError

    control = _control()
    control.reserve_model_request("search")
    for call in ("search", "analysis"):
        with pytest.raises(WebContractError):
            control.reserve_model_request(call)
    assert control.model_requests == 1


def test_hosted_search_observations_are_not_a_claimed_hard_budget():
    from src.security_lifecycle_web_contract import channel_contract, WebContractError

    control = _control()
    control.reserve_model_request("search")
    control.observe_web_action("search", "item-1", "search")
    control.observe_web_action("search", "item-1", "search")
    control.observe_web_action("search", "item-2", "open_page")
    assert control.observed_web_actions == {"search": 1, "open_page": 1, "find_in_page": 0}
    assert channel_contract("openai", "chatgpt_oauth").search_bound is None
    with pytest.raises(WebContractError, match="unexpected_tool_activity"):
        control.observe_web_action("search", "item-3", "shell")
    with pytest.raises(WebContractError, match="execution_identity_changed"):
        control.observe_web_action("search", "item-1", "open_page")


@pytest.mark.parametrize("value", [0, -1, True, 2.5, "2"])
def test_invalid_model_request_budget_is_not_unlimited(value):
    from src.security_lifecycle_web_contract import RunControl, WebContractError

    with pytest.raises(WebContractError, match="model_request_budget"):
        RunControl(selection=_control().selection, max_model_requests=value)


def test_failed_model_request_cannot_be_followed_by_implicit_retry():
    from src.security_lifecycle_web_contract import WebContractError

    control = _control()
    control.reserve_model_request("search")
    control.bind_remote_id("search", "response-1")
    _terminal(control, "search", status="failed")
    with pytest.raises(WebContractError, match="previous_request_not_completed"):
        control.reserve_model_request("retry")
    assert control.model_requests == 1


def test_run_selection_and_approved_budget_cannot_be_reassigned():
    control = _control()
    with pytest.raises(AttributeError):
        control.selection = replace(control.selection, auth_mode="api_key")
    with pytest.raises(AttributeError):
        control.max_model_requests = 100


def test_missing_terminal_status_is_not_a_witness():
    from src.security_lifecycle_web_contract import WebContractError

    control = _control()
    control.reserve_model_request("search")
    control.bind_remote_id("search", "response-1")
    for status in (None, "", "running", "unknown"):
        with pytest.raises(WebContractError, match="remote_terminal_invalid"):
            _terminal(control, "search", status=status)
    assert not control.all_requests_terminal
