#!/usr/bin/env python3
"""
Financial Datasets API Comprehensive Test Script

Tests ALL API endpoints (Stocks, Crypto, Macroeconomics) and saves raw responses.
Results saved to: comparison_results/financial_datasets/

API Categories:
    - Stocks: 17 endpoints (company facts, prices, news, financials, filings, etc.)
    - Crypto: 3 endpoints (tickers, snapshot, prices)
    - Macroeconomics: 3 endpoints (interest rates)

Usage:
    python scripts/testing/test_financial_datasets_api.py

Environment:
    FINANCIAL_DATASETS_API_KEY - API key (can be in config/.env)
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv("config/.env")

# Configuration
API_KEY = os.getenv("FINANCIAL_DATASETS_API_KEY")
BASE_URL = "https://api.financialdatasets.ai"
OUTPUT_DIR = Path("comparison_results/financial_datasets")
TEST_TICKER = "AAPL"
TEST_CRYPTO = "BTC-USD"  # Crypto format requires exchange pair (e.g., BTC-USD, ETH-USD)

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


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
            "headers": dict(response.headers),
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


def make_post_request(endpoint: str, json_data: dict = None) -> dict:
    """Make POST API request and return response with metadata."""
    url = f"{BASE_URL}{endpoint}"
    headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

    start_time = time.time()
    try:
        response = requests.post(url, headers=headers, json=json_data, timeout=30)
        elapsed = time.time() - start_time

        result = {
            "endpoint": endpoint,
            "json_data": json_data,
            "status_code": response.status_code,
            "elapsed_seconds": round(elapsed, 3),
            "timestamp": datetime.now().isoformat(),
            "headers": dict(response.headers),
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
            "json_data": json_data,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def test_all_endpoints():
    """Test ALL Financial Datasets API endpoints (Stocks, Crypto, Macro)."""

    results_summary = []

    # Date ranges for historical queries
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    # Total endpoints: 23 (17 Stocks + 3 Crypto + 3 Macro)
    TOTAL_ENDPOINTS = 23

    print("=" * 60)
    print("Financial Datasets API Comprehensive Test")
    print(f"Test Ticker: {TEST_TICKER}")
    print(f"Test Crypto: {TEST_CRYPTO}")
    print(f"Total Endpoints: {TOTAL_ENDPOINTS}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    # =========================================================================
    # 1. Company Facts
    # =========================================================================
    print(f"\n[1/{TOTAL_ENDPOINTS}] Testing getCompanyFacts (FREE)...")
    result = make_request(f"/company/facts", {"ticker": TEST_TICKER})
    save_result("01_company_facts", result)
    results_summary.append({
        "name": "getCompanyFacts",
        "endpoint": "/company/facts",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
    })

    # =========================================================================
    # 2. Stock Price Snapshot (Real-time)
    # =========================================================================
    print("\n[2/16] Testing getStockPriceSnapshot...")
    result = make_request(f"/prices/snapshot", {"ticker": TEST_TICKER})
    save_result("02_stock_price_snapshot", result)
    results_summary.append({
        "name": "getStockPriceSnapshot",
        "endpoint": "/prices/snapshot",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
    })

    # =========================================================================
    # 3. Stock Prices (Historical)
    # =========================================================================
    print("\n[3/16] Testing getStockPrices (30 days)...")
    result = make_request(f"/prices", {
        "ticker": TEST_TICKER,
        "interval": "day",
        "interval_multiplier": 1,  # Required: 1 day intervals
        "start_date": start_date,
        "end_date": end_date,
    })
    save_result("03_stock_prices_historical", result)
    results_summary.append({
        "name": "getStockPrices",
        "endpoint": "/prices",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
        "record_count": len(result.get("data", {}).get("prices", [])) if result.get("data") else 0,
    })

    # =========================================================================
    # 4. News
    # =========================================================================
    print("\n[4/16] Testing getNews...")
    result = make_request(f"/news", {"ticker": TEST_TICKER, "limit": 10})
    save_result("04_news", result)
    news_count = len(result.get("data", {}).get("news", [])) if result.get("data") else 0
    results_summary.append({
        "name": "getNews",
        "endpoint": "/news",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
        "record_count": news_count,
    })

    # =========================================================================
    # 5. Income Statement
    # =========================================================================
    print("\n[5/16] Testing getIncomeStatement...")
    result = make_request(f"/financials/income-statements", {
        "ticker": TEST_TICKER,
        "period": "annual",
        "limit": 5,
    })
    save_result("05_income_statement", result)
    results_summary.append({
        "name": "getIncomeStatement",
        "endpoint": "/financials/income-statements",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
        "record_count": len(result.get("data", {}).get("income_statements", [])) if result.get("data") else 0,
    })

    # =========================================================================
    # 6. Balance Sheet
    # =========================================================================
    print("\n[6/16] Testing getBalanceSheet...")
    result = make_request(f"/financials/balance-sheets", {
        "ticker": TEST_TICKER,
        "period": "annual",
        "limit": 5,
    })
    save_result("06_balance_sheet", result)
    results_summary.append({
        "name": "getBalanceSheet",
        "endpoint": "/financials/balance-sheets",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
        "record_count": len(result.get("data", {}).get("balance_sheets", [])) if result.get("data") else 0,
    })

    # =========================================================================
    # 7. Cash Flow Statement
    # =========================================================================
    print("\n[7/16] Testing getCashFlowStatement...")
    result = make_request(f"/financials/cash-flow-statements", {
        "ticker": TEST_TICKER,
        "period": "annual",
        "limit": 5,
    })
    save_result("07_cash_flow_statement", result)
    results_summary.append({
        "name": "getCashFlowStatement",
        "endpoint": "/financials/cash-flow-statements",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
        "record_count": len(result.get("data", {}).get("cash_flow_statements", [])) if result.get("data") else 0,
    })

    # =========================================================================
    # 8. SEC Filings List
    # =========================================================================
    print("\n[8/16] Testing getFilings...")
    result = make_request(f"/filings", {
        "ticker": TEST_TICKER,
        "form_type": "10-K",
        "limit": 5,
    })
    save_result("08_filings_list", result)
    filings_data = result.get("data", {}).get("filings", []) if result.get("data") else []
    results_summary.append({
        "name": "getFilings",
        "endpoint": "/filings",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
        "record_count": len(filings_data),
    })

    # =========================================================================
    # 9. Filing Items (Specific Section Extraction)
    # NOTE: /filings/items/available endpoint does NOT exist in the API
    # The API only provides /filings and /filings/items
    # Using /filings/items with Item-1A (Risk Factors) as the standard test
    # =========================================================================
    print("\n[9/16] Testing getFilingItems (Item-1A)...")
    result = make_request(f"/filings/items", {
        "ticker": TEST_TICKER,
        "filing_type": "10-K",
        "year": 2024,
        "item": "Item-1A",  # Risk Factors section
    })
    save_result("09_filing_items_1a", result)
    results_summary.append({
        "name": "getFilingItems",
        "endpoint": "/filings/items",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
    })

    # =========================================================================
    # 10. Filing Items (Extract different section - MD&A)
    # =========================================================================
    print("\n[10/16] Testing getFilingItems (Item-7 MD&A)...")
    result = make_request(f"/filings/items", {
        "ticker": TEST_TICKER,
        "filing_type": "10-K",
        "year": 2024,
        "item": "Item-7",  # Management Discussion & Analysis
    })
    save_result("10_filing_items_mda", result)
    results_summary.append({
        "name": "getFilingItems_MDA",
        "endpoint": "/filings/items",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
    })

    # =========================================================================
    # 11. Financial Metrics (Historical)
    # =========================================================================
    print("\n[11/16] Testing getFinancialMetrics...")
    result = make_request(f"/financial-metrics", {
        "ticker": TEST_TICKER,
        "period": "annual",
        "limit": 5,
    })
    save_result("11_financial_metrics", result)
    results_summary.append({
        "name": "getFinancialMetrics",
        "endpoint": "/financial-metrics",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
        "record_count": len(result.get("data", {}).get("financial_metrics", [])) if result.get("data") else 0,
    })

    # =========================================================================
    # 12. Financial Metrics Snapshot
    # =========================================================================
    print("\n[12/16] Testing getFinancialMetricsSnapshot...")
    result = make_request(f"/financial-metrics/snapshot", {"ticker": TEST_TICKER})
    save_result("12_financial_metrics_snapshot", result)
    results_summary.append({
        "name": "getFinancialMetricsSnapshot",
        "endpoint": "/financial-metrics/snapshot",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
    })

    # =========================================================================
    # 13. Analyst Estimates
    # =========================================================================
    print(f"\n[13/{TOTAL_ENDPOINTS}] Testing getAnalystEstimates...")
    result = make_request(f"/analyst-estimates", {
        "ticker": TEST_TICKER,
        "limit": 5,
    })
    save_result("13_analyst_estimates", result)
    results_summary.append({
        "name": "getAnalystEstimates",
        "endpoint": "/analyst-estimates",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
        "record_count": len(result.get("data", {}).get("analyst_estimates", [])) if result.get("data") else 0,
    })

    # =========================================================================
    # 14. Insider Trades (NEW)
    # =========================================================================
    print(f"\n[14/{TOTAL_ENDPOINTS}] Testing getInsiderTrades...")
    result = make_request(f"/insider-trades", {
        "ticker": TEST_TICKER,
        "limit": 10,
    })
    save_result("14_insider_trades", result)
    results_summary.append({
        "name": "getInsiderTrades",
        "endpoint": "/insider-trades",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
        "record_count": len(result.get("data", {}).get("insider_trades", [])) if result.get("data") else 0,
    })

    # =========================================================================
    # 15. Institutional Ownership (NEW)
    # =========================================================================
    print(f"\n[15/{TOTAL_ENDPOINTS}] Testing getInstitutionalOwnership...")
    result = make_request(f"/institutional-ownership", {
        "ticker": TEST_TICKER,
        "limit": 10,
    })
    save_result("15_institutional_ownership", result)
    results_summary.append({
        "name": "getInstitutionalOwnership",
        "endpoint": "/institutional-ownership",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
        "record_count": len(result.get("data", {}).get("institutional_ownership", [])) if result.get("data") else 0,
    })

    # =========================================================================
    # 16. Segmented Revenues (NEW)
    # =========================================================================
    print(f"\n[16/{TOTAL_ENDPOINTS}] Testing getSegmentedRevenues...")
    result = make_request(f"/financials/segmented-revenues", {
        "ticker": TEST_TICKER,
        "period": "annual",
        "limit": 5,
    })
    save_result("16_segmented_revenues", result)
    results_summary.append({
        "name": "getSegmentedRevenues",
        "endpoint": "/financials/segmented-revenues",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
        "record_count": len(result.get("data", {}).get("segmented_revenues", [])) if result.get("data") else 0,
    })

    # =========================================================================
    # 17. All Financial Statements Combined (NEW)
    # =========================================================================
    print(f"\n[17/{TOTAL_ENDPOINTS}] Testing getAllFinancials...")
    result = make_request(f"/financials", {
        "ticker": TEST_TICKER,
        "period": "annual",
        "limit": 2,
    })
    save_result("17_all_financials", result)
    results_summary.append({
        "name": "getAllFinancials",
        "endpoint": "/financials",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
    })

    # =========================================================================
    # 18. Earnings Press Releases (NEW - FREE $0.00)
    # NOTE: This endpoint only supports specific tickers (NOT AAPL).
    #       See /earnings/press-releases/tickers/ for supported list.
    #       Using COST as test ticker (confirmed supported).
    # =========================================================================
    print(f"\n[18/{TOTAL_ENDPOINTS}] Testing getEarningsPressReleases (FREE)...")
    result = make_request(f"/earnings/press-releases", {
        "ticker": "COST",  # AAPL not supported; COST is on the supported list
    })
    save_result("18_earnings_press_releases", result)
    results_summary.append({
        "name": "getEarningsPressReleases",
        "endpoint": "/earnings/press-releases",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
        "record_count": len(result.get("data", {}).get("press_releases", [])) if result.get("data") else 0,
    })

    # =========================================================================
    # 19. Available Stock Tickers (NEW)
    # =========================================================================
    print(f"\n[19/{TOTAL_ENDPOINTS}] Testing getAvailableStockTickers...")
    result = make_request(f"/prices/snapshot/tickers/")
    save_result("19_stock_tickers", result)
    results_summary.append({
        "name": "getAvailableStockTickers",
        "endpoint": "/prices/snapshot/tickers/",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
        "record_count": len(result.get("data", {}).get("tickers", [])) if result.get("data") else 0,
    })

    # =========================================================================
    # 20. Available Crypto Tickers
    # =========================================================================
    print(f"\n[20/{TOTAL_ENDPOINTS}] Testing getAvailableCryptoTickers...")
    # NOTE: Correct endpoint is /crypto/prices/tickers/ (with trailing slash)
    result = make_request(f"/crypto/prices/tickers/")
    save_result("20_crypto_tickers", result)
    results_summary.append({
        "name": "getAvailableCryptoTickers",
        "endpoint": "/crypto/prices/tickers/",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
        "record_count": len(result.get("data", {}).get("tickers", [])) if result.get("data") else 0,
    })

    # =========================================================================
    # 21. Crypto Price Snapshot
    # =========================================================================
    print(f"\n[21/{TOTAL_ENDPOINTS}] Testing getCryptoPriceSnapshot...")
    result = make_request(f"/crypto/prices/snapshot", {"ticker": TEST_CRYPTO})
    save_result("21_crypto_price_snapshot", result)
    results_summary.append({
        "name": "getCryptoPriceSnapshot",
        "endpoint": "/crypto/prices/snapshot",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
    })

    # =========================================================================
    # 22. Crypto Prices (Historical)
    # =========================================================================
    print(f"\n[22/{TOTAL_ENDPOINTS}] Testing getCryptoPrices (30 days)...")
    result = make_request(f"/crypto/prices", {
        "ticker": TEST_CRYPTO,
        "interval": "day",
        "interval_multiplier": 1,  # Required: 1 day intervals
        "start_date": start_date,
        "end_date": end_date,
    })
    save_result("22_crypto_prices_historical", result)
    results_summary.append({
        "name": "getCryptoPrices",
        "endpoint": "/crypto/prices",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
        "record_count": len(result.get("data", {}).get("prices", [])) if result.get("data") else 0,
    })

    # =========================================================================
    # 23. Macro Interest Rates Snapshot (NEW)
    # =========================================================================
    print(f"\n[23/{TOTAL_ENDPOINTS}] Testing getMacroInterestRatesSnapshot...")
    result = make_request(f"/macro/interest-rates/snapshot")
    save_result("23_macro_interest_rates_snapshot", result)
    results_summary.append({
        "name": "getMacroInterestRatesSnapshot",
        "endpoint": "/macro/interest-rates/snapshot",
        "status": result.get("status_code"),
        "elapsed": result.get("elapsed_seconds"),
        "record_count": len(result.get("data", {}).get("interest_rates", [])) if result.get("data") else 0,
    })

    # =========================================================================
    # Save Summary
    # =========================================================================
    print("\n" + "=" * 60)
    print("Saving summary...")

    summary = {
        "test_info": {
            "timestamp": datetime.now().isoformat(),
            "test_ticker": TEST_TICKER,
            "test_crypto": TEST_CRYPTO,
            "api_base_url": BASE_URL,
            "date_range": f"{start_date} to {end_date}",
        },
        "results": results_summary,
        "statistics": {
            "total_endpoints": len(results_summary),
            "successful": sum(1 for r in results_summary if r.get("status") == 200),
            "failed": sum(1 for r in results_summary if r.get("status") != 200),
            "total_time": sum(r.get("elapsed") or 0 for r in results_summary),
        }
    }

    save_result("00_test_summary", summary)

    # Generate markdown report
    generate_markdown_report(summary, results_summary)

    print("\n" + "=" * 60)
    print("Test Complete!")
    print(f"Results saved to: {OUTPUT_DIR}/")
    print(f"Total endpoints tested: {summary['statistics']['total_endpoints']}")
    print(f"Successful: {summary['statistics']['successful']}")
    print(f"Failed: {summary['statistics']['failed']}")
    print(f"Total time: {summary['statistics']['total_time']:.2f}s")
    print("=" * 60)


def generate_markdown_report(summary: dict, results: list):
    """Generate a markdown summary report."""

    report = f"""# Financial Datasets API Test Report

