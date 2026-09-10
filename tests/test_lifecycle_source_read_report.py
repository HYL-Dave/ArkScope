from dataclasses import asdict
import json

import pytest

from src.lifecycle_public_sources import SourceReadError
from tests.test_lifecycle_public_sources import Response, _reader, deny_real_network
from tests.test_lifecycle_web_store import setup_store, start


def test_all_source_failures_keep_measured_diagnostics_after_journal_reopen(tmp_path, monkeypatch):
    from src.lifecycle_web_projection import project_web_run
    from src.lifecycle_web_store import LifecycleWebStore

    path, store = setup_store(tmp_path)
    run = start(store)
    control = store.control(run["run_id"], owner="worker-1")
    reader, connections, _, _ = _reader(monkeypatch, [
        Response(b"short", headers={"Content-Length": "1000"}),
        Response(status=403, headers={"Set-Cookie": "do-not-retain-this-secret"}),
    ])
    control.reserve_model_request("search-1")
    control.bind_remote_id("search-1", "remote-search")
    control.observe_terminal("search-1", response_id="remote-search", status="completed", selection=control.selection)
    for url in [
        "https://ir.example.com/notice", "https://news.example.com/notice",
    ]:
        with pytest.raises(SourceReadError):
            reader.read(url)
    assert len(connections) == 2 and reader.request_count == 2
    report = {"requests": reader.request_count, "observations": [asdict(value) for value in reader.observations]}
    assert report["observations"][0]["declared_body_bytes"] == 1000
    assert report["observations"][0]["received_body_bytes"] == 5
    assert report["observations"][1]["status"] == 403
    store.fail(run["run_id"], owner="worker-1", code="source_read_incomplete", control=control, source_read_report=report)
    row = LifecycleWebStore(path).read(run["run_id"])
    assert row["status"] == "failed" and row["finding"] is None
    assert row["source_read_report"] == report and row["source_requests"] == 2
    projected = project_web_run(row, at="2026-09-07T00:00:00Z")
    assert projected["source_reads"] == report["observations"]
    assert projected["source_requests"] == 2 and projected["model_submissions"] == 1
    assert "secret" not in json.dumps(projected)
    assert projected["finding"] is None


@pytest.mark.parametrize("mutate", [
    lambda report: report.update(requests=True),
    lambda report: report.update(requests=9),
    lambda report: report.update(observations={}),
    lambda report: report["observations"][0].update(status="200"),
    lambda report: report["observations"][0].update(headers={"Authorization": "secret"}),
    lambda report: report["observations"][0].update(received_body_bytes=-1),
    lambda report: report["observations"].append(dict(report["observations"][0])),
])
def test_read_report_rejects_malformed_or_extraneous_details(tmp_path, mutate):
    from src.lifecycle_public_sources import SourceReadObservation
    _, store = setup_store(tmp_path)
    run = start(store)
    control = store.control(run["run_id"], owner="worker-1")
    report = {"requests": 1, "observations": [asdict(SourceReadObservation(1, 403, None, None, None, 0, 0, "source_unavailable"))]}
    mutate(report)
    with pytest.raises(ValueError, match="^source_read_report_invalid$"):
        store.fail(run["run_id"], owner="worker-1", code="source_read_incomplete", control=control, source_read_report=report)
    assert store.read(run["run_id"])["status"] == "queued"


def test_population_retains_failure_receipts_without_accepting_them_as_findings(tmp_path):
    from src.lifecycle_public_sources import SourceReadObservation
    from src.security_lifecycle_population import read_population_snapshot, build_population_manifest, _digest, LifecyclePopulationUnavailable
    from tests.test_lifecycle_web_review import context, confirm, prepare

    c = context(tmp_path)
    confirm(c, prepare(c))
    store = c["web"]
    original = store.read(c["run_id"])
    run = store.start(case_id=c["case_id"], observation_sha256=original["observation_sha256"], request=original["request"],
                      selection=original["selection"], options=original["options"], owner="worker-1", request_key="failed-read")
    report = {"requests": 1, "observations": [asdict(SourceReadObservation(1, 403, None, None, None, 0, 0, "source_unavailable"))]}
    store.fail(run["run_id"], owner="worker-1", code="source_read_incomplete",
               control=store.control(run["run_id"], owner="worker-1"), source_read_report=report)
    snapshot = read_population_snapshot(c["market"], c["profile"], at=c["now"][0])
    retained = build_population_manifest(snapshot)["retention"]["web_journal"]
    assert run["run_id"] in {item["run_id"] for item in retained["results"]}
    assert len(retained["acceptances"]) == 1
    # A receipt for a failed read must never satisfy an adoption dependency.
    snapshot["material"]["web_journal_inventory"]["acceptances"][0]["run_id"] = run["run_id"]
    snapshot["sha256"] = _digest({key: snapshot[key] for key in ("version", "at", "material")})
    with pytest.raises(LifecyclePopulationUnavailable, match="population_web_dependency_invalid"):
        build_population_manifest(snapshot)
