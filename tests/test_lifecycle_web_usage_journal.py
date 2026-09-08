from copy import deepcopy
from dataclasses import replace
import json

import pytest

from src.auth_drivers.lifecycle_web_models import WebModelError
from tests.test_lifecycle_web_controller import controller, launch, selection, wait_done
from tests.test_lifecycle_web_store import AT, completed, setup_store, start
from tests.test_security_lifecycle_web_pipeline import Reader, _fake_model


CHANNELS = [("openai", "api_key"), ("openai", "chatgpt_oauth"),
            ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")]


def run_pipeline(tmp_path, monkeypatch, *, failure=None, selected=None, unknown=False):
    from src import security_lifecycle_web_pipeline as pipeline
    from src.lifecycle_public_sources import SourceReadError

    calls = []
    reader = Reader()
    if failure == "sources":
        def fail_read(url):
            reader.urls.append(url)
            raise SourceReadError("source_unavailable")
        monkeypatch.setattr(reader, "read", fail_read)
    fake = _fake_model(calls)

    async def model(call, credential, control):
        if call.phase == "analysis" and failure in {"analysis", "lost"}:
            calls.append((call, credential))
            control.reserve_model_request(call.call_id)
            control.bind_remote_id(call.call_id, "remote-analysis")
            if failure == "analysis":
                control.observe_terminal(call.call_id, response_id="remote-analysis", status="failed", selection=call.selection)
            raise WebModelError("provider_call_failed")
        reply = await fake(call, credential, control)
        if unknown:
            reply = replace(reply, usage={"input_tokens": None, "output_tokens": None})
        return reply

    monkeypatch.setattr(pipeline, "call_lifecycle_web_model", model)
    service, store, credentials = controller(tmp_path, runner=pipeline.investigate, reader_factory=lambda limits: reader)
    try:
        result = wait_done(service, launch(service, selected=selected)["run_id"])
    finally:
        service.close()
    return result, store, calls, credentials, reader


@pytest.mark.parametrize("provider,auth", CHANNELS)
def test_real_pipeline_usage_survives_source_failure_and_reopen_for_each_channel(tmp_path, monkeypatch, provider, auth):
    from src.lifecycle_web_projection import latest_web_runs, project_web_run
    from src.lifecycle_web_store import LifecycleWebStore

    result, store, calls, credentials, reader = run_pipeline(
        tmp_path, monkeypatch, failure="sources", selected=selection(provider, auth))
    assert result["status"] == "failed" and result["failure_code"] == "source_read_incomplete"
    assert result["model_submissions"] == 1 and result["source_requests"] == 1
    assert len(calls) == len(credentials) == len(reader.urls) == 1
    assert result["finding"] is None and result["usage"] == {"input_tokens": 10, "output_tokens": 20}
    report = result["usage_report"]
    assert report["coverage"] == "complete" and report["recorded_submissions"] == 1
    assert report["totals"] == report["known_subtotal"] == result["usage"]
    assert report["phases"] == [{"phase": "search", "basis": "adapter_report", "input_tokens": 10, "output_tokens": 20,
                                 "cache_creation_input_tokens": None, "cache_read_input_tokens": None, "web_search_requests": None}]
    reopened = LifecycleWebStore(store.path)
    assert project_web_run(reopened.read(result["run_id"]), at=AT) == result
    with reopened.connection() as conn:
        assert latest_web_runs(conn, ["case-1"], at=AT) == [result]
    assert not any(private in json.dumps(report) for private in ("remote-", "call_id", "local:", "main_loop", "costUSD", "total_cost_usd"))


@pytest.mark.parametrize("failure,status", [("analysis", "failed"), ("lost", "remote_outcome_unknown")])
def test_unreported_analysis_is_unknown_not_zero_or_success_while_search_usage_survives(tmp_path, monkeypatch, failure, status):
    result, _, calls, _, _ = run_pipeline(tmp_path, monkeypatch, failure=failure)
    assert result["status"] == status and result["finding"] is None and len(calls) == 2
    assert result["model_submissions"] == 2 and result["usage"] == {"input_tokens": None, "output_tokens": None}
    report = result["usage_report"]
    assert report["coverage"] == "partial" and report["recorded_submissions"] == 1
    assert report["known_subtotal"] == {"input_tokens": 10, "output_tokens": 20}
    assert report["totals"] == result["usage"]


@pytest.mark.parametrize("provider,auth", CHANNELS)
def test_completed_pipeline_sums_each_accepted_phase_once_without_changing_action(tmp_path, monkeypatch, provider, auth):
    result, _, calls, _, _ = run_pipeline(tmp_path, monkeypatch, selected=selection(provider, auth))
    assert result["status"] == "succeeded" and result["finding"]["action"] == "terminal_delisting"
    assert len(calls) == 2 and result["usage"] == {"input_tokens": 20, "output_tokens": 40}
    report = result["usage_report"]
    assert report["coverage"] == "complete" and report["recorded_submissions"] == 2
    assert report["totals"] == result["usage"] and [phase["phase"] for phase in report["phases"]] == ["search", "analysis"]


def test_valid_result_with_no_reported_counters_remains_success_but_usage_unknown(tmp_path, monkeypatch):
    result, _, _, _, _ = run_pipeline(tmp_path, monkeypatch, unknown=True)
    assert result["status"] == "succeeded" and result["finding"]["action"] == "terminal_delisting"
    assert result["usage_report"]["coverage"] == "unknown"
    assert result["usage_report"]["known_subtotal"] == {"input_tokens": None, "output_tokens": None}


def test_legacy_usage_has_no_fabricated_scope_or_zero_counters(tmp_path):
    from src.lifecycle_web_projection import project_web_run

    _, store = setup_store(tmp_path)
    result = project_web_run(store.read(completed(store)), at=AT)
    assert result["usage"] == {"input_tokens": 20, "output_tokens": 40}
    assert result["usage_report"] is None


def _report():
    return {"version": 1, "phases": [{"call_id": "search-1", "remote_id": "remote-search", "observation": {
        "basis": "adapter_report", "values": {"input_tokens": 10, "output_tokens": 20,
            "cache_creation_input_tokens": None, "cache_read_input_tokens": None, "web_search_requests": None}, "main_loop": None}}]}


@pytest.mark.parametrize("mutate", [
    lambda report: report["phases"][0].update(remote_id="another-run"),
    lambda report: report["phases"].append(deepcopy(report["phases"][0])),
    lambda report: report["phases"][0].update(call_id="analysis-1"),
    lambda report: report["phases"][0]["observation"]["values"].update(input_tokens=True),
    lambda report: report["phases"][0]["observation"].update(secret="not-public"),
    lambda report: report.update(phases=None),
    lambda report: report.update(version=True),
])
def test_usage_receipt_rejects_cross_call_duplicate_and_malformed_observations_before_write(tmp_path, mutate):
    from src.lifecycle_web_store import WebJournalError

    _, store = setup_store(tmp_path)
    identity = start(store)["run_id"]
    control = store.control(identity, owner="worker-1")
    control.reserve_model_request("search-1")
    control.bind_remote_id("search-1", "remote-search")
    control.observe_terminal("search-1", response_id="remote-search", status="completed", selection=control.selection)
    report = _report()
    mutate(report)
    with pytest.raises(WebJournalError, match="^web_result_invalid$"):
        store.fail(identity, owner="worker-1", code="source_read_incomplete", control=control, usage_report=report)
    assert store.read(identity)["status"] == "queued"
    with store.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM lifecycle_web_results").fetchone()[0] == 0


def test_usage_only_failure_receipt_is_readable_and_does_not_create_a_finding(tmp_path):
    from src.lifecycle_web_projection import project_web_run

    _, store = setup_store(tmp_path)
    identity = start(store)["run_id"]
    control = store.control(identity, owner="worker-1")
    control.reserve_model_request("search-1")
    control.bind_remote_id("search-1", "remote-search")
    control.observe_terminal("search-1", response_id="remote-search", status="completed", selection=control.selection)
    store.fail(identity, owner="worker-1", code="search_no_sources", control=control, usage_report=_report())
    result = project_web_run(store.read(identity), at=AT)
    assert result["status"] == "failed" and result["source_reads"] is None and result["finding"] is None
    assert result["usage_report"]["totals"] == {"input_tokens": 10, "output_tokens": 20}


def rewrite_result(store, mutate):
    from src.lifecycle_web_schema import TRIGGERS
    from src.lifecycle_web_store import _json, _sha

    with store.connection(write=True) as conn:
        value = json.loads(conn.execute("SELECT payload_json FROM lifecycle_web_results").fetchone()[0])
        mutate(value)
        trigger = "lifecycle_web_results_update_immutable"
        conn.execute("DROP TRIGGER " + trigger)
        conn.execute("UPDATE lifecycle_web_results SET payload_json=?,result_sha256=?", (_json(value), _sha(value)))
        conn.execute(TRIGGERS[trigger])


@pytest.mark.parametrize("value", [None, [], {}, {"version": 1, "phases": None}, {"version": True, "phases": []}])
def test_present_malformed_saved_usage_is_not_treated_as_legacy_absence(tmp_path, value):
    from src.lifecycle_web_store import WebJournalError

    _, store = setup_store(tmp_path)
    identity = completed(store)
    rewrite_result(store, lambda material: material.update(usage_report=value))
    with pytest.raises(WebJournalError, match="^web_journal_integrity$"):
        store.read(identity)


@pytest.mark.parametrize("failure", [None, "sources", "lost"])
def test_reopened_usage_receipt_rechecks_remote_binding_even_with_valid_hash(tmp_path, monkeypatch, failure):
    from src.lifecycle_web_store import WebJournalError

    result, store, _, _, _ = run_pipeline(tmp_path, monkeypatch, failure=failure)
    rewrite_result(store, lambda material: material["usage_report"]["phases"][0].update(remote_id="another-run"))
    with pytest.raises(WebJournalError, match="^web_journal_integrity$"):
        store.read(result["run_id"])


def test_completed_result_rechecks_aggregate_agreement_on_read(tmp_path, monkeypatch):
    from src.lifecycle_web_store import WebJournalError

    result, store, _, _, _ = run_pipeline(tmp_path, monkeypatch)
    rewrite_result(store, lambda material: material["usage"].update(input_tokens=4))
    with pytest.raises(WebJournalError, match="^web_journal_integrity$"):
        store.read(result["run_id"])


def test_inconsistent_pipeline_total_is_rejected_before_success_but_phase_usage_is_retained(tmp_path, monkeypatch):
    from src import security_lifecycle_web_pipeline as pipeline

    monkeypatch.setattr(pipeline, "_sum_usage", lambda replies: {"input_tokens": 4, "output_tokens": 1036})
    result, store, calls, _, _ = run_pipeline(tmp_path, monkeypatch)
    assert result["status"] == "failed" and result["failure_code"] == "web_result_invalid"
    assert result["finding"] is None and len(calls) == 2
    assert result["usage_report"]["totals"] == {"input_tokens": 20, "output_tokens": 40}
    with store.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM lifecycle_web_acceptances").fetchone()[0] == 0


@pytest.mark.parametrize("value", [None, {}, "unknown", {"input_tokens": True, "output_tokens": 40},
                                   {"input_tokens": 20, "output_tokens": 40, "secret": "forbidden"}])
def test_legacy_usage_pair_rejects_malformed_shape_instead_of_exporting_it(tmp_path, value):
    from src.lifecycle_web_store import WebJournalError

    _, store = setup_store(tmp_path)
    identity = completed(store)
    rewrite_result(store, lambda material: material.update(usage=value))
    with pytest.raises(WebJournalError, match="^web_journal_integrity$"):
        store.read(identity)
