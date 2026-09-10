import asyncio
from copy import deepcopy
import json
from threading import Event

import pytest

from src.auth_drivers.lifecycle_web_models import WebCredential, WebModelError
from src.lifecycle_investigation.controller import InvestigationController
from src.lifecycle_investigation.news import LocalNews
from tests.test_lifecycle_investigation_store import running
from tests.lifecycle_investigation_fixtures import CHANNELS, controller, wait_done


def test_current_controller_owns_workers_without_a_legacy_execution_base():
    import ast
    import inspect
    from src.lifecycle_investigation import controller

    assert InvestigationController.__bases__ == (object,)
    imports = [node.module for node in ast.walk(ast.parse(inspect.getsource(controller)))
               if isinstance(node, ast.ImportFrom)]
    assert "src.lifecycle_web_controller" not in imports
    for method in ("start", "cancel", "close", "is_local_running"):
        assert method in InvestigationController.__dict__


@pytest.mark.parametrize("changed", ("cancel", "credential", "permission"))
def test_pre_dispatch_rereads_stop_identity_and_permission_after_credential_load(tmp_path, changed):
    _, store, initial, binding = running(tmp_path)
    store.finish(initial, owner="worker", status="failed")
    loading, release, invoked = Event(), Event(), []
    permit = [True]

    def before_dispatch():
        if not permit[0]:
            raise ValueError("writes_disabled")

    def load(selection):
        loading.set()
        assert release.wait(5)
        return WebCredential(selection, generation="changed" if changed == "credential" else "generation-1")

    async def runner(*args, **kwargs):
        invoked.append(True)
        raise AssertionError("Must stop before the agent or provider is invoked")

    controller = InvestigationController(store, credential_loader=load, news_factory=lambda: LocalNews(None, None),
        before_dispatch=before_dispatch, runner=runner, heartbeat_seconds=.02)
    job = controller.start(binding=binding, request_key="second-click")
    assert loading.wait(5)
    if changed == "cancel":
        controller.cancel(job["run_id"])
    if changed == "permission":
        permit[0] = False
    with controller._lock:
        thread = controller._workers[job["run_id"]].thread
    release.set()
    thread.join(5)
    assert not thread.is_alive()
    row = store.read(job["run_id"])
    assert invoked == []
    assert row["status"] == ("cancelled" if changed == "cancel" else "failed")
    assert row["calls"] == []
    controller.close()


@pytest.mark.parametrize("provider,auth", CHANNELS)
def test_current_worker_preserves_four_channel_identity_and_provider_free_readback(tmp_path, provider, auth):
    service, store, loads, binding = controller(tmp_path)
    binding["selection"].update(provider=provider, auth_mode=auth,
        model="gpt-5.6-luna" if provider == "openai" else "claude-sonnet-5")
    try:
        job = service.start(binding=binding, request_key="current-click")
        result = wait_done(service, job["run_id"])
        assert result["status"] == "succeeded", result
        assert result["execution"] == {"provider": provider, "auth_mode": auth,
            "model": binding["selection"]["model"], "effort": "high"}
        assert result["stats"]["model_submissions"] == 1
        assert result["stats"]["input_tokens"] == 10 and result["stats"]["output_tokens"] == 20
        assert result["action"] == "terminal_delisting" and result["passages"]
        assert store.read(job["run_id"])["calls"][0]["terminal"] == "completed"
        for _ in range(3):
            assert service.read(job["run_id"]) == result
            assert service.latest("OLD") == result
        assert len(loads) == 1 and loads[0].__dict__ == binding["selection"]
        assert all(value not in json.dumps(result) for value in ("synthetic-private", "local:7", "header_json", "owner"))
    finally:
        service.close()


def test_replayed_current_start_is_durable_across_controllers_without_redispatch(tmp_path):
    service, store, loads, binding = controller(tmp_path)
    try:
        first = service.start(binding=binding, request_key="current-click")
        wait_done(service, first["run_id"])
        assert service.start(binding=binding, request_key="current-click") == {"run_id": first["run_id"], "created": False}
        reopened = InvestigationController(store, credential_loader=lambda _: pytest.fail("replay dispatched"), news_factory=lambda: None)
        try:
            assert reopened.start(binding=binding, request_key="current-click") == {"run_id": first["run_id"], "created": False}
            changed = deepcopy(binding)
            changed["effort"] = "medium"
            with pytest.raises(ValueError, match="^investigation_request_changed$"):
                reopened.start(binding=changed, request_key="current-click")
        finally:
            reopened.close()
        assert len(loads) == 1 and len(store.read(first["run_id"])["calls"]) == 1
    finally:
        service.close()


