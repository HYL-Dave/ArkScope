#!/usr/bin/env python3
"""
Finnhub API 完整測試 - 用於觀察新聞/情緒與股價反應時間

免費 API (✅ 可用):
1. Company News (公司新聞)
2. Market News (市場新聞)
3. Insider Transactions (內線交易 Form 4)
4. Real-time Quote (即時報價)
5. Company Profile (公司資料)
6. Earnings Calendar (財報日程)
7. Analyst Recommendations (分析師建議)
8. Financial Metrics (財務指標)

付費 API (❌ 需升級):
- Social Sentiment API (Reddit/Twitter 情緒) - 需付費方案
- Stock Candles (歷史價格 K 線) - 需付費方案

所有 API 都有時間戳，可用於分析反應時間。
歷史股價建議使用免費的 Tiingo 或 yfinance 取得。
"""

import os
import sys
import json
import requests
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

# Load environment variables
env_path = Path(__file__).parent.parent / 'config' / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                value = value.strip().strip('"').strip("'")
                os.environ[key.strip()] = value


class FinnhubFreeAPIs:
    """
    Finnhub API 存取類別

    免費端點及其時間戳格式:

    | Endpoint              | 狀態    | 時間戳欄位         | 格式            |
    |-----------------------|---------|-------------------|-----------------|
    | Company News          | ✅ FREE | datetime          | Unix timestamp  |
    | Market News           | ✅ FREE | datetime          | Unix timestamp  |
    | Insider Transactions  | ✅ FREE | transactionDate   | YYYY-MM-DD      |
    |                       |         | filingDate        | YYYY-MM-DD      |
    | Real-time Quote       | ✅ FREE | t                 | Unix timestamp  |
    | Company Profile       | ✅ FREE | ipo               | YYYY-MM-DD      |
    | Earnings Calendar     | ✅ FREE | date              | YYYY-MM-DD      |
    | Analyst Recommendations| ✅ FREE| period            | YYYY-MM-DD      |
    | Financial Metrics     | ✅ FREE | period            | YYYY-MM-DD      |
    | Social Sentiment      | ❌ PAID | atTime            | ISO datetime    |
    | Stock Candles         | ❌ PAID | t[]               | Unix timestamp  |

    歷史股價建議使用: Tiingo (免費) 或 yfinance (免費)
    """

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('FINNHUB_API_KEY')
        if not self.api_key:
            raise ValueError(
                "需要 Finnhub API key!\n"
                "免費註冊: https://finnhub.io/register\n"
                "設定環境變數 FINNHUB_API_KEY 或傳入 api_key 參數"
            )
        self.session = requests.Session()

    def _request(self, endpoint: str, params: Dict = None) -> Any:
        """發送 API 請求"""
        if params is None:
            params = {}
        params['token'] = self.api_key

        url = f"{self.BASE_URL}{endpoint}"
        response = self.session.get(url, params=params, timeout=30)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            print(f"⚠️  Rate limit exceeded. 免費版限制 60 calls/min")
            return None
        else:
            print(f"❌ API Error {response.status_code}: {response.text}")
            return None

    # =========================================================================
    # 1. SOCIAL SENTIMENT API (Reddit/Twitter)
    # =========================================================================

    def get_social_sentiment(self, symbol: str) -> Optional[Dict]:
        """
        取得社群媒體情緒 (Reddit/Twitter)

        回傳格式:
        {
            "symbol": "AAPL",
            "reddit": [
                {
                    "atTime": "2024-01-15T00:00:00Z",  # <- 時間戳
                    "mention": 150,                     # 總提及次數
                    "positiveMention": 100,
                    "negativeMention": 20,
                    "positiveScore": 0.67,              # 0-1
                    "negativeScore": 0.13,              # 0-1
                    "score": 0.54                       # -1 到 1
                },
                ...
            ],
            "twitter": [
                {
                    "atTime": "2024-01-15T00:00:00Z",
                    "mention": 500,
                    "positiveMention": 300,
                    "negativeMention": 100,
                    "positiveScore": 0.60,
                    "negativeScore": 0.20,
                    "score": 0.40
                },
                ...
            ]
        }

        ⏰ 時間精度: 每小時聚合
        📊 可用於: 觀察情緒變化與股價的相關性
        """
        return self._request("/stock/social-sentiment", {"symbol": symbol})

    # =========================================================================
    # 2. INSIDER TRANSACTIONS API (SEC Form 4)
    # =========================================================================

    def get_insider_transactions(self, symbol: str) -> Optional[Dict]:
        """
        取得內線交易記錄 (SEC Form 4)

        回傳格式:
        {
            "symbol": "AAPL",
            "data": [
                {
                    "name": "Tim Cook",              # 內部人姓名
                    "share": 1000000,                # 交易後持股
                    "change": -50000,                # 變動數量 (負=賣出)
                    "transactionDate": "2024-01-10", # <- 交易日期
                    "filingDate": "2024-01-12",      # <- 申報日期
                    "transactionCode": "S",          # P=買入, S=賣出
                    "transactionPrice": 185.50       # 交易價格
                },
                ...
            ]
        }

        ⏰ 時間精度: 交易日 + 申報日 (可計算延遲)
        📊 可用於:
           - 追蹤內線買入訊號 (transactionCode='P')
           - 計算從交易到申報的延遲
           - 觀察申報後股價反應
        """
        return self._request("/stock/insider-transactions", {"symbol": symbol})

    # =========================================================================
    # 3. COMPANY NEWS API
    # =========================================================================

    def get_company_news(
        self,
        symbol: str,
        from_date: date = None,
        to_date: date = None
    ) -> Optional[List[Dict]]:
        """
        取得公司新聞

        回傳格式:
        [
            {
                "id": 123456789,
                "category": "company",
                "datetime": 1705320000,        # <- Unix timestamp (秒)
                "headline": "Apple Announces...",
                "source": "Reuters",
                "summary": "...",
                "url": "https://...",
                "related": "AAPL"
            },
            ...
        ]

        ⏰ 時間精度: Unix timestamp (秒級)
        📊 可用於:
           - 精確計算新聞發布時間
           - 比對新聞時間與分鐘級股價
        """
        if from_date is None:
            from_date = date.today() - timedelta(days=7)
        if to_date is None:
            to_date = date.today()

        return self._request("/company-news", {
            "symbol": symbol,
            "from": from_date.isoformat(),
            "to": to_date.isoformat()
        })

    # =========================================================================
    # 4. STOCK CANDLES API (價格數據)
    # =========================================================================

    def get_stock_candles(
        self,
        symbol: str,
        resolution: str = "D",  # 1, 5, 15, 30, 60, D, W, M
        from_date: date = None,
        to_date: date = None
    ) -> Optional[Dict]:
        """
        取得股價 K 線數據

        Resolution 選項:
        - "1", "5", "15", "30", "60" = 分鐘 (日內)
        - "D" = 日線
        - "W" = 週線
        - "M" = 月線

        回傳格式:
        {
            "s": "ok",
            "t": [1705320000, 1705406400, ...],  # <- Unix timestamps
            "o": [185.00, 186.50, ...],           # Open
            "h": [187.00, 188.00, ...],           # High
            "l": [184.50, 185.00, ...],           # Low
            "c": [186.00, 187.50, ...],           # Close
            "v": [1000000, 1200000, ...]          # Volume
        }

        ⏰ 時間精度: Unix timestamp (可到分鐘級)
        📊 可用於: 精確比對新聞/情緒時間與價格變動
        """
        if from_date is None:
            from_date = date.today() - timedelta(days=30)
        if to_date is None:
            to_date = date.today()

        from_ts = int(datetime.combine(from_date, datetime.min.time()).timestamp())
        to_ts = int(datetime.combine(to_date, datetime.max.time()).timestamp())

        return self._request("/stock/candle", {
            "symbol": symbol,
            "resolution": resolution,
            "from": from_ts,
            "to": to_ts
        })

    # =========================================================================
    # 5. REAL-TIME QUOTE API
    # =========================================================================

    def get_quote(self, symbol: str) -> Optional[Dict]:
        """
        取得即時報價 ✅ FREE

        回傳格式:
        {
            "c": 186.50,    # Current price
            "d": 1.50,      # Change
            "dp": 0.81,     # Change %
            "h": 187.00,    # High
            "l": 185.00,    # Low
            "o": 185.50,    # Open
            "pc": 185.00,   # Previous close
            "t": 1705406400 # <- Unix timestamp
        }
        """
        return self._request("/quote", {"symbol": symbol})

    # =========================================================================
    # 6. MARKET NEWS API ✅ FREE
    # =========================================================================

    def get_market_news(self, category: str = "general") -> Optional[List[Dict]]:
        """
        取得市場新聞 (非特定股票) ✅ FREE

        category 選項: general, forex, crypto, merger

        回傳格式同 company news
        """
        return self._request("/news", {"category": category})

    # =========================================================================
    # 7. COMPANY PROFILE API ✅ FREE
    # =========================================================================

    def get_company_profile(self, symbol: str) -> Optional[Dict]:
        """
        取得公司基本資料 ✅ FREE

        回傳格式:
        {
            "name": "Apple Inc",
            "ticker": "AAPL",
            "exchange": "NASDAQ",
            "finnhubIndustry": "Technology",
            "marketCapitalization": 2850000,  # 百萬美元
            "ipo": "1980-12-12",              # <- IPO 日期
            "weburl": "https://www.apple.com"
        }
        """
        return self._request("/stock/profile2", {"symbol": symbol})

    # =========================================================================
    # 8. EARNINGS CALENDAR API ✅ FREE
    # =========================================================================

    def get_earnings(self, symbol: str) -> Optional[List[Dict]]:
        """
        取得財報日程 ✅ FREE

        回傳格式:
        [
            {
                "date": "2024-01-25",      # <- 財報日期
                "epsActual": 2.18,
                "epsEstimate": 2.10,
                "hour": "amc",              # bmo=盤前, amc=盤後
                "quarter": 1,
                "year": 2024,
                "revenueActual": 119000000000,
                "revenueEstimate": 117500000000
            }
        ]

        ⏰ 可用於: 追蹤財報前後的股價波動
        """
        return self._request("/stock/earnings", {"symbol": symbol})

    # =========================================================================
    # 9. ANALYST RECOMMENDATIONS API ✅ FREE
    # =========================================================================

    def get_recommendations(self, symbol: str) -> Optional[List[Dict]]:
        """
        取得分析師建議 ✅ FREE

        回傳格式:
        [
            {
                "period": "2024-01-01",     # <- 統計期間
                "strongBuy": 25,
                "buy": 30,
                "hold": 10,
                "sell": 2,
                "strongSell": 0
            }
        ]

        ⏰ 可用於: 追蹤分析師共識變化
        """
        return self._request("/stock/recommendation", {"symbol": symbol})

    # =========================================================================
    # 10. FINANCIAL METRICS API ✅ FREE
    # =========================================================================

    def get_metrics(self, symbol: str) -> Optional[Dict]:
        """
        取得財務指標 ✅ FREE

        回傳格式:
        {
            "metric": {
                "52WeekHigh": 200.50,
                "52WeekLow": 150.25,
                "peBasicExclExtraTTM": 28.5,
                "dividendYieldIndicatedAnnual": 0.52,
                ...
            }
        }
        """
        return self._request("/stock/metric", {"symbol": symbol, "metric": "all"})


