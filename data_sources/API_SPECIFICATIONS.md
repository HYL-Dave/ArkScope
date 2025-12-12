# 數據源 API 規格說明

本文檔記錄各 API 的實際呼叫格式、回傳結構、和每筆請求的限制。

---

## Alpha Vantage 新聞 API

### 為什麼 AAPL 新聞會包含其他股票？

**這是 Alpha Vantage API 的設計行為**，不是 bug。

當你用 `tickers=AAPL` 搜尋時，API 回傳的是「與 AAPL 相關的新聞」，而不是「只有 AAPL 的新聞」。每篇新聞可能涉及多支股票：

```
請求: GET /query?function=NEWS_SENTIMENT&tickers=AAPL
回傳: 所有「提及 AAPL」的新聞，但這些新聞也可能提及 NVDA, TSLA, MSFT 等
```

### 原始 API 回傳結構

```json
{
  "feed": [
    {
      "title": "Some Tech Article",
      "time_published": "20251211T203342",
      "source": "Yahoo Finance",
      "overall_sentiment_score": 0.312,     // 文章整體情緒
      "overall_sentiment_label": "Somewhat-Bullish",
      "ticker_sentiment": [                 // 每個被提及股票的情緒
        {
          "ticker": "AAPL",
          "relevance_score": "0.705",       // AAPL 與文章的相關度
          "ticker_sentiment_score": "0.306",
          "ticker_sentiment_label": "Somewhat-Bullish"
        },
        {
          "ticker": "NVDA",                  // 同篇文章也提及 NVDA
          "relevance_score": "0.726",
          "ticker_sentiment_score": "0.333",
          "ticker_sentiment_label": "Somewhat-Bullish"
        }
      ]
    }
  ]
}
```

### 呼叫限制

| 參數 | 限制 |
|-----|------|
| 免費方案 | 25 calls/天, 5 calls/分鐘 |
| `limit` | 最大 1000 篇/請求 |
| `time_from/time_to` | 格式: `YYYYMMDDTHHMM` |
| `tickers` | 可多個，逗號分隔 |

### 如何只取 AAPL 專屬新聞？

需要在收到回傳後自行過濾：
```python
# 過濾 relevance_score > 0.8 且 AAPL 是主要股票的新聞
aapl_focused = [
    article for article in feed
    if any(ts['ticker'] == 'AAPL' and float(ts['relevance_score']) > 0.8
           for ts in article['ticker_sentiment'])
]
```

---

## SEC EDGAR API

### 為什麼回傳的是 HTML 連結？

**這是 SEC 官方的設計**。SEC EDGAR 提供兩種數據：

1. **Filing 列表** → 回傳文件列表和連結 (我們目前取得的)
2. **XBRL 結構化數據** → 回傳 JSON 格式的財務指標

### Filing API 回傳結構

```
請求: GET /cgi-bin/browse-edgar?action=getcompany&CIK=AAPL&type=10-K&output=atom
回傳: XML/Atom 格式的 filing 列表
```

每個 filing 只是「文件清單」，需要另外下載實際內容：

```
Filing 結構:
├── 10-K.htm          # HTML 版本 (人類閱讀用)
├── 10-K_htm.xml      # XBRL 實例文檔
├── Financial_Report.xlsx  # 某些 filing 有 Excel
└── 其他附件...
```

### Company Facts API (結構化數據) ✅ 已使用

這才是真正的 JSON 數據：

```
請求: GET /api/xbrl/companyfacts/CIK0000320193.json
回傳:
{
  "facts": {
    "us-gaap": {
      "Revenues": {
        "units": {
          "USD": [
            {"val": 394328000000, "end": "2022-09-24", "form": "10-K"},
            {"val": 383285000000, "end": "2023-09-30", "form": "10-K"}
          ]
        }
      },
      "NetIncomeLoss": { ... },
      "Assets": { ... }
    }
  }
}
```

我們已經在收集這個！見 `aapl_sec_edgar.json` 的 `xbrl_facts` 欄位。

### 呼叫限制

| 參數 | 限制 |
|-----|------|
| Rate limit | 10 requests/秒 (禮貌限制) |
| 必要 Header | `User-Agent: your-email@example.com` |
| CIK 格式 | 10 位數字，前面補 0 |

---

## Finnhub 新聞 API

### 原始 API 回傳結構

