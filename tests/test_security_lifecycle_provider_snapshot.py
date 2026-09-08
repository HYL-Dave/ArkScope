"""Immutable old-format receipts and the current snapshot integrity boundary."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import sqlite3

import pytest

from src import security_lifecycle_provider_store as provider_store
from src.security_lifecycle_investigation import observation_fingerprint
from src.security_lifecycle_listing_evidence import _evidence
from tests.test_security_lifecycle_provider_authority import NOW, terminal_records
from tests.test_security_lifecycle_provider_store import _paths


_FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "security_lifecycle_provider_snapshots_v1.json").read_text())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def legacy_row(check):
    return {**check["row"], "evidence_json": canonical([
        _FIXTURE["evidence_pool"][index] for index in check["evidence_indices"]
    ])}


def stored_row(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    profile, _ = _paths(tmp_path)
    store = provider_store.ProviderCheckStore(profile)
    store.record(ticker="OLD", at=NOW, evidence=tuple(_evidence(row) for row in terminal_records()), diagnostics={})
    with sqlite3.connect(profile) as conn:
        conn.row_factory = sqlite3.Row
        return store, dict(conn.execute("SELECT * FROM security_lifecycle_provider_checks").fetchone())


def payload_for(row):
    return {
        "ticker": row["ticker"], "at": row["observed_at"], "state": row["state"],
        "evidence": json.loads(row["evidence_json"]),
        "diagnostics": json.loads(row["diagnostics_json"]),
        "blockers": json.loads(row["blockers_json"]),
    }


def reseal_v2(row, envelope):
    observation = {key: value for key, value in envelope["observation"].items() if key != "provider_snapshot_sha256"}
    digest = hashlib.sha256(b"arkscope.lifecycle.provider_snapshot.v2\0" + canonical({
        "snapshot_format": 2, "payload": payload_for(row), "observation": observation,
    }).encode()).hexdigest()
    row["content_sha256"] = digest
    row["check_id"] = f"slpc_{digest}"
    envelope["observation"]["provider_snapshot_sha256"] = digest
    row["observation_json"] = canonical(envelope)


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("snapshot_test_must_not_use_network")

    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


@pytest.mark.parametrize("check", _FIXTURE["checks"], ids=lambda value: value["name"])
def test_frozen_legacy_snapshots_keep_their_observations_and_fingerprints(check):
    row = legacy_row(check)
    result = provider_store.ProviderCheckStore._read(row)
    expected = json.loads(row["observation_json"])
    assert result["observation"] == expected
    assert result["digest"] == row["content_sha256"]
    assert observation_fingerprint(result["observation"]) == observation_fingerprint(expected)


@pytest.mark.parametrize("check", _FIXTURE["checks"], ids=lambda value: value["name"])
def test_old_snapshot_readback_survives_current_policy_change(check, monkeypatch):
    row = legacy_row(check)
    before = provider_store.ProviderCheckStore._read(row)

    def must_not_classify(**kwargs):
        raise AssertionError("snapshot_reader_called_current_policy")

    monkeypatch.setattr(provider_store, "classify_provider_listing", must_not_classify)
    from src import security_lifecycle_provider_authority
    monkeypatch.setattr(security_lifecycle_provider_authority, "classify_provider_listing", must_not_classify)
    assert provider_store.ProviderCheckStore._read(row) == before


def test_new_snapshot_envelope_seals_observation_and_uses_the_existing_schema(tmp_path, monkeypatch):
    store, row = stored_row(tmp_path)
    envelope = json.loads(row["observation_json"])
    assert set(envelope) == {"snapshot_format", "observation"}
    assert type(envelope["snapshot_format"]) is int
    assert envelope["snapshot_format"] == 2
    resealed = deepcopy(row)
    reseal_v2(resealed, deepcopy(envelope))
    assert resealed == row
    before = store.latest()
    assert before["OLD"]["observation"] == envelope["observation"]
    assert "snapshot_format" not in before["OLD"]["observation"]
    raw_before = store.path.read_bytes()

    def must_not_classify(**kwargs):
        raise AssertionError("snapshot_reader_called_current_policy")

    monkeypatch.setattr(provider_store, "classify_provider_listing", must_not_classify)
    assert store.latest() == before
    assert store.path.read_bytes() == raw_before
    from src.security_lifecycle_schema import verify_profile_connection
    with sqlite3.connect(store.path) as conn:
        verify_profile_connection(conn)


def test_legacy_codec_does_not_apply_new_observation_shape_rules(tmp_path, monkeypatch):
    from src import security_lifecycle_provider_snapshot as codec

    _, current = stored_row(tmp_path)
    old = legacy_row(_FIXTURE["checks"][0])
    expected = provider_store.ProviderCheckStore._read(old)

    def new_format_rule(*args):
        raise ValueError("new_format_only_rule")

    monkeypatch.setattr(codec, "_validate_observation", new_format_rule)
    assert provider_store.ProviderCheckStore._read(old) == expected
    with pytest.raises(ValueError, match="new_format_only_rule"):
        provider_store.ProviderCheckStore._read(current)


@pytest.mark.parametrize("field", [
    "ticker", "observed_at", "state", "diagnostics_json", "blockers_json", "evidence_json",
    "description", "effective_date", "source_ref", "provider_snapshot_sha256", "check_id", "created_at",
])
def test_snapshot_codec_rejects_payload_and_observation_tampering(tmp_path, field):
    _, row = stored_row(tmp_path)
    envelope = json.loads(row["observation_json"])
    if field in {"description", "source_ref", "provider_snapshot_sha256"}:
        envelope["observation"][field] = "tampered"
    elif field == "effective_date":
        envelope["observation"]["kinds"][0][field] = "2024-01-01"
    elif field == "diagnostics_json":
        row[field] = '{"massive_requests":99}'
    elif field == "blockers_json":
        row[field] = '["massive_rate_limited"]'
    elif field == "evidence_json":
        row[field] = "[]"
    elif field == "state":
        row[field] = "active"
    elif field in {"observed_at", "created_at"}:
        row[field] = "2026-09-05T01:01:00Z"
    else:
        row[field] = "tampered"
    row["observation_json"] = canonical(envelope)
    with pytest.raises(ValueError, match="provider_snapshot_(digest|format)"):
        provider_store.ProviderCheckStore._read(row)


@pytest.mark.parametrize("version", [None, True, 2.0, "2", 1, 3])
def test_snapshot_codec_rejects_unknown_or_malformed_explicit_version(tmp_path, version):
    _, row = stored_row(tmp_path)
    envelope = json.loads(row["observation_json"])
    envelope["snapshot_format"] = version
    row["observation_json"] = canonical(envelope)
    with pytest.raises(ValueError, match="provider_snapshot_format"):
        provider_store.ProviderCheckStore._read(row)


@pytest.mark.parametrize("shape", ["missing_version", "missing_observation", "extra_envelope_key", "array", "null"])
def test_snapshot_codec_never_treats_a_malformed_envelope_as_legacy(tmp_path, shape):
    _, row = stored_row(tmp_path)
    envelope = json.loads(row["observation_json"])
    if shape == "missing_version":
        envelope.pop("snapshot_format")
    elif shape == "missing_observation":
        envelope.pop("observation")
    elif shape == "extra_envelope_key":
        envelope["other"] = None
    else:
        envelope = [] if shape == "array" else None
    row["observation_json"] = canonical(envelope)
    with pytest.raises(ValueError, match="provider_snapshot_format"):
        provider_store.ProviderCheckStore._read(row)


@pytest.mark.parametrize("change", ["ticker", "observed_at", "source", "source_ref", "filing_items", "kinds", "effective_date", "extra", "missing"])
def test_snapshot_codec_rejects_resealed_incoherent_observation_shape(tmp_path, change):
    _, row = stored_row(tmp_path)
    envelope = json.loads(row["observation_json"])
    observation = envelope["observation"]
    if change == "extra":
        observation["accepted"] = True
    elif change == "missing":
        observation.pop("description")
    elif change == "filing_items":
        observation[change] = {}
    elif change == "kinds":
        observation[change] = []
    elif change == "effective_date":
        observation["kinds"][0]["effective_date"] = "not-a-date"
    else:
        observation[change] = "different"
    reseal_v2(row, envelope)
    with pytest.raises(ValueError, match="provider_snapshot_format"):
        provider_store.ProviderCheckStore._read(row)


def test_legacy_and_versioned_snapshots_coexist_without_rewriting_history(tmp_path):
    profile, _ = _paths(tmp_path)
    check = next(item for item in _FIXTURE["checks"] if item["name"] == "missing_timeline_with_transport_blocker")
    old = legacy_row(check)
    with sqlite3.connect(profile) as conn:
        conn.execute(f"INSERT INTO security_lifecycle_provider_checks ({','.join(old)}) VALUES ({','.join('?' for _ in old)})", tuple(old.values()))
    store = provider_store.ProviderCheckStore(profile)
    previous = store.latest()["OLD"]
    store.record(ticker="OLD", at="2026-09-05T01:01:00Z", evidence=tuple(_evidence(row) for row in terminal_records()), diagnostics={})
    latest = store.latest()["OLD"]
    assert latest["at"] == "2026-09-05T01:01:00Z"
    assert latest["digest"] != previous["digest"]
    assert store.observations() == [latest["observation"]]
    with sqlite3.connect(profile) as conn:
        conn.row_factory = sqlite3.Row
        saved_old = dict(conn.execute("SELECT * FROM security_lifecycle_provider_checks WHERE check_id=?", (old["check_id"],)).fetchone())
        assert saved_old == old
        assert provider_store.ProviderCheckStore._read(saved_old) == previous


def insert_snapshot(conn, row):
    conn.execute(f"INSERT INTO security_lifecycle_provider_checks ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))


@pytest.mark.parametrize("version", ["legacy", "current"])
@pytest.mark.parametrize("size", [131072, 131073])
def test_both_snapshot_formats_obey_exact_storage_limit(tmp_path, version, size):
    profile, _ = _paths(tmp_path)
    if version == "legacy":
        row = legacy_row(_FIXTURE["checks"][0])
    else:
        _, row = stored_row(tmp_path / "current")
    evidence = json.loads(row["evidence_json"])
    evidence[0]["title"] += "x" * (size - len(canonical(evidence)))
    row["evidence_json"] = canonical(evidence)
    assert len(row["evidence_json"]) == size
    envelope = json.loads(row["observation_json"])
    if version == "legacy":
        digest = hashlib.sha256(canonical(payload_for(row)).encode()).hexdigest()
        row["content_sha256"] = digest
        row["check_id"] = f"slpc_{digest}"
        envelope["provider_snapshot_sha256"] = digest
        row["observation_json"] = canonical(envelope)
    else:
        reseal_v2(row, envelope)
    provider_store.ProviderCheckStore._read(row)
    with sqlite3.connect(profile) as conn:
        if size == 131073:
            with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                insert_snapshot(conn, row)
            assert conn.execute("SELECT count(*) FROM security_lifecycle_provider_checks").fetchone()[0] == 0
        else:
            insert_snapshot(conn, row)
            assert conn.execute("SELECT count(*) FROM security_lifecycle_provider_checks").fetchone()[0] == 1


@pytest.mark.parametrize("version", ["legacy", "current"])
def test_both_snapshot_formats_remain_append_only_and_unique(tmp_path, version):
    profile, _ = _paths(tmp_path)
    if version == "legacy":
        row = legacy_row(_FIXTURE["checks"][0])
    else:
        _, row = stored_row(tmp_path / "current")
    with sqlite3.connect(profile) as conn:
        insert_snapshot(conn, row)
        with pytest.raises(sqlite3.IntegrityError):
            insert_snapshot(conn, row)
        for sql in ("UPDATE security_lifecycle_provider_checks SET state='active'", "DELETE FROM security_lifecycle_provider_checks"):
            with pytest.raises(sqlite3.IntegrityError, match="provider_checks_append_only"):
                conn.execute(sql)
        conn.row_factory = sqlite3.Row
        assert dict(conn.execute("SELECT * FROM security_lifecycle_provider_checks").fetchone()) == row


def test_batch_storage_failure_preserves_legacy_rows_and_rolls_back_new_rows(tmp_path):
    profile, _ = _paths(tmp_path)
    old = legacy_row(_FIXTURE["checks"][0])
    with sqlite3.connect(profile) as conn:
        insert_snapshot(conn, old)
    store = provider_store.ProviderCheckStore(profile)
    material = tuple(_evidence(row) for row in terminal_records())
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        store.record_many([
            {"ticker": "OLD", "at": "2026-09-05T01:01:00Z", "evidence": material, "diagnostics": {}},
            {"ticker": "OLD", "at": "2026-09-05T01:02:00Z", "evidence": material * 100, "diagnostics": {}},
        ])
    with sqlite3.connect(profile) as conn:
        conn.row_factory = sqlite3.Row
        assert [dict(row) for row in conn.execute("SELECT * FROM security_lifecycle_provider_checks")] == [old]
