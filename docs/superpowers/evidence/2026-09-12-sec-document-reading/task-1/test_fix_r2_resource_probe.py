"""XHTML QName refinement resource controls, with preallocated synthetic inputs."""

import json
import time
import tracemalloc

import pytest

from src.lifecycle_public_sources import SourceReadError
from src.sec_research import document_text as mod


@pytest.mark.parametrize("depth", [32, 400])
def test_xhtml_case_distinct_namespace_scopes_remain_delta_bounded(request, depth):
    attrs = " ".join(f'xmlns:{prefix}{index}="urn:scope:{prefix}:{index}"'
                     for index in range(2048) for prefix in ("n", "N"))
    names = ["Scope" if index % 2 else "scope" for index in range(depth)]
    body = (f'<root {attrs} xmlns:Fact="http://www.xbrl.org/2013/inlineXBRL" '
            'xmlns:fact="urn:visible">'
            + "".join(f'<{name} xmlns:Local="urn:local:{index}">'
                      for index, name in enumerate(names))
            + '<Fact:hidden>HIDDEN inner</Fact:hidden><p><fact:hidden>Visible</fact:hidden></p>'
            + "".join(f'</{name}>' for name in reversed(names))
            + '<Fact:hidden>HIDDEN outer</Fact:hidden><p>Tail</p></root>').encode()
    checks = 0

    def check():
        nonlocal checks
        checks += 1

    started = time.perf_counter()
    tracemalloc.start()
    try:
        result = mod.extract_document_text(body, "application/xhtml+xml", check=check)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert result == ("Visible\nTail", "application/xhtml+xml")
    assert peak < 8 * 1024 * 1024
    request.node.user_properties.append(("measurement", json.dumps({
        "declared_namespaces": 4098, "nested_elements": depth,
        "body_bytes": len(body), "parser_peak_traced_bytes": peak,
        "check_calls": checks, "seconds": round(time.perf_counter() - started, 6),
    }, sort_keys=True)))


@pytest.mark.parametrize("kind,code", [
    ("nesting", "source_document_complexity"),
    ("markup", "source_document_complexity"),
    ("text", "source_text_too_large"),
])
def test_xhtml_qname_path_preserves_limits_without_truncation(kind, code, monkeypatch):
    if kind == "nesting":
        body = b"<Scope>" * 513 + b"Visible" + b"</Scope>" * 513
    elif kind == "markup":
        body = b'<Scope title="' + b"x" * (1024 * 1024) + b'">Visible</Scope>'
    else:
        monkeypatch.setattr(mod, "MAX_TEXT_BYTES", 64)
        body = ("<Scope>" + "\u00e9" * 33 + "</Scope>").encode()
    with pytest.raises(SourceReadError, match=f"^{code}$"):
        mod.extract_document_text(body, "application/xhtml+xml", check=lambda: None)


def test_xhtml_case_preserving_qnames_admit_exact_nesting_limit():
    body = b"<Scope>" * 512 + b"Visible" + b"</Scope>" * 512
    assert mod.extract_document_text(body, "application/xhtml+xml", check=lambda: None) == (
        "Visible", "application/xhtml+xml")


def test_xhtml_qname_stream_cancels_without_text_or_large_retained_state(request):
    body = b"<Scope>" + b"<P>Bounded cancellation.</P>" * 50000 + b"</Scope>"
    calls = 0

    def check():
        nonlocal calls
        calls += 1
        if calls == 50:
            raise SourceReadError("source_read_cancelled")

    tracemalloc.start()
    try:
        with pytest.raises(SourceReadError, match="^source_read_cancelled$"):
            mod.extract_document_text(body, "application/xhtml+xml", check=check)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert calls == 50
    assert peak < 4 * 1024 * 1024
    request.node.user_properties.append(("measurement", json.dumps({
        "body_bytes": len(body), "parser_peak_traced_bytes": peak, "check_calls": calls,
    }, sort_keys=True)))
