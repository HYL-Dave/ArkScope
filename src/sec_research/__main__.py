"""Operator-only portable bundles; no model-facing filesystem tool."""

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3

from .operations import (export_bundle, restore_bundle, _path, _basename, _file,
                         _new_destination, read_operator_json, write_operator_json)
from .paths import SecResearchPaths
from .maintenance import preview_cleanup, apply_cleanup, validate_preview, _output_path
from .schema_admin import preview_schema_reset, apply_schema_reset


def _profile_path():
    from src.api.dependencies import _local_state_db_path
    return Path(_local_state_db_path())


@contextmanager
def open_profile_readonly(path):
    path = _path(path)
    with _file(path):
        pass
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, isolation_level=None)
    try:
        conn.execute("PRAGMA query_only=ON")
        yield conn
    finally:
        conn.close()


def _maintenance(args):
    operation, action = args.operation.split("-")
    preview_path = _path(args.preview)
    if action == "preview":
        _new_destination(preview_path)
    else:
        if re.fullmatch("[0-9a-f]{64}", args.approval_sha256) is None:
            raise ValueError("sec_research_preview_invalid")
        _new_destination(_path(args.receipt))
        if operation == "schema":
            backup = _path(args.backup)
            _new_destination(backup)
            if _path(args.receipt).is_relative_to(backup):
                raise ValueError("sec_research_admin_path_invalid")
        preview = read_operator_json(preview_path)
        validate_preview(preview, operation=operation, approval_sha256=args.approval_sha256)
    paths = SecResearchPaths.resolve()
    profile_path = _path(_profile_path())
    if action == "preview":
        _output_path(paths, preview_path, profile_path=profile_path)
    else:
        _output_path(paths, args.receipt, profile_path=profile_path)
        if operation == "schema":
            _output_path(paths, args.backup, profile_path=profile_path)
    with open_profile_readonly(profile_path) as profile:
        if action == "preview":
            result = (preview_cleanup(paths, profile_connection=profile) if operation == "cleanup" else
                      preview_schema_reset(paths, mode=args.mode, profile_connection=profile))
            write_operator_json(preview_path, result)
        else:
            kwargs = dict(approval_sha256=args.approval_sha256, receipt_path=args.receipt, profile_connection=profile)
            result = (apply_cleanup(paths, preview, **kwargs) if operation == "cleanup" else
                      apply_schema_reset(paths, preview, backup_path=args.backup, **kwargs))
    # CLI output is a summary; explicit files carry complete operator evidence.
    print(json.dumps({k: result[k] for k in ("format", "version", "status", "code", "approval_sha256")
                      if k in result} | {k: result[k] for k in ("phase", "receipt_phase", "freed_bytes", "recovery",
                                                              "apply_effect", "reference_status")
                                        if k in result}, sort_keys=True))
    return 0 if result["status"] in {"ready", "ok"} else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=(
        "Whole market SQLite database plus SEC capture objects only. Independent "
        "profile/SA stores and other capture roots are not packaged."))
    commands = parser.add_subparsers(dest="operation", required=True)
    export = commands.add_parser("export")
    export.add_argument("--destination", type=Path, required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("--bundle", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    restore.add_argument("--database-name", default="market_data.db")
    for operation in ("cleanup", "schema"):
        preview = commands.add_parser(operation + "-preview", help="Write a create-only observed preview JSON")
        preview.add_argument("--preview", type=Path, required=True)
        if operation == "schema":
            preview.add_argument("--mode", choices=("reset", "uninstall"), required=True)
        apply = commands.add_parser(operation + "-apply", help="Apply one exact digest-approved preview")
        apply.add_argument("--preview", type=Path, required=True)
        apply.add_argument("--approval-sha256", required=True)
        apply.add_argument("--receipt", type=Path, required=True)
        if operation == "schema":
            apply.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.operation in {"cleanup-preview", "cleanup-apply", "schema-preview", "schema-apply"}:
            return _maintenance(args)
        _path(args.destination)
        if args.operation == "export":
            result = export_bundle(SecResearchPaths.resolve(), args.destination)
        else:
            _path(args.bundle)
            _basename(args.database_name)
            result = restore_bundle(args.bundle, args.destination, database_name=args.database_name)
        print(json.dumps({key: result[key] for key in ("format", "version", "scope", "database", "references")}, sort_keys=True))
        return 0
    except (ValueError, OSError, sqlite3.Error, TypeError):
        # Never expose paths, SQLite values, source bodies or exception details.
        print(json.dumps({"status": "unavailable", "code": "sec_research_admin_failed" if "-" in args.operation
                          else "sec_research_bundle_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