def test_current_worker_has_two_slots_and_no_pending_journal_queue(tmp_path):
    entered, release = Event(), Event()

    def load(selected):
        entered.set()
        assert release.wait(5)
        return WebCredential(selected, generation="generation-1")

    service, store, loads, binding = controller(tmp_path, loader=load)
    try:
        first = service.start(binding=binding, request_key="first")
        assert entered.wait(5)
        other = deepcopy(binding)
        other["target"]["ticker"] = "LIVE"
        second = service.start(binding=other, request_key="second")
        third = deepcopy(binding)
        third["target"]["ticker"] = "THIRD"
        with pytest.raises(WebModelError, match="^web_worker_busy$"):
            service.start(binding=third, request_key="third")
        with store.connection() as conn:
            assert conn.execute("SELECT COUNT(*) FROM lifecycle_investigation_jobs WHERE status='running'").fetchone()[0] == 2
        assert store.latest("THIRD") is None
        service.cancel(first["run_id"])
        service.cancel(second["run_id"])
    finally:
        release.set()
        service.close()
    assert len(loads) <= 2


@pytest.mark.parametrize("seconds", [0, -1, 30, float("inf"), float("nan")])
def test_current_worker_rejects_unbounded_or_invalid_heartbeat_interval(seconds):
    with pytest.raises(ValueError, match="^web_heartbeat_interval$"):
        InvestigationController(None, credential_loader=lambda _: None, news_factory=lambda: None, heartbeat_seconds=seconds)


def test_thread_start_failure_records_failure_and_releases_the_slot(tmp_path, monkeypatch):
    from threading import Thread
    service, store, loads, binding = controller(tmp_path)

    def unavailable(_):
        raise RuntimeError("thread unavailable")

    monkeypatch.setattr(Thread, "start", unavailable)
    try:
        with pytest.raises(RuntimeError, match="thread unavailable"):
            service.start(binding=binding, request_key="current-click")
        result = service.latest("OLD")
        assert result["status"] == "failed" and result["failure_code"] == "web_worker_unavailable"
        assert not service.is_local_running(result["run_id"]) and loads == []
        assert store.read(result["run_id"])["calls"] == []
    finally:
        service.close()


def test_current_credential_failure_is_sanitized_without_transport_fallback(tmp_path):
    def unavailable(_):
        raise RuntimeError("key=private-provider-secret")

    service, store, loads, binding = controller(tmp_path, loader=unavailable)
    try:
        result = wait_done(service, service.start(binding=binding, request_key="current-click")["run_id"])
        assert result["status"] == "failed" and result["failure_code"] == "web_execution_failed"
        assert len(loads) == 1 and store.read(result["run_id"])["calls"] == []
        assert "private-provider" not in json.dumps(result)
    finally:
        service.close()


@pytest.mark.parametrize("terminal", [False, True])
def test_current_cancel_requires_remote_terminal_not_just_interrupt_ack(tmp_path, terminal):
    entered = Event()

    async def runner(target, credential, control, **kwargs):
        control.reserve_model_request("owned-call")
        control.bind_remote_id("owned-call", "owned-remote")
        entered.set()
        while control.stop_state == "running":
            await asyncio.sleep(.01)
        control.observe_interrupt_ack("owned-call", "owned-remote")
        if terminal:
            control.observe_terminal("owned-call", response_id="owned-remote", status="interrupted", selection=control.selection)
        else:
            control.observe_transport_loss("owned-call")
        raise WebModelError("stop_requested")

    service, store, loads, binding = controller(tmp_path, runner=runner)
    try:
        identity = service.start(binding=binding, request_key="current-click")["run_id"]
        assert entered.wait(5)
        service.cancel(identity)
        result = wait_done(service, identity)
        assert result["status"] == ("cancelled" if terminal else "remote_outcome_unknown")
        assert result["stats"]["model_submissions"] == 1 and len(loads) == 1
        assert [call["call_id"] for call in store.read(identity)["calls"]] == ["owned-call"]
    finally:
        service.close()


