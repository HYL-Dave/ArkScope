from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def _observation(**overrides):
    from src.security_lifecycle import LifecycleObservation

    values = {
        "ticker": "EA",
        "cik": "0000712515",
        "issuer_name": "Electronic Arts Inc.",
        "event_type": "acquisition_completed",
        "lifecycle_state": "review_required",
        "filing_date": "2026-08-04",
        "effective_date": "2026-08-04",
        "source": "sec_edgar",
        "source_ref": "0000712515-26-000042",
        "filing_form": "8-K",
        "filing_items": ("2.01", "3.01"),
        "evidence_url": "https://www.sec.gov/Archives/example/ea-8k.htm",
        "description": "Completion of acquisition and listing removal review.",
        "observed_at": "2026-08-05T00:00:00Z",
    }
    values.update(overrides)
    return LifecycleObservation(**values)


def _relationship(**overrides):
    from src.security_lifecycle import CorporateRelationship

    values = {
        "action_type": "acquisition",
        "target_ticker": "EA",
        "target_cik": "0000712515",
        "target_name": "Electronic Arts Inc.",
        "acquirer_ticker": None,
        "acquirer_cik": None,
        "acquirer_name": "Oak-Eagle, LLC",
        "status": "candidate",
        "effective_date": "2026-08-04",
        "source": "sec_edgar",
        "source_ref": "0000712515-26-000042",
        "evidence_url": "https://www.sec.gov/Archives/example/ea-8k.htm",
        "evidence_excerpt": (
            "The Company became a wholly owned subsidiary of Oak-Eagle, LLC."
        ),
        "observed_at": "2026-08-05T00:00:00Z",
    }
    values.update(overrides)
    return CorporateRelationship(**values)


def test_security_lifecycle_read_is_no_create_on_missing_database(tmp_path):
    from src.security_lifecycle import read_security_lifecycle

    db_path = tmp_path / "missing" / "market_data.db"
    assert read_security_lifecycle(str(db_path)) == {
        "events": [],
        "relationships": [],
        "summary": {
            "event_count": 0,
            "review_required": 0,
            "pending_delisting": 0,
            "relationship_candidates": 0,
        },
    }
    assert not db_path.exists()
    assert not db_path.parent.exists()


def test_store_is_idempotent_and_keeps_reviewed_relationship_decision(tmp_path):
    import sqlite3

    from src.security_lifecycle import SecurityLifecycleStore, read_security_lifecycle

    db_path = tmp_path / "market_data.db"
    conn = sqlite3.connect(db_path)
    try:
        store = SecurityLifecycleStore(conn)
        assert store.upsert_observation(_observation()) is True
        assert store.upsert_observation(
            _observation(observed_at="2026-08-06T00:00:00Z")
        ) is False
        relation_id = store.upsert_relationship(_relationship())
        store.review_relationship(
            relation_id,
            status="confirmed",
            reviewed_at="2026-08-06T01:00:00Z",
        )
        assert store.upsert_relationship(
            _relationship(observed_at="2026-08-07T00:00:00Z")
        ) == relation_id
    finally:
        conn.close()

    snapshot = read_security_lifecycle(str(db_path))
    assert snapshot["summary"] == {
        "event_count": 1,
        "review_required": 1,
        "pending_delisting": 0,
        "relationship_candidates": 0,
    }
    assert snapshot["events"][0]["filing_items"] == ["2.01", "3.01"]
    assert snapshot["events"][0]["first_observed_at"] == "2026-08-05T00:00:00Z"
    assert snapshot["events"][0]["last_observed_at"] == "2026-08-06T00:00:00Z"
    assert snapshot["relationships"][0]["status"] == "confirmed"
    assert snapshot["relationships"][0]["reviewed_at"] == "2026-08-06T01:00:00Z"
    assert snapshot["relationships"][0]["last_observed_at"] == "2026-08-07T00:00:00Z"


