"""Digest-bound, dependency-aware disposal. Each database has its own atomic receipt.

Two WAL databases do not offer a crash-atomic shared commit. Stages are therefore
explicit, independently resumable, and never reported as one completed operation.
"""

from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3

from src.lifecycle_investigation.schema import verify_journal
from src.lifecycle_web_migration import _backup
from src.lifecycle_web_schema import TABLES as WEB_TABLES, TRIGGERS as WEB_TRIGGERS
from src.lifecycle_web_store import _sha, _json
from src.security_lifecycle_listing_migration import _quote_identifier as q, _sha_file
from src.security_lifecycle_schema import PROFILE_TABLE_SQL, verify_profile_connection, verify_market_connection, _normalize_sql


OWNED = (set(PROFILE_TABLE_SQL) | set(WEB_TABLES)) - {"security_lifecycle_provider_checks", "security_lifecycle_migration_receipts"}
RECEIPT_SQL = """CREATE TABLE lifecycle_legacy_disposal_receipts (
    approval_sha256 TEXT PRIMARY KEY, stage TEXT NOT NULL CHECK(stage IN ('market','profile')),
    completed_at TEXT NOT NULL, receipt_json TEXT NOT NULL, receipt_sha256 TEXT NOT NULL)"""
RECEIPT_TRIGGERS = {f"lifecycle_legacy_disposal_receipts_{op.lower()}": f"""CREATE TRIGGER lifecycle_legacy_disposal_receipts_{op.lower()}
    BEFORE {op} ON lifecycle_legacy_disposal_receipts BEGIN SELECT RAISE(ABORT,'disposal_receipt_immutable'); END""" for op in ("UPDATE", "DELETE")}


def _receipt(conn, approval, stage):
    row = conn.execute("SELECT sql FROM sqlite_master WHERE name='lifecycle_legacy_disposal_receipts'").fetchone()
    if row is None:
        return None
    if _normalize_sql(row[0]) != _normalize_sql(RECEIPT_SQL):
        raise ValueError("disposal_receipt_invalid")
    for name, sql in RECEIPT_TRIGGERS.items():
        row = conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()
        if not row or _normalize_sql(row[0]) != _normalize_sql(sql):
            raise ValueError("disposal_receipt_invalid")
    row = conn.execute("SELECT stage,receipt_json,receipt_sha256 FROM lifecycle_legacy_disposal_receipts WHERE approval_sha256=?", (approval,)).fetchone()
    if row is None:
        return None
    try:
        value = json.loads(row[1])
        if (row[0] != stage or _sha(value) != row[2] or value["stage"] != stage or value["approval_sha256"] != approval
                or value["status"] != "completed" or len(value["backup_sha256"]) != 64):
            raise ValueError("disposal_receipt_invalid")
    except (KeyError, TypeError, ValueError):
        raise ValueError("disposal_receipt_invalid") from None
    return value


@contextmanager
def connect(path, mode="ro"):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + f"?mode={mode}", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    if mode == "ro":
        conn.execute("PRAGMA query_only=ON")
    try:
        yield conn
    finally:
        conn.close()


def foreign_keys(conn):
    edges = []
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        groups = defaultdict(list)
        for row in conn.execute(f"PRAGMA foreign_key_list({q(table)})"):
            groups[row[0]].append(row)
        for group in groups.values():
            ordered = sorted(group, key=lambda row: row[1])
            edges.append((table, ordered[0][2], tuple((row[3], row[4]) for row in ordered)))
    return edges


def closure(conn, case_id):
    row = conn.execute("SELECT rowid AS _rowid_,* FROM security_lifecycle_cases WHERE case_id=? AND source='sec_edgar'", (case_id,)).fetchone()
    if row is None:
        raise ValueError("disposal_changed")
    result, pending = defaultdict(dict), [("security_lifecycle_cases", dict(row))]
    edges = foreign_keys(conn)
    reason = None
    while pending:
        table, row = pending.pop()
        if row["_rowid_"] in result[table]:
            continue
        result[table][row["_rowid_"]] = row
        if row.get("case_id", case_id) != case_id:
            reason = "cross_case_dependency"
        if table == "security_lifecycle_assessments" and row.get("acceptance_authority") == "human":
            reason = "human_assessment"
        if table in {"security_lifecycle_automation_runs", "security_lifecycle_investigation_runs", "lifecycle_web_runs"} and row.get("status") in {"running", "queued", "searching", "reading_sources", "analyzing", "cancelling", "remote_outcome_unknown"}:
            reason = "unfinished_execution"
        for child, parent, columns in edges:
            if parent != table:
                continue
            if any(parent_col is None for _, parent_col in columns):
                reason = "unreviewed_foreign_key"
                continue
            predicate = " AND ".join(f"{q(child_col)}=?" for child_col, _ in columns)
            params = tuple(row[parent_col] for _, parent_col in columns)
            if child not in OWNED:
                if conn.execute(f"SELECT 1 FROM {q(child)} WHERE {predicate} LIMIT 1", params).fetchone():
                    reason = "retained_external_dependency"
                continue
            children = conn.execute(f"SELECT rowid AS _rowid_,* FROM {q(child)} WHERE {predicate}", params).fetchall()
            for item in children:
                child_row = dict(item)
                assessment = child_row.get("assessment_id")
                if assessment:
                    owner = conn.execute("SELECT case_id FROM security_lifecycle_assessments WHERE assessment_id=?", (assessment,)).fetchone()
                    if owner and owner[0] != case_id:
                        reason = "cross_case_dependency"
                pending.append((child, child_row))
    return dict(result), reason


