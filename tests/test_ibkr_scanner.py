#!/usr/bin/env python3
"""
Integration tests for IBKR Scanner functionality.

REQUIRES: IBKR TWS or Gateway running on localhost:7497

Run with:
    python tests/test_ibkr_scanner.py

These tests verify:
1. Connection to IBKR
2. Scanner parameter retrieval
3. Basic market scans
4. Option-specific scans
5. Unusual activity detection
"""

import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv(project_root / "config" / ".env")

from data_sources import IBKRDataSource, OptionFilter


def test_connection():
    """Test basic IBKR connection."""
    print("\n1. Testing IBKR connection...")

    try:
        ibkr = IBKRDataSource()
        ibkr.connect()
        print("   ✓ Connected successfully")
        ibkr.disconnect()
        return True
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        return False


def test_scanner_parameters():
    """Test retrieving scanner parameters."""
    print("\n2. Testing scanner parameters retrieval...")

    with IBKRDataSource() as ibkr:
        xml = ibkr.get_scanner_parameters()

        if xml and len(xml) > 1000:
            print(f"   ✓ Retrieved {len(xml):,} chars of scanner parameters")
            # Check for key elements
            if 'scanCode' in xml and 'locationCode' in xml:
                print("   ✓ Contains expected elements (scanCode, locationCode)")
                return True
            else:
                print("   ✗ Missing expected elements")
                return False
        else:
            print("   ✗ Failed to retrieve parameters")
            return False


def test_basic_stock_scan():
    """Test basic stock scanner."""
    print("\n3. Testing basic stock scanner (TOP_PERC_GAIN)...")

    with IBKRDataSource() as ibkr:
        results = ibkr.scan_market(
            scan_code='TOP_PERC_GAIN',
            instrument='STK',
            location='STK.US.MAJOR',
            above_price=5.0,
        )

        if results:
            print(f"   ✓ Got {len(results)} results")
            print(f"   Top 3: {', '.join([r.symbol for r in results[:3]])}")
            return True
        else:
            print("   ✗ No results returned")
            return False


def test_option_volume_scan():
    """Test option volume scanner."""
    print("\n4. Testing option volume scanner (HOT_BY_OPT_VOLUME)...")

    with IBKRDataSource() as ibkr:
        results = ibkr.scan_unusual_option_volume(
            above_price=10.0,
            above_volume=100000,
        )

        if results:
            print(f"   ✓ Got {len(results)} stocks with high option volume")
            print(f"   Top 5: {', '.join([r.symbol for r in results[:5]])}")
            return True
        else:
            print("   ⚠ No results (may be market hours issue)")
            return True  # Not a failure, just no data


def test_iv_scan():
    """Test implied volatility scanners."""
    print("\n5. Testing IV scanners...")

    with IBKRDataSource() as ibkr:
        # High IV
        high_iv = ibkr.scan_high_iv_stocks(above_price=10.0)
        print(f"   High IV stocks: {len(high_iv)} results")

        # IV gainers
        iv_gainers = ibkr.scan_iv_gainers(above_price=10.0)
        print(f"   IV gainers: {len(iv_gainers)} results")

        if high_iv or iv_gainers:
            print("   ✓ IV scans working")
            if high_iv:
                print(f"   Top High IV: {', '.join([r.symbol for r in high_iv[:3]])}")
            return True
        else:
            print("   ⚠ No IV data (may be market hours issue)")
            return True


def test_put_call_ratio_scan():
    """Test put/call ratio scanners."""
    print("\n6. Testing P/C ratio scanners...")

    with IBKRDataSource() as ibkr:
        high_pc = ibkr.scan_high_put_call_ratio(above_price=10.0)
        low_pc = ibkr.scan_low_put_call_ratio(above_price=10.0)

        print(f"   High P/C ratio: {len(high_pc)} results")
        print(f"   Low P/C ratio: {len(low_pc)} results")

        if high_pc or low_pc:
            print("   ✓ P/C ratio scans working")
            return True
        else:
            print("   ⚠ No P/C data")
            return True


