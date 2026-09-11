"""The current investigation must not retain an abandoned executable journal."""

from pathlib import Path
from contextlib import contextmanager
import json
import sqlite3
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["store", "review", "projection"])
def test_abandoned_case_journal_module_is_absent(name):
    assert not (ROOT / f"src/lifecycle_web_{name}.py").exists()


def test_current_review_has_its_own_module():
    assert (ROOT / "src/lifecycle_investigation/review.py").is_file()


@pytest.mark.parametrize("name", ["phase_usage", "validate_usage_report", "project_usage_report", "USAGE_COVERAGE"])
def test_obsolete_two_phase_usage_report_is_absent(name):
    from src.auth_drivers import lifecycle_web_usage

    assert not hasattr(lifecycle_web_usage, name)


@pytest.mark.parametrize("mutation", [None, "request_count", "headers", "credential_url"])
def test_current_reopened_source_diagnostics_use_the_report_validator(tmp_path, mutation):
    from src.lifecycle_journal_codec import canonical_json, digest_json
    from tests.test_lifecycle_investigation_review import context

    c = context(tmp_path)
    payload = {"url": "https://issuer.example/notice", "http_requests": 1, "observations": [
        {"request_index": 1, "status": 403, "framing": None, "content_encoding": None,
         "declared_body_bytes": None, "received_body_bytes": 0, "decoded_body_bytes": 0,
         "result_code": "source_unavailable"}]}
    if mutation == "request_count":
        payload["http_requests"] = True
    elif mutation == "headers":
        payload["observations"][0]["headers"] = {"Authorization": "fixture-secret"}
    elif mutation == "credential_url":
        payload["url"] = "https://user:fixture-secret@issuer.example/notice"
    with sqlite3.connect(c["profile"]) as conn:
        ordinal = conn.execute("SELECT MAX(ordinal)+1 FROM lifecycle_investigation_steps WHERE run_id=?", (c["run_id"],)).fetchone()[0]
        conn.execute("INSERT INTO lifecycle_investigation_steps VALUES(?,?,?,?,?,?)",
            (c["run_id"], ordinal, "source_read", canonical_json(payload), digest_json(payload), c["now"][0]))
    if mutation is None:
        row = c["investigation"].read(c["run_id"], include_sources=False)
        assert row["steps"][-1]["payload"] == payload
    else:
        with pytest.raises(ValueError, match="^investigation_integrity$"):
            c["investigation"].read(c["run_id"], include_sources=False)


@pytest.mark.parametrize("interruption", ["none", "cancel", "deadline", "recording_failure"])
def test_completed_reply_interruption_keeps_truthful_readable_usage(tmp_path, monkeypatch, interruption):
    from src.lifecycle_investigation.agent import run_agent
    from src.lifecycle_investigation.store import InvestigationStore
    from tests.lifecycle_investigation_fixtures import controller
    from tests.test_lifecycle_investigation_agent import choose, completed
    from tests.test_lifecycle_investigation_findings import payload

    ticks = [0.0]

    async def model(call, credential, control):
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        reply = completed(call, control, choose("conclude", finding=payload(material["sources"][0]["passages"])))
        if interruption == "cancel":
            service.cancel(control.run_id)
        elif interruption == "deadline":
            ticks[0] = binding["runtime"]["deadline_seconds"] + 1
        return reply

    async def runner(*args, **kwargs):
        return await run_agent(*args, **kwargs, model=model, monotonic=lambda: ticks[0])

    service, store, loads, binding = controller(tmp_path, runner=runner)
    original_step = store.step

    def step(*args, **kwargs):
        if interruption == "recording_failure" and kwargs["kind"] == "model_result":
            raise ValueError("investigation_recording_unavailable")
        return original_step(*args, **kwargs)

    monkeypatch.setattr(store, "step", step)
    try:
        identity = service.start(binding=binding, request_key="completed-interruption")["run_id"]
        until = time.monotonic() + 5
        while service.is_local_running(identity) and time.monotonic() < until:
            time.sleep(0.01)
        assert not service.is_local_running(identity)
        status = {"none": "succeeded", "cancel": "cancelled", "deadline": "incomplete", "recording_failure": "failed"}[interruption]
        row = InvestigationStore(store.path).read(identity, include_sources=False)
        assert row["status"] == status
        assert row["calls"] == [{"call_id": "step-1", "remote_id": "step-1", "terminal": "completed"}]
        results = [step for step in row["steps"] if step["kind"] == "model_result"]
        assert len(results) == (0 if interruption == "recording_failure" else 1)
        assert (row["result"] is None) is (interruption == "recording_failure")
        stats = service.read(identity)["stats"]
        assert stats["model_submissions"] == 1
        assert (stats["input_tokens"], stats["output_tokens"]) == ((None, None) if interruption == "recording_failure" else (10, 20))
        assert service.read(identity)["status"] == status
        assert service.latest("OLD")["run_id"] == identity
        assert len(loads) == 1 and not row["adopted"]
    finally:
        service.close()


