# 情緒衍生特徵定義

> **Status: HISTORICAL (RL line paused 2026-04-25)** — feature definitions for RL training; see RL_COLLAPSE_FINDINGS.

> **目的**: 定義從基礎情緒分數衍生的技術特徵，用於 RL 訓練
> **版本**: 1.0 (2026-01-04)

---

## 基礎特徵 (已有)

| 特徵名 | 範圍 | 來源 | 說明 |
|--------|------|------|------|
| `llm_sentiment` | 1-5 | LLM 評分 | 情緒分數 (1=very bearish, 5=very bullish) |
| `llm_risk` | 1-5 | LLM 評分 | 風險分數 (1=low risk, 5=high risk) |

---

## 衍生特徵定義

### 1. 情緒趨勢特徵

#### `sentiment_7d_ma` (7 日情緒移動平均)

**定義**: 過去 7 個交易日情緒分數的簡單移動平均

```python
df['sentiment_7d_ma'] = (
    df.groupby('ticker')['llm_sentiment']
    .transform(lambda x: x.rolling(window=7, min_periods=1).mean())
)
```

**用途**:
- 平滑短期噪音
- 識別情緒趨勢方向
- 作為基準線比較當日情緒

**解讀**:

| 數值 | 含義 |
|------|------|
| > 4.0 | 持續正面情緒 |
| 3.0-4.0 | 中性偏正 |
| 2.0-3.0 | 中性偏負 |
| < 2.0 | 持續負面情緒 |

---

#### `sentiment_30d_ma` (30 日情緒移動平均)

**定義**: 過去 30 個交易日情緒分數的移動平均

```python
df['sentiment_30d_ma'] = (
    df.groupby('ticker')['llm_sentiment']
    .transform(lambda x: x.rolling(window=30, min_periods=5).mean())
)
```

**用途**:
- 識別長期情緒趨勢
- 檢測情緒週期
- 作為 mean reversion 的參考

---

### 2. 情緒動量特徵

#### `sentiment_momentum` (情緒動量)

**定義**: 當日情緒與 7 日均值的差異

```python
df['sentiment_momentum'] = df['llm_sentiment'] - df['sentiment_7d_ma']
```

**用途**:
- 檢測情緒「加速度」
- 捕捉突發事件的即時反應
- 識別情緒轉折點

**解讀**:

| 數值 | 含義 | 交易信號 |
|------|------|----------|
| > +1.0 | 情緒急劇轉正 | 潛在買入機會 |
| +0.5 ~ +1.0 | 情緒改善 | 觀察 |
| -0.5 ~ +0.5 | 穩定 | 維持 |
| -1.0 ~ -0.5 | 情緒惡化 | 觀察 |
| < -1.0 | 情緒急劇轉負 | 潛在賣出/避險 |

**實例**:
```
假設:
- 今日情緒: 4.5 (very bullish)
- 7日均值: 3.2
- Momentum = 4.5 - 3.2 = +1.3 (情緒突然轉強)

這可能表示:
- 突發正面新聞 (財報超預期、合約簽訂)
- 需要驗證是否可持續
```

---

#### `sentiment_acceleration` (情緒加速度)

**定義**: 今日動量與昨日動量的變化

```python
df['sentiment_acceleration'] = (
    df.groupby('ticker')['sentiment_momentum']
    .transform(lambda x: x.diff())
)
```

**用途**:
- 二階導數：情緒變化的變化
- 檢測拐點

---

### 3. 情緒波動特徵

#### `sentiment_volatility` (情緒波動度)

**定義**: 過去 7 日情緒分數的標準差

```python
df['sentiment_volatility'] = (
    df.groupby('ticker')['llm_sentiment']
    .transform(lambda x: x.rolling(window=7, min_periods=3).std())
)
```

**用途**:
- 檢測市場「不確定性」
- 高波動 = 多空分歧大 = 風險信號

**解讀**:

| 數值 | 含義 |
|------|------|
| > 1.0 | 高度不確定，情緒劇烈波動 |
| 0.5-1.0 | 中等波動 |
| < 0.5 | 穩定，共識強 |

---

#### `sentiment_range` (情緒極差)

**定義**: 過去 7 日最高與最低情緒的差異

```python
df['sentiment_range'] = (
    df.groupby('ticker')['llm_sentiment']
    .transform(lambda x: x.rolling(window=7, min_periods=3).max()
               - x.rolling(window=7, min_periods=3).min())
)
```

**用途**:
- 另一種波動度衡量
- 對極端值更敏感

---

### 4. 極端情緒特徵

#### `sentiment_extreme` (極端情緒標記)

**定義**: 標記情緒是否處於極端區域

