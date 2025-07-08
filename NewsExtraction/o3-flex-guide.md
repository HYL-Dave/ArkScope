# o3 模型與 Flex Processing 使用指南

## 概述

本指南說明如何在 FinRL 新聞處理管道中使用 OpenAI 的 o3 模型和 Flex Processing 功能。

## 主要改動

### 1. API 客戶端配置
```python
from openai import OpenAI
import httpx

# 配置更長的 timeout 以適應 Flex Processing
client = OpenAI(
    api_key=self.openai_api_key,
    timeout=httpx.Timeout(1800.0, connect=60.0)  # 30分鐘 timeout
)
```

### 2. 模型調用方式
```python
response = client.chat.completions.create(
    model="o3",  # 使用 o3 模型（非 o3-mini）
    messages=[...],
    temperature=0.1,  # o3 可以使用稍高的 temperature
    service_tier="flex"  # 啟用 Flex Processing
)
```

## o3 模型優勢

### 1. 更強的分析能力
- 可以進行更複雜的金融分析
- 支持更長的上下文（可處理完整新聞文章）
- 更準確的實體識別和關係提取

### 2. 深度質量評估
o3 模型可以評估更多維度：
- 信息價值評分
- 數據支撐程度
- 客觀性評估
- 潛在偏見識別
- 可疑聲明標記

### 3. 模式識別
- 跨文檔的模式分析
- 異常檢測
- 趨勢預測

## Flex Processing 特點

### 優勢
1. **成本效益**：相比標準處理便宜 50%
2. **適合批量處理**：非實時需求的理想選擇
3. **更高的速率限制**：可處理更多請求

### 注意事項
1. **響應時間**：可能需要幾分鐘到幾小時
2. **超時設置**：需要設置較長的 timeout（建議 30 分鐘）
3. **批次處理**：建議批量提交請求以優化效率

## 使用建議

### 1. 批次大小優化
```python
batch_size = 10  # o3 + Flex 的建議批次大小
# 可根據實際響應時間調整
```

### 2. 提示詞優化
利用 o3 的強大能力，可以要求更複雜的分析：
```python
# 綜合分析示例
prompt = """
請進行以下綜合分析：
1. 相關性評估（包含影響時效性）
2. 情感分析驗證（包含可信度）
3. 內容質量評估（包含信息密度）
4. 市場影響預測（包含影響範圍）
5. 關鍵實體和事件提取
"""
```

### 3. 錯誤處理
```python
try:
    response = client.chat.completions.create(...)
except httpx.TimeoutException:
    # Flex Processing 可能超時，記錄並重試
    logger.warning("Flex processing timeout, retrying...")
except Exception as e:
    # 其他錯誤處理
    logger.error(f"API error: {e}")
```

## 成本估算

使用 o3 + Flex Processing：
- **輸入成本**：約 $XX per 1M tokens（比標準便宜 50%）
- **輸出成本**：約 $XX per 1M tokens（比標準便宜 50%）
- **100 條新聞深度分析**：預估 $5-10
- **完整數據集抽樣（1000條）**：預估 $50-100

## 運行命令

### 完整分析（使用 o3 + Flex）
```bash
python finrl_news_pipeline.py \
    --openai-key "your-api-key" \
    --model "o3" \
    --use-flex \
    --sample-size 200
```

### 深度質量分析
```bash
python quality_analysis_script.py \
    --openai-key "your-api-key" \
    --model "o3" \
    --use-flex
```

## 監控和日誌

### 1. 進度追蹤
腳本會顯示批次處理進度：
```
處理批次 1/10
批次 1 完成，已處理 10 條新聞
處理批次 2/10
...
```

### 2. 性能指標
日誌文件會記錄：
- 每個批次的處理時間
- API 調用成功率
- 平均響應時間

### 3. 質量報告增強
使用 o3 後，質量報告會包含：
- 更詳細的質量評分（7個維度）
- 常見問題統計
- 可疑內容標記
- 改進建議

## 最佳實踐

1. **測試先行**：先用小樣本測試，確認配置正確
2. **批量處理**：充分利用 Flex Processing 的批量優勢
3. **異步處理**：考慮實現異步調用以提高效率
4. **結果緩存**：保存 o3 的分析結果，避免重複調用
5. **成本監控**：定期檢查 API 使用量和成本

## 故障排除

### 問題：Timeout 錯誤
解決方案：
- 增加 timeout 設置到 3600 秒
- 減少批次大小
- 檢查網絡連接

### 問題：JSON 解析錯誤
解決方案：
- 在 prompt 中強調返回格式
- 添加 JSON 格式驗證
- 使用 try-except 處理解析錯誤

### 問題：成本超出預期
解決方案：
- 減少 sample_size
- 優化 prompt 長度
- 使用更精確的文本截取

## 未來優化方向

1. **並行處理**：實現多線程調用以加快處理速度
2. **增量更新**：只分析新增的新聞數據
3. **結果數據庫**：建立分析結果數據庫便於查詢
4. **自動重試機制**：實現智能重試邏輯
5. **成本預算控制**：添加成本上限控制功能