@pytest.mark.parametrize("boundary", ["source", "model_result", "agent_action"])
@pytest.mark.parametrize("failure", ["none", "before_commit", "after_commit"])
def test_journal_ack_failure_stops_without_inventing_a_result(tmp_path, monkeypatch, boundary, failure):
    from src.lifecycle_investigation.agent import run_agent
    from tests.lifecycle_investigation_fixtures import controller
    from tests.test_lifecycle_investigation_agent import choose, completed
    from tests.test_lifecycle_investigation_findings import payload

    dispatched = []

    async def model(call, credential, control):
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        reply = completed(call, control, choose("conclude", finding=payload(material["sources"][0]["passages"])))
        dispatched.append(call.call_id)
        return reply

    async def runner(*args, **kwargs):
        return await run_agent(*args, **kwargs, model=model)

    service, store, loads, binding = controller(tmp_path, runner=runner)
    method = "source" if boundary == "source" else "step"
    original = getattr(store, method)

    def write(*args, **kwargs):
        selected = boundary == "source" or kwargs["kind"] == boundary
        if selected and failure == "before_commit":
            raise ValueError("investigation_recording_unavailable")
        original(*args, **kwargs)
        if selected and failure == "after_commit":
            raise ValueError("investigation_recording_unavailable")

    monkeypatch.setattr(store, method, write)
    try:
        identity = service.start(binding=binding, request_key="journal-acknowledgement")["run_id"]
        until = time.monotonic() + 5
        while service.is_local_running(identity) and time.monotonic() < until:
            time.sleep(0.01)
        assert not service.is_local_running(identity)
        row = store.read(identity)
        no_dispatch = boundary == "source" and failure != "none"
        assert dispatched == ([] if no_dispatch else ["step-1"])
        assert len(row["calls"]) == (0 if no_dispatch else 1)
        if row["calls"]:
            assert row["calls"][0]["terminal"] == "completed"
        records = row["sources"] if boundary == "source" else [step for step in row["steps"] if step["kind"] == boundary]
        assert bool(records) is (failure != "before_commit")
        assert row["status"] == ("succeeded" if failure == "none" else "failed")
        assert (row["result"] is None) is (failure != "none")
        view = service.read(identity)
        tokens = (10, 20) if failure == "none" else (None, None)
        assert (view["stats"]["input_tokens"], view["stats"]["output_tokens"]) == tokens
        if failure != "none":
            assert view["failure_code"] == "investigation_recording_unavailable"
            assert view["action"] is None and view["finding"] is None
        assert service.latest("OLD")["run_id"] == identity
        assert len(loads) == 1 and not row["adopted"]
    finally:
        service.close()


