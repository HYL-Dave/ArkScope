# o3_summary 遺失資料修復計畫

## 問題摘要

- **o3_summary** 遺失 6 筆 BKR (Baker Hughes) 資料
- 原始資料位置：rows 19334-19339
- 所有使用 o3_summary 作為輸入的下游評分檔案都遺失這 6 筆
- **o4-mini high** 額外遺失 2 筆 API 失敗 (rows 12543, 44893)

---

## 修復狀態總覽

| 階段 | 狀態 | 完成日期 |
|------|------|----------|
| 第零階段：強制備份 | ✅ 完成 | 2025-12-27 |
| 第一階段：修復 o3_summary | ✅ 完成 | 2025-12-27 |
| 第二階段：修復下游 sentiment 評分 | ✅ 完成 | 2025-12-27 |
| 第三階段：修復 o4-mini high sentiment 額外遺失 | ✅ 完成 | 2025-12-28 |
| 第四階段：修復下游 risk 評分 (6 BKR) | ✅ 完成 | 2025-12-28 |
| 第五階段：修復 o4-mini high risk 額外遺失 | ✅ 完成 | 2025-12-28 |

備份位置: `/mnt/md0/finrl/backups/repair_20251227/`

### 最終修復狀態 (2025-12-28)

所有修復已完成：

| 類型 | 修復狀態 | 有效分數 |
|------|----------|----------|
| 所有 sentiment | ✅ 完整 | 77,871 |
| 所有 risk | ✅ 完整 | 77,871 |
| o4-mini high risk | ✅ 完整 | 77,871 |

### 技術備註

- Stage 5 (o4-mini high risk 額外遺失) 需要 `max_completion_tokens=3200` 才能成功
- Row 52326 (MRVL) 使用了 3031 completion tokens
- 預設的 800 tokens 對於 o4-mini high reasoning 模型不足

---

## ⚠️ 第零階段：強制備份（修復前必須完成）

> **重要**: 所有修復操作開始前，必須先完成所有受影響檔案的備份。
> 備份未完成前，禁止進行任何修改操作。

### 0.1 備份目標清單

```
備份目錄: /mnt/md0/finrl/backups/repair_YYYYMMDD/

需備份檔案 (27 個):
1. o3/summary/o3_news_with_summary.csv                    # o3_summary 原檔
2-7. o3/sentiment/*.csv 和 o3/risk/*.csv (6 個)
8-13. o4-mini/sentiment/*.csv 和 o4-mini/risk/*.csv (6 個)
14-21. gpt-5/sentiment/*.csv 和 gpt-5/risk/*.csv (8 個)
22-27. gpt-4.1*/sentiment/*.csv 和 gpt-4.1*/risk/*.csv (6 個)
```

### 0.2 備份命令

```bash
# 建立備份目錄
BACKUP_DIR="/mnt/md0/finrl/backups/repair_$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# 執行備份
python scripts/repair/repair_o3_data.py --stage backup --backup-dir "$BACKUP_DIR"

# 驗證備份完整性
python scripts/repair/repair_o3_data.py --verify-backup "$BACKUP_DIR"
```

### 0.3 備份驗證清單

- [x] 所有 27 個檔案已備份
- [x] 備份檔案大小與原檔一致
- [x] 備份目錄已記錄完整路徑
- [x] 備份完成時間已記錄

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
Row 44893: 2015-11-17 | GILD (API 失敗)

