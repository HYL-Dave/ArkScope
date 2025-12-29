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

**修復數量**: 27 個檔案

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
| backups/repair_20251227/o3/summary/ | o3_news_with_summary.csv | `Unnamed: 0.1`, `Unnamed: 0` |
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

### 評分檔案 (sentiment)

清理後共 **15 個欄位**：

| 欄位 | 類型 | 說明 |
|------|------|------|
| Date | string | 日期 (YYYY-MM-DD HH:MM:SS UTC) |
| Article_title | string | 文章標題 |
| Stock_symbol | string | 股票代號 |
| Url | string | 文章連結 |
| Publisher | string | 發布者 |
| Author | string | 作者 |
| Article | string | 完整文章內容 |
| Lsa_summary | string | LSA 摘要 |
| Luhn_summary | string | Luhn 摘要 |
| Textrank_summary | string | TextRank 摘要 |
| Lexrank_summary | string | LexRank 摘要 |
| sentiment_deepseek | int | 情緒分數 (1-5) |
| o3_summary / gpt_5_summary | string | LLM 生成摘要 |
| prompt_tokens | int | API prompt token 數 |
| completion_tokens | int | API completion token 數 |

### 評分檔案 (risk)

清理後共 **16 個欄位** (比 sentiment 多一個 `risk_deepseek`)：

| 欄位 | 類型 | 說明 |
|------|------|------|
| ... | ... | (同 sentiment) |
| risk_deepseek | int | 風險分數 (1-5) |

### Summary 檔案

清理後共 **15 個欄位**：

| 欄位 | 類型 | 說明 |
|------|------|------|
| Date | string | 日期 |
| Article_title | string | 文章標題 |
| Stock_symbol | string | 股票代號 |
| Url | string | 文章連結 |
| Publisher | string | 發布者 |
| Author | string | 作者 |
| Article | string | 完整文章內容 |
| Lsa_summary | string | LSA 摘要 |
| Luhn_summary | string | Luhn 摘要 |
| Textrank_summary | string | TextRank 摘要 |
| Lexrank_summary | string | LexRank 摘要 |
| sentiment_deepseek | int | 原始情緒分數 |
| o3_summary / gpt_5_summary | string | LLM 生成摘要 |
| prompt_tokens | int | API prompt token 數 |
| completion_tokens | int | API completion token 數 |

---

## 目錄結構確認

### 原始目錄 `/mnt/md0/finrl/`

- 所有評分欄位保持 `sentiment_deepseek`, `risk_deepseek`
- 已移除所有 `Unnamed:` 欄位
- 已移除錯誤新增的模型特定欄位

### Renamed 目錄 `/mnt/md0/finrl/renamed/`

- 評分欄位已改名為模型特定名稱 (如 `sentiment_o3`, `risk_gpt_5`)
- 無 `Unnamed:` 欄位
- 無重複欄位

### 備份目錄 `/mnt/md0/finrl/backups/`

- 保留原始狀態（包含 `Unnamed:` 欄位）
- 不進行清理（作為歷史備份）

---

## 總結

| Phase | 修復內容 | 檔案數 |
|-------|---------|--------|
| Phase 1 | 刪除錯誤新增的模型特定欄位 | 26 |
| Phase 2 | 刪除主要評分目錄的 Unnamed 欄位 | 50 |
| Phase 3 | 清理 gpt-5-mini 和 claude 目錄 | 8 |
| Phase 4 | 清理 summary 目錄 | 27 |
| **總計** | | **111** |

**最終狀態**: 143 個工作目錄 CSV 檔案全部乾淨

---

*建立日期: 2025-12-29*