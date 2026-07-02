#!/usr/bin/env python3
"""Operator CLI for the S-G news score PostgreSQL cutover gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.news_normalized.score_cutover import (  # noqa: E402
    apply_news_scores_cutover,
    preview_news_scores_cutover,
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
    preview.add_argument("--pg-dsn", required=True)
    preview.add_argument("--output", required=True, type=Path)

    apply = subparsers.add_parser("apply")
    _add_db_argument(apply)
    apply.add_argument("--pg-dsn", required=True)
    apply.add_argument("--expected-fingerprint", required=True)
    apply.add_argument("--backup", required=True, type=Path)
    apply.add_argument(
        "--confirm-scheduler-paused",
        required=True,
        action="store_true",
        help="Confirm scheduler and manual score/news ingest are paused",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "preview":
        report = preview_news_scores_cutover(_market_db(args), args.pg_dsn)
        _write_json(args.output, report.to_json_dict())
        return 0
    if args.command == "apply":
        result = apply_news_scores_cutover(
            _market_db(args),
            pg_dsn=args.pg_dsn,
            expected_fingerprint=args.expected_fingerprint,
            backup_path=args.backup,
        )
        print(_json_line(result.to_json_dict()))
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


def _add_db_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        "--market-db",
        dest="db",
        type=Path,
        help="Path to market_data.db",
    )


def _market_db(args: argparse.Namespace) -> Path:
    db = getattr(args, "db", None) or args.market_db
    if db is None:
        raise SystemExit("one of --db or --market-db is required")
    return Path(db)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_line(payload) + "\n", encoding="utf-8")


def _json_line(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    raise SystemExit(main())
