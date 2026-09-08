import asyncio
from dataclasses import replace
import json
import threading
import time

import pytest

from src.auth_drivers.lifecycle_web_models import WebCredential, WebModelError
from src.security_lifecycle_web_contract import validate_selection
from tests.test_lifecycle_web_store import AT, setup_store
from tests.test_security_lifecycle_web_finding import NOTICE, finding_payload, public_input, source_page
from tests.test_security_lifecycle_web_pipeline import _options


def selection(provider="openai", auth="api_key"):
    return validate_selection(provider, auth, "gpt-5.6-luna" if provider == "openai" else "claude-sonnet-5", "local:7")


async def completed_runner(request, credential, control, *, options, on_stage, on_source, **kwargs):
    from src.security_lifecycle_web_pipeline import InvestigationResult
    from src.security_lifecycle_web_finding import validate_finding

    page = source_page(NOTICE)
    on_stage("searching")
    control.reserve_model_request("search-1")
    control.bind_remote_id("search-1", "remote-search")
    control.observe_terminal("search-1", response_id="remote-search", status="completed", selection=control.selection)
    on_stage("reading_sources")
    on_source("source-1", page)
    on_stage("analyzing")
    control.reserve_model_request("analysis-1")
    control.bind_remote_id("analysis-1", "remote-analysis")
    control.observe_terminal("analysis-1", response_id="remote-analysis", status="completed", selection=control.selection)
    on_stage("completed")
    finding = validate_finding(request, finding_payload(), {"source-1": page})
    return InvestigationResult(finding, {"source-1": page}, {}, 1, (), {"input_tokens": 100, "output_tokens": 80})


def controller(tmp_path, *, loader=None, runner=completed_runner, **kwargs):
    from src.lifecycle_web_controller import LifecycleWebController

    _, store = setup_store(tmp_path)
    calls = []
    def load(selected):
        calls.append(selected)
        if loader:
            return loader(selected)
        return WebCredential(selected, api_key="never-export-this-key")
    service = LifecycleWebController(store, credential_loader=load, runner=runner, **kwargs)
    return service, store, calls


def launch(service, *, selected=None, key="click-1"):
    selected = selected or selection()
    return service.start(case_id="case-1", observation_sha256="a" * 64, request=public_input(),
                         selection=selected, options=_options(selected.auth_mode), request_key=key)


def wait_done(service, identity):
    deadline = time.monotonic() + 4
    while service.is_local_running(identity) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not service.is_local_running(identity), "local worker did not terminate"
    return service.read(identity)


