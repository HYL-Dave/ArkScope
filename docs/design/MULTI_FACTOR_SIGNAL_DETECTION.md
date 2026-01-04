# 多因子信號檢測系統設計

> **目標**: 從多個獨立信號組合中檢測潛在的板塊/個股爆發機會
> **動機**: 單篇新聞情緒不足以捕捉複雜市場動態，需要事件鏈+板塊聚合+異常檢測
> **版本**: 1.0 (2026-01-04)

---

## 1. 問題定義

### 1.1 當前系統局限

| 局限 | 說明 | 太空股案例中的表現 |
|------|------|-------------------|
| **單篇獨立評分** | 每篇新聞獨立評分，無上下文 | 無法連結 12/18 政策 → 12/23 發射 |
| **無板塊視角** | 只看個股，無板塊聚合 | ASTS 情緒高不知道是板塊行情 |
| **無事件類型** | 不區分政策/技術/資金新聞 | 所有新聞同等權重 |
| **無時間關聯** | 不追蹤事件序列 | 無法識別「催化劑疊加」 |

### 1.2 目標能力

```
輸入: 過去 N 天的新聞 + 價格 + (可選) 期權數據
輸出: {
    "signal_type": "SECTOR_BREAKOUT",
    "sector": "SPACE",
    "confidence": 0.75,
    "factors": [
        {"type": "POLICY", "date": "2025-12-18", "impact": 0.3},
        {"type": "TECH_MILESTONE", "date": "2025-12-23", "impact": 0.5},
        {"type": "VALUATION_ANCHOR", "date": "2025-12", "impact": 0.2}
    ],
    "recommended_action": "BUY_SECTOR",
    "risk_level": 3
}
```

---

## 2. 系統架構

### 2.1 分層設計

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Layer 4: 信號合成器                               │
│     Synthesizer: 多因子加權 → 最終交易信號                               │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│ Layer 3: 事件鏈   │   │ Layer 3: 板塊聚合 │   │ Layer 3: 異常檢測 │
│ EventChain        │   │ SectorAggregator  │   │ AnomalyDetector   │
│                   │   │                   │   │                   │
│ 連結時間相關事件   │   │ 計算板塊情緒/動量  │   │ 檢測統計異常      │
└─────────┬─────────┘   └─────────┬─────────┘   └─────────┬─────────┘
          │                       │                       │
          └───────────────────────┼───────────────────────┘
                                  │
┌─────────────────────────────────┴─────────────────────────────────────┐
│                        Layer 2: 特徵增強                               │
│     • 事件類型標籤 (EventTagger)                                       │
│     • 情緒衍生特徵 (SentimentFeatures)                                 │
│     • 時間衰減權重 (TimeDecay)                                         │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
┌───────────────────────────────────┴─────────────────────────────────────┐
│                        Layer 1: 基礎評分                               │
│     • LLM 情緒/風險評分 (現有)                                          │
│     • 價格數據 (現有)                                                   │
│     • (可選) 期權數據                                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 數據流

```
新聞 ─────────────────────────────────────────────────────────────────────►
      │
      ▼
┌──────────────────┐
│ LLM 評分 + 標籤   │  sentiment, risk, event_type, keywords
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 特徵計算          │  sentiment_7d_ma, momentum, sector_sentiment
└────────┬─────────┘
         │
    ┌────┴────┬────────────┐
    │         │            │
    ▼         ▼            ▼
┌───────┐ ┌───────┐ ┌──────────┐
│事件鏈 │ │板塊   │ │異常      │
│檢測   │ │聚合   │ │檢測      │
└───┬───┘ └───┬───┘ └────┬─────┘
    │         │          │
    └─────────┼──────────┘
              │
              ▼
┌──────────────────┐
│ 信號合成          │  交易信號 + 置信度 + 風險
└──────────────────┘
```

---

## 3. 核心模組設計

### 3.1 事件類型標籤器 (EventTagger)

**目的**: 為每篇新聞添加結構化事件類型標籤

