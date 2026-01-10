"""
IBKR TWS API - Complete Free API Test Suite

This script tests ALL IBKR API functions to identify which are:
- FREE and working
- FREE but not working
- PAID (requires subscription)

Based on official documentation and actual testing.

Usage:
    python -m data_sources.test_ibkr_all_free_apis

Sources:
- https://www.interactivebrokers.com/en/pricing/market-data-pricing.php
- https://interactivebrokers.github.io/tws-api/fundamentals.html
- https://www.interactivebrokers.com/campus/ibkr-api-page/market-data-subscriptions/
"""

import os
import sys
import json
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ib_insync import IB, Stock, Option, util
    from bs4 import BeautifulSoup
    HAS_DEPS = True
except ImportError as e:
    HAS_DEPS = False
    print(f"Missing dependencies: {e}")

from dotenv import load_dotenv
load_dotenv("config/.env")


@dataclass
class TestResult:
    """Test result for an API function."""
    api_name: str
    status: str  # 'FREE_OK', 'FREE_FAIL', 'PAID_REQUIRED', 'ERROR'
    data_size: int  # bytes or record count
    error_code: Optional[int] = None
    error_message: Optional[str] = None
    notes: Optional[str] = None
    sample_data: Optional[str] = None


class IBKRFreeAPITester:
    """Test all IBKR API functions to identify free vs paid."""

    def __init__(self, host: str = None, port: int = None, client_id: int = 102):
        self.host = host or os.getenv("IBKR_HOST", "127.0.0.1")
        self.port = port or int(os.getenv("IBKR_PORT", "7497"))
        self.client_id = client_id
        self.ib: Optional[IB] = None
        self.results: List[TestResult] = []

    def connect(self) -> bool:
        """Connect to TWS/IB Gateway."""
        print(f"\n{'='*60}")
        print(f"Connecting to IBKR at {self.host}:{self.port}...")
        print(f"{'='*60}")

        self.ib = IB()
        try:
            self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=30)
            print(f"Connected! Server version: {self.ib.client.serverVersion()}")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from IBKR."""
        if self.ib:
            self.ib.disconnect()

    def add_result(self, result: TestResult):
        """Add a test result."""
        self.results.append(result)
        status_icon = {
            'FREE_OK': '✅',
            'FREE_FAIL': '⚠️',
            'PAID_REQUIRED': '💰',
            'ERROR': '❌'
        }.get(result.status, '?')

        print(f"  {status_icon} {result.api_name}: {result.status}")
        if result.data_size > 0:
            print(f"      Data: {result.data_size:,} bytes/records")
        if result.error_message:
            print(f"      Error: {result.error_message[:80]}")
        if result.notes:
            print(f"      Notes: {result.notes}")

    # =========================================================================
    # FREE API Tests
    # =========================================================================

    def test_contract_details(self, ticker: str = "AAPL") -> TestResult:
        """Test reqContractDetails - should be FREE."""
        print("\n[Test] Contract Details (reqContractDetails)")
        try:
            contract = Stock(ticker, "SMART", "USD")
            self.ib.qualifyContracts(contract)
            details = self.ib.reqContractDetails(contract)

            if details:
                return TestResult(
                    api_name="reqContractDetails",
                    status="FREE_OK",
                    data_size=len(details),
                    notes=f"Got {len(details)} contract detail(s) for {ticker}",
                    sample_data=str(details[0].longName if details else None)
                )
            else:
                return TestResult(
                    api_name="reqContractDetails",
                    status="FREE_FAIL",
                    data_size=0,
                    notes="No data returned"
                )
        except Exception as e:
            return TestResult(
                api_name="reqContractDetails",
                status="ERROR",
                data_size=0,
                error_message=str(e)
            )

    def test_option_chain(self, ticker: str = "AAPL") -> TestResult:
        """Test reqSecDefOptParams - should be FREE."""
        print("\n[Test] Option Chain (reqSecDefOptParams)")
        try:
            stock = Stock(ticker, "SMART", "USD")
            self.ib.qualifyContracts(stock)
            chains = self.ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)

            if chains:
                total_expirations = sum(len(c.expirations) for c in chains)
                total_strikes = sum(len(c.strikes) for c in chains)
                return TestResult(
                    api_name="reqSecDefOptParams",
                    status="FREE_OK",
                    data_size=len(chains),
                    notes=f"{len(chains)} exchanges, {total_expirations} expirations, {total_strikes} strikes"
                )
            else:
                return TestResult(
                    api_name="reqSecDefOptParams",
                    status="FREE_FAIL",
                    data_size=0
                )
        except Exception as e:
            return TestResult(
                api_name="reqSecDefOptParams",
                status="ERROR",
                data_size=0,
                error_message=str(e)
            )

    def test_fundamental_data(self, ticker: str = "AAPL") -> List[TestResult]:
        """Test reqFundamentalData - various report types."""
        print("\n[Test] Fundamental Data (reqFundamentalData)")
        results = []

        report_types = [
            ("ReportSnapshot", "Financial ratios overview"),
            ("ReportsFinSummary", "Financial summary"),
            ("ReportsOwnership", "Institutional ownership"),
            ("ReportsFinStatements", "Financial statements (may require sub)"),
            ("RESC", "Analyst estimates (often not working)"),
            ("CalendarReport", "WSH calendar (requires subscription)"),
        ]

        contract = Stock(ticker, "SMART", "USD")
        self.ib.qualifyContracts(contract)

        for report_type, description in report_types:
            print(f"  Testing {report_type}...")
            try:
                xml_data = self.ib.reqFundamentalData(contract, report_type)

                if xml_data and len(xml_data) > 0:
                    results.append(TestResult(
                        api_name=f"reqFundamentalData({report_type})",
                        status="FREE_OK",
                        data_size=len(xml_data),
                        notes=description
                    ))
                else:
                    results.append(TestResult(
                        api_name=f"reqFundamentalData({report_type})",
                        status="FREE_FAIL",
                        data_size=0,
                        notes=f"No data - {description}"
                    ))
            except Exception as e:
                error_str = str(e)
                if "430" in error_str:
                    status = "PAID_REQUIRED"
                    notes = "Error 430 - Subscription required"
                elif "Not allowed" in error_str:
                    status = "PAID_REQUIRED"
                    notes = "Not allowed - requires subscription"
                else:
                    status = "ERROR"
                    notes = description

                results.append(TestResult(
                    api_name=f"reqFundamentalData({report_type})",
                    status=status,
                    data_size=0,
                    error_message=error_str[:100] if len(error_str) > 100 else error_str,
                    notes=notes
                ))

            self.ib.sleep(1)  # Rate limiting

        return results

    def test_historical_data(self, ticker: str = "AAPL") -> TestResult:
        """Test reqHistoricalData - should be FREE for EOD."""
        print("\n[Test] Historical Data (reqHistoricalData)")
        try:
            contract = Stock(ticker, "SMART", "USD")
            self.ib.qualifyContracts(contract)

            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr='30 D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True
            )

            if bars:
                return TestResult(
                    api_name="reqHistoricalData (daily)",
                    status="FREE_OK",
                    data_size=len(bars),
                    notes=f"{len(bars)} daily bars"
                )
            else:
                return TestResult(
                    api_name="reqHistoricalData (daily)",
                    status="FREE_FAIL",
                    data_size=0
                )
        except Exception as e:
            return TestResult(
                api_name="reqHistoricalData (daily)",
                status="ERROR",
                data_size=0,
                error_message=str(e)
            )

    def test_news_providers(self) -> TestResult:
        """Test reqNewsProviders - should be FREE."""
        print("\n[Test] News Providers (reqNewsProviders)")
        try:
            providers = self.ib.reqNewsProviders()

            if providers:
                provider_codes = [p.code for p in providers]
                return TestResult(
                    api_name="reqNewsProviders",
                    status="FREE_OK",
                    data_size=len(providers),
                    notes=f"Providers: {', '.join(provider_codes[:5])}{'...' if len(provider_codes) > 5 else ''}"
                )
            else:
                return TestResult(
                    api_name="reqNewsProviders",
                    status="FREE_FAIL",
                    data_size=0
                )
        except Exception as e:
            return TestResult(
                api_name="reqNewsProviders",
                status="ERROR",
                data_size=0,
                error_message=str(e)
            )

    def test_historical_news(self, ticker: str = "AAPL") -> TestResult:
        """Test reqHistoricalNews - should be FREE for headlines."""
        print("\n[Test] Historical News (reqHistoricalNews)")
        try:
            contract = Stock(ticker, "SMART", "USD")
            self.ib.qualifyContracts(contract)

            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            news = self.ib.reqHistoricalNews(
                contract.conId,
                providerCodes='',  # All providers
                startDateTime='',
                endDateTime=end_time,
                totalResults=50
            )

            if news:
                return TestResult(
                    api_name="reqHistoricalNews",
                    status="FREE_OK",
                    data_size=len(news),
                    notes=f"{len(news)} news headlines"
                )
            else:
                return TestResult(
                    api_name="reqHistoricalNews",
                    status="FREE_FAIL",
                    data_size=0,
                    notes="No news returned"
                )
        except Exception as e:
            return TestResult(
                api_name="reqHistoricalNews",
                status="ERROR",
                data_size=0,
                error_message=str(e)
            )

    def test_scanner(self) -> TestResult:
        """Test reqScannerSubscription - should be FREE for some scanners."""
        print("\n[Test] Market Scanner (reqScannerSubscription)")
        try:
            from ib_insync import ScannerSubscription

            scanner = ScannerSubscription(
                instrument='STK',
                locationCode='STK.US.MAJOR',
                scanCode='MOST_ACTIVE'
            )
            results = self.ib.reqScannerData(scanner)

            if results:
                return TestResult(
                    api_name="reqScannerSubscription",
                    status="FREE_OK",
                    data_size=len(results),
                    notes=f"{len(results)} scanner results"
                )
            else:
                return TestResult(
                    api_name="reqScannerSubscription",
                    status="FREE_FAIL",
                    data_size=0
                )
        except Exception as e:
            return TestResult(
                api_name="reqScannerSubscription",
                status="ERROR",
                data_size=0,
                error_message=str(e)
            )

    # =========================================================================
    # PAID API Tests (expected to fail without subscription)
    # =========================================================================

    def test_realtime_market_data(self, ticker: str = "AAPL") -> TestResult:
        """Test reqMktData - requires subscription for API."""
        print("\n[Test] Real-time Market Data (reqMktData) - PAID")
        try:
            contract = Stock(ticker, "SMART", "USD")
            self.ib.qualifyContracts(contract)

            ticker_data = self.ib.reqMktData(contract, '', False, False)
            self.ib.sleep(3)

            # Check if we got data
            import math
            has_data = (
                ticker_data.last is not None and
                not (isinstance(ticker_data.last, float) and math.isnan(ticker_data.last))
            )

            self.ib.cancelMktData(contract)

            if has_data:
                return TestResult(
                    api_name="reqMktData (real-time)",
                    status="FREE_OK",
                    data_size=1,
                    notes=f"Last: ${ticker_data.last}"
                )
            else:
                return TestResult(
                    api_name="reqMktData (real-time)",
                    status="PAID_REQUIRED",
                    data_size=0,
                    error_code=10089,
                    notes="Requires market data subscription for API ($1.50-$10/month)"
                )
        except Exception as e:
            error_str = str(e)
            if "10089" in error_str or "10091" in error_str:
                return TestResult(
                    api_name="reqMktData (real-time)",
                    status="PAID_REQUIRED",
                    data_size=0,
                    error_message=error_str[:100],
                    notes="Requires US Equity/Options subscription"
                )
            return TestResult(
                api_name="reqMktData (real-time)",
                status="ERROR",
                data_size=0,
                error_message=str(e)
            )

    def test_option_greeks(self, ticker: str = "AAPL") -> TestResult:
        """Test option Greeks - requires subscription for API."""
        print("\n[Test] Option Greeks (reqMktData with option) - PAID")
        try:
            stock = Stock(ticker, "SMART", "USD")
            self.ib.qualifyContracts(stock)

            # Get nearest expiration
            chains = self.ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
            if not chains:
                return TestResult(
                    api_name="Option Greeks",
                    status="ERROR",
                    data_size=0,
                    notes="No option chain"
                )

            expirations = sorted(chains[0].expirations)
            today = datetime.now().strftime('%Y%m%d')
            expiration = None
            for exp in expirations:
                if exp > today:
                    expiration = exp
                    break

            if not expiration:
                return TestResult(
                    api_name="Option Greeks",
                    status="ERROR",
                    data_size=0,
                    notes="No future expiration"
                )

            # Use ATM strike
            atm_strike = 250  # Approximate for AAPL
            option = Option(ticker, expiration, atm_strike, 'C', "SMART")
            self.ib.qualifyContracts(option)

            ticker_data = self.ib.reqMktData(option, '100,101,104,106', False, False)
            self.ib.sleep(5)

            has_greeks = ticker_data.modelGreeks is not None

            self.ib.cancelMktData(option)

            if has_greeks:
                mg = ticker_data.modelGreeks
                return TestResult(
                    api_name="Option Greeks",
                    status="FREE_OK",
                    data_size=1,
                    notes=f"Delta: {mg.delta}, IV: {mg.impliedVol}"
                )
            else:
                return TestResult(
                    api_name="Option Greeks",
                    status="PAID_REQUIRED",
                    data_size=0,
                    notes="Requires OPRA L1 subscription ($1.50 Non-Pro / $32.75 Pro)"
                )
        except Exception as e:
            return TestResult(
                api_name="Option Greeks",
                status="PAID_REQUIRED",
                data_size=0,
                error_message=str(e)[:100],
                notes="Requires real-time options data subscription"
            )

    def test_tick_by_tick(self, ticker: str = "AAPL") -> TestResult:
        """Test reqTickByTickData - requires subscription."""
        print("\n[Test] Tick-by-Tick Data (reqTickByTickData) - PAID")
        try:
            contract = Stock(ticker, "SMART", "USD")
            self.ib.qualifyContracts(contract)

            ticks = []
            def on_tick(tick):
                ticks.append(tick)

            self.ib.reqTickByTickData(contract, 'Last', 0, False)
            self.ib.sleep(3)
            self.ib.cancelTickByTickData(contract, 'Last')

            if ticks:
                return TestResult(
                    api_name="reqTickByTickData",
                    status="FREE_OK",
                    data_size=len(ticks),
                    notes=f"Got {len(ticks)} ticks"
                )
            else:
                return TestResult(
                    api_name="reqTickByTickData",
                    status="PAID_REQUIRED",
                    data_size=0,
                    notes="Requires market data subscription"
                )
        except Exception as e:
            return TestResult(
                api_name="reqTickByTickData",
                status="PAID_REQUIRED",
                data_size=0,
                error_message=str(e)[:100]
            )

    def run_all_tests(self):
        """Run all API tests."""
        print("""
