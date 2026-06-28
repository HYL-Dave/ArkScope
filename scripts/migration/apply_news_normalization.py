#!/usr/bin/env python3
"""Apply one explicitly reviewed normalized-news migration plan."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.market_data_direct import backup_market_db, market_write_lock  # noqa: E402
from src.news_normalized.migration import (  # noqa: E402
    ResolvedMigrationPlan,
    build_resolved_plan,
)
from src.news_normalized.migration_apply import (  # noqa: E402
    MigrationApplyResult,
    validate_applied_plan,
    write_resolved_plan,
)
from src.news_normalized.schema import (  # noqa: E402
    begin_news_normalized_schema_transaction,
)


class MigrationFingerprintMismatch(ValueError):
    pass


class InsufficientMigrationSpace(RuntimeError):
    pass


def _existing_parent(path: Path) -> Path:
    current = path.resolve().parent
    while not current.exists():
        if current == current.parent:
            raise FileNotFoundError(f"no existing parent for backup path: {path}")
        current = current.parent
    return current


def require_backup_capacity(market_db: Path, backup_path: Path) -> None:
    """Reserve headroom for backup, normalized growth, and transaction overhead."""
    database_parent = market_db.resolve().parent
    backup_parent = _existing_parent(backup_path)
    database_size = market_db.stat().st_size
    if database_parent.stat().st_dev == backup_parent.stat().st_dev:
        required = database_size * 3
        if shutil.disk_usage(database_parent).free < required:
            raise InsufficientMigrationSpace(
                f"migration filesystem needs at least {required} free bytes"
            )
        return
    database_required = database_size * 2
    backup_required = database_size
    if shutil.disk_usage(database_parent).free < database_required:
        raise InsufficientMigrationSpace(
            f"database filesystem needs at least {database_required} free bytes"
        )
    if shutil.disk_usage(backup_parent).free < backup_required:
        raise InsufficientMigrationSpace(
            f"backup filesystem needs at least {backup_required} free bytes"
        )


def require_expected_fingerprints(
    plan: ResolvedMigrationPlan,
    *,
    expected_input_fingerprint: str,
    expected_resolved_fingerprint: str,
    expected_rejection_evidence_fingerprint: str,
) -> None:
    actual = {
        "input": plan.preview.input_fingerprint,
        "resolved": plan.preview.resolved_fingerprint,
        "rejection": plan.preview.rejection_evidence.fingerprint,
    }
    expected = {
        "input": expected_input_fingerprint,
        "resolved": expected_resolved_fingerprint,
        "rejection": expected_rejection_evidence_fingerprint,
    }
    mismatches = {
        name: {"expected": expected[name], "actual": actual[name]}
        for name in actual
        if actual[name] != expected[name]
    }
    if mismatches:
        raise MigrationFingerprintMismatch(
            f"reviewed migration fingerprints changed: {mismatches}"
        )
    if not plan.preview.would_apply or plan.preview.remaining_blockers:
        raise MigrationFingerprintMismatch("resolved migration plan is not applyable")


def open_apply_connection(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def validate_reopened_read_only(
    market_db: Path, plan: ResolvedMigrationPlan
) -> None:
    conn = sqlite3.connect(f"file:{market_db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        validate_applied_plan(conn, plan)
    finally:
        conn.close()


def require_idempotent_replan(
    market_db: Path, parquet_root: Path, plan: ResolvedMigrationPlan
) -> None:
    repeated = build_resolved_plan(
        market_db, sorted(parquet_root.rglob("*.parquet"))
    )
    require_expected_fingerprints(
        repeated,
        expected_input_fingerprint=plan.preview.input_fingerprint,
        expected_resolved_fingerprint=plan.preview.resolved_fingerprint,
        expected_rejection_evidence_fingerprint=(
            plan.preview.rejection_evidence.fingerprint
        ),
    )


def apply_news_normalization(
    market_db: Path,
    parquet_root: Path,
    *,
    expected_input_fingerprint: str,
    expected_resolved_fingerprint: str,
    expected_rejection_evidence_fingerprint: str,
    backup_path: Path,
) -> MigrationApplyResult:
    market_db = Path(market_db).resolve()
    parquet_root = Path(parquet_root).resolve()
    backup_path = Path(backup_path).resolve()
    if not market_db.is_file():
        raise FileNotFoundError(f"market DB does not exist: {market_db}")
    if not parquet_root.is_dir():
        raise FileNotFoundError(f"Parquet root does not exist: {parquet_root}")

    # The lock intentionally covers backup, commit, reopened validation, and replan.
    with market_write_lock(timeout=30.0):
        plan = build_resolved_plan(
            market_db, sorted(parquet_root.rglob("*.parquet"))
        )
        require_expected_fingerprints(
            plan,
            expected_input_fingerprint=expected_input_fingerprint,
            expected_resolved_fingerprint=expected_resolved_fingerprint,
            expected_rejection_evidence_fingerprint=(
                expected_rejection_evidence_fingerprint
            ),
        )
        require_backup_capacity(market_db, backup_path)
        backup = backup_market_db(
            str(market_db), str(backup_path), overwrite=False
        )
        if backup is None:
            raise RuntimeError("market DB backup was not created")

        conn = open_apply_connection(market_db)
        try:
            begin_news_normalized_schema_transaction(conn)
            result = write_resolved_plan(
                conn, plan, str(backup_path), _utc_now()
            )
            validate_applied_plan(conn, plan)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        validate_reopened_read_only(market_db, plan)
        require_idempotent_replan(market_db, parquet_root, plan)
        return result


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market-db", required=True, type=Path)
    parser.add_argument("--parquet-root", required=True, type=Path)
    parser.add_argument("--expected-input-fingerprint", required=True)
    parser.add_argument("--expected-resolved-fingerprint", required=True)
    parser.add_argument("--expected-rejection-evidence-fingerprint", required=True)
    parser.add_argument("--backup-path", required=True, type=Path)
    parser.add_argument(
        "--confirm-scheduler-paused",
        required=True,
        action="store_true",
        help="Confirm the scheduler and manual ingest are paused for the long write lock",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    result = apply_news_normalization(
        args.market_db,
        args.parquet_root,
        expected_input_fingerprint=args.expected_input_fingerprint,
        expected_resolved_fingerprint=args.expected_resolved_fingerprint,
        expected_rejection_evidence_fingerprint=(
            args.expected_rejection_evidence_fingerprint
        ),
        backup_path=args.backup_path,
    )
    print(json.dumps(asdict(result), sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