受影響檔案:
- /mnt/md0/finrl/o4-mini/sentiment/sentiment_o4_mini_high_by_o3_summary.csv
- /mnt/md0/finrl/o4-mini/risk/risk_o4_mini_high_by_o3_summary.csv
```

### 3.2 修復結果

| Row | 股票 | 日期 | Sentiment | Risk | 狀態 |
|-----|------|------|-----------|------|------|
| 12543 | AMGN | 2018-03-16 | 3 ✅ | 1 ✅ | 已修復 (2025-12-28) |
| 44893 | GILD | 2015-11-17 | 4 ✅ | 3 ✅ | 已修復 (2025-12-28) |

### 3.3 原始錯誤診斷更正

> **重要更正 (2025-12-28)**
>
> 原始計畫錯誤地將 Row **44887** (GILD 2015-11-**25**) 列為「o4-mini high API 失敗」。
>
> **實際應修復的是 Row 44893 (GILD 2015-11-17)**：
> - Row 44893 有有效的 o3_summary (707 chars)
> - 但 o4-mini high 對此行評分失敗 (API 錯誤)
> - 其他模型對此行都有正常評分
>
> **Row 44887 不需要修復** (資料品質問題)：
> - Row 44887 的原始 Article 欄位為空 (NaN)
> - 因此 o3_summary 無法生成，也是 NaN
> - **所有模型**對此行的評分都是 NaN（不只是 o4-mini high）
> - 這是**原始資料品質問題**，不是處理錯誤
>
> **各模型對 Row 44887 的評分比較**：
> | 模型 | o3_summary | Sentiment |
> |------|------------|-----------|
> | o3 high | NaN | NaN |
> | o3 medium | NaN | NaN |
> | o4-mini high | NaN | NaN |
> | o4-mini medium | NaN | NaN |
> | gpt-5 high | NaN | NaN |
> | gpt-4.1 | NaN | NaN |
> | 原始 DeepSeek | - | 3.0 (基於 title) |
>
> 原始 DeepSeek 能給出 3.0 分是因為它可能使用了 Article_title 作為輸入，
> 而我們的評分流程是基於完整文章內容（Article → o3_summary → 評分）。

---

## 第四階段：修復下游 risk 評分 (6 BKR)

### 4.1 問題識別

第二階段修復時**只執行了 sentiment 評分，risk 評分被遺漏**。

**所有 risk 檔案共同缺失的 6 筆 BKR (rows 19334-19339):**

| Row | Stock | Date |
|-----|-------|------|
| 19334 | BKR | 2020-07-20 |
| 19335 | BKR | 2020-07-17 |
| 19336 | BKR | 2020-07-16 |
| 19337 | BKR | 2020-07-12 |
| 19338 | BKR | 2020-07-10 |
| 19339 | BKR | 2020-07-07 |

### 4.2 受影響檔案 (13 個 risk 檔案)

| 模型 | Reasoning | 檔案 | 當前有效分數 |
|------|-----------|------|-------------|
| o3 | high | risk_o3_high_by_o3_summary.repaired.csv | 77,865 |
| o3 | medium | risk_o3_medium_by_o3_summary.repaired.csv | 77,865 |
| o3 | low | risk_o3_low_by_o3_summary.repaired.csv | 77,865 |
| o4-mini | high | risk_o4_mini_high_by_o3_summary.repaired.csv | 77,863 ⚠️ |
| o4-mini | medium | risk_o4_mini_medium_by_o3_summary.repaired.csv | 77,865 |
| o4-mini | low | risk_o4_mini_low_by_o3_summary.repaired.csv | 77,865 |
| gpt-5 | high | risk_gpt-5_high_by_o3_summary.repaired.csv | 77,865 |
| gpt-5 | medium | risk_gpt-5_medium_by_o3_summary.repaired.csv | 77,865 |
| gpt-5 | low | risk_gpt-5_low_by_o3_summary.repaired.csv | 77,865 |
| gpt-5 | minimal | risk_gpt-5_minimal_by_o3_summary.repaired.csv | 77,865 |
| gpt-4.1 | - | risk_gpt-4.1_by_o3_summary.repaired.csv | 77,865 |
| gpt-4.1-mini | - | risk_gpt-4.1-mini_by_o3_summary.repaired.csv | 77,865 |
| gpt-4.1-nano | - | risk_gpt-4.1-nano_by_o3_summary.repaired.csv | 77,865 |

### 4.3 修復命令

```bash
python scripts/repair/repair_o3_data.py --stage risk-bkr --skip-backup-check
```

### 4.4 修復狀態

| 步驟 | 狀態 | 日期 |
|------|------|------|
| 識別缺失行 | ✅ 完成 | 2025-12-28 |
| 生成 risk 分數 | ✅ 完成 (77/78) | 2025-12-28 |
| 驗證修復結果 | ✅ 完成 | 2025-12-28 |

**備註**: 77/78 是因為 o4-mini high Row 19336 已有分數，自動跳過。

---

## 第五階段：修復 o4-mini high risk 額外遺失

### 5.1 額外遺失識別

o4-mini high risk 除了 6 筆 BKR 外，還額外缺失 2 筆 (原始 API 失敗)：

| Row | Stock | Date | 原因 |
|-----|-------|------|------|
| 18077 | BKNG | 2018-02-27 | 原始評分時 API 失敗 |
| 52326 | MRVL | 2014-09-02 | 原始評分時 API 失敗 |

### 5.2 修復命令

```bash
python scripts/repair/repair_o3_data.py --stage o4mini-risk-extra --skip-backup-check
```

### 5.3 修復狀態

| 步驟 | 狀態 | 日期 |
|------|------|------|
| 識別缺失行 | ✅ 完成 | 2025-12-28 |
| 生成 risk 分數 | ✅ 完成 | 2025-12-28 |
| 驗證修復結果 | ✅ 完成 | 2025-12-28 |

### 5.4 修復結果

| Row | 股票 | 日期 | Risk 分數 | 備註 |
|-----|------|------|-----------|------|
| 18077 | BKNG | 2018-02-27 | 1 ✅ | 使用 max_completion_tokens=1600 |
| 52326 | MRVL | 2014-09-02 | 1 ✅ | 使用 max_completion_tokens=3200 (需 3031 tokens) |

**技術問題**: o4-mini high 模型需要更多 completion tokens 才能完成評分：
- 預設 800 tokens 不足
- Row 52326 需要 3031 tokens 才能成功

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

- [x] o3_summary 行數 = 127,176 (與原始資料一致)
- [x] 所有下游評分檔案行數 = 127,170 + 6 = 127,176
- [x] 隨機抽樣 100 行驗證對齊正確性
- [x] 邊界區域 (rows 19330-19345) 逐行驗證
- [x] 新增的 6 筆評分值合理性檢查
- [ ] o4-mini high Row 12543, 44893 修復完成

### 備份策略

所有修復前先備份：
```bash
cp file.csv file.csv.backup_$(date +%Y%m%d)
```

---

## 實際成本

| 階段 | API 呼叫數 | 模型 | 實際成本 | 狀態 |
|------|-----------|------|----------|------|
| Stage 1: o3_summary 修復 | 6 | o3 | ~$0.50 | ✅ |
| Stage 2: Sentiment 評分 (13 files × 6) | 78 | 混合 | ~$4.00 | ✅ |
| Stage 3: o4-mini high sentiment 額外 | 4 | o4-mini | ~$0.04 | ✅ |
| Stage 4: Risk 評分 (13 files × 6) | 78 | 混合 | ~$4.00 | ✅ |
| Stage 5: o4-mini high risk 額外 | 2 | o4-mini | ~$0.06* | ✅ |
| **總計** | **168** | - | **~$8.60** | ✅ |

*Stage 5 使用 max_completion_tokens=3200，成本略高

**Stage 4 成本細節:**
- o3 (3 configs × 6) = 18 calls @ ~$1.50
- o4-mini (3 configs × 6) = 18 calls @ ~$0.25
- gpt-5 (4 configs × 6) = 24 calls @ ~$2.00
- gpt-4.1 系列 (3 configs × 6) = 18 calls @ ~$0.25

---

## 執行順序

1. ✅ **備份所有受影響檔案** (Stage 0)
2. ✅ **修復 o3_summary** (Stage 1 - 生成 6 筆 summary)
3. ✅ **修復 13 個 sentiment 評分檔案** (Stage 2 - 每個生成 6 筆評分)
4. ✅ **修復 o4-mini high sentiment 額外遺失** (Stage 3 - Row 12543, 44893)
5. ✅ **修復 13 個 risk 評分檔案 (6 BKR)** (Stage 4 - 2025-12-28)
6. ✅ **修復 o4-mini high risk 額外遺失** (Stage 5 - Row 18077, 52326 - 2025-12-28)
7. ✅ **驗證所有檔案對齊正確性** (2025-12-28)
8. ✅ **更新 NEWS_STORAGE_DESIGN.md 的 N 值** (2025-12-28)
9. ✅ **用 .repaired.csv 替換原始檔案** (2025-12-28)
10. ✅ **清理暫存檔案** (2025-12-28)

---

## 最終清理報告

所有修復已完成並清理：

| 項目 | 數量 | 狀態 |
|------|------|------|
| 替換的檔案 | 27 | ✅ 完成 |
| 刪除 .repaired.csv | 27 | ✅ 已刪除 |
| 刪除 .pre_repair.csv | 27 | ✅ 已刪除 |
| 刪除 .backup_*.csv | 68 | ✅ 已刪除 |

**保留的備份**: `/mnt/md0/finrl/backups/repair_20251227/`

**最終檔案行數**: 所有 27 個檔案現為 **2,093,082 行** (原 2,092,944 + 138 修復行)

---

## 已知資料品質問題 (不需修復)

以下行因原始資料問題無法評分，這是正常狀態：

| Row | 股票 | 日期 | 問題描述 |
|-----|------|------|----------|
| 44887 | GILD | 2015-11-25 | 原始 Article 為空 (NaN)，無法生成 summary |

這些行在所有模型中都是 NaN，是資料品質問題而非處理錯誤。

---

*建立日期: 2025-12-27*
*最後更新: 2025-12-28 (全部修復完成、檔案替換、暫存清理)*