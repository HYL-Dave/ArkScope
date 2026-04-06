#!/usr/bin/env python3
"""
Fill missing LLM scores in training data using nano title-only scores.

Takes existing train/trade CSV pairs and fills llm_sentiment=0 or llm_risk=3
(the default "missing" values) with aggregated nano scores where available.
Produces new CSV files with a `_nanofilled` suffix — originals are untouched.

Usage:
    # Fill a single dataset
    python training/data_prep/fill_missing_scores.py \
        --train training/data_prep/output/train_gpt5mini_high_both.csv

    # Fill all datasets at once
    python training/data_prep/fill_missing_scores.py --all

    # Dry run (show stats only, don't write)
    python training/data_prep/fill_missing_scores.py --all --dry-run
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

# Nano score files (scored from HuggingFace DeepSeek dataset articles by title)
NANO_SENTIMENT = "/mnt/md0/finrl/gpt-5.4-nano/sentiment/sentiment_gpt-5.4-nano_xhigh_by_title.csv"
NANO_RISK = "/mnt/md0/finrl/gpt-5.4-nano/risk/risk_gpt-5.4-nano_xhigh_by_title.csv"

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# Datasets to EXCLUDE from --all filling:
# - deepseek: DeepSeek already scored all articles (including title-only);
#   filling it would erase the very difference we're investigating
# - polygon: completely different data source, nano scores don't apply
EXCLUDE_PATTERNS = ["deepseek", "polygon"]


def load_nano_daily(path, score_col, target_col):
    """Load nano scores → aggregate to daily mean per ticker → round to int."""
    df = pd.read_csv(path, usecols=["Date", "Stock_symbol", score_col], low_memory=False)
    df = df.rename(columns={"Stock_symbol": "tic", score_col: target_col})
    df["Date"] = pd.to_datetime(df["Date"])

    # Drop rows where score is NaN
    df = df.dropna(subset=[target_col])

    # Daily mean per ticker (multiple articles per day)
    daily = df.groupby([df["Date"].dt.date, "tic"])[target_col].mean().reset_index()
    daily.columns = ["date", "tic", target_col]
    daily["date"] = daily["date"].astype(str)
    daily[target_col] = daily[target_col].round().astype(int)

    return daily


def fill_dataset(train_path, nano_sentiment, nano_risk, dry_run=False):
    """Fill missing scores in a train/trade CSV pair."""
    name = os.path.basename(train_path).replace("train_", "").replace(".csv", "")
    print(f"\n{'=' * 60}")
    print(f"  Dataset: {name}")
    print(f"{'=' * 60}")

    train = pd.read_csv(train_path, low_memory=False)
    train["date"] = train["date"].astype(str)

    # Also look for matching trade file
    trade_path = train_path.replace("train_", "trade_")
    trade = None
    if os.path.exists(trade_path):
        trade = pd.read_csv(trade_path, low_memory=False)
        trade["date"] = trade["date"].astype(str)

    for df, label in [(train, "train")] + ([(trade, "trade")] if trade is not None else []):
        # Sentiment: missing = 0
        if "llm_sentiment" in df.columns:
            missing_s = (df["llm_sentiment"] == 0).sum()
            if missing_s > 0:
                merged = df.merge(
                    nano_sentiment, on=["date", "tic"], how="left", suffixes=("", "_nano"),
                )
                fill_mask = (merged["llm_sentiment"] == 0) & merged["llm_sentiment_nano"].notna()
                filled = fill_mask.sum()
                merged.loc[fill_mask, "llm_sentiment"] = merged.loc[fill_mask, "llm_sentiment_nano"].astype(int)
                merged.drop(columns=["llm_sentiment_nano"], inplace=True)

                # Copy back
                df["llm_sentiment"] = merged["llm_sentiment"].values
                still_missing = (df["llm_sentiment"] == 0).sum()
                print(f"  {label} sentiment: {missing_s:,} missing → filled {filled:,}, still missing {still_missing:,}")
            else:
                print(f"  {label} sentiment: no missing rows")

        # Risk: missing = 3 (neutral default) — but 3 is also a valid score
        # Only fill if the original dataset had risk=3 AND there's a nano score
        # We use a heuristic: if ALL risk values for a (date, tic) are exactly 3,
        # it's likely a default fill, not a real score.
        # However, since risk default is 3 and 3 is the most common real score,
        # we only fill rows where sentiment was ALSO missing (=0), indicating
        # no article coverage at all for that day.
        if "llm_risk" in df.columns:
            # Rows where sentiment was originally 0 (no article) AND risk is default 3
            # These are the truly "no data" rows
            no_data_mask = (df["llm_sentiment"] == 0) & (df["llm_risk"] == 3)
            missing_r = no_data_mask.sum()
            if missing_r > 0:
                merged = df.merge(
                    nano_risk, on=["date", "tic"], how="left", suffixes=("", "_nano"),
                )
                fill_mask = no_data_mask & merged["llm_risk_nano"].notna()
                filled = fill_mask.sum()
                merged.loc[fill_mask, "llm_risk"] = merged.loc[fill_mask, "llm_risk_nano"].astype(int)
                merged.drop(columns=["llm_risk_nano"], inplace=True)

                df["llm_risk"] = merged["llm_risk"].values
                still_missing = ((df["llm_sentiment"] == 0) & (df["llm_risk"] == 3)).sum()
                print(f"  {label} risk:      {missing_r:,} no-data → filled {filled:,}, still no-data {still_missing:,}")
            else:
                print(f"  {label} risk:      no missing rows")

    if dry_run:
        print("  [DRY RUN] No files written")
        return

    # Save with _nanofilled suffix
    out_train = os.path.join(OUTPUT_DIR, f"train_{name}_nanofilled.csv")
    train.to_csv(out_train, index=False)
    print(f"  Saved: {out_train}")

    if trade is not None:
        out_trade = os.path.join(OUTPUT_DIR, f"trade_{name}_nanofilled.csv")
        trade.to_csv(out_trade, index=False)
        print(f"  Saved: {out_trade}")


def main():
    parser = argparse.ArgumentParser(
        description="Fill missing LLM scores with nano title-only scores",
    )
    parser.add_argument("--train", help="Path to a single train CSV to fill")
    parser.add_argument("--all", action="store_true", help="Fill all train_*.csv in output dir")
    parser.add_argument("--dry-run", action="store_true", help="Show stats only, don't write files")
    parser.add_argument(
        "--nano-sentiment", default=NANO_SENTIMENT,
        help="Path to nano sentiment scores CSV",
    )
    parser.add_argument(
        "--nano-risk", default=NANO_RISK,
        help="Path to nano risk scores CSV",
    )
    args = parser.parse_args()

    if not args.train and not args.all:
        parser.error("Either --train or --all is required")

    # Load nano scores (once)
    print("Loading nano scores...")
    nano_sent = load_nano_daily(args.nano_sentiment, "sentiment_gpt_5_4_nano", "llm_sentiment_nano")
    nano_risk = load_nano_daily(args.nano_risk, "risk_gpt_5_4_nano", "llm_risk_nano")
    print(f"  Nano sentiment: {len(nano_sent):,} daily (date, tic) pairs")
    print(f"  Nano risk:      {len(nano_risk):,} daily (date, tic) pairs")

    if args.all:
        train_files = sorted(
            os.path.join(OUTPUT_DIR, f)
            for f in os.listdir(OUTPUT_DIR)
            if f.startswith("train_") and f.endswith(".csv")
            and "_nanofilled" not in f
            and not any(pat in f for pat in EXCLUDE_PATTERNS)
        )
        print(f"\nFound {len(train_files)} datasets to fill")
        print(f"  (excluding: {', '.join(EXCLUDE_PATTERNS)})")
        for path in train_files:
            fill_dataset(path, nano_sent, nano_risk, dry_run=args.dry_run)
    else:
        fill_dataset(args.train, nano_sent, nano_risk, dry_run=args.dry_run)

    print(f"\n{'=' * 60}")
    print("  Done. New files have '_nanofilled' suffix.")
    print("  Originals are untouched.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()