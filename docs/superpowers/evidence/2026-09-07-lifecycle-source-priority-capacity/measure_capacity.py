"""Synthetic, provider-free reader/journal/context capacity measurement.

Two simultaneous investigations, four retained sources each. No existing data,
profile, credentials, DNS or network. Generated databases live in a temporary
directory and are deleted; only aggregate measurements are published.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import gzip
import json
from pathlib import Path
import resource
import sys
import tempfile
import time
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--decoded-mib", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-timeout", type=float, default=45)
    args = parser.parse_args()
    if args.output.exists() or not 1 <= args.decoded_mib <= 128:
        raise ValueError("new_output_and_bounded_measurement_required")
    sys.path.insert(0, str(args.repo.resolve()))
    from src import lifecycle_public_sources as sources
    from src.lifecycle_source_context import select_source_context
    from tests.test_lifecycle_public_sources import Connection, Response
    from src.lifecycle_web_projection import project_web_run
    from src.security_lifecycle_web_contract import validate_selection
    from tests.test_lifecycle_web_store import setup_store
    from tests.test_security_lifecycle_web_pipeline import _options
    from tests.test_security_lifecycle_web_finding import NOTICE, finding_payload, public_input

    decoded_limit = args.decoded_mib * 1024 * 1024
    # Supplementary Unicode exercises both UTF-8 and ensure_ascii journal expansion.
    paragraph = ("<p>General layout: " + "\U00020000" * 4000 + "</p>").encode()
    tail = ("<p>" + NOTICE + "</p><p>However, the shares remain active OTC.</p></article>").encode()
    prefix = b"<article><h1>Public notice</h1>"
    count = (decoded_limit - len(prefix) - len(tail)) // len(paragraph)
    document = prefix + paragraph * count + tail
    encoded = gzip.compress(document)
    document_bytes = len(document)
    del document, paragraph
    baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024

    def connection(*args, **kwargs):
        return Connection(Response(encoded, headers={
            "Content-Type": "text/html; charset=utf-8", "Content-Encoding": "gzip", "Content-Length": str(len(encoded)),
        }))

    def investigate(root, index):
        root.mkdir()
        _, store = setup_store(root)
        options = replace(_options("api_key"), max_sources=4, max_source_requests=8,
                          max_source_bytes=32 * 1024 * 1024, max_decoded_source_bytes=decoded_limit,
                          source_timeout_seconds=args.source_timeout, model_timeout_seconds=180)
        identity = store.start(case_id="case-1", observation_sha256="a" * 64, request=public_input(),
            selection=validate_selection("openai", "api_key", "gpt-5.6-luna", "local:7"), options=options,
            owner="worker-1", request_key="synthetic-capacity")["run_id"]
        control = store.control(identity, owner="worker-1")
        for phase in ("search", "analysis"):
            control.reserve_model_request(phase + "-1")
            control.bind_remote_id(phase + "-1", "synthetic-" + phase)
            control.observe_terminal(phase + "-1", response_id="synthetic-" + phase, status="completed", selection=control.selection)
        reader = sources.PublicSourceReader(sources.SourceReadLimits(4, 0, 32 * 1024 * 1024, args.source_timeout, decoded_limit))
        pages, context_bytes, read_seconds = {}, 0, 0.0
        started = time.monotonic()
        for source in range(4):
            before = time.monotonic()
            page = reader.read(f"https://ir.example.com/{index}/{source}")
            read_seconds += time.monotonic() - before
            store.add_page(identity, owner="worker-1", source_id=f"source-{source + 1}", page=page)
            pages[f"source-{source + 1}"] = page
            print(json.dumps({"worker": index, "stage": "retained", "sources": len(pages)}), flush=True)
        context_started = time.monotonic()
        contexts, context_manifest = [], {}
        for source_id, page in pages.items():
            selected = select_source_context(public_input(), page)
            context_manifest[source_id] = selected.to_material()
            material = selected.prompt_material(page)
            assert material["coverage"] == "selected_passages"
            assert NOTICE in json.dumps(material)
            context_bytes += sum(len(value["text"].encode()) for value in material["passages"])
            contexts.append(material)
        prompt = json.dumps(contexts, ensure_ascii=True)
        print(json.dumps({"worker": index, "stage": "context_ready", "model_text_bytes": context_bytes}), flush=True)
        store.complete(identity, owner="worker-1", payload=finding_payload(contradictions=["The notice also reports active OTC trading."]),
                       source_failures={}, usage={"input_tokens": None, "output_tokens": None}, source_requests=4,
                       source_context=context_manifest,
                       source_read_report={"requests": 4, "observations": [asdict(item) for item in reader.observations]})
        print(json.dumps({"worker": index, "stage": "journal_completed"}), flush=True)
        # Exercise completion, revalidation and the UI/Research projection too.
        row = store.read(identity)
        reopened = row["pages"]
        assert len(reopened) == 4
        assert all(reopened[key].text_sha256 == page.text_sha256 for key, page in pages.items())
        projected = project_web_run(row, at="2026-09-07T00:00:00Z")
        assert projected["source_reading"]["model_text_bytes"] == context_bytes
        assert projected["finding"]["action"] is None
        return {"requests": reader.request_count, "document_decoded_bytes": document_bytes,
                "document_encoded_bytes": len(encoded), "retained_text_bytes": sum(len(page.text.encode()) for page in pages.values()),
                "model_text_bytes": context_bytes, "serialized_model_source_bytes": len(prompt.encode()),
                "read_seconds": round(read_seconds, 3), "selection_completion_and_readback_seconds": round(time.monotonic() - context_started, 3),
                "total_seconds": round(time.monotonic() - started, 3),
                "database_bytes": store.path.stat().st_size,
                "observations": [asdict(item) for item in reader.observations]}

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="arkscope-source-capacity-") as temporary:
        with patch.object(sources, "_PinnedHTTPSConnection", connection), patch.object(
            sources.PublicSourceReader, "_address", lambda self, host: (2, ("93.184.216.34", 443))
        ), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(investigate, Path(temporary) / str(index), index) for index in range(2)]
            results = [future.result() for future in futures]
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    report = {"provider_calls": 0, "network_calls": 0, "production_data_access": False, "concurrent_workers": 2,
              "retained_sources_per_worker": 4, "decoded_limit_bytes": decoded_limit, "encoded_limit_bytes": 32 * 1024 * 1024,
              "source_timeout_seconds": args.source_timeout,
              "baseline_peak_rss_bytes": baseline, "peak_rss_bytes": peak, "peak_growth_bytes": peak - baseline,
              "elapsed_seconds": round(time.monotonic() - started, 3), "runs": results}
    with args.output.open("x") as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({key: value for key, value in report.items() if key != "runs"}), flush=True)


if __name__ == "__main__":
    main()
