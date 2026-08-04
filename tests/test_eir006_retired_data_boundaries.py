from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_DISCOVERY_ROOTS = ("src", "data_sources", "apps", "training", "docs", "tests", "config")
_SEARCH_PATTERNS = (
    "data/prices",
    "prices/15min",
    "prices/hourly",
    r"collection_summary\.json",
    "_get_current_price_ibkr",
    "metrics_.*_annual_y",
    r"dal\.get_fundamentals",
    "query_fundamentals",
    "ibkr_fundamentals",
    "FROM fundamentals",
    "local_ticker_coverage",
    "local_market_stats",
    "get_available_tickers",
    "get_ticker_data_coverage",
    "market_sync_meta",
)

_REWIRED_CURRENT = {
    "docs/analysis/FINANCIAL_METRICS_FORMULAS.md",
    "docs/data/DATA_INVENTORY.md",
    "docs/data/DATA_SUBSCRIPTION_GUIDE.md",
    "docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md",
    "src/agents/anthropic_agent/tools.py",
    "src/agents/cli.py",
    "src/agents/openai_agent/tools.py",
    "src/api/routes/health.py",
    "src/api/routes/market_data.py",
    "src/market_data_admin.py",
    "src/tools/analysis_tools.py",
    "src/tools/backends/local_market_backend.py",
    "src/tools/backends/sqlite_backend.py",
    "src/tools/data_coverage_tools.py",
    "src/tools/price_tools.py",
    "src/tools/registry.py",
}
_RETIRED_CURRENT = {
    "data_sources/financial_metrics_calculator.py",
    "src/daily_update.py",
    "src/tools/backends/file_backend.py",
    "training/data_prep/README.md",
    "training/data_prep/prepare_training_data.py",
}
_LOW_LEVEL_COMPATIBILITY = {
    "src/tools/backends/__init__.py",
    "src/tools/backends/db_backend.py",
    "src/tools/data_access.py",
}
_UNRELATED = {
    "docs/design/ARKSCOPE_TOOL_CATALOG.md",
    "src/api/routes/news.py",
    "src/auth_drivers/chatgpt_oauth_driver.py",
    "src/auth_drivers/claude_code_sdk_driver.py",
    "src/market_data_direct.py",
    "src/service/provider_health.py",
}
_HISTORICAL = {
    "data_sources/ibkr_client_id.py",
    "docs/design/DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md",
    "docs/design/ENGINEERING_ISSUE_REGISTER.md",
    "docs/design/LLM_AUTH_DRIVER_PLAN.md",
    "docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_AUDIT.md",
    "docs/design/NEWS_DIRECT_LOCAL_PLAN.md",
    "docs/design/PG_EXIT_N9_BATCH1_DROP_PLAN.md",
    "docs/design/PG_EXIT_N9_BATCH2_CLEANUP_PLAN.md",
    "docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md",
    "docs/design/PROJECT_PRIORITY_MAP.md",
    "docs/design/REPO_HYGIENE_AUDIT_2026_07.md",
    "docs/superpowers/evidence/2026-07-26-legacy-scheduler-iv-domain-retirement.md",
    "docs/superpowers/plans/2026-06-27-news-direct-cutover.md",
    "docs/superpowers/plans/2026-07-02-s-b-fundamentals-refetch-cache.md",
    "docs/superpowers/plans/2026-07-06-dead-code-ui-sweep.md",
    "docs/superpowers/plans/2026-07-06-scripts-runtime-consolidation.md",
    "docs/superpowers/plans/2026-07-07-current-quote-tool.md",
    "docs/superpowers/plans/2026-07-19-db-derived-universe-tickers-core-retirement.md",
    "docs/superpowers/plans/2026-07-26-legacy-scheduler-iv-domain-retirement.md",
    "docs/superpowers/plans/2026-07-31-eir-002-green-backend-baseline.md",
    "docs/superpowers/plans/2026-08-01-scripts-retirement-tranche-a.md",
    "docs/superpowers/specs/2026-07-08-holdings-portfolio-design.md",
    "docs/superpowers/specs/2026-07-26-legacy-scheduler-iv-domain-retirement-design.md",
    "docs/superpowers/specs/2026-07-31-eir-002-green-backend-baseline-design.md",
}
_EIR006_AUTHORITIES = {
    "docs/superpowers/evidence/2026-08-03-eir-006-valuation-price-truth.md",
    "docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/README.md",
    "docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/cache-classification.tsv",
    "docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/consumer-census.tsv",
    "docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/controller_probe.py",
    "docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/db-result.json",
    "docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/destructive_controller.py",
    "docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/legacy-price-files.tsv",
    "docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/old-cache-rows.tsv",
    "docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_db_row_manifest.py",
    "docs/superpowers/evidence/2026-08-04-eir-006-deletion-manifest/task8_price_manifest.py",
    "docs/superpowers/plans/2026-08-03-eir-006-valuation-price-truth.md",
    "docs/superpowers/specs/2026-08-01-eir-006-valuation-price-truth-design.md",
}
_TEST_FIXTURES = {
    "tests/test_agents.py",
    "tests/test_api.py",
    "tests/test_daily_update_wrapper.py",
    "tests/test_data_access.py",
    "tests/test_data_coverage_tools.py",
    "tests/test_db_backend.py",
    "tests/test_db_backend_retired_prices.py",
    "tests/test_detailed_financials.py",
    "tests/test_eir006_retired_data_boundaries.py",
    "tests/test_financial_metrics_calculator.py",
    "tests/test_ibkr_fundamentals.py",
    "tests/test_job_runs.py",
    "tests/test_market_data_admin.py",
    "tests/test_market_data_direct.py",
    "tests/test_sqlite_backend.py",
    "tests/test_stored_sec_projection.py",
    "tests/test_tools.py",
}

