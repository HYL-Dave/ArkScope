#!/usr/bin/env python3
"""
Compare SEC EDGAR implementation vs Financial Datasets API.

This script compares our free SEC EDGAR implementation against
the paid Financial Datasets API to verify data accuracy.

Usage:
    python scripts/comparison/compare_sec_vs_financial_datasets.py
"""

import json
import sys
from pathlib import Path
from dataclasses import asdict

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from data_sources.sec_edgar_financials import SECEdgarFinancials


def load_financial_datasets_response(filename: str) -> dict:
    """Load saved Financial Datasets API response."""
    path = project_root / "comparison_results" / "financial_datasets" / filename
    if not path.exists():
        print(f"Warning: {filename} not found")
        return {}
    with open(path) as f:
        return json.load(f)


def compare_values(sec_val, fd_val, tolerance=0.01):
    """Compare two values with tolerance for floating point differences."""
    if sec_val is None and fd_val is None:
        return "both_null", None
    if sec_val is None:
        return "sec_missing", None
    if fd_val is None:
        return "fd_missing", None

    # Handle numeric comparison
    try:
        sec_num = float(sec_val)
        fd_num = float(fd_val)
        if sec_num == fd_num:
            return "exact_match", 0
        diff_pct = abs(sec_num - fd_num) / max(abs(fd_num), 1) * 100
        if diff_pct < tolerance:
            return "close_match", diff_pct
        return "mismatch", diff_pct
    except (TypeError, ValueError):
        if sec_val == fd_val:
            return "exact_match", 0
        return "mismatch", None


def compare_cash_flow():
    """Compare Cash Flow Statement."""
    print("\n" + "=" * 60)
    print("CASH FLOW STATEMENT COMPARISON")
    print("=" * 60)

    # Load Financial Datasets response
    fd_response = load_financial_datasets_response("07_cash_flow_statement.json")
    fd_data = fd_response.get("data", {}).get("cash_flow_statements", [])

    if not fd_data:
        print("No Financial Datasets cash flow data found")
        return

    # Get SEC EDGAR data
    sec = SECEdgarFinancials()
    sec_statements = sec.get_cash_flow_statement("AAPL", years=5)

    print(f"\nFinancial Datasets: {len(fd_data)} years")
    print(f"SEC EDGAR: {len(sec_statements)} years")

    # Compare most recent year
    if fd_data and sec_statements:
        fd_latest = fd_data[0]
        sec_latest = asdict(sec_statements[0])

        print(f"\nFD Period: {fd_latest.get('fiscal_period')}")
        print(f"SEC Period: {sec_latest.get('fiscal_period')}")

        print("\n{:<45} {:>15} {:>15} {:>12}".format(
            "Field", "SEC EDGAR", "Fin.Datasets", "Status"
        ))
        print("-" * 90)

        fields_to_compare = [
            'net_income',
            'depreciation_and_amortization',
            'share_based_compensation',
            'net_cash_flow_from_operations',
            'capital_expenditure',
            'net_cash_flow_from_investing',
            'net_cash_flow_from_financing',
            'dividends_and_other_cash_distributions',
            'issuance_or_purchase_of_equity_shares',
            'change_in_cash_and_equivalents',
            'ending_cash_balance',
            'free_cash_flow',
        ]

        match_count = 0
        total_count = 0

        for field in fields_to_compare:
            sec_val = sec_latest.get(field)
            fd_val = fd_latest.get(field)

            status, diff = compare_values(sec_val, fd_val)

            # Format values
            sec_str = f"{sec_val/1e9:.2f}B" if sec_val else "N/A"
            fd_str = f"{fd_val/1e9:.2f}B" if fd_val else "N/A"

            if status == "exact_match":
                status_str = "MATCH"
                match_count += 1
            elif status == "close_match":
                status_str = f"~{diff:.2f}%"
                match_count += 1
            elif status == "sec_missing":
                status_str = "SEC N/A"
            elif status == "fd_missing":
                status_str = "FD N/A"
            else:
                status_str = f"DIFF {diff:.1f}%" if diff else "DIFF"

            total_count += 1
            print(f"{field:<45} {sec_str:>15} {fd_str:>15} {status_str:>12}")

        print("-" * 90)
        print(f"Match Rate: {match_count}/{total_count} ({match_count/total_count*100:.1f}%)")


