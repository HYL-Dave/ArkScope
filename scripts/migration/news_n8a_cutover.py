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
    parser.add_argument(
        "--market-db",
        type=Path,
        help="Backward-compatible global alias for the subcommand --db option",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preview = subparsers.add_parser("preview")
    _add_db_argument(preview)
    preview.add_argument("--output", required=True, type=Path)

    begin = subparsers.add_parser("begin")
    _add_db_argument(begin)
    _add_profile_db_argument(begin)
    begin.add_argument("--expected-report", required=True, type=Path)
    begin.add_argument("--backup", required=True, type=Path)
    begin.add_argument(
        "--confirm-scheduler-paused",
        required=True,
        action="store_true",
        help="Confirm scheduler and manual news ingest are paused",
    )

    finalize = subparsers.add_parser("finalize")
    _add_db_argument(finalize)
    _add_profile_db_argument(finalize)
    finalize.add_argument("--run-id", required=True, type=int)
    finalize.add_argument(
        "--validation-json",
        required=True,
        type=Path,
        help=(
            "JSON with polygon, finnhub, ibkr, projection_parity, and "
            "pg_unreachable all set exactly to 'passed'"
        ),
    )

    rollback = subparsers.add_parser("rollback")
    _add_db_argument(rollback)
    _add_profile_db_argument(rollback)
    rollback.add_argument("--run-id", required=True, type=int)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    market_db = _market_db(args)
    if args.command == "preview":
        report = preview_news_pg_exit(market_db).to_json_dict()
        _write_json(args.output, report)
        return 0
    if args.command == "begin":
        with open(args.expected_report, encoding="utf-8") as handle:
            expected = json.load(handle)
        result = begin_news_pg_exit(
            market_db,
            expected_report=expected,
            backup_path=args.backup,
            profile_db=args.profile_db,
        )
        print(_json_line(result.to_json_dict()))
        return 0
    if args.command == "finalize":
        result = finalize_news_pg_exit(
            market_db,
            run_id=args.run_id,
            validation_json_path=args.validation_json,
            profile_db=args.profile_db,
        )
        print(_json_line(result.to_json_dict()))
        return 0
    if args.command == "rollback":
        result = rollback_news_pg_exit(
            market_db, run_id=args.run_id, profile_db=args.profile_db
        )
        print(_json_line(result.to_json_dict()))
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


def _add_db_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", type=Path, help="Path to market_data.db")


def _add_profile_db_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--profile-db",
        type=Path,
        help="Path to profile_state.db; defaults to data/profile_state.db",
    )


def _market_db(args: argparse.Namespace) -> Path:
    db = getattr(args, "db", None) or args.market_db
    if db is None:
        raise SystemExit("one of --db or --market-db is required")
    return db


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_line(payload) + "\n", encoding="utf-8")


def _json_line(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


if __name__ == "__main__":
    raise SystemExit(main())