def print_section(title: str):
    """印出區塊標題"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def timestamp_to_datetime(ts: int) -> datetime:
    """Unix timestamp 轉 datetime"""
    return datetime.fromtimestamp(ts)


def run_comprehensive_test(symbol: str = "AAPL"):
    """
    執行完整測試，展示所有免費 API 及其時間戳
    """
    print("\n" + "="*60)
    print("  FINNHUB 免費 API 完整測試")
    print("  觀察新聞/情緒與股價反應時間")
    print("="*60)

    try:
        api = FinnhubFreeAPIs()
        print(f"\n✅ API Key 已載入: {api.api_key[:8]}...{api.api_key[-4:]}")
    except ValueError as e:
        print(f"\n❌ {e}")
        return

    # =========================================================================
    # 1. Social Sentiment (PAID - 測試會失敗)
    # =========================================================================
    print_section("1. SOCIAL SENTIMENT (Reddit/Twitter) - ❌ PAID")

    print("⚠️  Social Sentiment API 需要付費方案")
    print("   免費替代方案: 直接爬取 Reddit/Twitter 或使用其他免費情緒 API")
    sentiment = api.get_social_sentiment(symbol)
    if sentiment:
        print(f"✅ (意外) 取得數據: {sentiment}")
    else:
        print("   確認: 免費方案無法存取此 API")

    # =========================================================================
    # 2. Insider Transactions
    # =========================================================================
    print_section("2. INSIDER TRANSACTIONS (Form 4)")

    insider = api.get_insider_transactions(symbol)

    if insider and insider.get('data'):
        transactions = insider['data']
        print(f"共 {len(transactions)} 筆內線交易記錄")
        print(f"\n最近 5 筆:")
        print(f"{'交易日':<12} {'申報日':<12} {'類型':<6} {'姓名':<20} {'變動':<12} {'價格':<10}")
        print("-" * 80)

        for tx in transactions[:5]:
            tx_date = tx.get('transactionDate', 'N/A')
            file_date = tx.get('filingDate', 'N/A')
            tx_code = tx.get('transactionCode', '?')
            tx_type = "買入" if tx_code == 'P' else "賣出" if tx_code == 'S' else tx_code
            name = tx.get('name', 'Unknown')[:18]
            change = tx.get('change', 0)
            price = tx.get('transactionPrice', 0)

            print(f"{tx_date:<12} {file_date:<12} {tx_type:<6} {name:<20} "
                  f"{change:>+10,} ${price:>8.2f}")

        # 計算交易到申報的延遲
        print(f"\n📊 延遲分析:")
        delays = []
        for tx in transactions[:20]:
            if tx.get('transactionDate') and tx.get('filingDate'):
                try:
                    tx_date = datetime.strptime(tx['transactionDate'], '%Y-%m-%d')
                    file_date = datetime.strptime(tx['filingDate'], '%Y-%m-%d')
                    delay = (file_date - tx_date).days
                    delays.append(delay)
                except:
                    pass

        if delays:
            avg_delay = sum(delays) / len(delays)
            print(f"   平均申報延遲: {avg_delay:.1f} 天")
            print(f"   最短延遲: {min(delays)} 天")
            print(f"   最長延遲: {max(delays)} 天")
    else:
        print("❌ 無法取得 Insider Transactions 數據")

    # =========================================================================
    # 3. Company News
    # =========================================================================
    print_section("3. COMPANY NEWS")

    news = api.get_company_news(symbol,
                                 from_date=date.today() - timedelta(days=7),
                                 to_date=date.today())

    if news:
        print(f"過去 7 天共 {len(news)} 篇新聞")
        print(f"\n最近 5 篇:")
        print(f"{'發布時間':<20} {'來源':<15} {'標題'}")
        print("-" * 80)

        for article in news[:5]:
            ts = article.get('datetime', 0)
            pub_time = timestamp_to_datetime(ts).strftime('%Y-%m-%d %H:%M') if ts else 'N/A'
            source = article.get('source', 'Unknown')[:13]
            headline = article.get('headline', '')[:45]

            print(f"{pub_time:<20} {source:<15} {headline}...")
    else:
        print("❌ 無法取得 Company News 數據")

    # =========================================================================
    # 4. Stock Candles - ❌ PAID
    # =========================================================================
    print_section("4. STOCK CANDLES (歷史價格) - ❌ PAID")

    print("⚠️  Stock Candles API 需要付費方案 (包括日線和分鐘線)")
    print("   免費替代方案:")
    print("   - Tiingo: 免費日線數據 (30+ 年歷史)")
    print("   - yfinance: 免費日線/分鐘數據")
    print("   - Alpha Vantage: 免費方案有限制")
    candles = api.get_stock_candles(symbol, resolution="D")
    if candles and candles.get('s') == 'ok':
        print(f"✅ (意外) 取得數據: {len(candles.get('t', []))} 筆")
    else:
        print("   確認: 免費方案無法存取此 API")

    # =========================================================================
    # 5. Real-time Quote ✅ FREE
    # =========================================================================
    print_section("5. REAL-TIME QUOTE - ✅ FREE")

    quote = api.get_quote(symbol)
    if quote and 'c' in quote:
        ts = quote.get('t', 0)
        quote_time = timestamp_to_datetime(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else 'N/A'
        print(f"股票: {symbol}")
        print(f"時間: {quote_time}")
        print(f"現價: ${quote.get('c', 0):.2f}")
        print(f"開盤: ${quote.get('o', 0):.2f}")
        print(f"最高: ${quote.get('h', 0):.2f}")
        print(f"最低: ${quote.get('l', 0):.2f}")
        print(f"前收: ${quote.get('pc', 0):.2f}")
        print(f"漲跌: ${quote.get('d', 0):.2f} ({quote.get('dp', 0):.2f}%)")
    else:
        print("❌ 無法取得 Quote 數據")

    # =========================================================================
    # 6. Earnings Calendar ✅ FREE
    # =========================================================================
    print_section("6. EARNINGS CALENDAR - ✅ FREE")

    earnings = api.get_earnings(symbol)
    if earnings:
        print(f"共 {len(earnings)} 筆財報記錄")
        print(f"\n最近 5 筆:")
        print(f"{'日期':<12} {'季度':<8} {'EPS 實際':<12} {'EPS 預估':<12} {'驚喜':<10}")
        print("-" * 60)

        for e in earnings[:5]:
            eps_actual = e.get('epsActual', 0) or 0
            eps_est = e.get('epsEstimate', 0) or 0
            surprise = eps_actual - eps_est if eps_est else 0
            surprise_pct = (surprise / abs(eps_est) * 100) if eps_est else 0

            print(f"{e.get('date', 'N/A'):<12} Q{e.get('quarter', '?')}/{e.get('year', '?'):<4} "
                  f"${eps_actual:>9.2f}  ${eps_est:>9.2f}  {surprise_pct:>+6.1f}%")
    else:
        print("❌ 無法取得 Earnings 數據")

    # =========================================================================
    # 7. Analyst Recommendations ✅ FREE
    # =========================================================================
    print_section("7. ANALYST RECOMMENDATIONS - ✅ FREE")

    recs = api.get_recommendations(symbol)
    if recs:
        print(f"共 {len(recs)} 期分析師建議")
        print(f"\n最近 3 期:")
        print(f"{'期間':<12} {'強買':<8} {'買入':<8} {'持有':<8} {'賣出':<8} {'強賣':<8}")
        print("-" * 60)

        for r in recs[:3]:
            print(f"{r.get('period', 'N/A'):<12} "
                  f"{r.get('strongBuy', 0):<8} {r.get('buy', 0):<8} "
                  f"{r.get('hold', 0):<8} {r.get('sell', 0):<8} "
                  f"{r.get('strongSell', 0):<8}")
    else:
        print("❌ 無法取得 Recommendations 數據")

    # =========================================================================
    # 8. Company Profile ✅ FREE
    # =========================================================================
    print_section("8. COMPANY PROFILE - ✅ FREE")

    profile = api.get_company_profile(symbol)
    if profile and profile.get('name'):
        print(f"公司名稱: {profile.get('name')}")
        print(f"股票代號: {profile.get('ticker')}")
        print(f"交易所: {profile.get('exchange')}")
        print(f"產業: {profile.get('finnhubIndustry')}")
        market_cap = profile.get('marketCapitalization', 0)
        print(f"市值: ${market_cap:,.0f}M (${market_cap/1000:.1f}B)")
        print(f"IPO 日期: {profile.get('ipo')}")
        print(f"網站: {profile.get('weburl')}")
    else:
        print("❌ 無法取得 Company Profile 數據")

    # =========================================================================
    # 9. 時間戳格式總結
    # =========================================================================
    print_section("9. 時間戳格式總結 (用於反應時間分析)")

    print("""
