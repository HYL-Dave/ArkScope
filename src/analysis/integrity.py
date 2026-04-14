"""Integrity validation and minimal repair helpers for Phase D artifacts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, List, Sequence

from .contracts import AnalysisArtifact, IntegrityResult

DEFAULT_REQUIRED_PATHS: tuple[str, ...] = (
    "final_decision.summary",
    "final_decision.action",
    "report_sections.executive_summary",
)


def _get_nested_value(data: Any, path: str) -> Any:
    """Resolve a dot-separated path against nested dicts."""
    current = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_nested_value(data: Any, path: str, value: Any) -> bool:
    """Set a dot-separated path in nested dicts, creating missing dicts."""
    if not isinstance(data, dict):
        return False
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        child = current.get(part)
        if child is None:
            child = {}
            current[part] = child
        if not isinstance(child, dict):
            return False
        current = child
    current[parts[-1]] = value
    return True


def _is_missing_value(value: Any) -> bool:
    """Return True when a required artifact field should be treated as missing."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def collect_missing_required_fields(
    artifact: AnalysisArtifact,
    required_paths: Sequence[str] | None = None,
) -> List[str]:
    """Collect missing required field paths from an analysis artifact."""
    required = tuple(required_paths or DEFAULT_REQUIRED_PATHS)
    root = {
        "request": artifact.request,
        "context_summary": artifact.context_summary,
        "strategy_results": artifact.strategy_results,
        "final_decision": artifact.final_decision,
        "report_sections": artifact.report_sections,
        "degradation_summary": artifact.degradation_summary,
    }
    missing: List[str] = []
    for path in required:
        value = _get_nested_value(root, path)
        if _is_missing_value(value):
            missing.append(path)
    return missing


def apply_placeholder_fill(
    artifact: AnalysisArtifact,
    missing_fields: Iterable[str],
    placeholder: str = "TBD",
) -> List[str]:
    """Apply minimal placeholder repair to missing required fields."""
    root = {
        "final_decision": deepcopy(artifact.final_decision),
        "report_sections": deepcopy(artifact.report_sections),
    }
    repairs: List[str] = []
    for path in missing_fields:
        if path.startswith("final_decision.") and _set_nested_value(root["final_decision"], path.removeprefix("final_decision."), placeholder):
            repairs.append(f"{path}=placeholder")
            continue
        if path.startswith("report_sections.") and _set_nested_value(root["report_sections"], path.removeprefix("report_sections."), placeholder):
            repairs.append(f"{path}=placeholder")
    if repairs:
        artifact.final_decision = root["final_decision"]
        artifact.report_sections = root["report_sections"]
        artifact.integrity_status = "placeholder_filled"
    return repairs


def validate_and_repair_artifact(
    artifact: AnalysisArtifact,
    required_paths: Sequence[str] | None = None,
    placeholder: str = "TBD",
) -> IntegrityResult:
    """Validate an artifact and apply minimal placeholder repair when needed."""
    missing = collect_missing_required_fields(artifact, required_paths=required_paths)
    if not missing:
        artifact.integrity_status = "clean"
        return IntegrityResult(artifact=artifact, status="clean")

    repairs = apply_placeholder_fill(artifact, missing, placeholder=placeholder)
    status = "placeholder_filled" if repairs else "repaired"
    artifact.integrity_status = status
    return IntegrityResult(
        artifact=artifact,
        status=status,
        missing_fields=list(missing),
        repairs_applied=repairs,
    )
