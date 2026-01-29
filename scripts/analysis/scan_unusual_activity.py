#!/usr/bin/env python3
"""
Unusual Options Activity Scanner.

This script uses IBKR's market scanners to detect unusual options activity,
similar to what services like Unusual Whales provide.

Scans include:
- High option volume (stocks being heavily traded in options)
- IV gainers (stocks with rapidly increasing implied volatility)
- IV vs Historical (stocks where IV exceeds historical volatility)
- Extreme Put/Call ratios (unusual bullish or bearish bets)

Usage:
    # Run all unusual activity scans
    python scan_unusual_activity.py

    # Run specific scan
    python scan_unusual_activity.py --scan high-volume

    # Filter by price
    python scan_unusual_activity.py --min-price 20 --max-price 500

    # Save results
    python scan_unusual_activity.py --output results/unusual_activity.json

Requirements:
    - IBKR TWS or Gateway running
    - Market data subscription for scanner access
"""

import argparse
import sys
import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import pandas as pd
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from config/.env
load_dotenv(project_root / "config" / ".env")

# Use random client ID to avoid conflicts
import os
os.environ['IBKR_CLIENT_ID'] = str(random.randint(100, 999))

from data_sources import IBKRDataSource

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Available scan types
SCAN_TYPES = {
    'high-volume': {
        'name': 'High Option Volume',
        'description': 'Stocks with unusually high option trading volume',
        'method': 'scan_unusual_option_volume',
    },
    'iv-gainers': {
        'name': 'IV Gainers',
        'description': 'Stocks with biggest implied volatility increases',
        'method': 'scan_iv_gainers',
    },
    'iv-over-hv': {
        'name': 'IV Over Historical',
        'description': 'Stocks where IV is elevated vs historical volatility',
        'method': 'scan_iv_over_historical',
    },
    'high-iv': {
        'name': 'High IV',
        'description': 'Stocks with highest implied volatility',
        'method': 'scan_high_iv_stocks',
    },
    'high-pc-ratio': {
        'name': 'High Put/Call Ratio',
        'description': 'Stocks with high put/call ratio (bearish sentiment)',
        'method': 'scan_high_put_call_ratio',
    },
    'low-pc-ratio': {
        'name': 'Low Put/Call Ratio',
        'description': 'Stocks with low put/call ratio (bullish sentiment)',
        'method': 'scan_low_put_call_ratio',
    },
    'unusual': {
        'name': 'Combined Unusual Activity',
        'description': 'Combines multiple scans to find unusual activity',
        'method': 'find_unusual_activity_candidates',
    },
}


def print_scan_results(results: List, scan_name: str, scan_desc: str):
    """Pretty print scan results."""
    print(f"\n{'='*70}")
    print(f" {scan_name}")
    print(f" {scan_desc}")
    print(f"{'='*70}")

    if not results:
        print("  No results found")
        return

    # Handle different result types
    if hasattr(results[0], 'symbol'):
        # ScannerResult objects
        print(f"\n{'Rank':<6} {'Symbol':<8} {'Type':<5} {'Exchange':<10}")
        print("-" * 35)
        for r in results[:25]:
            print(f"{r.rank:<6} {r.symbol:<8} {r.sec_type:<5} {r.exchange:<10}")
    else:
        # Dict results from find_unusual_activity_candidates
        print(f"\n{'Score':<8} {'Symbol':<8} {'Count':<6} {'Scans Appeared In'}")
        print("-" * 70)
        for r in results[:25]:
            scans = ', '.join([s.replace('_', ' ')[:20] for s in r['scans_appeared'][:3]])
            if len(r['scans_appeared']) > 3:
                scans += f" +{len(r['scans_appeared'])-3} more"
            print(f"{r['score']:<8} {r['symbol']:<8} {r['appearance_count']:<6} {scans}")

    print(f"\nTotal: {len(results)} results")


