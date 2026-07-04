#!/usr/bin/env python3
"""N9 batch-2 PostgreSQL archive/drop gate.

Batch-2 is narrower than batch-1: archive and drop the frozen PG ``job_runs``
table plus the orphan ``news_search_vector_update()`` function. Runtime already
uses local stores; this tool only builds evidence, proves the archive restores,
and performs the reviewed destructive drop.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import unquote, urlsplit, urlunsplit

TARGET_TABLES = ("job_runs",)
TARGET_FUNCTION_SIGNATURES = ("news_search_vector_update()",)
EXCLUDED_TABLES = (
    "prices",
    "agent_queries",
    "research_reports",
    "agent_memories",
)

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_BATCH2_TARGET_RE = re.compile(r"\bjob_runs\b|news_search_vector_update", re.IGNORECASE)
_BATCH1_RETIRED_RE = re.compile(
    r"\b(query_news_scores|news_scores|news_latest_scores|financial_data_cache|"
    r"iv_history|fundamentals)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str = ""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sort_report_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _sort_report_value(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return sorted((_sort_report_value(v) for v in value), key=_canonical_json)
    if isinstance(value, tuple):
        return [_sort_report_value(v) for v in value]
    return value


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _quote_ident(name: str) -> str:
    if not _IDENT_RE.match(name):
        raise ValueError(f"unsafe identifier: {name!r}")
    return '"' + name.replace('"', '""') + '"'


def _public_name(name: str) -> str:
    return f"public.{_quote_ident(name)}"


def build_evidence_report(
    *,
    pg_snapshot: Mapping[str, Any],
    grep_summary: Mapping[str, Any],
    local_default_proof: Mapping[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "scope": "pg_exit_n9_batch2",
        "targets": {
            "tables": sorted(TARGET_TABLES),
            "functions": sorted(TARGET_FUNCTION_SIGNATURES),
            "excluded_tables": sorted(EXCLUDED_TABLES),
        },
        "pg_snapshot": _sort_report_value(pg_snapshot),
        "grep_summary": _sort_report_value(grep_summary),
        "local_default_proof": _sort_report_value(local_default_proof),
    }
    payload["fingerprint"] = _sha256(payload)
    return payload


def classify_catalog_objects(
    regclass_by_name: Mapping[str, str | None],
    functions_by_signature: Mapping[str, bool],
) -> dict[str, list[dict[str, Any]]]:
    objects: list[dict[str, Any]] = []
    for name in sorted(TARGET_TABLES):
        objects.append({
            "kind": "table",
            "name": name,
            "status": "present" if regclass_by_name.get(name) is not None else "missing_unexpected",
        })
    for name in sorted(EXCLUDED_TABLES):
        objects.append({
            "kind": "excluded_table",
            "name": name,
            "status": "excluded_present" if regclass_by_name.get(name) is not None else "excluded_missing",
        })
    functions = [
        {
            "kind": "function",
            "name": signature,
            "status": "present" if functions_by_signature.get(signature) else "missing_unexpected",
        }
        for signature in sorted(TARGET_FUNCTION_SIGNATURES)
    ]
    return {"objects": objects, "functions": functions}


def classify_grep_hits(hits: Sequence[tuple[str, str]]) -> dict[str, list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    allowed: list[dict[str, str]] = []
    for path, match in hits:
        reason = _classify_single_hit(path, match)
        item = {"path": path, "reason": reason, "match": match}
        if reason == "runtime_reference_to_batch2_target":
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
    if p == "scripts/migration/n9_batch2_cleanup.py":
        return "n9_batch2_orchestrator"
    if p == "scripts/migration/n9_batch1_pg_drop.py":
        return "n9_batch1_archive_gate"
    if p.startswith("scripts/"):
        return "retired_cli_or_script"
    if p == "src/service/job_runs_store.py":
        return "local_sqlite_authority"
    if p == "src/service/job_runs_cutover.py":
        return "migration_cutover_dead_path_pending_batch2_cleanup"
    if p == "src/tools/backends/db_backend.py":
        return "retired_pg_backend_stub"
    if any(token in p for token in (
        "sqlite_backend.py",
        "local_market_backend.py",
        "sa_capture_backend.py",
        "macro_calendar/local_store.py",
        "service/jobs.py",
        "service/provider_health.py",
        "service/sa_market_news_health.py",
        "tools/sa_tools.py",
    )):
        return "local_sqlite_authority"
    if p == "src/service/data_scheduler.py":
        return "retired_source_guarded"
    if _BATCH2_TARGET_RE.search(match):
        return "runtime_reference_to_batch2_target"
    if _BATCH1_RETIRED_RE.search(match):
        return "retired_pg_domain_reference"
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

        names = sorted(set(TARGET_TABLES) | set(EXCLUDED_TABLES))
        cur.execute(
            """
            SELECT name, to_regclass('public.' || name) AS regclass
            FROM unnest(%s::text[]) AS name
            """,
            (names,),
        )
        regclass_by_name = {name: regclass for name, regclass in cur.fetchall()}

        function_presence: dict[str, bool] = {}
        for signature in TARGET_FUNCTION_SIGNATURES:
            cur.execute("SELECT to_regprocedure(%s)", (signature,))
            function_presence[signature] = cur.fetchone()[0] is not None

        classified = classify_catalog_objects(regclass_by_name, function_presence)
        row_counts: dict[str, int] = {}
        row_fingerprints: dict[str, str] = {}
        for item in classified["objects"]:
            if item["kind"] != "table" or item["status"] != "present":
                continue
            name = item["name"]
            cur.execute(f"SELECT COUNT(*) FROM {_public_name(name)}")
            count = int(cur.fetchone()[0])
            row_counts[name] = count
            item["row_count"] = count
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
            WHERE c.relname = ANY(%(names)s)
            UNION
            SELECT DISTINCT
                   'pg_proc',
                   p.oid::regprocedure::text,
                   c.relname || ' (rowtype)',
                   d.deptype::text
            FROM pg_depend d
            JOIN pg_proc p ON d.classid = 'pg_proc'::regclass AND d.objid = p.oid
            JOIN pg_type t ON d.refclassid = 'pg_type'::regclass AND d.refobjid = t.oid
            JOIN pg_class c ON t.typrelid = c.oid
            WHERE c.relname = ANY(%(names)s)
            ORDER BY 1, 2, 3, 4
            """,
            {"names": list(TARGET_TABLES)},
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
        "objects": classified["objects"],
        "functions": classified["functions"],
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
        "FROM job_runs|INSERT INTO job_runs|UPDATE job_runs|news_search_vector_update|"
        "query_news_scores|news_scores|news_latest_scores|financial_data_cache|iv_history|fundamentals"
    )
    proc = subprocess.run(
        ["rg", "-n", pattern, *[str(p) for p in paths]],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode not in (0, 1):
        return {
            "blockers": [{"path": "<rg>", "reason": "grep_failed", "match": proc.stderr.strip()[:500]}],
            "allowed_hits": [],
        }
    hits: list[tuple[str, str]] = []
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


def collect_local_default_proof() -> dict[str, Any]:
    return {
        "market_unset_routes_local": True,
        "macro_unset_routes_local": True,
        "job_runs_unset_routes_local": True,
        "explicit_false_routes_local": True,
        "source": "static_task1_contract",
    }


def build_pg_dump_command(
    *,
    database_url: str,
    output: str | Path,
    present_tables: Sequence[str],
) -> list[str]:
    del database_url
    cmd = [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        f"--file={Path(output)}",
    ]
    for name in sorted(set(present_tables)):
        if name in TARGET_TABLES:
            cmd.append(f"--table=public.{name}")
    return cmd


def _object_counts(snapshot: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    explicit = snapshot.get("row_counts")
    if isinstance(explicit, Mapping):
        counts.update({str(k): int(v) for k, v in explicit.items()})
    for item in snapshot.get("objects", []):
        if isinstance(item, Mapping) and item.get("status") == "present" and "row_count" in item:
            counts[str(item["name"])] = int(item["row_count"])
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
            mismatches.append({"table": table, "field": "row_count", "expected": expected, "actual": actual})
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
                ddl.append(str(row[0]).rstrip().rstrip(";") + ";\n")
    return "\n".join(ddl)


def pg_client_env(database_url: str, dbname: str | None = None) -> dict[str, str]:
    parts = urlsplit(database_url)
    env: dict[str, str] = {}
    if parts.hostname:
        env["PGHOST"] = parts.hostname
    if parts.port:
        env["PGPORT"] = str(parts.port)
    if parts.username:
        env["PGUSER"] = unquote(parts.username)
    if parts.password:
        env["PGPASSWORD"] = unquote(parts.password)
    name = dbname if dbname is not None else (parts.path.lstrip("/") or None)
    if name:
        env["PGDATABASE"] = name
    return env


def parse_pg_major(text: str) -> int:
    match = re.search(r"(\d+)", str(text))
    if not match:
        raise ValueError(f"cannot parse PostgreSQL version from {text!r}")
    return int(match.group(1))


def _run_checked(
    cmd: Sequence[str], *, database_url: str | None = None, dbname: str | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if database_url:
        env.update(pg_client_env(database_url, dbname))
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


def _pg_dump_client_version_text() -> str:
    return _run_checked(["pg_dump", "--version"]).stdout.strip()


def ensure_pg_dump_client_compatible(server_version: Any) -> None:
    if parse_pg_major(_pg_dump_client_version_text()) < parse_pg_major(server_version):
        raise SystemExit("pg_dump client is older than server; install matching/newer PostgreSQL client")


def _database_url_for_db(database_url: str, dbname: str) -> str:
    parts = urlsplit(database_url)
    return urlunsplit((parts.scheme, parts.netloc, "/" + dbname, parts.query, parts.fragment))


def _present_names(report: Mapping[str, Any], kind: str) -> list[str]:
    return sorted(
        str(item["name"])
        for item in report.get("pg_snapshot", {}).get("objects", [])
        if isinstance(item, Mapping) and item.get("kind") == kind and item.get("status") == "present"
    )


def _present_functions(report: Mapping[str, Any]) -> list[str]:
    return sorted(
        str(item["name"])
        for item in report.get("pg_snapshot", {}).get("functions", [])
        if isinstance(item, Mapping) and item.get("status") == "present"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="N9 batch-2 PG archive/drop gate")
    sub = parser.add_subparsers(dest="cmd", required=True)

    preview = sub.add_parser("preview", help="Build read-only N9 batch-2 evidence report")
    preview.add_argument("--database-url", required=True)
    preview.add_argument("--repo-root", required=True)
    preview.add_argument("--output", required=True)

    dump = sub.add_parser("dump", help="Create targeted N9 batch-2 PG archive")
    dump.add_argument("--database-url", required=True)
    dump.add_argument("--expected-report", required=True)
    dump.add_argument("--archive-dir", required=True)

    verify = sub.add_parser("verify-dump", help="Restore archive into a disposable DB and verify")
    verify.add_argument("--database-url", required=True)
    verify.add_argument("--archive-dir", required=True)
    verify.add_argument("--restore-db", required=True)
    verify.add_argument("--confirm-create-drop-restore-db", action="store_true")

    drop = sub.add_parser("drop", help="Drop reviewed N9 batch-2 PG objects")
    drop.add_argument("--database-url", required=True)
    drop.add_argument("--archive-dir")
    drop.add_argument("--reviewed-fingerprint")
    drop.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    drop.add_argument("--confirm-scheduler-paused", action="store_true")
    drop.add_argument("--confirm-native-host-paused", action="store_true")
    drop.add_argument("--confirm-destructive-drop", action="store_true")

    post = sub.add_parser("postcheck", help="Verify catalog state after N9 batch-2 drop")
    post.add_argument("--database-url", required=True)
    post.add_argument("--archive-dir", required=True)

    return parser


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    return build_arg_parser().parse_args(argv)


def _cmd_preview(args: argparse.Namespace) -> int:
    conn = connect_pg(args.database_url)
    try:
        report = build_evidence_report(
            pg_snapshot=collect_pg_snapshot(conn),
            grep_summary=collect_repo_grep_summary(args.repo_root),
            local_default_proof=collect_local_default_proof(),
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


def _cmd_dump(args: argparse.Namespace) -> int:
    archive_dir = Path(args.archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    evidence = _load_json(args.expected_report)
    server_version = evidence.get("pg_snapshot", {}).get("server_version")
    if server_version:
        ensure_pg_dump_client_compatible(server_version)
    _write_json(archive_dir / "evidence.json", evidence)
    dump_path = archive_dir / "n9_batch2.dump"
    cmd = build_pg_dump_command(
        database_url=args.database_url,
        output=dump_path,
        present_tables=_present_names(evidence, "table"),
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
        "scope": "pg_exit_n9_batch2",
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


def _cmd_verify_dump(args: argparse.Namespace) -> int:
    if not args.confirm_create_drop_restore_db:
        raise SystemExit("--confirm-create-drop-restore-db is required")
    archive_dir = Path(args.archive_dir)
    evidence = _load_json(archive_dir / "evidence.json")
    manifest = _load_json(archive_dir / "manifest.json")
    dump_path = archive_dir / "n9_batch2.dump"
    dump_sha = file_sha256(dump_path)
    if dump_sha != manifest.get("dump_sha256"):
        raise SystemExit("dump sha256 does not match manifest")

    restore_db = args.restore_db
    restore_url = _database_url_for_db(args.database_url, restore_db)
    created = False
    proof: dict[str, Any] = {"ok": False, "mismatches": [{"error": "not_run"}]}
    try:
        _run_checked(["createdb", restore_db], database_url=args.database_url)
        created = True
        _run_checked(
            ["pg_restore", "--exit-on-error", "--dbname", restore_db, str(dump_path)],
            database_url=args.database_url,
            dbname=restore_db,
        )
        function_ddl = archive_dir / "function_ddl.sql"
        if function_ddl.exists() and function_ddl.read_text(encoding="utf-8").strip():
            _run_checked(
                ["psql", "-v", "ON_ERROR_STOP=1", "--dbname", restore_db, "--file", str(function_ddl)],
                database_url=args.database_url,
                dbname=restore_db,
            )
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


def build_drop_sql(*, present_tables: Sequence[str], present_functions: Sequence[str]) -> list[str]:
    statements: list[str] = []
    for signature in sorted(present_functions):
        statements.append(f"DROP FUNCTION IF EXISTS public.{signature}")
    tables = [table for table in sorted(present_tables) if table in TARGET_TABLES]
    if tables:
        statements.append("DROP TABLE IF EXISTS " + ", ".join(f"public.{table}" for table in tables))
    for statement in statements:
        if "CASCADE" in statement.upper():
            raise ValueError("drop SQL must not use CASCADE")
    return statements


def validate_drop_args(args: argparse.Namespace) -> ValidationResult:
    if not getattr(args, "reviewed_fingerprint", None):
        return ValidationResult(False, "missing_reviewed_fingerprint")
    archive_dir = Path(getattr(args, "archive_dir", "") or "")
    if not archive_dir.exists():
        return ValidationResult(False, "missing_archive_dir")
    proof_path = archive_dir / "restore_proof.json"
    if not proof_path.exists():
        return ValidationResult(False, "missing_restore_proof")
    proof = _load_json(proof_path)
    if proof.get("ok") is not True:
        return ValidationResult(False, "restore_proof_not_ok")
    evidence_path = archive_dir / "evidence.json"
    manifest_path = archive_dir / "manifest.json"
    dump_path = archive_dir / "n9_batch2.dump"
    if not evidence_path.exists():
        return ValidationResult(False, "missing_evidence")
    if not manifest_path.exists():
        return ValidationResult(False, "missing_manifest")
    if not dump_path.exists():
        return ValidationResult(False, "missing_dump")
    evidence = _load_json(evidence_path)
    manifest = _load_json(manifest_path)
    if evidence.get("fingerprint") != args.reviewed_fingerprint:
        return ValidationResult(False, "reviewed_fingerprint_mismatch")
    if proof.get("evidence_fingerprint") not in (None, args.reviewed_fingerprint):
        return ValidationResult(False, "restore_proof_fingerprint_mismatch")
    if manifest.get("dump_sha256") != file_sha256(dump_path):
        return ValidationResult(False, "dump_sha256_mismatch")
    if not getattr(args, "confirm_scheduler_paused", False):
        return ValidationResult(False, "missing_scheduler_pause_confirmation")
    if not getattr(args, "confirm_native_host_paused", False):
        return ValidationResult(False, "missing_native_host_pause_confirmation")
    if not getattr(args, "confirm_destructive_drop", False):
        return ValidationResult(False, "missing_destructive_drop_confirmation")
    return ValidationResult(True)


def _verify_post_drop_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    targets_still_present = [
        item["name"]
        for item in snapshot.get("objects", [])
        if item.get("kind") == "table" and item.get("name") in TARGET_TABLES and item.get("status") == "present"
    ]
    functions_still_present = [
        item["name"]
        for item in snapshot.get("functions", [])
        if item.get("name") in TARGET_FUNCTION_SIGNATURES and item.get("status") == "present"
    ]
    excluded_missing = [
        item["name"]
        for item in snapshot.get("objects", [])
        if item.get("kind") == "excluded_table" and item.get("status") != "excluded_present"
    ]
    return {
        "ok": not targets_still_present and not functions_still_present and not excluded_missing,
        "targets_still_present": sorted(targets_still_present + functions_still_present),
        "excluded_missing": sorted(excluded_missing),
    }


def _cmd_drop(args: argparse.Namespace) -> int:
    result = validate_drop_args(args)
    if not result.ok:
        raise SystemExit(result.reason)
    archive_dir = Path(args.archive_dir)
    evidence = _load_json(archive_dir / "evidence.json")

    conn = connect_pg(args.database_url)
    try:
        current = build_evidence_report(
            pg_snapshot=collect_pg_snapshot(conn),
            grep_summary=collect_repo_grep_summary(args.repo_root),
            local_default_proof=collect_local_default_proof(),
        )
        if current.get("fingerprint") != evidence.get("fingerprint"):
            raise SystemExit("current evidence fingerprint differs from reviewed archive evidence")
        statements = build_drop_sql(
            present_tables=_present_names(evidence, "table"),
            present_functions=_present_functions(evidence),
        )
        try:
            with conn.cursor() as cur:
                cur.execute("BEGIN")
                cur.execute("SET LOCAL lock_timeout = '5s'")
                cur.execute("SET LOCAL statement_timeout = '60s'")
                for statement in statements:
                    cur.execute(statement)
                post = collect_pg_snapshot(conn)
                status = _verify_post_drop_snapshot(post)
                if not status["ok"]:
                    raise RuntimeError(f"post-drop validation failed: {status}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.close()
    print(json.dumps({
        "status": "dropped",
        "fingerprint": evidence["fingerprint"],
        "dropped_tables": len(_present_names(evidence, "table")),
        "dropped_functions": len(_present_functions(evidence)),
    }))
    return 0


def _cmd_postcheck(args: argparse.Namespace) -> int:
    archive_dir = Path(args.archive_dir)
    evidence = _load_json(archive_dir / "evidence.json")
    conn = connect_pg(args.database_url)
    try:
        snapshot = collect_pg_snapshot(conn)
    finally:
        conn.close()
    status = _verify_post_drop_snapshot(snapshot)
    status.update({
        "status": "postcheck",
        "evidence_fingerprint": evidence.get("fingerprint"),
    })
    print(json.dumps(status, sort_keys=True))
    return 0 if status["ok"] else 1


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or [])
    if args.cmd == "preview":
        return _cmd_preview(args)
    if args.cmd == "dump":
        return _cmd_dump(args)
    if args.cmd == "verify-dump":
        return _cmd_verify_dump(args)
    if args.cmd == "drop":
        return _cmd_drop(args)
    if args.cmd == "postcheck":
        return _cmd_postcheck(args)
    raise SystemExit(f"unknown command: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
