# FinRL 整合架構設計

> **目的**: 將 LLM 增強的新聞情緒/風險評分整合到 RL 訓練流程
> **狀態**: 設計文檔 (2026-01-03)

---

## 1. 當前實現狀態

### 1.1 已完成組件

| 組件 | 檔案位置 | 功能 |
|------|----------|------|
| **Gymnasium 環境** | `env_stocktrading_llm.py:19-589` | 情緒信號整合 |
| **PPO 訓練** | `train_ppo_llm.py:275-637` | 自定義 PPO + GAE |
| **數據準備** | `prepare_dataset_openai.py:44-65` | 合併價格 + 評分 |
| **回測** | `backtest_openai.py:44-75` | 基礎績效評估 |
| **情緒評分** | `score_sentiment_*.py` | 多 Provider 支援 |
| **風險評分** | `score_risk_*.py` | 1-5 風險量表 |

### 1.2 數據流現況

```
新聞收集 (IBKR/Polygon/Finnhub)
     │
     ▼
LLM 評分 (gpt-5/Claude)
     │ sentiment_score: 1-5
     │ risk_score: 1-5
     ▼
數據合併 (prepare_dataset_openai.py)
     │ 價格 + 技術指標 + 情緒 + 風險
     ▼
RL 環境 (StockTradingEnv)
     │ 狀態空間包含 llm_sentiment, llm_risk
     │ 行動遮罩基於情緒
     ▼
PPO 訓練 (train_ppo_llm.py)
```

### 1.3 行動遮罩邏輯

`env_stocktrading_llm.py:312-332`:

```python
# 根據情緒調整行動
if sentiment <= 1.5:      # very bearish
    actions *= 0.1        # 大幅減少買入
    sell_actions *= 1.1   # 輕微增加賣出
elif sentiment <= 2.5:    # bearish
    actions *= 0.8
elif sentiment >= 4.5:    # very bullish
    actions *= 1.1
elif sentiment >= 3.5:    # bullish
    actions *= 1.05
else:                     # neutral
    actions *= 0.98
```

---

## 2. 關鍵缺口分析

### 2.1 數據深度問題 (Critical)

| 股票 | IBKR 歷史深度 | RL 訓練需求 | 差距 |
|------|---------------|-------------|------|
| NVDA | 23 天 | 252+ 天 | 🔴 不足 |
| AAPL | 46 天 | 252+ 天 | 🔴 不足 |
| TSLA | 43 天 | 252+ 天 | 🔴 不足 |

**解決方案**: 使用 Polygon 或 EODHD 補充歷史新聞

### 2.2 特徵工程缺失

當前: 單日情緒評分直接輸入
缺失:
- [ ] 情緒趨勢 (7-day/30-day MA)
- [ ] 情緒動量 (當日 vs 7日均值)
- [ ] 情緒波動度 (rolling std)
- [ ] 新聞數量特徵 (news_count_today)

### 2.3 無模型版本控制

當前: 模型保存到 `models/` 目錄，無 metadata
缺失:
- [ ] 訓練數據 hash
- [ ] 超參數記錄
- [ ] 回測結果
- [ ] 評分模型版本 (gpt-5 vs gpt-5.1)

### 2.4 無反饋循環

當前: 訓練 → 回測 → 結束
缺失:
- [ ] 預測記錄
- [ ] 實際結果追蹤
- [ ] 準確度分析
- [ ] 失敗案例學習

---

## 3. 整合設計

### 3.1 數據管道架構

```
                          ┌─────────────────┐
                          │   數據湖 (Data  │
                          │   Lake)         │
                          └────────┬────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
          ▼                        ▼                        ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  raw/           │      │  processed/     │      │  features/      │
├─────────────────┤      ├─────────────────┤      ├─────────────────┤
│ news/ibkr/      │      │ sentiment/      │      │ train_ready/    │
│ news/polygon/   │  →   │ risk/           │  →   │   AAPL.parquet  │
│ prices/daily/   │      │ aggregated/     │      │   NVDA.parquet  │
│ prices/intraday/│      │   7day_ma/      │      │   ...           │
└─────────────────┘      │   30day_ma/     │      └─────────────────┘
                         └─────────────────┘
                                   │
                                   ▼
                         ┌─────────────────┐
                         │  RL Training    │
                         └─────────────────┘
```

### 3.2 特徵工程設計

**新增特徵** (在 `prepare_dataset_openai.py` 擴展):

```python
def engineer_sentiment_features(df: pd.DataFrame) -> pd.DataFrame:
    """添加情緒相關衍生特徵"""

    # 基礎情緒 (已存在)
    # df['llm_sentiment']: 1-5
    # df['llm_risk']: 1-5

    # 情緒趨勢
    df['sentiment_7d_ma'] = df.groupby('tic')['llm_sentiment'].transform(
        lambda x: x.rolling(7, min_periods=1).mean()
    )
    df['sentiment_30d_ma'] = df.groupby('tic')['llm_sentiment'].transform(
        lambda x: x.rolling(30, min_periods=1).mean()
    )

    # 情緒動量 (當日 vs 7日均值)
    df['sentiment_momentum'] = df['llm_sentiment'] - df['sentiment_7d_ma']

    # 情緒波動度
    df['sentiment_volatility'] = df.groupby('tic')['llm_sentiment'].transform(
        lambda x: x.rolling(7, min_periods=1).std()
    )

    # 極端情緒標記
    df['sentiment_extreme'] = (
        (df['llm_sentiment'] >= 4.5) | (df['llm_sentiment'] <= 1.5)
    ).astype(int)

    # 風險趨勢
    df['risk_7d_ma'] = df.groupby('tic')['llm_risk'].transform(
        lambda x: x.rolling(7, min_periods=1).mean()
    )

    return df
```

