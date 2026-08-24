"""Recoverable migration from legacy lifecycle rows to observation/case stores."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Callable, Optional

from src.security_lifecycle_investigation import (
    case_id_for,
    empty_evidence_set_sha256,
    observation_fingerprint,
)
from src.security_lifecycle_schema import (
    LifecycleSchemaMismatch,
    MARKET_INDEX_SQL,
    MARKET_TABLE_SQL,
    OBSERVATION_KINDS,
    V1_PROFILE_TABLE_SQL as PROFILE_TABLE_SQL,
    create_v1_profile_schema as create_profile_schema,
    verify_market_connection,
    verify_v1_profile_connection as verify_profile_connection,
)


MIGRATION_KEY = "security-lifecycle-observation-v1"
_LEGACY_REVIEW_STATES = frozenset(
    {None, "inactive_confirmed", "renamed_or_transferred"}
)
_LEGACY_LIFECYCLE_STATES = frozenset(
    {
        "review_required",
        "pending_delisting",
        "inactive_confirmed",
        "renamed_or_transferred",
    }
)
_CORE_FIELDS = (
    "ticker",
    "cik",
    "issuer_name",
    "filing_date",
    "source",
    "source_ref",
    "filing_form",
    "filing_items_json",
    "evidence_url",
    "description",
    "first_observed_at",
    "last_observed_at",
)


class LegacyMigrationRejected(RuntimeError):
    pass


class CoordinatedRestoreRequired(RuntimeError):
    pass


@dataclass(frozen=True)
class LegacyMigrationPlan:
    input_rows: int
    observations: tuple[dict, ...]
    legacy_assessments: tuple[dict, ...]
    projected_unresolved_cases: int
    relationship_rows: int
    legacy_row_map_tsv: str
    market_snapshot_sha256: str
    legacy_mapping_sha256: str
    old_id_to_case_id: dict[int, str]


@dataclass(frozen=True)
class LegacyMigrationResult:
    phase: str
    market_snapshot_sha256: str
    legacy_mapping_sha256: str
    old_id_to_case_id: dict[int, str]
    legacy_review_case_keys: tuple[tuple[str, str, str], ...]
    changed_tables: dict[str, list[str]]
    cross_store_keys_verified: bool


@dataclass(frozen=True)
class CoordinatedBackups:
    market_path: Path
    profile_path: Path
    market_sha256: str
    profile_sha256: str


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _canonical_json(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _open_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise LegacyMigrationRejected("database_missing")
    try:
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise LegacyMigrationRejected("database_unavailable") from exc
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
    )


def _validate_identity(row: dict) -> None:
    for field in ("source", "source_ref", "ticker"):
        value = row.get(field)
        if not isinstance(value, str) or not value or "\0" in value:
            raise LegacyMigrationRejected("invalid_observation_identity")


def _observation_from_group(rows: list[dict]) -> dict:
    first = rows[0]
    for row in rows[1:]:
        if any(row.get(field) != first.get(field) for field in _CORE_FIELDS):
            raise LegacyMigrationRejected("duplicate_core_conflict")
    kinds: dict[str, Optional[str]] = {}
    for row in rows:
        event_type = row.get("event_type")
        if event_type not in OBSERVATION_KINDS:
            raise LegacyMigrationRejected("unknown_observation_kind")
        effective_date = row.get("effective_date")
        if event_type in kinds:
            raise LegacyMigrationRejected("duplicate_kind_conflict")
        kinds[event_type] = effective_date
    try:
        filing_items = json.loads(first["filing_items_json"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise LegacyMigrationRejected("invalid_filing_items") from exc
    if (
        not isinstance(filing_items, list)
        or any(not isinstance(item, str) for item in filing_items)
        or filing_items != sorted(set(filing_items))
    ):
        raise LegacyMigrationRejected("invalid_filing_items")
    result = {field: first.get(field) for field in _CORE_FIELDS}
    result["id"] = min(int(row["id"]) for row in rows)
    result["filing_items"] = filing_items
    result["kinds"] = [
        {"event_type": event_type, "effective_date": effective_date}
        for event_type, effective_date in sorted(kinds.items())
    ]
    return result


def _reviews_for_group(rows: list[dict], observation: dict) -> list[dict]:
    states = {row.get("reviewed_state") for row in rows}
    if not states.issubset(_LEGACY_REVIEW_STATES):
        raise LegacyMigrationRejected("unknown_review_state")
    reviewed = states - {None}
    if not reviewed:
        return []
    if len(reviewed) != 1 or None in states:
        raise LegacyMigrationRejected("incompatible_legacy_reviews")
    state = next(iter(reviewed))
    reviewed_at_values = {row.get("reviewed_at") for row in rows}
    if len(reviewed_at_values) != 1 or None in reviewed_at_values:
        raise LegacyMigrationRejected("incompatible_legacy_reviews")
    return [
        {
            "source": observation["source"],
            "source_ref": observation["source_ref"],
            "ticker": observation["ticker"],
            "reviewed_state": state,
            "reviewed_at": next(iter(reviewed_at_values)),
            "observation_fingerprint_sha256": observation_fingerprint(observation),
        }
    ]


def preflight_legacy_migration(
    *, market_path: str | Path, profile_path: str | Path
) -> LegacyMigrationPlan:
    market = _open_read_only(Path(market_path))
    try:
        if not _table_exists(market, "security_lifecycle_observations"):
            raise LegacyMigrationRejected("legacy_observation_table_missing")
        required_columns = {
            "id",
            *_CORE_FIELDS,
            "event_type",
            "effective_date",
            "lifecycle_state",
            "reviewed_state",
            "reviewed_at",
        }
        actual_columns = {
            str(row[1])
            for row in market.execute(
                "PRAGMA table_info(security_lifecycle_observations)"
            )
        }
        if not required_columns.issubset(actual_columns):
            raise LegacyMigrationRejected("legacy_schema_mismatch")
        relationship_rows = (
            int(
                market.execute(
                    "SELECT COUNT(*) FROM corporate_action_relationships"
                ).fetchone()[0]
            )
            if _table_exists(market, "corporate_action_relationships")
            else 0
        )
        if relationship_rows:
            raise LegacyMigrationRejected("relationship_table_not_empty")
        integrity = str(market.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity != "ok":
            raise LegacyMigrationRejected("market_integrity_failed")
        rows = [
            dict(row)
            for row in market.execute(
                "SELECT * FROM security_lifecycle_observations ORDER BY id"
            )
        ]
    except sqlite3.Error as exc:
        raise LegacyMigrationRejected("legacy_preflight_failed") from exc
    finally:
        market.close()

    if not Path(profile_path).is_file():
        raise LegacyMigrationRejected("profile_database_missing")
    profile = _open_read_only(Path(profile_path))
    try:
        if str(profile.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
            raise LegacyMigrationRejected("profile_integrity_failed")
        profile_components = {
            str(row[0])
            for row in profile.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE 'security_lifecycle_%'"
            )
        }
        if profile_components:
            try:
                verify_profile_connection(profile)
            except LifecycleSchemaMismatch as exc:
                raise LegacyMigrationRejected("profile_schema_mismatch") from exc
            if _receipt(profile) is None:
                raise LegacyMigrationRejected("profile_lifecycle_schema_already_present")
    finally:
        profile.close()

    groups: dict[tuple[str, str, str], list[dict]] = {}
    for row in rows:
        _validate_identity(row)
        if row.get("lifecycle_state") not in _LEGACY_LIFECYCLE_STATES:
            raise LegacyMigrationRejected("unknown_lifecycle_state")
        groups.setdefault(
            (row["source"], row["source_ref"], row["ticker"]), []
        ).append(row)

    observations = []
    assessments = []
    old_id_to_case_id: dict[int, str] = {}
    mapping_rows = []
    for identity in sorted(groups):
        group = groups[identity]
        observation = _observation_from_group(group)
        case_id = case_id_for(*identity)
        observations.append(observation)
        assessments.extend(_reviews_for_group(group, observation))
        identity_json = json.dumps(identity, separators=(",", ":"))
        for row in group:
            old_id = int(row["id"])
            old_id_to_case_id[old_id] = case_id
            mapping_rows.append(
                (
                    old_id,
                    case_id,
                    identity_json,
                    row["event_type"],
                    row.get("effective_date") or "",
                    row.get("reviewed_state") or "",
                )
            )
    mapping_rows.sort(key=lambda item: item[0])
    header = (
        "old_id\tcase_id\tobservation_identity\tevent_type\t"
        "effective_date\treviewed_state"
    )
    legacy_row_map_tsv = header + "\n" + "".join(
        "\t".join(str(value) for value in row) + "\n" for row in mapping_rows
    )
    snapshot_sha = _sha_bytes(
        _canonical_json(
            {"relationship_count": relationship_rows, "rows": rows}
        )
    )
    mapping_sha = _sha_bytes(legacy_row_map_tsv.encode("utf-8"))
    return LegacyMigrationPlan(
        input_rows=len(rows),
        observations=tuple(observations),
        legacy_assessments=tuple(assessments),
        projected_unresolved_cases=len(observations) - len(assessments),
        relationship_rows=relationship_rows,
        legacy_row_map_tsv=legacy_row_map_tsv,
        market_snapshot_sha256=snapshot_sha,
        legacy_mapping_sha256=mapping_sha,
        old_id_to_case_id=old_id_to_case_id,
    )


def _receipt(profile: sqlite3.Connection) -> sqlite3.Row | None:
    if not _table_exists(profile, "security_lifecycle_migration_receipts"):
        return None
    return profile.execute(
        "SELECT * FROM security_lifecycle_migration_receipts WHERE migration_key=?",
        (MIGRATION_KEY,),
    ).fetchone()


def _write_profile_phase(
    profile: sqlite3.Connection,
    plan: LegacyMigrationPlan,
    *,
    at: str,
    id_factory: Callable[[str, int], str],
) -> None:
    create_profile_schema(profile)
    with profile:
        for ordinal, assessment in enumerate(plan.legacy_assessments, start=1):
            case_id = case_id_for(
                assessment["source"],
                assessment["source_ref"],
                assessment["ticker"],
            )
            profile.execute(
                "INSERT INTO security_lifecycle_cases "
                "(case_id,source,source_ref,ticker,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (
                    case_id,
                    assessment["source"],
                    assessment["source_ref"],
                    assessment["ticker"],
                    assessment["reviewed_at"],
                    assessment["reviewed_at"],
                ),
            )
            assessment_id = id_factory("sla", ordinal)
            if assessment["reviewed_state"] == "inactive_confirmed":
                outcome = "listing_ended"
                conclusion = "Legacy review marked the tracked security inactive."
                impact = "The legacy review did not retain supporting rationale."
            else:
                outcome = "symbol_or_venue_changed"
                conclusion = "Legacy review marked a symbol or venue change."
                impact = "The legacy label did not distinguish renaming from transfer."
            fingerprint = assessment["observation_fingerprint_sha256"]
            profile.execute(
                "INSERT INTO security_lifecycle_assessments "
                "(assessment_id,case_id,revision,status,relevance,confidence,author,"
                "conclusion,impact_summary,observation_fingerprint_sha256,"
                "evidence_set_sha256,created_at,accepted_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    assessment_id,
                    case_id,
                    1,
                    "accepted",
                    "direct_tracked_security",
                    "unknown",
                    "legacy_review",
                    conclusion,
                    impact,
                    fingerprint,
                    empty_evidence_set_sha256(),
                    assessment["reviewed_at"],
                    assessment["reviewed_at"],
                ),
            )
            profile.execute(
                "INSERT INTO security_lifecycle_assessment_outcomes VALUES (?,?)",
                (assessment_id, outcome),
            )
            profile.execute(
                "INSERT INTO security_lifecycle_assessment_evidence "
                "(assessment_id,reference_kind,evidence_id,cited_content_sha256) "
                "VALUES (?,'observation',NULL,?)",
                (assessment_id, fingerprint),
            )
        profile.execute(
            "INSERT INTO security_lifecycle_migration_receipts VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?)",
            (
                MIGRATION_KEY,
                plan.market_snapshot_sha256,
                plan.legacy_mapping_sha256,
                "profile_written",
                plan.input_rows,
                len(plan.observations),
                sum(len(item["kinds"]) for item in plan.observations),
                len(plan.legacy_assessments),
                at,
                at,
                None,
            ),
        )


def _write_market_phase(market: sqlite3.Connection, plan: LegacyMigrationPlan) -> None:
    market.execute("PRAGMA foreign_keys = OFF")
    try:
        with market:
            market.execute("DROP INDEX IF EXISTS idx_security_lifecycle_ticker_date")
            market.execute("DROP INDEX IF EXISTS idx_security_lifecycle_state_date")
            market.execute(
                "ALTER TABLE security_lifecycle_observations "
                "RENAME TO security_lifecycle_observations_legacy"
            )
            for statement in MARKET_TABLE_SQL.values():
                market.execute(statement)
            for statement in MARKET_INDEX_SQL.values():
                market.execute(statement)
            for observation in plan.observations:
                market.execute(
                    "INSERT INTO security_lifecycle_observations "
                    "(id,ticker,cik,issuer_name,filing_date,source,source_ref,filing_form,"
                    "filing_items_json,evidence_url,description,first_observed_at,last_observed_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        observation["id"],
                        observation["ticker"],
                        observation["cik"],
                        observation["issuer_name"],
                        observation["filing_date"],
                        observation["source"],
                        observation["source_ref"],
                        observation["filing_form"],
                        observation["filing_items_json"],
                        observation["evidence_url"],
                        observation["description"],
                        observation["first_observed_at"],
                        observation["last_observed_at"],
                    ),
                )
                market.executemany(
                    "INSERT INTO security_lifecycle_observation_kinds "
                    "(observation_id,event_type,effective_date) VALUES (?,?,?)",
                    [
                        (
                            observation["id"],
                            kind["event_type"],
                            kind["effective_date"],
                        )
                        for kind in observation["kinds"]
                    ],
                )
            market.execute("DROP TABLE security_lifecycle_observations_legacy")
            if _table_exists(market, "corporate_action_relationships"):
                market.execute("DROP TABLE corporate_action_relationships")
    finally:
        market.execute("PRAGMA foreign_keys = ON")


def _update_phase(profile: sqlite3.Connection, phase: str, at: str) -> None:
    completed_at = at if phase == "complete" else None
    with profile:
        profile.execute(
            "UPDATE security_lifecycle_migration_receipts "
            "SET phase=?,updated_at=?,completed_at=? WHERE migration_key=?",
            (phase, at, completed_at, MIGRATION_KEY),
        )


def _verify_cross_store(
    market: sqlite3.Connection, profile: sqlite3.Connection, receipt: sqlite3.Row
) -> tuple[tuple[str, str, str], ...]:
    verify_market_connection(market)
    verify_profile_connection(profile)
    observation_count = int(
        market.execute(
            "SELECT COUNT(*) FROM security_lifecycle_observations"
        ).fetchone()[0]
    )
    kind_count = int(
        market.execute(
            "SELECT COUNT(*) FROM security_lifecycle_observation_kinds"
        ).fetchone()[0]
    )
    if observation_count != int(receipt["expected_observations"]):
        raise LegacyMigrationRejected("observation_count_mismatch")
    if kind_count != int(receipt["expected_kinds"]):
        raise LegacyMigrationRejected("kind_count_mismatch")
    market_keys = {
        tuple(row)
        for row in market.execute(
            "SELECT source,source_ref,ticker FROM security_lifecycle_observations"
        )
    }
    profile_keys = tuple(
        sorted(
            tuple(row)
            for row in profile.execute(
                "SELECT source,source_ref,ticker FROM security_lifecycle_cases"
            )
        )
    )
    if not set(profile_keys).issubset(market_keys):
        raise LegacyMigrationRejected("cross_store_key_mismatch")
    if len(profile_keys) != int(receipt["expected_legacy_assessments"]):
        raise LegacyMigrationRejected("legacy_assessment_count_mismatch")
    if market.execute("PRAGMA foreign_key_check").fetchall():
        raise LegacyMigrationRejected("market_foreign_key_failure")
    if profile.execute("PRAGMA foreign_key_check").fetchall():
        raise LegacyMigrationRejected("profile_foreign_key_failure")
    if str(market.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
        raise LegacyMigrationRejected("market_integrity_failed")
    if str(profile.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
        raise LegacyMigrationRejected("profile_integrity_failed")
    return profile_keys


def _changed_tables() -> dict[str, list[str]]:
    return {
        "market": [
            "corporate_action_relationships",
            "security_lifecycle_observation_kinds",
            "security_lifecycle_observations",
        ],
        "profile": sorted(PROFILE_TABLE_SQL),
    }


def _market_has_current_schema(path: Path) -> bool:
    try:
        conn = _open_read_only(path)
    except LegacyMigrationRejected:
        return False
    try:
        verify_market_connection(conn)
    except (LifecycleSchemaMismatch, sqlite3.Error):
        return False
    finally:
        conn.close()
    return True


def _migrate_with_profile(
    *,
    market_path: str | Path,
    profile_path: Path,
    profile: sqlite3.Connection,
    clock: Callable[[], str],
    id_factory: Callable[[str, int], str],
    interrupt_after: str | None = None,
) -> LegacyMigrationResult:
    market_path = Path(market_path)
    try:
        receipt = _receipt(profile)
    except sqlite3.Error as exc:
        raise LegacyMigrationRejected("profile_receipt_read_failed") from exc

    plan: LegacyMigrationPlan | None = None
    market_already_written = bool(
        receipt is not None
        and receipt["phase"] == "profile_written"
        and _market_has_current_schema(market_path)
    )
    if receipt is None or (
        receipt["phase"] == "profile_written" and not market_already_written
    ):
        plan = preflight_legacy_migration(
            market_path=market_path, profile_path=profile_path
        )
    if receipt is None:
        _write_profile_phase(
            profile, plan, at=clock(), id_factory=id_factory  # type: ignore[arg-type]
        )
        receipt = _receipt(profile)
        if interrupt_after == "profile_written":
            return LegacyMigrationResult(
                phase="profile_written",
                market_snapshot_sha256=plan.market_snapshot_sha256,  # type: ignore[union-attr]
                legacy_mapping_sha256=plan.legacy_mapping_sha256,  # type: ignore[union-attr]
                old_id_to_case_id=plan.old_id_to_case_id,  # type: ignore[union-attr]
                legacy_review_case_keys=tuple(
                    sorted(
                        (item["source"], item["source_ref"], item["ticker"])
                        for item in plan.legacy_assessments  # type: ignore[union-attr]
                    )
                ),
                changed_tables=_changed_tables(),
                cross_store_keys_verified=False,
            )
    elif receipt["phase"] == "profile_written" and not market_already_written:
        if (
            receipt["market_snapshot_sha256"] != plan.market_snapshot_sha256
            or receipt["legacy_mapping_sha256"] != plan.legacy_mapping_sha256
        ):
            raise LegacyMigrationRejected("resume_snapshot_mismatch")

    if receipt["phase"] == "profile_written":
        if market_already_written:
            market = sqlite3.connect(market_path)
            market.row_factory = sqlite3.Row
            try:
                _verify_cross_store(market, profile, receipt)
            finally:
                market.close()
        else:
            market = sqlite3.connect(market_path)
            market.row_factory = sqlite3.Row
            try:
                _write_market_phase(market, plan)  # type: ignore[arg-type]
            finally:
                market.close()
        _update_phase(profile, "market_written", clock())
        receipt = _receipt(profile)
        if interrupt_after == "market_written":
            result = LegacyMigrationResult(
                phase="market_written",
                market_snapshot_sha256=receipt["market_snapshot_sha256"],
                legacy_mapping_sha256=receipt["legacy_mapping_sha256"],
                old_id_to_case_id=(plan.old_id_to_case_id if plan else {}),
                legacy_review_case_keys=tuple(
                    sorted(
                        (item["source"], item["source_ref"], item["ticker"])
                        for item in (plan.legacy_assessments if plan else ())
                    )
                ),
                changed_tables=_changed_tables(),
                cross_store_keys_verified=False,
            )
            return result

    market = sqlite3.connect(market_path)
    market.row_factory = sqlite3.Row
    try:
        profile_keys = _verify_cross_store(market, profile, receipt)
    finally:
        market.close()
    if receipt["phase"] != "complete":
        _update_phase(profile, "complete", clock())
        receipt = _receipt(profile)
    result = LegacyMigrationResult(
        phase="complete",
        market_snapshot_sha256=receipt["market_snapshot_sha256"],
        legacy_mapping_sha256=receipt["legacy_mapping_sha256"],
        old_id_to_case_id=(plan.old_id_to_case_id if plan else {}),
        legacy_review_case_keys=profile_keys,
        changed_tables=_changed_tables(),
        cross_store_keys_verified=True,
    )
    return result


def migrate_legacy_security_lifecycle(
    *,
    market_path: str | Path,
    profile_path: str | Path,
    clock: Callable[[], str],
    id_factory: Callable[[str, int], str],
    interrupt_after: str | None = None,
) -> LegacyMigrationResult:
    profile_path = Path(profile_path)
    profile = sqlite3.connect(profile_path)
    profile.row_factory = sqlite3.Row
    try:
        return _migrate_with_profile(
            market_path=market_path,
            profile_path=profile_path,
            profile=profile,
            clock=clock,
            id_factory=id_factory,
            interrupt_after=interrupt_after,
        )
    finally:
        profile.close()


def create_coordinated_backups(
    *, market_path: str | Path, profile_path: str | Path, backup_dir: str | Path
) -> CoordinatedBackups:
    market_path = Path(market_path)
    profile_path = Path(profile_path)
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=False)
    market_backup = backup_dir / "market_data.db"
    profile_backup = backup_dir / "profile_state.db"
    shutil.copy2(market_path, market_backup)
    shutil.copy2(profile_path, profile_backup)
    return CoordinatedBackups(
        market_path=market_backup,
        profile_path=profile_backup,
        market_sha256=_sha_file(market_backup),
        profile_sha256=_sha_file(profile_backup),
    )


def restore_coordinated_backups(
    *,
    market_path: str | Path,
    profile_path: str | Path,
    backups: CoordinatedBackups,
) -> None:
    market_path = Path(market_path)
    profile_path = Path(profile_path)
    if (
        not backups.market_path.is_file()
        or not backups.profile_path.is_file()
        or _sha_file(backups.market_path) != backups.market_sha256
        or _sha_file(backups.profile_path) != backups.profile_sha256
    ):
        raise CoordinatedRestoreRequired("both_verified_backups_required")
    market_tmp = market_path.with_name(f".{market_path.name}.restore")
    profile_tmp = profile_path.with_name(f".{profile_path.name}.restore")
    shutil.copy2(backups.market_path, market_tmp)
    shutil.copy2(backups.profile_path, profile_tmp)
    if (
        _sha_file(market_tmp) != backups.market_sha256
        or _sha_file(profile_tmp) != backups.profile_sha256
    ):
        market_tmp.unlink(missing_ok=True)
        profile_tmp.unlink(missing_ok=True)
        raise CoordinatedRestoreRequired("restore_copy_verification_failed")
    os.replace(market_tmp, market_path)
    os.replace(profile_tmp, profile_path)