def profile_scope(conn, roots):
    rows = defaultdict(dict)
    for root in roots:
        selected, reason = closure(conn, root)
        if reason:
            raise ValueError("disposal_changed")
        for table, values in selected.items():
            rows[table].update(values)
    return {table: {"rowids": sorted(values), "sha256": _sha([values[key] for key in sorted(values)])} for table, values in sorted(rows.items())}


def market_scope(conn, ids):
    rows, kinds = [], []
    for identity in ids:
        row = conn.execute("SELECT * FROM security_lifecycle_observations WHERE id=? AND source='sec_edgar'", (identity,)).fetchone()
        if row is None:
            raise ValueError("disposal_changed")
        if market_dependency(conn, row):
            raise ValueError("disposal_changed")
        rows.append(dict(row))
        kinds.extend(dict(row) for row in conn.execute("SELECT * FROM security_lifecycle_observation_kinds WHERE observation_id=? ORDER BY event_type", (identity,)))
    return {"observation_ids": ids, "sha256": _sha({"observations": rows, "kinds": kinds})}


def market_dependency(conn, observation):
    owned = {"security_lifecycle_observations", "security_lifecycle_observation_kinds"}
    parents = {"security_lifecycle_observations": [observation], "security_lifecycle_observation_kinds": conn.execute(
        "SELECT * FROM security_lifecycle_observation_kinds WHERE observation_id=?", (observation["id"],)).fetchall()}
    for child, parent, columns in foreign_keys(conn):
        if parent not in owned or child in owned:
            continue
        if any(column is None for _, column in columns):
            return True
        for row in parents[parent]:
            predicate = " AND ".join(f"{q(child_col)}=?" for child_col, _ in columns)
            if conn.execute(f"SELECT 1 FROM {q(child)} WHERE {predicate} LIMIT 1", tuple(row[parent_col] for _, parent_col in columns)).fetchone():
                return True
    return False


def preview_disposal(market_path, profile_path):
    with connect(profile_path) as profile, connect(market_path) as market:
        verify_profile_connection(profile)
        verify_market_connection(market)
        profile.execute("BEGIN")
        market.execute("BEGIN")
        discarded, retained = [], []
        observations = market.execute("SELECT * FROM security_lifecycle_observations WHERE source='sec_edgar' ORDER BY id").fetchall()
        kept_market = [row for row in observations if market_dependency(market, row)]
        market_keys = {(row["source"], row["source_ref"], row["ticker"]) for row in kept_market}
        cases = profile.execute("SELECT case_id,source,source_ref,ticker FROM security_lifecycle_cases WHERE source='sec_edgar' ORDER BY case_id").fetchall()
        for case in cases:
            _, reason = closure(profile, case["case_id"])
            if (case["source"], case["source_ref"], case["ticker"]) in market_keys:
                reason = "market_dependency"
            if reason:
                retained.append({**dict(case), "reason": reason})
            else:
                discarded.append(case["case_id"])
        kept_keys = {(row["source"], row["source_ref"], row["ticker"]) for row in retained} | market_keys
        ids = [row["id"] for row in observations if (row["source"], row["source_ref"], row["ticker"]) not in kept_keys]
        observed_keys = {(row["source"], row["source_ref"], row["ticker"]) for row in observations}
        case_keys = {(row["source"], row["source_ref"], row["ticker"]) for row in cases}
        unsigned = {"version": 1, "roots": discarded, "retained": retained,
            "retained_observations": [{"id": row["id"], "ticker": row["ticker"], "reason": "market_dependency"} for row in kept_market],
            "counts": {"cases": len(cases), "observations": len(observations), "discard_cases": len(discarded), "retained_cases": len(retained),
                "discard_observations": len(ids), "observation_only": len(observed_keys - case_keys), "case_only": len(case_keys - observed_keys)},
            "stages": {"profile": profile_scope(profile, discarded), "market": market_scope(market, ids)}}
        return {**unsigned, "approval_sha256": _sha(unsigned)}


