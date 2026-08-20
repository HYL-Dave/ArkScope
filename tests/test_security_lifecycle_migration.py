from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "security_lifecycle_legacy_37.json"

PROFILE_TABLES = {
    "security_lifecycle_cases",
    "security_lifecycle_investigation_runs",
    "security_lifecycle_evidence",
    "security_lifecycle_assessments",
    "security_lifecycle_assessment_outcomes",
    "security_lifecycle_assessment_evidence",
    "security_lifecycle_case_acknowledgements",
    "security_lifecycle_action_proposals",
    "security_lifecycle_migration_receipts",
}


LEGACY_OBSERVATION_SQL = """
CREATE TABLE security_lifecycle_observations (
    id INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL,
    cik TEXT,
    issuer_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL,
    filing_date TEXT NOT NULL,
    effective_date TEXT,
    source TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    filing_form TEXT NOT NULL,
    filing_items_json TEXT NOT NULL,
    evidence_url TEXT NOT NULL,
    description TEXT NOT NULL,
    first_observed_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL,
    reviewed_state TEXT,
    reviewed_at TEXT
)
"""


def _fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _legacy_databases(tmp_path, *, payload=None, relationship_count=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    payload = copy.deepcopy(payload or _fixture())
    if relationship_count is None:
        relationship_count = payload["relationship_count"]
    market_path = tmp_path / "market_data.db"
    profile_path = tmp_path / "profile_state.db"
    market = sqlite3.connect(market_path)
    market.execute(LEGACY_OBSERVATION_SQL)
    columns = [
        "id",
        "ticker",
        "cik",
        "issuer_name",
        "event_type",
        "lifecycle_state",
        "filing_date",
        "effective_date",
        "source",
        "source_ref",
        "filing_form",
        "filing_items_json",
        "evidence_url",
        "description",
        "first_observed_at",
        "last_observed_at",
        "reviewed_state",
        "reviewed_at",
    ]
    placeholders = ",".join("?" for _ in columns)
    market.executemany(
        f"INSERT INTO security_lifecycle_observations ({','.join(columns)}) "
        f"VALUES ({placeholders})",
        [[row[column] for column in columns] for row in payload["rows"]],
    )
    market.execute("CREATE TABLE corporate_action_relationships (id INTEGER PRIMARY KEY)")
    for index in range(int(relationship_count)):
        market.execute(
            "INSERT INTO corporate_action_relationships(id) VALUES (?)", (index + 1,)
        )
    market.execute("CREATE TABLE unrelated_market (value TEXT NOT NULL)")
    market.execute("INSERT INTO unrelated_market VALUES ('market-sentinel')")
    market.commit()
    market.close()
    profile = sqlite3.connect(profile_path)
    profile.execute("CREATE TABLE unrelated_profile (value TEXT NOT NULL)")
    profile.execute("INSERT INTO unrelated_profile VALUES ('profile-sentinel')")
    profile.commit()
    profile.close()
    return market_path, profile_path


def _migrate(tmp_path, *, payload=None, interrupt_after=None):
    from src.security_lifecycle_migration import migrate_legacy_security_lifecycle

    market_path, profile_path = _legacy_databases(tmp_path, payload=payload)
    result = migrate_legacy_security_lifecycle(
        market_path=market_path,
        profile_path=profile_path,
        clock=lambda: "2026-08-20T00:00:00Z",
        id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal:03d}",
        interrupt_after=interrupt_after,
    )
    return market_path, profile_path, result


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _new_observation():
    from src.security_lifecycle import LifecycleObservation, ObservationKind

    return LifecycleObservation(
        ticker="EA",
        cik="0000712515",
        issuer_name="Electronic Arts Inc.",
        filing_date="2026-08-04",
        source="sec_edgar",
        source_ref="ref",
        filing_form="8-K",
        filing_items=("2.01",),
        evidence_url="https://www.sec.gov/example",
        description="evidence",
        observed_at="2026-08-20T00:00:00Z",
        kinds=(ObservationKind("acquisition_completed", "2026-08-04"),),
    )


