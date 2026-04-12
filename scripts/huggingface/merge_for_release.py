#!/usr/bin/env python3
"""
Merge multi-LLM scored data into HuggingFace release format.

Produces 4 parquet files:
  - scores.parquet              — metadata + all score columns (~60 cols)
  - summaries.parquet           — Article + extractive + LLM summaries used for scoring
  - summaries_gpt5_grid.parquet — GPT-5 summary variants (4 reasoning × 3 verbosity)
  - summaries_gpt5mini_grid.parquet — GPT-5-mini summary variants (4R × 3V)

Source: FNSPID / FinRL_DeepSeek articles re-scored by multiple LLMs.
See column_mapping.md for full documentation.

Usage:
    python scripts/huggingface/merge_for_release.py
    python scripts/huggingface/merge_for_release.py --output-dir /path/to/output
    python scripts/huggingface/merge_for_release.py --dry-run
"""

import argparse
import os

import pandas as pd

FINRL_BASE = "/mnt/md0/finrl"
METADATA_COLS = ["Date", "Article_title", "Stock_symbol", "Url", "Publisher", "Author"]
JOIN_KEYS = ["Date", "Article_title", "Stock_symbol"]

# ── Score mapping ──────────────────────────────────────────────
# (relative_path, source_score_col, target_col_name)
# fmt: off
SCORE_MAP = [
    # ── o3 fulltext (no summary, scored from article) ──
    ("o3/sentiment/sentiment_o3_high_4.csv",
     "sentiment_o3", "sentiment_o3_high_fulltext"),
    ("o3/risk/risk_o3_medium_2.csv",
     "risk_o3", "risk_o3_medium_fulltext"),

    # ── o4-mini fulltext ──
    ("o4-mini/sentiment/sentiment_o4_mini_high_1.csv",
     "sentiment_o4_mini", "sentiment_o4mini_high_fulltext"),
    ("o4-mini/risk/risk_o4_mini_medium_2.csv",
     "risk_o4_mini", "risk_o4mini_medium_fulltext"),

    # ── Claude (by gpt5 R=high V=high summary) ──
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

    # ── GPT-5 × gpt5 summary (4 effort levels) ──
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

    # ── GPT-5 × o3 summary (4 effort levels) ──
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

    # ── o3 × o3 summary (3 effort levels) ──
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

    # ── o4-mini × o3 summary (3 effort levels) ──
    ("o4-mini/sentiment/sentiment_o4_mini_high_by_o3_summary.csv",
     "sentiment_o4_mini", "sentiment_o4mini_high_o3sum"),
    ("o4-mini/sentiment/sentiment_o4_mini_medium_by_o3_summary.csv",
     "sentiment_o4_mini", "sentiment_o4mini_medium_o3sum"),
    ("o4-mini/sentiment/sentiment_o4_mini_low_by_o3_summary.csv",
     "sentiment_o4_mini", "sentiment_o4mini_low_o3sum"),
    ("o4-mini/risk/risk_o4_mini_high_by_o3_summary.csv",
     "risk_o4_mini", "risk_o4mini_high_o3sum"),
    ("o4-mini/risk/risk_o4_mini_medium_by_o3_summary.csv",
     "risk_o4_mini", "risk_o4mini_medium_o3sum"),
    ("o4-mini/risk/risk_o4_mini_low_by_o3_summary.csv",
     "risk_o4_mini", "risk_o4mini_low_o3sum"),

    # ── gpt-4.1 (by o3 summary) ──
    ("gpt-4.1/sentiment/sentiment_gpt-4.1_by_o3_summary.csv",
     "sentiment_gpt_4_1", "sentiment_gpt41_o3sum"),
    ("gpt-4.1/risk/risk_gpt-4.1_by_o3_summary.csv",
     "risk_gpt_4_1", "risk_gpt41_o3sum"),

    # ── gpt-4.1-mini × gpt5 summary variants ──
    ("gpt-4.1-mini/sentiment/sentiment_gpt-4.1-mini_by_gpt-5_reason_high_verbosity_high_summary.csv",
     "sentiment_gpt_4_1_mini", "sentiment_gpt41mini_gpt5sum_Rhigh_Vhigh"),
    ("gpt-4.1-mini/sentiment/sentiment_gpt-4.1-mini_by_gpt-5_reason_high_verbosity_medium_summary.csv",
     "sentiment_gpt_4_1_mini", "sentiment_gpt41mini_gpt5sum_Rhigh_Vmed"),
    ("gpt-4.1-mini/sentiment/sentiment_gpt-4.1-mini_by_gpt-5_reason_medium_verbosity_high_summary.csv",
     "sentiment_gpt_4_1_mini", "sentiment_gpt41mini_gpt5sum_Rmed_Vhigh"),
    ("gpt-4.1-mini/sentiment/sentiment_gpt-4.1-mini_by_gpt-5_reason_low_verbosity_high_summary.csv",
     "sentiment_gpt_4_1_mini", "sentiment_gpt41mini_gpt5sum_Rlow_Vhigh"),
    ("gpt-4.1-mini/sentiment/sentiment_gpt-4.1-mini_by_gpt-5_reason_minimal_verbosity_high_summary.csv",
     "sentiment_gpt_4_1_mini", "sentiment_gpt41mini_gpt5sum_Rmin_Vhigh"),
    ("gpt-4.1-mini/risk/risk_gpt-4.1-mini_by_gpt-5_reason_high_verbosity_high_summary.csv",
     "risk_gpt_4_1_mini", "risk_gpt41mini_gpt5sum_Rhigh_Vhigh"),
    ("gpt-4.1-mini/risk/risk_gpt-4.1-mini_by_gpt-5_reason_high_verbosity_medium_summary.csv",
     "risk_gpt_4_1_mini", "risk_gpt41mini_gpt5sum_Rhigh_Vmed"),
    ("gpt-4.1-mini/risk/risk_gpt-4.1-mini_by_gpt-5_reason_medium_verbosity_high_summary.csv",
     "risk_gpt_4_1_mini", "risk_gpt41mini_gpt5sum_Rmed_Vhigh"),
    ("gpt-4.1-mini/risk/risk_gpt-4.1-mini_by_gpt-5_reason_low_verbosity_high_summary.csv",
     "risk_gpt_4_1_mini", "risk_gpt41mini_gpt5sum_Rlow_Vhigh"),
    ("gpt-4.1-mini/risk/risk_gpt-4.1-mini_by_gpt-5_reason_minimal_verbosity_high_summary.csv",
     "risk_gpt_4_1_mini", "risk_gpt41mini_gpt5sum_Rmin_Vhigh"),

    # ── gpt-4.1-mini × o3 summary ──
    ("gpt-4.1-mini/sentiment/sentiment_gpt-4.1-mini_by_o3_summary.csv",
     "sentiment_gpt_4_1_mini", "sentiment_gpt41mini_o3sum"),
    ("gpt-4.1-mini/risk/risk_gpt-4.1-mini_by_o3_summary.csv",
     "risk_gpt_4_1_mini", "risk_gpt41mini_o3sum"),

    # ── gpt-4.1-nano (by o3 summary) ──
    ("gpt-4.1-nano/sentiment/sentiment_gpt-4.1-nano_by_o3_summary.csv",
     "sentiment_gpt_4_1_nano", "sentiment_gpt41nano_o3sum"),
    ("gpt-4.1-nano/risk/risk_gpt-4.1-nano_by_o3_summary.csv",
     "risk_gpt_4_1_nano", "risk_gpt41nano_o3sum"),

    # ── GPT-5-mini (by gpt5 R=high V=high summary) ──
    ("gpt-5-mini/sentiment/sentiment_gpt-5-mini_with_R_high_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv",
     "sentiment_gpt_5_mini", "sentiment_gpt5mini_high_gpt5sum"),
    ("gpt-5-mini/risk/risk_gpt-5-mini_with_R_high_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv",
     "risk_gpt_5_mini", "risk_gpt5mini_high_gpt5sum"),

    # ── GPT-5.4-nano (title only, 100% coverage) ──
    ("gpt-5.4-nano/sentiment/sentiment_gpt-5.4-nano_xhigh_by_title.csv",
     "sentiment_gpt_5_4_nano", "sentiment_nano_title"),
    ("gpt-5.4-nano/risk/risk_gpt-5.4-nano_xhigh_by_title.csv",
     "risk_gpt_5_4_nano", "risk_nano_title"),
]
# fmt: on

