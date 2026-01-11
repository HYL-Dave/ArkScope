# src/signals/ 模組使用指南

多因子信號偵測系統，用於從新聞情緒數據中提取交易信號。

## 架構概覽

```
NewsData (DataFrame with llm_sentiment, llm_risk)
    │
    ├─→ EventTagger ──────→ 事件分類 (EARNINGS_BEAT, POLICY_POSITIVE, etc.)
    │
    ├─→ SectorAggregator ─→ 板塊指標 (sector momentum, rotation)
    │
    ├─→ EventChainDetector → 事件鏈 (POLICY + TECH_MILESTONE = 強信號)
    │
    ├─→ AnomalyDetector ──→ 異常偵測 (sentiment/volume z-score)
    │
    └─→ SignalSynthesizer ─→ 綜合交易信號 (STRONG_BUY/SELL/HOLD)
```

## 模組說明

| 模組 | 類別 | 功能 |
|------|------|------|
| `event_tagger.py` | `EventTagger` | 規則式事件分類 (13 種事件類型) |
| `sector_aggregator.py` | `SectorAggregator` | 板塊層級情緒分析與動能偵測 |
| `event_chain.py` | `EventChainDetector` | 連續事件序列偵測 (7 種預定義模式) |
| `anomaly_detector.py` | `AnomalyDetector` | Z-score 統計異常偵測 |
| `synthesizer.py` | `SignalSynthesizer` | 多因子信號綜合與交易建議 |

## 輸入數據要求

DataFrame 需包含以下欄位：

| 欄位 | 類型 | 說明 |
|------|------|------|
| `ticker` | string | 股票代號 |
| `date` | string | 日期 (YYYY-MM-DD) |
| `title` | string | 新聞標題 |
| `llm_sentiment` | float | LLM 情緒分數 (1-5) |
| `llm_risk` | float | LLM 風險分數 (1-5，可選) |

---

## 1. EventTagger - 事件分類器

將新聞標題分類為 13 種事件類型。

### 基本用法

```python
from src.signals import EventTagger

tagger = EventTagger()

# 單篇新聞
result = tagger.tag("Tesla beats Q3 earnings expectations, raises guidance")
print(result.primary_type)     # 'EARNINGS_BEAT'
print(result.confidence)       # 0.75
print(result.keywords_matched) # ['beat', 'raises guidance']
print(result.event_types)      # ['EARNINGS_BEAT'] (可能有多個)

# 批量處理
articles = [
    {'title': 'SpaceX achieves breakthrough with Starship landing'},
    {'title': 'Fed announces new rate policy supporting tech sector'}
]
results = tagger.tag_batch(articles)
```

### 自訂配置

```python
from pathlib import Path

# 使用自訂事件類型定義
tagger = EventTagger(config_path=Path('config/event_types.yaml'))
```

### 支援的事件類型

| 類型 | 說明 | 關鍵詞範例 |
|------|------|-----------|
| `POLICY_POSITIVE` | 政策利多 | executive order, subsidy, tax credit |
| `POLICY_NEGATIVE` | 政策利空 | ban, tariff, sanction, crackdown |
| `EARNINGS_BEAT` | 財報超預期 | beat, exceed, raises guidance |
| `EARNINGS_MISS` | 財報不及預期 | miss, disappoint, lowers guidance |
| `TECH_MILESTONE` | 技術突破 | launch, breakthrough, patent, first ever |
| `ANALYST_UPGRADE` | 分析師調升 | upgrade, raise target, buy rating |
| `ANALYST_DOWNGRADE` | 分析師調降 | downgrade, lower target, sell rating |
| `FUNDING` | 融資/併購 | ipo, fundraise, acquisition, merger |
| `PARTNERSHIP` | 合作夥伴 | partner, collaborate, agreement, deal |
| `PRODUCT_LAUNCH` | 產品發布 | launch, release, unveil, introduce |
| `EXEC_DEPARTURE` | 高管離職 | resign, step down, departure |
| `EXEC_HIRE` | 高管任命 | appoint, hire, new ceo |
| `LEGAL` | 法律訴訟 | lawsuit, litigation, settlement |
| `GENERAL` | 一般新聞 | (無匹配時預設) |

