# 美股 + 選擇權交易完整數據訂閱清單

> 最後更新：2026-01-18
>
> 本文件整理所有對美股和選擇權交易有幫助的數據來源，包含免費和付費選項。

---

## 目錄

1. [價格與市場數據](#-第一類價格與市場數據)
2. [選擇權流動分析](#-第二類選擇權流動分析-smart-money-訊號)
3. [新聞與情緒數據](#-第三類新聞與情緒數據)
4. [另類數據](#️-第四類另類數據-alpha-來源)
5. [基本面數據](#-第五類基本面數據)
6. [日曆與事件](#-第六類日曆與事件)
7. [技術分析與執行](#-第七類技術分析與執行)
8. [訂閱組合建議](#-訂閱組合建議)
9. [優先級總結](#-優先級總結)
10. [關鍵發現](#️-關鍵發現)

---

## 📊 第一類：價格與市場數據

| 數據類型 | Provider | 價格 | 必要性 | 說明 |
|---------|----------|------|:------:|------|
| **股票即時報價** | [IBKR](https://interactivebrokers.github.io/tws-api/) | 免費(有帳戶) | ✅ 必備 | 執行用 |
| **股票歷史價格** | [Tiingo](https://www.tiingo.com/) | 免費 | ✅ 必備 | 30+年 EOD |
| **Options 即時報價** | [Polygon/Massive](https://massive.com/) | $29/月 | ✅ 必備 | 即時 Greeks |
| **Options 歷史數據** | [ORATS](https://orats.com/data-api) | $99/月 | ⭐ 高價值 | 2007年起，含 IV surface |
| **Options Greeks/IV** | [ORATS Live](https://orats.com/blog/new-live-data-api-for-options-prices-greeks-theos-and-ivs) | +$50/月 | ⭐ 高價值 | 10秒延遲 |

### 補充說明

- **IBKR** 是唯一能同時提供數據和執行交易的平台
- **Tiingo** 免費方案提供 30+ 年 EOD 數據，足夠回測使用
- **ORATS** 是 Options 數據的業界黃金標準，提供：
  - 平滑化的 IV surface
  - 高品質 Greeks（Delta, Gamma, Theta, Vega, Rho）
  - Implied Earnings Move（財報預期波動）
  - 30/60/90天、6個月、1年插值 IV

---

## 📈 第二類：選擇權流動分析 (Smart Money 訊號)

| 數據類型 | Provider | 價格 | 必要性 | 說明 |
|---------|----------|------|:------:|------|
| **Unusual Options Activity** | [Unusual Whales](https://unusualwhales.com/pricing) | $48/月 | ⭐⭐ 極高 | 即時異常單偵測 |
| **Options Flow** | [FlowAlgo](https://www.flowalgo.com/) | ~$100/月 | ⭐ 高價值 | Block trades + Sweeps |
| **Dark Pool Prints** | [Unusual Whales](https://unusualwhales.com/) | 含上方 | ⭐⭐ 極高 | 機構隱藏交易 |
| **Options Flow (替代)** | [InsiderFinance](https://www.insiderfinance.io/flow) | ~$50-100/月 | 可選 | 智能資金追蹤 |
| **Options Flow (替代)** | [Cheddar Flow](https://www.cheddarflow.com/) | ~$100/月 | 可選 | 進階篩選 |
| **Options Flow (替代)** | [OptionStrat Flow](https://optionstrat.com/flow) | 待查 | 可選 | 含期貨 Options |
| **Options Flow (替代)** | [WhaleStream](https://www.whalestream.com/) | $69/月 | 可選 | Dark Pool 監控 |
| **Options Flow (替代)** | [BlackBoxStocks](https://blackboxstocks.com/) | 待查 | 可選 | 13,000 股票監控 |

### 為何這類數據極其重要？

```
Smart Money 足跡：
├── Block Trades: 單筆 > 10,000 股或 $200,000
├── Sweep Orders: 跨多交易所分散執行 (最高緊迫性)
├── 異常 Volume: 超過 30 日均量 500%+
└── OTM Calls/Puts 大單: 預期重大波動

為何比新聞更快：
├── 機構通常在新聞發布**前**就已布局
├── 消息經常提前洩漏
├── 內線人士透過選擇權市場行動
└── 例如: AMD 在財報前有大量 $120 Call Sweep → 財報後漲 20%
```

---

## 📰 第三類：新聞與情緒數據

| 數據類型 | Provider | 價格 | 必要性 | 說明 |
|---------|----------|------|:------:|------|
| **即時新聞** | [Benzinga Pro](https://www.benzinga.com/apis/) | ~$99/月 | ⭐ 高價值 | 原創新聞最快 |
| **新聞 (免費)** | [Finnhub](https://finnhub.io/) | 免費 | ✅ 必備 | ~7天歷史 |
| **新聞 + 情緒** | [Polygon](https://polygon.io/) | $29/月 | 含即時報價 | AI 情緒分數 |
| **社群情緒** | [Finnhub Premium](https://finnhub.io/) | $75+/月 | ⭐ 高價值 | Reddit/Twitter |
| **即時新聞 (專業)** | [IBKR Dow Jones](https://interactivebrokers.github.io/tws-api/news.html) | ~$10-20/月 | 可選 | 專業級最快 |
| **新聞聚合** | [Massive + Benzinga](https://massive.com/blog/tag/announcement) | $29/月 | 可選 | 分析師評級+財報 |

### 新聞時效性研究結論

```
Alpha 衰減時間表：
┌─────────────────────────────────────────────────────────┐
│  訊號類型          │ Alpha 衰減時間    │ 備註          │
├─────────────────────────────────────────────────────────┤
│  高頻量化訊號      │ 分鐘 → 小時       │ 已被套利      │
│  新聞情緒訊號      │ 4 小時達峰值      │ 之後遞減      │
│  正面事件衝擊      │ ~2 天            │ 快速消化       │
│  負面事件衝擊      │ ~5 天            │ 消化較慢       │
│  小型股新聞        │ 衰減更慢          │ 流動性低      │
│  PEAD (盈餘漂移)   │ 60-90 天         │ 最持久的異常   │
└─────────────────────────────────────────────────────────┘

結論：新聞延遲 1 天仍可操作負面消息和小型股
```

---

## 🏛️ 第四類：另類數據 (Alpha 來源)

| 數據類型 | Provider | 價格 | 必要性 | 說明 |
|---------|----------|------|:------:|------|
| **內線交易 (Form 4)** | [Finnhub](https://finnhub.io/) / SEC | 免費 | ✅ 必備 | 內部人買賣 |
| **國會交易** | [Quiver Quantitative](https://www.quiverquant.com/congresstrading/) | 免費/付費 | ⭐⭐ 極高 | 議員持股變動 |
| **國會交易 (替代)** | [Finnhub Premium](https://finnhub.io/) | $75+/月 | 可選 | 更完整 API |
| **機構持股 (13F)** | SEC EDGAR / Finnhub | 免費 | ✅ 必備 | 季度揭露 |
| **Short Interest** | [FINRA](https://developer.finra.org/docs) | 免費 | ✅ 必備 | 雙週更新 |
| **Short Interest (即時)** | [ORTEX](https://public.ortex.com/) | ~$50-100/月 | ⭐ 高價值 | 每日更新，70K+證券 |
| **ESG 評分** | [Finnhub Premium](https://finnhub.io/) | $75+/月 | 可選 | 環境/社會/治理 |
| **專利數據** | [Finnhub Premium](https://finnhub.io/) | $75+/月 | 可選 | 創新追蹤 |

### 國會交易數據

Quiver Quantitative 提供：
- 自 2016 年起的美國參眾兩院交易記錄
- 依據 STOCK Act，議員須在 45 天內公開申報
- Python API: `quiver.congress_trading("TSLA")`
- 免費版已足夠基本使用

### Short Interest 數據比較

| 來源 | 更新頻率 | 覆蓋範圍 | 價格 |
|------|---------|---------|------|
| FINRA | 雙週 | 美股 | 免費 |
| ORTEX | 每日/即時 | 70,000+ 證券 | ~$50-100/月 |

> ⚠️ 注意：每日 Short Volume ≠ Short Interest，不可直接換算

---

## 📑 第五類：基本面數據

| 數據類型 | Provider | 價格 | 必要性 | 說明 |
|---------|----------|------|:------:|------|
| **財務報表** | SEC EDGAR / IBKR | 免費 | ✅ 必備 | 10-K/10-Q |
| **財務報表 (結構化)** | [sec-api.io](https://sec-api.io/docs/sec-filings-item-extraction-api) | $0.05/section | 可選 | 自動解析 |
| **財務指標** | 自建 (FinancialMetricsCalculator) | 免費 | ✅ 必備 | 39 項指標 |
| **分析師預估** | [Zacks via Intrinio](https://docs.intrinio.com/documentation/web_api/get_zacks_eps_estimates_v2) | ~$50+/月 | ⭐ 高價值 | EPS 預測 |
| **分析師預估 (替代)** | [FactSet](https://developer.factset.com/api-catalog/factset-estimates-api) | 企業級 | 可選 | 800+ 分析師 |
| **Segmented Revenue** | [Financial Datasets](https://www.financialdatasets.ai/) | $30/月 | ⭐⭐ **獨家** | 唯一提供者 |

### sec-api.io 功能

```
支援 API：
├── Extractor API: 10-K/10-Q/8-K 章節提取 ($0.05/section)
├── XBRL-to-JSON: 財報轉 JSON
├── Query API: 18M+ 文件搜尋
├── Full-Text Search: 2001年起全文搜尋
├── Stream API: 即時推送 (WebSocket)
└── Download API: PDF 生成

特點：
├── 1993年起所有 EDGAR 文件
├── 新文件 300ms 內可用
└── 支援 Python SDK
```

### Financial Datasets 獨家功能

**Segmented Revenue API** 是市場上**唯一**提供分部營收數據的 API：
- 按業務線拆分收入
- 按地理區域拆分收入
- 無任何免費或其他付費替代方案

---

## 📅 第六類：日曆與事件

| 數據類型 | Provider | 價格 | 必要性 | 說明 |
|---------|----------|------|:------:|------|
| **財報日曆** | [Finnhub](https://finnhub.io/) / [EODHD](https://eodhd.com/) | 免費 | ✅ 必備 | 財報發布日 |
| **經濟日曆** | [Trading Economics](https://tradingeconomics.com/api/calendar.aspx) | 免費/付費 | ⭐ 高價值 | FOMC/CPI 等 |
| **Earnings Whispers** | [Earnings Whispers](https://www.earningswhispers.com/) | ~$15/月 | 可選 | 市場預期 vs 共識 |
| **股息/拆股日曆** | [EODHD](https://eodhd.com/) | $19.99/月 | 可選 | 企業行動 |
| **經濟日曆 (替代)** | [FXStreet](https://docs.fxstreet.com/api/calendar/) | 待查 | 可選 | Webhooks 支援 |
| **財報日曆 (串流)** | [Trading Economics](https://docs.tradingeconomics.com/financials/streaming/) | 付費 | 可選 | WebSocket 即時 |

### Earnings Whispers 價值

```
Whisper Number vs 共識預測：
├── Whisper 平均比分析師預測更準確
├── 打敗 Whisper → 平均單日漲 2%+
├── 打敗共識但錯過 Whisper → 僅漲 0.1%
└── 基於 Whisper 的策略顯著跑贏 S&P 500
```

---

## 🔧 第七類：技術分析與執行

| 數據類型 | Provider | 價格 | 必要性 | 說明 |
|---------|----------|------|:------:|------|
| **技術指標 API** | [Alpha Vantage](https://www.alphavantage.co/) | $49.99/月 | 可選 | 50+ 指標 |
| **技術指標 (免費)** | [Polygon](https://polygon.io/) | $29/月 | 含即時報價 | SMA/EMA/RSI |
| **交易執行** | [IBKR](https://www.interactivebrokers.com/) | $0+ | ✅ **必備** | 唯一能執行 |
| **交易執行 (替代)** | [Alpaca](https://alpaca.markets/) | 免費 | 可選 | 零佣金 API |
| **交易執行 (替代)** | [Tradier](https://tradier.com/) | ~$10/月 | 可選 | Options 專精 |

### 交易執行平台比較

| 平台 | 優點 | 缺點 | 最適合 |
|------|------|------|--------|
| **IBKR** | 90+ 市場、最低費用、專業級 | API 較複雜 | 專業交易者 |
| **Alpaca** | 零佣金、API 友善、Paper Trading | 僅美股 | 開發者/新手 |
| **Tradier** | Options 專精、API 簡潔 | 覆蓋較少 | Options 交易者 |

> ⚠️ **TD Ameritrade API 已停用** - Schwab 收購後已關閉，不要等待

### Alpha Vantage 2025 新功能

- **MCP Server 支援**: 第一個支援 AI-native 整合的金融 API
- 允許 LLM 直接查詢金融數據
- 獲 NASDAQ 和 OPRA 授權

---

## 💰 訂閱組合建議

### 方案 A：基礎版 (~$80/月)

```
必備免費：
├── IBKR (執行 + 即時報價)
├── Finnhub (新聞 + 內線交易)
├── SEC EDGAR (財務報表)
├── Tiingo (歷史價格)
├── Quiver Quantitative (國會交易)
└── FINRA (Short Interest)

付費：
├── Polygon ($29) - Options 即時 + 新聞情緒
└── Unusual Whales ($48) - Options Flow + Dark Pool
```

**覆蓋**: 即時報價、Options Flow、Dark Pool、基本新聞、內線交易、國會交易

---

### 方案 B：進階版 (~$180/月)

```
方案 A 全部 +
├── ORATS ($99) - Options 歷史 + Greeks + IV surface
└── Trading Economics (免費版) - 經濟日曆
```

**增加**: 完整 Options Greeks/IV 歷史、回測能力、經濟事件追蹤

---

### 方案 C：專業版 (~$330/月)

```
方案 B 全部 +
├── Finnhub Premium ($75) - 社群情緒 + 國會交易完整版 + ESG
├── ORTEX (~$50) - 即時 Short Interest
└── ORATS Live (+$50) - 10秒延遲 Greeks
```

**增加**: 社群情緒 (Reddit/Twitter)、即時 Short Interest、ESG 評分、專利數據

---

### 方案 D：完整版 (~$430/月)

```
方案 C 全部 +
├── Financial Datasets ($30) - Segmented Revenue (獨家)
└── Benzinga (~$99) - 專業級即時新聞
```

**增加**: 分部營收數據 (唯一來源)、最快原創新聞

---

### 方案 E：頂級版 (~$530/月)

```
方案 D 全部 +
├── Zacks/Intrinio (~$50) - 分析師預估
├── Earnings Whispers (~$15) - Whisper Numbers
└── sec-api.io (按需) - 結構化 SEC 文件
```

**增加**: EPS 預測、市場預期數據、自動化 SEC 文件解析

---

## 🎯 優先級總結

| 優先級 | 數據類型 | 最佳選擇 | 月費 | 為何重要 |
|:------:|---------|---------|-----:|---------|
| 1️⃣ | 交易執行 | IBKR | $0-30 | 唯一能將策略變現 |
| 2️⃣ | Options Flow + Dark Pool | Unusual Whales | $48 | Smart Money 訊號，比新聞更快 |
| 3️⃣ | Options 即時報價 | Polygon | $29 | 即時 Greeks 和定價 |
| 4️⃣ | Options 歷史 + Greeks | ORATS | $99 | 回測和策略開發必備 |
| 5️⃣ | 另類數據 | Finnhub Premium | $75 | 社群情緒、ESG、專利 |
| 6️⃣ | Short Interest | ORTEX | $50 | 即時空頭數據 |
| 7️⃣ | Segmented Revenue | Financial Datasets | $30 | **唯一來源**，無替代 |
| 8️⃣ | 專業新聞 | Benzinga | $99 | 最快原創新聞 |
| 9️⃣ | 分析師預估 | Zacks/Intrinio | $50 | EPS 預測準確度 |
| 🔟 | Whisper Numbers | Earnings Whispers | $15 | 市場真實預期 |

---

## ⚠️ 關鍵發現

### 1. Options Flow/Dark Pool 是最高價值訊號

```
訊號時效性排序（從快到慢）：
1. 異常選擇權活動 (分鐘級) ← 最有價值
2. Dark Pool 大單 (分鐘級)
3. 社群情緒 (小時級)
4. 內線交易申報 (小時-天級)
5. 新聞 (已是最慢) ← 價格已反應
```

> **當你看到新聞時，你已經落後了**

### 2. Financial Datasets Segmented Revenue 無替代

- 這是市場上**唯一**提供分部營收 API 的服務
- 對於分析多元化公司（如 Amazon、Alphabet）極其重要
- $30/月 是獲取此數據的唯一方式

### 3. ORATS 是 Options 數據的黃金標準

- 唯一同時提供即時 + 歷史 + 高品質 Greeks 的服務
- Implied Earnings Move 功能獨特
- 但價格較高 ($99-149/月)

### 4. 免費數據已覆蓋大部分基礎需求

```
免費可得：
├── 股票歷史價格 (Tiingo)
├── 財務報表 (SEC EDGAR)
├── 內線交易 (Finnhub/SEC)
├── 國會交易 (Quiver)
├── 機構持股 (SEC 13F)
├── Short Interest (FINRA，雙週)
├── 基本新聞 (Finnhub)
└── 財報日曆 (Finnhub)
```

### 5. 已停用或不建議的服務

| 服務 | 狀態 | 建議 |
|------|------|------|
| TD Ameritrade API | ❌ 已停用 | 改用 IBKR 或 Alpaca |
| IEX Cloud | ❌ 2024/8/31 停用 | 改用 Polygon 或 Alpha Vantage |
| Yahoo Finance | ⚠️ 非官方 | 僅供參考，不建議依賴 |

---

## 📚 參考資源

### 官方文檔

- [ORATS API Documentation](https://docs.orats.io/)
- [Polygon.io API](https://polygon.io/docs)
- [Finnhub API](https://finnhub.io/docs/api)
- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [IBKR TWS API](https://interactivebrokers.github.io/tws-api/)
- [Alpaca API](https://alpaca.markets/docs/)
- [Quiver API](https://api.quiverquant.com/docs/)
- [FINRA API](https://developer.finra.org/docs)

### 評測文章

- [Best Stock Market APIs 2025 - HackerNoon](https://hackernoon.com/best-stock-market-data-apis-for-algorithmic-traders-2025-edition)
- [Best Brokers for Algo Trading 2026 - BrokerChooser](https://brokerchooser.com/best-brokers/best-brokers-for-algo-trading-in-the-united-states)
- [Unusual Whales Review 2025](https://bullishbears.com/unusual-whales-review/)
- [ORATS Review 2025](https://bullishbears.com/orats-option-scanner-review/)

### 學術研究

- [Alpha Decay Research - Maven Securities](https://www.mavensecurities.com/alpha-decay-what-does-it-look-like-and-what-does-it-mean-for-systematic-traders/)
- [PEAD 50 Years Research - Quantpedia](https://quantpedia.com/50-years-in-pead-research/)
- [Twitter Sentiment Predictive Power - CEPR](https://cepr.org/voxeu/columns/twitter-sentiment-and-stock-market-movements-predictive-power-social-media)

---

*此文件應定期更新以反映最新價格和服務變動*