# ── Summary grid: reasoning × verbosity variants ──────────────
REASONING_LEVELS = ["high", "medium", "low", "minimal"]
VERBOSITY_LEVELS = ["high", "medium", "low"]

GPT5_SUMMARY_GRID = [
    (f"gpt-5/summary/gpt-5_reason_{r}_verbosity_{v}_news_with_summary.csv",
     "gpt_5_summary", f"gpt5_R{r}_V{v}")
    for r in REASONING_LEVELS for v in VERBOSITY_LEVELS
]  # 12 variants

GPT5MINI_SUMMARY_GRID = [
    (f"gpt-5-mini/summary/gpt-5-mini_reason_{r}_verbosity_{v}_news_with_summary.csv",
     "gpt_5_mini_summary", f"gpt5mini_R{r}_V{v}")
    for r in REASONING_LEVELS for v in VERBOSITY_LEVELS
]  # 12 variants


def load_score_column(rel_path: str, src_col: str, target_col: str) -> pd.Series:
    """Load a single score column, returning a named Series indexed by join keys."""
    path = os.path.join(FINRL_BASE, rel_path)
    df = pd.read_csv(path, usecols=JOIN_KEYS + [src_col], low_memory=False)
    df = df.set_index(JOIN_KEYS)
    return df[src_col].rename(target_col)