```python
class EventTagger:
    """事件類型標籤器"""

    EVENT_TYPES = {
        'POLICY_POSITIVE': ['executive order', 'legislation', 'subsidy', 'approve'],
        'POLICY_NEGATIVE': ['ban', 'restriction', 'tariff', 'sanction'],
        'EXEC_DEPARTURE': ['resign', 'step down', 'retire', 'leave'],
        'EXEC_HIRE': ['join', 'appoint', 'name', 'hire'],
        'TECH_MILESTONE': ['launch', 'breakthrough', 'patent', 'first ever'],
        'EARNINGS_BEAT': ['beat', 'exceed', 'above estimate'],
        'EARNINGS_MISS': ['miss', 'below', 'disappoint'],
        'FUNDING': ['IPO', 'fundraise', 'acquisition', 'merger'],
        'ANALYST_UPGRADE': ['upgrade', 'raise target', 'overweight'],
        'ANALYST_DOWNGRADE': ['downgrade', 'lower target', 'underweight'],
    }

    def tag(self, title: str, content: str) -> List[str]:
        """識別新聞中的事件類型"""
        text = f"{title} {content}".lower()
        tags = []

        for event_type, keywords in self.EVENT_TYPES.items():
            if any(kw in text for kw in keywords):
                tags.append(event_type)

        return tags if tags else ['GENERAL']
```

**LLM 增強版本** (更準確):

```python
TAGGING_PROMPT = """
分析以下新聞，識別事件類型。

新聞標題: {title}
新聞內容: {content}

從以下類型中選擇 (可多選):
- POLICY_POSITIVE: 政策利好
- POLICY_NEGATIVE: 政策利空
- TECH_MILESTONE: 技術里程碑
- EARNINGS_BEAT: 財報超預期
- EARNINGS_MISS: 財報不及預期
- FUNDING: 融資/IPO/併購
- EXEC_MOVEMENT: 高管變動
- ANALYST_RATING: 分析師評級
- GENERAL: 一般新聞

輸出 JSON: {"event_types": [...], "primary_type": "..."}
"""
```

---

### 3.2 板塊聚合器 (SectorAggregator)

**目的**: 計算板塊級別的情緒和動量

```python
class SectorAggregator:
    """板塊情緒聚合器"""

    SECTORS = {
        'SPACE': ['RKLB', 'ASTS', 'LUNR', 'SPCE', 'ASTR', 'RDW', 'MNTS'],
        'AI_CHIPS': ['NVDA', 'AMD', 'AVGO', 'MRVL', 'INTC', 'QCOM'],
        'EV': ['TSLA', 'RIVN', 'LCID', 'NIO', 'XPEV', 'LI'],
        'BIOTECH': ['MRNA', 'BNTX', 'REGN', 'GILD', 'AMGN'],
        'FINTECH': ['SQ', 'PYPL', 'COIN', 'AFRM', 'UPST'],
        'CLOUD': ['SNOW', 'NET', 'DDOG', 'MDB', 'CRWD'],
        # ... 更多板塊
    }

    def calculate_sector_metrics(self, df: pd.DataFrame, date: str) -> Dict:
        """計算板塊級別指標"""
        results = {}

        for sector, tickers in self.SECTORS.items():
            sector_df = df[(df['ticker'].isin(tickers)) & (df['date'] == date)]

            if len(sector_df) == 0:
                continue

            results[sector] = {
                'sentiment_mean': sector_df['llm_sentiment'].mean(),
                'sentiment_std': sector_df['llm_sentiment'].std(),
                'risk_mean': sector_df['llm_risk'].mean(),
                'article_count': len(sector_df),
                'bullish_ratio': (sector_df['llm_sentiment'] >= 4).mean(),
                'extreme_count': ((sector_df['llm_sentiment'] >= 4.5) |
                                  (sector_df['llm_sentiment'] <= 1.5)).sum(),
            }

        return results

    def detect_sector_momentum(self, df: pd.DataFrame, sector: str,
                               lookback: int = 7) -> Dict:
        """檢測板塊動量變化"""
        tickers = self.SECTORS.get(sector, [])
        sector_df = df[df['ticker'].isin(tickers)].copy()

        # 按日期聚合
        daily = sector_df.groupby('date')['llm_sentiment'].mean()

        if len(daily) < lookback:
            return {'momentum': 0, 'trend': 'INSUFFICIENT_DATA'}

        recent_mean = daily.tail(3).mean()
        prior_mean = daily.tail(lookback).head(lookback - 3).mean()
        momentum = recent_mean - prior_mean

        trend = 'ACCELERATING' if momentum > 0.5 else \
                'DECELERATING' if momentum < -0.5 else 'STABLE'

        return {
            'momentum': momentum,
            'trend': trend,
            'recent_sentiment': recent_mean,
            'prior_sentiment': prior_mean
        }
```

