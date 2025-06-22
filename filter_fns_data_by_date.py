#!/usr/bin/env python3
"""
Filter FNSPID raw news CSV by date cutoff (inclusive).

Example:
  python filter_fns_data_by_date.py \
    --input /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news/nasdaq_exteral_data.csv \
    --date-col Date \
    --start-date 2022-11-01 \
    --output nasdaq_exteral_data_after_2022_11.csv
"""
import argparse
import pandas as pd


def main():
    parser = argparse.ArgumentParser(
        description="Filter records in FNSPID raw news by date cutoff."
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to input CSV (FNSPID raw news)"
    )
    parser.add_argument(
        "--date-col", default="Date",
        help="Name of the date column in the input CSV"
    )
    parser.add_argument(
        "--start-date", required=True,
        help="Start date (inclusive) in YYYY-MM-DD format"
    )
    parser.add_argument(
        "--output", required=True,
        help="Path to output filtered CSV"
    )
    args = parser.parse_args()

    df = pd.read_csv(args.input, parse_dates=[args.date_col])
    df_filtered = df[df[args.date_col] >= args.start_date]
    df_filtered.to_csv(args.output, index=False)
    print(f"Filtered {len(df_filtered)} records on or after {args.start_date}, saved to {args.output}")


if __name__ == "__main__":
    main()