### 輸出結構

```python
@dataclass
class TagResult:
    event_types: List[str]      # 所有匹配的事件類型
    primary_type: str           # 主要事件類型 (最高分)
    confidence: float           # 信心度 (0-1)
    keywords_matched: List[str] # 匹配到的關鍵詞
```

---

## 2. SectorAggregator - 板塊分析器

計算板塊層級的情緒指標和動能變化。

### 基本用法

```python
from src.signals import SectorAggregator
import pandas as pd

aggregator = SectorAggregator()

df = pd.read_csv('your_scored_news.csv')

# 查詢股票所屬板塊
sector = aggregator.get_sector('NVDA')  # 'AI_CHIPS'

# 獲取板塊內所有股票
tickers = aggregator.get_sector_tickers('AI_CHIPS')  # ['NVDA', 'AMD', ...]
```

### 計算板塊指標

```python
# 計算特定日期的板塊指標
metrics = aggregator.calculate_sector_metrics(df, date='2025-01-03')

for sector, m in metrics.items():
    print(f"{sector}:")
    print(f"  sentiment_mean: {m.sentiment_mean:.2f}")
    print(f"  bullish_ratio: {m.bullish_ratio:.1%}")
    print(f"  bearish_ratio: {m.bearish_ratio:.1%}")
    print(f"  article_count: {m.article_count}")
    print(f"  tickers_covered: {m.tickers_covered}")
```

### 偵測板塊動能

```python
# 比較近期 vs 先前情緒變化
momentum = aggregator.detect_sector_momentum(df, sector='AI_CHIPS', lookback=7)

print(f"Trend: {momentum.trend}")           # ACCELERATING / DECELERATING / STABLE
print(f"Momentum: {momentum.momentum:.2f}") # 正=走強, 負=走弱
print(f"Recent sentiment: {momentum.recent_sentiment:.2f}")
print(f"Prior sentiment: {momentum.prior_sentiment:.2f}")
```

### 偵測板塊輪動

```python
# 找出哪些板塊正在走強/走弱
rotation = aggregator.detect_sector_rotation(df, lookback=7)

print("板塊排名 (by momentum):")
for r in rotation[:5]:
    print(f"  {r['sector']}: {r['trend']}, momentum={r['momentum']:.2f}")
```

### 預設板塊定義

```python
DEFAULT_SECTORS = {
    'SPACE': ['RKLB', 'ASTS', 'LUNR', 'SPCE', 'ASTR', 'RDW', 'MNTS', 'BKSY', 'PL'],
    'AI_CHIPS': ['NVDA', 'AMD', 'AVGO', 'MRVL', 'INTC', 'QCOM', 'MU', 'ARM'],
    'AI_SOFTWARE': ['MSFT', 'GOOGL', 'META', 'PLTR', 'AI', 'PATH', 'SNOW'],
    'EV': ['TSLA', 'RIVN', 'LCID', 'NIO', 'XPEV', 'LI', 'PTRA', 'GOEV'],
    'BIOTECH': ['MRNA', 'BNTX', 'REGN', 'GILD', 'AMGN', 'BIIB', 'VRTX'],
    'FINTECH': ['SQ', 'PYPL', 'COIN', 'AFRM', 'UPST', 'SOFI', 'HOOD'],
    'CLOUD': ['SNOW', 'NET', 'DDOG', 'MDB', 'CRWD', 'ZS', 'OKTA'],
    'CYBERSECURITY': ['CRWD', 'PANW', 'ZS', 'OKTA', 'FTNT', 'S'],
    'CLEAN_ENERGY': ['ENPH', 'SEDG', 'FSLR', 'RUN', 'PLUG', 'BE', 'CHPT'],
    'DEFENSE': ['LMT', 'RTX', 'NOC', 'BA', 'GD', 'HII'],
    'RETAIL': ['AMZN', 'WMT', 'TGT', 'COST', 'HD', 'LOW'],
    'HEALTHCARE': ['UNH', 'JNJ', 'PFE', 'LLY', 'ABBV', 'MRK'],
    'BANKS': ['JPM', 'BAC', 'WFC', 'C', 'GS', 'MS'],
}
```

