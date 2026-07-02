#!/usr/bin/env python3
"""Import scored Parquet columns into local ``news_article_scores``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.news_normalized.score_import import (  # noqa: E402
    apply_local_score_import_plan,
    build_local_score_import_plan,
    parquet_files_under,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market-db", required=True, type=Path)
    parser.add_argument("--news-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--expected-fingerprint")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    plan = build_local_score_import_plan(args.market_db, parquet_files_under(args.news_dir))
    if not args.dry_run and not args.expected_fingerprint:
        raise SystemExit("score import apply requires --expected-fingerprint")
    if args.expected_fingerprint and plan.fingerprint != args.expected_fingerprint:
        raise SystemExit("score import fingerprint mismatch")
    payload = plan.to_json_dict()
    if args.dry_run:
        _emit(args.output, payload)
        return 0
    written = apply_local_score_import_plan(args.market_db, plan)
    payload = {**payload, "written": written}
    _emit(args.output, payload)
    return 0


def _emit(path: Path | None, payload: dict) -> None:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if path is None:
        print(text)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