---

### 3.3 事件鏈檢測器 (EventChainDetector)

**目的**: 識別時間上相關的事件序列

```python
class EventChainDetector:
    """事件鏈檢測器"""

    def __init__(self, window_days: int = 14):
        self.window_days = window_days

    def detect_chains(self, events: List[Dict]) -> List[Dict]:
        """檢測事件鏈模式"""
        chains = []

        # 按時間排序
        sorted_events = sorted(events, key=lambda x: x['date'])

        # 尋找相關事件序列
        for i, event in enumerate(sorted_events):
            chain = [event]

            for j in range(i + 1, len(sorted_events)):
                next_event = sorted_events[j]

                # 時間窗口內
                days_diff = (next_event['date'] - event['date']).days
                if days_diff > self.window_days:
                    break

                # 主題相關 (同板塊或同股票)
                if self._is_related(event, next_event):
                    chain.append(next_event)

            if len(chain) >= 2:
                chains.append({
                    'events': chain,
                    'start_date': chain[0]['date'],
                    'end_date': chain[-1]['date'],
                    'impact_score': self._calculate_chain_impact(chain),
                    'pattern': self._identify_pattern(chain)
                })

        return chains

    def _is_related(self, e1: Dict, e2: Dict) -> bool:
        """判斷兩個事件是否相關"""
        # 同股票
        if e1.get('ticker') == e2.get('ticker'):
            return True
        # 同板塊
        if e1.get('sector') == e2.get('sector'):
            return True
        # 供應鏈關係 (需要知識圖譜)
        return False

    def _calculate_chain_impact(self, chain: List[Dict]) -> float:
        """計算事件鏈的累積影響"""
        impact = 0
        for i, event in enumerate(chain):
            # 後續事件有放大效應
            multiplier = 1 + (i * 0.2)
            impact += event.get('sentiment_impact', 0) * multiplier
        return impact

    def _identify_pattern(self, chain: List[Dict]) -> str:
        """識別事件鏈模式"""
        types = [e.get('event_type') for e in chain]

        # 政策 → 技術確認模式
        if 'POLICY_POSITIVE' in types and 'TECH_MILESTONE' in types:
            return 'POLICY_TECH_CONFIRMATION'

        # 分析師 → 財報模式
        if 'ANALYST_UPGRADE' in types and 'EARNINGS_BEAT' in types:
            return 'UPGRADE_EARNINGS_CONFIRMATION'

        return 'GENERAL_CATALYST_CHAIN'
```

---

### 3.4 異常檢測器 (AnomalyDetector)

**目的**: 檢測統計異常值

```python
class AnomalyDetector:
    """統計異常檢測器"""

    def detect_sentiment_anomaly(self, df: pd.DataFrame,
                                 ticker: str, date: str) -> Dict:
        """檢測情緒異常"""
        ticker_df = df[df['ticker'] == ticker].copy()

        if len(ticker_df) < 30:
            return {'is_anomaly': False, 'reason': 'INSUFFICIENT_DATA'}

        # 計算 Z-score
        mean = ticker_df['llm_sentiment'].mean()
        std = ticker_df['llm_sentiment'].std()
        current = ticker_df[ticker_df['date'] == date]['llm_sentiment'].values

        if len(current) == 0:
            return {'is_anomaly': False, 'reason': 'NO_DATA_FOR_DATE'}

        z_score = (current[0] - mean) / std

        return {
            'is_anomaly': abs(z_score) > 2,
            'z_score': z_score,
            'direction': 'POSITIVE' if z_score > 0 else 'NEGATIVE',
            'percentile': (ticker_df['llm_sentiment'] <= current[0]).mean()
        }

    def detect_volume_anomaly(self, df: pd.DataFrame,
                              ticker: str, date: str) -> Dict:
        """檢測新聞數量異常"""
        # 按日計算新聞數量
        daily_counts = df[df['ticker'] == ticker].groupby('date').size()

        if len(daily_counts) < 14:
            return {'is_anomaly': False, 'reason': 'INSUFFICIENT_DATA'}

        mean = daily_counts.rolling(14).mean()
        std = daily_counts.rolling(14).std()

        if date not in daily_counts.index:
            return {'is_anomaly': False, 'reason': 'NO_DATA_FOR_DATE'}

        current = daily_counts[date]
        z_score = (current - mean[date]) / std[date]

        return {
            'is_anomaly': z_score > 2,  # 只關注數量增加
            'z_score': z_score,
            'current_count': current,
            'historical_mean': mean[date]
        }
```

