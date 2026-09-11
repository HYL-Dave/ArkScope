"""Synthetic parser allocations only; input bytes are allocated before tracing."""

import hashlib
import json
import random
import time
import tracemalloc

import pytest

from src.lifecycle_public_sources import SourceReadError, _page_text
from src.sec_research import document_text as mod


def measure(request, body, mime, *, cancel_at=None):
    calls = 0

    def check():
        nonlocal calls
        calls += 1
        if calls == cancel_at:
            raise SourceReadError("source_read_cancelled")

    started = time.perf_counter()
    tracemalloc.start()
    try:
        if cancel_at is None:
            text, actual_mime = mod.extract_document_text(body, mime, check=check)
            assert actual_mime == mime
        else:
            with pytest.raises(SourceReadError, match="^source_read_cancelled$"):
                mod.extract_document_text(body, mime, check=check)
            assert calls == cancel_at
            text = ""
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    record = {
        "body_bytes": len(body), "text_utf8_bytes": len(text.encode()),
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "parser_peak_traced_bytes": peak, "check_calls": calls,
        "seconds": round(time.perf_counter() - started, 6), "cancel_at": cancel_at,
    }
    request.node.user_properties.append(("measurement", json.dumps(record, sort_keys=True)))
    assert peak < len(body) * 6 + 4 * 1024 * 1024
    return text


@pytest.mark.parametrize("mime", ["text/html", "application/xml"])
@pytest.mark.parametrize("count", [2000, 8000])
def test_synthetic_parser_memory(request, mime, count):
    unit = b"<p>Revenue " + b"v" * 512 + b" <b>123</b> end.</p>"
    body = b"<root>" + unit * count + b"<p>FINAL</p></root>"
    text = measure(request, body, mime)
    assert text.count("Revenue ") == count
    assert text.endswith("FINAL" if mime == "text/html" else "FINAL</p></root>")


@pytest.mark.parametrize("mime", ["text/plain", "text/html", "application/xml"])
def test_synthetic_parser_cancel(request, mime):
    body = b"<root>" + b"<p>Bounded cancellation.</p>" * 50000 + b"</root>"
    measure(request, body, mime, cancel_at=50)


def test_default_event_ceiling_rejects_comment_stream(request):
    body = b"visible" + b"<!--x-->" * 2_000_001
    started = time.perf_counter()
    with pytest.raises(SourceReadError, match="^source_document_complexity$"):
        mod.extract_document_text(body, "text/html", check=lambda: None)
    request.node.user_properties.append(("measurement", json.dumps({
        "body_bytes": len(body), "seconds": round(time.perf_counter() - started, 6),
        "result": "source_document_complexity", "default_event_ceiling": 2_000_000,
    }, sort_keys=True)))


def test_bounded_index_scratch_and_utf8_offsets(request):
    prefix = "ITEM 1. BUSINESS\n" + ("\u754c" * 512 + "\n") * 8000
    text = prefix + "ITEM 1A. RISK FACTORS\nFinal risks"
    start_byte = len(prefix.encode())
    tracemalloc.start()
    started = time.perf_counter()
    try:
        sections, gaps = mod.index_sections(text, "10-K", check=lambda: None)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert len(sections) == 2 and gaps == []
    assert sections[0]["end_byte"] == sections[1]["start_byte"] == start_byte
    assert peak < 2 * 1024 * 1024
    request.node.user_properties.append(("measurement", json.dumps({
        "text_utf8_bytes": len(text.encode()), "index_peak_traced_bytes": peak,
        "seconds": round(time.perf_counter() - started, 6),
    }, sort_keys=True)))


def test_chunk_normalization_matches_legacy_primitives(monkeypatch):
    rng = random.Random(20260912)
    monkeypatch.setattr(mod, "_CHUNK", 7)
    for _ in range(50):
        parts = [rng.choice(["a", "b", "\u754c", "\u00e9", " ", "\t", "\r", "\n"]) for _ in range(200)]
        value = "start" + "".join(parts) + "end"
        for mime, body in [("text/plain", value.encode()), ("text/html", ("<p>" + value + "</p>").encode())]:
            assert mod.extract_document_text(body, mime, check=lambda: None) == _page_text(body, mime)