可透過 `config/sectors.yaml` 自訂板塊定義。

### 輸出結構

```python
@dataclass
class SectorMetrics:
    sector: str
    sentiment_mean: float
    sentiment_std: float
    risk_mean: float
    article_count: int
    bullish_ratio: float    # sentiment >= 4 的比例
    bearish_ratio: float    # sentiment <= 2 的比例
    extreme_count: int      # sentiment >= 4.5 或 <= 1.5 的數量
    tickers_covered: List[str]

@dataclass
class SectorMomentum:
    sector: str
    momentum: float         # recent - prior sentiment
    trend: str              # ACCELERATING / DECELERATING / STABLE
    recent_sentiment: float
    prior_sentiment: float
    days_analyzed: int
```

---

## 3. EventChainDetector - 事件鏈偵測器

偵測連續事件序列，這類組合信號通常比單一事件更具預測力。

### 基本用法

```python
from src.signals import EventChainDetector

detector = EventChainDetector(window_days=14)  # 14 天內的事件視為相關

# 從 DataFrame 轉換為 Event 物件
# 注意: 需要 event_type 欄位 (來自 EventTagger)
events = detector.events_from_dataframe(
    df,
    ticker_col='ticker',
    date_col='date',
    event_type_col='event_type',
    sentiment_col='llm_sentiment',
    title_col='title'
)

# 偵測事件鏈
chains = detector.detect_chains(events)

for chain in chains:
    print(f"Pattern: {chain.pattern}")
    print(f"  Impact Score: {chain.impact_score:.2f}")
    print(f"  Ticker: {chain.ticker}")
    print(f"  Duration: {chain.start_date} to {chain.end_date}")
    print(f"  Events: {[e.event_type for e in chain.events]}")
```

### 預定義事件鏈模式

| Pattern | 序列 | 倍數 | 說明 |
|---------|------|------|------|
| `POLICY_TECH_CONFIRMATION` | POLICY_POSITIVE → TECH_MILESTONE | 1.5x | 政策支持後技術突破 |
| `UPGRADE_EARNINGS_CONFIRMATION` | ANALYST_UPGRADE → EARNINGS_BEAT | 1.3x | 分析師調升被財報驗證 |
| `FUNDING_MILESTONE` | FUNDING → TECH_MILESTONE | 1.4x | 融資後達成里程碑 |
| `EARNINGS_MOMENTUM` | EARNINGS_BEAT → ANALYST_UPGRADE | 1.3x | 財報超預期引發調升 |
| `PARTNERSHIP_LAUNCH` | PARTNERSHIP → PRODUCT_LAUNCH | 1.2x | 合作後產品發布 |
| `NEGATIVE_SPIRAL` | EARNINGS_MISS → ANALYST_DOWNGRADE | 1.3x | 財報不及預期引發調降 (bearish) |
| `EXEC_TURMOIL` | EXEC_DEPARTURE → ANALYST_DOWNGRADE | 1.2x | 高管離職引發擔憂 (bearish) |

### 輸出結構

```python
@dataclass
class Event:
    date: datetime
    ticker: Optional[str]
    sector: Optional[str]
    event_type: str
    sentiment_impact: float  # -1 to 1 (from llm_sentiment)
    title: str
    article_id: Optional[str]

@dataclass
class EventChain:
    events: List[Event]
    start_date: datetime
    end_date: datetime
    impact_score: float      # 累積影響分數 (可正可負)
    pattern: str             # 匹配的模式名稱
    ticker: Optional[str]
    sector: Optional[str]
```

---

## 4. AnomalyDetector - 異常偵測器

使用 Z-score 統計方法偵測情緒或新聞量的異常。

### 基本用法

```python
from src.signals import AnomalyDetector

detector = AnomalyDetector(
    min_history=14,   # 最少需要 14 天歷史數據
    z_threshold=2.0   # Z-score > 2 視為異常
)
```

### 情緒異常偵測