@pytest.mark.parametrize("outcome", ["completed", "pending"])
@pytest.mark.parametrize("stats_unavailable", [False, True])
def test_final_stats_read_failure_never_redispatches_or_invents_usage(tmp_path, monkeypatch, outcome, stats_unavailable):
    from src.auth_drivers.lifecycle_web_models import WebModelError
    from src.lifecycle_investigation.agent import run_agent
    from tests.lifecycle_investigation_fixtures import controller
    from tests.test_lifecycle_investigation_agent import choose, completed
    from tests.test_lifecycle_investigation_findings import payload

    state = {"stats_phase": False, "reads": 0}
    entries = []

    async def model(call, credential, control):
        entries.append(call.call_id)
        if outcome == "completed":
            material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
            reply = completed(call, control, choose("conclude", finding=payload(material["sources"][0]["passages"])))
        else:
            control.reserve_model_request(call.call_id)
        state["stats_phase"] = True
        before_polling = state["reads"]
        for _ in range(32):
            assert control.model_requests == len(entries)
            assert control.max_model_requests == binding["runtime"]["model_submissions"]
            assert control.stop_state == "running"
            assert control.selection == credential.selection
            control.terminal_statuses
        assert state["reads"] == before_polling
        if outcome == "pending":
            raise WebModelError("provider_call_failed")
        return reply

    async def runner(*args, **kwargs):
        return await run_agent(*args, **kwargs, model=model)

    service, store, loads, binding = controller(tmp_path, runner=runner)
    original = store.connection

    @contextmanager
    def connection(*, write=False):
        if state["stats_phase"] and not write:
            state["reads"] += 1
            if stats_unavailable:
                raise ValueError("investigation_recording_unavailable")
        with original(write=write) as conn:
            yield conn

    monkeypatch.setattr(store, "connection", connection)
    try:
        identity = service.start(binding=binding, request_key="final-statistics")["run_id"]
        until = time.monotonic() + 5
        while service.is_local_running(identity) and time.monotonic() < until:
            time.sleep(0.01)
        assert not service.is_local_running(identity)
        state["stats_phase"] = False
        assert state["reads"] == 1
        row = store.read(identity)
        status = "remote_outcome_unknown" if outcome == "pending" else "failed" if stats_unavailable else "succeeded"
        assert row["status"] == status
        assert len(row["calls"]) == 1
        assert row["calls"][0]["terminal"] == ("completed" if outcome == "completed" else None)
        assert (row["result"] is None) is stats_unavailable
        assert entries == ["step-1"] and len(loads) == 1 and not row["adopted"]
        view = service.read(identity)
        assert view["status"] == status and view["stats"]["model_submissions"] == 1
        tokens = (10, 20) if outcome == "completed" and not stats_unavailable else (None, None)
        assert (view["stats"]["input_tokens"], view["stats"]["output_tokens"]) == tokens
        if stats_unavailable or outcome == "pending":
            assert view["action"] is None
        assert service.latest("OLD")["run_id"] == identity
    finally:
        state["stats_phase"] = False
        service.close()


@pytest.mark.parametrize("boundary", ["source", "source_captured"])
@pytest.mark.parametrize("failure", ["none", "before_commit", "after_commit"])
def test_source_cleanup_preserves_host_journal_failure(tmp_path, monkeypatch, boundary, failure):
    from src.lifecycle_investigation.agent import run_agent
    from src.lifecycle_investigation.news import LocalNews
    from tests.lifecycle_investigation_fixtures import controller
    from tests.test_lifecycle_investigation_agent import choose, completed
    from tests.test_lifecycle_investigation_findings import NOTICE, payload
    from tests.test_security_lifecycle_web_finding import source_page

    url = "https://issuer.example/notice"
    calls, readers = [], []

    class Reader:
        request_count = 0
        stopped = False

        def read(self, actual_url):
            assert actual_url == url
            self.request_count += 1
            return source_page(NOTICE, actual_url)

        def request_stop(self):
            self.stopped = True

    def reader_factory(limits):
        reader = Reader()
        readers.append(reader)
        return reader

    async def model(call, credential, control):
        calls.append(call.call_id)
        if len(calls) == 1:
            output = choose("search_web", query="OLD listing")
        elif call.phase == "search":
            output = {"sources": [url], "unresolved_conditions": []}
        elif len(calls) == 3:
            output = choose("read_url", url=url)
        else:
            material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
            output = choose("conclude", finding=payload(material["sources"][0]["passages"]))
        return completed(call, control, output)

    async def runner(*args, **kwargs):
        return await run_agent(*args, **kwargs, model=model)

    service, store, loads, binding = controller(tmp_path, runner=runner, reader_factory=reader_factory)
    service.news_factory = lambda: LocalNews(None, None)
    method = "source" if boundary == "source" else "step"
    original = getattr(store, method)

    def write(*args, **kwargs):
        selected = boundary == "source" or kwargs["kind"] == "source_captured"
        if selected and failure == "before_commit":
            raise ValueError("investigation_recording_unavailable")
        original(*args, **kwargs)
        if selected and failure == "after_commit":
            raise ValueError("investigation_recording_unavailable")

    monkeypatch.setattr(store, method, write)
    try:
        identity = service.start(binding=binding, request_key="source-finalization")["run_id"]
        until = time.monotonic() + 5
        while service.is_local_running(identity) and time.monotonic() < until:
            time.sleep(0.01)
        assert not service.is_local_running(identity)
        row = store.read(identity)
        assert len(readers) == 1 and readers[0].stopped and readers[0].request_count == 1
        assert len(calls) == (4 if failure == "none" else 3)
        assert all(call["terminal"] == "completed" for call in row["calls"])
        assert row["cancel_requested_at"] is None
        assert bool(row["sources"]) is not (boundary == "source" and failure == "before_commit")
        assert len(loads) == 1 and not row["adopted"]
        reports = [step["payload"] for step in row["steps"] if step["kind"] == "source_read"]
        assert reports == [{"url": url, "http_requests": 1, "observations": []}]
        if failure == "none":
            assert row["status"] == "succeeded" and row["result"] is not None
        else:
            assert (row["status"], row["failure_code"], row["result"]) == (
                "failed", "investigation_recording_unavailable", None,
            )
            assert service.read(identity)["action"] is None
    finally:
        service.close()


