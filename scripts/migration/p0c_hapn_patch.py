#!/usr/bin/env python3
"""P0-C HAPN adopt-PG patch gate: build (PG read-only) / dry-run / apply."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.market_data_direct import backup_market_db, market_write_lock  # noqa: E402
from src.prices_patch import (  # noqa: E402
    build_patch_dict,
    plan_apply,
    validate_patch,
)

_AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS prices_patch_runs (
    id INTEGER PRIMARY KEY,
    fingerprint TEXT NOT NULL UNIQUE,
    counts_json TEXT NOT NULL,
    backup_path TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
"""


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True))


def _local_rows(conn: sqlite3.Connection, ticker: str, interval: str) -> dict:
    return {
        (str(t), str(i), str(dt)): (o, h, l, c, v)
        for t, dt, i, o, h, l, c, v in conn.execute(
            "SELECT ticker, datetime, interval, open, high, low, close, volume "
            "FROM prices WHERE ticker=? AND interval=?",
            (ticker, interval),
        )
    }


def _open_ro(path: str | Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True)


def _load_pg_ticker_rows(database_url: str, ticker: str, interval: str) -> dict:
    import psycopg2

    pg = psycopg2.connect(database_url)
    try:
        with pg.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                """SELECT ticker,
                          TO_CHAR(datetime AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS+0000'),
                          interval, open, high, low, close, volume
                   FROM prices WHERE ticker=%s AND interval=%s""",
                (ticker, interval),
            )
            return {(str(r[0]), str(r[2]), str(r[1])): (r[3], r[4], r[5], r[6], r[7])
                    for r in cur.fetchall()}
    finally:
        pg.close()