> Generated: {summary['test_info']['timestamp']}
> Test Ticker: {summary['test_info']['test_ticker']}
> Test Crypto: {summary['test_info']['test_crypto']}

## Summary

| Metric | Value |
|--------|-------|
| Total Endpoints | {summary['statistics']['total_endpoints']} |
| Successful | {summary['statistics']['successful']} |
| Failed | {summary['statistics']['failed']} |
| Total Time | {summary['statistics']['total_time']:.2f}s |

## Results by Endpoint

| # | Endpoint | Status | Time (s) | Records |
|---|----------|--------|----------|---------|
"""

    for i, r in enumerate(results, 1):
        status_emoji = "✅" if r.get("status") == 200 else "❌"
        record_count = r.get("record_count", "-")
        elapsed = r.get('elapsed') or 0
        report += f"| {i} | {r['name']} | {status_emoji} {r.get('status', 'N/A')} | {elapsed:.3f} | {record_count} |\n"

    report += f"""
## Raw Response Files

All raw JSON responses are saved in `comparison_results/financial_datasets/`:

| File | Description |
|------|-------------|
| `00_test_summary.json` | Test summary and statistics |
| `01_company_facts.json` | Company information (market cap, sector, etc.) |
| `02_stock_price_snapshot.json` | Real-time stock price |
| `03_stock_prices_historical.json` | 30-day historical prices |
| `04_news.json` | Recent news articles |
| `05_income_statement.json` | Annual income statements (5 years) |
| `06_balance_sheet.json` | Annual balance sheets (5 years) |
| `07_cash_flow_statement.json` | Annual cash flow statements (5 years) |
| `08_filings_list.json` | SEC 10-K filings list |
| `09_available_filing_items.json` | Available filing sections to extract |
| `10_filing_items_risk_factors.json` | Extracted risk factors section |
| `11_financial_metrics.json` | Historical financial ratios |
| `12_financial_metrics_snapshot.json` | Current financial ratios |
| `13_analyst_estimates.json` | EPS estimates |
| `14_crypto_tickers.json` | Available crypto tickers |
| `15_crypto_price_snapshot.json` | Real-time BTC price |
| `16_crypto_prices_historical.json` | 30-day BTC prices |

## Usage Notes

To re-run this test:
```bash
python scripts/testing/test_financial_datasets_api.py
```

Requires `FINANCIAL_DATASETS_API_KEY` in `config/.env`.
"""

    report_path = OUTPUT_DIR / "TEST_REPORT.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  Saved: {report_path}")


if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: FINANCIAL_DATASETS_API_KEY not found!")
        print("Please set it in config/.env or environment variable.")
        exit(1)

    print(f"API Key found: {API_KEY[:8]}...{API_KEY[-4:]}")
    test_all_endpoints()