```python
# 單一股票的情緒異常
anomaly = detector.detect_sentiment_anomaly(
    df,
    ticker='NVDA',
    date='2025-01-03'
)

if anomaly.is_anomaly:
    print(f"情緒異常!")
    print(f"  Z-score: {anomaly.z_score:.2f}")
    print(f"  Direction: {anomaly.direction}")  # POSITIVE / NEGATIVE
    print(f"  Current: {anomaly.current_value:.2f}")
    print(f"  Historical mean: {anomaly.historical_mean:.2f}")
    print(f"  Percentile: {anomaly.percentile:.1%}")
else:
    print(f"Reason: {anomaly.reason}")  # INSUFFICIENT_DATA / NO_DATA_FOR_DATE
```

### 新聞量異常偵測

```python
# 新聞量突然暴增
vol_anomaly = detector.detect_volume_anomaly(
    df,
    ticker='NVDA',
    date='2025-01-03',
    rolling_window=14
)

if vol_anomaly.is_anomaly:
    print(f"新聞量異常!")
    print(f"  今日文章數: {vol_anomaly.current_count}")
    print(f"  歷史平均: {vol_anomaly.historical_mean:.1f}")
    print(f"  Z-score: {vol_anomaly.z_score:.2f}")
```

### 板塊層級異常

```python
# 整個板塊的情緒異常
sector_tickers = ['NVDA', 'AMD', 'AVGO', 'MRVL']
sector_anomaly = detector.detect_sector_anomaly(
    df,
    sector_tickers=sector_tickers,
    date='2025-01-03'
)
```

### 跨股票掃描

```python
# 找出今日情緒最極端的股票
top_anomalies = detector.detect_cross_ticker_anomaly(
    df,
    date='2025-01-03',
    top_n=10
)

for ticker, anomaly in top_anomalies:
    print(f"{ticker}: z={anomaly.z_score:.2f}, {anomaly.direction}")
```

### 輸出結構

```python
@dataclass
class SentimentAnomaly:
    is_anomaly: bool
    z_score: float
    direction: str          # POSITIVE / NEGATIVE / NEUTRAL
    percentile: float
    historical_mean: float
    historical_std: float
    current_value: float
    reason: str             # '' (valid) / INSUFFICIENT_DATA / NO_DATA_FOR_DATE

@dataclass
class VolumeAnomaly:
    is_anomaly: bool
    z_score: float
    current_count: int
    historical_mean: float
    historical_std: float
    reason: str
```

---

## 5. SignalSynthesizer - 信號綜合器

將所有信號來源整合成單一交易建議。

### 基本用法

```python
from src.signals import SignalSynthesizer

synthesizer = SignalSynthesizer()

# 收集各來源的信號
signals = {
    'sector_momentum': sector_momentum_result,    # from SectorAggregator
    'sentiment_anomaly': sentiment_anomaly_result, # from AnomalyDetector
    'volume_anomaly': volume_anomaly_result,       # from AnomalyDetector
    'event_chains': list_of_chains,                # from EventChainDetector
    'extreme_sentiment': True,                     # or count of extreme articles
}

# 綜合分析
result = synthesizer.synthesize(signals, ticker='NVDA', sector='AI_CHIPS')

print(f"Action: {result.action.value}")       # STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL
print(f"Confidence: {result.confidence:.1%}")
print(f"Composite Score: {result.composite_score:.2f}")
print(f"Risk Level: {result.risk_level}/5")
print(f"Reasoning: {result.reasoning}")
```

### 查看因子貢獻

```python
contributions = synthesizer.get_factor_contributions(result)

for factor, pct in contributions.items():
    print(f"  {factor}: {pct:.1%}")
```

### 自訂權重

```python
# 初始化時設定
synthesizer = SignalSynthesizer(weights={
    'sector_momentum': 0.20,
    'event_chain': 0.35,
    'sentiment_anomaly': 0.25,
    'volume_anomaly': 0.10,
    'extreme_sentiment': 0.10,
})

# 或動態調整
synthesizer.adjust_weights({'event_chain': 0.40})
```

### 預設權重與閾值

```python
DEFAULT_WEIGHTS = {
    'sector_momentum': 0.25,
    'event_chain': 0.30,        # 事件鏈權重最高
    'sentiment_anomaly': 0.20,
    'volume_anomaly': 0.15,
    'extreme_sentiment': 0.10,
}

THRESHOLDS = {
    'strong_buy': 0.6,
    'buy': 0.3,
    'sell': -0.3,
    'strong_sell': -0.6,
}
```