### 3.3 狀態空間擴展

**當前狀態空間** (`env_stocktrading_llm.py`):
```
[cash, stock_holdings..., close_prices..., 技術指標..., llm_sentiment]
```

**擴展後狀態空間**:
```
[cash, stock_holdings..., close_prices..., 技術指標...,
 llm_sentiment, llm_risk,
 sentiment_7d_ma, sentiment_momentum, sentiment_volatility,
 risk_7d_ma, sentiment_extreme]
```

### 3.4 模型註冊設計

```python
@dataclass
class TrainedModel:
    """訓練模型 metadata"""
    model_id: str              # 唯一識別碼 (UUID)
    algorithm: str             # "PPO" | "CPPO" | "SAC"
    training_data_hash: str    # 訓練數據 MD5
    scoring_model: str         # "gpt-5" | "gpt-5.1"
    hyperparameters: dict
    training_date: datetime
    backtest_results: dict     # Sharpe, MDD, IR
    feature_columns: List[str] # 使用的特徵列

    def save(self, path: Path):
        """保存模型 + metadata"""
        torch.save(self.state_dict, path / "model.pth")
        with open(path / "metadata.json", "w") as f:
            json.dump(self.to_dict(), f)
```

**目錄結構**:
```
models/
├── registry.json              # 所有模型索引
└── ppo_sentiment_v1/
    ├── model.pth              # PyTorch 權重
    ├── metadata.json          # 訓練資訊
    └── backtest_results.png   # 績效圖表
```

---

## 4. 實現計劃

### Phase 1: 數據補充 (解決歷史深度)

```bash
# 1. 使用 Polygon 收集歷史新聞
python scripts/collection/collect_polygon_news.py \
    --start-date 2023-01-01 \
    --end-date 2024-12-31 \
    --tickers NVDA,AAPL,TSLA,MSFT,GOOGL

# 2. 批量評分
python score_sentiment_openai.py \
    --input data/news/raw/polygon/ \
    --output data/news/processed/sentiment/

# 3. 合併到訓練數據
python prepare_dataset_openai.py \
    --sources ibkr,polygon \
    --dedupe-by article_id
```

### Phase 2: 特徵工程

| 任務 | 檔案 | 行數 |
|------|------|------|
| 添加 `engineer_sentiment_features()` | `prepare_dataset_openai.py` | +50 |
| 更新狀態空間維度 | `env_stocktrading_llm.py` | ~10 |
| 更新 Actor-Critic 輸入維度 | `train_ppo_llm.py` | ~5 |

### Phase 3: 模型版本控制

| 任務 | 新增檔案 |
|------|----------|
| `TrainedModel` dataclass | `models/registry.py` |
| 自動保存 metadata | `train_ppo_llm.py` 修改 |
| 回測結果自動儲存 | `backtest_openai.py` 修改 |

### Phase 4: 回測驗證

```python
# 新增回測指標
def backtest_with_metrics(agent, test_data):
    """完整回測 + 指標計算"""
    results = agent.evaluate(test_data)

    return {
        "sharpe_ratio": calculate_sharpe(results),
        "max_drawdown": calculate_mdd(results),
        "information_ratio": calculate_ir(results, benchmark="SPY"),
        "win_rate": calculate_win_rate(results),
        "sentiment_correlation": calculate_sentiment_price_corr(results),
        "prediction_accuracy": calculate_prediction_accuracy(results)
    }
```

---

## 5. 優先順序

| 順序 | 任務 | 影響 | 工作量 |
|------|------|------|--------|
| 1 | 收集 Polygon 歷史新聞 | 🔴 Critical | 1-2 天 |
| 2 | 批量評分歷史新聞 | 🔴 Critical | 2-3 天 (API 限制) |
| 3 | 特徵工程 (`sentiment_7d_ma` 等) | 🟡 Important | 0.5 天 |
| 4 | 模型版本控制 | 🟢 Nice-to-have | 1 天 |
| 5 | 反饋循環 | 🟢 Nice-to-have | 2 天 |

---

## 6. 與 ARCHITECTURE_VISION.md 對應

| 架構層 | 當前狀態 | 此設計補充 |
|--------|----------|-----------|
| 即時智慧層 | 🔄 部分 (data_sources/) | - |
| 累積智慧層 | 🔄 部分 (訓練腳本) | ✅ 特徵工程, 模型註冊 |
| 人類智慧層 | ⏳ 未開始 | ⏳ 後續階段 |
| 統一數據持久層 | 🔄 部分 | ✅ 數據湖結構化 |

---

## 7. 風險與緩解

| 風險 | 影響 | 緩解措施 |
|------|------|----------|
| Polygon 評分 API 成本高 | $$$$ | 分批處理, 使用 flex mode |
| 歷史評分與現有不一致 | 模型混亂 | 固定評分模型版本 (gpt-5) |
| 特徵工程引入 look-ahead bias | 回測失真 | 嚴格 rolling window |
| 訓練數據量仍不足 | 過擬合 | 添加正則化, 早停 |

---

## 8. 成功指標

| 指標 | 目標 | 衡量方式 |
|------|------|----------|
| 歷史深度 | ≥1 年 | 每股票最早日期 |
| 訓練收斂 | Loss < 0.1 | 訓練日誌 |
| 回測 Sharpe | > 1.0 | 回測報告 |
| 情緒-收益相關 | > 0.3 | 相關性分析 |

---

*創建日期: 2026-01-03*
*版本: 1.0*