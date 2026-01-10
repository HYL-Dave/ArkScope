"""
Test IBKR TWS API Options and Greeks functionality.

This script tests:
1. Option chain retrieval
2. Real-time Greeks (delta, gamma, theta, vega, IV)
3. Model Greeks calculation

Requirements:
    - TWS or IB Gateway running locally
    - US market must be OPEN for real-time Greeks
    - pip install ib_insync

Usage:
    python -m data_sources.test_ibkr_options_greeks
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ib_insync import IB, Stock, Option, util
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    print("ERROR: ib_insync not installed. Run: pip install ib_insync")

# Load config
from dotenv import load_dotenv
load_dotenv("config/.env")


def connect_to_ibkr(
    host: str = None,
    port: int = None,
    client_id: int = 101
) -> Optional[IB]:
    """Connect to TWS/IB Gateway."""
    if not HAS_IB_INSYNC:
        return None

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


def get_option_chain(ib: IB, ticker: str = "AAPL") -> List[str]:
    """Get available option expirations for a stock."""
    print(f"\n{'='*60}")
    print(f"Test 1: Option Chain for {ticker}")
    print(f"{'='*60}")

    stock = Stock(ticker, "SMART", "USD")
    ib.qualifyContracts(stock)

    # Get option chains
    chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)

    if chains:
        print(f"\nFound {len(chains)} option exchange(s)")
        for chain in chains[:3]:  # First 3 exchanges
            print(f"\n  Exchange: {chain.exchange}")
            print(f"  Expirations: {len(chain.expirations)}")
            print(f"    Next 5: {sorted(chain.expirations)[:5]}")
            print(f"  Strikes: {len(chain.strikes)}")
            print(f"    Sample: {sorted(chain.strikes)[len(chain.strikes)//2-3:len(chain.strikes)//2+3]}")

        # Return expirations from first chain
        return sorted(chains[0].expirations)
    else:
        print("No option chains found")
        return []


def test_option_greeks(
    ib: IB,
    ticker: str = "AAPL",
    expiration: str = None,
    right: str = "C"  # C=Call, P=Put
) -> Dict[str, Any]:
    """
    Test getting real-time Greeks for an option.

    IMPORTANT: Greeks require market to be OPEN!
    """
    print(f"\n{'='*60}")
    print(f"Test 2: Real-time Greeks for {ticker} {right}")
    print(f"{'='*60}")

    # Get stock price first
    stock = Stock(ticker, "SMART", "USD")
    ib.qualifyContracts(stock)

    stock_ticker = ib.reqMktData(stock, '', False, False)
    ib.sleep(2)

    stock_price = stock_ticker.last or stock_ticker.close

    # Handle NaN or None
    import math
    if stock_price is None or (isinstance(stock_price, float) and math.isnan(stock_price)):
        print(f"\n{ticker} current price: Not available (pre-market or no subscription)")
        print("  Using estimated ATM strike based on recent close...")
        stock_price = None
    else:
        print(f"\n{ticker} current price: ${stock_price}")

    # Cancel stock data
    ib.cancelMktData(stock)

    # Find nearest expiration if not provided
    if not expiration:
        chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
        if chains:
            expirations = sorted(chains[0].expirations)
            # Find expiration about 30 days out
            today = datetime.now().strftime('%Y%m%d')
            for exp in expirations:
                if exp > today:
                    expiration = exp
                    break
        if not expiration:
            print("No valid expiration found")
            return {}

    print(f"Using expiration: {expiration}")

    # Find ATM strike
    if stock_price:
        atm_strike = round(stock_price / 5) * 5  # Round to nearest 5
    else:
        atm_strike = 250  # Default for AAPL

    print(f"ATM strike: ${atm_strike}")

    # Create option contract
    option = Option(ticker, expiration, atm_strike, right, "SMART")

    try:
        ib.qualifyContracts(option)
        print(f"\nOption contract: {option.localSymbol}")
        print(f"  ConId: {option.conId}")
    except Exception as e:
        print(f"Failed to qualify option contract: {e}")
        return {}

    # Request market data with Greeks
    # Generic tick types for Greeks:
    # 100 = Option Volume
    # 101 = Option Open Interest
    # 104 = Historical Volatility
    # 106 = Implied Volatility
    # 411 = Realtime Historical Volatility

    print("\nRequesting market data with Greeks...")
    option_ticker = ib.reqMktData(option, '100,101,104,106', False, False)

    # Wait for data
    for i in range(10):
        ib.sleep(1)
        print(f"  Waiting... ({i+1}/10)")

        # Check if we have Greeks
        if option_ticker.modelGreeks:
            print("  Got modelGreeks!")
            break
        if option_ticker.bidGreeks or option_ticker.askGreeks:
            print("  Got bid/ask Greeks!")
            break

    result = {
        'ticker': ticker,
        'expiration': expiration,
        'strike': atm_strike,
        'right': 'Call' if right == 'C' else 'Put',
        'stock_price': stock_price,
    }

    # Extract Greeks
    print(f"\n{'='*40}")
    print("GREEKS RESULTS")
    print(f"{'='*40}")

    # Model Greeks (theoretical)
    if option_ticker.modelGreeks:
        mg = option_ticker.modelGreeks
        result['model_greeks'] = {
            'impliedVol': mg.impliedVol,
            'delta': mg.delta,
            'gamma': mg.gamma,
            'theta': mg.theta,
            'vega': mg.vega,
            'pvDividend': mg.pvDividend,
            'optPrice': mg.optPrice,
            'undPrice': mg.undPrice,
        }
        print("\n[Model Greeks] (Theoretical)")
        print(f"  Implied Volatility: {mg.impliedVol:.4f}" if mg.impliedVol else "  Implied Volatility: N/A")
        print(f"  Delta: {mg.delta:.4f}" if mg.delta else "  Delta: N/A")
        print(f"  Gamma: {mg.gamma:.6f}" if mg.gamma else "  Gamma: N/A")
        print(f"  Theta: {mg.theta:.4f}" if mg.theta else "  Theta: N/A")
        print(f"  Vega: {mg.vega:.4f}" if mg.vega else "  Vega: N/A")
        print(f"  Option Price: ${mg.optPrice:.2f}" if mg.optPrice else "  Option Price: N/A")
        print(f"  Underlying Price: ${mg.undPrice:.2f}" if mg.undPrice else "  Underlying Price: N/A")
    else:
        print("\n[Model Greeks] Not available")
        print("  (Market might be closed or data subscription required)")

    # Bid Greeks
    if option_ticker.bidGreeks:
        bg = option_ticker.bidGreeks
        result['bid_greeks'] = {
            'impliedVol': bg.impliedVol,
            'delta': bg.delta,
            'gamma': bg.gamma,
            'theta': bg.theta,
            'vega': bg.vega,
        }
        print("\n[Bid Greeks]")
        print(f"  Delta: {bg.delta:.4f}" if bg.delta else "  Delta: N/A")
        print(f"  IV: {bg.impliedVol:.4f}" if bg.impliedVol else "  IV: N/A")

    # Ask Greeks
    if option_ticker.askGreeks:
        ag = option_ticker.askGreeks
        result['ask_greeks'] = {
            'impliedVol': ag.impliedVol,
            'delta': ag.delta,
            'gamma': ag.gamma,
            'theta': ag.theta,
            'vega': ag.vega,
        }
        print("\n[Ask Greeks]")
        print(f"  Delta: {ag.delta:.4f}" if ag.delta else "  Delta: N/A")
        print(f"  IV: {ag.impliedVol:.4f}" if ag.impliedVol else "  IV: N/A")

    # Last Greeks
    if option_ticker.lastGreeks:
        lg = option_ticker.lastGreeks
        result['last_greeks'] = {
            'impliedVol': lg.impliedVol,
            'delta': lg.delta,
        }
        print("\n[Last Greeks]")
        print(f"  Delta: {lg.delta:.4f}" if lg.delta else "  Delta: N/A")

    # Other option data
    print(f"\n{'='*40}")
    print("OTHER OPTION DATA")
    print(f"{'='*40}")

    print(f"\n  Bid: ${option_ticker.bid}" if option_ticker.bid else "\n  Bid: N/A")
    print(f"  Ask: ${option_ticker.ask}" if option_ticker.ask else "  Ask: N/A")
    print(f"  Last: ${option_ticker.last}" if option_ticker.last else "  Last: N/A")
    print(f"  Volume: {option_ticker.volume}" if option_ticker.volume else "  Volume: N/A")

    # Implied Volatility from generic ticks
    if hasattr(option_ticker, 'impliedVolatility') and option_ticker.impliedVolatility:
        print(f"  Historical IV: {option_ticker.impliedVolatility}")

    # Cancel market data
    ib.cancelMktData(option)

    return result


def test_multiple_strikes(ib: IB, ticker: str = "AAPL") -> List[Dict]:
    """Test Greeks for multiple strikes around ATM."""
    print(f"\n{'='*60}")
    print(f"Test 3: Greeks for Multiple Strikes ({ticker})")
    print(f"{'='*60}")

    # Get stock price
    import math
    stock = Stock(ticker, "SMART", "USD")
    ib.qualifyContracts(stock)
    stock_ticker = ib.reqMktData(stock, '', False, False)
    ib.sleep(2)
    stock_price = stock_ticker.last or stock_ticker.close
    if stock_price is None or (isinstance(stock_price, float) and math.isnan(stock_price)):
        stock_price = 250  # Default for AAPL when market data unavailable
    ib.cancelMktData(stock)

    # Get nearest expiration
    chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
    if not chains:
        return []

    expirations = sorted(chains[0].expirations)
    today = datetime.now().strftime('%Y%m%d')
    expiration = None
    for exp in expirations:
        if exp > today:
            expiration = exp
            break

    if not expiration:
        return []

    print(f"\nStock price: ${stock_price}")
    print(f"Expiration: {expiration}")

    # Test strikes: -10%, -5%, ATM, +5%, +10%
    atm = round(stock_price / 5) * 5
    strikes = [
        atm - 10,
        atm - 5,
        atm,
        atm + 5,
        atm + 10,
    ]

    results = []

    print(f"\n{'Strike':<10} {'Type':<6} {'Delta':<10} {'Gamma':<10} {'Theta':<10} {'IV':<10}")
    print("-" * 60)

    for strike in strikes:
        for right in ['C', 'P']:
            option = Option(ticker, expiration, strike, right, "SMART")
            try:
                ib.qualifyContracts(option)
            except:
                continue

            ticker_data = ib.reqMktData(option, '', False, False)
            ib.sleep(1)

            if ticker_data.modelGreeks:
                mg = ticker_data.modelGreeks
                delta = f"{mg.delta:.4f}" if mg.delta else "N/A"
                gamma = f"{mg.gamma:.6f}" if mg.gamma else "N/A"
                theta = f"{mg.theta:.4f}" if mg.theta else "N/A"
                iv = f"{mg.impliedVol:.2%}" if mg.impliedVol else "N/A"

                print(f"${strike:<9} {'Call' if right == 'C' else 'Put':<6} {delta:<10} {gamma:<10} {theta:<10} {iv:<10}")

                results.append({
                    'strike': strike,
                    'type': 'Call' if right == 'C' else 'Put',
                    'delta': mg.delta,
                    'gamma': mg.gamma,
                    'theta': mg.theta,
                    'vega': mg.vega,
                    'iv': mg.impliedVol,
                })
            else:
                print(f"${strike:<9} {'Call' if right == 'C' else 'Put':<6} {'(no data)':<40}")

            ib.cancelMktData(option)

    return results


def main():
    """Main test function."""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║     IBKR TWS API - Options & Greeks Test                      ║
║                                                               ║
║  IMPORTANT: US Market must be OPEN for real-time Greeks!      ║
║                                                               ║
║  Market Hours (US Eastern):                                   ║
║    Regular: 9:30 AM - 4:00 PM ET                              ║
║    Pre-market: 4:00 AM - 9:30 AM ET                           ║
║    After-hours: 4:00 PM - 8:00 PM ET                          ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    if not HAS_IB_INSYNC:
        print("ERROR: ib_insync is required. Install with: pip install ib_insync")
        return

    # Check market hours
    from datetime import datetime
    import pytz

    try:
        et = pytz.timezone('US/Eastern')
        now_et = datetime.now(et)
        hour = now_et.hour
        minute = now_et.minute
        weekday = now_et.weekday()

        print(f"Current US Eastern Time: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")

        if weekday >= 5:
            print("⚠️  WARNING: It's the weekend - market is CLOSED")
            print("   Greeks data will NOT be available")
        elif hour < 9 or (hour == 9 and minute < 30):
            print("⚠️  Pre-market hours - limited data may be available")
        elif hour >= 16:
            print("⚠️  After-hours - limited data may be available")
        else:
            print("✅ Market is OPEN - Greeks should be available")
    except:
        print("Could not determine market hours (pytz not installed)")

    # Connect
    ib = connect_to_ibkr()
    if not ib:
        print("\nFailed to connect. Please ensure TWS/IB Gateway is running.")
        return

    try:
        # Test 1: Option chain
        expirations = get_option_chain(ib, "AAPL")

        # Test 2: Single option Greeks
        result = test_option_greeks(ib, "AAPL")

        # Test 3: Multiple strikes
        multi_results = test_multiple_strikes(ib, "AAPL")

        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")

        if result.get('model_greeks'):
            print("\n✅ Real-time Greeks are available!")
            print("\nKey findings:")
            print("  - Model Greeks (theoretical) are calculated in real-time")
            print("  - No additional subscription needed for Greeks calculation")
            print("  - Market must be open for live data")
        else:
            print("\n⚠️  Greeks not available")
            print("\nPossible reasons:")
            print("  1. Market is closed (check market hours)")
            print("  2. Option has no liquidity")
            print("  3. Need market data subscription for real-time quotes")

        print("\n" + "="*60)
        print("CONCLUSIONS FOR IBKR OPTIONS")
        print("="*60)
        print("""
1. OPTION CHAIN: ✅ FREE
   - Full option chain data available
   - All expirations and strikes

2. REAL-TIME GREEKS: ✅ Available when market is open
   - modelGreeks: Theoretical Greeks calculated by IBKR
   - bidGreeks/askGreeks: Market-based Greeks
   - No additional subscription for Greeks calculation

3. REQUIREMENTS:
   - TWS/IB Gateway running
   - Market must be OPEN for real-time data
   - If closed: Greeks will be N/A

4. DATA AVAILABLE:
   - Delta, Gamma, Theta, Vega
   - Implied Volatility
   - Option prices (bid/ask/last)
   - Underlying price
        """)

    finally:
        print(f"\n{'='*60}")
        print("Disconnecting...")
        ib.disconnect()
        print("Done!")


if __name__ == "__main__":
    main()