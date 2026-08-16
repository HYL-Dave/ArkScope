from __future__ import annotations

import ast
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "src" / "market_coverage"


def _python_sources(*extra: Path) -> tuple[Path, ...]:
    return tuple(sorted(PACKAGE_ROOT.glob("*.py"))) + extra


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return tuple(imported)




def test_market_coverage_package_exports_no_write_or_repair_operation():
    package = importlib.import_module("src.market_coverage")
    exported = getattr(package, "__all__", None)
    assert isinstance(exported, tuple), "Coverage v2 must declare its public read API"
    forbidden_verbs = (
        "write",
        "repair",
        "backfill",
        "fetch",
        "collect",
        "schedule",
        "mutate",
    )

    assert exported
    assert not {
        name
        for name in exported
        if name.lower().startswith(forbidden_verbs)
    }
    service = getattr(package, "TradingDayCoverageService", None)
    assert service is not None
    public_methods = {
        name for name in vars(service) if not name.startswith("_")
    }
    assert public_methods == {"get_coverage"}


def test_backend_v2_contract_and_source_contain_no_retired_coverage_fields():
    from src.market_coverage import models

    dto_type = getattr(models, "TradingDayCoverageV2", None)
    day_type = getattr(models, "CoverageDayV2", None)
    partial_type = getattr(models, "PartialTickerCoverageV2", None)
    assert dto_type is not None and day_type is not None and partial_type is not None

    retired = {
        "max_observed_bar_count",
        "full",
        "well_covered",
        "covered",
        "missing",
        "missing_tickers",
        "session_complete",
        "thin",
        "complete_like",
    }
    assert not (retired & set(dto_type.model_fields))
    assert not (retired & set(day_type.model_fields))
    assert set(partial_type.model_fields) == {
        "ticker",
        "observed_slot_count",
        "expected_slot_count",
    }

    product_sources = _python_sources(
        ROOT / "src" / "api" / "routes" / "market_data.py",
        ROOT / "src" / "market_data_direct.py",
    )
    unambiguous_retired_tokens = (
        "summarize_trading_day_coverage",
        "_THIN_BAR_THRESHOLD",
        "_COMPLETE_COVERED_RATIO",
        "max_observed_bar_count",
        "well_covered",
        "missing_tickers",
        "complete_like",
    )
    token_offenders = {
        str(path.relative_to(ROOT)): tuple(
            token
            for token in unambiguous_retired_tokens
            if token in path.read_text(encoding="utf-8")
        )
        for path in product_sources
    }
    assert not {
        path: tokens for path, tokens in token_offenders.items() if tokens
    }

    exact_literal_offenders: dict[str, tuple[str, ...]] = {}
    for path in product_sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        literals = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in retired
        }
        if literals:
            exact_literal_offenders[str(path.relative_to(ROOT))] = tuple(
                sorted(literals)
            )
    assert not exact_literal_offenders


def test_scheduler_has_no_planner_missing_feed_or_unknown_exclusion_path():
    planner = ROOT / "src" / "scheduler_planner.py"
    scheduler = ROOT / "src" / "service" / "data_scheduler.py"
    scheduler_source = scheduler.read_text(encoding="utf-8")
    forbidden = (
        "scheduler_planner",
        "plan_price_backfill",
        "missing_tickers",
        "exclude_tickers",
        "gap_planned",
    )
    offenders = [token for token in forbidden if token in scheduler_source]

    assert not planner.exists(), "Task 6 retires the planner owner"
    assert not offenders, offenders


def test_coverage_enum_consumers_use_exact_exhaustive_matching():
    service = PACKAGE_ROOT / "service.py"
    assert service.is_file(), "Coverage v2 service is required"
    route = ROOT / "src" / "api" / "routes" / "market_data.py"
    forbidden_methods = {"startswith", "endswith", "find", "search", "match"}
    offenders: list[str] = []
    exhaustive_guards: list[str] = []

    for path in _python_sources(route):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imported = _imports(path)
                if any(name == "re" for name in imported):
                    offenders.append(f"{path.relative_to(ROOT)}: regex import")
                    break
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in forbidden_methods:
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: {node.func.attr}"
                    )
            if isinstance(node, ast.Match):
                for case in node.cases:
                    pattern = case.pattern
                    if not (
                        isinstance(pattern, ast.MatchAs)
                        and pattern.pattern is None
                        and pattern.name is not None
                    ):
                        continue
                    calls = (
                        child
                        for statement in case.body
                        for child in ast.walk(statement)
                        if isinstance(child, ast.Call)
                    )
                    if any(
                        isinstance(call.func, ast.Name)
                        and call.func.id == "assert_never"
                        and len(call.args) == 1
                        and isinstance(call.args[0], ast.Name)
                        and call.args[0].id == pattern.name
                        for call in calls
                    ):
                        exhaustive_guards.append(str(path.relative_to(ROOT)))
            if isinstance(node, ast.Compare):
                values = (node.left, *node.comparators)
                has_semantic_value = any(
                    isinstance(value, ast.Attribute)
                    and value.attr in {"status", "reason_code", "value"}
                    for value in values
                )
                has_string = any(
                    isinstance(value, ast.Constant) and isinstance(value.value, str)
                    for value in values
                )
                if has_semantic_value and has_string:
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: string enum compare"
                    )

    assert not offenders, offenders
    assert "src/market_coverage/service.py" in exhaustive_guards