```python
df['sentiment_extreme'] = (
    (df['llm_sentiment'] >= 4.5) | (df['llm_sentiment'] <= 1.5)
).astype(int)
```

**用途**:
- 觸發逆向信號檢查
- 提醒可能的過度反應

---

#### `sentiment_zscore` (情緒 Z 分數)

**定義**: 當日情緒相對於 30 日分佈的標準化分數

```python
df['sentiment_zscore'] = (
    df.groupby('ticker').apply(
        lambda g: (g['llm_sentiment'] - g['llm_sentiment'].rolling(30).mean())
                  / g['llm_sentiment'].rolling(30).std()
    )
)
```

**用途**:
- 標準化不同股票的情緒水平
- 識別統計異常值

**解讀**:

| Z-Score | 含義 |
|---------|------|
| > +2 | 極端正面 (top 2.5%) |
| +1 ~ +2 | 顯著正面 |
| -1 ~ +1 | 正常範圍 |
| -2 ~ -1 | 顯著負面 |
| < -2 | 極端負面 (bottom 2.5%) |

---

### 5. 趨勢交叉特徵

#### `sentiment_golden_cross` (情緒黃金交叉)

**定義**: 7 日均線上穿 30 日均線

```python
df['sentiment_golden_cross'] = (
    (df['sentiment_7d_ma'] > df['sentiment_30d_ma']) &
    (df['sentiment_7d_ma'].shift(1) <= df['sentiment_30d_ma'].shift(1))
).astype(int)
```

**用途**:
- 情緒趨勢轉折信號
- 類似技術分析的 MA 交叉

---

#### `sentiment_death_cross` (情緒死亡交叉)

**定義**: 7 日均線下穿 30 日均線

```python
df['sentiment_death_cross'] = (
    (df['sentiment_7d_ma'] < df['sentiment_30d_ma']) &
    (df['sentiment_7d_ma'].shift(1) >= df['sentiment_30d_ma'].shift(1))
).astype(int)
```

---

### 6. 風險衍生特徵

#### `risk_7d_ma` (7 日風險移動平均)

```python
df['risk_7d_ma'] = (
    df.groupby('ticker')['llm_risk']
    .transform(lambda x: x.rolling(window=7, min_periods=1).mean())
)
```

---

#### `risk_spike` (風險飆升)

**定義**: 當日風險顯著高於 7 日均值

```python
df['risk_spike'] = (df['llm_risk'] - df['risk_7d_ma'] > 1.0).astype(int)
```

**用途**:
- 警示突發風險事件
- 觸發避險邏輯

---

## 參數配置建議

| 參數 | 預設值 | 可調範圍 | 說明 |
|------|--------|----------|------|
| `short_window` | 7 天 | 3-14 天 | 短期均線週期 |
| `long_window` | 30 天 | 20-60 天 | 長期均線週期 |
| `extreme_threshold` | ±1.5 | ±1.0 ~ ±2.0 | 極端情緒閾值 |
| `momentum_threshold` | ±1.0 | ±0.5 ~ ±1.5 | 動量顯著閾值 |
| `vol_min_periods` | 3 天 | 2-5 天 | 波動度最小觀測期 |

---

## 特徵評估方法

### 1. 與未來收益的相關性

```python
def evaluate_feature(df, feature_name, target='return_next_day'):
    """評估特徵的預測能力"""

    # 相關性
    corr = df[feature_name].corr(df[target])

    # 分組收益
    groups = pd.qcut(df[feature_name], q=5, labels=['Q1','Q2','Q3','Q4','Q5'])
    group_returns = df.groupby(groups)[target].mean()

    # 方向準確率 (適用於 momentum 類特徵)
    if 'momentum' in feature_name:
        accuracy = ((df[feature_name] > 0) == (df[target] > 0)).mean()
    else:
        accuracy = None

    return {
        'correlation': corr,
        'group_returns': group_returns,
        'direction_accuracy': accuracy
    }
```

### 2. 特徵重要性 (RL 訓練後)

```python
# 使用 SHAP 或 feature ablation 評估
# 哪些衍生特徵對 RL 決策影響最大
```

---

## 實現位置

```
建議新增:
├── src/
│   └── features/
│       ├── __init__.py
│       ├── sentiment_features.py    # 本文檔中的特徵計算
│       └── feature_config.py        # 參數配置

現有整合點:
├── prepare_dataset_openai.py        # 添加特徵計算步驟
└── env_stocktrading_llm.py          # 更新狀態空間
```

---

## 變更日誌

| 版本 | 日期 | 變更 |
|------|------|------|
| 1.0 | 2026-01-04 | 初始版本：定義 12 個衍生特徵 |

---

*創建者: Claude Code*
*最後更新: 2026-01-04*