"""Synthetic delivery-guard tests, never real provider or formal-state probes."""

import importlib.util
from pathlib import Path

import pytest

from src.tools.schemas import DetailedFinancials, FundamentalsResult


@pytest.fixture
def offline_guard(monkeypatch, tmp_path):
    monkeypatch.setenv("ARKSCOPE_VERIFICATION_WORK", str(tmp_path / "verification"))
    monkeypatch.setenv("ARKSCOPE_FORMAL_DATA", str(tmp_path / "synthetic-formal"))
    path = Path(__file__).resolve().parents[1] / "docs/superpowers/evidence/2026-09-27-provider-state/offline_tests.py"
    spec = importlib.util.spec_from_file_location("financial_delivery_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("event,args", [
    ("socket.connect", (None, ("example.invalid", 443))),
    ("socket.sendto", (None, ("192.0.2.1", 443))),
    ("socket.getaddrinfo", ("example.invalid", 443)),
    ("socket.gethostbyname", ("example.invalid",)),
    ("socket.gethostbyaddr", ("192.0.2.1",)),
    ("subprocess.Popen", ("codex", ["codex", "exec"])),
    ("subprocess.Popen", ("claude", ["claude", "-p", "synthetic"])),
])
def test_offline_guard_rejects_synthetic_acquisition_events(offline_guard, event, args):
    with pytest.raises(PermissionError, match="offline verification rejected"):
        offline_guard.audit(event, args)


@pytest.mark.parametrize("uri", [False, True])
def test_offline_guard_rejects_formal_sqlite_without_opening_it(offline_guard, uri):
    path = offline_guard.FORBIDDEN / "synthetic.db"
    value = f"file:{path}?mode=ro" if uri else str(path)
    with pytest.raises(PermissionError, match="formal database"):
        offline_guard.audit("sqlite3.connect", (value,))
    assert not path.exists()
    assert not path.parent.exists()


def test_offline_guard_allows_only_fixture_local_prerequisites(offline_guard):
    offline_guard.audit("sqlite3.connect", (":memory:",))
    offline_guard.audit("socket.connect", (None, ("127.0.0.1", 8488)))
    offline_guard.audit("subprocess.Popen", ("codex", ["codex", "--version"]))
    fixture_cli = str(offline_guard.FIXTURES / "bin" / "codex")
    offline_guard.audit("subprocess.Popen", (fixture_cli, [fixture_cli, "exec"]))


def test_common_result_schema_does_not_advertise_retired_sources():
    description = FundamentalsResult.model_json_schema()["properties"]["data_source"]["description"]
    assert "seeking_alpha" in description
    assert "financial_datasets" in description
    assert "sec_edgar" not in description
    assert "ibkr" not in description


def test_comparison_copy_matches_its_supported_sources():
    from src.tools.registry import create_default_registry

    tool = create_default_registry().get("compare_financial_sources")
    sources = next(parameter for parameter in tool.parameters if parameter.name == "sources")
    assert sources.items["enum"] == ["seeking_alpha", "financial_datasets"]
    assert "SA" in tool.description and "Financial Datasets" in tool.description
    assert "SEC" not in tool.description


def test_legacy_detailed_schema_does_not_promise_an_active_operation():
    description = DetailedFinancials.model_json_schema()["description"]
    assert "legacy" in description.lower()
    assert "financial_operation_not_ported" in description


def test_old_formula_reference_points_to_current_financial_contract():
    root = Path(__file__).resolve().parents[1]
    content = (root / "docs/analysis/FINANCIAL_METRICS_FORMULAS.md").read_text()
    header = content.split("## 1.", 1)[0]
    assert "Historical" in header
    assert "DATA_ACQUISITION_AND_UPDATES.md" in header