---

### 3.5 信號合成器 (SignalSynthesizer)

**目的**: 整合多個信號產生最終交易建議

```python
class SignalSynthesizer:
    """多因子信號合成器"""

    def __init__(self):
        self.weights = {
            'sector_momentum': 0.25,
            'event_chain': 0.30,
            'sentiment_anomaly': 0.20,
            'volume_anomaly': 0.15,
            'extreme_sentiment': 0.10
        }

    def synthesize(self, signals: Dict) -> Dict:
        """合成最終信號"""
        score = 0
        factors = []

        # 板塊動量
        if signals.get('sector_momentum', {}).get('trend') == 'ACCELERATING':
            score += self.weights['sector_momentum']
            factors.append({
                'type': 'SECTOR_MOMENTUM',
                'impact': self.weights['sector_momentum'],
                'detail': signals['sector_momentum']
            })

        # 事件鏈
        chains = signals.get('event_chains', [])
        if chains:
            best_chain = max(chains, key=lambda x: x['impact_score'])
            chain_impact = min(best_chain['impact_score'] / 2, 1) * self.weights['event_chain']
            score += chain_impact
            factors.append({
                'type': 'EVENT_CHAIN',
                'impact': chain_impact,
                'pattern': best_chain['pattern'],
                'events': len(best_chain['events'])
            })

        # 情緒異常
        if signals.get('sentiment_anomaly', {}).get('is_anomaly'):
            anomaly = signals['sentiment_anomaly']
            if anomaly['direction'] == 'POSITIVE':
                score += self.weights['sentiment_anomaly']
                factors.append({
                    'type': 'SENTIMENT_ANOMALY',
                    'impact': self.weights['sentiment_anomaly'],
                    'z_score': anomaly['z_score']
                })

        # 新聞量異常
        if signals.get('volume_anomaly', {}).get('is_anomaly'):
            score += self.weights['volume_anomaly']
            factors.append({
                'type': 'VOLUME_SPIKE',
                'impact': self.weights['volume_anomaly']
            })

        # 決策
        if score >= 0.6:
            action = 'STRONG_BUY'
            confidence = min(score, 1.0)
        elif score >= 0.4:
            action = 'BUY'
            confidence = score
        elif score <= -0.4:
            action = 'SELL'
            confidence = abs(score)
        else:
            action = 'HOLD'
            confidence = 0.5

        return {
            'action': action,
            'confidence': confidence,
            'composite_score': score,
            'factors': factors,
            'risk_level': self._assess_risk(signals)
        }

    def _assess_risk(self, signals: Dict) -> int:
        """評估風險等級 (1-5)"""
        risk = 3  # 基礎風險

        # 極端情緒增加風險
        if signals.get('extreme_sentiment'):
            risk += 1

        # 高波動增加風險
        if signals.get('sentiment_volatility', 0) > 1:
            risk += 1

        return min(risk, 5)
```

---

## 4. 與現有系統整合

### 4.1 整合點

| 現有組件 | 整合方式 |
|----------|----------|
| `score_sentiment_*.py` | 添加 `event_type` 輸出欄位 |
| `prepare_dataset_openai.py` | 添加衍生特徵計算 |
| `env_stocktrading_llm.py` | 擴展狀態空間納入板塊特徵 |
| `train_ppo_llm.py` | 保持不變 (特徵層處理) |

### 4.2 新增組件

