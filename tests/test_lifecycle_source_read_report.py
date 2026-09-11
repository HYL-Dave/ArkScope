"""Measured source failures survive the real current agent and journal."""

from dataclasses import asdict
import json

import pytest

from src.lifecycle_investigation.agent import run_agent
from src.lifecycle_investigation.news import LocalNews
from src.lifecycle_investigation.store import InvestigationStore
from src.lifecycle_public_sources import PublicSourceReader, SourceReadError, SourceReadObservation, validate_source_read_report
from tests.lifecycle_investigation_fixtures import controller, wait_done
from tests.test_lifecycle_investigation_agent import choose, completed
from tests.test_lifecycle_investigation_findings import payload
from tests.test_lifecycle_public_sources import Response, _reader, deny_real_network


def test_all_source_failures_keep_measured_diagnostics_after_journal_reopen(tmp_path, monkeypatch):
    urls = ["https://issuer.example/notice", "https://issuer.example/second"]
    _, connections, _, _ = _reader(monkeypatch, [
        Response(b"short", headers={"Content-Length": "1000"}),
        Response(status=403, headers={"Set-Cookie": "do-not-retain-this-secret"}),
    ])
    calls = []
    async def model(call, credential, control):
        calls.append(call)
        if len(calls) == 1:
            return completed(call, control, choose("search_web", query="OLD listing status"))
        if call.phase == "search":
            return completed(call, control, {"sources": urls, "unresolved_conditions": []})
        if len(calls) <= 4:
            return completed(call, control, choose("read_url", url=urls[len(calls) - 3]))
        finding = {**payload([{"passage_id": "source-1:p1"}]), "event_kind": "unresolved",
            "timing": "unknown", "citations": [], "effective_date": None, "effective_date_text": None,
            "summary": "No readable listing evidence.", "unresolved_conditions": ["Trading status is unknown."]}
        return completed(call, control, choose("conclude", finding=finding))
    async def runner(*args, **kwargs):
        return await run_agent(*args, **kwargs, model=model)
    service, store, loads, binding = controller(tmp_path, runner=runner, reader_factory=PublicSourceReader)
    service.news_factory = lambda: LocalNews(None, None)
    try:
        identity = service.start(binding=binding, request_key="source-failures")["run_id"]
        result = wait_done(service, identity)
        assert result["status"] == "incomplete" and result["action"] is None
        assert len(connections) == result["stats"]["http_requests"] == 2
        assert all(conn.closed for conn in connections)
        row = InvestigationStore(store.path).read(identity)
        reports = [step["payload"] for step in row["steps"] if step["kind"] == "source_read"]
        assert [report["url"] for report in reports] == urls
        first, second = [report["observations"][0] for report in reports]
        assert first["declared_body_bytes"] == 1000 and first["received_body_bytes"] == 5
        assert first["result_code"] == "source_body_incomplete" and second["status"] == 403
        assert row["sources"] == {} and row["result"]["validated"]["action"] is None
        assert {(gap["url"], gap["reason"]) for gap in result["gaps"] if gap["url"]} == {
            (urls[0], "source_body_incomplete"), (urls[1], "source_unavailable")}
        assert "do-not-retain-this-secret" not in json.dumps([reports, result])
        assert len(loads) == 1
    finally:
        service.close()


@pytest.mark.parametrize("mutate", [
    lambda report: report.update(requests=True),
    lambda report: report.update(requests=9),
    lambda report: report.update(observations={}),
    lambda report: report["observations"][0].update(status="200"),
    lambda report: report["observations"][0].update(headers={"Authorization": "secret"}),
    lambda report: report["observations"][0].update(received_body_bytes=-1),
    lambda report: report["observations"].append(dict(report["observations"][0])),
])
def test_read_report_rejects_malformed_or_extraneous_details(mutate):
    report = {"requests": 1, "observations": [asdict(SourceReadObservation(1, 403, None, None, None, 0, 0, "source_unavailable"))]}
    mutate(report)
    with pytest.raises(SourceReadError, match="^source_read_report_invalid$"):
        validate_source_read_report(report, max_requests=4)