@pytest.mark.parametrize("command", ["cancel", "close"])
def test_current_stop_precedes_failed_cancel_write_and_shutdown_joins(tmp_path, monkeypatch, command):
    entered, stopped = Event(), Event()

    async def runner(target, credential, control, **kwargs):
        control.reserve_model_request("owned-call")
        entered.set()
        while control.stop_state == "running":
            await asyncio.sleep(.01)
        stopped.set()
        raise WebModelError("stop_requested")

    service, store, _, binding = controller(tmp_path, runner=runner)
    identity = service.start(binding=binding, request_key="current-click")["run_id"]
    assert entered.wait(5)
    worker = service._workers[identity]

    def unavailable(_):
        assert worker.control.stop_state != "running", "local stop must precede the journal write"
        raise ValueError("investigation_recording_unavailable")

    monkeypatch.setattr(store, "request_cancel", unavailable)
    try:
        if command == "cancel":
            with pytest.raises(ValueError, match="^investigation_recording_unavailable$"):
                service.cancel(identity)
        else:
            service.close()
            assert not worker.thread.is_alive()
        result = wait_done(service, identity)
        assert stopped.is_set() and result["status"] == "remote_outcome_unknown"
        assert store.read(identity)["cancel_requested_at"] is None
        service.close()
        with pytest.raises(WebModelError, match="^web_worker_unavailable$"):
            service.start(binding=binding, request_key="after-close")
    finally:
        worker.control.request_stop()
        worker.thread.join(5)
        service.close()
        assert not worker.thread.is_alive()


def test_current_permission_is_rechecked_at_each_agent_step(tmp_path):
    permit, entered = [True], []

    def boundary():
        if not permit[0]:
            raise WebModelError("web_write_disabled")

    async def runner(target, credential, control, *, on_step, **kwargs):
        on_step("searching", {})
        permit[0] = False
        on_step("analyzing", {})
        entered.append("model")
        raise AssertionError("revoked permission must prevent further dispatch")

    service, store, _, binding = controller(tmp_path, runner=runner, before_dispatch=boundary)
    try:
        result = wait_done(service, service.start(binding=binding, request_key="current-click")["run_id"])
        row = store.read(result["run_id"])
        assert result["status"] == "failed" and result["failure_code"] == "web_write_disabled"
        assert [step["kind"] for step in row["steps"]] == ["searching"]
        assert row["calls"] == [] and entered == []
    finally:
        service.close()


def test_current_progress_reads_skip_source_bodies_and_do_not_redispatch(tmp_path, monkeypatch):
    from src.lifecycle_investigation import store as journal
    _, store, identity, _ = running(tmp_path)
    source = {"text": "retained source body"}
    store.source(identity, owner="worker", source_id="source-1", payload=source)
    original = journal._decoded

    def decode(raw, digest):
        assert "retained source body" not in raw, "progress must not decode source bodies"
        return original(raw, digest)

    monkeypatch.setattr(journal, "_decoded", decode)
    service = InvestigationController(store, credential_loader=lambda _: pytest.fail("read dispatched"), news_factory=lambda: None)
    try:
        assert service.read(identity)["status"] == "running"
        assert service.latest("OLD")["run_id"] == identity
    finally:
        service.close()


def test_current_restart_read_is_nonwriting_and_recovery_does_not_redispatch(tmp_path):
    c, store, identity, _ = running(tmp_path)
    store.reserve_call(identity, owner="worker", call_id="owned-call")
    c["now"][0] = "2026-09-09T00:00:00Z"
    service = InvestigationController(store, credential_loader=lambda _: pytest.fail("read dispatched"), news_factory=lambda: None)
    try:
        assert service.read(identity)["status"] == "remote_outcome_unknown"
        assert store.read(identity)["status"] == "running"
        service.reconcile()
        assert store.read(identity)["status"] == "remote_outcome_unknown"
    finally:
        service.close()


def test_current_lease_failure_signals_remote_cleanup(tmp_path, monkeypatch):
    entered, stopped = Event(), Event()

    async def runner(target, credential, control, **kwargs):
        control.reserve_model_request("owned-call")
        entered.set()
        while control.stop_state == "running":
            await asyncio.sleep(.01)
        stopped.set()
        control.observe_transport_loss("owned-call")
        raise WebModelError("stop_requested")

    service, store, _, binding = controller(tmp_path, runner=runner, heartbeat_seconds=.02)
    try:
        identity = service.start(binding=binding, request_key="current-click")["run_id"]
        assert entered.wait(5)
        def unavailable(*args, **kwargs):
            raise ValueError("investigation_recording_unavailable")
        monkeypatch.setattr(store, "heartbeat", unavailable)
        result = wait_done(service, identity)
        assert stopped.is_set() and result["status"] == "remote_outcome_unknown"
    finally:
        service.close()