def test_incomplete_receipt_blocks_all_lifecycle_writes(tmp_path, monkeypatch):
    import src.collectors.sec_corporate_actions as collector
    from src.security_lifecycle import SecurityLifecycleStore
    from src.security_lifecycle_investigation import (
        LifecycleWritesUnavailable,
        SecurityLifecycleInvestigationStore,
    )
    from src.security_lifecycle_schema import create_market_schema, create_profile_schema

    market = sqlite3.connect(tmp_path / "market_data.db")
    market.row_factory = sqlite3.Row
    create_market_schema(market)
    profile = sqlite3.connect(tmp_path / "profile_state.db")
    profile.row_factory = sqlite3.Row
    create_profile_schema(profile)
    profile.execute(
        "INSERT INTO security_lifecycle_migration_receipts VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?)",
        (
            "legacy-v1",
            "a" * 64,
            "b" * 64,
            "profile_written",
            37,
            36,
            37,
            4,
            "2026-08-20T00:00:00Z",
            "2026-08-20T00:00:00Z",
            None,
        ),
    )
    profile.commit()
    try:
        with pytest.raises(LifecycleWritesUnavailable):
            SecurityLifecycleInvestigationStore(profile).ensure_case(
                source="sec_edgar",
                source_ref="ref",
                ticker="EA",
                at="2026-08-20T00:00:00Z",
            )
        with pytest.raises(LifecycleWritesUnavailable):
            SecurityLifecycleStore(market, migration_conn=profile).upsert_observation(
                _new_observation()
            )
        monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
        monkeypatch.setattr(
            collector,
            "parse_submission_events",
            lambda **_kwargs: collector.SubmissionObservationBatch(
                observations=(_new_observation(),)
            ),
        )

        class _Client:
            @staticmethod
            def get_cik(_ticker):
                return "0000712515"

            @staticmethod
            def fetch_submissions(_cik):
                return {"filings": {"recent": {"form": []}}}

        with pytest.raises(LifecycleWritesUnavailable):
            collector.run_incremental(
                tickers_arg="EA",
                client=_Client(),
                db_path=str(tmp_path / "market_data.db"),
                observed_at="2026-08-20T00:00:00Z",
                start_date="2026-01-01",
            )
    finally:
        profile.close()
        market.close()


def test_legacy_relationship_and_review_schema_is_absent_after_migration(tmp_path):
    market_path, _profile_path, _result = _migrate(tmp_path)
    conn = sqlite3.connect(market_path)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(security_lifecycle_observations)"
            )
        }
        assert "corporate_action_relationships" not in tables
        assert {
            "event_type",
            "effective_date",
            "lifecycle_state",
            "reviewed_state",
            "reviewed_at",
        }.isdisjoint(columns)
    finally:
        conn.close()


def test_legacy_row_mapping_is_complete_deterministic_and_stably_sorted(tmp_path):
    from src.security_lifecycle_migration import preflight_legacy_migration

    market_path, profile_path = _legacy_databases(tmp_path)
    first = preflight_legacy_migration(market_path=market_path, profile_path=profile_path)
    second = preflight_legacy_migration(market_path=market_path, profile_path=profile_path)
    assert first.legacy_row_map_tsv == second.legacy_row_map_tsv
    lines = first.legacy_row_map_tsv.splitlines()
    assert len(lines) == 38
    assert lines[0].startswith("old_id\tcase_id\tobservation_identity")
    assert [int(line.split("\t", 1)[0]) for line in lines[1:]] == sorted(
        row["id"] for row in _fixture()["rows"]
    )


def test_migration_collapses_ccl_only_after_core_fields_match(tmp_path):
    from src.security_lifecycle_migration import (
        LegacyMigrationRejected,
        preflight_legacy_migration,
    )

    market_path, profile_path = _legacy_databases(tmp_path / "valid")
    plan = preflight_legacy_migration(market_path=market_path, profile_path=profile_path)
    ccl = [item for item in plan.observations if item["ticker"] == "CCL"]
    assert len(ccl) == 1
    assert ccl[0]["kinds"] == [
        {"event_type": "acquisition_completed", "effective_date": "2026-05-07"},
        {"event_type": "listing_status_review", "effective_date": None},
    ]

    payload = _fixture()
    next(row for row in payload["rows"] if row["id"] == 5)["issuer_name"] = "Conflict"
    market_path, profile_path = _legacy_databases(tmp_path / "conflict", payload=payload)
    with pytest.raises(LegacyMigrationRejected, match="duplicate_core_conflict"):
        preflight_legacy_migration(market_path=market_path, profile_path=profile_path)


