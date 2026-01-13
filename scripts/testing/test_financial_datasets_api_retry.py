#!/usr/bin/env python3
"""
Financial Datasets API - Retry Failed Endpoints (Fixed with Context7 docs)

Parameters corrected based on official documentation:
- /prices: interval_multiplier is REQUIRED
- /crypto/prices: ticker format is "BTC-USD"
- /filings/items: item format is "Item-1A", year is REQUIRED
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("config/.env")

API_KEY = os.getenv("FINANCIAL_DATASETS_API_KEY")
BASE_URL = "https://api.financialdatasets.ai"
OUTPUT_DIR = Path("comparison_results/financial_datasets")
TEST_TICKER = "AAPL"


def make_request(endpoint: str, params: dict = None) -> dict:
    """Make API request and return response with metadata."""
    url = f"{BASE_URL}{endpoint}"
    headers = {"X-API-Key": API_KEY}

    start_time = time.time()
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        elapsed = time.time() - start_time

        result = {
            "endpoint": endpoint,
            "params": params,
            "status_code": response.status_code,
            "elapsed_seconds": round(elapsed, 3),
            "timestamp": datetime.now().isoformat(),
        }

        try:
            result["data"] = response.json()
        except json.JSONDecodeError:
            result["data"] = None
            result["raw_text"] = response.text[:1000]

        return result

    except requests.RequestException as e:
        return {
            "endpoint": endpoint,
            "params": params,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def save_result(name: str, result: dict):
    """Save result to JSON file."""
    filepath = OUTPUT_DIR / f"{name}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Saved: {filepath}")
    return result


def test_failed_endpoints():
    """Re-test the 6 failed endpoints with corrected parameters from Context7 docs."""

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    print("=" * 60)
    print("Financial Datasets API - Retry with Context7 Docs")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    results = []

    # =========================================================================
    # Fix 1: Stock Prices - interval_multiplier is REQUIRED
    # Doc: https://docs.financialdatasets.ai/api-reference/endpoint/prices
    # =========================================================================
    print("\n[1/6] /prices - adding interval_multiplier=1 (REQUIRED)...")
    result = make_request("/prices", {
        "ticker": TEST_TICKER,
        "interval": "day",
        "interval_multiplier": 1,  # REQUIRED per docs
        "start_date": start_date,
        "end_date": end_date,
    })
    save_result("03_stock_prices_historical", result)

    if result.get("status_code") == 200:
        prices = result.get("data", {}).get("prices", [])
        results.append(("getStockPrices", 200, f"{len(prices)} prices"))
    else:
        error_msg = result.get("data", {}).get("error", "unknown")
        results.append(("getStockPrices", result.get("status_code"), error_msg))

    # =========================================================================
    # Fix 2: Filing Items - year is REQUIRED, item format is "Item-1A"
    # Doc: https://docs.financialdatasets.ai/api-reference/endpoint/filings/items
    # =========================================================================
    print("\n[2/6] /filings/items - adding year=2024, item='Item-1A'...")
    result = make_request("/filings/items", {
        "ticker": TEST_TICKER,
        "filing_type": "10-K",  # REQUIRED
        "year": 2024,          # REQUIRED per docs
        "item": "Item-1A",     # Risk Factors section (correct format)
    })
    save_result("10_filing_items_risk_factors", result)

    if result.get("status_code") == 200:
        items = result.get("data", {}).get("items", [])
        results.append(("getFilingItems", 200, f"{len(items)} items"))
    else:
        error_msg = result.get("data", {}).get("error", "unknown")
        results.append(("getFilingItems", result.get("status_code"), error_msg))

    # =========================================================================
    # Fix 3: Crypto Price Snapshot - ticker format is "BTC-USD"
    # Doc: https://docs.financialdatasets.ai/api-reference/endpoint/crypto
    # =========================================================================
    print("\n[3/6] /crypto/prices/snapshot - using ticker='BTC-USD'...")
    result = make_request("/crypto/prices/snapshot", {
        "ticker": "BTC-USD",  # Correct format per docs
    })
    save_result("15_crypto_price_snapshot", result)

    if result.get("status_code") == 200:
        results.append(("getCryptoPriceSnapshot", 200, "success"))
    else:
        error_msg = result.get("data", {}).get("error", "unknown")
        results.append(("getCryptoPriceSnapshot", result.get("status_code"), error_msg))

    # =========================================================================
    # Fix 4: Crypto Prices Historical - ticker="BTC-USD", interval_multiplier=1
    # Doc: https://docs.financialdatasets.ai/api-reference/endpoint/crypto/historical
    # =========================================================================
    print("\n[4/6] /crypto/prices - ticker='BTC-USD', interval_multiplier=1...")
    result = make_request("/crypto/prices", {
        "ticker": "BTC-USD",         # Correct format
        "interval": "day",
        "interval_multiplier": 1,    # REQUIRED
        "start_date": start_date,
        "end_date": end_date,
    })
    save_result("16_crypto_prices_historical", result)

    if result.get("status_code") == 200:
        prices = result.get("data", {}).get("prices", [])
        results.append(("getCryptoPrices", 200, f"{len(prices)} prices"))
    else:
        error_msg = result.get("data", {}).get("error", "unknown")
        results.append(("getCryptoPrices", result.get("status_code"), error_msg))

    # =========================================================================
    # Fix 5: Available Crypto Tickers
    # =========================================================================
    print("\n[5/6] /crypto/tickers - getting available tickers...")
    result = make_request("/crypto/tickers")
    save_result("14_crypto_tickers", result)

    if result.get("status_code") == 200:
        tickers = result.get("data", {}).get("tickers", [])
        results.append(("getCryptoTickers", 200, f"{len(tickers)} tickers"))
    else:
        error_msg = result.get("data", {}).get("error", "unknown")
        results.append(("getCryptoTickers", result.get("status_code"), error_msg))

    # =========================================================================
    # Fix 6: Available Filing Items
    # =========================================================================
    print("\n[6/6] /filings/items/available - checking endpoint...")
    result = make_request("/filings/items/available")
    save_result("09_available_filing_items", result)

    if result.get("status_code") == 200:
        results.append(("getAvailableFilingItems", 200, "success"))
    else:
        error_msg = result.get("data", {}).get("error", "unknown")
        results.append(("getAvailableFilingItems", result.get("status_code"), error_msg))

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 60)
    print("Retry Results Summary")
    print("=" * 60)

    success = 0
    for name, status, info in results:
        emoji = "✅" if status == 200 else "❌"
        print(f"{emoji} {name}: {status} - {info}")
        if status == 200:
            success += 1

    print(f"\nFixed: {success}/6 endpoints")
    print("=" * 60)

    # Update test summary
    summary_path = OUTPUT_DIR / "00_test_summary.json"
    if summary_path.exists():
        with open(summary_path) as f:
            summary = json.load(f)

        summary["retry_results"] = {
            "timestamp": datetime.now().isoformat(),
            "results": [{"endpoint": r[0], "status": r[1], "info": str(r[2])} for r in results],
            "success_count": success,
            "total_count": 6,
        }
        summary["statistics"]["successful"] = 10 + success  # Original 10 + fixed
        summary["statistics"]["failed"] = 6 - success

        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nUpdated: {summary_path}")


if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: FINANCIAL_DATASETS_API_KEY not found!")
        exit(1)

    test_failed_endpoints()