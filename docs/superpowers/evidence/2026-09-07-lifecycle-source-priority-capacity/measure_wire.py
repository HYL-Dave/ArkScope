"""Actual 32 MiB synthetic identity body and one-byte-over rejection; no network."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import resource
import sys
import time
from unittest.mock import patch

from run_capacity import inputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("new_output_required")
    source_hashes = inputs(args.repo.resolve())
    sys.path.insert(0, str(args.repo.resolve()))
    from src import lifecycle_public_sources as sources
    from tests.test_lifecycle_public_sources import Connection, Response

    limit = 32 * 1024 * 1024
    tail = b"The final notice still reports active OTC trading."
    body = b"A" * (limit - len(tail)) + tail
    observations = []
    started = time.monotonic()
    for extra in (b"", b"X"):
        data = body + extra
        def connection(*args, **kwargs):
            return Connection(Response(data, headers={"Content-Type": "text/plain", "Content-Length": str(len(data))}))
        with patch.object(sources, "_PinnedHTTPSConnection", connection), patch.object(
            sources.PublicSourceReader, "_address", lambda self, host: (2, ("93.184.216.34", 443))
        ):
            reader = sources.PublicSourceReader(sources.SourceReadLimits(1, 0, limit, 45, 128 * 1024 * 1024))
            try:
                page = reader.read("https://ir.example.com/large-notice")
                assert not extra and page.text.encode() == body and page.text.endswith(tail.decode())
            except sources.SourceReadError as exc:
                assert extra and str(exc) == "source_body_too_large", str(exc)
            else:
                assert not extra
            observations.extend(asdict(value) for value in reader.observations)
    assert inputs(args.repo.resolve()) == source_hashes
    result = {"provider_calls": 0, "network_calls": 0, "production_data_access": False,
              "source_sha256": source_hashes,
              "wire_limit_bytes": limit, "exact_limit_text_and_tail_preserved": True,
              "one_byte_over_rejected_without_returning_prefix": True, "observations": observations,
              "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
              "elapsed_seconds": round(time.monotonic() - started, 3)}
    with args.output.open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
