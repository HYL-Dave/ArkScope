#!/usr/bin/env python3
"""
IBKR 基本面數據收集腳本

收集 IBKR TWS API 免費提供的基本面數據:
- ReportSnapshot: 財務比率 (P/E, ROE, EPS, 毛利率等)
- ReportsFinSummary: 財務摘要
- ReportsOwnership: 機構持股數據

資料來源: Reuters (透過 IBKR)

使用方式:
    # 收集所有 tickers 的基本面數據
    python collect_ibkr_fundamentals.py

    # 收集指定股票
    python collect_ibkr_fundamentals.py --tickers AAPL,MSFT,GOOGL

    # 只收集特定報告類型
    python collect_ibkr_fundamentals.py --report-types ReportSnapshot

    # 查看現有資料狀態
    python collect_ibkr_fundamentals.py --status

    # 使用不同的 IB Gateway 連接
    python collect_ibkr_fundamentals.py --host 192.168.0.152 --port 4001

需求:
    - IB Gateway 或 TWS 運行中
    - pip install ib_insync defusedxml
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict, field
import time

import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

try:
    from ib_insync import IB, Stock
    from defusedxml.ElementTree import fromstring  # 與 ib-fundamental 相同，安全解析
    from xml.etree.ElementTree import Element
    HAS_DEPS = True
except ImportError as e:
    HAS_DEPS = False
    print(f"Missing dependencies: {e}")
    print("Run: pip install ib_insync defusedxml")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Default tickers (fallback if config not found)
DEFAULT_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
    "JPM", "V", "JNJ", "WMT", "PG", "XOM", "UNH", "HD",
    "MA", "BAC", "DIS", "ADBE", "NFLX", "CRM", "COST", "PEP",
    "CSCO", "TMO", "ABT", "ACN", "AVGO", "MRK", "NKE"
]


def load_tickers(tickers_arg: Optional[str] = None) -> List[str]:
    """
    Load tickers from argument, config file, or default list.

    Priority:
    1. Command line argument (--tickers AAPL,MSFT)
    2. config/tickers_core.json (if exists)
    3. DEFAULT_TICKERS fallback
    """
    if tickers_arg:
        return [t.strip().upper() for t in tickers_arg.split(',')]

    config_path = Path("config/tickers_core.json")
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            settings = config.get('settings', {})
            tier_names = ['tier1_core']
            if settings.get('include_tier2', True):
                tier_names.append('tier2_expanded')
            if settings.get('include_tier3', True):
                tier_names.append('tier3_user_watchlist')

            tickers = set()
            for tier_name in tier_names:
                tier_data = config.get(tier_name, {})
                for category in tier_data.values():
                    if isinstance(category, dict) and 'tickers' in category:
                        tickers.update(category['tickers'])

            tickers = sorted(list(tickers))
            if tickers:
                logger.info(f"Loaded {len(tickers)} tickers from {config_path}")
                return tickers
        except Exception as e:
            logger.warning(f"Failed to load {config_path}: {e}")

    logger.info(f"Using default tickers ({len(DEFAULT_TICKERS)} stocks)")
    return DEFAULT_TICKERS

# Free report types (confirmed working)
FREE_REPORT_TYPES = [
    "ReportSnapshot",      # Financial ratios - most useful!
    "ReportsFinSummary",   # Financial summary
    "ReportsOwnership",    # Institutional ownership
]

# Paid/Not working report types
PAID_REPORT_TYPES = [
    "ReportsFinStatements",  # Requires subscription
    "RESC",                  # Analyst estimates - often not working
    "CalendarReport",        # Requires WSH subscription
]


@dataclass
class FinancialRatio:
    """Parsed financial ratio from ReportSnapshot."""
    ticker: str
    report_date: str
    field_name: str
    value: Optional[float]
    raw_value: str


@dataclass
class FundamentalData:
    """Complete fundamental data for a ticker."""
    ticker: str
    collected_at: str
    report_type: str
    company_name: Optional[str] = None
    cik: Optional[str] = None
    exchange: Optional[str] = None

    # Financial Ratios (from ReportSnapshot)
    price: Optional[float] = None
    market_cap: Optional[float] = None  # In millions
    enterprise_value: Optional[float] = None
    pe_ratio: Optional[float] = None
    price_to_book: Optional[float] = None
    price_to_sales: Optional[float] = None
    ev_to_ebitda: Optional[float] = None

    # Profitability
    roe: Optional[float] = None  # Return on Equity %
    roa: Optional[float] = None  # Return on Assets %
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None

    # Per Share
    eps_ttm: Optional[float] = None
    book_value_per_share: Optional[float] = None
    dividend_per_share: Optional[float] = None
    dividend_yield: Optional[float] = None

    # Revenue & Growth
    revenue_ttm: Optional[float] = None  # In millions
    ebitda_ttm: Optional[float] = None
    net_income_ttm: Optional[float] = None

    # Other
    beta: Optional[float] = None
    shares_outstanding: Optional[float] = None
    avg_volume_10d: Optional[float] = None

    # All ratios (raw)
    all_ratios: Dict[str, str] = field(default_factory=dict)


class IBKRFundamentalsCollector:
    """Collect fundamental data from IBKR TWS API."""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        client_id: int = 103,
        output_dir: str = "data_lake/raw/ibkr_fundamentals"
    ):
        self.host = host or os.getenv("IBKR_HOST", "127.0.0.1")
        self.port = port or int(os.getenv("IBKR_PORT", "7497"))
        self.client_id = client_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ib: Optional[IB] = None

    def connect(self) -> bool:
        """Connect to TWS/IB Gateway."""
        logger.info(f"Connecting to IBKR at {self.host}:{self.port}...")
        self.ib = IB()
        try:
            self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=30, readonly=True)
            logger.info(f"Connected! Server version: {self.ib.client.serverVersion()}")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from IBKR."""
        if self.ib:
            self.ib.disconnect()
            logger.info("Disconnected from IBKR")

    def parse_report_snapshot(self, ticker: str, xml_data: str) -> FundamentalData:
        """
        Parse ReportSnapshot XML into structured data.

        使用 defusedxml + ElementTree (與 ib-fundamental 相同方式)
        """
        root = fromstring(xml_data)  # 安全解析
        data = FundamentalData(
            ticker=ticker,
            collected_at=datetime.now().isoformat(),
            report_type="ReportSnapshot"
        )

        # Company Info - 使用 XPath
        co_ids = root.find(".//CoIDs")
        if co_ids is not None:
            for co_id in co_ids.findall("CoID"):
                id_type = co_id.get("Type", "")
                if id_type == "CompanyName" and co_id.text:
                    data.company_name = co_id.text.strip()
                elif id_type == "CIKNo" and co_id.text:
                    data.cik = co_id.text.strip()

        # Extract all ratios - 使用 findall + attrib
        for ratio in root.findall(".//Ratio"):
            field_name = ratio.get("FieldName", "")
            value_str = ratio.text.strip() if ratio.text else ""
            data.all_ratios[field_name] = value_str

            # Parse specific ratios
            try:
                value = float(value_str) if value_str else None
            except (ValueError, TypeError):
                value = None

            # Map to structured fields
            if field_name == "NPRICE":
                data.price = value
            elif field_name == "MKTCAP":
                data.market_cap = value
            elif field_name == "EV":
                data.enterprise_value = value
            elif field_name == "PEEXCLXOR":
                data.pe_ratio = value
            elif field_name == "PRICE2BK":
                data.price_to_book = value
            elif field_name == "TTMPR2REV" or field_name == "PRICE2SAL":
                data.price_to_sales = value
            elif field_name == "TTMROEPCT":
                data.roe = value
            elif field_name == "TTMROAPCT":
                data.roa = value
            elif field_name == "TTMGROSMGN":
                data.gross_margin = value
            elif field_name == "TTMOPMGN":
                data.operating_margin = value
            elif field_name == "TTMNPMGN":
                data.net_margin = value
            elif field_name == "TTMEPSXCLX" or field_name == "AEPSNORM":
                data.eps_ttm = value
            elif field_name == "QBVPS":
                data.book_value_per_share = value
            elif field_name == "TTMDIVSHR":
                data.dividend_per_share = value
            elif field_name == "YIELD":
                data.dividend_yield = value
            elif field_name == "TTMREV":
                data.revenue_ttm = value
            elif field_name == "TTMEBITD":
                data.ebitda_ttm = value
            elif field_name == "TTMNIAC":
                data.net_income_ttm = value
            elif field_name == "BETA":
                data.beta = value
            elif field_name == "SHAESSION":
                data.shares_outstanding = value
            elif field_name == "VOL10DAVG":
                data.avg_volume_10d = value

        return data

    def parse_ownership_data(self, ticker: str, xml_data: str) -> Dict[str, Any]:
        """Parse ReportsOwnership XML into structured data."""
        root = fromstring(xml_data)  # 安全解析

        ownership = {
            "ticker": ticker,
            "collected_at": datetime.now().isoformat(),
            "report_type": "ReportsOwnership",
            "institutions": [],
            "summary": {}
        }

        # Get summary - 使用 ElementTree 語法
        summary = root.find(".//ShareHolderSummary")
        if summary is not None:
            for item in summary:
                if item.text:
                    ownership["summary"][item.tag] = item.text.strip()

        # Get top institutions
        for owner in root.findall(".//Owner")[:50]:  # Top 50
            inst = {}
            for child in owner:
                if child.text:
                    inst[child.tag] = child.text.strip()
            if inst:
                ownership["institutions"].append(inst)

        return ownership

    def collect_fundamental(
        self,
        ticker: str,
        report_types: List[str] = None
    ) -> Dict[str, Any]:
        """Collect fundamental data for a single ticker."""
        if report_types is None:
            report_types = FREE_REPORT_TYPES

        results = {
            "ticker": ticker,
            "collected_at": datetime.now().isoformat(),
            "reports": {}
        }

        contract = Stock(ticker, "SMART", "USD")
        try:
            self.ib.qualifyContracts(contract)
        except Exception as e:
            logger.warning(f"{ticker}: Failed to qualify contract: {e}")
            results["error"] = str(e)
            return results

        for report_type in report_types:
            logger.debug(f"{ticker}: Requesting {report_type}...")
            try:
                xml_data = self.ib.reqFundamentalData(contract, report_type)

                if xml_data and len(xml_data) > 0:
                    if report_type == "ReportSnapshot":
                        parsed = self.parse_report_snapshot(ticker, xml_data)
                        results["reports"][report_type] = asdict(parsed)
                    elif report_type == "ReportsOwnership":
                        parsed = self.parse_ownership_data(ticker, xml_data)
                        results["reports"][report_type] = parsed
                    else:
                        # Store raw XML size for other types
                        results["reports"][report_type] = {
                            "status": "ok",
                            "size_bytes": len(xml_data)
                        }

                    logger.info(f"{ticker}: {report_type} - {len(xml_data):,} bytes")
                else:
                    results["reports"][report_type] = {
                        "status": "no_data",
                        "size_bytes": 0
                    }
                    logger.warning(f"{ticker}: {report_type} - No data")

            except Exception as e:
                results["reports"][report_type] = {
                    "status": "error",
                    "error": str(e)[:200]
                }
                logger.warning(f"{ticker}: {report_type} - Error: {e}")

            # Rate limiting: 60 requests per 10 minutes
            time.sleep(0.5)

        return results

    def collect_all(
        self,
        tickers: List[str],
        report_types: List[str] = None,
        save_individual: bool = True
    ) -> List[Dict[str, Any]]:
        """Collect fundamental data for all tickers."""
        all_results = []

        logger.info(f"Collecting fundamentals for {len(tickers)} tickers...")

        for i, ticker in enumerate(tickers):
            logger.info(f"[{i+1}/{len(tickers)}] Processing {ticker}...")

            result = self.collect_fundamental(ticker, report_types)
            all_results.append(result)

            # Save individual file
            if save_individual:
                today = date.today().isoformat()
                output_file = self.output_dir / f"{ticker}_{today}.json"
                with open(output_file, 'w') as f:
                    json.dump(result, f, indent=2)

            # Rate limiting between tickers
            time.sleep(1)

        return all_results

    def save_combined_report(self, results: List[Dict[str, Any]], filename: str = None):
        """Save combined report with all tickers."""
        if filename is None:
            filename = f"fundamentals_{date.today().isoformat()}.json"

        output_path = self.output_dir / filename
        with open(output_path, 'w') as f:
            json.dump({
                "collected_at": datetime.now().isoformat(),
                "ticker_count": len(results),
                "data": results
            }, f, indent=2)

        logger.info(f"Saved combined report to: {output_path}")

        # Also create summary CSV
        self.create_summary_csv(results)

    def create_summary_csv(self, results: List[Dict[str, Any]]):
        """Create summary CSV with key metrics."""
        rows = []

        for result in results:
            ticker = result["ticker"]
            reports = result.get("reports", {})

            if "ReportSnapshot" in reports and isinstance(reports["ReportSnapshot"], dict):
                snapshot = reports["ReportSnapshot"]
                rows.append({
                    "ticker": ticker,
                    "collected_at": result["collected_at"],
                    "company_name": snapshot.get("company_name"),
                    "cik": snapshot.get("cik"),
                    "price": snapshot.get("price"),
                    "market_cap_m": snapshot.get("market_cap"),
                    "enterprise_value_m": snapshot.get("enterprise_value"),
                    "pe_ratio": snapshot.get("pe_ratio"),
                    "price_to_book": snapshot.get("price_to_book"),
                    "price_to_sales": snapshot.get("price_to_sales"),
                    "roe_pct": snapshot.get("roe"),
                    "roa_pct": snapshot.get("roa"),
                    "gross_margin_pct": snapshot.get("gross_margin"),
                    "operating_margin_pct": snapshot.get("operating_margin"),
                    "net_margin_pct": snapshot.get("net_margin"),
                    "eps_ttm": snapshot.get("eps_ttm"),
                    "book_value_ps": snapshot.get("book_value_per_share"),
                    "dividend_yield_pct": snapshot.get("dividend_yield"),
                    "revenue_ttm_m": snapshot.get("revenue_ttm"),
                    "ebitda_ttm_m": snapshot.get("ebitda_ttm"),
                    "net_income_ttm_m": snapshot.get("net_income_ttm"),
                    "beta": snapshot.get("beta"),
                    "avg_volume_10d": snapshot.get("avg_volume_10d"),
                })

        if rows:
            df = pd.DataFrame(rows)
            csv_path = self.output_dir / f"fundamentals_summary_{date.today().isoformat()}.csv"
            df.to_csv(csv_path, index=False)
            logger.info(f"Saved summary CSV to: {csv_path}")

            # Print summary
            print("\n" + "="*60)
            print("FUNDAMENTALS SUMMARY")
            print("="*60)
            print(df[["ticker", "price", "market_cap_m", "pe_ratio", "roe_pct", "gross_margin_pct"]].to_string())

    def show_status(self):
        """Show status of existing data."""
        print("\n" + "="*60)
        print("IBKR FUNDAMENTALS DATA STATUS")
        print("="*60)

        files = list(self.output_dir.glob("*.json"))
        if not files:
            print("No data files found.")
            return

        # Group by date
        dates = {}
        for f in files:
            name = f.stem
            if "_" in name:
                file_date = name.split("_")[-1]
                if file_date not in dates:
                    dates[file_date] = []
                dates[file_date].append(f)

        for d in sorted(dates.keys(), reverse=True)[:5]:
            print(f"\n{d}:")
            for f in dates[d]:
                size = f.stat().st_size
                print(f"  - {f.name}: {size/1024:.1f} KB")


