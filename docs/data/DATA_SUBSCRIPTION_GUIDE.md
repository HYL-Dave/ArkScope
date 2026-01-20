# 數據訂閱完整指南

> **目的**: 記錄 AI Agent 自主發現板塊爆發模式所需的數據訂閱策略
> **最後更新**: 2026-01-19

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

由於 IBKR 是主要交易平台，充分利用其訂閱選項可以最大化價值。

### 市場數據訂閱 (Client Portal → Settings → Market Data)

| 訂閱項目 | 非專業月費 | 內容 | 建議 |
|---------|----------:|------|:----:|
| **US Equity & Options Bundle** | $4.50 | NYSE + NASDAQ + AMEX 即時串流 | ⭐⭐⭐ |
| **OPRA (Top of Book)** | $1.50 | 期權即時報價 (bid/ask/last/vol/OI) | ⭐⭐⭐ |
| **US Securities Snapshot Bundle** | $10.00 | 快照報價 (可用佣金抵免) | ⭐⭐ |

```
OPRA = Options Price Reporting Authority
     = 美國選擇權即時報價的官方數據源
     = 自建 Options Flow 的基礎數據
```

**費用抵免**: 如果月佣金 > $30，Snapshot Bundle 可抵免；佣金 > $5，Streaming Bundle 可抵免。

### 免費已包含

| 項目 | 說明 |
|------|------|
| **Cboe One + IEX** | 美股即時報價 (非整合) |
| **延遲數據** | 所有產品 15 分鐘延遲 |
| **100 快照/月** | 免費快照配額 |

### 研究訂閱 (Client Portal → Settings → Research Subscriptions)

```
路徑: Client Portal → 右上角頭像 → Settings → Research Subscriptions
```

| 服務 | 月費 | 用途 | 建議 |
|------|-----:|------|:----:|
| **Trading Central** | 免費 | 技術分析、自動化信號 | ⭐⭐ |
| **TipRanks** | 免費 | 分析師評級、目標價追蹤 | ⭐⭐ |
| **Seeking Alpha** | 免費 | 社群研究、股票評級 | ⭐ |
| **Morningstar** | 免費 | 基本面研究 | ⭐ |
| **Argus Research** | 免費 | 分析師報告、期權策略 | ⭐ |
| **Estimize** | 免費 | 眾包財報預估 (常優於華爾街共識) | ⭐⭐ |
| **Context Analytics** | 免費 | 社交媒體情緒分析 | ⭐ |
| **Market Chameleon** | 付費版可選 | 期權異常活動掃描 | ⭐⭐ |
| **Benzinga API** | $35 | 新聞 API 存取 | 可選 |

### 內建研究工具 (不需訂閱，直接使用)

```
路徑: Client Portal → Research → [工具名稱]
```

| 工具 | 用途 | 說明 |
|------|------|------|
| **Discover Tool** | 第三方內容整合 | 含 ORATS 回測、Trading Central 等 |
| **ORATS Backtester** | 期權策略回測 | 180+ 百萬歷史回測，免費 |
| **Fundamentals Explorer** | 財務比率、公司資料 | 基本面分析 |
| **Why Is It Moving?** | 股價漲跌原因 | Benzinga 提供 |
| **Events Calendar** | 財報、IPO、期權到期日 | 事件追蹤 |
| **Market Scanners** | 股票/ETF 掃描 | 價量篩選 |

### IBKR 推薦訂閱配置

```
┌─────────────────────────────────────────────────────────────┐
│                 IBKR 推薦訂閱配置                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [市場數據 - ~$6/月]                                         │
│  ├── US Equity & Options Bundle ─── $4.50 (可抵免)          │
│  └── OPRA (期權即時) ─────────────── $1.50                  │
│                                                             │
│  [新聞 - 免費，已啟用]                                       │
│  ├── Dow Jones Newswires ✓                                 │
│  ├── The Fly ✓                                             │
│  └── Briefing.com ✓                                        │
│                                                             │
│  [研究訂閱 - 免費，建議啟用]                                 │
│  ├── Trading Central ────── 技術分析                        │
│  ├── TipRanks ────────────── 分析師追蹤                     │
│  ├── Estimize ────────────── 眾包預估                       │
│  └── Context Analytics ──── 社交情緒                        │
│                                                             │
│  [內建工具 - 免費，直接使用]                                 │
│  ├── ORATS Backtester ───── 期權回測                        │
│  ├── Fundamentals Explorer ─ 基本面                         │
│  └── Events Calendar ────── 事件追蹤                        │
│                                                             │
│  [可選付費]                                                  │
│  ├── Benzinga API ────────── $35/月 (如需 API 新聞)         │
│  └── Market Chameleon Pro ── 付費 (進階期權掃描)            │
│                                                             │
└─────────────────────────────────────────────────────────────┘

IBKR 內訂閱總計: ~$6/月 (必要) + $35/月 (可選 Benzinga)
```

### 如何啟用研究訂閱

1. 登入 [Client Portal](https://portal.interactivebrokers.com/)
2. 點擊右上角**頭像圖示**
3. 選擇 **Settings**
4. 在 Trading Platform 區塊找到 **Research Subscriptions**
5. 點擊**齒輪圖示**設定
6. 勾選想要的服務 → Continue → 確認

**注意**: 部分服務有 30 天免費試用，試用後自動終止。

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

### 推薦配置

```
┌─────────────────────────────────────────────────────────────┐
│                    完整數據堆疊                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [付費訂閱 - $60/月]                                         │
│  ├── IBKR 即時數據 ──── 報價 + OPRA ($10)                   │
│  └── Unusual Whales ─── Options Flow + 國會交易 ($50)       │
│                                                             │
│  [免費 - 必須保留]                                           │
│  ├── IBKR 新聞 ──────── Dow Jones + The Fly + Briefing.com  │
│  ├── SEC EDGAR ──────── Form 4 (內部人) + Form 8-K (重大事件)│
│  ├── Quiver Quant ───── 政府合約                            │
│  └── Tiingo ─────────── 歷史股價 (備用)                     │
│                                                             │
│  [不需訂閱 - 用 LLM 增強]                                    │
│  ├── 事件類型標籤 ───── 調整 LLM prompt                      │
│  ├── 高管動態偵測 ───── 新聞關鍵詞 + LLM 分類                │
│  └── 板塊情緒聚合 ───── 自建 sector_stocks 映射              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
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

### 月度成本

| 項目 | 成本 | 必要性 |
|------|-----:|:------:|
| IBKR 即時數據 (NYSE + NASDAQ + OPRA) | $10 | ⭐⭐⭐ |
| Unusual Whales | $50 | ⭐⭐⭐ |
| Benzinga (IBKR) | $35 | ⭐ 可選 |
| **推薦總計** | **$60** | |
| 完整總計 (含 Benzinga) | $95 | |

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

考慮升級的情況：
1. 做 L3a (1-5 分鐘) 策略，需要更快新聞
2. 發現 IBKR 新聞漏掉重要突發消息
3. 需要 Benzinga 獨家內容

目前建議：先用現有配置，有明確痛點再升級。

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