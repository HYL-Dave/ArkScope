from __future__ import annotations

import json
import sqlite3

import pytest

from src.prices_patch import (
    build_patch_dict,
    patch_fingerprints,
    plan_apply,
    validate_patch,
)

K1 = ("HAPN", "15min", "2026-01-26T16:00:00+0000")   # missing locally → insert
K2 = ("HAPN", "15min", "2026-01-26T14:30:00+0000")   # drifted → update
PG1 = (21.0, 21.5, 20.9, 21.4, 30000)
PG2 = (21.17, 21.56, 21.06, 21.34, 37358)
PRE2 = (21.17, 21.56, 21.06, 21.33, 37358)


def _patch():
    return build_patch_dict(
        insert_rows=[(*K1, *PG1)],
        update_rows=[{"key": list(K2), "pg": list(PG2), "local_preimage": list(PRE2)}],
    )


def test_build_patch_dict_fingerprints_are_stable_and_scoped():
    p1, p2 = _patch(), _patch()
    assert p1["fingerprint"] == p2["fingerprint"]
    assert p1["counts"] == {"insert": 1, "update": 1}
    assert p1["ticker"] == "HAPN"
    fps = patch_fingerprints(p1)
    assert p1["key_scope_fingerprint"] == fps["key_scope_fingerprint"]
    assert p1["pg_values_fingerprint"] == fps["pg_values_fingerprint"]
    assert p1["local_preimage_fingerprint"] == fps["local_preimage_fingerprint"]


def test_validate_patch_rejects_foreign_ticker_and_overlap():
    bad = _patch()
    bad["insert_rows"][0][0] = "AAPL"
    assert any("ticker" in e for e in validate_patch(bad))

    overlap = build_patch_dict(
        insert_rows=[(*K2, *PG2)],
        update_rows=[{"key": list(K2), "pg": list(PG2), "local_preimage": list(PRE2)}],
    )
    assert any("overlap" in e for e in validate_patch(overlap))

    tampered = _patch()
    tampered["update_rows"][0]["pg"][3] = 99.9
    assert any("fingerprint" in e for e in validate_patch(tampered))


def test_plan_apply_classifies_all_states():
    patch = _patch()
    # K1 absent, K2 matches preimage → both actionable
    plan = plan_apply(patch, {K2: PRE2})
    assert plan.insert_needed == (K1,) and plan.update_needed == (K2,)
    assert plan.blocked == () and plan.would_apply is True and plan.already_applied is False

    # both already at PG values → already applied
    plan2 = plan_apply(patch, {K1: PG1, K2: PG2})
    assert plan2.already_applied is True and plan2.would_apply is False

    # K2 present but matches neither preimage nor pg → blocked
    plan3 = plan_apply(patch, {K2: (1.0, 1.0, 1.0, 1.0, 1)})
    assert plan3.blocked and plan3.would_apply is False


