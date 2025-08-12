#!/usr/bin/env python3
"""
Summarize token usage from a large CSV in a memory-efficient way.

Features:
- Works for any numeric token column (e.g., 'completion_tokens', 'prompt_tokens').
- Prints total tokens, non-null count, total rows, and mean for non-null rows.
- For rows where the token value is missing, reports if 'Article' and 'Lsa_summary' are empty.

Usage:
  python scripts/token_usage_summary.py --csv /path/to/file.csv \
         --cols completion_tokens prompt_tokens

If --cols is omitted, the script will search for common token columns.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd


def fmt_int(n: int) -> str:
    return f"{n:,}"


def is_empty_series(s: pd.Series) -> pd.Series:
    # Treat NaN or whitespace-only strings as empty
    if s.dtype == object:
        return s.isna() | (s.astype(str).str.strip() == "")
    return s.isna()


def summarize_column(csv_path: Path, col: str, chunksize: int = 200_000) -> None:
    exists = csv_path.exists()
    print(f"CSV: {csv_path}  (exists: {exists})")
    if not exists:
        return

    # Restrict columns for efficiency; include optional columns for empty checks
    candidate_cols = [col]
    optional_cols = []
    for name in ["Article", "Lsa_summary"]:
        optional_cols.append(name)

    # Probe header to see what exists
    header = pd.read_csv(csv_path, nrows=0)
    header_cols = list(header.columns)
    if col not in header_cols:
        print(f"- Column not found: '{col}'. Available columns: {header_cols}")
        return

    usecols = [c for c in [col, *optional_cols] if c in header_cols]

    total_rows = 0
    nonnull = 0
    total_tokens = 0

    missing_rows = 0
    missing_article_empty = 0
    missing_lsa_empty = 0
    missing_both_empty = 0

    for chunk in pd.read_csv(csv_path, usecols=usecols, chunksize=chunksize):
        total_rows += len(chunk)

        # Token column aggregation
        s = pd.to_numeric(chunk[col], errors="coerce")
        nonnull += int(s.notna().sum())
        total_tokens += int(s.fillna(0).sum())

        # Missing-value diagnostics
        m = s.isna()
        if m.any():
            missing_rows += int(m.sum())

            # Check Article emptiness if present
            if "Article" in chunk.columns:
                art_empty = is_empty_series(chunk["Article"]) if "Article" in chunk.columns else None
            else:
                art_empty = None

            # Check Lsa_summary emptiness if present
            if "Lsa_summary" in chunk.columns:
                lsa_empty = is_empty_series(chunk["Lsa_summary"]) if "Lsa_summary" in chunk.columns else None
            else:
                lsa_empty = None

            if art_empty is not None:
                missing_article_empty += int((m & art_empty).sum())
            if lsa_empty is not None:
                missing_lsa_empty += int((m & lsa_empty).sum())
            if art_empty is not None and lsa_empty is not None:
                missing_both_empty += int((m & art_empty & lsa_empty).sum())

    mean_tokens = (total_tokens / nonnull) if nonnull else 0.0

    print(f"- 欄位名稱: '{col}'")
    print(f"- 總 {col}: {fmt_int(total_tokens)}")
    print(f"- 有效筆數: {fmt_int(nonnull)} / 總筆數: {fmt_int(total_rows)}（其餘為缺值）")
    print(f"- 平均每筆 {col}（有效筆）: {mean_tokens:.1f}")

    # Missing diagnostics
    print("- 缺值筆數: " + fmt_int(missing_rows))
    if "Article" in usecols:
        print("  - 缺值中 Article 為空: " + fmt_int(missing_article_empty))
    else:
        print("  - 欄位 'Article' 不存在，無法檢查")
    if "Lsa_summary" in usecols:
        print("  - 缺值中 Lsa_summary 為空: " + fmt_int(missing_lsa_empty))
    else:
        print("  - 欄位 'Lsa_summary' 不存在，無法檢查")
    if "Article" in usecols and "Lsa_summary" in usecols:
        print("  - 缺值中 兩者皆空: " + fmt_int(missing_both_empty))


def autodetect_cols(csv_path: Path) -> List[str]:
    header = pd.read_csv(csv_path, nrows=0)
    cols = list(header.columns)
    preferred = []
    for name in ["completion_tokens", "prompt_tokens"]:
        if name in cols:
            preferred.append(name)
    # Fallback: any column containing both 'token' and 'completion' or 'prompt'
    if not preferred:
        for c in cols:
            lc = c.lower()
            if "token" in lc and ("completion" in lc or "prompt" in lc):
                preferred.append(c)
    return preferred


def main(argv: Optional[Iterable[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Summarize token usage from CSV")
    ap.add_argument("--csv", required=True, help="Path to the CSV file")
    ap.add_argument(
        "--cols",
        nargs="*",
        help="Token columns to summarize (e.g., completion_tokens prompt_tokens)"
    )
    ap.add_argument(
        "--chunksize",
        type=int,
        default=200_000,
        help="Chunk size for reading the CSV (default: 200000)")
    args = ap.parse_args(argv)

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        return

    cols = args.cols or autodetect_cols(csv_path)
    if not cols:
        print("No token columns detected. Please specify with --cols.")
        return

    for col in cols:
        summarize_column(csv_path, col, chunksize=args.chunksize)
        print("")


if __name__ == "__main__":
    main()

