import ast
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("relative", [
    "data_sources/sec_filings.py",
    "data_sources/sec_earnings_releases.py",
    "src/security_lifecycle_news_evidence.py",
    "src/news_identity_repair.py",
    "data_sources/eodhd_source.py",
    "data_sources/alpha_vantage_source.py",
    "data_sources/finnhub_source.py",
    "data_sources/source_factory.py",
])
def test_abandoned_leaf_is_physically_absent(relative):
    assert not (ROOT / relative).exists(), f"abandoned leaf remains: {relative}"


def test_file_backend_is_physically_absent():
    assert not (ROOT / "src/tools/backends/file_backend.py").exists()


def test_file_backend_is_not_importable():
    import importlib.util

    assert importlib.util.find_spec("src.tools.backends.file_backend") is None


def test_data_source_package_does_not_import_abandoned_modules():
    code = """
import importlib.abc
import sys

class RejectAbandonedProviderImport(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {
            'data_sources.eodhd_source',
            'data_sources.alpha_vantage_source',
            'data_sources.finnhub_source',
            'data_sources.source_factory',
        }:
            raise AssertionError(f'abandoned provider import requested: {fullname}')
        return None

sys.meta_path.insert(0, RejectAbandonedProviderImport())
import data_sources
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_data_source_package_has_no_abandoned_exports():
    import data_sources

    abandoned = {
        "EODHDDataSource", "AlphaVantageDataSource", "FinnhubDataSource",
        "get_data_source", "list_available_sources", "register_source",
        "get_multi_source_news", "eodhd_source", "alpha_vantage_source",
        "finnhub_source", "source_factory",
    }
    assert not abandoned.intersection(data_sources.__all__)
    assert not abandoned.intersection(vars(data_sources))


def test_data_source_package_preserves_current_exports():
    import data_sources
    from data_sources import base, ibkr_source, polygon_source, sec_edgar_source

    for module, names in (
        (base, ("BaseDataSource", "NewsArticle", "StockPrice", "SECFiling")),
        (polygon_source, ("PolygonDataSource",)),
        (sec_edgar_source, ("SECEdgarDataSource",)),
        (ibkr_source, (
            "IBKRDataSource", "IntradayBar", "OptionChainParams", "OptionQuote",
            "OptionFilter", "OptionHistoricalBar", "ScannerResult",
        )),
    ):
        for name in names:
            assert name in data_sources.__all__, f"current export missing: {name}"
            assert getattr(data_sources, name, None) is getattr(module, name)


def test_factory_has_no_placeholder_class_or_export():
    tree = ast.parse((ROOT / "src/auth_drivers/factory.py").read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.ClassDef) and node.name == "NotImplementedDriver"
        for node in ast.walk(tree)
    ), "obsolete auth factory placeholder remains"
    exported = (ROOT / "src/auth_drivers/__init__.py").read_text(encoding="utf-8")
    assert "NotImplementedDriver" not in exported


def test_sec_company_event_collector_is_physically_absent():
    assert not (ROOT / "src/collectors/sec_corporate_actions.py").exists()


@pytest.mark.parametrize("relative", ["src/lifecycle_web_controller.py", "src/lifecycle_web_preflight.py",
                                      "src/api/routes/lifecycle_web.py"])
def test_case_scoped_web_execution_is_physically_absent(relative):
    assert not (ROOT / relative).exists()


def test_legacy_cutover_gate_is_absent_but_retained_action_reader_remains():
    from src.lifecycle_investigation import retirement

    assert not hasattr(retirement, "cutover_active")
    assert callable(retirement.retained_action_cases)


def test_current_sec_api_documentation_uses_active_owners():
    specification = (ROOT / "data_sources/API_SPECIFICATIONS.md").read_text(
        encoding="utf-8"
    )
    for obsolete in ("pip install edgartools", "from edgar import"):
        assert obsolete not in specification, f"obsolete SEC recommendation: {obsolete}"
    for owner in (
        "SECEdgarDataSource",
        "SECEdgarFinancials",
        "SecTransport",
        "SecRequestGovernor",
    ):
        assert owner in specification, f"current SEC owner missing: {owner}"
