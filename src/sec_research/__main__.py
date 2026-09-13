"""Operator-only portable bundles; no model-facing filesystem tool."""

import argparse
import json
from pathlib import Path

from .operations import export_bundle, restore_bundle, _path, _basename
from .paths import SecResearchPaths


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
    args = parser.parse_args(argv)
    try:
        _path(args.destination)
        if args.operation == "export":
            result = export_bundle(SecResearchPaths.resolve(), args.destination)
        else:
            _path(args.bundle)
            _basename(args.database_name)
            result = restore_bundle(args.bundle, args.destination, database_name=args.database_name)
        print(json.dumps({key: result[key] for key in ("format", "version", "scope", "database", "references")}, sort_keys=True))
        return 0
    except (ValueError, OSError):
        # Never expose paths, SQLite values, source bodies or exception details.
        print(json.dumps({"status": "unavailable", "code": "sec_research_bundle_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
