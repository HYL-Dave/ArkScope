# o3_summary 遺失資料修復計畫

## 問題摘要

- **o3_summary** 遺失 6 筆 BKR (Baker Hughes) 資料
- 原始資料位置：rows 19334-19339
- 所有使用 o3_summary 作為輸入的下游評分檔案都遺失這 6 筆
- **o4-mini high** 額外遺失 2 筆 API 失敗 (rows 12543, 44887)

---

## 第一階段：修復 o3_summary

### 1.1 遺失資料識別

```
原始檔案: /mnt/md0/finrl/huggingface_datasets/FinRL_DeepSeek_sentiment/sentiment_deepseek_new_cleaned_nasdaq_news_full.csv
o3_summary: /mnt/md0/finrl/o3/summary/o3_news_with_summary.csv

遺失的 6 筆 (原始 row index):
Row 19334: 2020-07-20 | BKR | Oil firm BJ Services files...
Row 19335: 2020-07-17 | BKR | Energy Sector Update...
Row 19336: 2020-07-16 | BKR | Interesting BKR Put And Call...
Row 19337: 2020-07-12 | BKR | Validea's Top Five Energy...
Row 19338: 2020-07-10 | BKR | Energy Sector Update...
Row 19339: 2020-07-07 | BKR | Down to handful of active rigs...
```

### 1.2 修復步驟

1. 從原始 CSV 提取 rows 19334-19339 的 Article 內容
2. 呼叫 o3 API 生成 6 筆 summary (使用原始配置)
3. 插入到 o3_summary 的正確位置 (row 19334 之後)
4. 驗證對齊正確性

### 1.3 原始配置

```bash
# o3_summary 原始生成配置 (推測)
python openai_summary.py \
    --input /mnt/md0/finrl/huggingface_datasets/FinRL_DeepSeek_sentiment/sentiment_deepseek_new_cleaned_nasdaq_news_full.csv \
    --output /mnt/md0/finrl/o3/summary/o3_news_with_summary.csv \
    --model o3 \
    --reasoning-effort high \
    --text-column Article \
    --symbol-column Stock_symbol
```

---

## 第二階段：修復下游評分檔案

### 2.1 受影響檔案清單 (26 個)

**Sentiment 評分 (13 檔):**

| 模型 | Reasoning | 檔案路徑 |
|------|-----------|----------|
| o3 | high | `/mnt/md0/finrl/o3/sentiment/sentiment_o3_high_by_o3_summary.csv` |
| o3 | medium | `/mnt/md0/finrl/o3/sentiment/sentiment_o3_medium_by_o3_summary.csv` |
| o3 | low | `/mnt/md0/finrl/o3/sentiment/sentiment_o3_low_by_o3_summary.csv` |
| o4-mini | high | `/mnt/md0/finrl/o4-mini/sentiment/sentiment_o4_mini_high_by_o3_summary.csv` |
| o4-mini | medium | `/mnt/md0/finrl/o4-mini/sentiment/sentiment_o4_mini_medium_by_o3_summary.csv` |
| o4-mini | low | `/mnt/md0/finrl/o4-mini/sentiment/sentiment_o4_mini_low_by_o3_summary.csv` |
| gpt-5 | high | `/mnt/md0/finrl/gpt-5/sentiment/sentiment_gpt-5_high_by_o3_summary.csv` |
| gpt-5 | medium | `/mnt/md0/finrl/gpt-5/sentiment/sentiment_gpt-5_medium_by_o3_summary.csv` |
| gpt-5 | low | `/mnt/md0/finrl/gpt-5/sentiment/sentiment_gpt-5_low_by_o3_summary.csv` |
| gpt-5 | minimal | `/mnt/md0/finrl/gpt-5/sentiment/sentiment_gpt-5_minimal_by_o3_summary.csv` |
| gpt-4.1 | - | `/mnt/md0/finrl/gpt-4.1/sentiment/sentiment_gpt-4.1_by_o3_summary.csv` |
| gpt-4.1-mini | - | `/mnt/md0/finrl/gpt-4.1-mini/sentiment/sentiment_gpt-4.1-mini_by_o3_summary.csv` |
| gpt-4.1-nano | - | `/mnt/md0/finrl/gpt-4.1-nano/sentiment/sentiment_gpt-4.1-nano_by_o3_summary.csv` |

**Risk 評分 (13 檔):**

| 模型 | Reasoning | 檔案路徑 |
|------|-----------|----------|
| o3 | high | `/mnt/md0/finrl/o3/risk/risk_o3_high_by_o3_summary.csv` |
| o3 | medium | `/mnt/md0/finrl/o3/risk/risk_o3_medium_by_o3_summary.csv` |
| o3 | low | `/mnt/md0/finrl/o3/risk/risk_o3_low_by_o3_summary.csv` |
| o4-mini | high | `/mnt/md0/finrl/o4-mini/risk/risk_o4_mini_high_by_o3_summary.csv` |
| o4-mini | medium | `/mnt/md0/finrl/o4-mini/risk/risk_o4_mini_medium_by_o3_summary.csv` |
| o4-mini | low | `/mnt/md0/finrl/o4-mini/risk/risk_o4_mini_low_by_o3_summary.csv` |
| gpt-5 | high | `/mnt/md0/finrl/gpt-5/risk/risk_gpt-5_high_by_o3_summary.csv` |
| gpt-5 | medium | `/mnt/md0/finrl/gpt-5/risk/risk_gpt-5_medium_by_o3_summary.csv` |
| gpt-5 | low | `/mnt/md0/finrl/gpt-5/risk/risk_gpt-5_low_by_o3_summary.csv` |
| gpt-5 | minimal | `/mnt/md0/finrl/gpt-5/risk/risk_gpt-5_minimal_by_o3_summary.csv` |
| gpt-4.1 | - | `/mnt/md0/finrl/gpt-4.1/risk/risk_gpt-4.1_by_o3_summary.csv` |
| gpt-4.1-mini | - | `/mnt/md0/finrl/gpt-4.1-mini/risk/risk_gpt-4.1-mini_by_o3_summary.csv` |
| gpt-4.1-nano | - | `/mnt/md0/finrl/gpt-4.1-nano/risk/risk_gpt-4.1-nano_by_o3_summary.csv` |

