#!/usr/bin/env python3
"""
Merge multi-LLM scored data into HuggingFace release format.

Produces two parquet files:
  - scores.parquet   — 6 metadata + 40 score columns
  - summaries.parquet — 3 join keys + Article + 6 summary columns

Source: FNSPID / FinRL_DeepSeek articles re-scored by multiple LLMs.
See column_mapping.md for full documentation.

Usage:
    python scripts/huggingface/merge_for_release.py
    python scripts/huggingface/merge_for_release.py --output-dir /path/to/output
    python scripts/huggingface/merge_for_release.py --dry-run
"""

import argparse
import os
import sys

import pandas as pd

# ── File → column mapping ──────────────────────────────────────
# Each entry: (source_file, original_score_col, target_col)
# All paths relative to FINRL_BASE

FINRL_BASE = "/mnt/md0/finrl"

METADATA_COLS = ["Date", "Article_title", "Stock_symbol", "Url", "Publisher", "Author"]
JOIN_KEYS = ["Date", "Article_title", "Stock_symbol"]

# fmt: off
SCORE_MAP = [
    # ── o3 fulltext ──
    ("o3/sentiment/sentiment_o3_high_4.csv",
     "sentiment_o3", "sentiment_o3_high_fulltext"),
    ("o3/risk/risk_o3_medium_2.csv",
     "risk_o3", "risk_o3_medium_fulltext"),

    # ── Claude (gpt5 summary) ──
    ("claude/sentiment/sentiment_opus_by_gpt5_summary.csv",
     "sentiment_opus", "sentiment_opus_gpt5sum"),
    ("claude/risk/risk_opus_by_gpt5_summary.csv",
     "risk_opus", "risk_opus_gpt5sum"),
    ("claude/sentiment/sentiment_sonnet_by_gpt5_summary.csv",
     "sentiment_sonnet", "sentiment_sonnet_gpt5sum"),
    ("claude/risk/risk_sonnet_by_gpt5_summary.csv",
     "risk_sonnet", "risk_sonnet_gpt5sum"),
    ("claude/sentiment/sentiment_haiku_by_gpt5_summary.csv",
     "sentiment_haiku", "sentiment_haiku_gpt5sum"),
    ("claude/risk/risk_haiku_by_gpt5_summary.csv",
     "risk_haiku", "risk_haiku_gpt5sum"),

    # ── GPT-5 × gpt5 summary (4 efforts) ──
    ("gpt-5/sentiment/sentiment_gpt-5_R_high_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv",
     "sentiment_gpt_5", "sentiment_gpt5_high_gpt5sum"),
    ("gpt-5/sentiment/sentiment_gpt-5_R_medium_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv",
     "sentiment_gpt_5", "sentiment_gpt5_medium_gpt5sum"),
    ("gpt-5/sentiment/sentiment_gpt-5_R_low_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv",
     "sentiment_gpt_5", "sentiment_gpt5_low_gpt5sum"),
    ("gpt-5/sentiment/sentiment_gpt-5_R_minimal_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv",
     "sentiment_gpt_5", "sentiment_gpt5_minimal_gpt5sum"),
    ("gpt-5/risk/risk_gpt-5_R_high_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv",
     "risk_gpt_5", "risk_gpt5_high_gpt5sum"),
    ("gpt-5/risk/risk_gpt-5_R_medium_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv",
     "risk_gpt_5", "risk_gpt5_medium_gpt5sum"),
    ("gpt-5/risk/risk_gpt-5_R_low_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv",
     "risk_gpt_5", "risk_gpt5_low_gpt5sum"),
    ("gpt-5/risk/risk_gpt-5_R_minimal_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv",
     "risk_gpt_5", "risk_gpt5_minimal_gpt5sum"),

    # ── GPT-5 × o3 summary (4 efforts) ──
    ("gpt-5/sentiment/sentiment_gpt-5_high_by_o3_summary.csv",
     "sentiment_gpt_5", "sentiment_gpt5_high_o3sum"),
    ("gpt-5/sentiment/sentiment_gpt-5_medium_by_o3_summary.csv",
     "sentiment_gpt_5", "sentiment_gpt5_medium_o3sum"),
    ("gpt-5/sentiment/sentiment_gpt-5_low_by_o3_summary.csv",
     "sentiment_gpt_5", "sentiment_gpt5_low_o3sum"),
    ("gpt-5/sentiment/sentiment_gpt-5_minimal_by_o3_summary.csv",
     "sentiment_gpt_5", "sentiment_gpt5_minimal_o3sum"),
    ("gpt-5/risk/risk_gpt-5_high_by_o3_summary.csv",
     "risk_gpt_5", "risk_gpt5_high_o3sum"),
    ("gpt-5/risk/risk_gpt-5_medium_by_o3_summary.csv",
     "risk_gpt_5", "risk_gpt5_medium_o3sum"),
    ("gpt-5/risk/risk_gpt-5_low_by_o3_summary.csv",
     "risk_gpt_5", "risk_gpt5_low_o3sum"),
    ("gpt-5/risk/risk_gpt-5_minimal_by_o3_summary.csv",
     "risk_gpt_5", "risk_gpt5_minimal_o3sum"),

    # ── o3 × o3 summary (3 efforts) ──
    ("o3/sentiment/sentiment_o3_high_by_o3_summary.csv",
     "sentiment_o3", "sentiment_o3_high_o3sum"),
    ("o3/sentiment/sentiment_o3_medium_by_o3_summary.csv",
     "sentiment_o3", "sentiment_o3_medium_o3sum"),
    ("o3/sentiment/sentiment_o3_low_by_o3_summary.csv",
     "sentiment_o3", "sentiment_o3_low_o3sum"),
    ("o3/risk/risk_o3_high_by_o3_summary.csv",
     "risk_o3", "risk_o3_high_o3sum"),
    ("o3/risk/risk_o3_medium_by_o3_summary.csv",
     "risk_o3", "risk_o3_medium_o3sum"),
    ("o3/risk/risk_o3_low_by_o3_summary.csv",
     "risk_o3", "risk_o3_low_o3sum"),

    # ── o3 × gpt5 summary ──
    ("o3/sentiment/sentiment_o3_high_by_gpt-5_reason_high_verbosity_high.csv",
     "sentiment_o3", "sentiment_o3_high_gpt5sum"),
    ("o3/risk/risk_o3_high_by_gpt-5_reason_high_verbosity_high.csv",
     "risk_o3", "risk_o3_high_gpt5sum"),

    # ── GPT-5-mini (gpt5 summary) ──
    ("gpt-5-mini/sentiment/sentiment_gpt-5-mini_with_R_high_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv",
     "sentiment_gpt_5_mini", "sentiment_gpt5mini_high_gpt5sum"),
    ("gpt-5-mini/risk/risk_gpt-5-mini_with_R_high_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv",
     "risk_gpt_5_mini", "risk_gpt5mini_high_gpt5sum"),

    # ── GPT-5.4-nano (title only) ──
    ("gpt-5.4-nano/sentiment/sentiment_gpt-5.4-nano_xhigh_by_title.csv",
     "sentiment_gpt_5_4_nano", "sentiment_nano_title"),
    ("gpt-5.4-nano/risk/risk_gpt-5.4-nano_xhigh_by_title.csv",
     "risk_gpt_5_4_nano", "risk_nano_title"),
]
# fmt: on

