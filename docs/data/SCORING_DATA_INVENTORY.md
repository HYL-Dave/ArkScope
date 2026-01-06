# 評分數據清單 (Scoring Data Inventory)

> 此文件從 `NEWS_STORAGE_DESIGN.md` 分離，專門記錄 LLM 評分數據狀態。
>
> 相關文件:
> - [儲存設計](../../NEWS_STORAGE_DESIGN.md) - 目錄結構、Schema、收集策略
> - [新聞數據清單](NEWS_DATA_INVENTORY.md) - 原始新聞數據來源
> - [歷史分析紀錄](../analysis/HISTORICAL_ANALYSIS_LOG.md) - 分析實驗紀錄
> - [評分比較報告](../analysis/SCORE_COMPARISON_REPORT.md) - A/B 評分比較

> **⚠️ 版本說明 (2026-01-06)**
> - 欄位改名已完成：`sentiment_deepseek` → `sentiment_{model}` 格式
> - 改名後的檔案已取代原始評分檔案，原始版本移至 `/mnt/md0/finrl/backups/`
> - 文件中提及的 `/mnt/md0/finrl/renamed/` 目錄已不存在（內容已整合至主目錄）
> - Section 11.4.2 和 11.6 的改名流程為歷史紀錄，改名工作已完成

---

## 11. 評分資料清單 (Scoring Data Inventory)

### 11.1 總覽

- **資料位置**: `/mnt/md0/finrl/`
- **總檔案數**: 58 個評分 CSV
- **基底行數**: 127,176 (原始新聞數據)
- **有效摘要行數**: 77,871 (有 Lsa_summary 的記錄)
- **欄位改名版本**: `/mnt/md0/finrl/renamed/`

### 11.2 按評分模型分組

| 模型 | 檔案數 | sentiment | risk | 有效評分數 |
|------|-------|-----------|------|-----------|
| o3 | 10 | 5 | 5 | 77,871 |
| o4-mini | 8 | 4 | 4 | 77,871 |
| gpt-5 | 16 | 8 | 8 | 77,871 |
| gpt-5-mini | 2 | 1 | 1 | 77,871 |
| gpt-4.1 | 2 | 1 | 1 | 77,871 |
| gpt-4.1-mini | 12 | 6 | 6 | 77,871 |
| gpt-4.1-nano | 2 | 1 | 1 | 77,871 |
| haiku | 2 | 1 | 1 | 77,871 |
| sonnet | 2 | 1 | 1 | 77,871 |
| opus | 2 | 1 | 1 | 77,871 |

### 11.3 檔案詳細清單

#### claude/

| 檔案 | 行數 | 有效評分 | 評分欄位 | 摘要來源 |
|------|------|---------|---------|---------|
| risk_haiku_by_gpt5_summary.csv | 127,176 | 77,871 | sentiment_deepseek, risk_haiku | gpt_5_summary |
| risk_opus_by_gpt5_summary.csv | 127,176 | 77,871 | sentiment_deepseek, risk_opus | gpt_5_summary |
| risk_sonnet_by_gpt5_summary.csv | 127,176 | 77,871 | sentiment_deepseek, risk_sonnet | gpt_5_summary |
| sentiment_haiku_by_gpt5_summary.csv | 127,176 | 126,224 | sentiment_deepseek, sentiment_haiku | gpt_5_summary |
| sentiment_opus_by_gpt5_summary.csv | 127,176 | 126,224 | sentiment_deepseek, sentiment_opus | gpt_5_summary |
| sentiment_sonnet_by_gpt5_summary.csv | 127,176 | 126,224 | sentiment_deepseek, sentiment_sonnet | gpt_5_summary |

**註**: Claude sentiment 有 126,224 筆評分，因為是對所有有 gpt_5_summary 的記錄評分

#### gpt-4.1/

| 檔案 | 行數 | 有效評分 | 評分欄位 | 摘要來源 |
|------|------|---------|---------|---------|
| risk_gpt-4.1_by_o3_summary.csv | 127,176 | 77,871 | sentiment_deepseek, risk_deepseek | o3_summary |
| sentiment_gpt-4.1_by_o3_summary.csv | 127,176 | 77,871 | sentiment_deepseek | o3_summary |

#### gpt-4.1-mini/

