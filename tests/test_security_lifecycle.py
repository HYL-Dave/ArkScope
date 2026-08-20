from __future__ import annotations

import hashlib
import sqlite3

import pytest


def _observation(**overrides):
    from src.security_lifecycle import LifecycleObservation, ObservationKind

    values = {
        "ticker": "EA",
        "cik": "0000712515",
        "issuer_name": "Electronic Arts Inc.",
        "filing_date": "2026-08-04",
        "source": "sec_edgar",
        "source_ref": "0000712515-26-000042",
        "filing_form": "8-K",
        "filing_items": ("2.01", "3.01"),
        "evidence_url": "https://www.sec.gov/Archives/example/ea-8k.htm",
        "description": "Completion of acquisition and listing review.",
        "observed_at": "2026-08-05T00:00:00Z",
        "kinds": (
            ObservationKind("acquisition_completed", "2026-08-04"),
            ObservationKind("listing_status_review", None),
        ),
    }
    values.update(overrides)
    return LifecycleObservation(**values)


def _open_market(path):
    from src.security_lifecycle_schema import create_market_schema

    conn = sqlite3.connect(path)
    create_market_schema(conn)
    return conn


def _open_profile(path):
    from src.security_lifecycle_schema import create_profile_schema

    conn = sqlite3.connect(path)
    create_profile_schema(conn)
    return conn


def test_case_id_rejects_embedded_nul_and_hashes_literal_provider_identity():
    from src.security_lifecycle_investigation import case_id_for

    expected = "slc_" + hashlib.sha256(
        b"security-lifecycle-case-v1\0sec_edgar\0Ref-AbC\0Ea"
    ).hexdigest()
    assert case_id_for("sec_edgar", "Ref-AbC", "Ea") == expected
    for values in (
        ("sec\0edgar", "Ref-AbC", "Ea"),
        ("sec_edgar", "Ref\0AbC", "Ea"),
        ("sec_edgar", "Ref-AbC", "E\0A"),
    ):
        with pytest.raises(ValueError, match="embedded_nul"):
            case_id_for(*values)


def test_observation_store_rejects_unknown_kind_before_write(tmp_path):
    from src.security_lifecycle import (
        LifecycleObservation,
        ObservationKind,
        SecurityLifecycleStore,
    )

    conn = _open_market(tmp_path / "market_data.db")
    try:
        store = SecurityLifecycleStore(conn)
        invalid = LifecycleObservation(
            **{**_observation().__dict__, "kinds": (ObservationKind("rumor", None),)}
        )
        with pytest.raises(ValueError, match="event_type"):
            store.upsert_observation(invalid)
        assert conn.execute(
            "SELECT COUNT(*) FROM security_lifecycle_observations"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM security_lifecycle_observation_kinds"
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_observation_upsert_preserves_first_seen_and_refreshes_bounded_source_fields(
    tmp_path,
):
    from src.security_lifecycle import SecurityLifecycleStore

    conn = _open_market(tmp_path / "market_data.db")
    try:
        store = SecurityLifecycleStore(conn)
        observation_id = store.upsert_observation(_observation())
        assert store.upsert_observation(
            _observation(
                issuer_name="Electronic Arts, Inc.",
                description="updated evidence",
                observed_at="2026-08-06T00:00:00Z",
            )
        ) == observation_id
        row = conn.execute(
            "SELECT * FROM security_lifecycle_observations WHERE id=?",
            (observation_id,),
        ).fetchone()
        assert row["first_observed_at"] == "2026-08-05T00:00:00Z"
        assert row["last_observed_at"] == "2026-08-06T00:00:00Z"
        assert row["issuer_name"] == "Electronic Arts, Inc."
        assert row["description"] == "updated evidence"
    finally:
        conn.close()


def test_observation_upsert_reconciles_many_kinds_without_changing_case_identity(
    tmp_path,
):
    from src.security_lifecycle import ObservationKind, SecurityLifecycleStore
    from src.security_lifecycle_investigation import case_id_for

    conn = _open_market(tmp_path / "market_data.db")
    try:
        store = SecurityLifecycleStore(conn)
        observation_id = store.upsert_observation(_observation())
        case_id = case_id_for("sec_edgar", "0000712515-26-000042", "EA")
        store.upsert_observation(
            _observation(
                observed_at="2026-08-06T00:00:00Z",
                kinds=(ObservationKind("listing_status_review", None),),
            )
        )
        assert [
            row[0]
            for row in conn.execute(
                "SELECT id FROM security_lifecycle_observations"
            ).fetchall()
        ] == [observation_id]
        assert [
            tuple(row)
            for row in conn.execute(
                "SELECT event_type, effective_date "
                "FROM security_lifecycle_observation_kinds ORDER BY event_type"
            ).fetchall()
        ] == [("listing_status_review", None)]
        assert case_id_for("sec_edgar", "0000712515-26-000042", "EA") == case_id
    finally:
        conn.close()


def test_read_composition_keeps_profile_history_visible_when_source_is_missing(
    tmp_path,
):
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
        compose_security_lifecycle,
    )

    market_path = tmp_path / "market_data.db"
    profile_path = tmp_path / "profile_state.db"
    market = _open_market(market_path)
    market.close()
    profile = _open_profile(profile_path)
    try:
        store = SecurityLifecycleInvestigationStore(profile)
        case_id = store.ensure_case(
            source="sec_edgar",
            source_ref="missing-ref",
            ticker="EA",
            at="2026-08-06T00:00:00Z",
        )
    finally:
        profile.close()

    result = compose_security_lifecycle(str(market_path), str(profile_path))
    assert result["cases"] == [
        {
            "case_id": case_id,
            "source": "sec_edgar",
            "source_ref": "missing-ref",
            "ticker": "EA",
            "source_presence": "source_missing",
            "workflow_state": "unresolved",
            "observation": None,
            "current_assessment": None,
        }
    ]


