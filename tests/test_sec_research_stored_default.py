"""Omitted freshness is a local read at every public Research boundary."""

import asyncio
from contextlib import contextmanager
import hashlib
import inspect

import pytest

from src.sec_research.paths import SecResearchPaths
from src.sec_research.store import Store
from tests.test_sec_research_tool_adapters import (
    CHANNELS, NAMES, dispatch, registry, unwrap, wire,
)
from tests.test_sec_research_tool_service import (
    CIK, FILING_ID, doc_tool, document_rig, seed, tool_fixture,
)


def data_fingerprint(store):
    paths = store.paths
    files = [paths.market_db_path, paths.market_db_path.with_name(paths.market_db_path.name + "-wal")]
    for directory in ("objects", "staging"):
        files.extend((paths.capture_root / directory).rglob("*"))
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files if path.is_file()}


@pytest.mark.parametrize("channel", CHANNELS + ("service",))
@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("state", ("not-installed", "empty", "old"))
def test_omitted_freshness_never_acquires_or_changes_data(
    channel, name, state, registry, tool_fixture, monkeypatch, tmp_path,
):
    fixture = tool_fixture
    if state == "not-installed":
        fixture.service.store = Store(SecResearchPaths(tmp_path / "missing" / "market.db"))
    elif state == "old":
        seed(fixture)
        fixture.now = "2026-09-20T00:00:00Z"

    acquisitions = []

    @contextmanager
    def forbidden():
        acquisitions.append(True)
        raise ValueError("unexpected_acquisition")
        yield  # pragma: no cover

    fixture.service.acquisition_factory = forbidden
    wire(monkeypatch, fixture.service)
    before = data_fingerprint(fixture.service.store)
    arguments = {"filing_id": FILING_ID} if name == "read_sec_filing" else {"issuer": CIK}
    result = (fixture.service.invoke(name, arguments) if channel == "service"
              else unwrap(asyncio.run(dispatch(channel, registry, name, arguments))))
    assert acquisitions == []
    assert fixture.transport.calls == []
    assert data_fingerprint(fixture.service.store) == before
    if state == "not-installed":
        assert result["gaps"] == [{"code": "sec_research_not_installed"}]
        assert not fixture.service.store.paths.market_db_path.parent.exists()
    elif state == "old" and name != "read_sec_filing":
        assert result["status"] == "ok" and result["data"]


@pytest.mark.parametrize("name", NAMES)
def test_signature_and_exported_schema_have_stored_default(name, registry):
    from src.tools import sec_research_tools

    assert inspect.signature(getattr(sec_research_tools, name)).parameters["freshness"].default == "stored"
    parameter = next(p for p in registry.get(name).parameters if p.name == "freshness")
    assert parameter.default == "stored"
    assert "default" in registry.get(name).description.lower()


@pytest.mark.parametrize("channel", CHANNELS)
def test_default_reopens_document_without_acquisition(
    channel, registry, document_rig, monkeypatch,
):
    service, acquisitions = doc_tool(document_rig)
    document_rig.enqueue(b"<p>Stored filing text.</p>")
    original = service.invoke("read_sec_filing", {"filing_id": FILING_ID, "freshness": "refresh"})
    assert original["status"] in {"ok", "partial"}
    assert original["data"]["document"]["capture_id"]
    acquisitions.clear()
    document_rig.requests.clear()
    wire(monkeypatch, service)
    before = data_fingerprint(service.store)
    result = unwrap(asyncio.run(dispatch(channel, registry, "read_sec_filing", {"filing_id": FILING_ID})))
    assert result == original
    assert acquisitions == [] and document_rig.requests == []
    assert data_fingerprint(service.store) == before
