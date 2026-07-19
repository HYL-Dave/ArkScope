"""Explicit import and export compatibility for the retired universe JSON."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.active_universe import ActiveUniverseSnapshot
from src.profile_state import UniverseSourceAnnotation


ACTIVE_TIERS = ("tier1_core", "tier2_expanded", "tier3_user_watchlist")
KNOWN_RENAMES = {"LC": "HAPN"}
GENERATED_TIER = "tier3_user_watchlist"
GENERATED_CATEGORY = "db_derived_active"

_LEGACY_SOURCE_KEY = "legacy_config_seed"
_GENERATED_AUTHORITY = "profile_state.db + sa_capture.db via active_universe"
_GENERATED_WARNING = (
    "Generated compatibility snapshot; manual edits have no runtime effect"
)


@dataclass(frozen=True)
class LegacyUniverseEntry:
    ticker: str
    tier: str
    category_path: str


@dataclass(frozen=True)
class LegacyPreviewRow:
    ticker: str
    classification: Literal[
        "hidden", "overlap", "json_only", "db_only", "superseded_by_rename"
    ]
    default_action: Literal["annotate_only", "requires_approval", "do_not_import"]
    sources: tuple[str, ...]
    category_paths: tuple[str, ...]
    superseded_by: str | None = None


@dataclass(frozen=True)
class ReviewedLegacyImport:
    approved_memberships: tuple[str, ...]
    annotations: tuple[UniverseSourceAnnotation, ...]


def _normalize_ticker(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().upper()


def _category_parts(category_path: object) -> tuple[str, str] | None:
    if not isinstance(category_path, str):
        return None
    parts = category_path.split("/")
    if len(parts) != 2:
        return None
    tier, category = (part.strip() for part in parts)
    if tier not in ACTIVE_TIERS or not category or category.startswith("_"):
        return None
    return tier, category


def parse_active_json(
    document: Mapping[str, object]
) -> tuple[LegacyUniverseEntry, ...]:
    """Parse only active tier/category pairs from a loaded legacy document."""
    if not isinstance(document, Mapping):
        raise TypeError("legacy universe document must be a mapping")

    entries: set[LegacyUniverseEntry] = set()
    for tier in ACTIVE_TIERS:
        categories = document.get(tier)
        if not isinstance(categories, Mapping):
            continue
        category_names = sorted(
            key
            for key in categories
            if isinstance(key, str) and key and not key.startswith("_")
        )
        for category in category_names:
            category_value = categories[category]
            if isinstance(category_value, list):
                raw_tickers = category_value
            elif isinstance(category_value, Mapping) and isinstance(
                category_value.get("tickers"), list
            ):
                raw_tickers = category_value["tickers"]
            else:
                continue

            category_path = f"{tier}/{category}"
            for raw_ticker in raw_tickers:
                ticker = _normalize_ticker(raw_ticker)
                if ticker:
                    entries.add(
                        LegacyUniverseEntry(
                            ticker=ticker,
                            tier=tier,
                            category_path=category_path,
                        )
                    )

    return tuple(
        sorted(
            entries,
            key=lambda row: (row.ticker, row.tier, row.category_path),
        )
    )


def build_legacy_preview(
    entries: Iterable[LegacyUniverseEntry],
    *,
    snapshot: ActiveUniverseSnapshot,
    hidden_tickers: Iterable[str],
) -> tuple[LegacyPreviewRow, ...]:
    """Classify legacy entries against one complete active-universe snapshot."""
    categories_by_ticker: dict[str, set[str]] = {}
    for entry in entries:
        ticker = _normalize_ticker(entry.ticker)
        if ticker:
            categories_by_ticker.setdefault(ticker, set()).add(entry.category_path)

    active_tickers = {
        ticker
        for raw_ticker in snapshot.tickers
        if (ticker := _normalize_ticker(raw_ticker))
    }
    hidden = {
        ticker
        for raw_ticker in hidden_tickers
        if (ticker := _normalize_ticker(raw_ticker))
    }
    sources_by_ticker: dict[str, set[str]] = {}
    for raw_ticker, source_keys in snapshot.sources_by_ticker.items():
        ticker = _normalize_ticker(raw_ticker)
        if not ticker:
            continue
        sources_by_ticker.setdefault(ticker, set()).update(
            source.strip()
            for source in source_keys
            if isinstance(source, str) and source.strip()
        )

    rows: list[LegacyPreviewRow] = []
    for ticker in sorted(set(categories_by_ticker) | active_tickers):
        in_json = ticker in categories_by_ticker
        superseded_by = KNOWN_RENAMES.get(ticker)
        if ticker in hidden:
            classification = "hidden"
            default_action = "annotate_only"
            superseded_by = None
        elif in_json and superseded_by in active_tickers:
            classification = "superseded_by_rename"
            default_action = "do_not_import"
        elif in_json and ticker in active_tickers:
            classification = "overlap"
            default_action = "annotate_only"
            superseded_by = None
        elif in_json:
            classification = "json_only"
            default_action = "requires_approval"
            superseded_by = None
        else:
            classification = "db_only"
            default_action = "annotate_only"
            superseded_by = None

        rows.append(
            LegacyPreviewRow(
                ticker=ticker,
                classification=classification,
                default_action=default_action,
                sources=tuple(sorted(sources_by_ticker.get(ticker, set()))),
                category_paths=tuple(sorted(categories_by_ticker.get(ticker, set()))),
                superseded_by=superseded_by,
            )
        )

    return tuple(sorted(rows, key=lambda row: (row.ticker, row.classification)))


def build_reviewed_import(
    preview: Iterable[LegacyPreviewRow],
    approved_json_only: Iterable[str],
) -> ReviewedLegacyImport:
    """Materialize explicit membership decisions and all legacy annotations."""
    preview_rows = tuple(preview)
    approvable = {
        row.ticker
        for row in preview_rows
        if row.classification == "json_only"
        and row.default_action == "requires_approval"
    }

    approved: set[str] = set()
    for raw_ticker in approved_json_only:
        ticker = _normalize_ticker(raw_ticker)
        if not ticker:
            raise ValueError("approvals must name visible json_only tickers")
        approved.add(ticker)
    rejected = sorted(approved - approvable)
    if rejected:
        raise ValueError(
            "approvals must name visible json_only tickers: " + ", ".join(rejected)
        )

    annotations: set[UniverseSourceAnnotation] = set()
    for row in preview_rows:
        ticker = _normalize_ticker(row.ticker)
        if not ticker:
            raise ValueError("preview row ticker is required")
        tiers: set[str] = set()
        for category_path in row.category_paths:
            parts = _category_parts(category_path)
            if parts is None:
                raise ValueError(
                    f"invalid legacy category path for {ticker}: {category_path!r}"
                )
            tier, category = parts
            normalized_path = f"{tier}/{category}"
            tiers.add(tier)
            annotations.add(
                UniverseSourceAnnotation(
                    source_key=_LEGACY_SOURCE_KEY,
                    ticker=ticker,
                    annotation_key="legacy_category",
                    annotation_value=normalized_path,
                )
            )
        for tier in tiers:
            annotations.add(
                UniverseSourceAnnotation(
                    source_key=_LEGACY_SOURCE_KEY,
                    ticker=ticker,
                    annotation_key="legacy_tier",
                    annotation_value=tier,
                )
            )

    return ReviewedLegacyImport(
        approved_memberships=tuple(sorted(approved)),
        annotations=tuple(
            sorted(
                annotations,
                key=lambda row: (
                    row.source_key,
                    row.ticker,
                    row.annotation_key,
                    row.annotation_value,
                ),
            )
        ),
    )


def _paired_categories(
    snapshot_tickers: set[str],
    annotations: Iterable[UniverseSourceAnnotation],
) -> dict[str, set[tuple[str, str]]]:
    tiers_by_ticker: dict[str, set[str]] = {}
    categories_by_ticker: dict[str, set[tuple[str, str]]] = {}
    invalid_tickers: set[str] = set()

    for annotation in annotations:
        if annotation.source_key != _LEGACY_SOURCE_KEY:
            continue
        ticker = _normalize_ticker(annotation.ticker)
        if ticker not in snapshot_tickers:
            continue
        if annotation.annotation_key == "legacy_tier":
            tier = annotation.annotation_value.strip()
            if tier in ACTIVE_TIERS:
                tiers_by_ticker.setdefault(ticker, set()).add(tier)
            else:
                invalid_tickers.add(ticker)
        elif annotation.annotation_key == "legacy_category":
            parts = _category_parts(annotation.annotation_value)
            if parts is None:
                invalid_tickers.add(ticker)
            else:
                categories_by_ticker.setdefault(ticker, set()).add(parts)

    paired: dict[str, set[tuple[str, str]]] = {}
    annotated_tickers = set(tiers_by_ticker) | set(categories_by_ticker)
    for ticker in sorted(annotated_tickers | invalid_tickers):
        tiers = tiers_by_ticker.get(ticker, set())
        categories = categories_by_ticker.get(ticker, set())
        category_tiers = {tier for tier, _category in categories}
        if ticker in invalid_tickers or tiers != category_tiers:
            raise ValueError(
                f"annotation snapshot mismatch for {ticker}: "
                "legacy tiers and category paths differ"
            )
        if categories:
            paired[ticker] = categories
    return paired


def build_compat_export(
    snapshot: ActiveUniverseSnapshot,
    annotations: Iterable[UniverseSourceAnnotation],
) -> dict[str, object]:
    """Build a deterministic generated document for explicit compatibility."""
    snapshot_tickers = set(snapshot.tickers)
    paired_categories = _paired_categories(snapshot_tickers, annotations)
    grouped: dict[str, dict[str, set[str]]] = {tier: {} for tier in ACTIVE_TIERS}

    for ticker in sorted(snapshot_tickers):
        categories = paired_categories.get(ticker, set())
        if not categories:
            grouped[GENERATED_TIER].setdefault(GENERATED_CATEGORY, set()).add(ticker)
            continue
        for tier, category in sorted(categories):
            grouped[tier].setdefault(category, set()).add(ticker)

    document: dict[str, object] = {
        "_generated": {
            "authority": _GENERATED_AUTHORITY,
            "warning": _GENERATED_WARNING,
            "generated_at": snapshot.generated_at,
        }
    }
    for tier in ACTIVE_TIERS:
        document[tier] = {
            category: {"tickers": sorted(tickers & snapshot_tickers)}
            for category, tickers in sorted(grouped[tier].items())
            if tickers & snapshot_tickers
        }

    flattened = flatten_generated_active_tickers(document)
    if flattened != snapshot_tickers:
        missing = sorted(snapshot_tickers - flattened)
        extra = sorted(flattened - snapshot_tickers)
        raise ValueError(
            f"generated export active ticker mismatch: missing={missing}, extra={extra}"
        )
    return document


def flatten_generated_active_tickers(document: Mapping[str, object]) -> set[str]:
    """Return the normalized active ticker set from generated tier groups."""
    return {entry.ticker for entry in parse_active_json(document)}


def write_compat_export(path: str | Path, document: Mapping[str, object]) -> None:
    """Atomically replace an explicitly requested compatibility export."""
    target = Path(path)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(
                document,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
            handle.flush()
            os.fchmod(handle.fileno(), 0o600)
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except Exception:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        raise
