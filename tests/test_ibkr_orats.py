#!/usr/bin/env python3
"""
IBKR ORATS Options Analytics Test Suite

Tests IBKR connection and ORATS options analytics data availability.
ORATS provides advanced options analytics through IBKR's market data feed.

Requirements:
- IB Gateway or TWS running with API enabled
- ib_insync library: pip install ib_insync
- ORATS subscription (if available through IBKR)
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load config/.env file (setdefault allows shell env vars to override)
env_path = Path(__file__).parent.parent / 'config' / '.env'
if env_path.exists():
    print(f"[OK] Loaded .env from {env_path}")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key.strip(), value)

try:
    from ib_insync import IB, Stock, Option, util
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    print("[FAIL] ib_insync not installed. Run: pip install ib_insync")
    sys.exit(1)


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(test_name: str, passed: bool, details: str = ""):
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {test_name}")
    if details:
        for line in details.split('\n'):
            print(f"       {line}")


def run_tests():
    print("\n" + "="*60)
    print("       IBKR ORATS OPTIONS ANALYTICS TEST")
    print("       MindfulRL-Intraday Project")
    print("="*60)

    # Get connection parameters from environment
    host = os.environ.get('IBKR_HOST', '127.0.0.1')
    port = int(os.environ.get('IBKR_PORT', '4001'))
    client_id = int(os.environ.get('IBKR_CLIENT_ID', '1'))

    print(f"\n  Connection: {host}:{port} (client_id={client_id})")

    results = []
    ib = IB()

    # Test 1: Connection
    print_header("1. IB Gateway Connection")
    try:
        ib.connect(host, port, clientId=client_id, timeout=20, readonly=True)
        print_result("Connection", True, f"Connected to {host}:{port}")
        results.append(("IB Gateway Connection", True))
    except Exception as e:
        print_result("Connection", False, str(e))
        results.append(("IB Gateway Connection", False))
        print("\nCannot proceed without connection.")
        return results

    # Test 2: Account Info
    print_header("2. Account Information")
    try:
        accounts = ib.managedAccounts()
        if accounts:
            print_result("Account Info", True, f"Accounts: {accounts}")
            results.append(("Account Info", True))
        else:
            print_result("Account Info", False, "No accounts found")
            results.append(("Account Info", False))
    except Exception as e:
        print_result("Account Info", False, str(e))
        results.append(("Account Info", False))

    # Test 3: Market Data Subscriptions (check for ORATS)
    print_header("3. Market Data Subscriptions")
    try:
        # Get subscribed market data
        # Note: This shows what data subscriptions are active
        contract = Stock('AAPL', 'SMART', 'USD')
        ib.qualifyContracts(contract)

        # Request market data with all ticks
        ticker = ib.reqMktData(contract, '', False, False)
        ib.sleep(3)  # Wait for data

        print(f"  Market Data Fields Available:")
        fields = []
        if ticker.bid is not None and ticker.bid > 0:
            fields.append(f"Bid: {ticker.bid}")
        if ticker.ask is not None and ticker.ask > 0:
            fields.append(f"Ask: {ticker.ask}")
        if ticker.last is not None and ticker.last > 0:
            fields.append(f"Last: {ticker.last}")
        if ticker.volume is not None and ticker.volume > 0:
            fields.append(f"Volume: {ticker.volume:,}")

        if fields:
            print_result("Market Data", True, "\n".join(fields))
            results.append(("Market Data", True))
        else:
            print_result("Market Data", False, "No market data received (market closed?)")
            results.append(("Market Data", False))

        ib.cancelMktData(contract)

    except Exception as e:
        print_result("Market Data", False, str(e))
        results.append(("Market Data", False))

    # Test 4: Options Chain
    print_header("4. Options Chain (AAPL)")
    try:
        stock = Stock('AAPL', 'SMART', 'USD')
        ib.qualifyContracts(stock)

        # Get option chains
        chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)

        if chains:
            print(f"  Found {len(chains)} option exchanges")
            for chain in chains[:2]:  # Show first 2
                expirations = sorted(chain.expirations)[:3]  # Next 3 expirations
                strikes = len(chain.strikes)
                print(f"    Exchange: {chain.exchange}")
                print(f"    Expirations: {expirations}")
                print(f"    Strikes available: {strikes}")

            print_result("Options Chain", True, f"{len(chains)} exchanges available")
            results.append(("Options Chain", True))
        else:
            print_result("Options Chain", False, "No option chains found")
            results.append(("Options Chain", False))

    except Exception as e:
        print_result("Options Chain", False, str(e))
        results.append(("Options Chain", False))

    # Test 5: Option Greeks/Analytics (ORATS-style data)
    print_header("5. Option Greeks/Analytics")
    try:
        # Get a near-term option for AAPL
        stock = Stock('AAPL', 'SMART', 'USD')
        ib.qualifyContracts(stock)

        chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
        if chains:
            chain = chains[0]
            expirations = sorted(chain.expirations)

            # Get nearest expiration
            if expirations:
                expiry = expirations[0]

                # Get ATM strike (approximate)
                ticker_data = ib.reqMktData(stock, '', True, False)
                ib.sleep(2)
                current_price = ticker_data.last or ticker_data.close or 200
                ib.cancelMktData(stock)

                # Find closest strike (filter for reasonable range)
                reasonable_strikes = [s for s in chain.strikes if 0.8 * current_price <= s <= 1.2 * current_price]
                if not reasonable_strikes:
                    reasonable_strikes = list(chain.strikes)
                strikes = sorted(reasonable_strikes, key=lambda x: abs(x - current_price))
                strike = strikes[0] if strikes else round(current_price / 5) * 5

                print(f"  Testing option: AAPL {expiry} {strike} Call")

                # Create option contract
                option = Option('AAPL', expiry, strike, 'C', 'SMART')
                ib.qualifyContracts(option)

                # Request option market data with greeks
                # Generic tick 106 = implied volatility
                # Generic tick 100-101 = bid/ask
                # Generic tick 104 = historical volatility
                opt_ticker = ib.reqMktData(option, '106', False, False)
                ib.sleep(3)

                print(f"\n  Option Data Received:")
                greeks_found = False

                if opt_ticker.bid:
                    print(f"    Bid: ${opt_ticker.bid:.2f}")
                if opt_ticker.ask:
                    print(f"    Ask: ${opt_ticker.ask:.2f}")
                if opt_ticker.last:
                    print(f"    Last: ${opt_ticker.last:.2f}")

                # Model greeks (from ORATS or IBKR model)
                if opt_ticker.modelGreeks:
                    greeks = opt_ticker.modelGreeks
                    greeks_found = True
                    print(f"\n  Model Greeks (ORATS/IBKR):")
                    print(f"    IV: {greeks.impliedVol:.2%}" if greeks.impliedVol else "    IV: N/A")
                    print(f"    Delta: {greeks.delta:.4f}" if greeks.delta else "    Delta: N/A")
                    print(f"    Gamma: {greeks.gamma:.4f}" if greeks.gamma else "    Gamma: N/A")
                    print(f"    Theta: {greeks.theta:.4f}" if greeks.theta else "    Theta: N/A")
                    print(f"    Vega: {greeks.vega:.4f}" if greeks.vega else "    Vega: N/A")
                    print(f"    Option Price: ${greeks.optPrice:.2f}" if greeks.optPrice else "    Price: N/A")

                # Bid/Ask greeks
                if opt_ticker.bidGreeks:
                    greeks_found = True
                    print(f"\n  Bid Greeks:")
                    print(f"    IV: {opt_ticker.bidGreeks.impliedVol:.2%}" if opt_ticker.bidGreeks.impliedVol else "    N/A")

                if opt_ticker.askGreeks:
                    greeks_found = True
                    print(f"\n  Ask Greeks:")
                    print(f"    IV: {opt_ticker.askGreeks.impliedVol:.2%}" if opt_ticker.askGreeks.impliedVol else "    N/A")

                if greeks_found:
                    print_result("Option Greeks", True, "Greeks data available")
                    results.append(("Option Greeks", True))
                else:
                    print_result("Option Greeks", False, "No greeks data (market closed or no subscription?)")
                    results.append(("Option Greeks", False))

                ib.cancelMktData(option)

    except Exception as e:
        print_result("Option Greeks", False, str(e))
        results.append(("Option Greeks", False))

    # Test 6: Historical Volatility
    print_header("6. Historical Volatility (OPTION_IMPLIED_VOLATILITY)")
    try:
        stock = Stock('AAPL', 'SMART', 'USD')
        ib.qualifyContracts(stock)

        end_date = date.today()
        bars = ib.reqHistoricalData(
            stock,
            endDateTime='',
            durationStr='30 D',
            barSizeSetting='1 day',
            whatToShow='OPTION_IMPLIED_VOLATILITY',
            useRTH=True,
            formatDate=1,
        )

        if bars:
            print(f"  Retrieved {len(bars)} days of IV data")
            print(f"\n  Recent IV values:")
            for bar in bars[-5:]:
                print(f"    {bar.date}: IV = {bar.close:.2%}")
            print_result("Historical IV", True, f"{len(bars)} records")
            results.append(("Historical IV", True))
        else:
            print_result("Historical IV", False, "No IV data returned")
            results.append(("Historical IV", False))

    except Exception as e:
        print_result("Historical IV", False, str(e))
        results.append(("Historical IV", False))

    # Test 7: News Providers (check for options news)
    print_header("7. News Providers")
    try:
        providers = ib.reqNewsProviders()
        if providers:
            print(f"  Available news providers:")
            for p in providers:
                print(f"    {p.code}: {p.name}")
            print_result("News Providers", True, f"{len(providers)} providers")
            results.append(("News Providers", True))
        else:
            print_result("News Providers", False, "No news providers available")
            results.append(("News Providers", False))
    except Exception as e:
        print_result("News Providers", False, str(e))
        results.append(("News Providers", False))

    # Test 8: Options Flow Data (Unusual Activity)
    print_header("8. Options Scanner (Unusual Activity)")
    try:
        from ib_insync import ScannerSubscription

        # Create scanner for unusual options activity
        scanner = ScannerSubscription(
            instrument='STK',
            locationCode='STK.US.MAJOR',
            scanCode='TOP_TRADE_COUNT',  # Most active by trade count
        )

        scan_data = ib.reqScannerData(scanner)

        if scan_data:
            print(f"  Most Active Stocks by Trade Count:")
            for item in scan_data[:5]:
                print(f"    {item.contractDetails.contract.symbol}: rank {item.rank}")
            print_result("Scanner", True, f"{len(scan_data)} results")
            results.append(("Options Scanner", True))
        else:
            print_result("Scanner", False, "No scanner data")
            results.append(("Options Scanner", False))

        ib.cancelScannerSubscription(scanner)

    except Exception as e:
        print_result("Scanner", False, str(e))
        results.append(("Options Scanner", False))

    # Disconnect
    print_header("DISCONNECTING")
    ib.disconnect()
    print("  Disconnected from IB Gateway")

    # Summary
    print_header("TEST SUMMARY")
    passed = sum(1 for _, p in results if p)
    total = len(results)
    print(f"\n  Passed: {passed}/{total}")

    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")

    # ORATS Assessment
    print_header("ORATS OPTIONS ANALYTICS ASSESSMENT")
    has_greeks = any(name == "Option Greeks" and p for name, p in results)
    has_iv = any(name == "Historical IV" and p for name, p in results)
    has_chain = any(name == "Options Chain" and p for name, p in results)

    if has_greeks and has_iv and has_chain:
        print("""
  ORATS-style options analytics are AVAILABLE through your IBKR account!

  Available Features:
  - Real-time option greeks (Delta, Gamma, Theta, Vega)
  - Implied Volatility (bid/ask/model)
  - Historical IV data
  - Options chain data
  - Model pricing

  Note: IBKR provides these analytics through their proprietary model.
  If you have a separate ORATS subscription, that data may also be
  integrated through IBKR's API.
        """)
    else:
        print("""
  Some options analytics features are unavailable.

  This could be because:
  1. Market is closed (greeks require live data)
  2. No options market data subscription
  3. ORATS subscription not linked

  To enable ORATS through IBKR:
  1. Log into Account Management
  2. Go to Settings > Market Data
  3. Subscribe to "US Options Bundle" or specific exchanges
  4. ORATS data is sometimes included with advanced bundles
        """)

    return results


if __name__ == "__main__":
    run_tests()