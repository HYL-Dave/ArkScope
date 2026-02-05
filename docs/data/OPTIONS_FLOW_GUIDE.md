# Options Flow 指南

> **目的**: 理解 Options Flow 的概念、用途、以及如何取得數據
> **最後更新**: 2026-01-19

---

## 目錄

1. [什麼是 Options Flow](#什麼是-options-flow)
2. [為什麼期權能透露資訊](#為什麼期權能透露資訊)
3. [關鍵信號類型](#關鍵信號類型)
4. [數據取得方式](#數據取得方式)
5. [服務比較](#服務比較)
6. [自建偵測系統](#自建偵測系統)
7. [整合建議](#整合建議)

---

## 什麼是 Options Flow

**一句話定義**: 監測「大戶」(機構、對沖基金) 的期權交易行為，因為他們往往比散戶更早知道消息。

```
Options Flow = 即時追蹤大額/異常的期權交易
             = 觀察 "Smart Money" 的動向
             = 潛在的領先指標
```

### 核心價值

| 傳統分析 | Options Flow 分析 |
|----------|-------------------|
| 看新聞後反應 | 在新聞前發現異常 |
| 分析已發生的事 | 預測即將發生的事 |
| 跟隨市場 | 跟隨 Smart Money |

---

## 為什麼期權能透露資訊

### 機構為何偏好期權？

```
假設某機構知道 ASTS 下週會宣布大合約:

選項 A: 直接買股票
├── 需要大量資金
├── 買入會推高股價，暴露意圖
└── SEC 可能調查內線交易

選項 B: 買 Call 期權 ⭐
├── 小資金撬動大收益 (槓桿效應)
├── 不直接影響股價
└── 相對隱蔽
```

### 期權市場的領先性

```
時間線示例:

T-14 天  機構開始買入 Call 期權
         └── Options Flow 可偵測到異常

T-7 天   期權 IV 開始上升
         └── 市場隱約感知「有事要發生」

T-0 天   新聞發布，股價暴漲
         └── 散戶此時才知道

結論: 期權市場常「領先」股價 1-2 週
```

---

## 關鍵信號類型

### 1. Sweep (掃單)

| 項目 | 說明 |
|------|------|
| **定義** | 同一期權在短時間內 (< 5秒) 跨多個交易所成交 |
| **含義** | 買家急著買入，不惜吃掉多個交易所的賣單 |
| **強度** | 🔥🔥🔥 最強信號之一 |

```
示例:
ASTS Jan $30 Call
├── 10:15:01 CBOE  買入 500 contracts @ $2.10
├── 10:15:02 PHLX  買入 300 contracts @ $2.12
├── 10:15:03 ISE   買入 400 contracts @ $2.15
└── 總計: 1,200 contracts 在 3 秒內跨 3 交易所

解讀: 有人非常急著建立多頭部位
```

### 2. Block Trade (大宗交易)

| 項目 | 說明 |
|------|------|
| **定義** | 單筆交易金額 > $1M 或 > 100 contracts |
| **含義** | 機構級資金進場 |
| **強度** | 🔥🔥 強信號 |

### 3. Unusual Volume (異常成交量)

| 項目 | 說明 |
|------|------|
| **定義** | 當日成交量 >> 未平倉量 (OI) 的 2 倍以上 |
| **含義** | 突然有人大量建立新倉位 |
| **強度** | 🔥 中等信號 |

```
示例:
ASTS Jan $30 Call
├── Open Interest: 5,000
├── 今日 Volume: 15,000 (3x OI!)
└── 解讀: 大量新資金湧入這個期權
```

### 4. IV Spike (隱含波動率飆升)

| 項目 | 說明 |
|------|------|
| **定義** | IV percentile > 90% (歷史高位) |
| **含義** | 市場預期即將有大波動 |
| **強度** | 🔥 輔助確認信號 |

### 信號強度組合

```
最強組合 (高度關注):
├── Sweep + Block + IV Spike
└── 多個信號同時出現在同一標的

中等組合 (值得追蹤):
├── Unusual Volume + IV 上升
└── 單一 Sweep 無其他確認

弱信號 (僅供參考):
└── 單一小額 Block
```

---

## 數據取得方式

### 方式對比

| 方式 | 成本 | 工作量 | 數據品質 | 適合 |
|------|-----:|:------:|:--------:|------|
| **IBKR 自建** | $1.50/月 | 高 | 原始數據 | 享受開發的人 |
| **訂閱服務** | $50-150/月 | 零 | 已分析過濾 | 重視效果的人 |

### IBKR 原始數據 vs 訂閱服務

```
IBKR 原始數據 ($1.50/月 OPRA):
├── 提供: 每筆成交的 time, price, size, exchange
├── 不提供: 是否為 Sweep、方向判斷、歷史分析
└── 需要: 自己寫偵測邏輯

訂閱服務 (如 Unusual Whales $50/月):
├── 提供: 已分析的 Sweep/Block 信號
├── 提供: Bullish/Bearish 方向判斷
├── 提供: 歷史數據、回測功能
└── 提供: API 整合
```

---

## 服務比較

### 主要服務商

| 服務 | 月費 | 年費 (月均) | 特色 | 適合 |
|------|-----:|:-----------:|------|------|
| **Unusual Whales** | $50 | $44 | 國會交易、初學者友善、有 API | 初學者、性價比 |
| **Cheddar Flow** | $85 | $75 | 簡潔介面、Dark Pool (Pro $99) | 中階交易者 |
| **FlowAlgo** | $149 | $99 | 最快速度 (快 2-3 秒)、專業級 | 專業日內交易 |

### 功能對比

| 功能 | Unusual Whales | Cheddar Flow | FlowAlgo |
|------|:--------------:|:------------:|:--------:|
| Sweep 偵測 | ✅ | ✅ | ✅ |
| Block 偵測 | ✅ | ✅ | ✅ |
| Dark Pool | ✅ | Pro 版 | ✅ |
| 國會交易 | ✅ | ❌ | ❌ |
| API | ✅ | ❌ | ✅ |
| 歷史數據 | ✅ | ✅ | ✅ |
| 速度 | 中 | 中 | 最快 |

### 選擇建議

```
如果你是...

初學者 / 想了解概念:
└── Unusual Whales $50/月 (介面友善、有教學)

重視效果 / 不想花時間開發:
└── Unusual Whales $50/月 (性價比最高、有 API)

專業日內交易 / 需要最快速度:
└── FlowAlgo $149/月 (比其他快 2-3 秒)

喜歡自己開發 / 預算有限:
└── IBKR OPRA $1.50/月 + 自建系統
```

---

## 自建偵測系統

### 架構概覽

```
┌─────────────────────────────────────────────────────────────┐
│                  自建 Options Flow 系統                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [1. 取得期權鏈]                                             │
│  ├── reqSecDefOptParams() → 取得所有 strikes, expirations   │
│  └── 過濾: 近期到期 + ATM 附近                               │
│                                                             │
│  [2. 訂閱 Tick-by-Tick 數據]                                │
│  ├── reqTickByTickData(contract, 'AllLast')                │
│  └── 每筆成交: time, price, size, exchange                  │
│                                                             │
│  [3. 異常偵測邏輯]                                           │
│  ├── Sweep: 5 秒內跨 2+ 交易所                              │
│  ├── Block: 單筆 > 100 contracts                           │
│  └── Volume Spike: volume > 2x OI                          │
│                                                             │
│  [4. 輸出信號]                                               │
│  └── DB / 通知 / insights 文件                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Python 實作範例

```python
"""
Options Flow 自建偵測系統核心邏輯
完整程式碼見: data_sources/options_flow_detector.py (待建立)
"""
from ib_async import IB, Option

class OptionsFlowDetector:
    """偵測 Sweep, Block, Volume Spike"""

    # 偵測參數
    SWEEP_TIME_WINDOW = 5      # 秒
    SWEEP_MIN_EXCHANGES = 2    # 最少跨幾個交易所
    BLOCK_MIN_SIZE = 100       # contracts
    VOLUME_OI_RATIO = 2.0      # volume > 2x OI

    def detect_sweep(self, ticks: list) -> bool:
        """
        Sweep 偵測: 短時間內跨多交易所成交
        """
        window_ticks = [t for t in ticks if t.age < self.SWEEP_TIME_WINDOW]
        exchanges = set(t.exchange for t in window_ticks)
        return len(exchanges) >= self.SWEEP_MIN_EXCHANGES

    def detect_block(self, tick) -> bool:
        """
        Block 偵測: 單筆大單
        """
        return tick.size >= self.BLOCK_MIN_SIZE

    def detect_volume_spike(self, daily_volume: int, open_interest: int) -> bool:
        """
        Volume Spike 偵測: 成交量異常
        """
        return daily_volume > open_interest * self.VOLUME_OI_RATIO
```

### IBKR 限制與解決方案

| 限制 | 說明 | 解決方案 |
|------|------|----------|
| Tick-by-tick 上限 | 同時最多 5 個合約 | 分批訂閱、優先監控高關注標的 |
| 無歷史 OI | tick 數據不含 OI | 每日收盤後另外抓取 |
| 無 IV 計算 | 需自行計算 | 用 reqMktData 取得 impliedVol |

---

## 整合建議

### 與 AI Agent 整合

```
數據流:
Options Flow 信號
    │
    ▼
[整合到 LLM 評分]
    │
    ├── 新聞情緒: 4 (正面)
    ├── 風險: 2 (低)
    └── Options Flow: BULLISH_SWEEP ← 新增
    │
    ▼
[AI Agent 決策]
    └── 多因子確認 → 更高信心度
```

### 與 sector_breakout_patterns.md 整合

```
板塊爆發偵測增強:
├── 政策催化 (新聞)
├── 技術突破 (新聞)
├── 人事異動 (新聞 + SEC Form 4)
└── Options Flow ⭐ 新增
    ├── 板塊內多股同時出現 Sweep
    ├── IV 整體上升
    └── Smart Money 共識信號
```

---

## 參考資源

- [Unusual Whales](https://unusualwhales.com/) - Options Flow 服務
- [FlowAlgo](https://flowalgo.com/) - 專業級 Options Flow
- [IBKR Tick-by-Tick API](https://interactivebrokers.github.io/tws-api/tick_data.html)
- [ib_async Documentation](https://ib-api-reloaded.github.io/ib_async/api)

---

## 相關文件

- [TRADING_FREQUENCY_DATA_STRATEGY.md](./TRADING_FREQUENCY_DATA_STRATEGY.md) - 交易頻率與數據策略
- [L3_DAY_TRADING_FEASIBILITY.md](./L3_DAY_TRADING_FEASIBILITY.md) - L3 日內交易可行性
- [sector_breakout_patterns.md](../insights/sector_breakout_patterns.md) - 板塊爆發模式

---

*創建者: Claude Code*
*版本: 1.0*