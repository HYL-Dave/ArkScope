#!/usr/bin/env python3
"""Operator CLI for the N8a normalized-news PostgreSQL exit gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.news_normalized.cutover import (  # noqa: E402
    begin_news_pg_exit,
    finalize_news_pg_exit,
    preview_news_pg_exit,
    rollback_news_pg_exit,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market-db", required=True, type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    preview = subparsers.add_parser("preview")
    preview.add_argument("--output", required=True, type=Path)

    begin = subparsers.add_parser("begin")
    begin.add_argument("--expected-report", required=True, type=Path)
    begin.add_argument("--backup", required=True, type=Path)
    begin.add_argument(
        "--confirm-scheduler-paused",
        required=True,
        action="store_true",
        help="Confirm scheduler and manual news ingest are paused",
    )

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--run-id", required=True, type=int)
    finalize.add_argument("--validation-json", required=True, type=Path)

    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("--run-id", required=True, type=int)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "preview":
        report = preview_news_pg_exit(args.market_db).to_json_dict()
        _write_json(args.output, report)
        return 0
    if args.command == "begin":
        with open(args.expected_report, encoding="utf-8") as handle:
            expected = json.load(handle)
        result = begin_news_pg_exit(
            args.market_db,
            expected_report=expected,
            backup_path=args.backup,
        )
        print(_json_line(result.to_json_dict()))
        return 0
    if args.command == "finalize":
        result = finalize_news_pg_exit(
            args.market_db,
            run_id=args.run_id,
            validation_json_path=args.validation_json,
        )
        print(_json_line(result.to_json_dict()))
        return 0
    if args.command == "rollback":
        result = rollback_news_pg_exit(args.market_db, run_id=args.run_id)
        print(_json_line(result.to_json_dict()))
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_line(payload) + "\n", encoding="utf-8")


def _json_line(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


if __name__ == "__main__":
    raise SystemExit(main())
