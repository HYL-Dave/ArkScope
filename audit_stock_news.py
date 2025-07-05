#!/usr/bin/env python3
"""
Audit stock news CSVs for time ordering and per-stock daily duplicates.
"""
import os
import glob
import argparse

import pandas as pd


def audit_file(csv_path, date_col, sym_col):
    # Read CSV, treating date column as string first to handle malformed lines robustly
    df = pd.read_csv(csv_path, on_bad_lines='warn', engine='python', dtype={date_col: str})
    report = []
    # Convert date column to datetime, coercing errors
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    # Report rows where date parsing failed
    bad_dates = df[df[date_col].isna()]
    for idx, row in bad_dates.iterrows():
        report.append((os.path.basename(csv_path), 'bad_date',
                       f"Invalid date: {row.get(date_col, row[date_col])} at row {idx}"))
    # Only keep rows with valid dates
    df = df.dropna(subset=[date_col])

    # Check monotonic order of date_col (strict increasing or decreasing)
    inc = df[date_col].is_monotonic_increasing
    dec = df[date_col].is_monotonic_decreasing
    if not inc and not dec:
        report.append((os.path.basename(csv_path), 'order', 'Date column not monotonic'))
        # report specific violations (skip equal timestamps)
        for i in range(1, len(df)):
            prev = df[date_col].iloc[i-1]
            curr = df[date_col].iloc[i]
            if curr == prev:
                continue
            if curr < prev:
                report.append((os.path.basename(csv_path), 'order_violation',
                               f'{date_col} at row {df.index[i]} ({curr}) < row {df.index[i-1]} ({prev})'))
            else:
                report.append((os.path.basename(csv_path), 'order_violation',
                               f'{date_col} at row {df.index[i]} ({curr}) > row {df.index[i-1]} ({prev})'))

    # Check duplicates: group by symbol and calendar date
    df['__date'] = df[date_col].dt.date
    dup = df.groupby([sym_col, '__date']).size().reset_index(name='count')
    dup = dup[dup['count'] > 1]
    for _, row in dup.iterrows():
        report.append((os.path.basename(csv_path), 'duplicate',
                       f"{sym_col}={row[sym_col]} date={row['__date']} count={row['count']}"))
    return report


def main():
    parser = argparse.ArgumentParser(
        description='Audit stock news CSVs for date order and daily duplicates.'
    )
    parser.add_argument('--path', required=True,
                        help='Path to a CSV file or directory containing CSVs to audit')
    parser.add_argument('--date-column', default='Date',
                        help='Name of the date column to check (default: Date)')
    parser.add_argument('--symbol-column', default='Stock_symbol',
                        help='Name of the stock symbol column (default: Stock_symbol)')
    parser.add_argument('--output', default='audit_report.csv',
                        help='CSV file to write the audit report')
    args = parser.parse_args()

    all_reports = []
    # Determine files to audit: single file or all CSVs in directory
    if os.path.isfile(args.path):
        csv_files = [args.path]
    else:
        csv_files = glob.glob(os.path.join(args.path, '*.csv'))
    for csv_file in sorted(csv_files):
        rep = audit_file(csv_file, args.date_column, args.symbol_column)
        all_reports.extend(rep)

    if all_reports:
        out_df = pd.DataFrame(all_reports, columns=['file', 'issue', 'detail'])
        out_df.to_csv(args.output, index=False)
        print(f'Audit report written to {args.output} ({len(out_df)} issues)')
    else:
        print('No issues found in any files.')


if __name__ == '__main__':
    main()