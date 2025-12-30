# 欄位清理修復記錄 (2025-12-29)

## 問題背景

### 問題成因

1. **錯誤新增的模型特定欄位**
   - `rename_score_columns.py` 腳本的設計是將 `sentiment_deepseek` → `sentiment_o3` 等，並輸出到 `/mnt/md0/finrl/renamed/` 目錄
   - 但某個早期版本的腳本錯誤地在**原始目錄** (`/mnt/md0/finrl/`) 中新增了模型特定欄位
   - 導致原始檔案同時存在 `sentiment_deepseek` 和 `sentiment_o3` 兩個重複欄位

2. **Unnamed 欄位殘留**
   - `Unnamed: 0` 和 `Unnamed: 0.1` 是 pandas 在讀取 CSV 時自動生成的索引欄位
   - 當使用 `df.to_csv(index=True)` 或多次讀寫時會累積這些欄位
   - 這些欄位**沒有任何用途**，純粹是 pandas 處理的副作用

---

## Phase 1: 刪除原始目錄中錯誤新增的模型特定欄位

**問題描述**: 原始目錄的 `*_by_o3_summary.csv` 檔案被錯誤地新增了 `sentiment_o3`, `risk_o3` 等欄位

**修復時間**: 2025-12-29

**修復數量**: 26 個檔案

### 詳細清單

| 目錄 | 檔案 | 刪除的欄位 |
|------|------|-----------|
| o3/sentiment/ | sentiment_o3_high_by_o3_summary.csv | `sentiment_o3` |
| o3/sentiment/ | sentiment_o3_medium_by_o3_summary.csv | `sentiment_o3` |
| o3/sentiment/ | sentiment_o3_low_by_o3_summary.csv | `sentiment_o3` |
| o3/risk/ | risk_o3_high_by_o3_summary.csv | `risk_o3` |
| o3/risk/ | risk_o3_medium_by_o3_summary.csv | `risk_o3` |
| o3/risk/ | risk_o3_low_by_o3_summary.csv | `risk_o3` |
| o4-mini/sentiment/ | sentiment_o4_mini_high_by_o3_summary.csv | `sentiment_o4_mini` |
| o4-mini/sentiment/ | sentiment_o4_mini_medium_by_o3_summary.csv | `sentiment_o4_mini` |
| o4-mini/sentiment/ | sentiment_o4_mini_low_by_o3_summary.csv | `sentiment_o4_mini` |
| o4-mini/risk/ | risk_o4_mini_high_by_o3_summary.csv | `risk_o4_mini` |
| o4-mini/risk/ | risk_o4_mini_medium_by_o3_summary.csv | `risk_o4_mini` |
| o4-mini/risk/ | risk_o4_mini_low_by_o3_summary.csv | `risk_o4_mini` |
| gpt-5/sentiment/ | sentiment_gpt-5_high_by_o3_summary.csv | `sentiment_gpt_5` |
| gpt-5/sentiment/ | sentiment_gpt-5_medium_by_o3_summary.csv | `sentiment_gpt_5` |
| gpt-5/sentiment/ | sentiment_gpt-5_low_by_o3_summary.csv | `sentiment_gpt_5` |
| gpt-5/sentiment/ | sentiment_gpt-5_minimal_by_o3_summary.csv | `sentiment_gpt_5` |
| gpt-5/risk/ | risk_gpt-5_high_by_o3_summary.csv | `risk_gpt_5` |
| gpt-5/risk/ | risk_gpt-5_medium_by_o3_summary.csv | `risk_gpt_5` |
| gpt-5/risk/ | risk_gpt-5_low_by_o3_summary.csv | `risk_gpt_5` |
| gpt-5/risk/ | risk_gpt-5_minimal_by_o3_summary.csv | `risk_gpt_5` |
| gpt-4.1/sentiment/ | sentiment_gpt-4.1_by_o3_summary.csv | `sentiment_gpt_4.1` |
| gpt-4.1/risk/ | risk_gpt-4.1_by_o3_summary.csv | `risk_gpt_4.1` |
| gpt-4.1-mini/sentiment/ | sentiment_gpt-4.1-mini_by_o3_summary.csv | `sentiment_gpt_4.1_mini` |
| gpt-4.1-mini/risk/ | risk_gpt-4.1-mini_by_o3_summary.csv | `risk_gpt_4.1_mini` |
| gpt-4.1-nano/sentiment/ | sentiment_gpt-4.1-nano_by_o3_summary.csv | `sentiment_gpt_4.1_nano` |
| gpt-4.1-nano/risk/ | risk_gpt-4.1-nano_by_o3_summary.csv | `risk_gpt_4.1_nano` |

