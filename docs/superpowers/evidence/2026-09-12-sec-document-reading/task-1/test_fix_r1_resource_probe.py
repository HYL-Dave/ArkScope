"""Bounded namespace-delta allocation probe; no input allocation is traced."""

import json
import time
import tracemalloc

import pytest

from src.sec_research.document_text import extract_document_text


@pytest.mark.parametrize("depth", [32, 400])
def test_namespace_scopes_do_not_multiply_inherited_maps(request, depth):
    attributes = " ".join(f'xmlns:n{index}="urn:scope:{index}"' for index in range(4096))
    body = (f'<root {attributes} xmlns:inl="http://www.xbrl.org/2013/inlineXBRL">'
            + "<div>" * depth
            + '<inl:hidden>HIDDEN</inl:hidden><p>Visible</p>'
            + "</div>" * depth + "</root>").encode()
    checks = 0

    def check():
        nonlocal checks
        checks += 1

    started = time.perf_counter()
    tracemalloc.start()
    try:
        result = extract_document_text(body, "text/html", check=check)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert result == ("Visible", "text/html")
    assert peak < 8 * 1024 * 1024
    request.node.user_properties.append(("measurement", json.dumps({
        "declared_namespaces": 4097, "nested_elements": depth,
        "body_bytes": len(body), "parser_peak_traced_bytes": peak,
        "check_calls": checks, "seconds": round(time.perf_counter() - started, 6),
    }, sort_keys=True)))
