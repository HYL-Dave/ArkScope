"""Two real controller jobs sharing one temporary journal; fake model and HTTPS."""

import argparse
from dataclasses import asdict
import gzip
import json
from pathlib import Path
import resource
import sqlite3
import sys
import tempfile
import time
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--decoded-mib", type=int, required=True)
    parser.add_argument("--source-timeout", type=float, required=True)
    parser.add_argument("--dense", action="store_true")
    args = parser.parse_args()
    if args.output.exists() or not 1 <= args.decoded_mib <= 128:
        raise ValueError("new_output_and_bounded_measurement_required")
    sys.path.insert(0, str(args.repo.resolve()))
    from src import lifecycle_public_sources as sources
    from src import security_lifecycle_web_pipeline as pipeline
    from src.auth_drivers.lifecycle_web_models import WebCredential, ModelReply
    from src.lifecycle_web_controller import LifecycleWebController
    from src.lifecycle_web_store import LifecycleWebStore
    from src.lifecycle_web_projection import project_web_run
    from src.security_lifecycle_web_contract import validate_selection
    from tests.test_lifecycle_public_sources import Connection, Response
    from tests.test_lifecycle_web_store import setup_store, AT
    from tests.test_security_lifecycle_web_finding import NOTICE, finding_payload, public_input

    limit = args.decoded_mib * 1024 * 1024
    paragraph = (("<p>Shares remain active: " if args.dense else "<p>General layout: ") + "\U00020000" * 4000 + "</p>").encode()
    tail = ("<p>" + NOTICE + "</p><p>However, the shares remain active OTC.</p></article>").encode()
    prefix = b"<article><h1>Public notice</h1>"
    document = prefix + paragraph * ((limit - len(prefix) - len(tail)) // len(paragraph)) + tail
    document_bytes = len(document)
    encoded = gzip.compress(document)
    del paragraph, document
    selection = validate_selection("openai", "api_key", "gpt-5.6-luna", "local:7")
    credential = WebCredential(selection, api_key="synthetic-capacity-only")
    options = pipeline.WebInvestigationOptions(max_sources=4, max_source_requests=8, max_redirects=2,
        max_source_bytes=32 * 1024 * 1024, max_decoded_source_bytes=limit,
        source_timeout_seconds=args.source_timeout, model_timeout_seconds=180,
        max_search_uses=4, output_token_limit=16384, effort="high")
    calls, receipts = [], []

    async def model(call, actual, control):
        assert actual is credential
        control.reserve_model_request(call.call_id)
        control.bind_remote_id(call.call_id, "synthetic-" + call.phase)
        calls.append(call.phase)
        print(json.dumps({"stage": call.phase, "calls": len(calls)}), flush=True)
        payload = ({"sources": [f"https://ir.example.com/source/{index}" for index in range(4)], "unresolved_conditions": []}
                   if call.phase == "search" else finding_payload(contradictions=["Active OTC trading is also reported."]))
        control.observe_terminal(call.call_id, response_id="synthetic-" + call.phase, status="completed", selection=selection)
        return ModelReply("synthetic-" + call.phase, payload, {"input_tokens": None, "output_tokens": None})

    def connection(*args, **kwargs):
        return Connection(Response(encoded, headers={"Content-Type": "text/html; charset=utf-8",
                          "Content-Encoding": "gzip", "Content-Length": str(len(encoded))}))

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="lifecycle-capacity-runtime-") as temporary:
        path, _ = setup_store(Path(temporary))
        with sqlite3.connect(path) as conn:
            conn.execute("INSERT INTO security_lifecycle_cases VALUES (?,?,?,?,?,?)", ("case-2", "sec_edgar", "source-2", "OLD", AT, AT))
        store = LifecycleWebStore(path)
        controller = LifecycleWebController(store, credential_loader=lambda _: credential)
        with patch.object(sources, "_PinnedHTTPSConnection", connection), patch.object(
            sources.PublicSourceReader, "_address", lambda self, host: (2, ("93.184.216.34", 443))
        ), patch.object(pipeline, "call_lifecycle_web_model", model):
            try:
                for index in range(2):
                    receipts.append(controller.start(case_id=f"case-{index + 1}", observation_sha256="a" * 64,
                        request=public_input(), selection=selection, options=options, request_key=f"capacity-{index}"))
                while any(controller.is_local_running(row["run_id"]) for row in receipts):
                    if time.monotonic() - started > 500:
                        raise TimeoutError("offline_capacity_timeout")
                    time.sleep(0.1)
            finally:
                controller.close()
        with sqlite3.connect(path) as conn:
            rows = conn.execute("SELECT status,failure_code FROM lifecycle_web_runs ORDER BY case_id").fetchall()
        projections = [project_web_run(store.read(row["run_id"]), at=store._now()) for row in receipts]
        report = {"provider_calls": 0, "network_calls": 0, "production_data_access": False,
                  "shared_journal": True, "real_controller_and_heartbeat": True, "concurrent_workers": 2,
                  "dense_context": args.dense,
                  "simulated_model_phases": calls, "statuses": rows, "options": asdict(options),
                  "document_decoded_bytes": document_bytes, "database_bytes": path.stat().st_size,
                  "source_reading": [row["source_reading"] for row in projections],
                  "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                  "elapsed_seconds": round(time.monotonic() - started, 3)}
    with args.output.open("x") as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(report), flush=True)
    if rows != [("succeeded", None), ("succeeded", None)] or sorted(calls) != ["analysis", "analysis", "search", "search"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