### 輸出結構

```python
class SignalAction(Enum):
    STRONG_BUY = 'STRONG_BUY'
    BUY = 'BUY'
    HOLD = 'HOLD'
    SELL = 'SELL'
    STRONG_SELL = 'STRONG_SELL'

@dataclass
class TradingSignal:
    action: SignalAction
    confidence: float           # 0-1
    composite_score: float      # 加權綜合分數
    risk_level: int             # 1-5
    factors: List[SignalFactor] # 各因子詳情
    ticker: Optional[str]
    sector: Optional[str]
    reasoning: str              # 人類可讀的推理說明

@dataclass
class SignalFactor:
    factor_type: str
    impact: float
    weight: float
    details: Dict[str, Any]
```

---

## 完整使用流程

```python
import pandas as pd
from src.signals import (
    EventTagger, SectorAggregator, EventChainDetector,
    AnomalyDetector, SignalSynthesizer
)

# 1. 載入已評分的新聞數據
df = pd.read_csv('scored_news.csv')
# 必要欄位: ticker, date, title, llm_sentiment

# 2. 事件分類 (如果還沒有 event_type 欄位)
tagger = EventTagger()
df['event_type'] = df['title'].apply(lambda t: tagger.tag(t).primary_type)

# 3. 初始化各偵測器
sector_agg = SectorAggregator()
anomaly_det = AnomalyDetector()
chain_det = EventChainDetector()
synthesizer = SignalSynthesizer()

# 4. 準備事件鏈數據
events = chain_det.events_from_dataframe(df, event_type_col='event_type')
all_chains = chain_det.detect_chains(events)

# 5. 對每檔股票生成信號
date = '2025-01-03'
results = []

for ticker in df['ticker'].unique():
    sector = sector_agg.get_sector(ticker)

    # 收集該股票的所有信號
    signals = {
        'sector_momentum': sector_agg.detect_sector_momentum(df, sector) if sector else {},
        'sentiment_anomaly': anomaly_det.detect_sentiment_anomaly(df, ticker, date),
        'volume_anomaly': anomaly_det.detect_volume_anomaly(df, ticker, date),
        'event_chains': [c for c in all_chains if c.ticker == ticker],
    }

    # 綜合分析
    result = synthesizer.synthesize(signals, ticker=ticker, sector=sector)

    results.append({
        'ticker': ticker,
        'sector': sector,
        'action': result.action.value,
        'confidence': result.confidence,
        'risk': result.risk_level,
        'score': result.composite_score,
        'reasoning': result.reasoning
    })

# 6. 篩選強信號
strong_buy = [r for r in results if r['action'] == 'STRONG_BUY' and r['confidence'] > 0.7]
strong_sell = [r for r in results if r['action'] == 'STRONG_SELL' and r['confidence'] > 0.7]

print(f"Strong Buy signals: {len(strong_buy)}")
print(f"Strong Sell signals: {len(strong_sell)}")
```

---

## 與 FinRL 整合

這些模組產生的信號可作為 FinRL 環境的額外特徵：

```python
# 將 composite_score 加入觀察空間
observation['signal_score'] = result.composite_score

# 將 action 用於 position sizing
if result.action == SignalAction.STRONG_BUY:
    position_multiplier = 1.5
elif result.action == SignalAction.STRONG_SELL:
    position_multiplier = 0.5
else:
    position_multiplier = 1.0

# 將 risk_level 用於風控
if result.risk_level >= 4:
    max_position_size *= 0.5  # 高風險時減少部位
```

---

## 配置文件

- `config/sectors.yaml` - 自訂板塊定義
- `config/event_types.yaml` - 自訂事件類型關鍵詞

---

## 相關文件

- [STRATEGIC_DIRECTION_2026Q1.md](../../docs/strategy/STRATEGIC_DIRECTION_2026Q1.md) - 多因子信號系統設計背景
- [MULTI_FACTOR_SIGNAL_DETECTION.md](../../docs/design/MULTI_FACTOR_SIGNAL_DETECTION.md) - 詳細設計文檔