def test_store_rejects_unknown_states_before_sqlite_write(tmp_path):
    import sqlite3

    import pytest

    from src.security_lifecycle import LifecycleObservation, SecurityLifecycleStore

    conn = sqlite3.connect(tmp_path / "market_data.db")
    try:
        store = SecurityLifecycleStore(conn)
        with pytest.raises(ValueError, match="lifecycle_state"):
            store.upsert_observation(
                LifecycleObservation(
                    **{
                        **_observation().__dict__,
                        "lifecycle_state": "definitely_delisted",
                    }
                )
            )
    finally:
        conn.close()


def test_read_projection_never_claims_that_universe_was_mutated(tmp_path):
    import sqlite3

    from src.security_lifecycle import SecurityLifecycleStore, read_security_lifecycle

    db_path = tmp_path / "market_data.db"
    conn = sqlite3.connect(db_path)
    try:
        SecurityLifecycleStore(conn).upsert_observation(
            _observation(
                event_type="listing_removal_notice",
                lifecycle_state="pending_delisting",
            )
        )
    finally:
        conn.close()

    snapshot = read_security_lifecycle(str(db_path))
    rendered = str(snapshot).lower()
    assert "auto_removed" not in rendered
    assert "hidden" not in rendered
    assert snapshot["summary"]["pending_delisting"] == 1


def test_market_data_route_reads_lifecycle_without_provider_or_scheduler(
    tmp_path, monkeypatch
):
    import sqlite3

    import src.api.routes.market_data as route
    from src.security_lifecycle import SecurityLifecycleStore

    db_path = tmp_path / "market_data.db"
    conn = sqlite3.connect(db_path)
    try:
        SecurityLifecycleStore(conn).upsert_observation(_observation())
    finally:
        conn.close()
    monkeypatch.setattr(route, "resolve_market_db_path", lambda: str(db_path))
    monkeypatch.setitem(
        __import__("sys").modules,
        "src.service.data_scheduler",
        None,
    )

    result = route.security_lifecycle_status(limit=25)

    assert result["summary"]["event_count"] == 1
    assert result["events"][0]["ticker"] == "EA"


def test_relationship_review_route_is_explicit_and_does_not_touch_profile_state(
    tmp_path, monkeypatch
):
    import sqlite3

    import src.api.routes.market_data as route
    from src.security_lifecycle import SecurityLifecycleStore

    db_path = tmp_path / "market_data.db"
    profile_path = tmp_path / "profile_state.db"
    profile_path.write_bytes(b"profile-sentinel")
    conn = sqlite3.connect(db_path)
    try:
        relation_id = SecurityLifecycleStore(conn).upsert_relationship(_relationship())
    finally:
        conn.close()
    allowed = []
    monkeypatch.setattr(route, "resolve_market_db_path", lambda: str(db_path))
    monkeypatch.setattr(
        route,
        "require_db_write",
        lambda action, payload: allowed.append((action, payload)),
    )

    result = route.review_corporate_relationship(
        relation_id,
        route.CorporateRelationshipReview(status="confirmed"),
    )

    assert result == {"id": relation_id, "status": "confirmed"}
    assert allowed == [
        (
            "review_corporate_relationship",
            {"relationship_id": relation_id, "status": "confirmed"},
        )
    ]
    assert profile_path.read_bytes() == b"profile-sentinel"


def test_relationship_review_404_does_not_create_lifecycle_tables(tmp_path, monkeypatch):
    import sqlite3

    import pytest
    from fastapi import HTTPException

    import src.api.routes.market_data as route

    db_path = tmp_path / "market_data.db"
    sqlite3.connect(db_path).close()
    monkeypatch.setattr(route, "resolve_market_db_path", lambda: str(db_path))
    monkeypatch.setattr(route, "require_db_write", lambda *_args, **_kwargs: None)

    with pytest.raises(HTTPException) as exc_info:
        route.review_corporate_relationship(
            999,
            route.CorporateRelationshipReview(status="confirmed"),
        )
    assert exc_info.value.status_code == 404
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE name LIKE '%lifecycle%' "
            "OR name LIKE 'corporate_action%'"
        ).fetchall() == []
    finally:
        conn.close()