---

## Phase 2: 刪除 Unnamed 欄位 (主要評分目錄)

**問題描述**: pandas 讀寫過程中產生的索引欄位殘留

**修復時間**: 2025-12-29

**修復數量**: 50 個檔案

### 詳細清單

| 目錄 | 檔案 | 刪除的欄位 |
|------|------|-----------|
| o3/sentiment/ | sentiment_o3_high_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o3/sentiment/ | sentiment_o3_high_4.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o3/sentiment/ | sentiment_o3_medium_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o3/sentiment/ | sentiment_o3_low_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o3/sentiment/ | sentiment_o3_high_by_gpt-5_reason_high_verbosity_high.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o3/risk/ | risk_o3_medium_2.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o3/risk/ | risk_o3_low_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o3/risk/ | risk_o3_high_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o3/risk/ | risk_o3_high_by_gpt-5_reason_high_verbosity_high.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o3/risk/ | risk_o3_medium_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o4-mini/sentiment/ | sentiment_o4_mini_medium_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o4-mini/sentiment/ | sentiment_o4_mini_high_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o4-mini/sentiment/ | sentiment_o4_mini_low_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o4-mini/sentiment/ | sentiment_o4_mini_high_1.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o4-mini/risk/ | risk_o4_mini_medium_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o4-mini/risk/ | risk_o4_mini_low_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o4-mini/risk/ | risk_o4_mini_high_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o4-mini/risk/ | risk_o4_mini_medium_2.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/sentiment/ | sentiment_gpt-5_low_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/sentiment/ | sentiment_gpt-5_minimal_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/sentiment/ | sentiment_gpt-5_high_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/sentiment/ | sentiment_gpt-5_R_minimal_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/sentiment/ | sentiment_gpt-5_medium_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/sentiment/ | sentiment_gpt-5_R_high_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/sentiment/ | sentiment_gpt-5_R_low_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/sentiment/ | sentiment_gpt-5_R_medium_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/risk/ | risk_gpt-5_R_medium_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/risk/ | risk_gpt-5_high_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/risk/ | risk_gpt-5_minimal_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/risk/ | risk_gpt-5_low_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/risk/ | risk_gpt-5_medium_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/risk/ | risk_gpt-5_R_low_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/risk/ | risk_gpt-5_R_minimal_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/risk/ | risk_gpt-5_R_high_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-4.1/sentiment/ | sentiment_gpt-4.1_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-4.1/risk/ | risk_gpt-4.1_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-4.1-mini/sentiment/ | sentiment_gpt-4.1-mini_by_gpt-5_reason_high_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-4.1-mini/sentiment/ | sentiment_gpt-4.1-mini_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-4.1-mini/sentiment/ | sentiment_gpt-4.1-mini_by_gpt-5_reason_minimal_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-4.1-mini/sentiment/ | sentiment_gpt-4.1-mini_by_gpt-5_reason_high_verbosity_medium_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-4.1-mini/sentiment/ | sentiment_gpt-4.1-mini_by_gpt-5_reason_low_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-4.1-mini/sentiment/ | sentiment_gpt-4.1-mini_by_gpt-5_reason_medium_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-4.1-mini/risk/ | risk_gpt-4.1-mini_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-4.1-mini/risk/ | risk_gpt-4.1-mini_by_gpt-5_reason_medium_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-4.1-mini/risk/ | risk_gpt-4.1-mini_by_gpt-5_reason_high_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-4.1-mini/risk/ | risk_gpt-4.1-mini_by_gpt-5_reason_minimal_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-4.1-mini/risk/ | risk_gpt-4.1-mini_by_gpt-5_reason_high_verbosity_medium_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-4.1-mini/risk/ | risk_gpt-4.1-mini_by_gpt-5_reason_low_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-4.1-nano/sentiment/ | sentiment_gpt-4.1-nano_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-4.1-nano/risk/ | risk_gpt-4.1-nano_by_o3_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |

---

## Phase 3: 清理 gpt-5-mini 和 claude 目錄

**問題描述**: 這些目錄在 Phase 2 時被遺漏

**修復時間**: 2025-12-29

**修復數量**: 8 個檔案

### 詳細清單

