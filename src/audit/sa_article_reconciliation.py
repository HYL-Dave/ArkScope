from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from src.market_data_admin import resolve_market_db_path
from src.tools.backends.sa_capture_backend import SACaptureBackend


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--preview-legacy", action="store_true")
    parser.add_argument("--queue", action="store_true")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args(argv)
    backend = SACaptureBackend(
        sa_db=args.db,
        market_db=resolve_market_db_path(),
        base_path=PROJECT_ROOT,
    )
    payload = (
        backend.preview_sa_legacy_article_links(limit=args.limit)
        if args.preview_legacy
        else backend.query_sa_article_review_queue(limit=args.limit)
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
