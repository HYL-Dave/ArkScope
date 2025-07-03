#!/usr/bin/env python3
"""
Audit stock news CSVs for time ordering and per-stock daily duplicates.
"""
import os
import glob
import argparse

import pandas as pd


def audit_file(csv_path, date_col, sym_col):
    df = pd.read_csv(csv_path, parse_dates=[date_col], on_bad_lines='warn', engine='python')
    report = []
    # Check monotonic order of date_col (strict increasing or decreasing)
    if not df[date_col].is_monotonic_increasing and not df[date_col].is_monotonic_decreasing:
        report.append((os.path.basename(csv_path), 'order',
                       'Date column not monotonic'))

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
                        help='Directory path containing CSV files to audit')
    parser.add_argument('--date-column', default='Date',
                        help='Name of the date column to check (default: Date)')
    parser.add_argument('--symbol-column', default='Stock_symbol',
                        help='Name of the stock symbol column (default: Stock_symbol)')
    parser.add_argument('--output', default='audit_report.csv',
                        help='CSV file to write the audit report')
    args = parser.parse_args()

    all_reports = []
    files = glob.glob(os.path.join(args.path, '*.csv'))
    for csv_file in sorted(files):
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