@pytest.mark.parametrize("provider,auth", [("openai", "api_key"), ("openai", "chatgpt_oauth"),
                                          ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")])
def test_web_controller_preserves_four_channel_provenance_and_read_is_provider_free(tmp_path, provider, auth):
    service, store, calls = controller(tmp_path)
    selected = selection(provider, auth)
    try:
        run = launch(service, selected=selected)
        result = wait_done(service, run["run_id"])
        assert result["status"] == "succeeded"
        assert result["execution"] == {"provider": provider, "auth_mode": auth, "model": selected.model}
        assert result["model_submissions"] == 2 and result["usage"] == {"input_tokens": 100, "output_tokens": 80}
        assert result["finding"]["action"] == "terminal_delisting"
        assert result["finding"]["citations"][0]["quote"] == NOTICE
        for _ in range(3):
            assert service.read(run["run_id"]) == result
            assert service.latest("case-1")["run_id"] == run["run_id"]
        assert calls == [selected]
        encoded = json.dumps(result)
        assert all(word not in encoded for word in ("never-export", "local:7", "remote-search", "header_json", "owner"))
        assert store.read(run["run_id"])["finding"].action == "terminal_delisting"
    finally:
        service.close()


def test_replayed_start_does_not_reload_credential_or_repeat_model_work(tmp_path):
    service, _, calls = controller(tmp_path)
    try:
        first = launch(service)
        wait_done(service, first["run_id"])
        repeated = launch(service)
        assert repeated == {"run_id": first["run_id"], "created": False}
        assert len(calls) == 1
    finally:
        service.close()


def test_credential_failure_does_not_try_another_transport_or_expose_exception(tmp_path):
    def bad(selected):
        raise RuntimeError("key=sensitive-private-value")
    service, _, calls = controller(tmp_path, loader=bad)
    try:
        run = launch(service)
        result = wait_done(service, run["run_id"])
        assert result["status"] == "failed" and result["failure_code"] == "web_execution_failed"
        assert result["model_submissions"] == 0 and len(calls) == 1
        assert "sensitive" not in json.dumps(result)
    finally:
        service.close()


def test_changed_credential_generation_is_rejected_before_model_reservation(tmp_path):
    service, _, calls = controller(tmp_path, loader=lambda selected: WebCredential(selected, api_key="new-key", generation="b" * 64))
    try:
        run = service.start(case_id="case-1", observation_sha256="a" * 64, request=public_input(),
                            selection=selection(), options=_options("api_key"), request_key="click-1",
                            credential_generation="a" * 64)
        result = wait_done(service, run["run_id"])
        assert result["status"] == "failed" and result["failure_code"] == "selected_credential_changed"
        assert result["model_submissions"] == 0 and len(calls) == 1
    finally:
        service.close()


def test_stop_during_oauth_refresh_prevents_late_model_dispatch(tmp_path):
    entered, release = threading.Event(), threading.Event()
    calls = []
    def load(selected):
        entered.set()
        assert release.wait(2)
        return WebCredential(selected)
    async def unexpected(*args, **kwargs):
        calls.append("model")
        return await completed_runner(*args, **kwargs)
    service, _, _ = controller(tmp_path, loader=load, runner=unexpected)
    try:
        run = launch(service, selected=selection("openai", "chatgpt_oauth"))
        assert entered.wait(2)
        service.cancel(run["run_id"])
        release.set()
        result = wait_done(service, run["run_id"])
        assert result["status"] == "cancelled" and result["model_submissions"] == 0 and calls == []
    finally:
        release.set()
        service.close()


@pytest.mark.parametrize("observe_terminal", [False, True])
def test_cancel_requires_real_terminal_and_does_not_dispatch_analysis(tmp_path, observe_terminal):
    entered = threading.Event()
    async def runner(request, credential, control, **kwargs):
        control.reserve_model_request("search-1")
        control.bind_remote_id("search-1", "remote-search")
        entered.set()
        while control.stop_state == "running":
            await asyncio.sleep(0.01)
        control.observe_interrupt_ack("search-1", "remote-search")
        if observe_terminal:
            control.observe_terminal("search-1", response_id="remote-search", status="interrupted", selection=control.selection)
        else:
            control.observe_transport_loss("search-1")
        raise WebModelError("stop_requested")
    service, store, calls = controller(tmp_path, runner=runner)
    try:
        run = launch(service)
        assert entered.wait(2)
        service.cancel(run["run_id"])
        result = wait_done(service, run["run_id"])
        assert result["status"] == ("cancelled" if observe_terminal else "remote_outcome_unknown")
        assert result["model_submissions"] == 1 and len(calls) == 1
        assert list(store.read(run["run_id"])["calls"]) == ["search-1"]
    finally:
        service.close()


def test_write_authority_is_reread_before_each_dispatch_stage(tmp_path):
    checks = []
    def boundary():
        checks.append(True)
        if len(checks) >= 3:
            raise WebModelError("web_write_disabled")
    service, store, _ = controller(tmp_path, before_dispatch=boundary)
    try:
        run = launch(service)
        result = wait_done(service, run["run_id"])
        assert result["status"] == "failed" and result["failure_code"] == "web_write_disabled"
        assert result["model_submissions"] <= 1
        assert "analysis-1" not in store.read(run["run_id"])["calls"]
    finally:
        service.close()


def test_restart_read_reports_expired_lease_without_restarting_or_spending(tmp_path):
    from src.lifecycle_web_controller import LifecycleWebController
    from tests.test_lifecycle_web_store import start

    _, store = setup_store(tmp_path)
    run = start(store)
    control = store.control(run["run_id"], owner="worker-1")
    control.reserve_model_request("search-1")
    store.clock = lambda: "2026-09-06T01:02:00+00:00"
    calls = []
    service = LifecycleWebController(store, credential_loader=lambda *args: calls.append(args))
    try:
        result = service.read(run["run_id"])
        assert result["status"] == "remote_outcome_unknown"
        assert result["failure_code"] == "web_execution_interrupted" and calls == []
        assert store.read(run["run_id"])["status"] == "queued", "read must not write or dispatch"
        service.reconcile()
        assert store.read(run["run_id"])["status"] == "remote_outcome_unknown" and calls == []
    finally:
        service.close()


def test_lease_failure_stops_remote_work_instead_of_silently_losing_observability(tmp_path, monkeypatch):
    from src.lifecycle_web_store import WebJournalError
    entered = threading.Event()
    async def runner(request, credential, control, **kwargs):
        control.reserve_model_request("search-1")
        control.bind_remote_id("search-1", "remote-search")
        entered.set()
        while control.stop_state == "running":
            await asyncio.sleep(0.01)
        control.observe_transport_loss("search-1")
        raise WebModelError("stop_requested")
    service, store, _ = controller(tmp_path, runner=runner, heartbeat_seconds=0.03)
    try:
        run = launch(service)
        assert entered.wait(2)
        def fail(*args, **kwargs):
            raise WebJournalError("web_recording_unavailable")
        monkeypatch.setattr(store, "heartbeat", fail)
        result = wait_done(service, run["run_id"])
        assert result["status"] == "remote_outcome_unknown"
        assert result["failure_code"] == "web_recording_unavailable"
    finally:
        service.close()


def test_shutdown_still_joins_worker_when_cancellation_recording_is_unavailable(tmp_path, monkeypatch):
    from src.lifecycle_web_store import WebJournalError
    entered = threading.Event()
    async def runner(request, credential, control, **kwargs):
        control.reserve_model_request("search-1")
        entered.set()
        while control.stop_state == "running":
            await asyncio.sleep(0.01)
        raise WebModelError("stop_requested")
    service, store, _ = controller(tmp_path, runner=runner)
    run = launch(service)
    assert entered.wait(2)
    def unavailable(*args, **kwargs):
        raise WebJournalError("web_recording_unavailable")
    monkeypatch.setattr(store, "request_cancel", unavailable)
    worker = service._workers[run["run_id"]]
    try:
        service.close()
        assert not service.is_local_running(run["run_id"])
        assert service.read(run["run_id"])["status"] == "remote_outcome_unknown"
    finally:
        # Ensure even a failing RED assertion does not leave a background worker.
        worker.control.request_stop()
        worker.thread.join(5)
        assert not worker.thread.is_alive()