| 檔案 | 行數 | 有效評分 | 評分欄位 | 摘要來源 |
|------|------|---------|---------|---------|
| risk_gpt-4.1-mini_by_gpt-5_reason_*_summary.csv (5個) | 127,176 | 77,871 | sentiment_deepseek, risk_deepseek | gpt_5_summary |
| risk_gpt-4.1-mini_by_o3_summary.csv | 127,176 | 77,871 | sentiment_deepseek, risk_deepseek | o3_summary |
| sentiment_gpt-4.1-mini_by_gpt-5_reason_*_summary.csv (5個) | 127,176 | 77,871 | sentiment_deepseek | gpt_5_summary |
| sentiment_gpt-4.1-mini_by_o3_summary.csv | 127,176 | 77,871 | sentiment_deepseek | o3_summary |

#### gpt-4.1-nano/

| 檔案 | 行數 | 有效評分 | 評分欄位 | 摘要來源 |
|------|------|---------|---------|---------|
| risk_gpt-4.1-nano_by_o3_summary.csv | 127,176 | 77,871 | sentiment_deepseek, risk_deepseek | o3_summary |
| sentiment_gpt-4.1-nano_by_o3_summary.csv | 127,176 | 77,871 | sentiment_deepseek | o3_summary |

#### gpt-5/

| 檔案 | 行數 | 有效評分 | 評分欄位 | 摘要來源 |
|------|------|---------|---------|---------|
| risk_gpt-5_R_*_V_low_by_gpt-5_summary.csv (4個) | 127,176 | 77,871 | sentiment_deepseek, risk_deepseek | gpt_5_summary |
| risk_gpt-5_*_by_o3_summary.csv (4個) | 127,176 | 77,871 | sentiment_deepseek, risk_deepseek | o3_summary |
| sentiment_gpt-5_R_*_V_low_by_gpt-5_summary.csv (4個) | 127,176 | 77,871 | sentiment_deepseek | gpt_5_summary |
| sentiment_gpt-5_*_by_o3_summary.csv (4個) | 127,176 | 77,871 | sentiment_deepseek | o3_summary |

#### gpt-5-mini/

| 檔案 | 行數 | 有效評分 | 評分欄位 | 摘要來源 |
|------|------|---------|---------|---------|
| risk_gpt-5-mini_with_R_high_V_low_by_gpt-5_summary.csv | 127,176 | 77,871 | sentiment_deepseek, risk_deepseek | gpt_5_summary |
| sentiment_gpt-5-mini_with_R_high_V_low_by_gpt-5_summary.csv | 127,176 | 77,871 | sentiment_deepseek | gpt_5_summary |

#### o3/

| 檔案 | 行數 | 有效評分 | 評分欄位 | 摘要來源 |
|------|------|---------|---------|---------|
| risk_o3_high_by_gpt-5_summary.csv | 127,176 | 77,871 | sentiment_deepseek, risk_deepseek | gpt_5_summary |
| risk_o3_*_by_o3_summary.csv (3個) | 127,176 | 77,871 | sentiment_deepseek, risk_deepseek | o3_summary |
| risk_o3_medium_2.csv | 127,176 | 77,871 | risk_deepseek | - |
| sentiment_o3_high_4.csv | 77,871 | 77,871 | sentiment_deepseek | - |
| sentiment_o3_high_by_gpt-5_summary.csv | 127,176 | 77,871 | sentiment_deepseek | gpt_5_summary |
| sentiment_o3_*_by_o3_summary.csv (3個) | 127,176 | 77,871 | sentiment_deepseek | o3_summary |

**註**: `sentiment_o3_high_4.csv` 是過濾修復後的版本，只保留有效記錄

#### o4-mini/

| 檔案 | 行數 | 有效評分 | 評分欄位 | 摘要來源 |
|------|------|---------|---------|---------|
| risk_o4_mini_*_by_o3_summary.csv (3個) | 127,176 | 77,871 | sentiment_deepseek, risk_deepseek | o3_summary |
| risk_o4_mini_medium_2.csv | 127,176 | 77,871 | risk_deepseek | - |
| sentiment_o4_mini_high_1.csv | 77,871 | 77,871 | sentiment_deepseek | - |
| sentiment_o4_mini_*_by_o3_summary.csv (3個) | 127,176 | 77,871 | sentiment_deepseek | o3_summary |

**註**: `sentiment_o4_mini_high_1.csv` 是過濾修復後的版本，只保留有效記錄