def test_read_composition_projects_untouched_observation_without_profile_write(tmp_path):
    from src.security_lifecycle import SecurityLifecycleStore
    from src.security_lifecycle_investigation import compose_security_lifecycle

    market_path = tmp_path / "market_data.db"
    profile_path = tmp_path / "profile_state.db"
    conn = _open_market(market_path)
    try:
        SecurityLifecycleStore(conn).upsert_observation(_observation())
    finally:
        conn.close()

    result = compose_security_lifecycle(str(market_path), str(profile_path))
    assert len(result["cases"]) == 1
    assert result["cases"][0]["source_presence"] == "present"
    assert result["cases"][0]["workflow_state"] == "unresolved"
    assert result["cases"][0]["observation"]["kinds"] == [
        {"event_type": "acquisition_completed", "effective_date": "2026-08-04"},
        {"event_type": "listing_status_review", "effective_date": None},
    ]
    assert not profile_path.exists()


def test_source_reattachment_restores_identical_fingerprint_and_revalidates_changed_content(
    tmp_path,
):
    from src.security_lifecycle import SecurityLifecycleStore
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
        compose_security_lifecycle,
        observation_fingerprint,
    )

    market_path = tmp_path / "market_data.db"
    profile_path = tmp_path / "profile_state.db"
    market = _open_market(market_path)
    try:
        market_store = SecurityLifecycleStore(market)
        market_store.upsert_observation(_observation())
        fingerprint = observation_fingerprint(market_store.get_observation("sec_edgar", "0000712515-26-000042", "EA"))
        market.execute("DELETE FROM security_lifecycle_observations")
        market.commit()
    finally:
        market.close()
    profile = _open_profile(profile_path)
    try:
        profile_store = SecurityLifecycleInvestigationStore(profile)
        profile_store.insert_legacy_assessment(
            source="sec_edgar",
            source_ref="0000712515-26-000042",
            ticker="EA",
            reviewed_state="inactive_confirmed",
            reviewed_at="2026-08-06T00:00:00Z",
            observation_fingerprint_sha256=fingerprint,
        )
    finally:
        profile.close()

    assert compose_security_lifecycle(str(market_path), str(profile_path))["cases"][0][
        "source_presence"
    ] == "source_missing"

    market = sqlite3.connect(market_path)
    market.row_factory = sqlite3.Row
    try:
        store = SecurityLifecycleStore(market)
        store.upsert_observation(_observation())
    finally:
        market.close()
    identical = compose_security_lifecycle(str(market_path), str(profile_path))["cases"][0]
    assert identical["workflow_state"] == "resolved"
    assert identical["current_assessment"]["stale"] is False

    market = sqlite3.connect(market_path)
    market.row_factory = sqlite3.Row
    try:
        store = SecurityLifecycleStore(market)
        store.upsert_observation(
            _observation(description="changed source evidence", observed_at="2026-08-07T00:00:00Z")
        )
    finally:
        market.close()
    changed = compose_security_lifecycle(str(market_path), str(profile_path))["cases"][0]
    assert changed["workflow_state"] == "unresolved"
    assert changed["current_assessment"] is None
    assert changed["assessment_history"][0]["stale"] is True


def test_store_level_failure_is_typed_unavailable_not_empty_fallback(tmp_path):
    from src.security_lifecycle_investigation import (
        LifecycleStoreUnavailable,
        compose_security_lifecycle,
    )

    market_path = tmp_path / "market_data.db"
    profile_path = tmp_path / "profile_state.db"
    market_path.write_bytes(b"not sqlite")
    profile = _open_profile(profile_path)
    profile.close()

    with pytest.raises(LifecycleStoreUnavailable) as exc_info:
        compose_security_lifecycle(str(market_path), str(profile_path))
    assert exc_info.value.store == "market"