```
src/
├── signals/
│   ├── __init__.py
│   ├── event_tagger.py        # 事件類型標籤
│   ├── sector_aggregator.py   # 板塊聚合
│   ├── event_chain.py         # 事件鏈檢測
│   ├── anomaly_detector.py    # 異常檢測
│   └── synthesizer.py         # 信號合成
├── config/
│   ├── sectors.yaml           # 板塊定義
│   └── event_types.yaml       # 事件類型定義
```

### 4.3 使用流程

```python
# 完整流程示例
from signals import (
    EventTagger, SectorAggregator,
    EventChainDetector, AnomalyDetector, SignalSynthesizer
)

# 1. 載入數據
df = pd.read_csv('polygon_scored.csv')

# 2. 事件標籤
tagger = EventTagger()
df['event_types'] = df.apply(
    lambda r: tagger.tag(r['title'], r['content']), axis=1
)

# 3. 板塊聚合
aggregator = SectorAggregator()
sector_metrics = aggregator.calculate_sector_metrics(df, '2026-01-02')

# 4. 事件鏈檢測
chain_detector = EventChainDetector()
chains = chain_detector.detect_chains(events)

# 5. 異常檢測
anomaly_detector = AnomalyDetector()
sentiment_anomaly = anomaly_detector.detect_sentiment_anomaly(df, 'ASTS', '2026-01-02')

# 6. 信號合成
synthesizer = SignalSynthesizer()
signal = synthesizer.synthesize({
    'sector_momentum': sector_metrics.get('SPACE'),
    'event_chains': chains,
    'sentiment_anomaly': sentiment_anomaly,
    # ...
})

print(signal)
# {
#     'action': 'STRONG_BUY',
#     'confidence': 0.75,
#     'factors': [...],
#     'risk_level': 3
# }
```

---

## 5. 與 Dexter 整合可能性

### 5.1 Dexter 的優勢

| 功能 | Dexter | 本系統 |
|------|--------|--------|
| 多輪對話 | ✅ 原生支持 | ❌ 需額外實現 |
| 工具調用 | ✅ 19 個財務工具 | 🔄 可整合 |
| 上下文理解 | ✅ LLM 原生 | 🔄 需規則定義 |

### 5.2 整合方案

```
Dexter 作為「前端智能層」
     │
     │ 用戶問題: "太空股最近怎麼樣？"
     │
     ▼
┌──────────────────────────────┐
│ Dexter Query Router          │
│ 識別需要多因子分析            │
└──────────────┬───────────────┘
               │
               │ 調用內部工具
               ▼
┌──────────────────────────────┐
│ MindfulRL 多因子信號系統      │
│ (本設計的實現)                │
└──────────────┬───────────────┘
               │
               │ 返回結構化信號
               ▼
┌──────────────────────────────┐
│ Dexter Answer Synthesizer    │
│ 生成自然語言回答              │
└──────────────────────────────┘
```

---

## 6. 實現路線圖

| 階段 | 任務 | 工作量 | 依賴 |
|------|------|--------|------|
| **Phase 1** | 事件類型標籤 (規則版) | 1 天 | 無 |
| **Phase 1** | 板塊定義配置 | 0.5 天 | 無 |
| **Phase 1** | 板塊情緒聚合 | 1 天 | 無 |
| **Phase 2** | 事件類型標籤 (LLM 版) | 2 天 | Phase 1 |
| **Phase 2** | 事件鏈檢測器 | 2 天 | Phase 1 |
| **Phase 2** | 異常檢測器 | 1 天 | 無 |
| **Phase 3** | 信號合成器 | 2 天 | Phase 2 |
| **Phase 3** | 回測驗證 | 2 天 | Phase 3 |
| **Phase 4** | Dexter 整合 | 3 天 | Phase 3 |

---

## 7. 評估指標

| 指標 | 定義 | 目標 |
|------|------|------|
| **信號準確率** | 預測方向正確比例 | > 55% |
| **板塊捕捉率** | 歷史板塊行情中識別出的比例 | > 70% |
| **假陽性率** | 錯誤信號比例 | < 30% |
| **提前天數** | 信號到爆發的平均天數 | 1-3 天 |

---

*創建日期: 2026-01-04*
*版本: 1.0*