@pytest.mark.parametrize("interruption", ["none", "cancel_before_reservation", "reservation_failure", "reservation_ack_lost"])
def test_pre_dispatch_reservation_uses_durable_count_and_preserves_unknown_outcome(tmp_path, monkeypatch, interruption):
    from src.lifecycle_investigation.agent import run_agent
    from src.lifecycle_investigation.store import InvestigationStore
    from tests.lifecycle_investigation_fixtures import controller
    from tests.test_lifecycle_investigation_agent import choose, completed
    from tests.test_lifecycle_investigation_findings import payload

    dispatched = []

    async def model(call, credential, control):
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        reply = completed(call, control, choose("conclude", finding=payload(material["sources"][0]["passages"])))
        dispatched.append(call.call_id)
        return reply

    async def runner(*args, **kwargs):
        return await run_agent(*args, **kwargs, model=model)

    service, store, loads, binding = controller(tmp_path, runner=runner)
    original_reserve = store.reserve_call

    def reserve(identity, **kwargs):
        if interruption == "cancel_before_reservation":
            store.cancel(identity)
        elif interruption == "reservation_failure":
            raise ValueError("investigation_recording_unavailable")
        original_reserve(identity, **kwargs)
        if interruption == "reservation_ack_lost":
            raise ValueError("investigation_recording_unavailable")

    monkeypatch.setattr(store, "reserve_call", reserve)
    try:
        identity = service.start(binding=binding, request_key="reservation-interruption")["run_id"]
        until = time.monotonic() + 5
        while service.is_local_running(identity) and time.monotonic() < until:
            time.sleep(0.01)
        assert not service.is_local_running(identity)
        status = {"none": "succeeded", "cancel_before_reservation": "cancelled", "reservation_failure": "failed",
                  "reservation_ack_lost": "remote_outcome_unknown"}[interruption]
        row = InvestigationStore(store.path).read(identity, include_sources=False)
        assert row["status"] == status
        assert len(row["calls"]) == (1 if interruption in {"none", "reservation_ack_lost"} else 0)
        stats = row["result"]["stats"]
        assert stats["model_submissions"] == len(row["calls"])
        tokens = (10, 20) if interruption == "none" else (None, None) if interruption == "reservation_ack_lost" else (0, 0)
        assert (stats["input_tokens"], stats["output_tokens"]) == tokens
        assert dispatched == (["step-1"] if interruption == "none" else [])
        if interruption != "none":
            assert row["result"]["validated"] is None and not row["adopted"]
        assert service.read(identity)["status"] == status
        assert service.latest("OLD")["run_id"] == identity and len(loads) == 1
    finally:
        service.close()