### 11.4 標準欄位結構

> **2025-12-29 更新**: 已移除所有 `Unnamed:` 索引欄位
> 詳見 [REPAIR_LOG_COLUMN_CLEANUP_20251229.md](REPAIR_LOG_COLUMN_CLEANUP_20251229.md)

欄位結構因**檔案類型**和**目錄位置**而異：

#### 11.4.1 原始目錄 `/mnt/md0/finrl/` 的欄位結構

**類型 A: 無 LLM 摘要的基礎檔案** (檔名無 `_by_` 後綴)

| 檔案類型 | 欄位數 | 評分欄位 |
|---------|--------|---------|
| Sentiment | 12 | `sentiment_deepseek` |
| Risk | 13 | `sentiment_deepseek`, `risk_deepseek` |

範例: `sentiment_o3_high_4.csv`, `risk_o3_medium_2.csv`

**類型 B: 含 LLM 摘要的檔案** (檔名含 `_by_o3_summary` 或 `_by_gpt-5_*`)

| 檔案類型 | 欄位數 | Summary 欄位 | 評分欄位 |
|---------|--------|-------------|---------|
| Sentiment | 15 | `o3_summary` 或 `gpt_5_summary` | `sentiment_deepseek` |
| Risk | 16 | `o3_summary` 或 `gpt_5_summary` | `sentiment_deepseek`, `risk_deepseek` |

**基本欄位 (所有檔案通用):**

| 欄位 | 類型 | 說明 |
|------|------|------|
| Date | string | YYYY-MM-DD HH:MM:SS UTC |
| Article_title | string | 文章標題 |
| Stock_symbol | string | 股票代號 |
| Url | string | 原始 URL |
| Publisher | string | 發布商 |
| Author | string | 作者 |
| Article | string | 完整文章 (可能為空) |
| Lsa_summary | string | LSA 摘要 |
| Luhn_summary | string | Luhn 摘要 |
| Textrank_summary | string | TextRank 摘要 |
| Lexrank_summary | string | LexRank 摘要 |

**評分與 LLM 欄位 (視檔案類型):**

| 欄位 | 類型 | 存在條件 |
|------|------|---------|
| sentiment_deepseek | int | 所有檔案 |
| risk_deepseek | int | 僅 Risk 檔案 |
| o3_summary / gpt_5_summary | string | 僅含 LLM 摘要的檔案 |
| prompt_tokens | int | 僅含 LLM 摘要的檔案 |
| completion_tokens | int | 僅含 LLM 摘要的檔案 |

#### 11.4.2 Renamed 目錄 `/mnt/md0/finrl/renamed/` 的欄位結構

經過 `rename_score_columns.py` 處理（使用 `df.rename()` **重命名**而非複製），評分欄位改為模型特定名稱：

| 檔案類型 | 評分欄位改名 | `sentiment_deepseek` 欄位 |
|---------|------------|--------------------------|
| Sentiment | `sentiment_deepseek` → `sentiment_o3` / `sentiment_gpt_5` / ... | **不存在** (已重命名) |
| Risk | `risk_deepseek` → `risk_o3` / `risk_gpt_5` / ... | 保留 (來自輸入資料) |

> **重要**: Renamed Sentiment 檔案中的 `sentiment_o3` 等欄位是該模型的評分值，
> 這些檔案**完全沒有** `sentiment_deepseek` 欄位（因為它被重命名了）。

> **注意**: Risk 檔案中的 `sentiment_deepseek` 是輸入檔案中既有的欄位，在風險評分過程中被原樣保留。
> **風險評分腳本不使用情緒分數作為輸入**—它們獨立地對 headline 進行風險評分。
>
> **資料來源追蹤 (2025-12-30 驗證)**:
> - Summary 檔案 input: 原始 HuggingFace 檔案 → `openai_summary.py` 只加 summary 欄位
> - Risk 檔案 input: Summary 檔案 → `score_risk_*.py` 只加 risk 欄位
> - 驗證: 所有 risk 檔案的 `sentiment_deepseek` hash 一致 = 原始 DeepSeek 評分 (126,224 筆)
> - **結論**: 無模型混用，`sentiment_deepseek` 皆為原始 DeepSeek 評分

### 11.5 欄位名稱改名對照

為開源發布準備，評分欄位需要改名以反映實際使用的模型：

