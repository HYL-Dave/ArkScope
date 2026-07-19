"""Fingerprint-gated maintenance commands for retiring the legacy universe JSON.

This module is an operator tool, not a runtime dependency. Preview and
fingerprint reads open SQLite databases read-only and never initialize schema.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import threading
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from src.active_universe import (
    ActiveUniverseUnavailable,
    EQUITY_ASSET_CLASSES,
    build_active_universe_snapshot,
)
from src.profile_state import ProfileStateStore, UniverseSourceAnnotation
from src.universe_compat import (
    LegacyPreviewRow,
    ReviewedLegacyImport,
    build_compat_export,
    build_legacy_preview,
    build_reviewed_import,
    flatten_generated_active_tickers,
    parse_active_json,
    write_compat_export,
)


_LEGACY_SOURCE_KEY = "legacy_config_seed"
_FINGERPRINT_KEYS = (
    "legacy_json_sha256",
    "profile_sources_sha256",
    "sa_sources_sha256",
    "legacy_overview_sha256",
)

_PROFILE_SCHEMA = {
    "watchlists": frozenset({"id", "name", "kind", "archived_at"}),
    "watchlist_memberships": frozenset({"list_id", "ticker", "archived_at"}),
    "portfolio_accounts": frozenset({"id", "archived_at"}),
    "portfolio_positions": frozenset(
        {"account_id", "symbol", "asset_class", "closed_at"}
    ),
    "ticker_meta": frozenset({"ticker", "hidden_at"}),
    "universe_source_memberships": frozenset(
        {"source_key", "ticker", "created_at", "archived_at"}
    ),
    "universe_source_annotations": frozenset(
        {"source_key", "ticker", "annotation_key", "annotation_value"}
    ),
}
_PROFILE_UNIQUE_SHAPES = {
    "universe_source_memberships": ("source_key", "ticker"),
    "universe_source_annotations": (
        "source_key",
        "ticker",
        "annotation_key",
        "annotation_value",
    ),
}
_SA_SCHEMA = {
    "sa_alpha_picks": frozenset(
        {"symbol", "portfolio_status", "is_stale"}
    ),
    "sa_refresh_meta": frozenset(
        {
            "scope",
            "last_attempt_at",
            "last_success_at",
            "snapshot_ts",
            "row_count",
            "ok",
            "last_error",
            "updated_at",
        }
    ),
}


class UniverseRetirementError(RuntimeError):
    """Base class for sanitized operator-facing failures."""

    code = "universe_retirement_failed"

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code}


class RequiredSchemaMissing(UniverseRetirementError):
    code = "required_schema_missing"

    def __init__(self, source: str, missing: Iterable[str]):
        self.source = source
        self.missing = tuple(sorted(set(missing)))
        super().__init__(f"{self.code}: {source}")

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "source": self.source}


class SourceUnavailable(UniverseRetirementError):
    code = "source_unavailable"

    def __init__(self, source: str, reason: str):
        self.source = source
        self.reason = reason
        super().__init__(f"{self.code}: {source}:{reason}")

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "source": self.source, "reason": self.reason}


class InvalidLegacyJson(UniverseRetirementError):
    code = "invalid_legacy_json"

    def __init__(self):
        super().__init__(self.code)


class InvalidPreviewReport(UniverseRetirementError):
    code = "invalid_preview_report"

    def __init__(self):
        super().__init__(self.code)


class FingerprintMismatch(UniverseRetirementError):
    code = "fingerprint_mismatch"

    def __init__(self, changed: Iterable[str]):
        changed_set = set(changed)
        self.changed = tuple(key for key in _FINGERPRINT_KEYS if key in changed_set)
        super().__init__(f"{self.code}: {','.join(self.changed)}")

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "changed": list(self.changed)}


class OverviewCoverageError(UniverseRetirementError):
    code = "legacy_overview_not_represented"

    def __init__(self, missing: Iterable[str]):
        self.missing = tuple(sorted(set(missing)))
        super().__init__(f"{self.code}: {','.join(self.missing)}")

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "missing": list(self.missing)}


class ApprovalMismatch(UniverseRetirementError):
    code = "approval_mismatch"

    def __init__(self, *, missing: Iterable[str], extra: Iterable[str]):
        self.missing = tuple(sorted(set(missing)))
        self.extra = tuple(sorted(set(extra)))
        super().__init__(self.code)

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "missing": list(self.missing),
            "extra": list(self.extra),
        }


class InvalidApproval(UniverseRetirementError):
    code = "invalid_approval"

    def __init__(self):
        super().__init__(self.code)


class TransitionParityError(UniverseRetirementError):
    code = "transition_parity_failed"

    def __init__(self):
        super().__init__(self.code)


class RestoreRequired(UniverseRetirementError):
    code = "restore_required"

    def __init__(self, stage: str):
        self.stage = stage
        super().__init__(f"{self.code}: {stage}")

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "stage": self.stage}


class OutputPathConflict(UniverseRetirementError):
    code = "output_path_conflict"

    def __init__(self):
        super().__init__(self.code)


class OutputPreflightError(UniverseRetirementError):
    code = "output_preflight_failed"

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"{self.code}: {reason}")

    def as_dict(self) -> dict[str, object]:
        return {"code": self.code, "reason": self.reason}


class OverviewUnavailable(UniverseRetirementError):
    code = "legacy_overview_unavailable"

    def __init__(self):
        super().__init__(self.code)


@dataclass(frozen=True)
class InputFingerprints:
    legacy_json_sha256: str
    profile_sources_sha256: str
    sa_sources_sha256: str
    legacy_overview_sha256: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: object) -> "InputFingerprints":
        if not isinstance(value, Mapping) or set(value) != set(_FINGERPRINT_KEYS):
            raise InvalidPreviewReport
        fields: dict[str, str] = {}
        for key in _FINGERPRINT_KEYS:
            digest = value.get(key)
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise InvalidPreviewReport
            fields[key] = digest
        return cls(**fields)


@dataclass(frozen=True)
class _ProfileSources:
    active_lists: tuple[tuple[str, str, str], ...]
    open_portfolio: tuple[tuple[str, str], ...]
    hidden: tuple[str, ...]
    legacy_membership: tuple[str, ...]
    annotations: tuple[tuple[str, str, str, str], ...]

    def fingerprint_payload(self) -> dict[str, object]:
        return {
            "active_lists": self.active_lists,
            "open_portfolio": self.open_portfolio,
            "hidden": self.hidden,
            "legacy_membership": self.legacy_membership,
            "annotations": self.annotations,
        }


@dataclass(frozen=True)
class _SaSources:
    current_nonstale_picks: tuple[str, ...]
    current_refresh_meta: tuple[object, ...] | None

    def fingerprint_payload(self) -> dict[str, object]:
        return {
            "current_nonstale_picks": self.current_nonstale_picks,
            "current_refresh_meta": self.current_refresh_meta,
        }


@dataclass(frozen=True)
class _InputState:
    legacy_json_bytes: bytes
    profile: _ProfileSources
    sa: _SaSources
    overview_tickers: tuple[str, ...]
    fingerprints: InputFingerprints


def _normalize_ticker(value: object) -> str:
    return value.strip().upper() if isinstance(value, str) else ""


def _normalize_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize_asset_class(value: object) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def _normalize_ticker_set(values: Iterable[object]) -> tuple[str, ...]:
    if isinstance(values, str):
        values = (values,)
    return tuple(
        sorted(
            {
                ticker
                for value in values
                if (ticker := _normalize_ticker(value))
            }
        )
    )


def _normalize_approvals(values: Iterable[object]) -> tuple[str, ...]:
    if isinstance(values, str):
        values = (values,)
    normalized: set[str] = set()
    for value in values:
        ticker = _normalize_ticker(value)
        if not ticker:
            raise InvalidApproval
        normalized.add(ticker)
    return tuple(sorted(normalized))


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _semantic_hash(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _open_read_only(path: str | Path, source: str) -> sqlite3.Connection:
    candidate = Path(path)
    if not candidate.is_file():
        raise SourceUnavailable(source, "source_db_missing")
    try:
        connection = sqlite3.connect(
            f"{candidate.resolve().as_uri()}?mode=ro",
            uri=True,
            timeout=5.0,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        return connection
    except sqlite3.DatabaseError:
        raise SourceUnavailable(source, "source_db_unreadable") from None


def _quoted_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _require_schema(
    connection: sqlite3.Connection,
    source: str,
    requirements: Mapping[str, frozenset[str]],
    unique_shapes: Mapping[str, tuple[str, ...]] | None = None,
) -> None:
    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    missing: list[str] = []
    for table, required_columns in requirements.items():
        if table not in tables:
            missing.append(table)
            continue
        columns = {
            row["name"]
            for row in connection.execute(
                f"PRAGMA table_info({_quoted_identifier(table)})"
            ).fetchall()
        }
        missing.extend(
            f"{table}.{column}" for column in sorted(required_columns - columns)
        )
    for table, required_shape in (unique_shapes or {}).items():
        if table not in tables:
            continue
        unique_column_shapes: set[tuple[str, ...]] = set()
        table_info = connection.execute(
            f"PRAGMA table_info({_quoted_identifier(table)})"
        ).fetchall()
        primary_key = tuple(
            row["name"]
            for row in sorted(
                (row for row in table_info if int(row["pk"]) > 0),
                key=lambda row: int(row["pk"]),
            )
        )
        if primary_key:
            unique_column_shapes.add(primary_key)
        indexes = connection.execute(
            f"PRAGMA index_list({_quoted_identifier(table)})"
        ).fetchall()
        for index in indexes:
            if not int(index["unique"]) or int(index["partial"]):
                continue
            columns = connection.execute(
                f"PRAGMA index_info({_quoted_identifier(index['name'])})"
            ).fetchall()
            unique_column_shapes.add(
                tuple(
                    row["name"]
                    for row in sorted(columns, key=lambda row: int(row["seqno"]))
                )
            )
        if required_shape not in unique_column_shapes:
            missing.append(f"{table}.unique({','.join(required_shape)})")
    if missing:
        raise RequiredSchemaMissing(source, missing)


def _read_profile_sources(path: str | Path) -> _ProfileSources:
    connection = _open_read_only(path, "profile")
    try:
        _require_schema(
            connection,
            "profile",
            _PROFILE_SCHEMA,
            _PROFILE_UNIQUE_SHAPES,
        )
        active_list_rows = connection.execute(
            """
            SELECT w.name, w.kind, m.ticker
            FROM watchlist_memberships AS m
            JOIN watchlists AS w ON w.id = m.list_id
            WHERE m.archived_at IS NULL AND w.archived_at IS NULL
            """
        ).fetchall()
        portfolio_rows = connection.execute(
            """
            SELECT p.symbol, p.asset_class
            FROM portfolio_positions AS p
            JOIN portfolio_accounts AS a ON a.id = p.account_id
            WHERE p.closed_at IS NULL AND a.archived_at IS NULL
            """
        ).fetchall()
        hidden_rows = connection.execute(
            "SELECT ticker FROM ticker_meta WHERE hidden_at IS NOT NULL"
        ).fetchall()
        legacy_rows = connection.execute(
            "SELECT ticker FROM universe_source_memberships "
            "WHERE source_key=? AND archived_at IS NULL",
            (_LEGACY_SOURCE_KEY,),
        ).fetchall()
        annotation_rows = connection.execute(
            "SELECT source_key, ticker, annotation_key, annotation_value "
            "FROM universe_source_annotations"
        ).fetchall()
    except RequiredSchemaMissing:
        raise
    except sqlite3.DatabaseError:
        raise SourceUnavailable("profile", "source_db_unreadable") from None
    finally:
        connection.close()

    active_lists = tuple(
        sorted(
            (
                _normalize_text(row["name"]),
                _normalize_text(row["kind"]),
                _normalize_ticker(row["ticker"]),
            )
            for row in active_list_rows
        )
    )
    open_portfolio = tuple(
        sorted(
            (
                _normalize_ticker(row["symbol"]),
                _normalize_asset_class(row["asset_class"]),
            )
            for row in portfolio_rows
        )
    )
    hidden = tuple(sorted(_normalize_ticker(row["ticker"]) for row in hidden_rows))
    legacy_membership = tuple(
        sorted(_normalize_ticker(row["ticker"]) for row in legacy_rows)
    )
    annotations = tuple(
        sorted(
            (
                _normalize_text(row["source_key"]),
                _normalize_ticker(row["ticker"]),
                _normalize_text(row["annotation_key"]),
                _normalize_text(row["annotation_value"]),
            )
            for row in annotation_rows
        )
    )
    return _ProfileSources(
        active_lists=active_lists,
        open_portfolio=open_portfolio,
        hidden=hidden,
        legacy_membership=legacy_membership,
        annotations=annotations,
    )


def _read_sa_sources(path: str | Path) -> _SaSources:
    connection = _open_read_only(path, "sa")
    try:
        _require_schema(connection, "sa", _SA_SCHEMA)
        pick_rows = connection.execute(
            "SELECT symbol FROM sa_alpha_picks "
            "WHERE portfolio_status='current' AND is_stale=0"
        ).fetchall()
        refresh_row = connection.execute(
            "SELECT last_attempt_at, last_success_at, snapshot_ts, row_count, ok, "
            "last_error, updated_at FROM sa_refresh_meta WHERE scope='current'"
        ).fetchone()
    except RequiredSchemaMissing:
        raise
    except sqlite3.DatabaseError:
        raise SourceUnavailable("sa", "source_db_unreadable") from None
    finally:
        connection.close()

    picks = tuple(sorted(_normalize_ticker(row["symbol"]) for row in pick_rows))
    refresh = tuple(refresh_row) if refresh_row is not None else None
    return _SaSources(
        current_nonstale_picks=picks,
        current_refresh_meta=refresh,
    )


def _read_legacy_json_bytes(path: str | Path) -> bytes:
    candidate = Path(path)
    if not candidate.is_file():
        raise SourceUnavailable("legacy_json", "source_file_missing")
    try:
        with candidate.open("rb") as handle:
            return handle.read()
    except OSError:
        raise SourceUnavailable("legacy_json", "source_file_unreadable") from None


def _parse_legacy_entries(raw: bytes):
    try:
        document = json.loads(raw.decode("utf-8"))
        return parse_active_json(document)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        raise InvalidLegacyJson from None


def _input_state(
    *,
    profile_db: str | Path,
    sa_db: str | Path,
    legacy_json: str | Path,
    legacy_overview_tickers: Iterable[object],
) -> _InputState:
    raw = _read_legacy_json_bytes(legacy_json)
    profile = _read_profile_sources(profile_db)
    sa = _read_sa_sources(sa_db)
    overview = _normalize_ticker_set(legacy_overview_tickers)
    fingerprints = InputFingerprints(
        legacy_json_sha256=hashlib.sha256(raw).hexdigest(),
        profile_sources_sha256=_semantic_hash(profile.fingerprint_payload()),
        sa_sources_sha256=_semantic_hash(sa.fingerprint_payload()),
        legacy_overview_sha256=_semantic_hash(overview),
    )
    return _InputState(
        legacy_json_bytes=raw,
        profile=profile,
        sa=sa,
        overview_tickers=overview,
        fingerprints=fingerprints,
    )


def _snapshot(*, profile_db: str | Path, sa_db: str | Path, now: datetime | None):
    try:
        return build_active_universe_snapshot(
            profile_db=profile_db,
            sa_db=sa_db,
            now=now,
        )
    except ActiveUniverseUnavailable as error:
        reasons = set(error.source_reasons.values())
        reason = (
            "required_schema_missing"
            if reasons == {"required_schema_missing"}
            else "source_db_unreadable"
        )
        raise SourceUnavailable("active_universe", reason) from None


def _observed_sources_by_ticker(
    state: _InputState,
) -> dict[str, tuple[str, ...]]:
    sources: dict[str, set[str]] = {}

    def record(raw_ticker: object, source_key: str) -> None:
        ticker = _normalize_ticker(raw_ticker)
        if ticker:
            sources.setdefault(ticker, set()).add(source_key)

    for _name, _kind, ticker in state.profile.active_lists:
        record(ticker, "manual_lists")
    for ticker, asset_class in state.profile.open_portfolio:
        if _normalize_asset_class(asset_class) in EQUITY_ASSET_CLASSES:
            record(ticker, "portfolio_open")
    for ticker in state.profile.legacy_membership:
        record(ticker, _LEGACY_SOURCE_KEY)
    for ticker in state.sa.current_nonstale_picks:
        record(ticker, "sa_alpha_picks_current")

    return {
        ticker: tuple(sorted(source_keys))
        for ticker, source_keys in sorted(sources.items())
    }


def _preview_rows(state: _InputState, snapshot) -> tuple[LegacyPreviewRow, ...]:
    return build_legacy_preview(
        _parse_legacy_entries(state.legacy_json_bytes),
        snapshot=snapshot,
        hidden_tickers=state.profile.hidden,
        observed_sources_by_ticker=_observed_sources_by_ticker(state),
    )


def _row_document(row: LegacyPreviewRow) -> dict[str, object]:
    return {
        "ticker": row.ticker,
        "classification": row.classification,
        "default_action": row.default_action,
        "sources": list(row.sources),
        "category_paths": list(row.category_paths),
        "superseded_by": row.superseded_by,
    }


def build_preview_report(
    *,
    profile_db: str | Path,
    sa_db: str | Path,
    legacy_json: str | Path,
    legacy_overview_tickers: Iterable[object],
    now: datetime | None = None,
) -> dict[str, object]:
    """Build a pure-read report from explicit source paths and overview rows."""
    state = _input_state(
        profile_db=profile_db,
        sa_db=sa_db,
        legacy_json=legacy_json,
        legacy_overview_tickers=legacy_overview_tickers,
    )
    snapshot = _snapshot(profile_db=profile_db, sa_db=sa_db, now=now)
    rows = _preview_rows(state, snapshot)
    active_json = {
        entry.ticker for entry in _parse_legacy_entries(state.legacy_json_bytes)
    }
    snapshot_tickers = set(snapshot.tickers)
    return {
        "fingerprints": state.fingerprints.as_dict(),
        "counts": {
            "json_active": len(active_json),
            "snapshot_active": len(snapshot_tickers),
        },
        "rows": [_row_document(row) for row in rows],
        "overview_missing": sorted(set(state.overview_tickers) - snapshot_tickers),
        "requires_approval": sorted(
            row.ticker
            for row in rows
            if row.classification == "json_only"
            and row.default_action == "requires_approval"
        ),
    }


def _fingerprints_from_report(report: object) -> InputFingerprints:
    if not isinstance(report, Mapping):
        raise InvalidPreviewReport
    return InputFingerprints.from_mapping(report.get("fingerprints"))


def _changed_fingerprints(
    expected: Mapping[str, str], current: Mapping[str, str]
) -> list[str]:
    return [
        key for key in _FINGERPRINT_KEYS if expected[key] != current[key]
    ]


def _profile_store_for_existing_schema(path: str | Path) -> ProfileStateStore:
    store = object.__new__(ProfileStateStore)
    store.db_path = str(path)
    store._write_lock = threading.Lock()
    return store


def _legacy_annotations(profile: _ProfileSources) -> tuple[UniverseSourceAnnotation, ...]:
    return tuple(
        UniverseSourceAnnotation(
            source_key=source_key,
            ticker=ticker,
            annotation_key=annotation_key,
            annotation_value=annotation_value,
        )
        for source_key, ticker, annotation_key, annotation_value in profile.annotations
        if source_key == _LEGACY_SOURCE_KEY
    )


def _assert_transition_parity(document: Mapping[str, object], snapshot) -> None:
    try:
        flattened = flatten_generated_active_tickers(document)
    except (TypeError, ValueError):
        raise TransitionParityError from None
    if flattened != set(snapshot.tickers):
        raise TransitionParityError


def _same_path(first: str | Path, second: str | Path) -> bool:
    try:
        first_path = Path(first)
        second_path = Path(second)
        if first_path.resolve() == second_path.resolve():
            return True
        if first_path.exists() and second_path.exists():
            return os.path.samefile(first_path, second_path)
        return False
    except (OSError, RuntimeError):
        raise OutputPreflightError("output_uninspectable") from None


def _preflight_output(
    output: str | Path,
    *,
    protected_paths: Iterable[str | Path],
) -> Path:
    target = Path(output)
    if any(_same_path(target, protected) for protected in protected_paths):
        raise OutputPathConflict

    parent = target.parent
    try:
        if not parent.exists():
            raise OutputPreflightError("parent_missing")
        if not parent.is_dir():
            raise OutputPreflightError("parent_not_directory")
        if not (parent.stat().st_mode & 0o222) or not os.access(parent, os.W_OK):
            raise OutputPreflightError("parent_not_writable")
        if target.is_symlink():
            raise OutputPreflightError("target_symlink")
        if target.exists() and not target.is_file():
            raise OutputPreflightError("target_not_regular_file")
    except OutputPreflightError:
        raise
    except OSError:
        raise OutputPreflightError("output_uninspectable") from None
    return target


def apply_reviewed_preview(
    *,
    profile_db: str | Path,
    sa_db: str | Path,
    legacy_json: str | Path,
    legacy_overview_tickers: Iterable[object],
    preview_report: Mapping[str, object],
    approved_json_only: Iterable[object],
    transition_out: str | Path,
    preview_report_path: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Apply an unchanged preview, then emit one exact transition export."""
    state = _input_state(
        profile_db=profile_db,
        sa_db=sa_db,
        legacy_json=legacy_json,
        legacy_overview_tickers=legacy_overview_tickers,
    )
    reviewed_fingerprints = _fingerprints_from_report(preview_report)
    current_map = state.fingerprints.as_dict()
    reviewed_map = reviewed_fingerprints.as_dict()
    changed = _changed_fingerprints(reviewed_map, current_map)
    if changed:
        raise FingerprintMismatch(changed)

    snapshot_before = _snapshot(profile_db=profile_db, sa_db=sa_db, now=now)
    rows = _preview_rows(state, snapshot_before)
    overview_missing = sorted(
        set(state.overview_tickers) - set(snapshot_before.tickers)
    )
    if overview_missing:
        raise OverviewCoverageError(overview_missing)

    required_approvals = {
        row.ticker
        for row in rows
        if row.classification == "json_only"
        and row.default_action == "requires_approval"
    }
    supplied_approvals = set(_normalize_approvals(approved_json_only))
    missing_approvals = required_approvals - supplied_approvals
    extra_approvals = supplied_approvals - required_approvals
    if missing_approvals or extra_approvals:
        raise ApprovalMismatch(missing=missing_approvals, extra=extra_approvals)
    protected_paths: list[str | Path] = [profile_db, sa_db, legacy_json]
    if preview_report_path is not None:
        protected_paths.append(preview_report_path)
    _preflight_output(transition_out, protected_paths=protected_paths)

    reviewed = build_reviewed_import(rows, supplied_approvals)
    retained_memberships = {
        row.ticker
        for row in rows
        if row.ticker in state.profile.legacy_membership
        and row.category_paths
        and row.classification not in {"hidden", "superseded_by_rename"}
    }
    reviewed = ReviewedLegacyImport(
        approved_memberships=tuple(
            sorted(set(reviewed.approved_memberships) | retained_memberships)
        ),
        annotations=reviewed.annotations,
    )

    # This closes in-process hook seams only. The reviewed production procedure
    # must still stop external writers throughout preview and apply.
    final_state = _input_state(
        profile_db=profile_db,
        sa_db=sa_db,
        legacy_json=legacy_json,
        legacy_overview_tickers=legacy_overview_tickers,
    )
    final_map = final_state.fingerprints.as_dict()
    final_changes = _changed_fingerprints(current_map, final_map)
    if final_changes:
        raise FingerprintMismatch(final_changes)

    store = _profile_store_for_existing_schema(profile_db)
    import_summary = store.replace_legacy_config_import(
        approved_memberships=reviewed.approved_memberships,
        annotations=reviewed.annotations,
    )

    try:
        snapshot_after = _snapshot(profile_db=profile_db, sa_db=sa_db, now=now)
        profile_after = _read_profile_sources(profile_db)
        document = build_compat_export(
            snapshot_after,
            _legacy_annotations(profile_after),
        )
        _assert_transition_parity(document, snapshot_after)
        transition_active = len(flatten_generated_active_tickers(document))
    except Exception:
        raise RestoreRequired("post_commit_verification") from None
    try:
        _preflight_output(transition_out, protected_paths=protected_paths)
        write_compat_export(transition_out, document)
    except Exception:
        raise RestoreRequired("transition_write") from None
    return {
        "fingerprints": current_map,
        "counts": {
            "snapshot_active": len(snapshot_after.tickers),
            "transition_active": transition_active,
        },
        "import": import_summary,
    }


