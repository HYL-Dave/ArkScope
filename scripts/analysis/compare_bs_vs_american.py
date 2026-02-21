#!/usr/bin/env python3
"""
Compare Black-Scholes vs Bjerksund-Stensland 2002 pricing.

Usage:
    # Math-only comparison (no IBKR needed)
    python scripts/analysis/compare_bs_vs_american.py --math-only

    # With IBKR market data comparison (needs TWS connection)
    python scripts/analysis/compare_bs_vs_american.py NVDA AMD TSLA

    # Export results to JSON
    python scripts/analysis/compare_bs_vs_american.py --math-only --json results.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis import (
    american_greeks,
    bjerksund_stensland_2002,
    black_scholes_greeks,
    black_scholes_price,
    calculate_american_iv,
    calculate_implied_volatility,
)


# ============================================================
# Math-only comparison
# ============================================================

def compare_prices_across_params() -> List[Dict]:
    """Compare BS vs BS2002 prices across a parameter grid."""
    results = []

    # Parameter grid
    spots = [80, 90, 100, 110, 120]      # S
    strike = 100                            # K
    expiries = [0.083, 0.25, 0.5, 1.0]    # T (1mo, 3mo, 6mo, 1yr)
    vols = [0.20, 0.30, 0.50]              # sigma
    rates = [0.04, 0.05]                   # r
    divs = [0.0, 0.02, 0.05]              # q

    for S in spots:
        for T in expiries:
            for sigma in vols:
                for r in rates:
                    for q in divs:
                        for opt_type in ["C", "P"]:
                            bs = black_scholes_price(S, strike, T, r, sigma, opt_type)
                            am = bjerksund_stensland_2002(S, strike, T, r, sigma, q, opt_type)
                            diff = am - bs
                            pct = (diff / bs * 100) if bs > 0.01 else 0.0

                            results.append({
                                "S": S, "K": strike, "T": T, "r": r,
                                "sigma": sigma, "q": q, "type": opt_type,
                                "bs_price": round(bs, 4),
                                "am_price": round(am, 4),
                                "diff": round(diff, 4),
                                "diff_pct": round(pct, 2),
                            })
    return results


def compare_greeks_across_params() -> List[Dict]:
    """Compare BS vs American Greeks for key scenarios."""
    results = []

    scenarios = [
        # (label, S, K, T, r, sigma, q, type)
        ("ATM call no div", 100, 100, 0.25, 0.05, 0.30, 0.0, "C"),
        ("ATM put no div", 100, 100, 0.25, 0.05, 0.30, 0.0, "P"),
        ("ITM put no div", 80, 100, 0.5, 0.05, 0.30, 0.0, "P"),
        ("Deep ITM put", 70, 100, 1.0, 0.05, 0.30, 0.0, "P"),
        ("ATM call 2% div", 100, 100, 0.25, 0.05, 0.30, 0.02, "C"),
        ("ATM call 5% div", 100, 100, 0.25, 0.05, 0.30, 0.05, "C"),
        ("OTM call high vol", 100, 120, 0.5, 0.05, 0.50, 0.0, "C"),
        ("Long-dated ATM put", 100, 100, 2.0, 0.05, 0.25, 0.0, "P"),
    ]

    for label, S, K, T, r, sigma, q, opt_type in scenarios:
        bs_g = black_scholes_greeks(S, K, T, r, sigma, opt_type)
        am_g = american_greeks(S, K, T, r, sigma, q, opt_type)

        results.append({
            "scenario": label,
            "S": S, "K": K, "T": T, "sigma": sigma, "q": q, "type": opt_type,
            "bs_delta": round(bs_g["delta"], 4),
            "am_delta": round(am_g["delta"], 4),
            "delta_diff": round(am_g["delta"] - bs_g["delta"], 4),
            "bs_gamma": round(bs_g["gamma"], 4),
            "am_gamma": round(am_g["gamma"], 4),
            "bs_vega": round(bs_g["vega"], 4),
            "am_vega": round(am_g["vega"], 4),
            "bs_theta": round(bs_g["theta"], 4),
            "am_theta": round(am_g["theta"], 4),
        })
    return results


def compare_iv_recovery() -> List[Dict]:
    """Compare IV recovery: price with known vol → recover vol via BS and American IV."""
    results = []

    scenarios = [
        # (label, S, K, T, r, q, true_sigma, type)
        ("ATM call", 100, 100, 0.25, 0.05, 0.0, 0.30, "C"),
        ("ATM put", 100, 100, 0.25, 0.05, 0.0, 0.30, "P"),
        ("ITM put", 80, 100, 0.5, 0.05, 0.0, 0.30, "P"),
        ("Deep ITM put", 70, 100, 1.0, 0.05, 0.0, 0.30, "P"),
        ("Call with div", 100, 100, 0.5, 0.05, 0.03, 0.25, "C"),
        ("High vol put", 100, 100, 0.25, 0.05, 0.0, 0.60, "P"),
    ]

    for label, S, K, T, r, q, true_sigma, opt_type in scenarios:
        # Get American price with true vol
        am_price = bjerksund_stensland_2002(S, K, T, r, true_sigma, q, opt_type)

        # Recover IV using American model
        am_iv = calculate_american_iv(am_price, S, K, T, r, q, opt_type)

        # Also try recovering with BS (European) — should show bias for puts
        bs_iv = None
        try:
            bs_iv = calculate_implied_volatility(am_price, S, K, T, r, opt_type)
        except Exception:
            pass

        results.append({
            "scenario": label,
            "true_sigma": true_sigma,
            "am_price": round(am_price, 4),
            "am_iv": round(am_iv, 6) if am_iv else None,
            "am_iv_error": round(abs(am_iv - true_sigma), 6) if am_iv else None,
            "bs_iv": round(bs_iv, 6) if bs_iv else None,
            "bs_iv_error": round(abs(bs_iv - true_sigma), 6) if bs_iv else None,
            "bs_iv_bias": round(bs_iv - true_sigma, 6) if bs_iv else None,
        })
    return results


def print_price_summary(results: List[Dict]) -> None:
    """Print summary statistics of price comparison."""
    puts = [r for r in results if r["type"] == "P"]
    calls = [r for r in results if r["type"] == "C"]

    # Calls without dividends
    calls_no_div = [r for r in calls if r["q"] == 0.0]
    # Puts without dividends
    puts_no_div = [r for r in puts if r["q"] == 0.0]
    # Calls with dividends
    calls_div = [r for r in calls if r["q"] > 0.0]

    print("=" * 80)
    print("BLACK-SCHOLES vs BJERKSUND-STENSLAND 2002 — PRICE COMPARISON")
    print("=" * 80)

    def print_stats(label: str, data: List[Dict]) -> None:
        if not data:
            return
        diffs = [r["diff"] for r in data]
        pcts = [r["diff_pct"] for r in data]
        print(f"\n{label} ({len(data)} scenarios)")
        print(f"  Price diff:  min={min(diffs):.4f}  max={max(diffs):.4f}  "
              f"avg={sum(diffs)/len(diffs):.4f}")
        print(f"  Pct diff:    min={min(pcts):.2f}%  max={max(pcts):.2f}%  "
              f"avg={sum(pcts)/len(pcts):.2f}%")

    print_stats("Calls (no dividend) — expect AM ≈ BS", calls_no_div)
    print_stats("Puts (no dividend) — expect AM > BS", puts_no_div)
    print_stats("Calls (with dividend) — expect AM > BS", calls_div)

    # Highlight largest differences
    print("\n" + "-" * 80)
    print("TOP 10 LARGEST PRICE DIFFERENCES (absolute)")
    print("-" * 80)
    sorted_results = sorted(results, key=lambda r: abs(r["diff"]), reverse=True)
    print(f"{'Type':>4} {'S':>5} {'T':>5} {'σ':>5} {'q':>5} "
          f"{'BS':>8} {'AM':>8} {'Diff':>8} {'%':>7}")
    for r in sorted_results[:10]:
        print(f"{r['type']:>4} {r['S']:>5} {r['T']:>5.2f} {r['sigma']:>5.2f} {r['q']:>5.2f} "
              f"{r['bs_price']:>8.4f} {r['am_price']:>8.4f} {r['diff']:>8.4f} {r['diff_pct']:>6.2f}%")


def print_greeks_comparison(results: List[Dict]) -> None:
    """Print Greeks comparison table."""
    print("\n" + "=" * 80)
    print("GREEKS COMPARISON (BS vs American)")
    print("=" * 80)

    print(f"\n{'Scenario':<25} {'Δ(BS)':>8} {'Δ(AM)':>8} {'ΔDiff':>8} "
          f"{'Γ(BS)':>8} {'Γ(AM)':>8} {'θ(BS)':>8} {'θ(AM)':>8}")
    print("-" * 95)
    for r in results:
        print(f"{r['scenario']:<25} {r['bs_delta']:>8.4f} {r['am_delta']:>8.4f} "
              f"{r['delta_diff']:>8.4f} {r['bs_gamma']:>8.4f} {r['am_gamma']:>8.4f} "
              f"{r['bs_theta']:>8.4f} {r['am_theta']:>8.4f}")


def print_iv_comparison(results: List[Dict]) -> None:
    """Print IV recovery comparison."""
    print("\n" + "=" * 80)
    print("IV RECOVERY COMPARISON")
    print("=" * 80)
    print("(Price generated with AM model at true σ, then IV recovered via AM and BS)")

    print(f"\n{'Scenario':<20} {'True σ':>7} {'AM Price':>9} "
          f"{'AM IV':>8} {'AM Err':>8} {'BS IV':>8} {'BS Bias':>8}")
    print("-" * 80)
    for r in results:
        am_iv_s = f"{r['am_iv']:.4f}" if r['am_iv'] else "FAIL"
        am_err_s = f"{r['am_iv_error']:.6f}" if r['am_iv_error'] is not None else "N/A"
        bs_iv_s = f"{r['bs_iv']:.4f}" if r['bs_iv'] else "FAIL"
        bs_bias_s = f"{r['bs_iv_bias']:+.6f}" if r['bs_iv_bias'] is not None else "N/A"
        print(f"{r['scenario']:<20} {r['true_sigma']:>7.2f} {r['am_price']:>9.4f} "
              f"{am_iv_s:>8} {am_err_s:>8} {bs_iv_s:>8} {bs_bias_s:>8}")

    print("\nNote: BS IV bias shows systematic error when using European IV for American prices.")
    print("Negative bias = BS overestimates IV (because American price > European for same vol).")


def run_math_comparison(json_output: Optional[str] = None) -> None:
    """Run full math-only comparison."""
    print("Running math-only comparison...\n")

    # 1. Price comparison
    price_results = compare_prices_across_params()
    print_price_summary(price_results)

    # 2. Greeks comparison
    greeks_results = compare_greeks_across_params()
    print_greeks_comparison(greeks_results)

    # 3. IV recovery
    iv_results = compare_iv_recovery()
    print_iv_comparison(iv_results)

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    puts_no_div = [r for r in price_results if r["type"] == "P" and r["q"] == 0.0]
    avg_put_premium = sum(r["diff"] for r in puts_no_div) / len(puts_no_div) if puts_no_div else 0
    max_put_premium = max(r["diff"] for r in puts_no_div) if puts_no_div else 0
    print(f"  Average early exercise premium (puts, no div): ${avg_put_premium:.4f}")
    print(f"  Maximum early exercise premium (puts, no div): ${max_put_premium:.4f}")
    print(f"  Total scenarios tested: {len(price_results)}")

    if json_output:
        output = {
            "prices": price_results,
            "greeks": greeks_results,
            "iv_recovery": iv_results,
        }
        Path(json_output).write_text(json.dumps(output, indent=2))
        print(f"\nResults exported to {json_output}")


# ============================================================
# Market data comparison (requires IBKR)
# ============================================================

def compare_with_market(tickers: List[str], json_output: Optional[str] = None) -> None:
    """Compare BS vs BS2002 against IBKR market data."""
    try:
        from src.tools.data_access import DataAccessLayer
        from src.tools.backends.db_backend import DatabaseBackend
    except ImportError:
        print("ERROR: Cannot import DataAccessLayer. Run from project root.")
        return

    dal = DataAccessLayer(DatabaseBackend())
    all_results = []

    for ticker in tickers:
        ticker = ticker.upper()
        print(f"\n{'='*60}")
        print(f"  {ticker}")
        print(f"{'='*60}")

        # Get IV history for spot price and HV
        iv_points = dal.get_iv_history(ticker)
        if not iv_points:
            print(f"  No IV history data for {ticker}")
            continue

        latest = iv_points[-1]
        spot = latest.spot_price
        hv = latest.hv_30d

        if spot is None:
            print(f"  No spot price available for {ticker}")
            continue

        print(f"  Spot: ${spot:.2f}  HV(30d): {hv:.4f}" if hv else f"  Spot: ${spot:.2f}  HV: N/A")

        # Check for cached option quotes
        cache_key = f"option_quotes_{ticker}"
        quotes = dal.get_from_cache(cache_key, max_age_minutes=120)

        if not quotes:
            print(f"  No cached option quotes. Use IBKR TWS to fetch quotes first.")
            print(f"  (Run: python scripts/analysis/scan_option_mispricing.py {ticker})")
            continue

        print(f"  Found {len(quotes)} option quotes in cache")

        for quote in quotes[:20]:  # Limit to first 20 for readability
            try:
                S = spot
                K = quote.get("strike", 0)
                T = quote.get("tte", 0)  # time to expiry
                r = 0.05
                mid = quote.get("mid", 0)
                opt_type = quote.get("right", "C")
                ibkr_iv = quote.get("iv")

                if not all([K, T, mid]):
                    continue

                bs = black_scholes_price(S, K, T, r, hv or 0.25, opt_type)
                am = bjerksund_stensland_2002(S, K, T, r, hv or 0.25, 0.0, opt_type)

                # IV from each model
                bs_iv = None
                am_iv = None
                try:
                    bs_iv = calculate_implied_volatility(mid, S, K, T, r, opt_type)
                except Exception:
                    pass
                try:
                    am_iv = calculate_american_iv(mid, S, K, T, r, 0.0, opt_type)
                except Exception:
                    pass

                result = {
                    "ticker": ticker,
                    "strike": K,
                    "type": opt_type,
                    "T": round(T, 4),
                    "market_mid": round(mid, 2),
                    "bs_theo": round(bs, 2),
                    "am_theo": round(am, 2),
                    "bs_err": round(bs - mid, 2),
                    "am_err": round(am - mid, 2),
                    "ibkr_iv": round(ibkr_iv, 4) if ibkr_iv else None,
                    "bs_iv": round(bs_iv, 4) if bs_iv else None,
                    "am_iv": round(am_iv, 4) if am_iv else None,
                }
                all_results.append(result)

                print(f"  {opt_type} K={K:>7.1f} T={T:.3f}  "
                      f"Mid=${mid:>7.2f}  BS=${bs:>7.2f}  AM=${am:>7.2f}  "
                      f"IV(IBKR)={ibkr_iv:.3f}" if ibkr_iv else
                      f"  {opt_type} K={K:>7.1f} T={T:.3f}  "
                      f"Mid=${mid:>7.2f}  BS=${bs:>7.2f}  AM=${am:>7.2f}")
            except Exception as e:
                print(f"  Error processing quote: {e}")

    if json_output and all_results:
        Path(json_output).write_text(json.dumps(all_results, indent=2))
        print(f"\nResults exported to {json_output}")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Compare Black-Scholes vs Bjerksund-Stensland 2002 pricing"
    )
    parser.add_argument("tickers", nargs="*", help="Tickers for market data comparison")
    parser.add_argument("--math-only", action="store_true",
                        help="Run math-only comparison (no IBKR needed)")
    parser.add_argument("--json", type=str, default=None,
                        help="Export results to JSON file")
    args = parser.parse_args()

    if args.math_only or not args.tickers:
        run_math_comparison(args.json)
    else:
        compare_with_market(args.tickers, args.json)


if __name__ == "__main__":
    main()