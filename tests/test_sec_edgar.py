#!/usr/bin/env python3
"""
SEC EDGAR API Test Suite

Tests the SEC EDGAR data source implementation for filings and company facts.
No API key required - SEC EDGAR is free and official.
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file for SEC_USER_AGENT
env_path = Path(__file__).parent.parent / 'config' / '.env'
if env_path.exists():
    print(f"[OK] Loaded .env from {env_path}")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                value = value.strip().strip('"').strip("'")
                os.environ[key.strip()] = value


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(test_name: str, passed: bool, details: str = ""):
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {test_name}")
    if details:
        print(f"       {details}")


def run_tests():
    from data_sources.sec_edgar_source import SECEdgarDataSource

    print("\n" + "="*60)
    print("       SEC EDGAR API TEST SUITE")
    print("       MindfulRL-Intraday Project")
    print("       (No API key required - Free & Official)")
    print("="*60)

    results = []

    # Test 1: Initialize
    print_header("1. Initialization")
    sec = SECEdgarDataSource()
    print_result("Initialization", True, f"User-Agent: {sec.user_agent[:30]}...")
    results.append(("Initialization", True))

    # Test 2: Connection Test
    print_header("2. Connection Test")
    try:
        is_valid = sec.validate_credentials()
        if is_valid:
            print_result("API Connection", True, "Successfully connected to SEC EDGAR")
            results.append(("API Connection", True))
        else:
            print_result("API Connection", False, "Connection validation failed")
            results.append(("API Connection", False))
    except Exception as e:
        print_result("API Connection", False, str(e))
        results.append(("API Connection", False))

    # Test 3: CIK Lookup
    print_header("3. CIK Lookup Test")
    test_tickers = ['AAPL', 'MSFT', 'GOOGL']
    cik_results = []

    for ticker in test_tickers:
        cik = sec.get_cik(ticker)
        if cik:
            cik_results.append((ticker, cik))
            print(f"  {ticker}: CIK {cik}")

    if len(cik_results) == len(test_tickers):
        print_result("CIK Lookup", True, f"Found CIK for all {len(test_tickers)} tickers")
        results.append(("CIK Lookup", True))
    else:
        print_result("CIK Lookup", False, f"Found {len(cik_results)}/{len(test_tickers)} CIKs")
        results.append(("CIK Lookup", False))

    # Test 4: Fetch Recent Filings
    print_header("4. Recent Filings Test")
    print(f"\n  Fetching 10-K, 10-Q, 8-K for AAPL (last 365 days)...")

    try:
        filings = sec.fetch_sec_filings(
            tickers=['AAPL'],
            filing_types=['10-K', '10-Q', '8-K'],
            start_date=date.today() - timedelta(days=365),
        )

        if filings:
            print_result("Filings Fetch", True, f"Retrieved {len(filings)} filings")
            print(f"\n  Recent filings:")

            # Count by type
            type_counts = {}
            for f in filings:
                type_counts[f.filing_type] = type_counts.get(f.filing_type, 0) + 1

            for ftype, count in type_counts.items():
                print(f"    {ftype}: {count}")

            print(f"\n  Sample filings:")
            for filing in filings[:5]:
                print(f"    [{filing.filing_date}] {filing.filing_type}: {filing.title}")
            results.append(("Filings Fetch", True))
        else:
            print_result("Filings Fetch", False, "No filings returned")
            results.append(("Filings Fetch", False))
    except Exception as e:
        print_result("Filings Fetch", False, str(e))
        results.append(("Filings Fetch", False))

    # Test 5: Multi-Ticker Filings
    print_header("5. Multi-Ticker Filings Test")
    print(f"\n  Fetching 10-K for ['AAPL', 'MSFT', 'GOOGL'] (last 2 years)...")

    try:
        filings = sec.fetch_sec_filings(
            tickers=['AAPL', 'MSFT', 'GOOGL'],
            filing_types=['10-K'],
            start_date=date.today() - timedelta(days=730),
        )

        if filings:
            # Count by ticker
            ticker_counts = {}
            for f in filings:
                ticker_counts[f.ticker] = ticker_counts.get(f.ticker, 0) + 1

            print_result("Multi-Ticker Filings", True, f"Retrieved {len(filings)} 10-K filings")
            print(f"  By ticker:")
            for ticker, count in ticker_counts.items():
                print(f"    {ticker}: {count}")
            results.append(("Multi-Ticker Filings", True))
        else:
            print_result("Multi-Ticker Filings", False, "No filings returned")
            results.append(("Multi-Ticker Filings", False))
    except Exception as e:
        print_result("Multi-Ticker Filings", False, str(e))
        results.append(("Multi-Ticker Filings", False))

    # Test 6: Company Facts (Structured Financial Data)
    print_header("6. Company Facts Test (XBRL Data)")
    print(f"\n  Fetching structured financial data for AAPL...")

    try:
        facts = sec.fetch_company_facts('AAPL')

        if facts and 'facts' in facts:
            print_result("Company Facts", True, "Retrieved XBRL company facts")

            # Show available taxonomies
            taxonomies = list(facts.get('facts', {}).keys())
            print(f"  Available taxonomies: {', '.join(taxonomies)}")

            # Show sample concepts from us-gaap
            us_gaap = facts.get('facts', {}).get('us-gaap', {})
            if us_gaap:
                concepts = list(us_gaap.keys())[:10]
                print(f"  Sample concepts ({len(us_gaap)} total): {', '.join(concepts[:5])}...")

            results.append(("Company Facts", True))
        else:
            print_result("Company Facts", False, "No facts returned")
            results.append(("Company Facts", False))
    except Exception as e:
        print_result("Company Facts", False, str(e))
        results.append(("Company Facts", False))

    # Test 7: Specific Financial Concept
    print_header("7. Financial Concept Test")
    print(f"\n  Fetching Revenue data for AAPL...")

    try:
        # Try different revenue concept names
        revenue = None
        for concept in ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet']:
            revenue = sec.fetch_company_concept('AAPL', 'us-gaap', concept)
            if revenue and 'units' in revenue:
                break

        if revenue and 'units' in revenue:
            print_result("Financial Concept", True, f"Retrieved {revenue.get('tag', 'Revenue')} data")

            # Show recent values
            usd_values = revenue.get('units', {}).get('USD', [])
            if usd_values:
                recent = sorted(usd_values, key=lambda x: x.get('end', ''), reverse=True)[:5]
                print(f"  Recent values:")
                for val in recent:
                    period = val.get('end', 'N/A')
                    amount = val.get('val', 0) / 1e9  # Convert to billions
                    form = val.get('form', '')
                    print(f"    {period} ({form}): ${amount:.2f}B")

            results.append(("Financial Concept", True))
        else:
            print_result("Financial Concept", False, "No revenue data returned")
            results.append(("Financial Concept", False))
    except Exception as e:
        print_result("Financial Concept", False, str(e))
        results.append(("Financial Concept", False))

    # Test 8: 8-K as News
    print_header("8. 8-K Filings as News Test")
    print(f"\n  Fetching recent 8-K filings (current reports)...")

    try:
        news = sec.fetch_news(['AAPL', 'MSFT'], days_back=90)

        if news:
            print_result("8-K as News", True, f"Retrieved {len(news)} 8-K filings as news")
            print(f"\n  Recent 8-K filings:")
            for article in news[:5]:
                print(f"    [{article.published_date.strftime('%Y-%m-%d')}] {article.title[:50]}...")
            results.append(("8-K as News", True))
        else:
            print_result("8-K as News", False, "No 8-K filings returned")
            results.append(("8-K as News", False))
    except Exception as e:
        print_result("8-K as News", False, str(e))
        results.append(("8-K as News", False))

    # Summary
    print_header("TEST SUMMARY")
    passed = sum(1 for _, p in results if p)
    total = len(results)
    print(f"\n  Passed: {passed}/{total}")

    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")

    if passed == total:
        print("\n  All tests passed! SEC EDGAR integration is ready.")
    else:
        print("\n  Some tests failed. Please check the errors above.")

    # Additional info
    print_header("NOTES")
    print("""
  SEC EDGAR provides:
  - 10-K: Annual reports (comprehensive financial statements)
  - 10-Q: Quarterly reports
  - 8-K:  Current reports (material events, news-like)
  - XBRL: Structured financial data (Revenue, Net Income, etc.)

  Free & Official - No API key required!
  Rate limit: 10 requests/second (be respectful)
    """)

    return results


if __name__ == "__main__":
    run_tests()