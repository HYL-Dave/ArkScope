# 數據訂閱完整指南

> **目的**: 記錄 AI Agent 自主發現板塊爆發模式所需的數據訂閱策略
> **最後更新**: 2026-01-20

---

## 目錄

1. [目標：自主發現板塊爆發](#目標自主發現板塊爆發)
2. [數據需求分析](#數據需求分析)
3. [IBKR 訂閱詳解](#ibkr-訂閱詳解)
4. [新聞數據深度分析](#新聞數據深度分析)
5. [Options Flow 數據](#options-flow-數據)
6. [完整數據堆疊](#完整數據堆疊)
7. [成本總結](#成本總結)
8. [常見問題](#常見問題)

---

## 目標：自主發現板塊爆發

根據 [sector_breakout_patterns.md](../insights/sector_breakout_patterns.md) 的案例分析，AI Agent 需要捕捉以下信號：

```
板塊爆發三因子模型:

板塊大漲 = 政策催化 × 技術確認 × 資金共識

├── 政策催化 (30%): 行政命令、立法、補貼
├── 技術確認 (40%): 產品發布、技術突破
└── 資金共識 (30%): 期權異動、機構動態、IPO
```

### 信號與數據對照

| 信號類型 | 數據來源 | 當前狀態 |
|----------|----------|:--------:|
| 政策催化 | 新聞 + LLM 分類 | ✅ 有 |
| 人事異動 | 新聞 + SEC Form 8-K | ✅ 有 |
| 技術突破 | 新聞 + LLM 分類 | ✅ 有 |
| 期權異動 | Options Flow | ⚠️ 需訂閱或自建 |
| 資金共識 | 國會交易 + Options Flow | ⚠️ 部分 |

---

## 數據需求分析

### 已有數據源 (免費)

| 數據源 | 用途 | 數據量 | 狀態 |
|--------|------|--------|:----:|
| **IBKR 新聞** | Dow Jones, The Fly, Briefing.com | ~37,000 則/月 | ✅ 運作中 |
| **SEC EDGAR** | Form 4 (內部人交易), Form 8-K (重大事件) | - | ✅ 有 Parser |
| **Finnhub** | 補充新聞、公司資料 | - | ✅ 可用 |
| **Tiingo** | 歷史股價 | 30+ 年 | ✅ 可用 |
| **Quiver Quant** | 國會交易、政府合約 | - | ✅ 免費版可用 |

### 需要訂閱的數據

| 數據源 | 用途 | 月費 | 必要性 |
|--------|------|-----:|:------:|
| **IBKR 即時數據** | 即時報價 + OPRA | ~$10 | ⭐⭐⭐ 強烈建議 |
| **Unusual Whales** | Options Flow + 國會交易 | $50 | ⭐⭐⭐ 強烈建議 |
| **Benzinga (IBKR)** | 額外新聞來源 | $35 | ⭐ 可選 |

---

## IBKR 訂閱詳解

由於 IBKR 是主要交易平台，以下是根據實際 Client Portal 截圖整理的完整訂閱選項。

### ⚠️ 重要：API 可用性區分

**對於 AI Agent 自動化整合，只有 API 可存取的數據才有意義。**

| 類別 | API 可用？ | 說明 |
|------|:----------:|------|
| **市場數據 (報價)** | ✅ | `reqMktData()`, `reqHistoricalData()` |
| **新聞 (IBIS)** | ✅ | `reqNewsArticle()`, `reqHistoricalNews()` |
| **期權鏈 + Greeks** | ✅ | `reqSecDefOptParams()`, `reqMktData()` |
| **基本面 (有限)** | ✅ | `reqFundamentalData()` - Reuters 財報摘要 |
| **Benzinga via API** | ✅ | 需訂閱 $35/月，明確標示 "via API" |
| **Wall Street Horizon API** | ✅ | 需訂閱 $49/月，明確標示 "API" |
| **其他 Research 訂閱** | ❌ | GUI 整合，無 API |

---

### 市場數據訂閱 (Settings → Market Data Subscriptions)

#### Quote Bundles (套餐)

| 訂閱項目 | 月費 | 內容 | 抵免條件 |
|---------|-----:|------|---------|
| **US Equity & Options Add-On Streaming Bundle** | $4.50 | NYSE + AMEX + NASDAQ + OPRA 即時串流 | 需先訂閱 Snapshot Bundle |
| **US Securities Snapshot and Futures Value Bundle** | $10.00 | 美股快照 + 期貨 L1 | 佣金 > $30 可抵免 |
| **US Futures Value Bundle PLUS (L2)** | $5.00 | CBOT, CME, COMEX, NYMEX 深度 | 需先訂閱 Snapshot Bundle |
| **Cboe One Add-On Bundle** | $1.00 | Cboe 四個交易所 | 佣金 > $5 可抵免 |

#### Level I (NBBO) - 美股相關

| 訂閱項目 | 月費 | 內容 | 抵免條件 |
|---------|-----:|------|---------|
| **NYSE (Network A/CTA)** | $1.50 | NYSE 上市股票 | - |
| **NASDAQ (Network C/UTP)** | $1.50 | NASDAQ 上市股票 | - |
| **NYSE American, BATS, ARCA, IEX (Network B)** | $1.50 | AMEX 等交易所 | - |
| **OPRA (US Options Exchanges)** | $1.50 | 美國期權報價 ⭐ | 佣金 > $20 可抵免 |
| **Cboe One** | $1.00 | Cboe 四個交易所 | - |
| **OTC Markets** | $8.00 | 場外交易股票 | - |
| **US Mutual Funds** | 免費 | 共同基金 | - |

#### Level I (NBBO) - 期貨相關

| 訂閱項目 | 月費 | 內容 | 抵免條件 |
|---------|-----:|------|---------|
| **CME Real-Time** | $1.55 | ES, NQ, HE 等 | 佣金 > $20 可抵免 |
| **CBOT Real-Time** | $1.55 | YM, ZB, ZC 等 | 佣金 > $20 可抵免 |
| **NYMEX Real-Time** | $1.55 | CL, RB, NG 等 | 佣金 > $20 可抵免 |
| **COMEX Real-Time** | $1.55 | GC, SI, HG 等 | 佣金 > $20 可抵免 |

#### Level II (Deep Book)

| 訂閱項目 | 月費 | 內容 |
|---------|-----:|------|
| **NASDAQ TotalView-OpenView** | $16.50 | NASDAQ 深度 |
| **NYSE OpenBook** | $25.00 | NYSE 深度 |
| **NYSE ArcaBook** | $11.00 | NYSE Arca 深度 |
| **CME Real-Time (L2)** | $12.10 | CME 期貨深度 (佣金 > $20 可抵免) |

#### 免費已包含

| 項目 | 說明 |
|------|------|
| **US Real-Time Non Consolidated (IBKR-PRO)** | BATS, BYX, EDGX 等五交易所即時報價 ✓ |
| **US Mutual Funds** | 共同基金報價 ✓ |
| **CME Event Contracts** | CME 事件合約 ✓ |
| **US and EU Bond Quotes** | 債券報價 ✓ |
| **ICE Futures US - Digital Asset / Gold Silver** | 比特幣、黃金白銀期貨 ✓ |

---

### 研究訂閱 (Settings → Research Subscriptions)

#### IBIS Research Platform (免費!) ⭐

```
這是最重要的免費服務，已包含大量數據：
```

| 包含內容 | 說明 |
|----------|------|
| **新聞** | Dow Jones, Reuters, Briefing.com, The Fly |
| **基本面** | 財報、共識預估、比率、SEC 申報、內部人交易 |
| **事件日曆** | 財報、經濟指標、IPO、拆股 |
| **分析師研究** | Morningstar, Zacks 報告 |
| **升降級公告** | 追蹤賣方研究活動 |
| **市場評論** | 宏觀經濟、產業焦點、盤中更新 |

**注意**: IBIS 新聞可透過 TWS API 存取 (`reqNewsArticle`)，這就是你目前在用的！

#### Premium Newswires (付費新聞)

| 服務 | 月費 | API | 說明 |
|------|-----:|:---:|------|
| **Benzinga Breaking News via API (NP)** | $35 | ✅ | 明確標示 "via API" |
| **Dow Jones Institutional News** | $78 | ❌ | 更全面的 DJ 新聞 |
| **StreetInsider Premium** | $49 | ❌ | 市場動態新聞 |
| **TipRanks Premium News** | $4.99 | ❌ | 分析師新聞 |

#### Analyst Research (分析師研究)

| 服務 | 月費 | 說明 |
|------|-----:|------|
| **Smartkarma Previews** | 免費 | 亞太研究摘要 |
| **MacroRisk Analytics Previews** | 免費 | 經濟研究摘要 |
| **TFI Securities** | 免費 | 港股、A股、美股研究 |
| **MarketEdge NP** | $9.45 | 技術分析報告 |
| **Morningstar Reports** | $15 | 股票、ETF、信用報告 |

#### Technical Analysis (技術分析)

| 服務 | 月費 | 說明 |
|------|-----:|------|
| **Trading Central Technical Insight** | 免費 | 技術分析信號 ⭐ |
| **Simpler Trading (TTM Squeeze, Wave A/B/C 等)** | $50 各 | 進階技術指標 |

#### Third Party Services (第三方服務)

| 服務 | 月費 | API | 說明 |
|------|-----:|:---:|------|
| **Wall Street Horizon** | 免費 | ❌ | 企業事件日曆 |
| **Wall Street Horizon (API)** | $49 | ✅ | 企業事件數據 API |
| **TipRanks Basic** | 免費 | ❌ | 5 檔股票提醒 |
| **TipRanks Premium** | $29.99 | ❌ | 完整分析師追蹤 |
| **TipRanks Ultimate** | $49.99 | ❌ | 最完整版 |
| **Market Chameleon Total Access** | $99 | ❌ | 期權異常掃描 |
| **Reflexivity Basic** | 免費 | ❌ | AI 投資分析 |
| **Capitalise** | 免費 | ❌ | 自然語言交易自動化 |
| **Passiv Community** | 免費 | ❌ | 投資組合再平衡 |
| **Zacks Rank Trading Tool** | $9 | ❌ | Zacks 評級工具 |

#### Market Commentary (市場評論)

| 服務 | 月費 | 說明 |
|------|-----:|------|
| **Crowdwisers Macro** | $10 | 宏觀分析 |
| **Validea Guru Stock Reports** | $10.80 | 大師策略評級 |
| **ValuEngine ETF** | $5 | ETF 評級 |
| **InsiderInsights Pro Trader** | $54.45 | 內部人交易分析 |

---

### 有 API 的研究訂閱 (可整合 LLM)

```
只有這兩個 Research 訂閱明確標示有 API：
```

| 服務 | 月費 | 用途 |
|------|-----:|------|
| **Benzinga Breaking News via API** | $35 | 即時新聞 API |
| **Wall Street Horizon Corporate Event Data (API)** | $49 | 企業事件日曆 API |

**其他所有 Research 訂閱都是 GUI only，只能在 TWS/Portal 介面查看。**

### IBKR 推薦訂閱配置

```
┌─────────────────────────────────────────────────────────────┐
│              IBKR 推薦訂閱配置                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ✅ 已有 (免費，API 可用)                                   │
│  ─────────────────────────────────────────────────────────  │
│  ├── IBIS Research Platform ────── DJ, Reuters, The Fly 新聞│
│  ├── US Real-Time Non Consolidated ─ 基本美股即時報價       │
│  └── 基本面數據 ──────────────────── reqFundamentalData()   │
│                                                             │
│  ⭐ 建議訂閱 (API 可用)                                     │
│  ─────────────────────────────────────────────────────────  │
│  ├── OPRA (期權 L1) ──────────────── $1.50/月 (佣金>$20免)  │
│  ├── 或 US Equity & Options Bundle ─ $4.50/月 (含 OPRA)    │
│  └── 可選: Benzinga API ────────────── $35/月 (如需更快新聞)│
│                                                             │
│  📚 免費啟用 (GUI only，手動研究)                           │
│  ─────────────────────────────────────────────────────────  │
│  ├── Trading Central Technical Insight                     │
│  ├── TipRanks Basic                                        │
│  ├── Wall Street Horizon (事件日曆)                        │
│  ├── Reflexivity Basic                                     │
│  └── Capitalise (自然語言交易)                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

最小成本配置: OPRA $1.50/月 (佣金 > $20 可抵免，等於免費)
建議配置: US Equity & Options Bundle $4.50/月 (更完整)
```

### 訂閱路徑

**Market Data Subscriptions:**
1. Client Portal → 頭像 → Settings
2. 找到 **Market Data Subscriptions**
3. 選擇 North America → 勾選所需項目

**Research Subscriptions:**
1. Client Portal → 頭像 → Settings
2. 找到 **Research Subscriptions**
3. 勾選想要的服務 → Continue → 確認

**注意**:
- 大部分 Research 訂閱只在 TWS/Portal 介面顯示
- 只有 **Benzinga via API** 和 **Wall Street Horizon API** 可程式化存取

---

## 新聞數據深度分析

### 新聞速度層級

```
┌─────────────────────────────────────────────────────────────┐
│                      新聞速度金字塔                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Tier 0: 微秒級 (無法取得)                                   │
│  └── 機構專線、Colocation、$500K+/年                        │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  Tier 1: 秒級 (專業終端)                                    │
│  ├── Bloomberg Terminal ($2,000/月)                        │
│  ├── Reuters Eikon ($1,800/月)                             │
│  └── Dow Jones Newswires 直連                              │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  Tier 2: 秒~分鐘級 (我們在這裡) ⭐                          │
│  ├── Dow Jones (via IBKR) ← 已有                           │
│  ├── The Fly (via IBKR) ← 已有                             │
│  ├── Benzinga Pro ($35-166/月)                             │
│  ├── Briefing.com ← 已有                                   │
│  └── 這些服務之間差異「幾秒」，對 L3b 無意義                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 現有 IBKR 新聞來源分析

```
目前已有 (via IBKR API，免費):

├── DJ-N (Dow Jones Newswires) ─── 30,907 則/月
│   └── 最權威來源：WSJ、Barron's 等
│
├── FLY (The Fly) ──────────────── 4,318 則/月
│   └── 研報摘要、分析師評級彙整
│
├── BRFUPDN/BRFG (Briefing.com) ── 1,392 則/月
│   └── 市場評論、盤前摘要
│
└── 總計: ~37,000 則/月
```

### Benzinga 是否需要？

| 問題 | 答案 |
|------|------|
| Benzinga 比 Dow Jones 快嗎？ | ❌ 不是，Dow Jones 是源頭 |
| Benzinga 比 The Fly 快嗎？ | 可能快幾秒，但無實質差異 |
| L3b 策略需要 Benzinga 嗎？ | ❌ 現有來源已足夠 |
| 什麼時候需要 Benzinga？ | 做 L3a (1-5 分鐘) 且發現漏新聞時 |

**結論**: 對 L3b (15 分鐘) 策略，現有的 Dow Jones + The Fly + Briefing.com 已經足夠，不需要額外訂閱 Benzinga。

---

## Options Flow 數據

### 什麼是 Options Flow？

**一句話**: 監測「大戶」(機構、對沖基金) 的期權交易行為，因為他們往往比散戶更早知道消息。

### 為什麼重要？

```
案例：ASTS 太空板塊爆發 (2026-01-02)

時間線:
├── 12/10  ASTS Jan $30 Call: 成交量突然是 OI 的 3 倍
├── 12/15  出現 $2.3M 的 Call Sweep (跨 4 個交易所)
├── 12/18  IV percentile 飆到 95%
└── 01/02  太空板塊爆發，ASTS 大漲

結論: Options Flow 可以比新聞早 2-3 週發現異常
```

### 關鍵信號類型

| 信號 | 定義 | 強度 |
|------|------|:----:|
| **Sweep** | 同一期權在 5 秒內跨多交易所掃貨 | 🔥🔥🔥 |
| **Block** | 單筆 > $1M 或 > 100 contracts | 🔥🔥 |
| **Unusual Volume** | 當日成交量 >> 2x OI | 🔥 |
| **IV Spike** | IV percentile > 90% | 🔥 |

### 取得方式比較

| 方式 | 成本 | 工作量 | 適合 |
|------|-----:|:------:|------|
| **IBKR OPRA 自建** | $1.50/月 | 高 | 享受開發 |
| **Unusual Whales** | $50/月 | 零 | 重視效果 |
| **FlowAlgo** | $149/月 | 零 | 專業日內 |

### 服務比較

| 服務 | 月費 | 特色 | 適合 |
|------|-----:|------|------|
| **Unusual Whales** | $50 | 國會交易、初學者友善、有 API | 性價比最高 |
| **Cheddar Flow** | $85 | 簡潔介面、Dark Pool | 中階 |
| **FlowAlgo** | $149 | 最快 (快 2-3 秒)、專業級 | 專業日內 |

**建議**: Unusual Whales $50/月 是最佳選擇，因為：
- 包含 Options Flow + 國會交易
- 有 API 可整合
- 性價比高

詳細說明見 [OPTIONS_FLOW_GUIDE.md](./OPTIONS_FLOW_GUIDE.md)

---

## 完整數據堆疊

### 推薦配置 (全部 API 可存取)

```
┌─────────────────────────────────────────────────────────────┐
│            完整數據堆疊 (全部可自動化)                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [IBKR 免費] API ✓                                          │
│  ├── IBIS 新聞 ────────── Dow Jones + The Fly + Briefing    │
│  ├── IBIS 基本面 ──────── 財報、SEC、內部人交易              │
│  ├── 基本即時報價 ────── Cboe One + IEX (非整合)            │
│  └── 期權鏈 + Greeks ─── reqSecDefOptParams()               │
│                                                             │
│  [IBKR 付費 - $1.50~4.50/月] API ✓                          │
│  ├── OPRA ──────────────── $1.50 (期權 L1，佣金>$20 免)     │
│  └── US Equity Bundle ─── $4.50 (含 OPRA + 股票串流)        │
│                                                             │
│  [外部付費 - $50/月] API ✓                                  │
│  └── Unusual Whales ───── Options Flow + 國會交易           │
│                                                             │
│  [免費外部] API ✓                                           │
│  ├── SEC EDGAR ────────── Form 4 + Form 8-K                │
│  ├── Quiver Quant ────── 政府合約 (有限 API)                │
│  └── Tiingo ──────────── 歷史股價                           │
│                                                             │
│  [可選 IBKR 付費] API ✓                                     │
│  ├── Benzinga API ────── $35 (更快新聞)                     │
│  └── WSH Event API ───── $49 (企業事件)                     │
│                                                             │
│  [手動參考 - GUI only]                                      │
│  └── Trading Central, TipRanks Basic 等 ─── 免費啟用        │
│                                                             │
└─────────────────────────────────────────────────────────────┘

最小成本: $50-51.50/月 (IBIS免費 + OPRA$1.50 + UW$50)
建議成本: $54.50/月 (IBIS免費 + Bundle$4.50 + UW$50)
```

### 信號覆蓋度

| 信號 | 數據來源 | 覆蓋 |
|------|----------|:----:|
| 政策催化 | IBKR 新聞 (Dow Jones) + LLM | ✅ |
| 人事異動 | IBKR 新聞 + SEC Form 8-K | ✅ |
| 技術突破 | IBKR 新聞 + LLM 分類 | ✅ |
| 期權異動 | Unusual Whales | ✅ |
| 國會交易 | Unusual Whales | ✅ |
| 政府合約 | Quiver Quantitative | ✅ |
| 內部人交易 | SEC Form 4 | ✅ |
| 板塊聚合 | 自建 sector mapping | ✅ |

---

## 成本總結

### 月度成本 (可自動化的訂閱)

| 項目 | 成本 | API | 必要性 | 說明 |
|------|-----:|:---:|:------:|------|
| IBIS (新聞 + 基本面) | 免費 | ✅ | ⭐⭐⭐ | 已包含 DJ, The Fly |
| OPRA (期權 L1) | $1.50 | ✅ | ⭐⭐⭐ | 佣金 > $20 可抵免 |
| US Equity & Options Bundle | $4.50 | ✅ | ⭐⭐ | 含 OPRA + 股票串流 |
| Unusual Whales | $50 | ✅ | ⭐⭐⭐ | Options Flow + 國會交易 |
| **最小配置** | **$50-51.50** | | | IBIS + OPRA + UW |
| **建議配置** | **$54.50** | | | IBIS + Bundle + UW |

### 可選付費 (有 API)

| 項目 | 成本 | API | 說明 |
|------|-----:|:---:|------|
| Benzinga via API | $35 | ✅ | 如需更快新聞 |
| Wall Street Horizon API | $49 | ✅ | 企業事件日曆 API |

### 免費可啟用 (GUI only，手動研究)

| 項目 | 說明 |
|------|------|
| Trading Central | 技術分析信號 |
| TipRanks Basic | 分析師追蹤 (5 檔) |
| Reflexivity Basic | AI 投資分析 |
| Wall Street Horizon | 事件日曆 (非 API) |
| Capitalise | 自然語言交易 |
| Smartkarma Previews | 亞太研究 |

### 與不訂閱的比較

```
不訂閱 Options Flow:
├── 只能靠新聞事後分析
├── 無法發現 Smart Money 提前佈局
└── 錯過 1-2 週的領先信號

訂閱 Unusual Whales ($50/月):
├── Options Flow: Sweep, Block, Volume Spike
├── 國會交易: 政客的持倉變化
├── API 整合: 可自動化
└── 相當於每天 $1.67
```

---

## 常見問題

### Q: IBKR 新聞和 Finnhub 新聞有什麼不同？

| 項目 | IBKR 新聞 | Finnhub 新聞 |
|------|----------|-------------|
| 來源 | Dow Jones, The Fly (頂級) | 多來源聚合 |
| 延遲 | 秒級 | 分鐘級 |
| 數量 | ~37,000/月 | ~20,000/月 |
| API | 需要 IB Gateway | REST API |

**結論**: IBKR 新聞品質更高，Finnhub 作為備用或補充。

### Q: 為什麼不用 Polygon.io 替代全部？

| Polygon.io 優點 | Polygon.io 缺點 |
|-----------------|-----------------|
| 整合報價 + 新聞 + Options | $199/月 (完整版) |
| < 20ms 延遲 | 很多功能與 IBKR 重疊 |
| 2003 年起歷史數據 | 無國會交易、政府合約 |

**結論**: 如果已有 IBKR，Polygon.io 的 CP 值不高。

### Q: 什麼時候應該升級到 Benzinga？

**更正**: IBKR 的 "Benzinga Breaking News via API (NP)" ($35/月) **確實有 API 存取**，這是在 Research Subscriptions 中明確標示的。

考慮升級的情況：
1. 做 L3a (1-5 分鐘) 策略，需要更快新聞
2. 發現 IBIS 免費新聞 (DJ, The Fly) 漏掉重要突發消息
3. 需要 Benzinga 獨家的盤前/盤後摘要

目前建議：先用現有 IBIS 免費新聞 (Dow Jones + The Fly + Briefing.com)，這些已經是頂級來源。

### Q: IBKR 研究訂閱可以整合到 AI Agent 嗎？

**大部分不能，但有例外。**

**有 API 的研究訂閱 (可整合):**
- **Benzinga Breaking News via API** ($35/月) - 明確標示 "via API"
- **Wall Street Horizon Corporate Event Data (API)** ($49/月) - 明確標示 "API"

**無 API 的研究訂閱 (GUI only):**
- Trading Central, TipRanks, Market Chameleon 等都只在 TWS/Portal 介面顯示
- 無法程式化存取，無法整合到 LLM pipeline

**IBKR 免費且有 API 的數據:**
- IBIS 新聞 (Dow Jones, The Fly, Briefing.com) - `reqNewsArticle()`
- 市場數據 (報價、歷史價格) - `reqMktData()`, `reqHistoricalData()`
- 期權鏈和 Greeks - `reqSecDefOptParams()`
- 基本面數據 - `reqFundamentalData()`

### Q: 自建 Options Flow 值得嗎？

| 自建 | 訂閱 Unusual Whales |
|------|---------------------|
| $1.50/月 | $50/月 |
| 需要 2-3 天開發 | 即開即用 |
| 完全可控 | 依賴第三方 |
| 無歷史數據回測 | 有歷史數據 |
| 無國會交易 | 含國會交易 |

**結論**: 除非享受開發過程，否則訂閱更划算。

---

## 相關文件

- [OPTIONS_FLOW_GUIDE.md](./OPTIONS_FLOW_GUIDE.md) - Options Flow 詳細指南
- [TRADING_FREQUENCY_DATA_STRATEGY.md](./TRADING_FREQUENCY_DATA_STRATEGY.md) - 交易頻率與數據策略
- [L3_DAY_TRADING_FEASIBILITY.md](./L3_DAY_TRADING_FEASIBILITY.md) - L3 日內交易可行性
- [sector_breakout_patterns.md](../insights/sector_breakout_patterns.md) - 板塊爆發模式案例

---

## 參考資源

- [Elite Trader - Fastest News Sources](https://www.elitetrader.com/et/threads/what-is-the-fastest-text-based-news-source-for-stock-headlines.386813/)
- [Unusual Whales](https://unusualwhales.com/)
- [IBKR Research & News](https://www.interactivebrokers.com/en/pricing/research-news-services.php)
- [Quiver Quantitative](https://www.quiverquant.com/)

---

*創建者: Claude Code*
*版本: 1.0*