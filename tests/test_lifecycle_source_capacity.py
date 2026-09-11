from dataclasses import asdict, replace
import hashlib
import json

import pytest

from tests.test_security_lifecycle_web_finding import source_page


@pytest.mark.parametrize("text", [
    "plain ASCII", "quoted \"value\" \\ tab\tline\n", "\u4e0b\u5e02 / \U00020000",
    "x" * 65535 + "\U00020000\"\\" + "\u4e2d" * 70000,
], ids=["ascii", "escapes", "unicode", "chunk_boundary"])
def test_streamed_page_fingerprints_are_byte_identical_to_legacy_json(text):
    from src.lifecycle_public_sources import _capture_digest, _page_material_digest

    page = source_page(text)
    material = asdict(page)
    expected = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
    assert _page_material_digest(material) == expected(material)
    material.pop("capture_sha256")
    assert _capture_digest(page) == expected(material)
    assert _capture_digest(replace(page, text=text + "changed")) != _capture_digest(page)


def test_large_page_hash_never_serializes_the_whole_source_at_once(monkeypatch):
    from src import lifecycle_public_sources as sources

    page = source_page("\U00020000" * (512 * 1024))
    expected = page.capture_sha256
    original = json.dumps
    chunks = []

    def bounded(value, **kwargs):
        if isinstance(value, dict):
            assert len(value.get("text", "")) <= 65536
        if isinstance(value, str):
            assert len(value) <= 65536
            chunks.append(len(value))
        return original(value, **kwargs)

    monkeypatch.setattr(sources.json, "dumps", bounded)
    assert sources._capture_digest(page) == expected
    assert len([length for length in chunks if length == 65536]) == 8


@pytest.mark.parametrize("mime", ["text/plain", "application/json", "application/xml"])
def test_full_context_reuses_the_retained_text_without_a_second_source_copy(mime):
    from src.lifecycle_public_sources import _capture_digest
    from src.lifecycle_source_context import select_source_context
    from tests.test_security_lifecycle_web_finding import public_input

    text = "\U00020000" * 50000
    if mime == "application/json":
        text = json.dumps({"description": text}, ensure_ascii=False)
    elif mime == "application/xml":
        text = "<description>" + text + "</description>"
    page = replace(source_page(text), mime_type=mime)
    page = replace(page, capture_sha256=_capture_digest(page))
    material = select_source_context(public_input(), page).prompt_material(page)
    assert material["coverage"] == "full_text"
    assert material["passages"][0]["text"] is page.text
    assert material["passages"][0]["end_byte"] == len(text.encode())
