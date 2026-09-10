from copy import deepcopy
import json

import pytest

from tests.test_lifecycle_web_store import AT, completed, setup_store, start


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


def saved_usage_receipt(tmp_path, *, failure=None):
    _, store = setup_store(tmp_path)
    report = _report()
    if failure is None:
        analysis = deepcopy(report["phases"][0])
        analysis.update(call_id="analysis-1", remote_id="remote-analysis")
        report["phases"].append(analysis)
        return store, completed(store, usage_report=report)
    identity = start(store)["run_id"]
    control = store.control(identity, owner="worker-1")
    control.reserve_model_request("search-1")
    control.bind_remote_id("search-1", "remote-search")
    control.observe_terminal("search-1", response_id="remote-search", status="completed", selection=control.selection)
    if failure == "lost":
        control.reserve_model_request("analysis-1")
        control.bind_remote_id("analysis-1", "remote-analysis")
        control.observe_transport_loss("analysis-1")
    store.fail(identity, owner="worker-1", code="source_read_incomplete", control=control, usage_report=report)
    return store, identity


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
def test_reopened_usage_receipt_rechecks_remote_binding_even_with_valid_hash(tmp_path, failure):
    from src.lifecycle_web_store import WebJournalError

    store, identity = saved_usage_receipt(tmp_path, failure=failure)
    assert store.read(identity)["status"] == {None: "succeeded", "sources": "failed", "lost": "remote_outcome_unknown"}[failure]
    rewrite_result(store, lambda material: material["usage_report"]["phases"][0].update(remote_id="another-run"))
    with pytest.raises(WebJournalError, match="^web_journal_integrity$"):
        store.read(identity)


def test_completed_result_rechecks_aggregate_agreement_on_read(tmp_path):
    from src.lifecycle_web_store import WebJournalError

    store, identity = saved_usage_receipt(tmp_path)
    assert store.read(identity)["status"] == "succeeded"
    rewrite_result(store, lambda material: material["usage"].update(input_tokens=4))
    with pytest.raises(WebJournalError, match="^web_journal_integrity$"):
        store.read(identity)


@pytest.mark.parametrize("value", [None, {}, "unknown", {"input_tokens": True, "output_tokens": 40},
                                   {"input_tokens": 20, "output_tokens": 40, "secret": "forbidden"}])
def test_legacy_usage_pair_rejects_malformed_shape_instead_of_exporting_it(tmp_path, value):
    from src.lifecycle_web_store import WebJournalError

    _, store = setup_store(tmp_path)
    identity = completed(store)
    rewrite_result(store, lambda material: material.update(usage=value))
    with pytest.raises(WebJournalError, match="^web_journal_integrity$"):
        store.read(identity)