```
請求: GET /company-news?symbol=AAPL&from=2025-12-05&to=2025-12-12
回傳:
[
  {
    "category": "company",
    "datetime": 1733961234,      // Unix timestamp
    "headline": "Apple announces...",
    "id": 12345678,
    "image": "https://...",
    "related": "AAPL",           // 只有這一支股票
    "source": "Reuters",
    "summary": "Apple Inc...",
    "url": "https://..."
  }
]
```

**注意**: Finnhub 的新聞 API 比較「精確」，`related` 欄位通常只有目標股票。

### 呼叫限制

| 參數 | 限制 |
|-----|------|
| 免費方案 | 60 calls/分鐘 |
| 歷史深度 | **最多 1 年** |
| 每次回傳 | 無明確上限，但建議分段取 |

---

## Polygon.io 新聞 API

### 原始 API 回傳結構

```
請求: GET /v2/reference/news?ticker=AAPL&limit=10
回傳:
{
  "results": [
    {
      "title": "Apple...",
      "published_utc": "2025-12-11T20:33:42Z",
      "article_url": "https://...",
      "tickers": ["AAPL"],        // 可能有多個股票
      "publisher": {
        "name": "Yahoo Finance",
        "homepage_url": "https://..."
      },
      "insights": [               // AI 情緒分析
        {
          "ticker": "AAPL",
          "sentiment": "positive",
          "sentiment_reasoning": "..."
        }
      ]
    }
  ]
}
```

### 呼叫限制

| 參數 | 限制 |
|-----|------|
| 免費方案 | 5 calls/分鐘 |
| `limit` | 最大 1000/請求 |
| 延遲 | 15 分鐘 |

---

## Tiingo 股價 API

### 原始 API 回傳結構

```
請求: GET /tiingo/daily/AAPL/prices?startDate=2025-01-01&endDate=2025-12-12
回傳:
[
  {
    "date": "2025-01-02T00:00:00+00:00",
    "open": 180.5,
    "high": 182.3,
    "low": 179.8,
    "close": 181.2,
    "volume": 54321000,
    "adjOpen": 180.5,
    "adjHigh": 182.3,
    "adjLow": 179.8,
    "adjClose": 181.2,       // 調整後價格
    "adjVolume": 54321000,
    "divCash": 0.0,
    "splitFactor": 1.0
  }
]
```

### 呼叫限制

| 參數 | 限制 |
|-----|------|
| 免費方案 | 500 symbols/月, 50 symbols/小時 |
| 每次回傳 | 無上限 (可取整個歷史) |
| 新聞 API | **403 禁止** (需付費) |

---

## yfinance (Yahoo Finance)

### 回傳結構

yfinance 是 Python 套件，直接回傳 pandas DataFrame：

```python
import yfinance as yf
ticker = yf.Ticker("AAPL")

# 歷史價格
hist = ticker.history(period="1mo")
# 回傳 DataFrame:
#                  Open       High        Low      Close    Volume
# Date
# 2025-12-02  275.123  276.543  274.321  275.890  45678900

# 新聞 (有限)
news = ticker.news
# 回傳 list of dict:
# [{"title": "...", "publisher": "...", "link": "...", "providerPublishTime": 1733961234}]
```

### 呼叫限制

| 參數 | 限制 |
|-----|------|
| Rate limit | 無官方限制 (非官方 API) |
| 分鐘級數據 | **僅 7 天** |
| 風險 | 可能被 Yahoo 封鎖 |

---

## 每筆請求的數據量限制

| API | 每次請求最大數據量 | 建議策略 |
|-----|------------------|---------|
| Alpha Vantage | 1000 篇新聞 | 分時間段取 |
| Finnhub | 無硬限制 | 建議每 30 天一次 |
| Polygon | 1000 條記錄 | 使用 pagination |
| Tiingo | 無限制 | 可一次取多年 |
| SEC EDGAR | 無限制 | 單次取完整歷史 |
| yfinance | 無限制 | 可一次取完整歷史 |

---

## 收集 AAPL 純淨數據的正確方式

基於以上分析，如果要收集「純 AAPL」數據：

### 股價
```python
# Tiingo (推薦) - 純 AAPL
tiingo.fetch_prices(['AAPL'], start_date, end_date)

# yfinance (備用) - 純 AAPL
yf.Ticker('AAPL').history(start=start_date, end=end_date)
```

