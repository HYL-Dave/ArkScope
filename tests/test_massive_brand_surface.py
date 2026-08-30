from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_BARE_POLYGON = re.compile(r"\b(?:Polygon(?:\.io)?|POLYGON(?:\.IO)?)\b")


@dataclass(frozen=True, order=True)
class Occurrence:
    path: str
    text: str


_ALLOWLIST = {
    Occurrence(
        "src/massive_config_migration.py",
        '"""Explicit migration from the legacy Polygon credential namespace to Massive."""',
    ): "This names the retired credential namespace at the migration boundary.",
    Occurrence(
        "docs/design/ARKSCOPE_PROVIDER_CATALOG.md",
        "| **provider** | Massive.com (formerly Polygon.io). |",
    ): "The canonical provider catalog records the former legal brand once.",
    Occurrence(
        "data_sources/base.py",
        'POLYGON = "polygon"',
    ): "This is a durable enum member, not provider-facing copy.",
    Occurrence(
        "data_sources/ibkr_source.py",
        "return DataSourceType.POLYGON  # Reuse enum for now",
    ): "This is an existing durable enum reference, not provider-facing copy.",
    Occurrence(
        "src/tools/schemas.py",
        'POLYGON = "polygon"',
    ): "This is a durable wire enum member, not provider-facing copy.",
}

_CODE_ROOTS = (
    _REPO_ROOT / "src",
    _REPO_ROOT / "data_sources",
    _REPO_ROOT / "apps" / "arkscope-web" / "src",
)
_CURRENT_DOC_ROOTS = (
    _REPO_ROOT / "docs" / "data",
    _REPO_ROOT / "docs" / "design",
)
_CURRENT_DOC_FILES = (
    _REPO_ROOT / "README.md",
    _REPO_ROOT / "PROJECT_STRUCTURE.md",
    _REPO_ROOT / "config" / ".env.template",
    _REPO_ROOT / "data_sources" / "API_SPECIFICATIONS.md",
    _REPO_ROOT / "data_sources" / "DATA_SOURCE_QUIRKS.md",
    _REPO_ROOT / "data_sources" / "IBKR_GUIDE.md",
    _REPO_ROOT / "data_sources" / "PAID_SUBSCRIPTION_EVALUATION.tex",
)
_HISTORICAL_DOCS = frozenset(
    {
        "docs/design/PROJECT_PRIORITY_MAP.md",
        "docs/design/SLICE_7B3_SDK_DRIVER_DESIGN.md",
    }
)


def _source_files() -> list[Path]:
    files: set[Path] = set()
    for root in _CODE_ROOTS:
        files.update(
            path for path in root.rglob("*") if path.suffix in {".py", ".ts", ".tsx"}
        )
    for root in _CURRENT_DOC_ROOTS:
        files.update(path for path in root.rglob("*") if path.suffix in {".md", ".tex"})
    files.update(path for path in _CURRENT_DOC_FILES if path.exists())
    return sorted(
        path
        for path in files
        if ".test." not in path.name
        and "__pycache__" not in path.parts
        and path.relative_to(_REPO_ROOT).as_posix() not in _HISTORICAL_DOCS
    )


def _occurrences() -> set[Occurrence]:
    found: set[Occurrence] = set()
    for path in _source_files():
        relative = path.relative_to(_REPO_ROOT).as_posix()
        for line in path.read_text(encoding="utf-8").splitlines():
            if _BARE_POLYGON.search(line):
                found.add(Occurrence(relative, line.strip()))
    return found


def test_product_and_current_document_surfaces_have_only_reviewed_polygon_mentions():
    actual = _occurrences()
    expected = set(_ALLOWLIST)

    assert actual == expected, {
        "unreviewed": sorted(actual - expected),
        "stale_allowlist": sorted(expected - actual),
    }
    assert all(reason.strip() for reason in _ALLOWLIST.values())