┌─────────────────────┬──────────────────┬─────────────────────────────┐
│ API                 │ 時間欄位         │ 格式                        │
├─────────────────────┼──────────────────┼─────────────────────────────┤
│ Social Sentiment    │ atTime           │ ISO 8601 (2024-01-15T00:00) │
│ Company News        │ datetime         │ Unix timestamp (秒)         │
│ Insider Transactions│ transactionDate  │ YYYY-MM-DD                  │
│                     │ filingDate       │ YYYY-MM-DD                  │
│ Stock Candles       │ t[]              │ Unix timestamp (秒)         │
│ Quote               │ t                │ Unix timestamp (秒)         │
└─────────────────────┴──────────────────┴─────────────────────────────┘

📊 反應時間分析方法:

1. 新聞 → 股價反應
   - 取得新聞 datetime (Unix timestamp)
   - 取得同時段分鐘 K 線
   - 比較新聞前後的價格變動

2. 社群情緒 → 股價反應
   - 取得 Social Sentiment 的 atTime
   - 對應同時段的股價數據
   - 計算情緒分數與次日回報的相關性

3. 內線交易 → 股價反應
   - 取得 filingDate (申報日)
   - 觀察申報日後 1-5 天的股價變動
   - 分析買入訊號的預測能力
""")

    # =========================================================================
    # 10. 總結
    # =========================================================================
    print_section("10. FINNHUB 免費 API 總結")

    print("""