def main():
    parser = argparse.ArgumentParser(
        description="Collect IBKR fundamental data",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--tickers",
        type=str,
        help="Comma-separated tickers (default: predefined list)"
    )
    parser.add_argument(
        "--report-types",
        type=str,
        help=f"Comma-separated report types. Free: {','.join(FREE_REPORT_TYPES)}"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("IBKR_HOST", "127.0.0.1"),
        help="IB Gateway/TWS host"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("IBKR_PORT", "7497")),
        help="IB Gateway/TWS port"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data_lake/raw/ibkr_fundamentals",
        help="Output directory"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show status of existing data"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not HAS_DEPS:
        print("Missing dependencies. Run: pip install ib_insync defusedxml")
        sys.exit(1)

    collector = IBKRFundamentalsCollector(
        host=args.host,
        port=args.port,
        output_dir=args.output_dir
    )

    if args.status:
        collector.show_status()
        return

    # Load tickers (from arg, config/tickers_core.json, or defaults)
    tickers = load_tickers(args.tickers)

    # Parse report types
    if args.report_types:
        report_types = [t.strip() for t in args.report_types.split(",")]
    else:
        report_types = FREE_REPORT_TYPES

    # Connect and collect
    if not collector.connect():
        print("Failed to connect to IBKR")
        sys.exit(1)

    try:
        results = collector.collect_all(tickers, report_types)
        collector.save_combined_report(results)

        # Summary stats
        success = sum(1 for r in results if r.get("reports", {}).get("ReportSnapshot", {}).get("status") != "error")
        print(f"\n{'='*60}")
        print(f"COLLECTION COMPLETE")
        print(f"{'='*60}")
        print(f"Tickers processed: {len(tickers)}")
        print(f"Successful: {success}")
        print(f"Output: {collector.output_dir}")

    finally:
        collector.disconnect()


if __name__ == "__main__":
    main()