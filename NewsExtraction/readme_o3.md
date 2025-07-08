# FinRL 新聞數據處理管道 (Reasoning Models + Flex Processing)

使用 OpenAI reasoning 模型（o3, o4-mini）和 Flex Processing 進行高質量金融新聞數據處理。

## 🚀 快速開始

### 1. 一鍵安裝和測試
```bash
# 賦予執行權限
chmod +x quickstart.sh

# 運行快速開始腳本
./quickstart.sh
```

### 2. 手動安裝
```bash
# 安裝依賴
pip install datasets duckdb pyarrow pandas requests tqdm openai httpx numpy matplotlib seaborn scikit-learn textstat

# 設置 API Key
export OPENAI_API_KEY="your-api-key"

# 測試配置
python test_o3_flex.py --api-key "$OPENAI_API_KEY"
```

## 📊 主要功能

### 使用 Reasoning 模型的優勢
- **深度分析**：7個質量維度評估（語法、完整性、專業性、可讀性、信息價值、數據支撐、客觀性）
- **市場影響預測**：預測新聞對股價的影響方向、持續時間和範圍
- **實體識別**：精確提取人物、機構、金額等關鍵信息
- **異常檢測**：識別可疑或需要驗證的內容

### Flex Processing 特性
- **成本優化**：比標準處理便宜 50%
- **批量處理**：適合大規模數據處理
- **靈活時間**：可接受較長處理時間以換取成本優勢

## 🔧 使用方法

### 基本命令

#### 1. 完整處理流程（推薦首次使用）
```bash
python finrl_news_pipeline.py \
    --openai-key "your-api-key" \
    --model o3 \
    --use-flex \
    --sample-size 200 \
    --reasoning-effort medium
```

#### 2. 快速處理（跳過 LLM）
```bash
python finrl_news_pipeline.py --skip-llm
```

#### 3. 使用不同模型
```bash
# 使用 o4-mini (輕量級 reasoning 模型)
python finrl_news_pipeline.py --model o4-mini --use-flex

# 使用 gpt-4.1 (不支援 Flex)
python finrl_news_pipeline.py --model gpt-4.1
```

#### 4. 深度質量分析
```bash
python quality_analysis_script.py \
    --openai-key "your-api-key" \
    --model o3 \
    --use-flex \
    --sample-size 500
```

### 參數說明

| 參數 | 說明 | 預設值 | 適用模型 |
|------|------|--------|----------|
| `--openai-key` | OpenAI API Key | 環境變量 | 所有 |
| `--model` | 使用的模型 | o3 | o3, o4-mini, gpt-4.1, gpt-4.1-mini |
| `--use-flex` | 啟用 Flex Processing | True | 僅 o3, o4-mini |
| `--reasoning-effort` | Reasoning 強度 | medium | 僅 o3, o4-mini |
| `--sample-size` | LLM 檢查的樣本數量 | 100 | 所有 |
| `--batch-size` | 每批處理的新聞數量 | 10 | 所有 |

### Reasoning Effort 選擇指南

| Effort | 適用場景 | 處理速度 | 成本 |
|--------|----------|----------|------|
| `low` | 簡單分類、情感分析 | 快 | 低 |
| `medium` | 綜合新聞分析 | 中 | 中 |
| `high` | 深度模式識別、複雜推理 | 慢 | 高 |

## 📁 輸出文件

### 數據文件
- `news_89_2013_2023_raw.parquet` - 原始下載數據
- `news_89_2013_2023_cleaned.parquet` - 清洗後的完整數據
- `news_89_2013_2023_daily.parquet` - 每日聚合數據
- `high_quality_news.parquet` - 高質量數據子集
- `finrl_news.db` - DuckDB 數據庫

### 報告文件
- `data_quality_report.json` - 基礎質量報告
- `comprehensive_quality_report.json` - 深度分析報告
- `news_temporal_heatmap.png` - 時間分佈熱力圖
- `finrl_news_pipeline.log` - 處理日誌

## 💰 成本估算

使用不同模型的預估成本：

| 模型 | Flex Processing | 100條新聞 | 1000條新聞 |
|------|----------------|-----------|------------|
| o3 | ✓ | $5-10 | $50-100 |
| o4-mini | ✓ | $2-5 | $20-50 |
| gpt-4.1 | ✗ | $3-6 | $30-60 |
| gpt-4.1-mini | ✗ | $1-2 | $10-20 |

*注：實際成本取決於新聞長度、reasoning effort 和分析深度*

## 🔍 數據使用示例

### 1. 查詢特定股票新聞
```python
import duckdb

con = duckdb.connect('finrl_news.db')
aapl_news = con.execute("""
    SELECT * FROM news 
    WHERE Stock_symbol = 'AAPL' 
    AND importance_score > 0.8
    ORDER BY Date DESC
    LIMIT 10
""").df()
```

### 2. 獲取市場影響預測
```python
import pandas as pd
import json

# 讀取質量報告
with open('data_quality_report.json') as f:
    report = json.load(f)

# 查看市場影響分析
market_impacts = report['llm_validation']['market_impact_analysis']
```

### 3. 與 FinRL 整合
```python
# 讀取每日聚合數據
news_df = pd.read_parquet('news_89_2013_2023_daily.parquet')

# 與價格數據合併
merged_df = price_df.merge(
    news_df[['Stock_symbol', 'Date', 'Sentiment', 'importance_score']],
    on=['Stock_symbol', 'Date'],
    how='left'
)
```

## ⚠️ 注意事項

### Reasoning 模型使用
1. o3/o1 模型沒有 temperature 參數，使用 reasoning_effort
2. 必須設置 max_completion_tokens
3. Flex Processing 響應時間可能較長（幾分鐘到幾小時）

### 模型選擇建議
- **簡單任務**：使用 gpt-4.1-mini 或 o4-mini
- **標準分析**：使用 gpt-4.1 或 o3 (medium effort)
- **深度分析**：使用 o3 (high effort)

### 最佳實踐
1. **英文 Prompt**：美股新聞分析建議使用英文
2. **批量處理**：充分利用 Flex Processing 的批量優勢
3. **錯誤重試**：腳本包含自動重試機制
4. **成本控制**：監控 API 使用量，合理設置 sample_size

## 🐛 故障排除

### 常見問題

#### 1. Timeout 錯誤
```bash
# 增加 timeout 設置
export API_TIMEOUT=3600  # 60分鐘
```

#### 2. 模型訪問錯誤
- 確認 API Key 有相應模型權限
- o3/o1 可能需要特殊權限

#### 3. Flex Processing 不可用
- 只有 reasoning 模型支援 Flex
- 一般模型會自動關閉 Flex

## 📈 進階使用

### 自定義 Reasoning Effort
```python
# 根據任務動態調整
if complex_analysis:
    processor.reasoning_effort = "high"
else:
    processor.reasoning_effort = "low"
```

### 混合模型策略
```python
# 初步篩選使用便宜模型
initial_filter = process_with_model("gpt-4.1-mini")

# 深度分析使用 reasoning 模型
deep_analysis = process_with_model("o3", subset=high_value_news)
```

## 📞 支持

如有問題，請檢查：
1. 日誌文件 `finrl_news_pipeline.log`
2. OpenAI 服務狀態
3. API 使用額度和權限

---

**版本**: 2.0.0 (Reasoning Models + Flex Processing)  
**更新日期**: 2024-01