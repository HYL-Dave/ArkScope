# FinRL 新聞處理系統 - 專案交接文件

## 📁 必須下載的核心檔案

### 1. 主要處理腳本
- **`finrl_news_pipeline.py`** (Artifact ID: finrl-news-pipeline)
  - 主要的數據處理管道
  - 包含 7 個處理步驟
  - 支援 o3, o4-mini, gpt-4.1, gpt-4.1-mini

### 2. 質量分析腳本
- **`quality_analysis_script.py`** (Artifact ID: quality-analysis-script)
  - 深度數據質量分析
  - 時間分佈分析
  - 語言質量檢查

### 3. 測試和工具腳本
- **`test_o3_flex.py`** (Artifact ID: test-o3-flex)
  - 模型配置測試
  - 支援所有模型測試
  - 包含比較功能

- **`cost_calculator.py`** (Artifact ID: cost-calculator)
  - 成本估算工具
  - 模型比較
  - 混合策略建議

### 4. 配置檔案
- **`env_config.sh`** (Artifact ID: env-config)
  - 環境變量模板
  - 包含所有配置選項

- **`requirements.txt`** (Artifact ID: requirements)
  - Python 依賴清單

### 5. 文檔
- **`readme_o3.md`** (Artifact ID: readme-o3)
  - 主要使用說明
  - 包含所有命令範例

- **`o3-flex-guide.md`** (Artifact ID: o3-flex-guide)
  - 技術實施指南
  - API 使用細節

- **`model-selection-guide.md`** (Artifact ID: model-selection-guide)
  - 模型選擇決策指南
  - 性能基準

### 6. 快速開始腳本
- **`quickstart.sh`** (Artifact ID: quick-start)
  - 一鍵安裝腳本
  - 環境設置和測試

## 🔄 專案當前狀態

### 已完成
1. ✅ 完整的數據處理管道
2. ✅ 支援最新的 OpenAI 模型（o3, o4-mini, gpt-4.1, gpt-4.1-mini）
3. ✅ Flex Processing 整合
4. ✅ 英文 prompt 優化
5. ✅ 成本計算和優化工具
6. ✅ 完整的測試套件
7. ✅ 詳細的文檔

### 技術重點
- **Reasoning 模型特性**：無 temperature，使用 reasoning_effort
- **Flex Processing**：僅 reasoning 模型支援，成本降低 50%
- **混合策略**：可以組合使用不同模型優化成本

### 已知限制
1. Flex Processing 響應時間較長（幾分鐘到幾小時）
2. o3/o1 模型可能需要特殊 API 權限
3. 批次處理大小需要根據實際測試調整

## 📋 下一步開發建議

### 1. 性能優化
```python
# 實現並行處理
from concurrent.futures import ThreadPoolExecutor
# 可以並行處理多個批次
```

### 2. 增量更新功能
```python
# 追蹤已處理的新聞
processed_ids = load_processed_ids()
new_news = filter_unprocessed(all_news, processed_ids)
```

### 3. 結果數據庫
```sql
-- 建立分析結果表
CREATE TABLE news_analysis (
    news_id TEXT PRIMARY KEY,
    stock_symbol TEXT,
    analysis_date TIMESTAMP,
    model_used TEXT,
    sentiment_score REAL,
    market_impact TEXT,
    quality_scores JSON
);
```

### 4. 實時監控
- API 使用量追蹤
- 成本實時統計
- 質量指標儀表板

## 🚀 快速繼續開發

### 1. 環境設置
```bash
# 安裝依賴
pip install -r requirements.txt

# 設置環境變量
source env_config.sh
# 編輯 env_config.sh 填入您的 API Key
```

### 2. 測試現有功能
```bash
# 測試模型配置
python test_o3_flex.py --api-key "$OPENAI_API_KEY" --model o3 --use-flex

# 運行小樣本測試
python finrl_news_pipeline.py --model o4-mini --use-flex --sample-size 10
```

### 3. 查看成本
```bash
# 估算不同方案
python cost_calculator.py --compare --num-news 1000
```

## 💡 重要提醒

### API 參數差異
```python
# Reasoning 模型 (o3, o4-mini)
{
    "model": "o3",
    "messages": [{"role": "user", "content": "..."}],
    "reasoning_effort": "medium",  # 不是 temperature!
    "max_completion_tokens": 2000,
    "service_tier": "flex"
}

# 一般模型 (gpt-4.1, gpt-4.1-mini)
{
    "model": "gpt-4.1",
    "messages": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."}
    ],
    "temperature": 0,
    "max_tokens": 2000
}
```

### 成本優化策略
1. 使用 o4-mini + Flex 作為預設（平衡成本和質量）
2. 只對重要新聞使用 o3
3. 大規模篩選使用 gpt-4.1-mini
4. 充分利用批次處理

## 📞 問題追蹤

### 常見問題
1. **Timeout**: 增加 timeout 到 3600 秒
2. **JSON 解析錯誤**: 檢查 prompt 格式
3. **權限錯誤**: 確認 API key 有相應模型權限

### 調試命令
```bash
# 詳細日誌
export LOG_LEVEL=DEBUG
python finrl_news_pipeline.py --model o3 --sample-size 1

# 測試單一新聞
python -c "
from finrl_news_pipeline import FinRLNewsProcessor
processor = FinRLNewsProcessor('your-key')
# 測試單條新聞處理
"
```

## 🔗 相關資源

- [OpenAI Flex Processing 文檔](https://platform.openai.com/docs/guides/flex-processing)
- [原始數據集 (FNSPID)](https://huggingface.co/datasets/Zihan1004/FNSPID)
- [FinRL Contest 2025](https://github.com/Open-Finance-Lab/FinRL_Contest_2025)

---

**最後更新**: 2024-01-23  
**版本**: 2.0.0  
**主要貢獻**: 整合 o3 模型、Flex Processing、成本優化

## 附錄：檔案 Artifact ID 對照表

| 檔案名稱 | Artifact ID | 說明 |
|---------|-------------|------|
| finrl_news_pipeline.py | finrl-news-pipeline | 主處理腳本 |
| quality_analysis_script.py | quality-analysis-script | 質量分析 |
| test_o3_flex.py | test-o3-flex | 測試腳本 |
| cost_calculator.py | cost-calculator | 成本計算 |
| env_config.sh | env-config | 環境配置 |
| requirements.txt | requirements | 依賴清單 |
| readme_o3.md | readme-o3 | 使用說明 |
| o3-flex-guide.md | o3-flex-guide | 技術指南 |
| model-selection-guide.md | model-selection-guide | 模型選擇 |
| quickstart.sh | quick-start | 快速開始 |
| 本文件 | project-handover | 交接文件 |