| 原欄位名 | 新欄位名 | 適用模型目錄 |
|---------|---------|-------------|
| sentiment_deepseek | sentiment_o3 | o3/ |
| sentiment_deepseek | sentiment_o4_mini | o4-mini/ |
| sentiment_deepseek | sentiment_gpt_5 | gpt-5/ |
| sentiment_deepseek | sentiment_gpt_5_mini | gpt-5-mini/ |
| sentiment_deepseek | sentiment_gpt_4_1 | gpt-4.1/ |
| sentiment_deepseek | sentiment_gpt_4_1_mini | gpt-4.1-mini/ |
| sentiment_deepseek | sentiment_gpt_4_1_nano | gpt-4.1-nano/ |
| risk_deepseek | risk_o3 | o3/ |
| risk_deepseek | risk_o4_mini | o4-mini/ |
| risk_deepseek | risk_gpt_5 | gpt-5/ |
| risk_deepseek | risk_gpt_5_mini | gpt-5-mini/ |
| risk_deepseek | risk_gpt_4_1 | gpt-4.1/ |
| risk_deepseek | risk_gpt_4_1_mini | gpt-4.1-mini/ |
| risk_deepseek | risk_gpt_4_1_nano | gpt-4.1-nano/ |

**注意**: Claude 模型檔案使用模型特定命名 (`sentiment_haiku/opus/sonnet`, `risk_haiku/opus/sonnet`)。

### 11.6 改名工具

改名腳本位置: `scripts/repair/rename_score_columns.py`

```bash
# 預覽改名 (dry-run)
python scripts/repair/rename_score_columns.py --output-dir /mnt/md0/finrl/renamed --dry-run

# 執行改名 (創建到新目錄)
python scripts/repair/rename_score_columns.py --output-dir /mnt/md0/finrl/renamed
```

**改名結果:**
- 52 個 OpenAI 模型檔案會被改名
- 6 個 Claude 模型檔案保持不變
- 原始檔案不會被修改
- 改名版本儲存在 `/mnt/md0/finrl/renamed/`

### 11.7 LLM Summary 來源檔案

LLM 生成的摘要檔案位於各模型的 `summary/` 目錄下。

#### Summary 目錄總覽

| 目錄 | 檔案數 | Summary 欄位名 | 說明 |
|------|--------|---------------|------|
| `o3/summary/` | 1 | `o3_summary` | o3 模型生成 |
| `gpt-5/summary/` | 12 | `gpt_5_summary` | 4 reasoning × 3 verbosity 組合 |
| `gpt-5-mini/summary/` | 12 | `gpt_5_mini_summary` | 4 reasoning × 3 verbosity 組合 |
| `gpt-5.1/summary/` | 1 | `gpt_5.1_summary` | gpt-5.1 模型生成 |
| **合計** | **26** | | |

#### 標準欄位結構 (所有 Summary 檔案通用)

所有 summary 檔案都有 **15 個欄位**，結構完全相同 (僅 summary 欄位名不同)：

> **2025-12-29 更新**: 已移除 `Unnamed: 0.1` 和 `Unnamed: 0` 索引欄位（pandas 讀寫殘留）
> 詳見 [REPAIR_LOG_COLUMN_CLEANUP_20251229.md](REPAIR_LOG_COLUMN_CLEANUP_20251229.md)

| 欄位 | 類型 | 說明 |
|------|------|------|
| Date | string | YYYY-MM-DD |
| Article_title | string | 文章標題 |
| Stock_symbol | string | 股票代號 |
| Url | string | 原始 URL |
| Publisher | string | 發布商 |
| Author | string | 作者 |
| Article | string | 完整文章 |
| Lsa_summary | string | LSA 摘要 |
| Luhn_summary | string | Luhn 摘要 |
| Textrank_summary | string | TextRank 摘要 |
| Lexrank_summary | string | LexRank 摘要 |
| sentiment_deepseek | int | 原始 DeepSeek 情緒評分 |
| **{model}_summary** | string | **LLM 生成的摘要** |
| prompt_tokens | int | API prompt token 數 |
| completion_tokens | int | API completion token 數 |

#### 有效記錄數

| 檔案 | 總行數 | 有效 Summary |
|------|--------|--------------|
| `o3/summary/o3_news_with_summary.csv` | 127,176 | 77,871 |
| `gpt-5/summary/*.csv` (各檔案) | 127,176 | 77,871 |
| `gpt-5-mini/summary/*.csv` (各檔案) | 127,176 | 77,871 |
| `gpt-5.1/summary/*.csv` | 127,176 | 77,871 |

