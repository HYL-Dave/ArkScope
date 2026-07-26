from __future__ import annotations

import inspect
from pathlib import Path

from src.tools.iv_skew_tools import get_iv_skew_analysis
from src.tools.option_chain_tools import get_option_chain
from src.tools.options_tools import calculate_greeks


ROOT = Path(__file__).resolve().parents[1]

LEGACY_RUNTIME_TOKENS = {
    "query_iv_history",
    "get_iv_history",
    "get_iv_history_df",
    "IVAnalysisResult",
    "IVHistoryPoint",
    'data_type == "iv_history"',
}


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_current_runtime_has_no_legacy_iv_storage_or_api_owner():
    runtime_owners = (
        "src/tools/backends/__init__.py",
        "src/tools/backends/db_backend.py",
        "src/tools/backends/file_backend.py",
        "src/tools/backends/local_market_backend.py",
        "src/tools/backends/sqlite_backend.py",
        "src/tools/data_access.py",
        "src/tools/schemas.py",
        "src/tools/options_tools.py",
        "src/api/routes/options.py",
        "src/api/routes/market_data.py",
        "src/api/app.py",
    )
    source = "\n".join(_read(path) for path in runtime_owners)

    for token in LEGACY_RUNTIME_TOKENS:
        assert token not in source
    assert not (ROOT / "src/api/routes/scan.py").exists()
    assert "scan_router" not in _read("src/api/app.py")

    former_job_owners = {
        "src/market_data_admin.py": (
            "_JOBS",
            "_JOBS_LOCK",
            "start_bootstrap_job",
            "start_update_job",
            "get_job",
        ),
        "src/api/routes/market_data.py": (
            "start_bootstrap_job",
            "get_job",
            "/market-data/jobs/",
        ),
        "apps/arkscope-web/src/api.ts": (
            "MarketDataJob",
            "getMarketDataJob",
            "/market-data/jobs/",
        ),
    }
    for path, tokens in former_job_owners.items():
        owner_source = _read(path)
        for token in tokens:
            assert token not in owner_source, f"{path} still owns {token}"


def test_retained_option_capabilities_do_not_import_legacy_iv_store():
    retained = (calculate_greeks, get_option_chain, get_iv_skew_analysis)
    for capability in retained:
        source = inspect.getsource(capability)
        assert "get_iv_history" not in source
        assert "query_iv_history" not in source


def test_non_migration_scripts_do_not_read_legacy_iv_store():
    scripts_root = ROOT / "scripts"
    current_scripts = [
        path
        for path in scripts_root.rglob("*.py")
        if "migration" not in path.relative_to(scripts_root).parts
    ]
    assert not (scripts_root / "analysis/compare_bs_vs_american.py").exists()
    assert not (scripts_root / "analysis/scan_option_mispricing.py").exists()

    for path in current_scripts:
        source = path.read_text(encoding="utf-8")
        assert "get_iv_history" not in source, str(path.relative_to(ROOT))
        assert "data/options/iv_history" not in source, str(path.relative_to(ROOT))


def test_sql_init_and_current_backends_have_no_legacy_iv_schema():
    owners = (
        "sql/001_init_schema.sql",
        "src/tools/backends/__init__.py",
        "src/tools/backends/db_backend.py",
        "src/tools/backends/file_backend.py",
        "src/tools/backends/local_market_backend.py",
        "src/tools/backends/sqlite_backend.py",
        "src/tools/data_access.py",
    )
    source = "\n".join(_read(path) for path in owners)
    assert "CREATE TABLE iv_history" not in source
    assert "query_iv_history" not in source
    assert "get_iv_history_df" not in source
    assert 'data_type == "iv_history"' not in source
