"""Authorized metadata inventory. No application bootstrap or credential reads."""

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3


COLUMNS = {
    "sqlite_master": {"name", "type", "tbl_name", "sql"},
    "sqlite_schema": {"name", "type", "tbl_name", "sql"},
    "llm_credentials": {"id", "provider", "auth_type", "active", "updated_at", "expires_at"},
    "model_route": {"task", "provider", "model", "effort", "updated_at"},
    "data_provider_config": {"provider", "field", "updated_at"},
    "security_lifecycle_cases": {"case_id", "source", "source_ref", "ticker"},
    "security_lifecycle_observations": {"id", "source", "source_ref", "ticker"},
    "security_lifecycle_provider_checks": {"check_id", "ticker", "state", "observed_at", "rowid"},
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@contextmanager
def read_connection(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    conn.execute("PRAGMA query_only=ON")
    reads = set()

    def authorize(operation, first, second, database, trigger):
        if operation == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if operation == sqlite3.SQLITE_READ:
            columns = COLUMNS.get(first, set())
            column = (second or "").lower()
            if column in columns or (not column and (first in COLUMNS or first.startswith("security_lifecycle_") or first.startswith("lifecycle_web_"))):
                reads.add((first, column))
                return sqlite3.SQLITE_OK
        if operation == sqlite3.SQLITE_FUNCTION and second in {"count", "min", "max"}:
            return sqlite3.SQLITE_OK
        if operation == sqlite3.SQLITE_TRANSACTION and first in {"BEGIN", "ROLLBACK"}:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    conn.set_authorizer(authorize)
    try:
        conn.execute("BEGIN")
        yield conn, reads
    finally:
        conn.rollback()
        conn.close()


def write_new_json(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")


def schema(conn):
    rows = conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()
    tables = {row[1] for row in rows if row[0] == "table"}
    owned = sorted(name for name in tables if name.startswith(("security_lifecycle_", "lifecycle_web_")))
    counts = {}
    for name in owned:
        quoted = '"' + name.replace('"', '""') + '"'
        counts[name] = conn.execute("SELECT COUNT(*) FROM " + quoted).fetchone()[0]
    return {"schema_sha256": digest(rows), "table_count": len(tables),
            "lifecycle_table_rows": counts, "web_journal_present": any(name.startswith("lifecycle_web_") for name in tables)}, tables


def correspondence(cases, observations, provider_tickers):
    cases, observations = set(map(tuple, cases)), set(map(tuple, observations))
    provider = {("listing_authority", "listing:" + ticker, ticker) for ticker in provider_tickers}
    expected = observations | provider
    return {
        "case_count": len(cases), "market_observation_count": len(observations),
        "provider_case_count": sum(row[0] == "listing_authority" for row in cases),
        "expected_provider_observation_count": len(provider),
        "market_only_count": len(observations - cases),
        "expected_provider_without_case_count": len(provider - cases),
        "case_without_observation_count": len(cases - expected),
        "case_identity_sha256": digest(sorted(cases)),
        "market_identity_sha256": digest(sorted(observations)),
        "expected_identity_sha256": digest(sorted(expected)),
        "case_sources": dict(sorted(Counter(row[0] for row in cases).items())),
    }


def inventory(profile, market, sa):
    # Hold independent read snapshots together; do not imply cross-file atomicity.
    with read_connection(profile) as (pc, pr), read_connection(market) as (mc, mr), read_connection(sa) as (sc, sr):
        profile_schema, tables = schema(pc)
        market_schema, _ = schema(mc)
        sa_schema, _ = schema(sc)
        cases = pc.execute("SELECT source,source_ref,ticker FROM security_lifecycle_cases ORDER BY source,source_ref,ticker").fetchall()
        observations = mc.execute("SELECT source,source_ref,ticker FROM security_lifecycle_observations ORDER BY source,source_ref,ticker").fetchall()
        checks = pc.execute("SELECT ticker,state,observed_at FROM security_lifecycle_provider_checks ORDER BY observed_at,rowid").fetchall() if "security_lifecycle_provider_checks" in tables else []
        latest = {row[0]: row for row in checks}
        tracked = {row[0] for row in checks if row[1] != "active"}
        credentials = pc.execute("SELECT id,provider,auth_type,active,updated_at,expires_at FROM llm_credentials ORDER BY id").fetchall()
        routes = [dict(zip(("task", "provider", "model", "effort", "updated_at"), row)) for row in pc.execute(
            "SELECT task,provider,model,effort,updated_at FROM model_route ORDER BY task")]
        fields = [dict(zip(("provider", "field", "updated_at"), row)) for row in pc.execute(
            "SELECT provider,field,updated_at FROM data_provider_config ORDER BY provider,field")]
        result = {
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "authority": "2026-09-07 user authorization: read-only schema/case correspondence and non-secret credential metadata",
            "production_writes": False, "provider_calls": 0, "token_store_read": False,
            "snapshot_scope": "independent SQLite read snapshots; no cross-file atomicity claim",
            "profile": profile_schema, "market": market_schema, "sa": sa_schema,
            "correspondence": correspondence(cases, observations, tracked),
            "provider_checks": {"total": len(checks), "latest_tickers": len(latest),
                "latest_state_counts": dict(sorted(Counter(row[1] for row in latest.values()).items())),
                "oldest_latest_observation": min((row[2] for row in latest.values()), default=None),
                "newest_latest_observation": max((row[2] for row in latest.values()), default=None)},
            "credentials": [{"provider": row[1], "auth_type": row[2], "active": bool(row[3]),
                "updated_at": row[4], "expires_at": row[5]} for row in credentials],
            "claude_oauth_candidates": sum(row[1:3] == ("anthropic", "claude_code_oauth") for row in credentials),
            "model_routes": routes, "configured_provider_fields_not_values": fields,
        }
        result["column_reads"] = {"profile": sorted(pr), "market": sorted(mr), "sa": sorted(sr)}
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--market", required=True, type=Path)
    parser.add_argument("--sa", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("inventory output already exists")
    result = inventory(args.profile, args.market, args.sa)
    write_new_json(args.output, result)
    print(json.dumps({"correspondence": result["correspondence"], "provider_checks": result["provider_checks"],
        "web_journal_present": result["profile"]["web_journal_present"], "credentials": result["credentials"],
        "claude_oauth_candidates": result["claude_oauth_candidates"], "model_routes": result["model_routes"]}, indent=2))


if __name__ == "__main__":
    main()
