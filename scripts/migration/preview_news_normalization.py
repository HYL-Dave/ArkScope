#!/usr/bin/env python3
"""Read-only normalized-news migration preview."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.news_normalized.migration import plan_news_normalization  # noqa: E402


def _snapshot(market_db: Path, parquet_paths: list[Path]) -> tuple:
    paths = [market_db, *parquet_paths]
    return tuple(
        (str(path.resolve()), path.stat().st_size, path.stat().st_mtime_ns)
        for path in paths
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market-db", required=True, type=Path)
    parser.add_argument("--parquet-root", required=True, type=Path)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    market_db = args.market_db.resolve()
    parquet_root = args.parquet_root.resolve()
    if not market_db.is_file():
        raise SystemExit(f"market DB does not exist: {market_db}")
    if not parquet_root.is_dir():
        raise SystemExit(f"Parquet root does not exist: {parquet_root}")
    parquet_paths = sorted(parquet_root.rglob("*.parquet"))
    before = _snapshot(market_db, parquet_paths)
    preview = plan_news_normalization(market_db, parquet_paths)
    after = _snapshot(market_db, parquet_paths)
    if before != after:
        raise RuntimeError("news normalization preview inputs changed during read")
    print(json.dumps(preview.to_dict(), sort_keys=True, ensure_ascii=True))
    return 0 if preview.would_apply else 2


if __name__ == "__main__":
    raise SystemExit(main())
