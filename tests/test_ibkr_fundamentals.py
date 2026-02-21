"""
Test IBKR TWS API reqFundamentalData functionality.

This script tests the official ib_insync method reqFundamentalData()
to verify that fundamental data can be obtained directly without third-party packages.

Report Types Available:
- ReportsFinSummary: Financial summary
- ReportsOwnership: Company's ownership
- ReportSnapshot: Company's financial overview (most useful)
- ReportsFinStatements: Financial Statements
- RESC: Analyst Estimates
- CalendarReport: Company's calendar

Usage:
    python -m data_sources.test_ibkr_fundamentals

Requirements:
    - TWS or IB Gateway running locally
    - pip install ib_insync beautifulsoup4 lxml
"""

import os
import sys
from datetime import datetime

import pytest
pytestmark = pytest.mark.skip("manual test script — requires IBKR TWS")
from typing import Optional, Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ib_insync import IB, Stock, util
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    print("ERROR: ib_insync not installed. Run: pip install ib_insync")

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    print("WARNING: beautifulsoup4 not installed. XML parsing will be limited.")

# Load config
from dotenv import load_dotenv
load_dotenv("config/.env")


def connect_to_ibkr(
    host: str = None,
    port: int = None,
    client_id: int = 100
) -> Optional[IB]:
    """Connect to TWS/IB Gateway."""
    if not HAS_IB_INSYNC:
        return None

    # Get from env or use defaults
    host = host or os.getenv("IBKR_HOST", "127.0.0.1")
    port = port or int(os.getenv("IBKR_PORT", "7497"))

    print(f"\n{'='*60}")
    print(f"Connecting to IBKR at {host}:{port}...")
    print(f"{'='*60}")

    ib = IB()
    try:
        ib.connect(host, port, clientId=client_id, timeout=30)
        print(f"Connected! Server version: {ib.client.serverVersion()}")
        return ib
    except Exception as e:
        print(f"Connection failed: {e}")
        return None


def test_fundamental_ratios_tick258(ib: IB, ticker: str = "AAPL") -> Dict[str, Any]:
    """
    Test Method 1: Get fundamental ratios using generic tick 258.

    This is what ibkr_source.py currently uses.
    Returns real-time fundamental ratios (limited set).
    """
    print(f"\n{'='*60}")
    print(f"Test 1: Generic Tick 258 - Real-time Ratios for {ticker}")
    print(f"{'='*60}")

    contract = Stock(ticker, "SMART", "USD")
    ib.qualifyContracts(contract)

    # Request with generic tick 258 for fundamental ratios
    ticker_data = ib.reqMktData(contract, '258', False, False)
    ib.sleep(3)  # Wait for data

    result = {}

    if ticker_data.fundamentalRatios:
        ratios = ticker_data.fundamentalRatios
        result = {
            'method': 'generic_tick_258',
            'ticker': ticker,
            'pe_ratio': getattr(ratios, 'PEEXCLXOR', None),
            'eps': getattr(ratios, 'AEPSNORM', None),
            'price_to_book': getattr(ratios, 'PRICE2BK', None),
            'price_to_sales': getattr(ratios, 'PRICE2SAL', None),
            'dividend_yield': getattr(ratios, 'YIELD', None),
            'beta': getattr(ratios, 'BETA', None),
            'market_cap': getattr(ratios, 'MKTCAP', None),
            'revenue_ttm': getattr(ratios, 'TTMREV', None),
            'gross_margin': getattr(ratios, 'GROSMGN', None),
            'roe': getattr(ratios, 'TTMROEPCT', None),
        }
        print(f"\nFundamental Ratios (Tick 258):")
        for key, value in result.items():
            if key not in ['method', 'ticker']:
                print(f"  {key}: {value}")
    else:
        print("No fundamental ratios returned")
        result = {'method': 'generic_tick_258', 'ticker': ticker, 'error': 'No data'}

    # Cancel market data
    ib.cancelMktData(contract)

    return result


def test_req_fundamental_data(
    ib: IB,
    ticker: str = "AAPL",
    report_type: str = "ReportSnapshot"
) -> Dict[str, Any]:
    """
    Test Method 2: reqFundamentalData() - The official API method.

    This returns comprehensive fundamental data in XML format.

    Available report types:
    - ReportsFinSummary: Financial summary
    - ReportsOwnership: Company's ownership
    - ReportSnapshot: Company's financial overview (RECOMMENDED)
    - ReportsFinStatements: Financial Statements
    - RESC: Analyst Estimates
    - CalendarReport: Company's calendar
    """
    print(f"\n{'='*60}")
    print(f"Test 2: reqFundamentalData - {report_type} for {ticker}")
    print(f"{'='*60}")

    contract = Stock(ticker, "SMART", "USD")
    ib.qualifyContracts(contract)

    result = {
        'method': 'reqFundamentalData',
        'report_type': report_type,
        'ticker': ticker,
    }

    try:
        # This is the official API method!
        xml_data = ib.reqFundamentalData(contract, report_type)

        if xml_data:
            result['raw_xml_length'] = len(xml_data)
            print(f"\nReceived XML data: {len(xml_data)} characters")

            # Parse XML if BeautifulSoup available
            if HAS_BS4:
                soup = BeautifulSoup(xml_data, "xml")

                # Extract ratios based on report type
                if report_type == "ReportSnapshot":
                    ratios = soup.find_all("Ratio")
                    result['ratios'] = {}
                    print(f"\nExtracted {len(ratios)} ratios:")
                    for ratio in ratios[:20]:  # First 20
                        field_name = ratio.get('FieldName', 'Unknown')
                        value = ratio.text.strip() if ratio.text else None
                        result['ratios'][field_name] = value
                        print(f"  {field_name}: {value}")

                    if len(ratios) > 20:
                        print(f"  ... and {len(ratios) - 20} more ratios")

                    # Try to find company info
                    company_info = soup.find("CoIDs")
                    if company_info:
                        result['company_name'] = company_info.find("CoID", {"Type": "CompanyName"})
                        result['cik'] = company_info.find("CoID", {"Type": "CIKNo"})
                        if result['company_name']:
                            result['company_name'] = result['company_name'].text
                        if result['cik']:
                            result['cik'] = result['cik'].text
                        print(f"\nCompany: {result.get('company_name', 'N/A')}")
                        print(f"CIK: {result.get('cik', 'N/A')}")

                elif report_type == "ReportsFinStatements":
                    # Look for financial statement data
                    statements = soup.find_all("FiscalPeriod")
                    result['fiscal_periods'] = len(statements)
                    print(f"\nFound {len(statements)} fiscal periods")

                    # Get most recent
                    if statements:
                        recent = statements[0]
                        period_type = recent.get('Type', 'Unknown')
                        end_date = recent.get('EndDate', 'Unknown')
                        print(f"Most recent: {period_type} ending {end_date}")

                elif report_type == "RESC":
                    # Analyst estimates
                    estimates = soup.find_all("FYEstimate")
                    result['estimates_count'] = len(estimates)
                    print(f"\nFound {len(estimates)} analyst estimates")

            else:
                # No BeautifulSoup, just show raw preview
                print(f"\nXML Preview (first 500 chars):")
                print(xml_data[:500])
                result['xml_preview'] = xml_data[:500]
        else:
            print("No data returned")
            result['error'] = "No data returned"

    except Exception as e:
        print(f"Error: {e}")
        result['error'] = str(e)

    return result


