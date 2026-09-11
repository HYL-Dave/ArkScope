"""Focused frozen-Task1 storage-shape probe; no current product code edits."""

import importlib
import subprocess
import sys
import types

import pytest


HEAD = "e207b3ad495729958f0f2340cb0a012c6272a521"
ROOT = "/tmp/arkscope-listing-sec-macro-convergence"
CIK = "0000320193"
WHEN = "2026-09-11T12:00:00Z"


@pytest.fixture
def frozen(monkeypatch):
    package = importlib.import_module("src.sec_research")
    for name in ("schema", "store", "queries"):
        fullname = "src.sec_research." + name
        source = subprocess.check_output(
            ["git", "show", HEAD + ":src/sec_research/" + name + ".py"],
            cwd=ROOT,
        )
        module = types.ModuleType(fullname)
        module.__file__ = HEAD + ":src/sec_research/" + name + ".py"
        monkeypatch.setitem(sys.modules, fullname, module)
        monkeypatch.setattr(package, name, module, raising=False)
        exec(compile(source, module.__file__, "exec"), module.__dict__)
    return package.store.Store, package.queries.StoredQueries


@pytest.mark.parametrize("bindings", ["{}", "PRIVATE invalid JSON", "null", "1"])
def test_invalid_stored_binding_shape_has_closed_envelope(tmp_path, frozen, bindings):
    from src.sec_research.paths import SecResearchPaths

    store_type, query_type = frozen
    store = store_type(SecResearchPaths(tmp_path / "market.db"))
    store.install()
    with store.connect() as conn:
        conn.execute(
            """INSERT INTO sec_research_receipts
            (cik, status, completed, pending, gaps, observed_at, recorded_at, source_snapshots)
            VALUES (?, 'ok', '[]', '[]', '[]', ?, ?, ?)""",
            (CIK, WHEN, WHEN, bindings),
        )
    result = query_type(store).filings(CIK)
    assert result["status"] == "unavailable"
    assert result["data"] == []
    assert set(result) == {"status", "data", "gaps", "observed_at", "coverage", "next_cursor"}