| 目錄 | 檔案 | 刪除的欄位 |
|------|------|-----------|
| gpt-5-mini/sentiment/ | sentiment_gpt-5-mini_with_R_high_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5-mini/risk/ | risk_gpt-5-mini_with_R_high_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| claude/sentiment/ | sentiment_sonnet_by_gpt5_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| claude/sentiment/ | sentiment_haiku_by_gpt5_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| claude/sentiment/ | sentiment_opus_by_gpt5_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| claude/risk/ | risk_sonnet_by_gpt5_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| claude/risk/ | risk_opus_by_gpt5_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| claude/risk/ | risk_haiku_by_gpt5_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |

---

## Phase 4: 清理 summary 目錄

**問題描述**: summary 檔案也有 Unnamed 欄位殘留

**修復時間**: 2025-12-29

**修復數量**: 26 個檔案

> ⚠️ **錯誤記錄**: 備份檔案 `backups/repair_20251227/o3/summary/o3_news_with_summary.csv`
> 在此階段被錯誤修改。備份目錄不應該被清理，此修改違反了保留原始狀態的原則。

### 詳細清單

| 目錄 | 檔案 | 刪除的欄位 |
|------|------|-----------|
| gpt-5.1/summary/ | gpt-5.1_reason_high_verbosity_high_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/summary/ | gpt-5_reason_low_verbosity_medium_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/summary/ | gpt-5_reason_low_verbosity_low_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/summary/ | gpt-5_reason_low_verbosity_high_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/summary/ | gpt-5_reason_minimal_verbosity_high_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/summary/ | gpt-5_reason_high_verbosity_high_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/summary/ | gpt-5_reason_minimal_verbosity_medium_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/summary/ | gpt-5_reason_high_verbosity_medium_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/summary/ | gpt-5_reason_medium_verbosity_high_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/summary/ | gpt-5_reason_medium_verbosity_medium_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/summary/ | gpt-5_reason_high_verbosity_low_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/summary/ | gpt-5_reason_minimal_verbosity_low_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5/summary/ | gpt-5_reason_medium_verbosity_low_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5-mini/summary/ | gpt-5-mini_reason_low_verbosity_high_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5-mini/summary/ | gpt-5-mini_reason_medium_verbosity_high_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5-mini/summary/ | gpt-5-mini_reason_high_verbosity_high_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5-mini/summary/ | gpt-5-mini_reason_minimal_verbosity_high_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5-mini/summary/ | gpt-5-mini_reason_medium_verbosity_low_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5-mini/summary/ | gpt-5-mini_reason_high_verbosity_medium_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5-mini/summary/ | gpt-5-mini_reason_low_verbosity_low_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5-mini/summary/ | gpt-5-mini_reason_minimal_verbosity_low_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5-mini/summary/ | gpt-5-mini_reason_low_verbosity_medium_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5-mini/summary/ | gpt-5-mini_reason_medium_verbosity_medium_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5-mini/summary/ | gpt-5-mini_reason_high_verbosity_low_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| gpt-5-mini/summary/ | gpt-5-mini_reason_minimal_verbosity_medium_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
| o3/summary/ | o3_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |

---

## 修復後欄位結構

欄位結構因檔案類型和目錄位置而異。以下分類說明：

---

### 原始目錄 `/mnt/md0/finrl/` 的欄位結構

#### 類型 A: 無 LLM 摘要的基礎檔案

檔名特徵: `sentiment_o3_high_4.csv`, `risk_o3_medium_2.csv` (無 `_by_` 後綴)

**Sentiment 檔案 (12 欄):**
```
Date, Article_title, Stock_symbol, Url, Publisher, Author, Article,
Lsa_summary, Luhn_summary, Textrank_summary, Lexrank_summary,
sentiment_deepseek
```

**Risk 檔案 (13 欄):** 同上 + `risk_deepseek`

#### 類型 B: 含 o3_summary 的檔案

檔名特徵: `*_by_o3_summary.csv`

**Sentiment 檔案 (15 欄):**
```
Date, Article_title, Stock_symbol, Url, Publisher, Author, Article,
Lsa_summary, Luhn_summary, Textrank_summary, Lexrank_summary,
sentiment_deepseek, o3_summary, prompt_tokens, completion_tokens
```

**Risk 檔案 (16 欄):** 同上 + `risk_deepseek` (在最後)

#### 類型 C: 含 gpt_5_summary 的檔案

檔名特徵: `*_by_gpt-5_*` 或 `*_by_gpt5_summary.csv`

**Sentiment 檔案 (15 欄):**
```
Date, Article_title, Stock_symbol, Url, Publisher, Author, Article,
Lsa_summary, Luhn_summary, Textrank_summary, Lexrank_summary,
sentiment_deepseek, gpt_5_summary, prompt_tokens, completion_tokens
```

**Risk 檔案 (16 欄):** 同上 + `risk_deepseek` (在最後)