┌─────────────────────────┬────────┬─────────────────────────────────┐
│ API                     │ 狀態   │ 用途                            │
├─────────────────────────┼────────┼─────────────────────────────────┤
│ Company News            │ ✅ FREE│ 公司新聞 (Unix timestamp)       │
│ Market News             │ ✅ FREE│ 市場新聞                        │
│ Insider Transactions    │ ✅ FREE│ 內線交易 Form 4                 │
│ Real-time Quote         │ ✅ FREE│ 即時報價 (有延遲)               │
│ Company Profile         │ ✅ FREE│ 公司基本資料                    │
│ Earnings Calendar       │ ✅ FREE│ 財報日期和 EPS                  │
│ Analyst Recommendations │ ✅ FREE│ 分析師買賣建議                  │
│ Financial Metrics       │ ✅ FREE│ 52 週高低、PE、殖利率           │
├─────────────────────────┼────────┼─────────────────────────────────┤
│ Social Sentiment        │ ❌ PAID│ Reddit/Twitter 情緒             │
│ Stock Candles           │ ❌ PAID│ 歷史 K 線 (日/分鐘)             │
└─────────────────────────┴────────┴─────────────────────────────────┘

📌 建議搭配:
   - 歷史股價: Tiingo (免費 30+ 年日線) 或 yfinance
   - 社群情緒: 直接爬取 Reddit/Twitter 或使用其他免費 API
