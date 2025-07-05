#!/usr/bin/env python3
"""
Compare sentiment scores between two CSV files and output entries with differing scores.
"""
import argparse
import pandas as pd

def main():
    parser = argparse.ArgumentParser(
        description="Compare sentiment score columns between two CSVs and dump differences."
    )
    parser.add_argument(
        "--old", required=True,
        help="Path to the first (old) CSV file containing sentiment scores"
    )
    parser.add_argument(
        "--new", required=True,
        help="Path to the second (new) CSV file containing sentiment scores"
    )
    parser.add_argument(
        "--output", required=True,
        help="Path to output CSV file to write rows with differing scores"
    )
    parser.add_argument(
        "--on", nargs='+', default=None,
        help=(
            "Columns to join on. If omitted, all common columns except the score column are used."
        )
    )
    parser.add_argument(
        "--score-col", default="sentiment_deepseek",
        help="Name of the sentiment score column to compare (default: sentiment_deepseek)"
    )
    args = parser.parse_args()

    # Read input CSVs
    df_old = pd.read_csv(args.old, on_bad_lines='warn', engine='python')
    df_new = pd.read_csv(args.new, on_bad_lines='warn', engine='python')

    # Determine join keys
    if args.on:
        on_cols = args.on
    else:
        common = set(df_old.columns) & set(df_new.columns)
        common.discard(args.score_col)
        on_cols = sorted(common)

    if not on_cols:
        parser.error(
            "No join keys found: please specify --on columns or ensure CSVs share common columns besides the score column"
        )

    # Merge and find differences
    merged = pd.merge(
        df_old, df_new,
        on=on_cols,
        how='inner',
        suffixes=("_old", "_new")
    )
    old_col = f"{args.score_col}_old"
    new_col = f"{args.score_col}_new"
    if old_col not in merged.columns or new_col not in merged.columns:
        parser.error(
            f"Missing score columns in merged data: {old_col}, {new_col}"
        )
    diff = merged[merged[old_col] != merged[new_col]]

    if diff.empty:
        print("No differences in sentiment scores found.")
    else:
        diff.to_csv(args.output, index=False)
        print(
            f"Found {len(diff)} rows with differing scores; written to {args.output}"
        )

if __name__ == "__main__":
    main()