def build_scores(dry_run: bool = False) -> pd.DataFrame:
    """Build the merged scores DataFrame."""
    meta_path = os.path.join(
        FINRL_BASE, "claude/sentiment/sentiment_opus_by_gpt5_summary.csv",
    )
    print(f"  Loading metadata from {os.path.basename(meta_path)}...")
    base = pd.read_csv(meta_path, usecols=METADATA_COLS, low_memory=False)
    print(f"  Base: {len(base)} rows")

    if dry_run:
        print(f"\n  Would merge {len(SCORE_MAP)} score columns:")
        for rel_path, src_col, target_col in SCORE_MAP:
            exists = "OK" if os.path.exists(os.path.join(FINRL_BASE, rel_path)) else "MISSING"
            print(f"    {exists}  {target_col:45s} ← {src_col}")
        return base

    base = base.set_index(JOIN_KEYS)
    total = len(SCORE_MAP)
    for i, (rel_path, src_col, target_col) in enumerate(SCORE_MAP, 1):
        abs_path = os.path.join(FINRL_BASE, rel_path)
        if not os.path.exists(abs_path):
            print(f"  [{i}/{total}] MISSING: {rel_path}")
            continue
        series = load_score_column(rel_path, src_col, target_col)
        base = base.join(series, how="left")
        filled = base[target_col].notna().sum()
        print(f"  [{i}/{total}] {target_col:45s} {filled:>6d} ({filled/len(base):.0%})")

    base = base.reset_index()
    return base


def build_summaries(dry_run: bool = False) -> pd.DataFrame:
    """Build the core summaries DataFrame (used for scoring)."""
    meta_path = os.path.join(
        FINRL_BASE, "claude/sentiment/sentiment_opus_by_gpt5_summary.csv",
    )

    if dry_run:
        print("\n  summaries.parquet columns:")
        print("    Article, Lsa_summary, Luhn_summary, Textrank_summary, Lexrank_summary")
        print("    gpt_5_summary (R=high V=high, used for Claude/GPT-5/GPT-5-mini scoring)")
        print("    o3_summary (used for o3/o4-mini/gpt-4.1 scoring)")
        return pd.DataFrame()

    print("  Loading base summaries...")
    base_cols = JOIN_KEYS + [
        "Article", "Lsa_summary", "Luhn_summary",
        "Textrank_summary", "Lexrank_summary", "gpt_5_summary",
    ]
    base = pd.read_csv(meta_path, usecols=base_cols, low_memory=False)
    base = base.set_index(JOIN_KEYS)

    # Add o3_summary
    o3_path = os.path.join(FINRL_BASE, "o3/summary/o3_news_with_summary.csv")
    o3_df = pd.read_csv(o3_path, usecols=JOIN_KEYS + ["o3_summary"], low_memory=False)
    o3_df = o3_df.set_index(JOIN_KEYS)
    base = base.join(o3_df, how="left")

    base = base.reset_index()
    for col in base.columns:
        if col not in JOIN_KEYS:
            filled = base[col].notna().sum()
            print(f"    {col:25s} {filled:>6d}/{len(base)} ({filled/len(base):.0%})")
    return base