def run_single_scan(ibkr: IBKRDataSource, scan_type: str, above_price: float) -> List:
    """Run a single scan and return results."""
    scan_info = SCAN_TYPES[scan_type]
    method = getattr(ibkr, scan_info['method'])

    if scan_type == 'unusual':
        return method(above_price=above_price)
    else:
        return method(above_price=above_price)


def results_to_dict(results: List) -> List[Dict]:
    """Convert results to serializable dicts."""
    output = []
    for r in results:
        if hasattr(r, 'symbol'):
            # ScannerResult
            output.append({
                'symbol': r.symbol,
                'rank': r.rank,
                'sec_type': r.sec_type,
                'exchange': r.exchange,
                'con_id': r.con_id,
                'local_symbol': r.local_symbol,
            })
        else:
            # Already a dict
            output.append(r)
    return output


def main():
    parser = argparse.ArgumentParser(
        description='Scan for unusual options activity using IBKR scanners'
    )
    parser.add_argument('--scan', '-s', choices=list(SCAN_TYPES.keys()),
                        help='Specific scan to run (default: all)')
    parser.add_argument('--min-price', type=float, default=5.0,
                        help='Minimum stock price (default: 5.0)')
    parser.add_argument('--location', default='STK.US.MAJOR',
                        help='Market location (default: STK.US.MAJOR)')
    parser.add_argument('--output', '-o', type=str,
                        help='Output file (JSON format)')
    parser.add_argument('--list-scans', action='store_true',
                        help='List available scan types')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # List available scans
    if args.list_scans:
        print("\nAvailable Scan Types:")
        print("=" * 60)
        for key, info in SCAN_TYPES.items():
            print(f"\n  {key}")
            print(f"    Name: {info['name']}")
            print(f"    Description: {info['description']}")
        return

    # Determine which scans to run
    scans_to_run = [args.scan] if args.scan else list(SCAN_TYPES.keys())

    all_results = {}

    try:
        with IBKRDataSource() as ibkr:
            print(f"\nConnected to IBKR. Running {len(scans_to_run)} scan(s)...")
            print(f"Filters: min_price=${args.min_price}, location={args.location}")

            for scan_type in scans_to_run:
                scan_info = SCAN_TYPES[scan_type]

                try:
                    results = run_single_scan(ibkr, scan_type, args.min_price)
                    all_results[scan_type] = results
                    print_scan_results(results, scan_info['name'], scan_info['description'])

                except Exception as e:
                    logger.error(f"Error running {scan_type}: {e}")
                    all_results[scan_type] = []

    except Exception as e:
        logger.error(f"Connection error: {e}")
        sys.exit(1)

    # Save results if output specified
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        output_data = {
            'scan_time': datetime.now().isoformat(),
            'parameters': {
                'min_price': args.min_price,
                'location': args.location,
            },
            'results': {k: results_to_dict(v) for k, v in all_results.items()},
        }

        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        logger.info(f"Results saved to {output_path}")

    # Summary
    print(f"\n{'='*70}")
    print(" SUMMARY")
    print(f"{'='*70}")

    total_unique = set()
    for scan_type, results in all_results.items():
        count = len(results)
        scan_name = SCAN_TYPES[scan_type]['name']
        print(f"  {scan_name}: {count} results")

        # Collect unique symbols
        for r in results:
            if hasattr(r, 'symbol'):
                total_unique.add(r.symbol)
            elif 'symbol' in r:
                total_unique.add(r['symbol'])

    print(f"\n  Unique symbols across all scans: {len(total_unique)}")

    if total_unique:
        # Show most frequent
        from collections import Counter
        symbol_counts = Counter()
        for results in all_results.values():
            for r in results:
                sym = r.symbol if hasattr(r, 'symbol') else r.get('symbol', '')
                if sym:
                    symbol_counts[sym] += 1

        print("\n  Most frequent (appeared in multiple scans):")
        for sym, count in symbol_counts.most_common(10):
            if count > 1:
                print(f"    {sym}: {count} scans")


if __name__ == '__main__':
    main()