def export_transition_snapshot(
    *,
    profile_db: str | Path,
    sa_db: str | Path,
    output: str | Path,
    now: datetime | None = None,
) -> dict[str, object]:
    """Export the current accepted snapshot without consulting legacy JSON."""
    _preflight_output(output, protected_paths=(profile_db, sa_db))
    profile = _read_profile_sources(profile_db)
    _read_sa_sources(sa_db)
    snapshot = _snapshot(profile_db=profile_db, sa_db=sa_db, now=now)
    try:
        document = build_compat_export(snapshot, _legacy_annotations(profile))
    except (TypeError, ValueError):
        raise TransitionParityError from None
    _assert_transition_parity(document, snapshot)
    write_compat_export(output, document)
    return {
        "counts": {
            "snapshot_active": len(snapshot.tickers),
            "transition_active": len(flatten_generated_active_tickers(document)),
        }
    }


def _load_production_overview_tickers() -> tuple[str, ...]:
    try:
        from src.tools.analysis_tools import get_watchlist_overview
        from src.tools.data_access import DataAccessLayer

        overview = get_watchlist_overview(DataAccessLayer(db_dsn="auto"))
        rows = overview.get("tickers") if isinstance(overview, Mapping) else None
        if not isinstance(rows, list):
            raise OverviewUnavailable
        tickers: list[object] = []
        for row in rows:
            if not isinstance(row, Mapping) or "ticker" not in row:
                raise OverviewUnavailable
            tickers.append(row["ticker"])
        return _normalize_ticker_set(tickers)
    except OverviewUnavailable:
        raise
    except Exception:
        raise OverviewUnavailable from None