def test_migration_manifest_limits_changes_to_authorized_tables(tmp_path):
    market_path, profile_path, result = _migrate(tmp_path)
    assert result.phase == "complete"
    market = sqlite3.connect(market_path)
    profile = sqlite3.connect(profile_path)
    try:
        assert market.execute("SELECT * FROM unrelated_market").fetchall() == [
            ("market-sentinel",)
        ]
        assert profile.execute("SELECT * FROM unrelated_profile").fetchall() == [
            ("profile-sentinel",)
        ]
        assert result.changed_tables == {
            "market": [
                "corporate_action_relationships",
                "security_lifecycle_observation_kinds",
                "security_lifecycle_observations",
            ],
            "profile": sorted(PROFILE_TABLES),
        }
    finally:
        profile.close()
        market.close()


def test_migration_maps_ambiguous_transfer_review_without_inventing_precision(tmp_path):
    _market_path, profile_path, _result = _migrate(tmp_path)
    conn = sqlite3.connect(profile_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT a.relevance,a.successor_ticker,a.destination_venue,o.outcome "
            "FROM security_lifecycle_assessments a "
            "JOIN security_lifecycle_assessment_outcomes o "
            "ON o.assessment_id=a.assessment_id ORDER BY a.assessment_id"
        ).fetchall()
        assert len(rows) == 4
        assert {row["relevance"] for row in rows} == {"direct_tracked_security"}
        assert {row["outcome"] for row in rows} == {"symbol_or_venue_changed"}
        assert all(row["successor_ticker"] is None for row in rows)
        assert all(row["destination_venue"] is None for row in rows)
    finally:
        conn.close()


def test_migration_maps_inactive_review_without_synthesizing_a_proposal(tmp_path):
    payload = _fixture()
    reviewed = next(row for row in payload["rows"] if row["reviewed_state"] is not None)
    reviewed["reviewed_state"] = "inactive_confirmed"
    market_path, profile_path, _result = _migrate(tmp_path, payload=payload)
    conn = sqlite3.connect(profile_path)
    try:
        outcomes = conn.execute(
            "SELECT outcome FROM security_lifecycle_assessment_outcomes"
        ).fetchall()
        assert ("listing_ended",) in outcomes
        assert conn.execute(
            "SELECT COUNT(*) FROM security_lifecycle_action_proposals"
        ).fetchone()[0] == 0
    finally:
        conn.close()
    assert market_path.exists()


def test_migration_preflight_maps_37_rows_to_36_observations_37_kinds_and_4_reviews(
    tmp_path,
):
    from src.security_lifecycle_migration import preflight_legacy_migration

    market_path, profile_path = _legacy_databases(tmp_path)
    plan = preflight_legacy_migration(market_path=market_path, profile_path=profile_path)
    assert plan.input_rows == 37
    assert len(plan.observations) == 36
    assert sum(len(item["kinds"]) for item in plan.observations) == 37
    assert len(plan.legacy_assessments) == 4
    assert plan.projected_unresolved_cases == 32
    assert plan.relationship_rows == 0