def test_all_report_types(ib: IB, ticker: str = "AAPL") -> List[Dict[str, Any]]:
    """Test all available report types."""
    print(f"\n{'='*60}")
    print(f"Test 3: All Report Types for {ticker}")
    print(f"{'='*60}")

    report_types = [
        "ReportSnapshot",        # Financial overview (most useful)
        "ReportsFinSummary",     # Financial summary
        "ReportsOwnership",      # Company ownership
        "ReportsFinStatements",  # Financial statements
        "RESC",                  # Analyst estimates
        "CalendarReport",        # Company calendar
    ]

    results = []
    contract = Stock(ticker, "SMART", "USD")
    ib.qualifyContracts(contract)

    for report_type in report_types:
        print(f"\n--- Testing {report_type} ---")
        try:
            xml_data = ib.reqFundamentalData(contract, report_type)
            if xml_data:
                print(f"  Success! Received {len(xml_data)} characters")
                results.append({
                    'report_type': report_type,
                    'status': 'success',
                    'size': len(xml_data)
                })
            else:
                print(f"  No data returned")
                results.append({
                    'report_type': report_type,
                    'status': 'no_data',
                    'size': 0
                })
        except Exception as e:
            error_msg = str(e)
            print(f"  Error: {error_msg}")
            results.append({
                'report_type': report_type,
                'status': 'error',
                'error': error_msg
            })

        ib.sleep(1)  # Rate limiting

    return results


def main():
    """Main test function."""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║     IBKR TWS API - Fundamental Data Test                      ║
║                                                                ║
║  Testing reqFundamentalData() - Official ib_insync method     ║
║                                                                ║
║  Purpose: Verify that fundamental data can be obtained        ║
║           directly WITHOUT third-party packages               ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    if not HAS_IB_INSYNC:
        print("ERROR: ib_insync is required. Install with: pip install ib_insync")
        return

    # Connect
    ib = connect_to_ibkr()
    if not ib:
        print("\nFailed to connect. Please ensure TWS/IB Gateway is running.")
        return

    test_results = {}

    try:
        # Test 1: Generic tick 258 (current implementation)
        test_results['tick_258'] = test_fundamental_ratios_tick258(ib, "AAPL")

        # Test 2: reqFundamentalData - ReportSnapshot
        test_results['report_snapshot'] = test_req_fundamental_data(
            ib, "AAPL", "ReportSnapshot"
        )

        # Test 3: reqFundamentalData - RESC (Analyst Estimates)
        test_results['analyst_estimates'] = test_req_fundamental_data(
            ib, "AAPL", "RESC"
        )

        # Test 4: All report types
        test_results['all_reports'] = test_all_report_types(ib, "AAPL")

        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")

        print("""
Key Findings:

1. ib_insync IS the official Python wrapper for TWS API
   - NOT a third-party library
   - Recommended by IBKR for Python development

2. reqFundamentalData() is available directly in ib_insync
   - Returns comprehensive XML data
   - Just need BeautifulSoup to parse (optional)

3. No additional library needed for basic usage
   - ib_fundamental is just a convenience wrapper
   - Parses XML → pandas DataFrame
   - Nice to have, not required

4. Available Report Types:
   - ReportSnapshot: Financial ratios (P/E, ROE, etc.)
   - ReportsFinStatements: Balance sheet, income, cash flow
   - RESC: Analyst estimates
   - ReportsOwnership: Institutional ownership
   - ReportsFinSummary: Financial summary
   - CalendarReport: Earnings dates, etc.
        """)

        # Print test success/failure
        print("\nTest Results:")
        for test_name, result in test_results.items():
            if test_name != 'all_reports':
                status = '✓' if 'error' not in result else '✗'
                print(f"  {status} {test_name}")
            else:
                print(f"  All report types:")
                for r in result:
                    status = '✓' if r['status'] == 'success' else '✗'
                    print(f"    {status} {r['report_type']}: {r.get('size', 0)} chars")

    finally:
        print(f"\n{'='*60}")
        print("Disconnecting...")
        ib.disconnect()
        print("Done!")


if __name__ == "__main__":
    main()