def _mk_local(tmp_path, rows):
    db = tmp_path / "market_data.db"
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE prices (ticker TEXT NOT NULL, datetime TEXT NOT NULL,
        interval TEXT NOT NULL, open REAL, high REAL, low REAL, close REAL, volume INTEGER,
        PRIMARY KEY (ticker, datetime, interval))""")
    conn.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?,?)", rows)
    conn.commit(); conn.close()
    return db


def test_cli_dry_run_reports_plan_without_writing(tmp_path, capsys):
    from scripts.migration import p0c_hapn_patch as cli
    db = _mk_local(tmp_path, [(K2[0], K2[2], K2[1], *PRE2),
                          ("AAPL", "2026-01-02T14:30:00+0000", "15min", 1, 1, 1, 1, 1)])
    patch_path = tmp_path / "patch.json"
    patch_path.write_text(json.dumps(_patch()), encoding="utf-8")

    code = cli.main(["dry-run", "--patch", str(patch_path), "--market-db", str(db)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["would_apply"] is True and out["insert_needed"] == 1 and out["update_needed"] == 1
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == 2  # unchanged
    conn.close()


def test_cli_apply_inserts_updates_validates_and_is_idempotent(tmp_path, capsys, monkeypatch):
    from contextlib import nullcontext
    from scripts.migration import p0c_hapn_patch as cli
    monkeypatch.setattr(cli, "market_write_lock", lambda timeout=30.0: nullcontext())
    db = _mk_local(tmp_path, [(K2[0], K2[2], K2[1], *PRE2)])
    patch = _patch()
    patch_path = tmp_path / "patch.json"
    patch_path.write_text(json.dumps(patch), encoding="utf-8")
    backup = tmp_path / "backup.db"

    code = cli.main(["apply", "--patch", str(patch_path), "--market-db", str(db),
                     "--expected-fingerprint", patch["fingerprint"],
                     "--backup", str(backup), "--confirm-writers-paused"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["applied"] is True
    assert out["inserted"] == 1 and out["updated"] == 1
    assert backup.exists()

    conn = sqlite3.connect(db)
    assert conn.execute("SELECT close, volume FROM prices WHERE datetime=?", (K1[2],)).fetchone() == (21.4, 30000)
    assert conn.execute("SELECT close FROM prices WHERE datetime=?", (K2[2],)).fetchone()[0] == 21.34
    audit = conn.execute("SELECT fingerprint FROM prices_patch_runs").fetchall()
    assert audit == [(patch["fingerprint"],)]
    conn.close()

    code2 = cli.main(["apply", "--patch", str(patch_path), "--market-db", str(db),
                      "--expected-fingerprint", patch["fingerprint"],
                      "--backup", str(tmp_path / "backup2.db"), "--confirm-writers-paused"])
    out2 = json.loads(capsys.readouterr().out)
    assert code2 == 0 and out2["already_applied"] is True and out2["inserted"] == 0


def test_cli_apply_refuses_fingerprint_mismatch_and_blocked_rows(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from scripts.migration import p0c_hapn_patch as cli
    monkeypatch.setattr(cli, "market_write_lock", lambda timeout=30.0: nullcontext())
    patch = _patch()
    patch_path = tmp_path / "patch.json"
    patch_path.write_text(json.dumps(patch), encoding="utf-8")

    db = _mk_local(tmp_path, [(K2[0], K2[2], K2[1], *PRE2)])
    with pytest.raises(SystemExit):
        cli.main(["apply", "--patch", str(patch_path), "--market-db", str(db),
                  "--expected-fingerprint", "wrong",
                  "--backup", str(tmp_path / "b.db"), "--confirm-writers-paused"])

    blocked_dir = tmp_path / "blocked"
    blocked_dir.mkdir()
    db2 = _mk_local(blocked_dir, [(K2[0], K2[2], K2[1], 1.0, 1.0, 1.0, 1.0, 1)])
    with pytest.raises(SystemExit):
        cli.main(["apply", "--patch", str(patch_path), "--market-db", str(db2),
                  "--expected-fingerprint", patch["fingerprint"],
                  "--backup", str(tmp_path / "b2.db"), "--confirm-writers-paused"])


def test_cli_build_produces_model_order_rows(tmp_path, capsys, monkeypatch):
    from scripts.migration import p0c_hapn_patch as cli

    # PG has K1 (missing locally) and K2 (drifted); local has only K2 at preimage.
    monkeypatch.setattr(cli, "_load_pg_ticker_rows", lambda url, t, i: {K1: PG1, K2: PG2})
    db = _mk_local(tmp_path, [(K2[0], K2[2], K2[1], *PRE2)])
    out_path = tmp_path / "patch.json"

    code = cli.main(["build", "--database-url", "postgres://secret@x/db",
                     "--market-db", str(db), "--output", str(out_path)])
    out = json.loads(capsys.readouterr().out)
    patch = json.loads(out_path.read_text(encoding="utf-8"))

    assert code == 0 and "secret" not in json.dumps(out)
    assert out["insert"] == 1 and out["update"] == 1
    # model row order: (ticker, interval, datetime, o, h, l, c, v)
    assert patch["insert_rows"][0][:3] == list(K1)
    assert patch["update_rows"][0]["key"] == list(K2)
    assert patch["update_rows"][0]["local_preimage"] == list(PRE2)
    from src.prices_patch import validate_patch as vp
    assert vp(patch) == []