def _delete_order(conn, names):
    remaining, ordered = set(names), []
    edges = foreign_keys(conn)
    while remaining:
        leaves = sorted(table for table in remaining if not any(child in remaining and child != table and parent == table for child, parent, _ in edges))
        if not leaves:
            raise ValueError("disposal_dependency_cycle")
        ordered.extend(leaves)
        remaining.difference_update(leaves)
    return ordered


def apply_disposal_stage(path, plan, *, stage, approval_sha256, backup_path, app_stopped, profile_path=None):
    if stage not in {"profile", "market"} or app_stopped is not True:
        raise ValueError("disposal_app_stop_required")
    unsigned = {key: value for key, value in plan.items() if key != "approval_sha256"}
    if _sha(unsigned) != approval_sha256 or plan.get("approval_sha256") != approval_sha256:
        raise ValueError("disposal_approval_invalid")
    if stage == "market":
        if profile_path is None:
            raise ValueError("disposal_profile_stage_required")
        with connect(profile_path) as profile:
            verify_journal(profile)
            if _receipt(profile, approval_sha256, "profile") is None:
                raise ValueError("disposal_profile_stage_required")
    with connect(path, "rw") as conn:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE name='lifecycle_legacy_disposal_receipts'").fetchone()
        receipt = _receipt(conn, approval_sha256, stage)
        if receipt is not None:
            if stage == "profile":
                reappeared = any(conn.execute("SELECT 1 FROM security_lifecycle_cases WHERE case_id=?", (identity,)).fetchone() for identity in plan["roots"])
            else:
                reappeared = any(conn.execute("SELECT 1 FROM security_lifecycle_observations WHERE id=?", (identity,)).fetchone() for identity in plan["stages"]["market"]["observation_ids"])
            if reappeared:
                raise ValueError("disposal_changed")
            return {**receipt, "status": "already_completed"}
        if stage == "profile":
            verify_journal(conn)
        expected = plan["stages"][stage]
        def observed():
            return profile_scope(conn, plan["roots"]) if stage == "profile" else market_scope(conn, expected["observation_ids"])
        if observed() != expected:
            raise ValueError("disposal_changed")
        backup = Path(backup_path).resolve()
        if backup == Path(path).resolve():
            raise ValueError("disposal_backup_path")
        _backup(conn, backup)
        conn.execute("BEGIN IMMEDIATE")
        try:
            if observed() != expected:
                raise ValueError("disposal_changed")
            if not exists:
                conn.execute(RECEIPT_SQL)
                for sql in RECEIPT_TRIGGERS.values():
                    conn.execute(sql)
            if stage == "profile":
                dropped = []
                for name, sql in WEB_TRIGGERS.items():
                    owner = conn.execute("SELECT tbl_name,sql FROM sqlite_master WHERE name=?", (name,)).fetchone()
                    if owner and owner[0] in expected:
                        if _normalize_sql(owner[1]) != _normalize_sql(sql):
                            raise ValueError("disposal_changed")
                        conn.execute(f"DROP TRIGGER {q(name)}")
                        dropped.append(sql)
                for table in _delete_order(conn, expected):
                    conn.executemany(f"DELETE FROM {q(table)} WHERE rowid=?", [(identity,) for identity in expected[table]["rowids"]])
                for sql in dropped:
                    conn.execute(sql)
                verify_profile_connection(conn)
                verify_journal(conn)
            else:
                conn.executemany("DELETE FROM security_lifecycle_observation_kinds WHERE observation_id=?", [(i,) for i in expected["observation_ids"]])
                conn.executemany("DELETE FROM security_lifecycle_observations WHERE id=?", [(i,) for i in expected["observation_ids"]])
                verify_market_connection(conn)
            if conn.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("disposal_foreign_key")
            receipt = {"status": "completed", "stage": stage, "approval_sha256": approval_sha256,
                "backup_sha256": _sha_file(backup),
                "counts": {table: len(value["rowids"]) for table, value in expected.items()} if stage == "profile" else {"observations": len(expected["observation_ids"])}}
            conn.execute("INSERT INTO lifecycle_legacy_disposal_receipts VALUES(?,?,?,?,?)",
                (approval_sha256, stage, datetime.now(timezone.utc).isoformat(), _json(receipt), _sha(receipt)))
            conn.commit()
            return receipt
        except BaseException:
            conn.rollback()
            raise