╔═══════════════════════════════════════════════════════════════╗
║     IBKR TWS API - Complete Free API Test Suite               ║
║                                                               ║
║  Testing which APIs are free vs require subscription          ║
╚═══════════════════════════════════════════════════════════════╝
        """)

        if not self.connect():
            print("Failed to connect to IBKR")
            return

        try:
            print("\n" + "="*60)
            print("SECTION 1: FREE APIs")
            print("="*60)

            # Free APIs
            self.add_result(self.test_contract_details())
            self.add_result(self.test_option_chain())
            self.add_result(self.test_historical_data())
            self.add_result(self.test_news_providers())
            self.add_result(self.test_historical_news())
            self.add_result(self.test_scanner())

            # Fundamental data (various report types)
            fund_results = self.test_fundamental_data()
            for result in fund_results:
                self.add_result(result)

            print("\n" + "="*60)
            print("SECTION 2: PAID APIs (expected to require subscription)")
            print("="*60)

            self.add_result(self.test_realtime_market_data())
            self.add_result(self.test_option_greeks())
            self.add_result(self.test_tick_by_tick())

            # Summary
            self.print_summary()

        finally:
            self.disconnect()
            print("\nDisconnected from IBKR")

    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)

        free_ok = [r for r in self.results if r.status == 'FREE_OK']
        free_fail = [r for r in self.results if r.status == 'FREE_FAIL']
        paid = [r for r in self.results if r.status == 'PAID_REQUIRED']
        errors = [r for r in self.results if r.status == 'ERROR']

        print(f"\n✅ FREE & Working: {len(free_ok)}")
        for r in free_ok:
            print(f"   - {r.api_name} ({r.data_size:,} records)")

        if free_fail:
            print(f"\n⚠️ FREE but No Data: {len(free_fail)}")
            for r in free_fail:
                print(f"   - {r.api_name}: {r.notes or 'No data'}")

        print(f"\n💰 PAID (Requires Subscription): {len(paid)}")
        for r in paid:
            print(f"   - {r.api_name}: {r.notes or ''}")

        if errors:
            print(f"\n❌ Errors: {len(errors)}")
            for r in errors:
                print(f"   - {r.api_name}: {r.error_message or 'Unknown error'}")

        # Pricing summary
        print("\n" + "="*60)
        print("MARKET DATA SUBSCRIPTION PRICING (Non-Professional)")
        print("="*60)
        print("""
| Service | Monthly Fee | What You Get |
|---------|-------------|--------------|
| US Securities Bundle | $10.00 | Stocks + Options + Futures snapshots |
| US Equity + Options Add-On | $4.50 | Real-time streaming |
| NASDAQ L1 (Network C) | $1.50 | NASDAQ quotes |
| NYSE L1 (Network A) | $1.50 | NYSE quotes |
| OPRA Options L1 | $1.50 | Real-time Greeks |

Minimum for API real-time data: $1.50-$4.50/month
Full streaming package: $10/month

Source: https://www.interactivebrokers.com/en/pricing/market-data-pricing.php
        """)

        # Save results to JSON
        results_dict = [asdict(r) for r in self.results]
        output_path = "data_sources/ibkr_api_test_results.json"
        with open(output_path, 'w') as f:
            json.dump({
                'test_date': datetime.now().isoformat(),
                'results': results_dict
            }, f, indent=2)
        print(f"\nResults saved to: {output_path}")


def main():
    if not HAS_DEPS:
        print("Missing required dependencies. Run: pip install ib_insync beautifulsoup4")
        return

    tester = IBKRFreeAPITester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()