def cmd_build(args: argparse.Namespace) -> int:
    pg_rows = _load_pg_ticker_rows(args.database_url, args.ticker, args.interval)

    conn = _open_ro(args.market_db)
    try:
        local_rows = _local_rows(conn, args.ticker, args.interval)
    finally:
        conn.close()

    missing = sorted(set(pg_rows) - set(local_rows))
    drift = sorted(
        key for key in set(pg_rows) & set(local_rows)
        if [None if x is None else x for x in pg_rows[key]]
        != [None if x is None else x for x in local_rows[key]]
    )
    patch = build_patch_dict(
        insert_rows=[[*key, *pg_rows[key]] for key in missing],
        update_rows=[
            {"key": list(key), "pg": list(pg_rows[key]), "local_preimage": list(local_rows[key])}
            for key in drift
        ],
        ticker=args.ticker,
        interval=args.interval,
    )
    Path(args.output).write_text(json.dumps(patch, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _print({
        "status": "built",
        "fingerprint": patch["fingerprint"],
        "insert": patch["counts"]["insert"],
        "update": patch["counts"]["update"],
    })
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    patch = _load_json(args.patch)
    errors = validate_patch(patch)
    if errors:
        raise SystemExit("invalid patch: " + "; ".join(errors[:5]))
    conn = _open_ro(args.market_db)
    try:
        plan = plan_apply(patch, _local_rows(conn, patch["ticker"], patch["interval"]))
    finally:
        conn.close()
    _print({
        "status": "dry-run",
        "fingerprint": patch["fingerprint"],
        "insert_needed": len(plan.insert_needed),
        "update_needed": len(plan.update_needed),
        "already_applied_keys": len(plan.already_applied_keys),
        "blocked": len(plan.blocked),
        "blocked_samples": [dict(b, key=list(b["key"])) for b in plan.blocked[:5]],
        "would_apply": plan.would_apply,
        "already_applied": plan.already_applied,
    })
    return 0 if (plan.would_apply or plan.already_applied) else 1


def cmd_apply(args: argparse.Namespace) -> int:
    patch = _load_json(args.patch)
    errors = validate_patch(patch)
    if errors:
        raise SystemExit("invalid patch: " + "; ".join(errors[:5]))
    if patch["fingerprint"] != args.expected_fingerprint:
        raise SystemExit("patch fingerprint mismatch vs --expected-fingerprint")

    with market_write_lock(timeout=30.0):
        ro = _open_ro(args.market_db)
        try:
            plan = plan_apply(patch, _local_rows(ro, patch["ticker"], patch["interval"]))
            already_run = bool(
                ro.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='prices_patch_runs'"
                ).fetchone()
                and ro.execute(
                    "SELECT 1 FROM prices_patch_runs WHERE fingerprint=?",
                    (patch["fingerprint"],),
                ).fetchone()
            )
        finally:
            ro.close()
        if plan.blocked:
            raise SystemExit(
                "patch blocked: " + json.dumps([dict(b, key=list(b["key"])) for b in plan.blocked[:5]])
            )
        if plan.already_applied and already_run:
            _print({"status": "applied", "already_applied": True, "applied": False,
                    "inserted": 0, "updated": 0, "fingerprint": patch["fingerprint"]})
            return 0

        created = backup_market_db(str(args.market_db), str(args.backup), overwrite=False)
        if created is None:
            raise SystemExit(f"market DB does not exist: {args.market_db}")

        conn = sqlite3.connect(args.market_db)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.executescript(_AUDIT_SCHEMA)
            inserted = 0
            for row in patch["insert_rows"]:
                key = (str(row[0]), str(row[1]), str(row[2]))
                if key not in plan.insert_needed:
                    continue
                conn.execute(
                    "INSERT INTO prices (ticker, datetime, interval, open, high, low, close, volume) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (row[0], row[2], row[1], *row[3:8]),
                )
                inserted += 1
            updated = 0
            for entry in patch["update_rows"]:
                key = tuple(str(x) for x in entry["key"])
                if key not in plan.update_needed:
                    continue
                conn.execute(
                    "UPDATE prices SET open=?, high=?, low=?, close=?, volume=? "
                    "WHERE ticker=? AND datetime=? AND interval=?",
                    (*entry["pg"], key[0], key[2], key[1]),
                )
                updated += 1
            conn.execute(
                "INSERT OR IGNORE INTO prices_patch_runs "
                "(fingerprint, counts_json, backup_path, applied_at) VALUES (?,?,?,?)",
                (
                    patch["fingerprint"],
                    json.dumps({"inserted": inserted, "updated": updated}, sort_keys=True),
                    str(args.backup),
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )
            _validate_applied(conn, patch)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    ro = _open_ro(args.market_db)
    try:
        _validate_applied(ro, patch)
    finally:
        ro.close()
    _print({"status": "applied", "already_applied": False, "applied": True,
            "inserted": inserted, "updated": updated, "fingerprint": patch["fingerprint"]})
    return 0


def _validate_applied(conn: sqlite3.Connection, patch: dict[str, Any]) -> None:
    rows = _local_rows(conn, patch["ticker"], patch["interval"])
    problems = []
    for row in patch["insert_rows"]:
        key = (str(row[0]), str(row[1]), str(row[2]))
        if key not in rows:
            problems.append(("missing_after_apply", key))
        elif [None if x is None else x for x in rows[key]] != [None if x is None else x for x in row[3:8]]:
            problems.append(("insert_value_mismatch", key))
    for entry in patch["update_rows"]:
        key = tuple(str(x) for x in entry["key"])
        if [None if x is None else x for x in rows.get(key, ())] != [None if x is None else x for x in entry["pg"]]:
            problems.append(("update_value_mismatch", key))
    if problems:
        raise RuntimeError(f"post-apply validation failed: {problems[:5]}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    build = sub.add_parser("build", help="Read-only: derive the HAPN patch from PG + local")
    build.add_argument("--database-url", required=True)
    build.add_argument("--market-db", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--ticker", default="HAPN")
    build.add_argument("--interval", default="15min")

    dry = sub.add_parser("dry-run", help="Validate patch and plan against local; no writes")
    dry.add_argument("--patch", required=True)
    dry.add_argument("--market-db", required=True)

    apply_p = sub.add_parser("apply", help="Apply reviewed patch (backup + lock + single txn)")
    apply_p.add_argument("--patch", required=True)
    apply_p.add_argument("--market-db", required=True)
    apply_p.add_argument("--expected-fingerprint", required=True)
    apply_p.add_argument("--backup", required=True)
    apply_p.add_argument("--confirm-writers-paused", required=True, action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "build":
        return cmd_build(args)
    if args.cmd == "dry-run":
        return cmd_dry_run(args)
    if args.cmd == "apply":
        return cmd_apply(args)
    parser.error(f"unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
