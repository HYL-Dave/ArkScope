#!/usr/bin/env python3
"""N9 batch-1 PostgreSQL archive/drop gate.

This module is intentionally gate-heavy. ``preview`` is read-only and produces a
fingerprinted evidence report. Destructive drop support is added in later tasks
and must remain gated by reviewed evidence plus restore proof.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import unquote, urlsplit, urlunsplit

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
_SQL_TARGET_RE = re.compile(
    r"\b(FROM|JOIN|INTO|UPDATE|TABLE|DROP|DELETE\s+FROM)\s+"
    r"(public\.)?"
    r"(news_scores|news_latest_scores|financial_data_cache|iv_history|fundamentals|signals|"
    r"sa_[A-Za-z0-9_]+|macro_[A-Za-z0-9_]+|cal_[A-Za-z0-9_]+)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str = ""


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
    if p == "scripts/migration/n9_batch1_pg_drop.py":
        return "n9_batch1_orchestrator"
    if p.startswith("scripts/"):
        if p == "scripts/migrate_to_supabase.py":
            return "retired_pg_importer_disabled_or_archive_only"
        return "retired_cli_or_script"
    if p == "src/service/data_scheduler.py" and (
        "collect_iv_history.py" in match
        or "\"--iv\"" in match
        or "_N9_RETIRED_SOURCES" in match
        or "iv_history" in match
    ):
        return "retired_source_guarded"
    if any(token in p for token in (
        "sqlite_backend.py",
        "sa_capture_backend.py",
        "src/sa_capture_store.py",
        "macro_calendar/local_store.py",
        "src/service/jobs.py",
        "src/service/sa_market_news_health.py",
        "src/tools/data_access.py",
        "src/tools/data_coverage_tools.py",
        "src/tools/sa_tools.py",
        "src/tools/sa_digest_tools.py",
        "src/sa/comment_signal_backfill.py",
    )):
        return "local_sqlite_authority"
    if p == "src/news_normalized/score_cutover.py":
        return "migration_cutover_dead_path_pending_n9_cleanup"
    if p.startswith("src/agents/"):
        return "agent_tool_surface"
    if "local_market_backend.py" in p and "super().query_iv_history" in match:
        return "runtime_reference_to_drop_target"
    if "api/routes/market_data.py" in p and ("prices\", \"iv" in match or "bootstrap_market" in match or "validate_market" in match):
        return "runtime_reference_to_drop_target"
    if "market_data_admin.py" in p and _SQL_TARGET_RE.search(match):
        return "invalidated_rollback_lever_pending_n9_cleanup"
    if any(token in p for token in (
        "db_backend.py",
        "macro_calendar/store.py",
        "service/macro_calendar_health.py",
    )):
        return "invalidated_rollback_lever_pending_n9_cleanup"
    if _SQL_TARGET_RE.search(match):
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

    post = sub.add_parser("postcheck", help="Verify catalog state after the N9 batch-1 drop")
    post.add_argument("--database-url", required=True)
    post.add_argument("--archive-dir", required=True)

    drop = sub.add_parser("drop", help="Drop reviewed N9 batch-1 PG objects")
    drop.add_argument("--database-url", required=True)
    drop.add_argument("--archive-dir")
    drop.add_argument("--reviewed-fingerprint")
    drop.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    drop.add_argument("--confirm-scheduler-paused", action="store_true")
    drop.add_argument("--confirm-native-host-paused", action="store_true")
    drop.add_argument("--confirm-destructive-drop", action="store_true")

    return parser


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    return build_arg_parser().parse_args(argv)


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



def collect_trigger_function_ddl(conn, tables) -> str:
    """DDL for non-internal trigger functions attached to the target tables.

    Table-scoped pg_dump emits CREATE TRIGGER but not the function it calls, so a
    restore into a fresh DB needs these definitions applied first."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT pg_get_functiondef(p.oid)
            FROM pg_trigger t
            JOIN pg_class c ON t.tgrelid = c.oid
            JOIN pg_proc p ON t.tgfoid = p.oid
            WHERE NOT t.tgisinternal AND c.relname = ANY(%s)
            ORDER BY 1
            """,
            (list(tables),),
        )
        return "\n\n".join(str(row[0]) for row in cur.fetchall())


def collect_required_extensions(conn) -> list[str]:
    """Non-builtin extensions the archive needs before a restore (e.g. pgvector)."""
    with conn.cursor() as cur:
        cur.execute("SELECT extname FROM pg_extension WHERE extname <> 'plpgsql' ORDER BY extname")
        return [str(row[0]) for row in cur.fetchall()]


def build_extension_statements(extnames) -> list[str]:
    names = sorted({str(n) for n in extnames if str(n) != "plpgsql"})
    return [f'CREATE EXTENSION IF NOT EXISTS "{name}"' for name in names]


def pg_client_env(database_url: str, dbname: str | None = None) -> dict[str, str]:
    """libpq env vars for PG client tools (keeps credentials out of argv)."""
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
    """First integer in a PG client/server version string is the major version."""
    match = re.search(r"(\d+)", str(text))
    if not match:
        raise ValueError(f"cannot parse PostgreSQL version from {text!r}")
    return int(match.group(1))


def _pg_dump_client_version_text() -> str:
    return _run_checked(["pg_dump", "--version"]).stdout.strip()


def ensure_pg_dump_client_compatible(server_version: Any) -> None:
    client_text = _pg_dump_client_version_text()
    if parse_pg_major(client_text) < parse_pg_major(server_version):
        raise SystemExit(
            "pg_dump client is older than server; install matching/newer "
            "PostgreSQL client before destructive N9 dump."
        )


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


def _cmd_dump(args: argparse.Namespace) -> int:
    archive_dir = Path(args.archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    evidence = _load_json(args.expected_report)
    server_version = evidence.get("pg_snapshot", {}).get("server_version")
    if server_version:
        ensure_pg_dump_client_compatible(server_version)
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
        trigger_ddl = collect_trigger_function_ddl(conn, _present_names(evidence, "table"))
        target_ddl = read_function_ddl(conn)
        pieces = [piece for piece in (trigger_ddl, target_ddl) if piece.strip()]
        function_ddl = (
            "SET check_function_bodies = off;\n\n" + "\n\n".join(pieces) + "\n"
            if pieces else ""
        )
        (archive_dir / "function_ddl.sql").write_text(function_ddl, encoding="utf-8")
        required_extensions = collect_required_extensions(conn)
    finally:
        conn.close()

    manifest = {
        "schema_version": 1,
        "scope": "pg_exit_n9_batch1",
        "evidence_fingerprint": evidence["fingerprint"],
        "dump_sha256": file_sha256(dump_path),
        "required_extensions": required_extensions,
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
        for statement in build_extension_statements(manifest.get("required_extensions", [])):
            _run_checked(
                ["psql", "--dbname", restore_db, "-c", statement],
                database_url=args.database_url,
                dbname=restore_db,
            )
        function_ddl = archive_dir / "function_ddl.sql"
        if function_ddl.exists() and function_ddl.read_text(encoding="utf-8").strip():
            # Trigger functions must exist BEFORE pg_restore creates the tables'
            # triggers; check_function_bodies=off lets functions referencing the
            # not-yet-restored tables be created.
            _run_checked(
                ["psql", "--dbname", restore_db, "--file", str(function_ddl)],
                database_url=args.database_url,
                dbname=restore_db,
            )
        _run_checked(
            ["pg_restore", "--exit-on-error", "--dbname", restore_db, str(dump_path)],
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


def build_drop_sql(
    *,
    present_tables: Sequence[str],
    present_views: Sequence[str],
    present_functions: Sequence[str],
) -> list[str]:
    statements: list[str] = []
    for signature in present_functions:
        statements.append(f"DROP FUNCTION IF EXISTS public.{signature}")
    for view in present_views:
        if not _IDENT_RE.match(view):
            raise ValueError(f"unsafe view identifier: {view!r}")
        statements.append(f"DROP VIEW IF EXISTS public.{view}")
    tables = [table for table in present_tables if table not in EXCLUDED_TABLES]
    if tables:
        for table in tables:
            if not _IDENT_RE.match(table):
                raise ValueError(f"unsafe table identifier: {table!r}")
        statements.append("DROP TABLE IF EXISTS " + ", ".join(f"public.{table}" for table in tables))
    for statement in statements:
        if "CASCADE" in statement.upper():
            raise ValueError("drop SQL must not use CASCADE")
    return statements


def validate_drop_args(args: argparse.Namespace) -> ValidationResult:
    if not getattr(args, "reviewed_fingerprint", None):
        return ValidationResult(False, "missing_reviewed_fingerprint")
    archive_dir = Path(getattr(args, "archive_dir", "") or "")
    proof_path = archive_dir / "restore_proof.json"
    if not proof_path.exists():
        return ValidationResult(False, "missing_restore_proof")
    proof = _load_json(proof_path)
    if proof.get("ok") is not True:
        return ValidationResult(False, "restore_proof_not_ok")
    if proof.get("evidence_fingerprint") != args.reviewed_fingerprint:
        return ValidationResult(False, "restore_proof_fingerprint_mismatch")
    manifest_path = archive_dir / "manifest.json"
    dump_path = archive_dir / "n9_batch1.dump"
    if not manifest_path.exists():
        return ValidationResult(False, "missing_archive_manifest")
    if not dump_path.exists():
        return ValidationResult(False, "missing_archive_dump")
    manifest = _load_json(manifest_path)
    if manifest.get("evidence_fingerprint") not in (None, args.reviewed_fingerprint):
        return ValidationResult(False, "archive_manifest_fingerprint_mismatch")
    if manifest.get("dump_sha256") != file_sha256(dump_path):
        return ValidationResult(False, "archive_dump_sha256_mismatch")
    if not getattr(args, "confirm_scheduler_paused", False):
        return ValidationResult(False, "missing_scheduler_pause_confirmation")
    if not getattr(args, "confirm_native_host_paused", False):
        return ValidationResult(False, "missing_native_host_pause_confirmation")
    if not getattr(args, "confirm_destructive_drop", False):
        return ValidationResult(False, "missing_destructive_drop_confirmation")
    return ValidationResult(True)


def _current_evidence_report(*, database_url: str, repo_root: str | Path) -> dict[str, Any]:
    conn = connect_pg(database_url)
    try:
        pg_snapshot = collect_pg_snapshot(conn)
    finally:
        conn.close()
    return build_evidence_report(
        pg_snapshot=pg_snapshot,
        grep_summary=collect_repo_grep_summary(repo_root),
    )


def _read_regclasses(cur, names: Sequence[str]) -> dict[str, str | None]:
    unique_names = sorted(set(names))
    if not unique_names:
        return {}
    cur.execute(
        """
        SELECT name, to_regclass('public.' || name) AS regclass
        FROM unnest(%s::text[]) AS name
        """,
        (unique_names,),
    )
    found = {str(name): regclass for name, regclass in cur.fetchall()}
    return {name: found.get(name) for name in unique_names}


def _read_regprocedures(cur, signatures: Sequence[str]) -> dict[str, str | None]:
    unique_signatures = sorted(set(signatures))
    if not unique_signatures:
        return {}
    cur.execute(
        """
        SELECT signature, to_regprocedure('public.' || signature) AS regprocedure
        FROM unnest(%s::text[]) AS signature
        """,
        (unique_signatures,),
    )
    found = {str(signature): regprocedure for signature, regprocedure in cur.fetchall()}
    return {signature: found.get(signature) for signature in unique_signatures}


def _excluded_present_names(evidence: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for obj in evidence.get("pg_snapshot", {}).get("objects", []):
        if not isinstance(obj, Mapping):
            continue
        if obj.get("kind") == "excluded_table" and obj.get("status") == "excluded_present":
            out.append(str(obj["name"]))
    return sorted(out)


def _verify_post_drop_catalog(
    cur,
    *,
    dropped_tables: Sequence[str],
    dropped_views: Sequence[str],
    dropped_functions: Sequence[str],
    excluded_tables: Sequence[str],
) -> None:
    statuses = _read_regclasses(cur, list(dropped_tables) + list(dropped_views) + list(excluded_tables))
    function_statuses = _read_regprocedures(cur, dropped_functions)
    still_present = sorted(
        name for name in set(dropped_tables) | set(dropped_views)
        if statuses.get(name) is not None
    )
    functions_still_present = sorted(
        signature for signature in set(dropped_functions)
        if function_statuses.get(signature) is not None
    )
    missing_excluded = sorted(name for name in excluded_tables if statuses.get(name) is None)
    if still_present:
        raise RuntimeError("post_drop_target_still_present:" + ",".join(still_present))
    if functions_still_present:
        raise RuntimeError("post_drop_function_still_present:" + ",".join(functions_still_present))
    if missing_excluded:
        raise RuntimeError("post_drop_excluded_missing:" + ",".join(missing_excluded))


def _cmd_drop(args: argparse.Namespace) -> int:
    validation = validate_drop_args(args)
    if not validation.ok:
        raise SystemExit(validation.reason)
    archive_dir = Path(args.archive_dir)
    evidence = _load_json(archive_dir / "evidence.json")
    if evidence.get("fingerprint") != args.reviewed_fingerprint:
        raise SystemExit("evidence fingerprint mismatch")
    current = _current_evidence_report(database_url=args.database_url, repo_root=args.repo_root)
    if current.get("fingerprint") != args.reviewed_fingerprint:
        raise SystemExit("current evidence fingerprint mismatch")

    present_tables = _present_names(evidence, "table")
    present_views = _present_names(evidence, "view")
    statements = build_drop_sql(
        present_tables=present_tables,
        present_views=present_views,
        present_functions=list(TARGET_FUNCTION_SIGNATURES),
    )
    conn = connect_pg(args.database_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout = '5s'")
            cur.execute("SET LOCAL statement_timeout = '60s'")
            for statement in statements:
                cur.execute(statement)
            _verify_post_drop_catalog(
                cur,
                dropped_tables=present_tables,
                dropped_views=present_views,
                dropped_functions=TARGET_FUNCTION_SIGNATURES,
                excluded_tables=_excluded_present_names(evidence),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        print(json.dumps({
            "status": "failed",
            "stage": "drop_transaction",
            "reason": "dependency_blocked",
        }))
        raise
    finally:
        conn.close()
    print(json.dumps({
        "status": "dropped",
        "fingerprint": args.reviewed_fingerprint,
        "dropped_tables": len(present_tables),
        "dropped_statements": len(statements),
    }))
    return 0


def _cmd_postcheck(args: argparse.Namespace) -> int:
    archive_dir = Path(args.archive_dir)
    evidence = _load_json(archive_dir / "evidence.json")
    dropped_tables = _present_names(evidence, "table")
    dropped_views = _present_names(evidence, "view")
    excluded = _excluded_present_names(evidence)
    conn = connect_pg(args.database_url)
    try:
        with conn.cursor() as cur:
            statuses = _read_regclasses(cur, list(dropped_tables) + list(dropped_views) + excluded)
            function_statuses = _read_regprocedures(cur, TARGET_FUNCTION_SIGNATURES)
    finally:
        conn.close()
    still_present = sorted(
        name for name in set(dropped_tables) | set(dropped_views)
        if statuses.get(name) is not None
    )
    functions_still_present = sorted(
        signature for signature in set(TARGET_FUNCTION_SIGNATURES)
        if function_statuses.get(signature) is not None
    )
    excluded_missing = sorted(name for name in excluded if statuses.get(name) is None)
    ok = not still_present and not functions_still_present and not excluded_missing
    print(json.dumps({
        "status": "postcheck",
        "ok": ok,
        "fingerprint": evidence.get("fingerprint"),
        "targets_still_present": still_present,
        "functions_still_present": functions_still_present,
        "excluded_missing": excluded_missing,
    }, sort_keys=True))
    return 0 if ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.cmd == "preview":
        return _cmd_preview(args)
    if args.cmd == "dump":
        return _cmd_dump(args)
    if args.cmd == "verify-dump":
        return _cmd_verify_dump(args)
    if args.cmd == "postcheck":
        return _cmd_postcheck(args)
    if args.cmd == "drop":
        return _cmd_drop(args)
    parser.error(f"unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
