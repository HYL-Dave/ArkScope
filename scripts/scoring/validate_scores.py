#!/usr/bin/env python3
"""
Validate a sentiment-scored CSV for completeness and correctness.
Checks that required columns exist, all rows have sentiment scores,
and scores are integers in the expected range (1-5).
"""
import sys
import argparse

import pandas as pd


def main():
    parser = argparse.ArgumentParser(
        description="Validate sentiment CSV output"
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to sentiment CSV to validate"
    )
    parser.add_argument(
        "--symbol-column", default="symbol",
        help="Name of the column for stock symbol in CSV"
    )
    parser.add_argument(
        "--text-column", default="headline",
        help="Name of the column for text/summary in CSV"
    )
    parser.add_argument(
        "--date-column", default=None,
        help="Name of the column for date in CSV (optional)"
    )
    parser.add_argument(
        "--sentiment-column", default="sentiment_deepseek",
        help="Name of the sentiment score column in CSV"
    )
    args = parser.parse_args()

    try:
        df = pd.read_csv(args.input)
    except Exception as e:
        print(f"ERROR: Failed to read CSV '{args.input}': {e}", file=sys.stderr)
        sys.exit(1)

    # Check required columns
    required = [args.symbol_column, args.text_column, args.sentiment_column]
    if args.date_column:
        required.append(args.date_column)
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"ERROR: Missing required columns: {missing}", file=sys.stderr)
        sys.exit(1)

    total = len(df)
    print(f"Total rows: {total}")

    # Validate sentiment scores
    scores = pd.to_numeric(df[args.sentiment_column], errors="coerce")
    missing_scores = scores.isna().sum()
    invalid = df.loc[~scores.isna() & ~scores.isin([1, 2, 3, 4, 5]), args.sentiment_column]
    invalid_count = len(invalid)
    print(f"Missing sentiment scores: {missing_scores}")
    print(f"Invalid sentiment scores (not in 1-5): {invalid_count}")
    if invalid_count:
        print("Examples of invalid scores:")
        print(invalid.head().to_string(index=False))

    if missing_scores or invalid_count:
        sys.exit(1)
    print("All sentiment scores present and valid (1-5). CSV looks good.")


if __name__ == "__main__":
    main()