---

### Renamed 目錄 `/mnt/md0/finrl/renamed/` 的欄位結構

此目錄的檔案經過 `rename_score_columns.py` 處理，評分欄位已改名為模型特定名稱。

#### Sentiment 檔案

| 原始欄位 | 改名後欄位 | 適用模型 |
|---------|-----------|---------|
| `sentiment_deepseek` | `sentiment_o3` | o3 |
| `sentiment_deepseek` | `sentiment_o4_mini` | o4-mini |
| `sentiment_deepseek` | `sentiment_gpt_5` | gpt-5 |
| `sentiment_deepseek` | `sentiment_gpt_4_1` | gpt-4.1 |
| `sentiment_deepseek` | `sentiment_gpt_4_1_mini` | gpt-4.1-mini |
| `sentiment_deepseek` | `sentiment_gpt_4_1_nano` | gpt-4.1-nano |

範例 (o3 sentiment):
```
Date, Article_title, Stock_symbol, Url, Publisher, Author, Article,
Lsa_summary, Luhn_summary, Textrank_summary, Lexrank_summary,
sentiment_o3, o3_summary, prompt_tokens, completion_tokens
```

#### Risk 檔案

Risk 檔案同時保留原始的 `sentiment_deepseek`（來自基礎資料集），並將 `risk_deepseek` 改名為模型特定名稱：

範例 (o3 risk):
```
Date, Article_title, Stock_symbol, Url, Publisher, Author, Article,
Lsa_summary, Luhn_summary, Textrank_summary, Lexrank_summary,
sentiment_deepseek, o3_summary, prompt_tokens, completion_tokens, risk_o3
```

> **注意**: Risk 檔案中的 `sentiment_deepseek` 是輸入檔案中既有的欄位，
> 在風險評分過程中被原樣保留。**風險評分腳本 (`score_risk_openai.py`, `score_risk_anthropic.py`)
> 不使用情緒分數作為輸入**—它們獨立地對 headline 進行風險評分。
>
> **資料來源追蹤 (2025-12-30 驗證)**:
> - Summary 檔案的 input 全部是原始 HuggingFace 檔案 (`sentiment_deepseek_new_cleaned_nasdaq_news_full.csv`)
> - Risk 檔案的 input 是 Summary 檔案，`openai_summary.py` 只新增 summary 欄位，其他欄位原樣保留
> - 經驗證所有 risk 檔案的 `sentiment_deepseek` hash 一致，皆為原始 DeepSeek 評分 (126,224 筆)
> - **結論**: 無模型混用問題，所有 `sentiment_deepseek` 都是原始 DeepSeek 模型的評分

---

### Summary 目錄的欄位結構

Summary 檔案只包含 LLM 生成的摘要，不包含評分欄位。

**15 欄:**
```
Date, Article_title, Stock_symbol, Url, Publisher, Author, Article,
Lsa_summary, Luhn_summary, Textrank_summary, Lexrank_summary,
sentiment_deepseek, [o3_summary|gpt_5_summary], prompt_tokens, completion_tokens
```

> **注意**: Summary 檔案中的 `sentiment_deepseek` 是原始基礎資料的情緒分數，
> 不是 LLM 重新評分的結果。

---

### 備份目錄 `/mnt/md0/finrl/backups/`

- ⚠️ **錯誤**: `backups/repair_20251227/o3/summary/o3_news_with_summary.csv` 在 Phase 4 被錯誤修改
- 該檔案的 `Unnamed: 0.1` 和 `Unnamed: 0` 欄位已被移除（不應該被修改）
- 備份目錄應保留原始狀態，此錯誤導致無法從備份還原原始欄位結構

---

## 總結

| Phase | 修復內容 | 檔案數 |
|-------|---------|--------|
| Phase 1 | 刪除錯誤新增的模型特定欄位 | 26 |
| Phase 2 | 刪除主要評分目錄的 Unnamed 欄位 | 50 |
| Phase 3 | 清理 gpt-5-mini 和 claude 目錄 | 8 |
| Phase 4 | 清理 summary 目錄 | 26 (原誤報 27) |
| **總計** | | **110** |

> **錯誤記錄**: Phase 4 原報告 27 個檔案，實際應為 26 個。
> 備份檔案 `backups/repair_20251227/o3/summary/o3_news_with_summary.csv` 不應被計入。

**最終狀態**: 142 個工作目錄 CSV 檔案已清理完成

---

*建立日期: 2025-12-29*
*更新日期: 2025-12-30 (修正備份錯誤記錄、嚴謹化欄位結構描述)*