def test_migration_preserves_every_source_field_kind_date_and_old_row_mapping(tmp_path):
    market_path, _profile_path, result = _migrate(tmp_path)
    payload = _fixture()
    expected_by_id = {row["id"]: row for row in payload["rows"]}
    assert set(result.old_id_to_case_id) == set(expected_by_id)
    conn = sqlite3.connect(market_path)
    conn.row_factory = sqlite3.Row
    try:
        for old_id, case_id in result.old_id_to_case_id.items():
            old = expected_by_id[old_id]
            row = conn.execute(
                "SELECT * FROM security_lifecycle_observations "
                "WHERE source=? AND source_ref=? AND ticker=?",
                (old["source"], old["source_ref"], old["ticker"]),
            ).fetchone()
            assert row is not None
            for field in (
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
            ):
                assert row[field] == old[field]
            assert conn.execute(
                "SELECT 1 FROM security_lifecycle_observation_kinds "
                "WHERE observation_id=? AND event_type=? AND effective_date IS ?",
                (row["id"], old["event_type"], old["effective_date"]),
            ).fetchone()
            assert case_id.startswith("slc_")
    finally:
        conn.close()


def test_migration_receipt_binds_market_snapshot_hash_and_complete_case_keys(tmp_path):
    _market_path, profile_path, result = _migrate(tmp_path)
    conn = sqlite3.connect(profile_path)
    conn.row_factory = sqlite3.Row
    try:
        receipt = conn.execute(
            "SELECT * FROM security_lifecycle_migration_receipts"
        ).fetchone()
        assert receipt["phase"] == "complete"
        assert receipt["market_snapshot_sha256"] == result.market_snapshot_sha256
        assert receipt["legacy_mapping_sha256"] == result.legacy_mapping_sha256
        assert receipt["expected_legacy_rows"] == 37
        assert receipt["expected_observations"] == 36
        assert receipt["expected_kinds"] == 37
        assert receipt["expected_legacy_assessments"] == 4
        profile_keys = {
            tuple(row)
            for row in conn.execute(
                "SELECT source,source_ref,ticker FROM security_lifecycle_cases"
            )
        }
        assert profile_keys == set(result.legacy_review_case_keys)
    finally:
        conn.close()


def test_migration_rejects_conflicting_duplicate_fields_kinds_or_reviews(tmp_path):
    from src.security_lifecycle_migration import (
        LegacyMigrationRejected,
        preflight_legacy_migration,
    )

    mutations = []
    core = _fixture()
    next(row for row in core["rows"] if row["id"] == 5)["description"] = "conflict"
    mutations.append(core)
    kinds = _fixture()
    row = next(row for row in kinds["rows"] if row["id"] == 5)
    row["event_type"] = "listing_status_review"
    row["effective_date"] = "2026-05-07"
    mutations.append(kinds)
    reviews = _fixture()
    ccl_rows = [row for row in reviews["rows"] if row["ticker"] == "CCL"]
    ccl_rows[0]["reviewed_state"] = "inactive_confirmed"
    ccl_rows[0]["reviewed_at"] = "2026-08-20T00:00:00Z"
    ccl_rows[1]["reviewed_state"] = "renamed_or_transferred"
    ccl_rows[1]["reviewed_at"] = "2026-08-20T00:00:00Z"
    mutations.append(reviews)
    for index, payload in enumerate(mutations):
        market_path, profile_path = _legacy_databases(
            tmp_path / str(index), payload=payload
        )
        with pytest.raises(LegacyMigrationRejected):
            preflight_legacy_migration(
                market_path=market_path, profile_path=profile_path
            )


def test_migration_rejects_nonempty_relationship_table_before_either_store_changes(
    tmp_path,
):
    from src.security_lifecycle_migration import (
        LegacyMigrationRejected,
        migrate_legacy_security_lifecycle,
    )

    market_path, profile_path = _legacy_databases(tmp_path, relationship_count=1)
    before = (_sha(market_path), _sha(profile_path))
    with pytest.raises(LegacyMigrationRejected, match="relationship_table_not_empty"):
        migrate_legacy_security_lifecycle(
            market_path=market_path,
            profile_path=profile_path,
            clock=lambda: "2026-08-20T00:00:00Z",
            id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal:03d}",
        )
    assert (_sha(market_path), _sha(profile_path)) == before