""")


def save_data_for_analysis(symbol: str = "AAPL", output_dir: str = None):
    """
    儲存所有免費 API 數據到 JSON 檔案，便於後續分析
    """
    if output_dir is None:
        output_dir = Path(__file__).parent / "sentiment_analysis_data"

    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    api = FinnhubFreeAPIs()

    print(f"正在取得 {symbol} 的免費 API 數據...")

    data = {
        "symbol": symbol,
        "fetched_at": datetime.now().isoformat(),
        # 免費 API
        "insider_transactions": api.get_insider_transactions(symbol),
        "company_news": api.get_company_news(
            symbol,
            from_date=date.today() - timedelta(days=30),
            to_date=date.today()
        ),
        "quote": api.get_quote(symbol),
        "company_profile": api.get_company_profile(symbol),
        "earnings": api.get_earnings(symbol),
        "recommendations": api.get_recommendations(symbol),
        "metrics": api.get_metrics(symbol),
    }

    output_file = output_dir / f"{symbol}_finnhub_free_data_{date.today().isoformat()}.json"

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ 免費 API 數據已儲存至: {output_file}")
    return output_file


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Finnhub 免費 API 測試")
    parser.add_argument("--symbol", "-s", default="AAPL", help="股票代號")
    parser.add_argument("--save", action="store_true", help="儲存數據到 JSON")

    args = parser.parse_args()

    run_comprehensive_test(args.symbol)

    if args.save:
        print_section("儲存數據")
        save_data_for_analysis(args.symbol)