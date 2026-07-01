#!/usr/bin/env python3
"""Compatibility wrapper for the normalized IBKR news worker.

Runtime scheduler code must invoke ``python -m src.news_normalized.ibkr_cli``.
This file remains only for manual/backward compatibility during scripts retirement.
Retire it in N9, or earlier once grep confirms no manual/docs/tests path still
requires the old ``scripts/`` entrypoint.
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.news_normalized import ibkr_cli  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    return ibkr_cli.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