def test_migration_rejects_unknown_review_and_nul_identity_before_either_store_changes(
    tmp_path,
):
    from src.security_lifecycle_migration import (
        LegacyMigrationRejected,
        migrate_legacy_security_lifecycle,
    )

    payloads = []
    unknown = _fixture()
    next(row for row in unknown["rows"] if row["reviewed_state"] is not None)[
        "reviewed_state"
    ] = "approved"
    payloads.append(unknown)
    nul = _fixture()
    nul["rows"][0]["source_ref"] += "\0suffix"
    payloads.append(nul)
    for index, payload in enumerate(payloads):
        market_path, profile_path = _legacy_databases(
            tmp_path / str(index), payload=payload
        )
        before = (_sha(market_path), _sha(profile_path))
        with pytest.raises(LegacyMigrationRejected):
            migrate_legacy_security_lifecycle(
                market_path=market_path,
                profile_path=profile_path,
                clock=lambda: "2026-08-20T00:00:00Z",
                id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal:03d}",
            )
        assert (_sha(market_path), _sha(profile_path)) == before


def test_migration_restore_requires_both_databases_before_reopen(tmp_path):
    from src.security_lifecycle_migration import (
        CoordinatedRestoreRequired,
        create_coordinated_backups,
        restore_coordinated_backups,
    )

    market_path, profile_path = _legacy_databases(tmp_path / "live")
    backups = create_coordinated_backups(
        market_path=market_path,
        profile_path=profile_path,
        backup_dir=tmp_path / "backups",
    )
    original = (market_path.read_bytes(), profile_path.read_bytes())
    market_path.write_bytes(b"changed-market")
    profile_path.write_bytes(b"changed-profile")
    backups.profile_path.unlink()
    with pytest.raises(CoordinatedRestoreRequired):
        restore_coordinated_backups(
            market_path=market_path,
            profile_path=profile_path,
            backups=backups,
        )
    assert market_path.read_bytes() == b"changed-market"
    assert profile_path.read_bytes() == b"changed-profile"
    backups.profile_path.write_bytes(original[1])
    restore_coordinated_backups(
        market_path=market_path,
        profile_path=profile_path,
        backups=backups,
    )
    assert (market_path.read_bytes(), profile_path.read_bytes()) == original


def test_migration_resumes_after_phase_one_without_duplicate_profile_rows(tmp_path):
    from src.security_lifecycle_migration import migrate_legacy_security_lifecycle

    market_path, profile_path, interrupted = _migrate(
        tmp_path, interrupt_after="profile_written"
    )
    assert interrupted.phase == "profile_written"
    result = migrate_legacy_security_lifecycle(
        market_path=market_path,
        profile_path=profile_path,
        clock=lambda: "2026-08-20T00:00:01Z",
        id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal:03d}",
    )
    assert result.phase == "complete"
    conn = sqlite3.connect(profile_path)
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM security_lifecycle_cases"
        ).fetchone()[0] == 4
        assert conn.execute(
            "SELECT COUNT(*) FROM security_lifecycle_assessments"
        ).fetchone()[0] == 4
    finally:
        conn.close()


def test_migration_resumes_after_phase_two_and_verifies_cross_store_keys(
    tmp_path, monkeypatch
):
    import src.security_lifecycle_migration as migration

    market_path, profile_path = _legacy_databases(tmp_path)
    real_update_phase = migration._update_phase

    def interrupt_before_market_receipt(profile, phase, at):
        if phase == "market_written":
            raise RuntimeError("simulated_crash_after_market_commit")
        return real_update_phase(profile, phase, at)

    monkeypatch.setattr(migration, "_update_phase", interrupt_before_market_receipt)
    with pytest.raises(RuntimeError, match="simulated_crash_after_market_commit"):
        migration.migrate_legacy_security_lifecycle(
            market_path=market_path,
            profile_path=profile_path,
            clock=lambda: "2026-08-20T00:00:00Z",
            id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal:03d}",
        )
    monkeypatch.setattr(migration, "_update_phase", real_update_phase)

    result = migration.migrate_legacy_security_lifecycle(
        market_path=market_path,
        profile_path=profile_path,
        clock=lambda: "2026-08-20T00:00:01Z",
        id_factory=lambda prefix, ordinal: f"{prefix}_{ordinal:03d}",
    )
    assert result.phase == "complete"
    assert result.cross_store_keys_verified is True
