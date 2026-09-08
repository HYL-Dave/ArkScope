"""Offline controller/journal replay, explicitly not another live canary."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from unittest.mock import patch

import claude_canary as original
from diagnose_analysis import snapshot


PACKET = Path(__file__).resolve().parent


def verify(label, capture, analysis, work, receipts):
    from src import security_lifecycle_web_pipeline as pipeline
    from src.auth_drivers.lifecycle_web_models import ModelReply, WebCredential
    from src.lifecycle_public_sources import PublicSourceReader, SourceReadError
    from src.lifecycle_web_controller import LifecycleWebController
    from src.lifecycle_web_projection import project_web_run
    from src.lifecycle_web_store import LifecycleWebStore, install_web_journal
    from src.security_lifecycle_schema import create_profile_schema

    before = snapshot(capture)
    assert sum(receipt["files"] == before for receipt in receipts) == 1
    original_result = json.loads((capture / "result.json").read_text())
    metrics = json.loads((capture / "metrics.json").read_text())
    checked = json.loads((analysis / "metrics.json").read_text())
    assert checked["status"] == "completed" and checked["source_http_requests"] == 0
    assert checked["capture_files_sha256"] == before
    row = LifecycleWebStore(capture / "profile.sqlite").read(original_result["run_id"])
    search_output = json.loads((capture / "search-output.json").read_text())
    replies = {"search": search_output, "analysis": json.loads((analysis / "analysis-output.json").read_text())}
    usage = {"search": metrics["phase_replies"][0], "analysis": checked}
    pages_by_url = {page.url: page for page in row["pages"].values()}
    outcomes = dict(zip(search_output["sources"], metrics["source_reads"], strict=True))
    replay_calls, replay_reads = [], []

    class Reader:
        request_count = 0
        observations = ()

        def __init__(self, limits):
            pass

        def read(self, url):
            replay_reads.append(url)
            receipt = outcomes[url]
            if receipt["status"] == "failed":
                raise SourceReadError(receipt["code"])
            page = pages_by_url[receipt["url"]]
            assert (page.body_sha256, page.text_sha256, page.capture_sha256) == (
                receipt["document_sha256"], receipt["text_sha256"], receipt["capture_sha256"])
            return page

        def request_stop(self):
            pass

    async def replay(call, credential, control):
        if call.phase == "analysis":
            assert hashlib.sha256(call.prompt.encode()).hexdigest() == checked["prompt_sha256"]
        replay_calls.append(call.phase)
        remote = "offline-replay-" + call.phase
        control.reserve_model_request(call.call_id)
        control.bind_remote_id(call.call_id, remote)
        control.observe_terminal(call.call_id, response_id=remote, status="completed", selection=call.selection)
        return ModelReply(remote, replies[call.phase], usage[call.phase]["usage"], usage[call.phase]["usage_observation"])

    def no_network(*args, **kwargs):
        raise AssertionError("public_source_network_forbidden_in_recorded_replay")

    at = datetime.now(timezone.utc).isoformat()
    work.mkdir(mode=0o700)
    path = work / "offline-profile.sqlite"
    with sqlite3.connect(path) as conn:
        create_profile_schema(conn)
        conn.execute("INSERT INTO security_lifecycle_cases VALUES (?,?,?,?,?,?)", ("offline-replay-TA", "listing_authority", "listing:TA", "TA", at, at))
        conn.commit()
        install_web_journal(conn, at=at)
    store = LifecycleWebStore(path)
    with patch.object(pipeline, "call_lifecycle_web_model", replay), patch.object(PublicSourceReader, "read", no_network):
        service = LifecycleWebController(store, runner=pipeline.investigate, reader_factory=Reader,
                                         credential_loader=lambda selected: WebCredential(selected))
        try:
            run = service.start(case_id="offline-replay-TA", observation_sha256=original.digest(row["request"].model_dump()),
                request=row["request"], selection=row["selection"], options=row["options"], request_key="recorded-replay")
            deadline = time.monotonic() + 30
            while service.is_local_running(run["run_id"]) and time.monotonic() < deadline:
                time.sleep(0.02)
            assert not service.is_local_running(run["run_id"])
            result = service.read(run["run_id"])
        finally:
            service.close()
    assert replay_calls == ["search", "analysis"] and len(replay_reads) == 4
    assert result["status"] == "succeeded" and result["finding"]["action"] is None
    assert result["finding"]["block_reasons"] == checked["validated_finding"]["block_reasons"]
    assert len(result["finding"]["citations"]) == checked["validated_finding"]["unique_passage_count"]
    assert result["usage_report"]["coverage"] == "complete" and result["usage_report"]["recorded_submissions"] == 2
    expected_usage = {name: usage["search"]["usage"][name] + usage["analysis"]["usage"][name]
                      for name in ("input_tokens", "output_tokens")}
    assert result["usage_report"]["totals"] == result["usage"] == expected_usage
    reopened = LifecycleWebStore(path).read(run["run_id"])
    assert project_web_run(reopened, at=at) == result
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM security_lifecycle_assessments").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM lifecycle_web_acceptances").fetchone()[0] == 0
    assert snapshot(capture) == before
    original.write_new_json(work / "offline-result.json", result)
    return {"label": label, "kind": "offline_replay_of_recorded_search_analysis_and_pages",
        "provider_calls": 0, "source_http_attempts": 0, "production_reads_or_writes": 0,
        "status": result["status"], "action": result["finding"]["action"],
        "block_reasons": result["finding"]["block_reasons"], "accepted_passages": len(result["finding"]["citations"]),
        "combined_recorded_usage_not_new_consumption": expected_usage, "reopened_result_identical": True,
        "original_capture_unchanged": True, "adoptions": 0,
        "temporary_journal_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    admitted = original.require_sources(original.ROOT, PACKET / "json-analysis-admission",
        "9c4f48ddc0f4bad452a93b610a610942336390f1ea761fca14bcf12e62e4ba60")
    receipts = json.loads((PACKET / "json-analysis-admission/verification.json").read_text())["analysis_capture_receipts"]
    root = Path("/tmp/lifecycle-recorded-json-readback")
    root.mkdir(mode=0o700)
    results = [verify(label, Path(capture), Path(analysis), root / label, receipts) for label, capture, analysis in (
        ("R3", "/tmp/lifecycle-renewed-full-r3", "/tmp/lifecycle-final-json-analysis-r3"),
        ("R1", "/tmp/lifecycle-usage-live-r1", "/tmp/lifecycle-final-json-analysis-r1"),
    )]
    original.write_new_json(root / "verification.json", {"source_checkpoint": admitted,
        "fresh_end_to_end_live_canary": False, "results": results})
    print(json.dumps({"offline_replays": len(results), "provider_calls": 0, "http_attempts": 0,
        "all_reopened_equal": True, "actions": [value["action"] for value in results]}))


if __name__ == "__main__":
    main()