**註**: 只有 77,871 筆有效是因為原始資料中只有 61.2% 的記錄有 Article 內容可供生成摘要。

#### 各目錄檔案清單

**o3/summary/** (1 個檔案)
```
o3_news_with_summary.csv
```

**gpt-5/summary/** (12 個檔案)
```
gpt-5_reason_{R}_verbosity_{V}_news_with_summary.csv

R = minimal | low | medium | high
V = low | medium | high
```

**gpt-5-mini/summary/** (12 個檔案)
```
gpt-5-mini_reason_{R}_verbosity_{V}_news_with_summary.csv

R = minimal | low | medium | high
V = low | medium | high
```

**gpt-5.1/summary/** (1 個檔案)
```
gpt-5.1_reason_high_verbosity_high_news_with_summary.csv
```

#### 評分檔案中的 Summary 欄位使用

評分檔案使用上述 summary 檔案作為輸入來源：

| 評分檔案使用的欄位 | 檔案數 | 來源 |
|------------------|--------|------|
| `o3_summary` | 26 | 從 `o3/summary/` 合併 |
| `gpt_5_summary` | 28 | 從 `gpt-5/summary/` 合併 |
| (無 LLM summary) | 4 | 早期檔案，使用 `Lsa_summary` |

**註**: `Lsa_summary` 是傳統演算法 (LSA) 生成的摘要，存在於所有檔案中但只有 77,871 筆有效記錄。

### 11.8 無效分數 (Score = 0) 檢查

> **檢查日期**: 2026-01-04

#### 11.8.1 檢查結果摘要

| 來源 | 類型 | 檔案數 | 無效分數 | 總數 | 比例 |
|------|------|--------|---------|------|------|
| **原始 DeepSeek** | sentiment | - | **228** | 126,224 | 0.18% |
| o3 | sentiment | 5 | 0 | 77,871 | 0% |
| o4-mini | sentiment | 4 | 0 | 77,871 | 0% |
| gpt-5 | sentiment | 8 | 0 | 77,871 | 0% |
| gpt-5-mini | sentiment | 1 | 0 | 77,871 | 0% |
| gpt-4.1 | sentiment | 1 | 0 | 77,871 | 0% |
| gpt-4.1-mini | sentiment | 6 | 0 | 77,871 | 0% |
| gpt-4.1-nano | sentiment | 1 | 0 | 77,871 | 0% |
| Claude (haiku/sonnet/opus) | sentiment | 3 | 0 | 77,871 | 0% |
| 所有模型 | risk | 全部 | 0 | - | 0% |

#### 11.8.2 無效分數詳情

**原始 DeepSeek 評分** (`sentiment_deepseek` in summary files):
- 位置: `/mnt/md0/finrl/*/summary/*.csv` 和 `claude/finrl_claude_all_scores.csv`
- 無效分數: 228 筆 (分數 = 0，應為 1-5)
- 影響: 僅影響原始 DeepSeek 評分，不影響後續 LLM 模型評分

**所有 LLM 模型評分**:
- ✅ OpenAI 系列 (o3, o4-mini, gpt-5, gpt-4.1 等): 無無效分數
- ✅ Claude 系列 (haiku, sonnet, opus): 無無效分數
- ✅ 所有 risk 評分: 無無效分數

#### 11.8.3 finrl_claude_all_scores.csv 結構說明

此檔案 (`/mnt/md0/finrl/claude/finrl_claude_all_scores.csv`) 包含:

| 欄位 | 來源 | 有效數 | 無效分數 |
|------|------|--------|---------|
| `sentiment_deepseek` | 原始 DeepSeek | 126,224 | 228 |
| `sentiment_haiku` | Claude Haiku | 77,871 | 0 |
| `sentiment_sonnet` | Claude Sonnet | 77,871 | 0 |
| `sentiment_opus` | Claude Opus | 77,871 | 0 |
| `risk_haiku` | Claude Haiku | 77,871 | 0 |
| `risk_sonnet` | Claude Sonnet | 77,871 | 0 |
| `risk_opus` | Claude Opus | 77,871 | 0 |

**註**: 此檔案用於 **DeepSeek vs Claude** 比較，非 OpenAI vs Claude。

---