# Summaries: which files contain which summary columns
# (file, summary_col) — we pick from the first file that has each column
SUMMARY_SOURCES = {
    "Article": "claude/sentiment/sentiment_opus_by_gpt5_summary.csv",
    "Lsa_summary": "claude/sentiment/sentiment_opus_by_gpt5_summary.csv",
    "Luhn_summary": "claude/sentiment/sentiment_opus_by_gpt5_summary.csv",
    "Textrank_summary": "claude/sentiment/sentiment_opus_by_gpt5_summary.csv",
    "Lexrank_summary": "claude/sentiment/sentiment_opus_by_gpt5_summary.csv",
    "gpt_5_summary": "claude/sentiment/sentiment_opus_by_gpt5_summary.csv",
    "o3_summary": "o3/sentiment/sentiment_o3_high_by_o3_summary.csv",
}


def load_score_column(rel_path: str, src_col: str, target_col: str) -> pd.Series:
    """Load a single score column from a CSV, returning a named Series."""
    abs_path = os.path.join(FINRL_BASE, rel_path)
    df = pd.read_csv(abs_path, usecols=JOIN_KEYS + [src_col], low_memory=False)
    df = df.set_index(JOIN_KEYS)
    series = df[src_col].rename(target_col)
    return series


def build_scores(dry_run: bool = False) -> pd.DataFrame:
    """Build the merged scores DataFrame."""
    # Load metadata from a representative file (Claude Opus has all rows)
    meta_path = os.path.join(
        FINRL_BASE,
        "claude/sentiment/sentiment_opus_by_gpt5_summary.csv",
    )
    print(f"  Loading metadata from {meta_path}...")
    base = pd.read_csv(meta_path, usecols=METADATA_COLS, low_memory=False)
    print(f"  Base: {len(base)} rows")

    if dry_run:
        print(f"\n  Would merge {len(SCORE_MAP)} score columns:")
        for rel_path, src_col, target_col in SCORE_MAP:
            abs_path = os.path.join(FINRL_BASE, rel_path)
            exists = "OK" if os.path.exists(abs_path) else "MISSING"
            print(f"    {exists}  {target_col:40s} ← {src_col} from {rel_path}")
        return base

    # Set index for joining
    base = base.set_index(JOIN_KEYS)

    # Merge each score column
    total = len(SCORE_MAP)
    for i, (rel_path, src_col, target_col) in enumerate(SCORE_MAP, 1):
        abs_path = os.path.join(FINRL_BASE, rel_path)
        if not os.path.exists(abs_path):
            print(f"  [{i}/{total}] MISSING: {rel_path}")
            continue

        series = load_score_column(rel_path, src_col, target_col)
        base = base.join(series, how="left")
        filled = base[target_col].notna().sum()
        print(f"  [{i}/{total}] {target_col:40s} {filled:>6d} filled ({filled/len(base):.1%})")

    base = base.reset_index()
    return base