_OLD_AUTHORITY_PATTERNS = {
    "data/prices",
    "prices/15min",
    "prices/hourly",
    "collection_summary.json",
    "_get_current_price_ibkr",
    "dal.get_fundamentals",
    "ibkr_fundamentals",
}


def _read(relative_path: str) -> str:
    return (_ROOT / relative_path).read_text(encoding="utf-8")


def _discover_consumers() -> list[tuple[str, str]]:
    command = ["rg", "--json"]
    for pattern in _SEARCH_PATTERNS:
        command.extend(("-e", pattern))
    command.extend(_DISCOVERY_ROOTS)
    completed = subprocess.run(
        command,
        cwd=_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr

    rows: set[tuple[str, str]] = set()
    for raw_line in completed.stdout.splitlines():
        event = json.loads(raw_line)
        if event.get("type") != "match":
            continue
        data = event["data"]
        path = data["path"]["text"]
        for submatch in data["submatches"]:
            rows.add((path, submatch["match"]["text"]))
    return sorted(rows, key=lambda row: (row[0].encode(), row[1].encode()))


def _verdict(path: str) -> str:
    groups = (
        ("rewired_current_consumer", _REWIRED_CURRENT),
        ("retired_current_consumer", _RETIRED_CURRENT),
        ("low_level_empty_compatibility", _LOW_LEVEL_COMPATIBILITY),
        ("unrelated_lexical_hit", _UNRELATED),
        ("historical_reference", _HISTORICAL),
        ("test_fixture_reference", _TEST_FIXTURES),
    )
    matches = [name for name, paths in groups if path in paths]
    assert len(matches) == 1, f"unclassified or multiply classified consumer: {path} -> {matches}"
    return matches[0]


def test_current_docs_training_and_tool_copy_name_only_current_authorities():
    current_docs = (
        "docs/analysis/FINANCIAL_METRICS_FORMULAS.md",
        "docs/data/DATA_INVENTORY.md",
        "docs/data/DATA_SUBSCRIPTION_GUIDE.md",
        "docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md",
    )
    current_training = (
        "training/data_prep/prepare_training_data.py",
        "training/data_prep/README.md",
    )
    current_tool_copy = (
        "src/tools/registry.py",
        "src/agents/anthropic_agent/tools.py",
        "src/agents/openai_agent/tools.py",
        "src/tools/analysis_tools.py",
        "src/tools/schemas.py",
    )

    for path in (*current_docs, *current_training):
        text = _read(path)
        assert "data/prices" not in text, path
        assert "prices/15min" not in text, path
        assert "prices/hourly" not in text, path
        assert "collection_summary.json" not in text, path

    for path in current_docs:
        assert "market_data.db" in _read(path), path

    expected_tool_claim = (
        "Static SEC facts plus a qualified local completed-session price, "
        "or typed unavailable."
    )
    for path in current_tool_copy:
        text = _read(path)
        assert "IBKR real-time" not in text, path
        assert expected_tool_claim in text, path

    training_script = _read("training/data_prep/prepare_training_data.py")
    assert "direct IBKR TWS/Gateway daily fetch" in training_script
    file_backend = _read("src/tools/backends/file_backend.py")
    assert "retired empty compatibility" in file_backend.lower()


def test_current_runtime_consumer_census_is_closed_and_exact():
    rows = [row for row in _discover_consumers() if row[0] not in _EIR006_AUTHORITIES]
    classified = [(path, match, _verdict(path)) for path, match in rows]

    stale_current = [
        (path, match)
        for path, match, verdict in classified
        if verdict in {"rewired_current_consumer", "retired_current_consumer"}
        and (
            match in _OLD_AUTHORITY_PATTERNS
            or re.fullmatch(r"metrics_.*_annual_y", match)
        )
    ]
    assert stale_current == []

    current_runtime = "\n".join(
        (_ROOT / path).read_text(encoding="utf-8")
        for path in sorted(_REWIRED_CURRENT | _RETIRED_CURRENT)
        if path.endswith(".py")
    )
    assert re.search(r"(?:INSERT|REPLACE)(?:\s+OR\s+REPLACE)?\s+INTO\s+fundamentals", current_runtime, re.I) is None
    assert re.search(r"(?:INSERT|REPLACE)[^\n]*metrics_.*_annual_y", current_runtime, re.I) is None
