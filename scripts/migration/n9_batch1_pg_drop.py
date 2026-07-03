#!/usr/bin/env python3
"""N9 batch-1 PostgreSQL archive/drop gate.

This module is intentionally gate-heavy. ``preview`` is read-only and produces a
fingerprinted evidence report. Destructive drop support is added in later tasks
and must remain gated by reviewed evidence plus restore proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

TARGET_TABLES = (
    "news",
    "news_scores",
    "fundamentals",
    "iv_history",
    "financial_data_cache",
    "signals",
    "sa_alpha_picks",
    "sa_refresh_meta",
    "sa_articles",
    "sa_article_comments",
    "sa_market_news",
    "sa_comment_signals",
    "macro_series",
    "macro_observations",
    "macro_release_dates",
    "cal_economic_events",
    "cal_economic_event_revisions",
    "cal_earnings_events",
    "cal_earnings_event_revisions",
    "cal_ipo_events",
    "cal_ipo_event_revisions",
)

TARGET_VIEWS = ("news_latest_scores",)
TARGET_FUNCTION_SIGNATURES = (
    "news_sentiment_summary(character varying, integer, character varying)",
)
OPTIONAL_TARGETS = {"signals"}
EXCLUDED_TABLES = (
    "prices",
    "job_runs",
    "agent_queries",
    "research_reports",
    "agent_memories",
)

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DROP_DOMAIN_RE = re.compile(
    r"\b(news_scores|news_latest_scores|news_sentiment_summary|financial_data_cache|"
    r"iv_history|fundamentals|sa_[A-Za-z0-9_]+|macro_[A-Za-z0-9_]+|cal_[A-Za-z0-9_]+|signals)\b"
)


def _sort_report_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _sort_report_value(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return sorted((_sort_report_value(v) for v in value), key=_canonical_json)
    if isinstance(value, tuple):
        return [_sort_report_value(v) for v in value]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _quote_ident(name: str) -> str:
    if not _IDENT_RE.match(name):
        raise ValueError(f"unsafe identifier: {name!r}")
    return '"' + name.replace('"', '""') + '"'


def _public_name(name: str) -> str:
    return f"public.{_quote_ident(name)}"


def build_evidence_report(*, pg_snapshot: Mapping[str, Any], grep_summary: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "scope": "pg_exit_n9_batch1",
        "targets": {
            "tables": sorted(TARGET_TABLES),
            "views": sorted(TARGET_VIEWS),
            "functions": sorted(TARGET_FUNCTION_SIGNATURES),
            "excluded_tables": sorted(EXCLUDED_TABLES),
        },
        "pg_snapshot": _sort_report_value(pg_snapshot),
        "grep_summary": _sort_report_value(grep_summary),
    }
    payload["fingerprint"] = _sha256(payload)
    return payload


def classify_target_objects(regclass_by_name: Mapping[str, str | None]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name in sorted(set(TARGET_TABLES) | set(TARGET_VIEWS)):
        present = regclass_by_name.get(name) is not None
        if present:
            status = "present"
        elif name in OPTIONAL_TARGETS:
            status = "missing_expected_optional"
        else:
            status = "missing_unexpected"
        out[name] = {
            "kind": "view" if name in TARGET_VIEWS else "table",
            "name": name,
            "status": status,
        }
    for name in sorted(EXCLUDED_TABLES):
        present = regclass_by_name.get(name) is not None
        out[name] = {
            "kind": "excluded_table",
            "name": name,
            "status": "excluded_present" if present else "excluded_missing",
        }
    return out


def classify_grep_hits(hits: Sequence[tuple[str, str]]) -> dict[str, list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    allowed: list[dict[str, str]] = []
    for path, match in hits:
        reason = _classify_single_hit(path, match)
        item = {"path": path, "reason": reason, "match": match}
        if reason == "runtime_reference_to_drop_target":
            blockers.append(item)
        else:
            allowed.append(item)
    return {
        "blockers": sorted(blockers, key=lambda x: (x["path"], x["match"])),
        "allowed_hits": sorted(allowed, key=lambda x: (x["path"], x["match"])),
    }


def _classify_single_hit(path: str, match: str) -> str:
    p = path.replace("\\", "/")
    if p.startswith(("tests/", "docs/", "sql/")):
        return "docs_or_tests"
    if "local_market_backend.py" in p and "super().query_iv_history" in match:
        return "runtime_reference_to_drop_target"
    if "api/routes/market_data.py" in p and ("prices\", \"iv" in match or "bootstrap_market" in match or "validate_market" in match):
        return "runtime_reference_to_drop_target"
    if "market_data_admin.py" in p and (
        "FROM iv_history" in match
        or "FROM fundamentals" in match
        or "FROM news" in match
    ):
        return "runtime_reference_to_drop_target"
    if "migrate_to_supabase.py" in p and ("import_iv_history" in match or "import_fundamentals" in match or "import_news(" in match):
        return "archive_script_pending_disable_check"
    if "db_backend.py" in p:
        return "invalidated_rollback_lever_pending_n9_cleanup"
    if any(token in p for token in ("sqlite_backend.py", "sa_capture_backend.py", "macro_calendar/local_store.py")):
        return "local_sqlite_authority"
    if _DROP_DOMAIN_RE.search(match):
        return "runtime_reference_to_drop_target"
    return "allowed_non_target"


def connect_pg(database_url: str):
    import psycopg2

    return psycopg2.connect(database_url)


def collect_pg_snapshot(conn) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout = '30s'")
        cur.execute("SHOW server_version")
        server_version = cur.fetchone()[0]

        names = sorted(set(TARGET_TABLES) | set(TARGET_VIEWS) | set(EXCLUDED_TABLES))
        cur.execute(
            """
            SELECT name, to_regclass('public.' || name) AS regclass
            FROM unnest(%s::text[]) AS name
            """,
            (names,),
        )
        regclass_by_name = {name: regclass for name, regclass in cur.fetchall()}
        objects_by_name = classify_target_objects(regclass_by_name)

        row_counts: dict[str, int] = {}
        row_fingerprints: dict[str, str] = {}
        for name in TARGET_TABLES:
            if objects_by_name[name]["status"] != "present":
                continue
            cur.execute(f"SELECT COUNT(*) FROM {_public_name(name)}")
            row_counts[name] = int(cur.fetchone()[0])
            cur.execute(
                f"""
                SELECT md5(COALESCE(string_agg(md5(row_to_json(t)::text), ''
                                      ORDER BY row_to_json(t)::text), '')) AS row_fingerprint
                FROM {_public_name(name)} AS t
                """
            )
            row_fingerprints[name] = cur.fetchone()[0]

        cur.execute(
            """
            SELECT DISTINCT
                   d.classid::regclass::text AS dependent_catalog,
                   d.objid::regclass::text AS dependent_object,
                   d.refobjid::regclass::text AS referenced_object,
                   d.deptype::text AS dependency_type
            FROM pg_depend d
            JOIN pg_class c ON c.oid = d.refobjid
            WHERE c.relname = ANY(%s)
            ORDER BY 1, 2, 3, 4
            """,
            (list(TARGET_TABLES) + list(TARGET_VIEWS),),
        )
        dependencies = [
            {
                "dependent_catalog": row[0],
                "dependent_object": row[1],
                "referenced_object": row[2],
                "dependency_type": row[3],
            }
            for row in cur.fetchall()
        ]

    return {
        "server_version": server_version,
        "objects": list(objects_by_name.values()),
        "row_counts": row_counts,
        "row_fingerprints": row_fingerprints,
        "dependencies": dependencies,
    }


def collect_repo_grep_summary(repo_root: str | Path) -> dict[str, list[dict[str, str]]]:
    root = Path(repo_root)
    paths = [p for p in (root / "src", root / "scripts", root / "tests", root / "docs", root / "sql") if p.exists()]
    if not paths:
        return {"blockers": [], "allowed_hits": []}
    pattern = (
        "news_scores|news_latest_scores|news_sentiment_summary|financial_data_cache|"
        "iv_history|fundamentals|sa_|macro_|cal_|signals|query_iv_history|query_fundamentals|"
        "get_financial_cache|incremental_update\\(|--news|--iv|--fundamentals|--scores"
    )
    proc = subprocess.run(
        ["rg", "-n", pattern, *[str(p) for p in paths]],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    hits: list[tuple[str, str]] = []
    if proc.returncode not in (0, 1):
        return {
            "blockers": [{
                "path": "<rg>",
                "reason": "grep_failed",
                "match": proc.stderr.strip()[:500],
            }],
            "allowed_hits": [],
        }
    for line in proc.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        path, _lineno, match = parts
        try:
            rel = str(Path(path).resolve().relative_to(root.resolve()))
        except ValueError:
            rel = path
        hits.append((rel, match.strip()))
    return classify_grep_hits(hits)


def build_pg_dump_command(
    *,
    database_url: str,
    output: str | Path,
    present_tables: Sequence[str],
    present_views: Sequence[str],
) -> list[str]:
    del database_url  # supplied to subprocess env by the caller; do not expose in argv
    cmd = [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        f"--file={Path(output)}",
    ]
    for name in sorted(set(present_tables) | set(present_views)):
        if name in EXCLUDED_TABLES:
            continue
        cmd.append(f"--table=public.{name}")
    return cmd


def _object_counts(snapshot: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    explicit_counts = snapshot.get("row_counts")
    if isinstance(explicit_counts, Mapping):
        counts.update({str(k): int(v) for k, v in explicit_counts.items()})
    for obj in snapshot.get("objects", []):
        if not isinstance(obj, Mapping):
            continue
        if obj.get("status") == "present" and "row_count" in obj:
            counts[str(obj["name"])] = int(obj["row_count"])
    return counts


def compare_restore_to_evidence(restored: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    expected_snapshot = evidence.get("pg_snapshot", {})
    expected_counts = _object_counts(expected_snapshot)
    restored_counts = _object_counts(restored)
    expected_fps = expected_snapshot.get("row_fingerprints", {})
    restored_fps = restored.get("row_fingerprints", {})
    mismatches: list[dict[str, Any]] = []

    for table in sorted(expected_counts):
        expected = expected_counts.get(table)
        actual = restored_counts.get(table)
        if expected != actual:
            mismatches.append({
                "table": table,
                "field": "row_count",
                "expected": expected,
                "actual": actual,
            })
    for table in sorted(expected_fps):
        expected = expected_fps.get(table)
        actual = restored_fps.get(table)
        if expected != actual:
            mismatches.append({
                "table": table,
                "field": "row_fingerprint",
                "expected": expected,
                "actual": actual,
            })
    return {"ok": not mismatches, "mismatches": mismatches}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_function_ddl(conn) -> str:
    ddl: list[str] = []
    with conn.cursor() as cur:
        for signature in TARGET_FUNCTION_SIGNATURES:
            cur.execute("SELECT pg_get_functiondef(%s::regprocedure::oid)", (signature,))
            row = cur.fetchone()
            if row and row[0]:
                ddl.append(row[0].rstrip() + ";\n")
    return "\n".join(ddl)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="N9 batch-1 PG archive/drop gate")
    sub = parser.add_subparsers(dest="cmd", required=True)

    preview = sub.add_parser("preview", help="Build read-only N9 batch-1 evidence report")
    preview.add_argument("--database-url", required=True)
    preview.add_argument("--repo-root", required=True)
    preview.add_argument("--output", required=True)

    dump = sub.add_parser("dump", help="Create targeted N9 batch-1 PG archive")
    dump.add_argument("--database-url", required=True)
    dump.add_argument("--expected-report", required=True)
    dump.add_argument("--archive-dir", required=True)

    verify = sub.add_parser("verify-dump", help="Restore archive into a disposable DB and verify")
    verify.add_argument("--database-url", required=True)
    verify.add_argument("--archive-dir", required=True)
    verify.add_argument("--restore-db", required=True)
    verify.add_argument("--confirm-create-drop-restore-db", action="store_true")

    return parser


def _cmd_preview(args: argparse.Namespace) -> int:
    conn = connect_pg(args.database_url)
    try:
        report = build_evidence_report(
            pg_snapshot=collect_pg_snapshot(conn),
            grep_summary=collect_repo_grep_summary(args.repo_root),
        )
    finally:
        conn.close()
    _write_json(Path(args.output), report)
    print(json.dumps({
        "status": "previewed",
        "fingerprint": report["fingerprint"],
        "blockers": len(report["grep_summary"]["blockers"]),
        "target_tables": len(TARGET_TABLES),
    }))
    return 0


def _present_names(report: Mapping[str, Any], kind: str) -> list[str]:
    out: list[str] = []
    for obj in report.get("pg_snapshot", {}).get("objects", []):
        if not isinstance(obj, Mapping):
            continue
        if obj.get("kind") == kind and obj.get("status") == "present":
            out.append(str(obj["name"]))
    return sorted(out)


def _run_checked(cmd: Sequence[str], *, database_url: str | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if database_url:
        env["PGDATABASE"] = database_url
    proc = subprocess.run(
        list(cmd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {proc.stderr.strip()[:500]}")
    return proc


def _cmd_dump(args: argparse.Namespace) -> int:
    archive_dir = Path(args.archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    evidence = _load_json(args.expected_report)
    evidence_path = archive_dir / "evidence.json"
    _write_json(evidence_path, evidence)
    dump_path = archive_dir / "n9_batch1.dump"

    cmd = build_pg_dump_command(
        database_url=args.database_url,
        output=dump_path,
        present_tables=_present_names(evidence, "table"),
        present_views=_present_names(evidence, "view"),
    )
    _run_checked(cmd, database_url=args.database_url)
    restore_list = _run_checked(["pg_restore", "--list", str(dump_path)])
    (archive_dir / "pg_restore_list.txt").write_text(restore_list.stdout, encoding="utf-8")

    conn = connect_pg(args.database_url)
    try:
        (archive_dir / "function_ddl.sql").write_text(read_function_ddl(conn), encoding="utf-8")
    finally:
        conn.close()

    manifest = {
        "schema_version": 1,
        "scope": "pg_exit_n9_batch1",
        "evidence_fingerprint": evidence["fingerprint"],
        "dump_sha256": file_sha256(dump_path),
        "dump_file": dump_path.name,
        "restore_list_file": "pg_restore_list.txt",
        "function_ddl_file": "function_ddl.sql",
    }
    _write_json(archive_dir / "manifest.json", manifest)
    print(json.dumps({
        "status": "dumped",
        "fingerprint": evidence["fingerprint"],
        "archive_dir": str(archive_dir),
        "dump_sha256": manifest["dump_sha256"],
    }))
    return 0


def _database_url_for_db(database_url: str, dbname: str) -> str:
    parts = urlsplit(database_url)
    return urlunsplit((parts.scheme, parts.netloc, "/" + dbname, parts.query, parts.fragment))


def _cmd_verify_dump(args: argparse.Namespace) -> int:
    if not args.confirm_create_drop_restore_db:
        raise SystemExit("--confirm-create-drop-restore-db is required")
    archive_dir = Path(args.archive_dir)
    evidence = _load_json(archive_dir / "evidence.json")
    manifest = _load_json(archive_dir / "manifest.json")
    dump_path = archive_dir / "n9_batch1.dump"
    dump_sha = file_sha256(dump_path)
    if dump_sha != manifest.get("dump_sha256"):
        raise SystemExit("dump sha256 does not match manifest")

    restore_db = args.restore_db
    restore_url = _database_url_for_db(args.database_url, restore_db)
    created = False
    try:
        _run_checked(["createdb", restore_db], database_url=args.database_url)
        created = True
        _run_checked(["pg_restore", "--exit-on-error", "--dbname", restore_db, str(dump_path)])
        function_ddl = archive_dir / "function_ddl.sql"
        if function_ddl.exists() and function_ddl.read_text(encoding="utf-8").strip():
            _run_checked(["psql", "--dbname", restore_db, "--file", str(function_ddl)])
        conn = connect_pg(restore_url)
        try:
            restored = collect_pg_snapshot(conn)
        finally:
            conn.close()
        proof = compare_restore_to_evidence(restored, evidence)
        proof.update({
            "evidence_fingerprint": evidence["fingerprint"],
            "dump_sha256": dump_sha,
            "restore_db": restore_db,
        })
        _write_json(archive_dir / "restore_proof.json", proof)
    finally:
        if created:
            _run_checked(["dropdb", restore_db], database_url=args.database_url)

    print(json.dumps({
        "status": "verified" if proof["ok"] else "failed",
        "ok": proof["ok"],
        "fingerprint": evidence["fingerprint"],
    }))
    return 0 if proof["ok"] else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.cmd == "preview":
        return _cmd_preview(args)
    if args.cmd == "dump":
        return _cmd_dump(args)
    if args.cmd == "verify-dump":
        return _cmd_verify_dump(args)
    parser.error(f"unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