def build_summaries(dry_run: bool = False) -> pd.DataFrame:
    """Build the summaries DataFrame."""
    # Load join keys from the same base
    meta_path = os.path.join(
        FINRL_BASE,
        "claude/sentiment/sentiment_opus_by_gpt5_summary.csv",
    )
    cols_needed = JOIN_KEYS + list(SUMMARY_SOURCES.keys())

    if dry_run:
        print(f"\n  Would build summaries with columns: {list(SUMMARY_SOURCES.keys())}")
        for col, rel_path in SUMMARY_SOURCES.items():
            abs_path = os.path.join(FINRL_BASE, rel_path)
            exists = "OK" if os.path.exists(abs_path) else "MISSING"
            print(f"    {exists}  {col:20s} ← {rel_path}")
        return pd.DataFrame()

    # Most summary columns are in the same file (Claude Opus)
    # Only o3_summary needs a separate source
    print("  Loading summaries...")

    # Load base with most columns
    base_cols_available = JOIN_KEYS + [
        "Article", "Lsa_summary", "Luhn_summary",
        "Textrank_summary", "Lexrank_summary", "gpt_5_summary",
    ]
    base = pd.read_csv(meta_path, usecols=base_cols_available, low_memory=False)
    base = base.set_index(JOIN_KEYS)

    # Add o3_summary from separate file
    o3_path = os.path.join(FINRL_BASE, SUMMARY_SOURCES["o3_summary"])
    o3_df = pd.read_csv(o3_path, usecols=JOIN_KEYS + ["o3_summary"], low_memory=False)
    o3_df = o3_df.set_index(JOIN_KEYS)
    base = base.join(o3_df, how="left")

    base = base.reset_index()

    for col in ["Article"] + [c for c in base.columns if "summary" in c.lower()]:
        filled = base[col].notna().sum()
        print(f"    {col:20s} {filled:>6d}/{len(base)} ({filled/len(base):.1%})")

    return base


def main():
    parser = argparse.ArgumentParser(
        description="Merge multi-LLM scores into HuggingFace release format"
    )
    parser.add_argument(
        "--output-dir", default="scripts/huggingface/output",
        help="Output directory for parquet files",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be merged without reading data",
    )
    parser.add_argument(
        "--scores-only", action="store_true",
        help="Only build scores.parquet",
    )
    parser.add_argument(
        "--summaries-only", action="store_true",
        help="Only build summaries.parquet",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    build_both = not args.scores_only and not args.summaries_only

    # ── Scores ──
    if build_both or args.scores_only:
        print("\n=== Building scores.parquet ===")
        scores = build_scores(dry_run=args.dry_run)

        if not args.dry_run:
            score_cols = [c for c in scores.columns if c not in METADATA_COLS]
            sent_cols = [c for c in score_cols if c.startswith("sentiment_")]
            risk_cols = [c for c in score_cols if c.startswith("risk_")]
            print(f"\n  Total: {len(scores)} rows, {len(sent_cols)} sentiment + "
                  f"{len(risk_cols)} risk = {len(score_cols)} score columns")

            # Convert score columns to nullable Int8 (1-5 scale, saves space)
            for col in score_cols:
                scores[col] = scores[col].astype("Int8")

            out_path = os.path.join(args.output_dir, "scores.parquet")
            scores.to_parquet(out_path, index=False, engine="pyarrow")
            size_mb = os.path.getsize(out_path) / 1024 / 1024
            print(f"  Saved: {out_path} ({size_mb:.1f} MB)")

    # ── Summaries ──
    if build_both or args.summaries_only:
        print("\n=== Building summaries.parquet ===")
        summaries = build_summaries(dry_run=args.dry_run)

        if not args.dry_run:
            out_path = os.path.join(args.output_dir, "summaries.parquet")
            summaries.to_parquet(out_path, index=False, engine="pyarrow")
            size_mb = os.path.getsize(out_path) / 1024 / 1024
            print(f"  Saved: {out_path} ({size_mb:.1f} MB)")

    if not args.dry_run:
        print(f"\n  Output directory: {args.output_dir}")
        print("  Done!")


if __name__ == "__main__":
    main()