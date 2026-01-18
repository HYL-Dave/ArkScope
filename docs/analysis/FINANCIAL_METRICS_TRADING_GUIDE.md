# Financial Metrics 交易導向學習指南

> **目標**: 從交易者角度理解 39 個財務指標，建立對數字的直覺
> **使用方式**: 作為學習參考，有問題隨時標記並討論

---

## 目錄

1. [核心概念框架](#1-核心概念框架)
2. [Profitability Metrics - 獲利能力](#2-profitability-metrics---獲利能力指標)
3. [Liquidity Metrics - 流動性](#3-liquidity-metrics---流動性指標)
4. [Leverage Metrics - 槓桿/償債能力](#4-leverage-metrics---槓桿償債能力指標)
5. [Efficiency Metrics - 營運效率](#5-efficiency-metrics---營運效率指標)
6. [Valuation Metrics - 估值](#6-valuation-metrics---估值指標)
7. [Growth Metrics - 成長性](#7-growth-metrics---成長性指標)
8. [Per-Share Metrics - 每股指標](#8-per-share-metrics---每股指標)
9. [指標間的關聯性](#9-指標間的關聯性)
10. [Trading Signals 應用](#10-trading-signals-應用)

---

## 1. 核心概念框架

### 1.1 財務報表基礎

財務指標來自三大報表：

```
┌─────────────────────────────────────────────────────────────────┐
│                    Income Statement (損益表)                      │
│    Revenue → Gross Profit → Operating Income → Net Income        │
│    "公司這段期間賺了多少錢"                                         │
├─────────────────────────────────────────────────────────────────┤
│                    Balance Sheet (資產負債表)                      │
│    Assets = Liabilities + Shareholders' Equity                   │
│    "公司現在有什麼、欠什麼、股東擁有什麼"                             │
├─────────────────────────────────────────────────────────────────┤
│                    Cash Flow Statement (現金流量表)                │
│    Operating CF + Investing CF + Financing CF = Net Change       │
│    "現金實際流入流出多少"                                           │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 指標的交易意義分類

| 類別 | 回答的問題 | 交易相關性 |
|------|-----------|-----------|
| **Profitability** | 公司賺錢效率如何？ | ⭐⭐⭐ 獲利是股價的根本支撐 |
| **Liquidity** | 公司短期會不會倒？ | ⭐⭐ 危機預警信號 |
| **Leverage** | 公司借了多少錢？ | ⭐⭐ 風險評估 |
| **Efficiency** | 資產運用得好不好？ | ⭐⭐ 營運品質指標 |
| **Valuation** | 股價貴不貴？ | ⭐⭐⭐⭐ 直接影響買賣決策 |
| **Growth** | 公司在成長還是衰退？ | ⭐⭐⭐⭐ 預測未來股價 |
| **Per-Share** | 每股值多少？ | ⭐⭐⭐ 與股價直接比較 |

### 1.3 行業差異重要性

**關鍵認知**: 不同行業的「正常值」差異極大！

| 行業 | 特徵 | 典型指標範圍 |
|------|------|-------------|
| **科技 (AAPL, MSFT)** | 輕資產、高毛利 | 毛利率 60-80%, P/E 25-35 |
| **零售 (WMT, COST)** | 低毛利、高周轉 | 毛利率 20-30%, 存貨周轉 8-12 |
| **銀行 (JPM, BAC)** | 高槓桿、利差收入 | D/E 8-12, ROE 10-15% |
| **公用事業 (NEE)** | 穩定、高負債 | D/E 1-2, 股息率 3-5% |
| **生技 (MRNA)** | 研發密集、波動大 | 可能無獲利, P/S 看營收 |

---

## 2. Profitability Metrics - 獲利能力指標

> **核心問題**: 公司把營收轉化為利潤的效率如何？

### 2.1 Gross Margin (毛利率)

```
公式: Gross Profit / Revenue
     = (Revenue - Cost of Goods Sold) / Revenue

白話: 每賣 $100，扣掉直接成本後剩多少
```

**直覺建立**:

- 毛利率反映**產品/服務的基本獲利能力**
- 高毛利 = 產品有定價能力、品牌價值、或技術護城河
- 低毛利 = 競爭激烈、薄利多銷

**行業參考**:

| 行業 | 典型毛利率 | 範例 |
|------|-----------|------|
| 軟體 SaaS | 70-85% | MSFT: 69%, CRM: 74% |
| 消費品牌 | 50-65% | AAPL: 47%, NKE: 44% |
| 零售 | 20-35% | WMT: 25%, COST: 13% |
| 航空 | 15-25% | DAL: 20% |

**交易信號**:
- ✅ 毛利率穩定或上升 → 定價能力維持
- ⚠️ 毛利率下降 → 可能面臨競爭壓力或成本上升
- 🔴 毛利率大幅低於同業 → 結構性問題

**AAPL 實例**:
```
FY2025 毛利率: 46.91%
解讀: 每賣 $100 iPhone/Mac/服務，扣掉製造成本後剩 $46.91
     這在硬體公司中算高，因為品牌溢價 + 服務收入佔比提升
```

---

### 2.2 Operating Margin (營業利益率)

```
公式: Operating Income / Revenue
     = (Revenue - COGS - Operating Expenses) / Revenue

白話: 扣掉所有營運成本後，每 $100 營收剩多少
```

**與毛利率的差異**:
```
Revenue
  - COGS (製造/採購成本)
  ─────────────────────
  = Gross Profit (毛利)        ← Gross Margin 看這裡
  - R&D (研發)
  - SG&A (銷管費用)
  - Other Operating Expenses
  ─────────────────────
  = Operating Income (營業利益)  ← Operating Margin 看這裡
```

**直覺建立**:
- 營業利益率反映**核心業務的真實獲利能力**
- 包含了研發、行銷、管理等必要支出
- 比毛利率更能反映公司的經營效率

**交易信號**:
- 毛利率高但營業利益率低 → 費用控制差，或研發投入大
- 營業利益率改善 → 規模效應或成本優化

**AAPL 實例**:
```
FY2025 營業利益率: 31.97%
毛利率 46.91% - 營業利益率 31.97% = 14.94%
解讀: 14.94% 的營收用於研發和銷管，這比例相當健康
```

---

### 2.3 Net Margin (淨利率)

```
公式: Net Income / Revenue

白話: 所有成本、費用、稅、利息扣完後，最終剩多少
```

**損益表完整路徑**:
```
Revenue                          $416,161M (100%)
- COGS                          -$220,960M
= Gross Profit                   $195,201M (46.9%)
- Operating Expenses             -$62,151M
= Operating Income               $133,050M (32.0%)
- Interest Expense               -$2,921M
+ Other Income                   +$2,506M
= Pre-tax Income                 $132,635M
- Income Tax                     -$20,625M
= Net Income                     $112,010M (26.9%) ← 淨利率
```

**直覺建立**:
- 淨利率是最終的「落袋為安」
- 受到利息支出（負債多少）和稅率影響
- 用於計算 EPS，直接影響股價

**AAPL 實例**:
```
FY2025 淨利率: 26.92%
解讀: 每 $100 營收最終變成 $26.92 的股東利潤
     這是非常優秀的淨利率（科技業平均約 15-20%）
```

---

### 2.4 Return on Equity (ROE, 股東權益報酬率)

```
公式: Net Income / Shareholders' Equity

白話: 股東投入的每 $1，一年能賺回多少
```

**核心概念**:
- ROE 是衡量**股東投資回報**最重要的指標之一
- 巴菲特最愛看的指標：「長期而言，股票回報約等於 ROE」

**ROE 的拆解 (DuPont Analysis)**:
```
ROE = Net Margin × Asset Turnover × Equity Multiplier
    = (淨利/營收) × (營收/資產) × (資產/股東權益)
    = 獲利能力   ×   資產效率   ×   財務槓桿

高 ROE 可能來自:
1. 高淨利率 (好) - 產品有定價能力
2. 高資產周轉 (好) - 資產運用效率高
3. 高槓桿 (風險) - 借很多錢
```

**行業參考**:

| 行業 | 典型 ROE | 說明 |
|------|---------|------|
| 科技 | 20-40% | 輕資產、高獲利 |
| 消費品 | 15-25% | 品牌價值 |
| 銀行 | 10-15% | 高槓桿但利差薄 |
| 公用事業 | 8-12% | 穩定但受管制 |

**AAPL 實例**:
```
FY2025 ROE: 151.9% (!)
解讀: 這數字異常高，原因是 AAPL 大量回購股票
     Shareholders' Equity = $73.7B (很低)
     Net Income = $112.0B (很高)

     ROE 超過 100% 表示:
     - 股東權益很低（回購 + 負債）
     - 獲利能力極強

     這種情況下 ROE 的參考價值降低，要看其他指標
```

---

### 2.5 Return on Assets (ROA, 資產報酬率)

```
公式: Net Income / Total Assets

白話: 公司的每 $1 資產，一年能產生多少利潤
```

**與 ROE 的關係**:
```
ROE = ROA × Equity Multiplier
    = ROA × (Assets / Equity)
    = ROA × (1 + Debt/Equity)

如果 ROE 很高但 ROA 低 → 高槓桿驅動
如果 ROE 和 ROA 都高 → 真正的優質公司
```

**行業參考**:

| 行業 | 典型 ROA | 說明 |
|------|---------|------|
| 軟體 | 15-25% | 輕資產 |
| 製造 | 5-10% | 重資產 |
| 零售 | 5-8% | 存貨佔比高 |
| 銀行 | 1-2% | 資產負債表巨大 |

**AAPL 實例**:
```
FY2025 ROA: 31.18%
解讀: 極高的 ROA，說明:
     1. 資產利用效率非常高
     2. 獲利能力強
     這比 ROE 151% 更能反映真實經營能力
```

---

### 2.6 Return on Invested Capital (ROIC, 投資資本報酬率)

```
公式: NOPAT / Invested Capital
     = Operating Income × (1 - Tax Rate) / (Equity + Debt - Cash)

白話: 投入的資本（不管是股東的還是借的），能產生多少稅後營業利潤
```

**為什麼 ROIC 比 ROE 更好？**
```
ROE 的問題:
- 可以透過增加負債來「美化」
- 不反映真正的資本效率

ROIC 的優勢:
- 同時考慮股東資本和債務資本
- 稅後營業利潤排除了財務槓桿影響
- 更能反映核心業務的資本效率
```

**ROIC vs WACC**:
```
WACC (Weighted Average Cost of Capital) = 公司的資金成本

如果 ROIC > WACC → 創造價值 (每投入 $1 創造超過 $1 價值)
如果 ROIC < WACC → 毀滅價值 (不如把錢還給股東)

典型 WACC: 8-12%
優秀 ROIC: 15%+
```

**AAPL 實例**:
```
FY2025 ROIC: 77.03%
解讀: 極高的 ROIC，遠超任何 WACC
     說明 AAPL 的資本配置效率極高
     每投入 $1 資本，產生 $0.77 的稅後營業利潤
```

---

### Profitability 指標總結

```
┌────────────────────────────────────────────────────────────┐
│                    AAPL Profitability 全景                  │
├────────────────────────────────────────────────────────────┤
│  Revenue  ════════════════════════════════════>  $416.2B   │
│     │                                                      │
│     ├──> Gross Margin: 46.9%    "產品獲利能力強"            │
│     │                                                      │
│     ├──> Operating Margin: 32.0% "營運效率優秀"            │
│     │                                                      │
│     └──> Net Margin: 26.9%       "最終落袋豐厚"            │
│                                                            │
│  Asset Efficiency ─────────────────────────────────────    │
│     │                                                      │
│     ├──> ROA: 31.2%              "資產運用極佳"            │
│     │                                                      │
│     ├──> ROE: 151.9%             "受回購影響，參考性低"     │
│     │                                                      │
│     └──> ROIC: 77.0%             "資本效率頂級"            │
└────────────────────────────────────────────────────────────┘
```

---

## 3. Liquidity Metrics - 流動性指標

> **核心問題**: 公司短期內能不能付得起帳單？會不會週轉不靈？

### 3.1 Current Ratio (流動比率)

```
公式: Current Assets / Current Liabilities

白話: 一年內能變現的資產 / 一年內要付的債務
```

**Current Assets 包括**:
- Cash (現金)
- Marketable Securities (短期投資)
- Accounts Receivable (應收帳款)
- Inventory (存貨)
- Prepaid Expenses (預付費用)

**Current Liabilities 包括**:
- Accounts Payable (應付帳款)
- Short-term Debt (短期借款)
- Accrued Expenses (應計費用)
- Deferred Revenue (遞延收入)

**直覺建立**:
```
Current Ratio = 1.0 → 剛好打平，有點危險
Current Ratio = 1.5 → 有 50% 緩衝，算健康
Current Ratio = 2.0 → 很安全，但可能資金運用不夠積極
Current Ratio < 1.0 → 流動負債 > 流動資產，需要關注
```

**AAPL 實例**:
```
FY2025 Current Ratio: 0.893
Current Assets: $147.96B
Current Liabilities: $165.63B

解讀: Current Ratio < 1 通常是警訊，但 AAPL 是例外
原因:
1. 極強的現金產生能力 (每季 $25B+ 營運現金流)
2. 供應商願意給長賬期 (應付帳款很高)
3. 信用評級 AAA，隨時可以借到錢
4. 這是刻意的財務策略，不是危機
```

---

### 3.2 Quick Ratio (速動比率)

```
公式: (Current Assets - Inventory) / Current Liabilities

白話: 排除存貨後，快速能變現的資產 / 短期負債
```

**為什麼要排除存貨？**
- 存貨變現需要時間（賣出去）
- 存貨可能跌價（過時、損壞）
- Quick Ratio 更保守、更嚴格

**參考範圍**:
```
Quick Ratio > 1.0 → 良好
Quick Ratio 0.5-1.0 → 需關注但不一定危險
Quick Ratio < 0.5 → 可能有流動性風險
```

**AAPL 實例**:
```
FY2025 Quick Ratio: 0.859
= (147,957 - 5,717) / 165,631
= 142,240 / 165,631

解讀: AAPL 存貨只有 $5.7B (占流動資產 3.9%)
     所以 Quick Ratio 和 Current Ratio 差不多
     對於像汽車、零售這種存貨佔比高的公司，差異會更大
```

---

### 3.3 Cash Ratio (現金比率)

```
公式: Cash and Equivalents / Current Liabilities

白話: 最嚴格的流動性測試 - 純現金能付多少短期債務
```

**直覺建立**:
- Cash Ratio 是最保守的指標
- 不考慮應收帳款能否收回
- 不考慮存貨能否賣掉

**參考範圍**:
```
Cash Ratio > 0.5 → 現金充裕
Cash Ratio 0.2-0.5 → 正常範圍
Cash Ratio < 0.2 → 現金偏緊
```

**AAPL 實例**:
```
FY2025 Cash Ratio: 0.217
Cash: $35.93B
Current Liabilities: $165.63B

解讀: 純現金只能覆蓋 21.7% 的短期負債
     但 AAPL 還有 $35B 的短期投資 (Marketable Securities)
     加上去後實際流動性更好
```

---

### 3.4 Operating Cash Flow Ratio (營運現金流比率)

```
公式: Operating Cash Flow / Current Liabilities

白話: 一年的營運現金流能付多少短期債務
```

**這個指標的獨特價值**:
- 前三個指標看的是「存量」(資產負債表時點)
- 這個指標看的是「流量」(一年的現金流入)
- 反映公司**持續產生現金**的能力

**AAPL 實例**:
```
FY2025 Operating Cash Flow Ratio: 0.673
Operating Cash Flow: $111.48B
Current Liabilities: $165.63B

解讀: AAPL 一年的營運現金流能付掉 67.3% 的短期負債
     這非常健康！
     說明即使流動資產不夠，持續的現金流也能應付
```

---

### Liquidity 指標總結

```
┌────────────────────────────────────────────────────────────┐
│                    Liquidity 階梯圖                         │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  最寬鬆 ──────────────────────────────────────> 最嚴格    │
│                                                            │
│  Current Ratio    Quick Ratio    Cash Ratio                │
│  (含全部流動資產)  (排除存貨)     (只看現金)                 │
│       0.893          0.859          0.217                  │
│                                                            │
│  + Operating Cash Flow Ratio: 0.673 (流量角度)              │
│                                                            │
├────────────────────────────────────────────────────────────┤
│  AAPL 結論:                                                │
│  - 傳統流動性指標偏低，但這是刻意的財務策略                   │
│  - 營運現金流強勁，實際流動性無虞                            │
│  - 對於 AAA 評級的公司，這些指標參考性降低                   │
└────────────────────────────────────────────────────────────┘
```

---

## 4. Leverage Metrics - 槓桿/償債能力指標

> **核心問題**: 公司借了多少錢？還得起嗎？

### 4.1 Debt to Equity (負債權益比, D/E)

```
公式: Total Debt / Shareholders' Equity

白話: 每 $1 股東權益，配了多少債務
```

**直覺建立**:
```
D/E = 0.5 → 借的錢是股東權益的一半，槓桿低
D/E = 1.0 → 借的錢等於股東權益，中等槓桿
D/E = 2.0 → 借的錢是股東權益的兩倍，高槓桿
D/E > 3.0 → 非常高的槓桿，風險較大
```

**行業差異**:

| 行業 | 典型 D/E | 說明 |
|------|---------|------|
| 科技 | 0.3-0.8 | 輕資產，少借錢 |
| 製造 | 0.5-1.5 | 需要設備投資 |
| 公用事業 | 1.0-2.0 | 資本密集，穩定現金流支撐 |
| 銀行 | 8-15 | 負債經營是核心模式 |
| 房地產 | 1.5-3.0 | 資產抵押借款 |

**AAPL 實例**:
```
FY2025 D/E: 1.338
Total Debt: $98.66B
Shareholders' Equity: $73.73B

解讀:
- 看起來槓桿中等偏高
- 但要考慮 AAPL 有 $35.9B 現金 + $35.2B 短期投資
- Net Debt = $98.66B - $71.1B = $27.56B
- Net D/E = $27.56B / $73.73B = 0.37 (很低!)
- 實際財務風險極低
```

---

### 4.2 Debt to Assets (負債資產比)

```
公式: Total Debt / Total Assets

白話: 資產中有多少比例是借錢買的
```

**與 D/E 的關係**:
```
假設: Assets = Debt + Equity (簡化)

D/E = Debt / Equity
D/A = Debt / Assets = Debt / (Debt + Equity)

如果 D/E = 1.0, 則 D/A = 1/(1+1) = 0.5 (50%)
如果 D/E = 2.0, 則 D/A = 2/(2+1) = 0.67 (67%)
```

**直覺建立**:
```
D/A < 30% → 保守財務結構
D/A 30-50% → 中等槓桿
D/A 50-70% → 高槓桿
D/A > 70% → 非常高槓桿
```

**AAPL 實例**:
```
FY2025 D/A: 27.46%
Total Debt: $98.66B
Total Assets: $359.24B

解讀: 只有 27.46% 的資產是債務融資
     財務結構相當保守
```

---

### 4.3 Interest Coverage (利息保障倍數)

```
公式: Operating Income / Interest Expense
或:   EBIT / Interest Expense

白話: 營業利潤是利息支出的多少倍
```

**直覺建立**:
```
Interest Coverage < 1.5 → 危險！利息壓力大
Interest Coverage 1.5-3 → 需要關注
Interest Coverage 3-5 → 良好
Interest Coverage > 5 → 非常安全
Interest Coverage > 10 → 利息支出幾乎可忽略
```

**AAPL 實例**:
```
FY2025 Interest Coverage: null (或非常高)

Operating Income: $133.05B
Interest Expense: 很低或淨利息收入

解讀: AAPL 的利息收入可能大於支出
     因為持有大量現金和有價證券
     所以這個指標對 AAPL 意義不大
```

---

### Leverage 指標總結

```
┌────────────────────────────────────────────────────────────┐
│                    AAPL Leverage 分析                       │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  帳面槓桿:                                                  │
│    D/E = 1.34    (中等)                                    │
│    D/A = 27.5%   (保守)                                    │
│                                                            │
│  實際槓桿 (扣除現金):                                       │
│    Net Debt = $98.7B - $71.1B = $27.6B                     │
│    Net D/E = 0.37  (很低!)                                 │
│                                                            │
│  結論: AAPL 實際財務風險極低                                │
│        帳面負債是為了稅務優化和資本效率                      │
└────────────────────────────────────────────────────────────┘
```

---

## 5. Efficiency Metrics - 營運效率指標

> **核心問題**: 公司的資產運用效率如何？營運資金管理好不好？

### 5.1 Asset Turnover (資產周轉率)

```
公式: Revenue / Total Assets

白話: 每 $1 資產能產生多少營收
```

**直覺建立**:
- 高資產周轉 = 資產運用效率高 = 「薄利多銷」模式
- 低資產周轉 = 資產重 = 「高毛利」模式通常資產周轉較低

**行業差異**:

| 行業 | 典型資產周轉率 | 說明 |
|------|--------------|------|
| 零售 | 2.0-3.0 | 存貨快速周轉 |
| 餐飲 | 1.5-2.5 | 高頻消費 |
| 製造 | 0.8-1.5 | 重資產 |
| 科技 | 0.5-1.0 | 輕資產但營收不夠多 |
| 公用事業 | 0.3-0.5 | 極重資產 |

**AAPL 實例**:
```
FY2025 Asset Turnover: 1.16
Revenue: $416.16B
Total Assets: $359.24B

解讀: 每 $1 資產產生 $1.16 營收
     對科技公司來說很高
     說明資產運用效率優秀
```

---

### 5.2 Inventory Turnover (存貨周轉率)

```
公式: COGS / Average Inventory  (標準方法)
或:   Revenue / Inventory       (簡化方法)

白話: 一年賣掉幾批存貨
```

**直覺建立**:
```
Inventory Turnover = 4  → 一年賣4輪，每批存90天
Inventory Turnover = 12 → 一年賣12輪，每批存30天
Inventory Turnover = 52 → 每週賣一輪 (生鮮超市)
```

**行業差異**:

| 行業 | 典型存貨周轉 | 說明 |
|------|------------|------|
| 超市生鮮 | 30-50 | 每週多次周轉 |
| 服飾 | 3-6 | 季節性換季 |
| 汽車 | 6-10 | 45-60天庫存 |
| 珠寶 | 1-2 | 高價低頻 |
| 藥品 | 2-4 | 庫存管理重要 |

**AAPL 實例**:
```
標準方法: COGS / Avg Inventory = 33.98
FD 方法:  Revenue / End Inventory = 72.78

解讀:
- AAPL 的存貨周轉非常快
- 這是 JIT (Just-In-Time) 供應鏈管理的結果
- 庫存壓力低，現金流好
```

---

### 5.3 Receivables Turnover (應收帳款周轉率)

```
公式: Revenue / Average Accounts Receivable

白話: 一年收幾輪錢
```

**直覺建立**:
```
Receivables Turnover = 12 → 平均30天收回帳款
Receivables Turnover = 6  → 平均60天收回帳款
Receivables Turnover = 4  → 平均90天收回帳款
```

**行業差異**:

| 行業 | 典型周轉率 | 收款天數 |
|------|----------|---------|
| 零售 (現金) | 50+ | 7天內 |
| 消費品 | 8-12 | 30-45天 |
| 製造B2B | 4-8 | 45-90天 |
| 建築 | 3-5 | 75-120天 |

**AAPL 實例**:
```
標準 (Trade AR): 11.37 → 32天收款
含 Non-trade AR: 6.28 → 58天收款

解讀:
- Trade AR 周轉快是因為消費者付款快
- Non-trade AR 主要是供應商返點等，周期較長
```

---

### 5.4 Days Sales Outstanding (DSO, 應收帳款天數)

```
公式: 365 / Receivables Turnover
或:   Accounts Receivable / (Revenue / 365)

白話: 平均多少天能收回帳款
```

**直覺建立**:
- DSO 越短越好 = 現金回收快
- DSO 變長可能意味著客戶付款困難

**AAPL 實例**:
```
我們計算: 32.09 天 (標準方法)
FD 值:    0.14 天 (異常!)

解讀: FD 的值明顯有誤，0.14天不可能
     正常 DSO 約 30-35 天
```

---

### 5.5 Operating Cycle (營運週期)

```
公式: Days Inventory Outstanding + Days Sales Outstanding
    = (365/Inventory Turnover) + (365/Receivables Turnover)

白話: 從買進存貨到收回現金，需要多少天
```

**直覺建立**:
```
Operating Cycle = 進貨 → 生產/存放 → 銷售 → 收款

短 Operating Cycle (30-60天): 現金回收快，營運資金需求低
長 Operating Cycle (90-180天): 需要更多營運資金支撐
```

**AAPL 實例**:
```
Days Inventory: 365/33.98 = 10.74 天
Days Receivables: 365/11.37 = 32.09 天
Operating Cycle: 42.84 天

解讀: 不到 45 天就能完成一個營運週期
     這是非常高效的供應鏈管理
```

---

### 5.6 Working Capital Turnover (營運資金周轉率)

```
公式: Revenue / Working Capital
     Working Capital = Current Assets - Current Liabilities

白話: 每 $1 營運資金能產生多少營收
```

**特殊情況 - 負營運資金**:
```
AAPL Working Capital = $147.96B - $165.63B = -$17.67B (負的!)

這代表:
- 流動負債 > 流動資產
- 公司實際上在用供應商的錢做生意
- 對於強勢公司這是好事（不需要自己的錢）
- 對於弱勢公司可能是危機信號
```

**AAPL 實例**:
```
Working Capital Turnover: -23.55 (因為 WC 是負的)

解讀:
- 負 WC 是 AAPL 的競爭優勢
- 供應商願意給長賬期
- 消費者立即付款
- 等於免費借用供應鏈的錢
```

---

### Efficiency 指標總結

```
┌────────────────────────────────────────────────────────────┐
│                    AAPL 營運效率全景                        │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Cash Conversion Cycle (現金轉換週期):                      │
│                                                            │
│  [採購] ──→ [存貨] ──→ [銷售] ──→ [收款]                    │
│          10.7天    +    32.1天    =    42.8天              │
│    (Days Inventory)  (Days Receivables)  (Operating Cycle) │
│                                                            │
│  但是! AAPL 還有應付帳款:                                   │
│  Days Payable Outstanding (DPO) ≈ 70-80 天                  │
│                                                            │
│  Cash Conversion Cycle = DIO + DSO - DPO                   │
│                       = 10.7 + 32.1 - 75 ≈ -32 天!         │
│                                                            │
│  負的 CCC 意味著: AAPL 在付錢給供應商之前就已經收到客戶的錢！   │
│  這是極強的現金流管理能力                                    │
└────────────────────────────────────────────────────────────┘
```

---

## 6. Valuation Metrics - 估值指標

> **核心問題**: 這個股價值不值得買？貴了還是便宜？

### 6.1 Market Cap (市值)

```
公式: Stock Price × Shares Outstanding

白話: 買下整間公司需要多少錢
```

**市值分類**:

| 類別 | 市值範圍 | 特點 |
|------|---------|------|
| Mega Cap | >$200B | AAPL, MSFT, 流動性最好 |
| Large Cap | $10-200B | 多數藍籌股 |
| Mid Cap | $2-10B | 成長空間較大 |
| Small Cap | $300M-2B | 波動較大 |
| Micro Cap | <$300M | 流動性風險 |

**AAPL 實例**:
```
Market Cap: ~$3.83T
= 全球市值最大的公司之一
= 超過許多國家的 GDP
```

---

### 6.2 Enterprise Value (EV, 企業價值)

```
公式: Market Cap + Total Debt - Cash

白話: 收購整間公司實際需要多少錢
      (買下股權 + 承擔債務 - 拿到的現金)
```

**為什麼 EV 比 Market Cap 更重要？**
```
比較兩間公司:

公司 A: Market Cap $100B, Debt $50B, Cash $10B
公司 B: Market Cap $100B, Debt $0B,  Cash $40B

同樣市值，但:
- 收購 A 要: $100B + $50B - $10B = $140B
- 收購 B 要: $100B + $0B - $40B = $60B

EV 才能真正比較公司價值
```

**AAPL 實例**:
```
EV = $3,832B + $98.7B - $35.9B = $3,895B
解讀: EV 比 Market Cap 高 $62.7B
     說明 AAPL 有淨負債 (Debt > Cash)
```

---

### 6.3 Price to Earnings Ratio (P/E, 本益比)

```
公式: Market Cap / Net Income
或:   Stock Price / Earnings Per Share

白話: 付多少倍的盈利來買這間公司
```

**直覺建立**:
```
P/E = 10 → 如果盈利不變，10年回本
P/E = 20 → 20年回本
P/E = 50 → 市場預期高成長來支撐
```

**P/E 的解讀框架**:

| P/E 範圍 | 可能含義 |
|---------|---------|
| P/E < 10 | 可能被低估，或市場預期衰退 |
| P/E 10-15 | 相對便宜，成熟公司 |
| P/E 15-25 | 合理區間，穩定成長 |
| P/E 25-40 | 市場預期較高成長 |
| P/E > 40 | 高成長預期，或泡沫 |
| P/E 負值 | 公司虧損，用 P/S 替代 |

**行業參考**:

| 行業 | 典型 P/E | 說明 |
|------|---------|------|
| 科技成長 | 30-50 | NVDA, CRM |
| 科技成熟 | 20-30 | AAPL, MSFT |
| 金融 | 10-15 | 穩定但低成長 |
| 公用事業 | 15-20 | 穩定股息 |
| 消費必需 | 20-25 | 抗跌性 |

**AAPL 實例**:
```
P/E = 34.22
解讀:
- 高於科技成熟公司平均
- 市場預期 AAPL 仍有成長 (服務收入、AI)
- 或者反映「品質溢價」
```

---

### 6.4 Price to Book Ratio (P/B, 股價淨值比)

```
公式: Market Cap / Shareholders' Equity
或:   Stock Price / Book Value Per Share

白話: 股價是帳面淨資產的多少倍
```

**直覺建立**:
```
P/B = 1.0 → 股價 = 帳面價值，破產清算約能拿回成本
P/B = 2.0 → 市場認為公司價值是帳面的兩倍
P/B = 10+ → 主要價值在無形資產（品牌、技術、商譽）
```

**行業差異**:

| 行業 | 典型 P/B | 說明 |
|------|---------|------|
| 銀行 | 1.0-1.5 | 資產接近公允價值 |
| 製造 | 1.5-3.0 | 重資產 |
| 消費 | 3-6 | 品牌價值 |
| 科技 | 5-15+ | 無形資產重要 |
| 軟體 | 10-30 | 幾乎全是無形資產 |

**AAPL 實例**:
```
P/B = 51.98
解讀:
- P/B 極高，因為 AAPL 的真正價值不在帳面資產
- 品牌價值、生態系統、客戶忠誠度都是無形資產
- 大量回購導致 Equity 很低，進一步推高 P/B
```

---

### 6.5 Price to Sales Ratio (P/S, 股價營收比)

```
公式: Market Cap / Revenue
或:   Stock Price / Revenue Per Share

白話: 每 $1 營收，市場願意付多少
```

**P/S 的適用情境**:
- 公司虧損時 P/E 無法使用
- 不同會計方法導致淨利波動大
- 比較不同獲利階段的公司

**直覺建立**:
```
P/S = 1   → $1 營收對應 $1 市值 (低估或低毛利)
P/S = 5   → 市場預期這營收能轉化為可觀利潤
P/S = 10+ → 高成長預期 (常見於 SaaS)
```

**AAPL 實例**:
```
P/S = 9.21
解讀:
- 每 $1 營收對應 $9.21 市值
- 這反映 AAPL 的高淨利率 (26.9%)
- P/S × Net Margin ≈ P/E
- 9.21 × 0.269 ≈ 2.48... (等等，這不對)
- 9.21 / 0.269 ≈ 34.2 (這才對！和 P/E 吻合)
```

---

### 6.6 EV/EBITDA (企業價值/EBITDA)

```
公式: Enterprise Value / EBITDA
      EBITDA = Operating Income + Depreciation & Amortization

白話: 用多少倍的現金獲利能力買下整間公司
```

**為什麼用 EBITDA？**
- 排除折舊攤銷（非現金支出）
- 排除利息（資本結構影響）
- 排除稅（不同稅務環境）
- 更能反映核心業務的現金產生能力

**直覺建立**:
```
EV/EBITDA < 8   → 相對便宜
EV/EBITDA 8-12  → 合理區間
EV/EBITDA 12-20 → 偏貴或高成長
EV/EBITDA > 20  → 市場給予高溢價
```

**AAPL 實例**:
```
EV/EBITDA = 26.91
EBITDA = $133.05B + $11.70B = $144.75B

解讀:
- 略高於 20，反映市場對 AAPL 的溢價
- 約 27 年的 EBITDA 才能買下整間公司
```

---

### 6.7 EV/Revenue (企業價值/營收比)

```
公式: Enterprise Value / Revenue

白話: 類似 P/S，但用 EV 而非 Market Cap
```

**EV/Revenue vs P/S**:
- 對於高負債公司，EV/Revenue > P/S
- 對於淨現金公司，EV/Revenue < P/S
- EV/Revenue 更適合跨公司比較

**AAPL 實例**:
```
EV/Revenue = 9.36
P/S = 9.21
差異來自 AAPL 的淨負債
```

---

### 6.8 Free Cash Flow Yield (自由現金流收益率)

```
公式: Free Cash Flow / Market Cap

白話: 每 $1 市值，公司產生多少自由現金流
```

**直覺建立**:
- 類似股息率，但看的是公司能分配的最大現金
- FCF Yield 高 = 股價相對便宜，或現金流強

**與債券比較**:
```
如果 10 年期國債殖利率 = 4.5%
FCF Yield = 3% → 股票可能偏貴
FCF Yield = 6% → 股票可能有吸引力
```

**AAPL 實例**:
```
FCF Yield = 2.58%
FCF = $98.77B
Market Cap = $3,832B

解讀:
- 每 $100 投資 AAPL，公司一年產生 $2.58 自由現金流
- 低於當前國債殖利率
- 但 AAPL 還有成長性，國債沒有
```

---

### 6.9 PEG Ratio (本益成長比)

```
公式: P/E Ratio / Earnings Growth Rate (%)

白話: 每 1% 的成長率，市場給多少倍 P/E
```

**直覺建立**:
```
PEG = 1.0 → P/E 與成長率匹配，"合理"估值
PEG < 1.0 → 可能被低估（成長率高於 P/E）
PEG 1-2   → 合理區間
PEG > 2.0 → 可能偏貴
```

**注意事項**:
- 成長率用哪個？過去？預期？
- 不同的成長率來源會導致 PEG 差異很大

**AAPL 實例**:
```
我們的 PEG = 34.22 / 19.50 = 1.75
FD 的 PEG = 2.55 (用不同成長率)

解讀:
- PEG < 2 表示估值還算合理
- 市場願意為 AAPL 的品質付溢價
```

---

### Valuation 指標總結

```
┌────────────────────────────────────────────────────────────┐
│                    AAPL 估值全景                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  絕對值:                                                    │
│    Market Cap:  $3.83T (全球第一)                          │
│    Enterprise Value: $3.90T                                │
│                                                            │
│  相對估值:                                                  │
│    P/E = 34.2   (科技成熟偏高)                             │
│    P/B = 52.0   (品牌溢價+低權益)                          │
│    P/S = 9.2    (高淨利率支撐)                             │
│    EV/EBITDA = 26.9  (略高於行業)                          │
│                                                            │
│  現金流視角:                                                │
│    FCF Yield = 2.6%  (低於國債)                            │
│    但 AAPL 有成長性 + 品質溢價                              │
│                                                            │
│  成長調整:                                                  │
│    PEG = 1.75   (考慮成長後較合理)                         │
│                                                            │
│  結論: AAPL 估值不便宜，但品質支撐溢價                       │
└────────────────────────────────────────────────────────────┘
```

---

## 7. Growth Metrics - 成長性指標

> **核心問題**: 公司是在成長還是衰退？成長速度如何？

### 7.1 Revenue Growth (營收成長率)

```
公式: (Revenue_t - Revenue_t-1) / Revenue_t-1

白話: 營收比去年增加多少百分比
```

**直覺建立**:
```
Revenue Growth < 0%   → 營收衰退，嚴重警訊
Revenue Growth 0-5%   → 低成長，可能是成熟期
Revenue Growth 5-15%  → 穩健成長
Revenue Growth 15-30% → 高成長
Revenue Growth > 30%  → 爆發性成長（難以持續）
```

**AAPL 實例**:
```
FY2025 vs FY2024: 6.43%

解讀:
- 對於 $4000億+ 營收的公司，6.4% 成長已不容易
- 這是 ~$250億 的增量營收
- 市場預期 AI 和服務業務能加速成長
```

---

### 7.2 Earnings Growth (淨利成長率)

```
公式: (Net Income_t - Net Income_t-1) / Net Income_t-1

白話: 淨利比去年增加多少百分比
```

**與營收成長的關係**:
```
情境 1: 營收成長 > 淨利成長
  → 成本上升或毛利下降，獲利能力減弱

情境 2: 營收成長 < 淨利成長
  → 營運槓桿發揮作用，規模效應顯現

情境 3: 營收成長 = 淨利成長
  → 獲利結構穩定
```

**AAPL 實例**:
```
Revenue Growth: 6.43%
Earnings Growth: 19.50%

解讀:
- 淨利成長 >> 營收成長
- 說明 AAPL 的營運效率在改善
- 可能來自服務收入佔比提升（毛利更高）
```

---

### 7.3 Book Value Growth (帳面價值成長率)

```
公式: (Equity_t - Equity_t-1) / Equity_t-1

白話: 股東權益增加了多少
```

**影響因素**:
```
Equity 變化 = Net Income (淨利增加)
            - Dividends (股息減少)
            - Buybacks (回購減少)
            + Stock Issuance (發股增加)
```

**AAPL 實例**:
```
Book Value Growth: 29.47%

解讀:
- 看起來很高，但要考慮基數效應
- AAPL Equity 因大量回購而很低
- 所以百分比變化被放大
```

---

### 7.4 EPS Growth (每股盈餘成長率)

```
公式: (EPS_t - EPS_t-1) / EPS_t-1

白話: 每股賺的錢成長多少
```

**為什麼 EPS Growth 可能 ≠ Earnings Growth？**
```
EPS = Net Income / Shares Outstanding

如果公司回購股票:
- Net Income 不變
- Shares 減少
- EPS 增加！

這就是為什麼 EPS Growth 常常 > Earnings Growth
```

**AAPL 實例**:
```
Earnings Growth: 19.50%
EPS Growth: 22.59%

解讀:
- EPS 成長比淨利成長高 3%
- 差異來自股票回購減少了股數
- AAPL 每年回購 ~$800億股票
```

---

### 7.5 Free Cash Flow Growth (自由現金流成長率)

```
公式: (FCF_t - FCF_t-1) / FCF_t-1

白話: 自由現金流成長多少
```

**FCF 的重要性**:
- 比淨利更難造假
- 代表公司真正能自由支配的現金
- 可用於回購、股息、併購、還債

**AAPL 實例**:
```
FCF Growth: -9.23%

解讀:
- FCF 下降不一定是壞事
- 可能是增加資本支出（投資未來）
- 需要看具體原因
```

---

### 7.6 Operating Income Growth (營業利益成長率)

```
公式: (Operating Income_t - Operating Income_t-1) / Operating Income_t-1

白話: 核心業務獲利成長多少
```

**與淨利成長的差異**:
- Operating Income 不含利息和稅
- 更能反映核心業務的表現
- 不受財務結構和稅務策略影響

**AAPL 實例**:
```
Operating Income Growth: 7.98%

解讀:
- 略高於營收成長 (6.43%)
- 說明營運效率改善
```

---

### 7.7 EBITDA Growth (EBITDA 成長率)

```
公式: (EBITDA_t - EBITDA_t-1) / EBITDA_t-1

白話: 現金獲利能力成長多少
```

**EBITDA vs Operating Income**:
```
EBITDA = Operating Income + Depreciation & Amortization

- 對於資本密集型公司，D&A 很大
- EBITDA 更接近營運現金流
- 常用於跨公司比較（排除折舊政策差異）
```

**AAPL 實例**:
```
EBITDA Growth: 7.49%

解讀:
- 與 Operating Income Growth (7.98%) 接近
- 因為 AAPL 的 D&A 相對穩定
```

---

### Growth 指標總結

```
┌────────────────────────────────────────────────────────────┐
│                    AAPL 成長全景                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  營收端:                                                    │
│    Revenue Growth: 6.43%                                   │
│    (大象也能跳舞，但速度會慢)                                │
│                                                            │
│  獲利端:                                                    │
│    Operating Income Growth: 7.98%  (效率改善)              │
│    Earnings Growth: 19.50%  (大幅超越營收成長)              │
│    EPS Growth: 22.59%  (回購加成)                          │
│                                                            │
│  現金端:                                                    │
│    FCF Growth: -9.23%  (短期下降，需關注原因)               │
│    EBITDA Growth: 7.49%  (穩健)                            │
│                                                            │
│  資產端:                                                    │
│    Book Value Growth: 29.47%  (基數低，波動大)              │
│                                                            │
│  結論:                                                      │
│    - 營收低速成長是體量原因                                  │
│    - 獲利成長優於營收，說明營運效率提升                       │
│    - EPS 成長最亮眼，回購策略有效                            │
└────────────────────────────────────────────────────────────┘
```

---

## 8. Per-Share Metrics - 每股指標

> **核心問題**: 每股值多少？與股價如何比較？

### 8.1 Earnings Per Share (EPS, 每股盈餘)

```
公式: Net Income / Weighted Average Shares Outstanding

白話: 每持有一股，分到多少淨利
```

**EPS 的重要性**:
- 最常用的獲利指標
- P/E = Price / EPS
- 分析師最關注的指標之一

**Basic vs Diluted EPS**:
```
Basic EPS: 用實際流通股數
Diluted EPS: 假設所有選擇權、可轉債都轉換成股票

Diluted EPS < Basic EPS (股數更多，分母更大)
差距大 → 有大量潛在稀釋
```

**AAPL 實例**:
```
EPS (Basic): $7.55
EPS (Diluted): $7.49

解讀:
- 差異很小，稀釋效果有限
- 因為 AAPL 大量回購，抵消了員工股票激勵的稀釋
```

---

### 8.2 Book Value Per Share (BVPS, 每股淨值)

```
公式: Shareholders' Equity / Shares Outstanding

白話: 如果公司清算，每股大約能分到多少
```

**直覺建立**:
```
如果 BVPS = $50，Stock Price = $100
→ P/B = 2.0
→ 市場認為公司價值是帳面的兩倍

如果 Stock Price < BVPS
→ P/B < 1
→ 可能被低估，或市場擔心資產減值
```

**AAPL 實例**:
```
BVPS: $4.99
Stock Price: ~$260

解讀:
- P/B = 260/4.99 = 52
- 帳面價值幾乎無參考意義
- AAPL 的真正價值在品牌、生態、客戶忠誠
```

---

### 8.3 Free Cash Flow Per Share (每股自由現金流)

```
公式: Free Cash Flow / Shares Outstanding

白話: 每股產生多少自由現金流
```

**與 EPS 的比較**:
```
FCF per Share > EPS → 盈餘品質高（現金收入多）
FCF per Share < EPS → 可能有應計項目，需關注

長期: FCF per Share ≈ EPS (累計應趨近)
```

**AAPL 實例**:
```
FCF per Share: $6.69
EPS: $7.49

解讀:
- FCF per Share 略低於 EPS
- 差異主要來自營運資金變化和資本支出
- 比例健康
```

---

### 8.4 Payout Ratio (股利支付率)

```
公式: Dividends / Net Income
或:   DPS / EPS

白話: 賺的錢有多少比例發給股東
```

**直覺建立**:
```
Payout Ratio < 30%  → 保留大部分盈餘再投資
Payout Ratio 30-50% → 平衡型
Payout Ratio 50-70% → 偏向回饋股東
Payout Ratio > 80%  → 高股息，但成長空間有限
Payout Ratio > 100% → 發超過賺的，可能不可持續
```

**AAPL 實例**:
```
Payout Ratio: 13.77%
Dividends: $15.42B
Net Income: $112.01B

解讀:
- 股息只佔盈餘 14%
- 但 AAPL 每年回購 ~$800億
- 實際回饋股東 = 股息 + 回購 = ~$950億
- 總回饋率 = 950/1120 = 85%
```

---

### Per-Share 指標總結

```
┌────────────────────────────────────────────────────────────┐
│                    AAPL Per-Share 全景                     │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  每股指標          │    值     │ 與股價($260)比較          │
│  ─────────────────│──────────│─────────────────          │
│  EPS              │   $7.49   │ P/E = 34.7x              │
│  Book Value/Share │   $4.99   │ P/B = 52.1x              │
│  FCF/Share        │   $6.69   │ P/FCF = 38.9x            │
│                                                            │
│  股東回報:                                                  │
│    Dividend/Share: ~$1.00/year (Yield ~0.4%)               │
│    Payout Ratio: 13.77%                                   │
│    + Buyback: ~$800B/year → 每股回購效益 ~5%               │
│    Total Shareholder Yield: ~5.4%                         │
│                                                            │
│  結論: 低股息但高回購，總回報可觀                            │
└────────────────────────────────────────────────────────────┘
```

---

## 9. 指標間的關聯性

### 9.1 DuPont 分析 (ROE 拆解)

```
ROE = Net Margin × Asset Turnover × Equity Multiplier

AAPL 實例:
ROE = 26.9% × 1.16 × 4.87 = 152%
       │        │        │
       │        │        └── Equity Multiplier (Assets/Equity)
       │        │            = 359.24/73.73 = 4.87
       │        │            (高槓桿)
       │        │
       │        └── Asset Turnover
       │            = Revenue/Assets = 416.16/359.24 = 1.16
       │            (高效率)
       │
       └── Net Margin = 26.9%
           (高獲利)

三項都強 → ROE 極高
但要注意 Equity Multiplier 高是因為回購，不是負債過高
```

---

### 9.2 估值與獲利的關係

```
P/E = P/S × 1/Net Margin

例如:
AAPL P/S = 9.21
AAPL Net Margin = 26.9%
推導 P/E = 9.21 / 0.269 = 34.2 ✓

這說明:
- 高淨利率 → 可以支撐較高的 P/S
- 如果 P/S 高但 Net Margin 低 → P/E 會非常高（可能是泡沫）
```

---

### 9.3 成長與估值的平衡 (PEG)

```
PEG = P/E / Growth Rate

投資邏輯:
- 高成長可以支撐高 P/E
- 但成長必須可持續
- PEG 幫助判斷 P/E 是否合理

AAPL:
P/E = 34.2
Earnings Growth = 19.5%
PEG = 34.2/19.5 = 1.75

解讀: 略貴，但在可接受範圍
```

---

### 9.4 現金流與盈餘品質

```
FCF vs Net Income 比較:

AAPL:
Net Income = $112.01B
FCF = $98.77B
Ratio = 0.88

解讀:
- FCF/NI < 1 表示有部分盈餘「卡」在營運資金或資本支出
- 但 0.88 是健康的比例
- 如果 FCF/NI 長期 < 0.5，要警惕盈餘品質
```

---

## 10. Trading Signals 應用

### 10.1 價值陷阱 vs 價值投資

```
情境: P/E 很低是好是壞？

價值投資機會 (低 P/E + 好指標):
✅ ROE > 15%
✅ Debt/Equity < 0.5
✅ Free Cash Flow > 0
✅ Revenue 穩定或成長

價值陷阱 (低 P/E + 壞指標):
⚠️ ROE 下降趨勢
⚠️ Debt/Equity 上升
⚠️ Free Cash Flow 負數
⚠️ Revenue 衰退
```

---

### 10.2 成長股估值

```
高成長公司可能 P/E 很高，如何判斷？

用 PEG 調整:
PEG < 1.5 → 成長率能支撐估值
PEG 1.5-2.0 → 合理但需謹慎
PEG > 2.0 → 可能過度樂觀

用 Rule of 40 (SaaS):
Revenue Growth + Profit Margin >= 40% → 健康
例如: 30% 成長 + 10% 利潤率 = 40% (及格)
```

---

### 10.3 財報發布交易信號

```
關注的指標變化:

營收:
- Beat/Miss 預期 → 直接影響股價
- 同比成長趨勢 → 更重要的方向性信號

毛利率:
- 上升 → 定價能力增強，正面
- 下降 → 成本壓力或競爭加劇，負面

Guidance (未來展望):
- 往往比實際業績更影響股價
- 管理層預期 > 市場預期 → 利多
```

---

### 10.4 建立監控指標清單

```
核心指標 (每季追蹤):
1. Revenue Growth (營收成長)
2. Gross Margin (毛利率)
3. Operating Margin (營業利益率)
4. EPS vs Estimates (EPS vs 預期)
5. Free Cash Flow (自由現金流)

次要指標 (每年檢視):
6. ROE / ROIC
7. Debt/Equity
8. Valuation (P/E, P/S, EV/EBITDA)
9. Working Capital trends
```

---

## 附錄: 快速參考卡

### Profitability
| 指標 | 公式 | 好的範圍 |
|------|------|---------|
| Gross Margin | GP/Revenue | 行業相關，越高越好 |
| Operating Margin | OI/Revenue | >15% 良好 |
| Net Margin | NI/Revenue | >10% 良好 |
| ROE | NI/Equity | >15% 良好 |
| ROA | NI/Assets | >5% 良好 |
| ROIC | NOPAT/IC | >WACC |

### Liquidity
| 指標 | 公式 | 好的範圍 |
|------|------|---------|
| Current Ratio | CA/CL | >1.5 |
| Quick Ratio | (CA-Inv)/CL | >1.0 |
| Cash Ratio | Cash/CL | >0.2 |

### Leverage
| 指標 | 公式 | 好的範圍 |
|------|------|---------|
| D/E | Debt/Equity | <1.0 (非金融) |
| D/A | Debt/Assets | <50% |
| Interest Coverage | EBIT/Interest | >5x |

### Valuation
| 指標 | 公式 | 解讀 |
|------|------|------|
| P/E | Price/EPS | 15-25 合理 |
| P/B | Price/BVPS | 1-3 合理 (行業差異大) |
| P/S | MC/Revenue | <3 便宜 |
| EV/EBITDA | EV/EBITDA | 8-12 合理 |
| PEG | PE/Growth | <1.5 合理 |

---

*最後更新: 2026-01-17*
*文件: docs/analysis/FINANCIAL_METRICS_TRADING_GUIDE.md*