def build_summary_grid(
    grid_spec: list,
    label: str,
    dry_run: bool = False,
) -> pd.DataFrame:
    """Build a summary grid DataFrame (reasoning × verbosity variants)."""
    if dry_run:
        print(f"\n  {label}: {len(grid_spec)} variants")
        for rel_path, _, target_col in grid_spec:
            exists = "OK" if os.path.exists(os.path.join(FINRL_BASE, rel_path)) else "MISSING"
            print(f"    {exists}  {target_col}")
        return pd.DataFrame()

    base = None
    total = len(grid_spec)
    for i, (rel_path, src_col, target_col) in enumerate(grid_spec, 1):
        abs_path = os.path.join(FINRL_BASE, rel_path)
        if not os.path.exists(abs_path):
            print(f"  [{i}/{total}] MISSING: {rel_path}")
            continue

        df = pd.read_csv(abs_path, usecols=JOIN_KEYS + [src_col], low_memory=False)
        df = df.rename(columns={src_col: target_col})
        df = df.set_index(JOIN_KEYS)

        if base is None:
            base = df
        else:
            base = base.join(df, how="left")

        filled = base[target_col].notna().sum()
        print(f"  [{i}/{total}] {target_col:25s} {filled:>6d} ({filled/len(base):.0%})")

    if base is not None:
        base = base.reset_index()
    return base


def save_parquet(df: pd.DataFrame, path: str, int8_cols: bool = False):
    """Save DataFrame as parquet, optionally converting score cols to Int8."""
    if int8_cols:
        for col in df.columns:
            if col.startswith(("sentiment_", "risk_")):
                df[col] = df[col].astype("Int8")
    df.to_parquet(path, index=False, engine="pyarrow")
    size_mb = os.path.getsize(path) / 1024 / 1024
    print(f"  Saved: {path} ({size_mb:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(
        description="Merge multi-LLM scores into HuggingFace release format"
    )
    parser.add_argument("--output-dir", default="scripts/huggingface/output")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # 1. Scores
    print("\n=== scores.parquet ===")
    scores = build_scores(dry_run=args.dry_run)
    if not args.dry_run:
        score_cols = [c for c in scores.columns if c.startswith(("sentiment_", "risk_"))]
        sent = [c for c in score_cols if c.startswith("sentiment_")]
        risk = [c for c in score_cols if c.startswith("risk_")]
        print(f"\n  Total: {len(scores)} rows, {len(sent)} sentiment + {len(risk)} risk"
              f" = {len(score_cols)} score columns")
        save_parquet(scores, os.path.join(args.output_dir, "scores.parquet"), int8_cols=True)

    # 2. Core summaries
    print("\n=== summaries.parquet ===")
    summaries = build_summaries(dry_run=args.dry_run)
    if not args.dry_run:
        save_parquet(summaries, os.path.join(args.output_dir, "summaries.parquet"))

    # 3. GPT-5 summary grid
    print("\n=== summaries_gpt5_grid.parquet ===")
    gpt5_grid = build_summary_grid(GPT5_SUMMARY_GRID, "GPT-5 grid", dry_run=args.dry_run)
    if not args.dry_run and gpt5_grid is not None:
        save_parquet(gpt5_grid, os.path.join(args.output_dir, "summaries_gpt5_grid.parquet"))

    # 4. GPT-5-mini summary grid
    print("\n=== summaries_gpt5mini_grid.parquet ===")
    mini_grid = build_summary_grid(GPT5MINI_SUMMARY_GRID, "GPT-5-mini grid", dry_run=args.dry_run)
    if not args.dry_run and mini_grid is not None:
        save_parquet(mini_grid, os.path.join(args.output_dir, "summaries_gpt5mini_grid.parquet"))

    if not args.dry_run:
        print(f"\n  All files saved to: {args.output_dir}")


if __name__ == "__main__":
    main()