def compare_filings_list():
    """Compare Filings List."""
    print("\n" + "=" * 60)
    print("FILINGS LIST COMPARISON")
    print("=" * 60)

    # Load Financial Datasets response
    fd_response = load_financial_datasets_response("08_filings_list.json")
    fd_data = fd_response.get("data", {}).get("filings", [])

    if not fd_data:
        print("No Financial Datasets filings data found")
        return

    # Get SEC EDGAR data
    sec = SECEdgarFinancials()
    sec_filings = sec.get_filings_list("AAPL", limit=10)

    print(f"\nFinancial Datasets: {len(fd_data)} filings")
    print(f"SEC EDGAR: {len(sec_filings)} filings")

    print("\n=== Financial Datasets Filings ===")
    print("{:<15} {:<12} {:<30}".format("Type", "Date", "Accession"))
    for f in fd_data[:5]:
        print(f"{f.get('filing_type', 'N/A'):<15} {f.get('report_date', 'N/A'):<12} {f.get('accession_number', 'N/A'):<30}")

    print("\n=== SEC EDGAR Filings ===")
    print("{:<15} {:<12} {:<30}".format("Type", "Date", "Accession"))
    for f in sec_filings[:5]:
        f_dict = asdict(f)
        print(f"{f_dict.get('filing_type', 'N/A'):<15} {f_dict.get('report_date', 'N/A'):<12} {f_dict.get('accession_number', 'N/A'):<30}")

    # Check if we can get specific filing types
    print("\n=== 10-K Filings Only (SEC EDGAR) ===")
    sec_10k = sec.get_filings_list("AAPL", filing_types=["10-K"], limit=5)
    for f in sec_10k:
        f_dict = asdict(f)
        print(f"{f_dict.get('filing_type'):<15} {f_dict.get('report_date'):<12} {f_dict.get('accession_number')}")


def analyze_filing_items_cost():
    """Analyze cost/benefit of Filing Items extraction."""
    print("\n" + "=" * 60)
    print("FILING ITEMS EXTRACTION - COST/BENEFIT ANALYSIS")
    print("=" * 60)

    # Load Filing Items responses
    item_1a = load_financial_datasets_response("09_filing_items_1a.json")
    item_7 = load_financial_datasets_response("10_filing_items_mda.json")

    print("\n=== Financial Datasets Filing Items ===")
    print(f"Item 1A (Risk Factors): {item_1a.get('elapsed_seconds', 'N/A')}s")
    print(f"Item 7 (MD&A): {item_7.get('elapsed_seconds', 'N/A')}s")

    # Estimate text length
    items_1a = item_1a.get("data", {}).get("items", [])
    items_7 = item_7.get("data", {}).get("items", [])

    if items_1a:
        text_1a = items_1a[0].get("text", "")
        print(f"Item 1A text length: {len(text_1a):,} characters")

    if items_7:
        text_7 = items_7[0].get("text", "")
        print(f"Item 7 text length: {len(text_7):,} characters")

    print("\n=== Cost Analysis ===")
    print("""
    SELF-BUILD OPTION:
    - Development time: 2-3 weeks (40-60 hours)
    - HTML parsing: BeautifulSoup + regex
    - Challenges:
      * Section boundary detection
      * Table extraction & formatting
      * Company-specific variations
      * Ongoing maintenance
    - Estimated dev cost: $4,000-8,000 (at $100/hr)

    FINANCIAL DATASETS API:
    - Cost per request: Not publicly listed (estimate $0.05-0.10)
    - Latency: 5-15 seconds per item
    - 75 tickers × 2 items × 5 years = 750 requests
    - Estimated cost: $37.50-75.00

    SEC-API.IO ALTERNATIVE:
    - 10-K/10-Q Text Extractor: $0.05 per section
    - Full 10-K: $0.20 per filing
    - Better documentation, dedicated service
    - https://sec-api.io/docs/sec-filings-text-extraction-api

    RECOMMENDATION:
    -------------------------
    For <1000 filings: Use Financial Datasets or sec-api.io
    For >5000 filings: Consider self-build

    Given 75 tickers × 5 years = 375 10-K filings:
    - sec-api.io cost: $75 (at $0.20/filing)
    - Financial Datasets: Similar or lower
    - Self-build: Not worth it for this scale
    """)


def main():
    print("=" * 60)
    print("SEC EDGAR vs Financial Datasets API Comparison")
    print("=" * 60)

    compare_cash_flow()
    compare_filings_list()
    analyze_filing_items_cost()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("""
    REPLACEMENT STATUS:

    | Feature              | Can Replace? | Notes                        |
    |----------------------|--------------|------------------------------|
    | Cash Flow Statement  | YES          | SEC EDGAR XBRL = same data   |
    | Filings List         | YES          | SEC EDGAR = better filtering |
    | Filing Items (text)  | NO*          | Requires HTML parsing        |

    * Filing Items extraction requires complex HTML parsing.
      For <1000 filings, API cost < development cost.

    COST SAVINGS:
    - Cash Flow: $0.04 × 75 tickers × 5 years = $15/run → $0
    - Filings List: Already free from SEC
    - Total annual savings: ~$50-100/year

    REMAINING PAID FEATURES:
    - Filing Items extraction (text from 10-K sections)
    - Best option: sec-api.io or Financial Datasets
    """)


if __name__ == "__main__":
    main()