### 新聞 (需要後處理)
```python
# Finnhub - related 欄位通常只有目標股票
finnhub_news = finnhub.fetch_news(['AAPL'], days_back=7)

# Alpha Vantage - 需要過濾
alpha_news = alpha_vantage.fetch_news_raw(tickers=['AAPL'])
aapl_focused = [
    n for n in alpha_news
    if any(ts['ticker'] == 'AAPL' and float(ts['relevance_score']) > 0.7
           for ts in n.get('ticker_sentiments', []))
]
```

### 財報
```python
# SEC EDGAR - Company Facts API 提供結構化 JSON
facts = sec_edgar.fetch_company_facts('AAPL')
revenue = facts['facts']['us-gaap']['Revenues']['units']['USD']
```

---

## edgartools 套件 (推薦)

### 安裝
```bash
pip install edgartools
```

### 為什麼使用 edgartools？

`edgartools` 是專門為 SEC EDGAR 設計的 Python 套件，優點：

1. **直接解析 10-K 章節** - Business, Risk Factors, MD&A 等
2. **XBRL 自動處理** - 不需要手動解析 XML
3. **DataFrame 輸出** - 財務報表直接轉為 pandas
4. **內建速率限制** - 自動遵守 SEC 的 10 req/sec 限制

### 基本使用

```python
from edgar import set_identity, Company

# SEC 要求身份識別
set_identity("your.name@example.com")

# 取得公司
company = Company("AAPL")

# 取得 10-K 財報列表
filings_10k = company.get_filings(form="10-K")
print(f"10-K 數量: {len(filings_10k)}")  # 32 份

# 取得最新 10-K 的內容物件
ten_k = filings_10k[0].obj()
```

### 提取 10-K 章節內容

```python
# Item 1: Business 描述
business = ten_k.business
print(business[:500])

# Item 1A: Risk Factors
risk_factors = ten_k.risk_factors
print(risk_factors[:500])

# Item 7: Management's Discussion and Analysis
mda = ten_k.management_discussion
print(mda[:500])
```

### 實際輸出範例

```
Item 1.    Business

Company Background

The Company designs, manufactures and markets smartphones, personal
computers, tablets, wearables and accessories, and sells a variety
of related services...

Products:
- iPhone: iPhone 17 Pro, iPhone Air, iPhone 17, iPhone 16, iPhone 16e
- Mac: MacBook Air, MacBook Pro, iMac, Mac mini, Mac Studio, Mac Pro
- iPad: iPad Pro, iPad Air, iPad, iPad mini
- Wearables: Apple Watch, AirPods, Vision Pro
```

### 10-K 可用屬性

| 屬性 | 說明 |
|-----|------|
| `ten_k.business` | Item 1: 公司業務描述 |
| `ten_k.risk_factors` | Item 1A: 風險因素 |
| `ten_k.management_discussion` | Item 7: MD&A |
| `ten_k.financials` | Item 8: 財務報表 (XBRL) |
| `ten_k.balance_sheet` | 資產負債表 |
| `ten_k.income_statement` | 損益表 |
| `ten_k.cash_flow_statement` | 現金流量表 |
| `ten_k.items` | 所有章節列表 |

### Company Facts (XBRL 結構化數據)

```python
# 取得所有財務指標
facts = company.get_facts()

# 也可以直接用 SEC API
# GET /api/xbrl/companyfacts/CIK0000320193.json
```

### 與我們現有程式碼的整合

`edgartools` 可以作為 `sec_edgar_source.py` 的補充：

```python
# 現有: 取得 filing 列表和 XBRL facts
from data_sources.sec_edgar_source import SECEdgarDataSource
sec = SECEdgarDataSource()
filings = sec.fetch_sec_filings(['AAPL'], filing_types=['10-K'])
facts = sec.fetch_company_facts('AAPL')

# 新增: 用 edgartools 解析 10-K 章節內容
from edgar import Company
company = Company("AAPL")
ten_k = company.get_filings(form="10-K")[0].obj()
business_text = ten_k.business  # 直接取得純文字
```

---

## 推薦的數據源組合

| 數據類型 | 推薦來源 | 備用來源 |
|---------|---------|---------|
| 股價 | Tiingo | yfinance |
| 新聞 | Finnhub | Alpha Vantage (需過濾) |
| 財報數據 (結構化) | SEC EDGAR API | edgartools |
| 財報內容 (文字) | **edgartools** | SEC HTML |
| 即時報價 | Finnhub | Alpha Vantage |
| 公司資訊 | Polygon | Finnhub |

---

*最後更新: 2025-12-12*