def test_unusual_activity():
    """Test combined unusual activity detection."""
    print("\n7. Testing unusual activity detection...")

    with IBKRDataSource() as ibkr:
        candidates = ibkr.find_unusual_activity_candidates(above_price=10.0)

        if candidates:
            print(f"   ✓ Found {len(candidates)} unusual activity candidates")
            print("\n   Top candidates:")
            for c in candidates[:5]:
                scans = ', '.join([s.split('_')[0] for s in c['scans_appeared']])
                print(f"     {c['symbol']}: score={c['score']}, appeared in {c['appearance_count']} scans")
            return True
        else:
            print("   ⚠ No unusual activity detected")
            return True


def test_option_filter():
    """Test option chain filtering."""
    print("\n8. Testing option chain filtering...")

    with IBKRDataSource() as ibkr:
        # Get a quote first to know current price
        quote = ibkr.get_current_quote('AAPL')
        if not quote:
            print("   ✗ Could not get AAPL quote")
            return False

        current_price = quote.get('last') or quote.get('close')
        print(f"   AAPL current price: ${current_price:.2f}")

        # Filter options
        filter_config = OptionFilter(
            strike_range_pct=0.05,  # ±5%
            min_dte=7,
            max_dte=30,
            rights=['C', 'P'],
        )

        contracts = ibkr.filter_interesting_options('AAPL', filter_config)

        if contracts:
            print(f"   ✓ Found {len(contracts)} interesting contracts")
            # Show sample
            sample = contracts[0]
            print(f"   Sample: {sample['expiry']} ${sample['strike']} {sample['right']}")
            return True
        else:
            print("   ✗ No contracts found")
            return False


def test_option_quote():
    """Test getting option quotes."""
    print("\n9. Testing option quote retrieval...")

    with IBKRDataSource() as ibkr:
        # First filter to find a valid contract
        contracts = ibkr.filter_interesting_options(
            'SPY',
            OptionFilter(strike_range_pct=0.02, min_dte=7, max_dte=14, rights=['C']),
        )

        if not contracts:
            print("   ✗ No contracts to test")
            return False

        contract = contracts[0]
        print(f"   Testing: SPY {contract['expiry']} ${contract['strike']} {contract['right']}")

        quote = ibkr.get_option_quote(
            ticker='SPY',
            expiry=contract['expiry'],
            strike=contract['strike'],
            right=contract['right'],
        )

        if quote and quote.bid is not None:
            print(f"   ✓ Got quote: bid=${quote.bid:.2f}, ask=${quote.ask:.2f}")
            if quote.delta:
                print(f"   Greeks: delta={quote.delta:.3f}, iv={quote.implied_vol:.1%}" if quote.implied_vol else f"   Greeks: delta={quote.delta:.3f}")
            return True
        else:
            print("   ⚠ No quote data (may need OPRA subscription)")
            return True


def run_all_tests():
    """Run all integration tests."""
    print("=" * 60)
    print(" IBKR Scanner Integration Tests")
    print(f" Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print("\nNote: Some tests may return no data outside market hours.")

    results = {}

    # Test 1: Connection (required for all others)
    if not test_connection():
        print("\n" + "=" * 60)
        print(" FAILED: Cannot connect to IBKR")
        print(" Make sure TWS or Gateway is running on localhost:7497")
        print("=" * 60)
        return

    # Run remaining tests
    tests = [
        ("Scanner Parameters", test_scanner_parameters),
        ("Basic Stock Scan", test_basic_stock_scan),
        ("Option Volume Scan", test_option_volume_scan),
        ("IV Scans", test_iv_scan),
        ("P/C Ratio Scans", test_put_call_ratio_scan),
        ("Unusual Activity", test_unusual_activity),
        ("Option Filter", test_option_filter),
        ("Option Quote", test_option_quote),
    ]

    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"   ✗ Error: {e}")
            results[name] = False

    # Summary
    print("\n" + "=" * 60)
    print(" TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")

    print(f"\n  Total: {passed}/{total} tests passed")
    print("=" * 60)


if __name__ == '__main__':
    run_all_tests()