def _read_preview_report(path: str | Path) -> Mapping[str, object]:
    try:
        with Path(path).open("rb") as handle:
            value = json.loads(handle.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise InvalidPreviewReport from None
    if not isinstance(value, Mapping):
        raise InvalidPreviewReport
    return value


def _write_report(
    path: str | Path,
    report: Mapping[str, object],
    *,
    protected_paths: Iterable[str | Path] = (),
) -> None:
    target = _preflight_output(path, protected_paths=protected_paths)
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
            json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fchmod(handle.fileno(), 0o600)
            os.fsync(handle.fileno())
        _preflight_output(target, protected_paths=protected_paths)
        os.replace(temporary, target)
    except Exception:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        raise


def write_preview_report(
    *,
    profile_db: str | Path,
    sa_db: str | Path,
    legacy_json: str | Path,
    legacy_overview_tickers: Iterable[object],
    report_out: str | Path,
    now: datetime | None = None,
) -> dict[str, object]:
    """Build and atomically write a preview after validating its destination."""
    protected = (profile_db, sa_db, legacy_json)
    _preflight_output(report_out, protected_paths=protected)
    report = build_preview_report(
        profile_db=profile_db,
        sa_db=sa_db,
        legacy_json=legacy_json,
        legacy_overview_tickers=legacy_overview_tickers,
        now=now,
    )
    _write_report(report_out, report, protected_paths=protected)
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview and apply the legacy-universe retirement gate."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    preview = commands.add_parser("preview")
    preview.add_argument("--profile-db", required=True)
    preview.add_argument("--sa-db", required=True)
    preview.add_argument("--legacy-json", required=True)
    preview.add_argument("--report-out", required=True)

    apply = commands.add_parser("apply")
    apply.add_argument("--profile-db", required=True)
    apply.add_argument("--sa-db", required=True)
    apply.add_argument("--legacy-json", required=True)
    apply.add_argument("--preview-report", required=True)
    apply.add_argument("--transition-out", required=True)
    approvals = apply.add_mutually_exclusive_group(required=True)
    approvals.add_argument(
        "--approve-json-only",
        action="append",
        default=None,
        metavar="SYMBOL",
    )
    approvals.add_argument("--approve-none", action="store_true")

    export = commands.add_parser("export")
    export.add_argument("--profile-db", required=True)
    export.add_argument("--sa-db", required=True)
    export.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    try:
        if arguments.command == "preview":
            result = write_preview_report(
                profile_db=arguments.profile_db,
                sa_db=arguments.sa_db,
                legacy_json=arguments.legacy_json,
                legacy_overview_tickers=_load_production_overview_tickers(),
                report_out=arguments.report_out,
            )
        elif arguments.command == "apply":
            result = apply_reviewed_preview(
                profile_db=arguments.profile_db,
                sa_db=arguments.sa_db,
                legacy_json=arguments.legacy_json,
                legacy_overview_tickers=_load_production_overview_tickers(),
                preview_report=_read_preview_report(arguments.preview_report),
                approved_json_only=arguments.approve_json_only or (),
                transition_out=arguments.transition_out,
                preview_report_path=arguments.preview_report,
            )
        else:
            result = export_transition_snapshot(
                profile_db=arguments.profile_db,
                sa_db=arguments.sa_db,
                output=arguments.output,
            )
    except UniverseRetirementError as error:
        print(json.dumps(error.as_dict(), sort_keys=True), file=sys.stderr)
        return 2
    except Exception:
        print(json.dumps({"code": "universe_retirement_failed"}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