### 2.2 修復策略

對每個下游評分檔案：

1. 讀取修復後的 o3_summary 中的 6 筆新增 summary
2. 呼叫對應模型 API 生成 6 筆評分 (使用原始配置)
3. 插入到評分檔案的正確位置 (row 19334)
4. 驗證對齊正確性

### 2.3 原始配置重建

```bash
# o3 sentiment 評分配置
python score_sentiment_openai.py \
    --input <repaired_o3_summary> \
    --output <output_file> \
    --model o3 \
    --reasoning-effort {high|medium|low} \
    --text-column o3_summary

# gpt-5 sentiment 評分配置
python score_sentiment_openai.py \
    --input <repaired_o3_summary> \
    --output <output_file> \
    --model gpt-5 \
    --reasoning-effort {high|medium|low|minimal} \
    --text-column o3_summary

# gpt-4.1 系列 (無 reasoning)
python score_sentiment_openai.py \
    --input <repaired_o3_summary> \
    --output <output_file> \
    --model gpt-4.1 \
    --text-column o3_summary
```

---

## 第三階段：修復 o4-mini high 額外遺失

### 3.1 額外遺失識別

```
Row 12543: 2018-03-16 | AMGN (API 失敗)
Row 44887: 2015-11-17 | GILD (API 失敗)

受影響檔案:
- /mnt/md0/finrl/o4-mini/sentiment/sentiment_o4_mini_high_by_o3_summary.csv
- /mnt/md0/finrl/o4-mini/risk/risk_o4_mini_high_by_o3_summary.csv
```

### 3.2 修復步驟

1. 從 o3_summary 提取 rows 12543, 44887 的 summary
2. 呼叫 o4-mini (reasoning=high) API 生成這 2 筆評分
3. 插入到對應評分檔案的正確位置
4. 驗證對齊正確性

---

## 實作腳本設計

### repair_o3_summary.py

```python
#!/usr/bin/env python3
"""
修復 o3_summary 遺失的 6 筆 BKR 資料
"""

ORIGINAL_CSV = "/mnt/md0/finrl/huggingface_datasets/FinRL_DeepSeek_sentiment/sentiment_deepseek_new_cleaned_nasdaq_news_full.csv"
O3_SUMMARY_CSV = "/mnt/md0/finrl/o3/summary/o3_news_with_summary.csv"

MISSING_ROWS = [19334, 19335, 19336, 19337, 19338, 19339]

def main():
    # 1. 載入原始資料
    # 2. 提取遺失行的 Article 內容
    # 3. 呼叫 o3 API 生成 summary
    # 4. 備份原始 o3_summary
    # 5. 插入新 summary 到正確位置
    # 6. 驗證對齊
    pass
```

### repair_downstream_scores.py

```python
#!/usr/bin/env python3
"""
修復所有使用 o3_summary 的下游評分檔案
"""

REPAIRED_O3_SUMMARY = "/mnt/md0/finrl/o3/summary/o3_news_with_summary_repaired.csv"

AFFECTED_FILES = [
    # (file_path, model, reasoning, task)
    ("o3/sentiment/sentiment_o3_high_by_o3_summary.csv", "o3", "high", "sentiment"),
    # ... 26 files total
]

def repair_file(file_path, model, reasoning, task, new_summaries):
    # 1. 呼叫對應模型 API 評分新增的 6 筆
    # 2. 備份原始檔案
    # 3. 插入評分到正確位置
    # 4. 驗證對齊
    pass

def main():
    for file_info in AFFECTED_FILES:
        repair_file(*file_info)
```

---

## 驗證清單

### 修復後驗證

- [ ] o3_summary 行數 = 127,176 (與原始資料一致)
- [ ] 所有下游評分檔案行數 = 127,170 + 6 = 127,176
- [ ] 隨機抽樣 100 行驗證對齊正確性
- [ ] 邊界區域 (rows 19330-19345) 逐行驗證
- [ ] 新增的 6 筆評分值合理性檢查

### 備份策略

所有修復前先備份：
```bash
cp file.csv file.csv.backup_$(date +%Y%m%d)
```

---

## 預估成本

| 階段 | API 呼叫數 | 模型 | 預估成本 |
|------|-----------|------|----------|
| o3_summary 修復 | 6 | o3 | ~$0.50 |
| o3 評分 (6 configs) | 36 | o3 | ~$3.00 |
| o4-mini 評分 (6 configs) | 36 | o4-mini | ~$0.50 |
| gpt-5 評分 (8 configs) | 48 | gpt-5 | ~$4.00 |
| gpt-4.1 系列 (6 configs) | 36 | gpt-4.1-* | ~$0.50 |
| o4-mini high 額外修復 | 4 | o4-mini | ~$0.05 |
| **總計** | **166** | - | **~$8.55** |

---

## 執行順序

1. **備份所有受影響檔案**
2. **修復 o3_summary** (生成 6 筆 summary)
3. **修復 26 個下游評分檔案** (每個生成 6 筆評分)
4. **修復 o4-mini high 額外遺失** (2 筆 × 2 任務)
5. **驗證所有檔案對齊正確性**
6. **更新 NEWS_STORAGE_DESIGN.md 的 N 值**

---

*建立日期: 2025-12-27*