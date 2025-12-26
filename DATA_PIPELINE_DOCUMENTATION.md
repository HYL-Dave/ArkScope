# /mnt/md0/finrl 資料處理流程文檔

本文檔記錄 FinRL 新聞情緒/風險評分實驗的完整資料處理流程。

## 目錄

- [1. 源頭資料](#1-源頭資料)
- [2. Summary 生成管道](#2-summary-生成管道)
- [3. Risk/Sentiment 評分管道](#3-risksentiment-評分管道)
- [4. 檔案命名規則](#4-檔案命名規則)
- [5. 實驗設計矩陣](#5-實驗設計矩陣)
- [6. 目錄結構](#6-目錄結構)

---

## 1. 源頭資料

### 1.1 HuggingFace 資料集

| 來源 | Repo ID | 本地路徑 | 說明 |
|------|---------|----------|------|
| FNSPID | `Zihan1004/FNSPID` | `huggingface_datasets/FNSPID_raw_news/` | 原始新聞 + 股價資料 |
| DeepSeek Sentiment | `benstaf/nasdaq_news_sentiment` | `huggingface_datasets/FinRL_DeepSeek_sentiment/` | 已標註情緒的新聞 |
| DeepSeek Risk | `benstaf/risk_nasdaq` | `huggingface_datasets/FinRL_DeepSeek_risk/` | 已標註風險的新聞 |

### 1.2 主要資料檔案

| 檔案 | 行數 | 大小 | 關鍵欄位 |
|------|------|------|----------|
| `sentiment_deepseek_new_cleaned_nasdaq_news_full.csv` | 2,092,986 | 562M | Lsa_summary, sentiment_deepseek |
| `risk_deepseek_cleaned_nasdaq_news_full.csv` | 2,092,986 | 562M | Lsa_summary, risk_deepseek |

### 1.3 下載方式

```bash
python download.py
```

使用 `huggingface_hub.snapshot_download()` 下載。

---

## 2. Summary 生成管道

使用 `openai_summary.py` 腳本，將原始新聞文本生成精簡摘要。

### 2.1 o3 Summary

```bash
python openai_summary.py \
  --input huggingface_datasets/FinRL_DeepSeek_sentiment/sentiment_deepseek_new_cleaned_nasdaq_news_full.csv \
  --output o3/summary/o3_news_with_summary.csv \
  --model o3 \
  --chunk-size 10 \
  --allow-flex --flex-timeout 1000 --flex-retries 5
```

- **輸出欄位**: `o3_summary`
- **行數**: 2,092,943 (略少於原始，因部分失敗)

### 2.2 gpt-5 Summary (12 種配置)

```bash
python openai_summary.py \
  --input huggingface_datasets/FinRL_DeepSeek_sentiment/sentiment_deepseek_new_cleaned_nasdaq_news_full.csv \
  --output gpt-5/summary/gpt-5_reason_{REASONING}_verbosity_{VERBOSITY}_news_with_summary.csv \
  --model gpt-5 \
  --reasoning-effort {minimal|low|medium|high} \
  --verbosity {low|medium|high} \
  --allow-flex
```

- **輸出欄位**: `gpt_5_summary`
- **配置矩陣**: 4 reasoning × 3 verbosity = 12 種組合

| Reasoning | Verbosity Low | Verbosity Medium | Verbosity High |
|-----------|---------------|------------------|----------------|
| minimal | 601M | 607M | 611M |
| low | 602M | 609M | 613M |
| medium | 602M | 610M | 615M |
| high | 601M | 610M | **616M** ★主要使用 |

### 2.3 gpt-5-mini Summary

與 gpt-5 相同的 12 種配置，輸出到 `gpt-5-mini/summary/`。

### 2.4 gpt-5.1 Summary

```bash
python openai_summary.py \
  --model gpt-5.1 \
  --reasoning-effort high \
  --verbosity high \
  --output gpt-5.1/summary/gpt-5.1_reason_high_verbosity_high_news_with_summary.csv
```

---

## 3. Risk/Sentiment 評分管道

### 3.1 OpenAI 模型評分

使用 `score_risk_openai.py` 和 `score_sentiment_openai.py`。

#### 使用 o3_summary 評分

```bash
python score_{risk|sentiment}_openai.py \
  --input o3/summary/o3_news_with_summary.csv \
  --output {MODEL}/{risk|sentiment}/{task}_{MODEL}_by_o3_summary.csv \
  --model {MODEL} \
  --text-column o3_summary \
  --reasoning-effort {minimal|low|medium|high}
```

#### 使用 gpt_5_summary 評分

```bash
python score_{risk|sentiment}_openai.py \
  --input gpt-5/summary/gpt-5_reason_{R}_verbosity_{V}_news_with_summary.csv \
  --output {MODEL}/{risk|sentiment}/{task}_{MODEL}_by_gpt-5_reason_{R}_verbosity_{V}_summary.csv \
  --model {MODEL} \
  --text-column gpt_5_summary
```

### 3.2 Claude 模型評分 (Anthropic API)

使用 `score_risk_anthropic.py` 和 `score_sentiment_anthropic.py`。

```bash
python score_{risk|sentiment}_anthropic.py \
  --input gpt-5/summary/gpt-5_reason_high_verbosity_high_news_with_summary.csv \
  --output claude/{risk|sentiment}/{task}_{haiku|sonnet|opus}_by_gpt5_summary.csv \
  --batch \
  --model {haiku|sonnet|opus} \
  --text-column gpt_5_summary
```

---

## 4. 檔案命名規則

### 4.1 命名格式

```
{task}_{model}_{reasoning}_by_{summary_source}.csv
```

- **task**: `risk` 或 `sentiment`
- **model**: 評分模型 (o3, o4-mini, gpt-4.1, gpt-5, etc.)
- **reasoning**: reasoning effort level (可選)
- **summary_source**: 輸入文本來源

### 4.2 編號檔案 (早期實驗)

早期實驗直接使用原版 `Lsa_summary`，產出編號檔案。後來手動改名以標記 reasoning level：

| 原始檔名 | 改名後 | Reasoning | 輸入源 |
|----------|--------|-----------|--------|
| `sentiment_o4_mini_1.csv` | `sentiment_o4_mini_high_1.csv` | high | DeepSeek_sentiment (Lsa_summary) |
| `risk_o4_mini_2.csv` | `risk_o4_mini_medium_2.csv` | medium | DeepSeek_risk (Lsa_summary) |
| `risk_o3_2.csv` | `risk_o3_medium_2.csv` | medium | DeepSeek_risk (Lsa_summary) |
| `sentiment_o3_high_4.csv` | (未改名) | high | DeepSeek_sentiment (Lsa_summary) |

### 4.3 腳本預設值演進

| 時期 | 預設 reasoning-effort |
|------|----------------------|
| 早期 | medium |
| 後期 | high |

---

## 5. 實驗設計矩陣

### 5.1 關鍵變因

| 變因 | 選項 |
|------|------|
| **評分模型** | o3, o4-mini, gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-5, gpt-5-mini, gpt-5.1, claude-haiku/sonnet/opus |
| **輸入源** | ① 原版 Lsa_summary ② o3_summary ③ gpt_5_summary (12種配置) |
| **Reasoning effort** | minimal, low, medium, high |
| **任務類型** | sentiment, risk |
| **Summary verbosity** | low, medium, high (僅 gpt-5 summary 生成時) |

### 5.2 完整實驗矩陣

```
                        ┌─────────────────────────────────────────────────────┐
                        │                 輸入文本來源                         │
                        ├──────────────┬──────────────┬───────────────────────┤
                        │ Lsa_summary  │ o3_summary   │ gpt_5_summary         │
                        │ (原版)       │ (自製)       │ (自製,12配置)         │
┌───────────────────────┼──────────────┼──────────────┼───────────────────────┤
│ o3                    │ high_4,      │ ✓ min/low/   │ high_by_gpt-5         │
│ (min/low/med/high)    │ medium_2     │   med/high   │ _reason_high_verb_high│
├───────────────────────┼──────────────┼──────────────┼───────────────────────┤
│ o4-mini               │ high_1,      │ ✓ low/med/   │                       │
│ (low/med/high)        │ medium_2     │   high       │                       │
├───────────────────────┼──────────────┼──────────────┼───────────────────────┤
│ gpt-4.1               │              │ ✓            │                       │
├───────────────────────┼──────────────┼──────────────┼───────────────────────┤
│ gpt-4.1-mini          │              │ ✓            │ ✓ 多種 R×V 配置       │
├───────────────────────┼──────────────┼──────────────┼───────────────────────┤
│ gpt-4.1-nano          │              │ ✓            │                       │
├───────────────────────┼──────────────┼──────────────┼───────────────────────┤
│ gpt-5                 │              │ ✓ min/low/   │ ✓ R_{min/low/med/high}│
│ (min/low/med/high)    │              │   med/high   │   _V_low              │
├───────────────────────┼──────────────┼──────────────┼───────────────────────┤
│ gpt-5-mini            │              │              │ ✓ R_high_V_low        │
├───────────────────────┼──────────────┼──────────────┼───────────────────────┤
│ claude-haiku          │              │              │ ✓ (high_high only)    │
│ claude-sonnet         │              │              │ ✓ (high_high only)    │
│ claude-opus           │              │              │ ✓ (high_high only)    │
└───────────────────────┴──────────────┴──────────────┴───────────────────────┘
```

---

## 6. 目錄結構

```
/mnt/md0/finrl/
├── download.py                          # HuggingFace 資料集下載腳本
├── DATA_PIPELINE_DOCUMENTATION.md       # 本文檔
│
├── huggingface_datasets/                # 源頭資料
│   ├── FNSPID_raw_news/
│   │   ├── Stock_news/                  # 原始新聞
│   │   └── Stock_price/                 # 股價資料
│   ├── FinRL_DeepSeek_sentiment/
│   │   ├── sentiment_deepseek_new_cleaned_nasdaq_news_full.csv
│   │   └── sentiment_llama_cleaned_nasdaq_news_full.csv
│   └── FinRL_DeepSeek_risk/
│       ├── risk_deepseek_cleaned_nasdaq_news_full.csv
│       └── risk_llama_cleaned_nasdaq_news_full.csv
│
├── o3/
│   ├── summary/
│   │   └── o3_news_with_summary.csv     # o3 生成的摘要
│   ├── risk/
│   │   ├── risk_o3_medium_2.csv         # 原版 Lsa, reasoning=medium
│   │   ├── risk_o3_low_by_o3_summary.csv
│   │   ├── risk_o3_medium_by_o3_summary.csv
│   │   ├── risk_o3_high_by_o3_summary.csv
│   │   └── risk_o3_high_by_gpt-5_reason_high_verbosity_high.csv
│   └── sentiment/
│       ├── sentiment_o3_high_4.csv      # 原版 Lsa, reasoning=high
│       ├── sentiment_o3_low_by_o3_summary.csv
│       ├── sentiment_o3_medium_by_o3_summary.csv
│       ├── sentiment_o3_high_by_o3_summary.csv
│       └── sentiment_o3_high_by_gpt-5_reason_high_verbosity_high.csv
│
├── o4-mini/
│   ├── risk/
│   │   ├── risk_o4_mini_medium_2.csv    # 原版 Lsa, reasoning=medium
│   │   ├── risk_o4_mini_low_by_o3_summary.csv
│   │   ├── risk_o4_mini_medium_by_o3_summary.csv
│   │   └── risk_o4_mini_high_by_o3_summary.csv
│   └── sentiment/
│       ├── sentiment_o4_mini_high_1.csv # 原版 Lsa, reasoning=high
│       ├── sentiment_o4_mini_low_by_o3_summary.csv
│       ├── sentiment_o4_mini_medium_by_o3_summary.csv
│       └── sentiment_o4_mini_high_by_o3_summary.csv
│
├── gpt-4.1/
│   ├── risk/
│   │   └── risk_gpt-4.1_by_o3_summary.csv
│   └── sentiment/
│       └── sentiment_gpt-4.1_by_o3_summary.csv
│
├── gpt-4.1-mini/
│   ├── risk/
│   │   ├── risk_gpt-4.1-mini_by_o3_summary.csv
│   │   ├── risk_gpt-4.1-mini_by_gpt-5_reason_minimal_verbosity_high_summary.csv
│   │   ├── risk_gpt-4.1-mini_by_gpt-5_reason_low_verbosity_high_summary.csv
│   │   ├── risk_gpt-4.1-mini_by_gpt-5_reason_medium_verbosity_high_summary.csv
│   │   ├── risk_gpt-4.1-mini_by_gpt-5_reason_high_verbosity_high_summary.csv
│   │   └── risk_gpt-4.1-mini_by_gpt-5_reason_high_verbosity_medium_summary.csv
│   └── sentiment/
│       └── (同上結構)
│
├── gpt-4.1-nano/
│   ├── risk/
│   │   └── risk_gpt-4.1-nano_by_o3_summary.csv
│   └── sentiment/
│       └── sentiment_gpt-4.1-nano_by_o3_summary.csv
│
├── gpt-5/
│   ├── summary/                         # 12 種 reasoning×verbosity 配置
│   │   ├── gpt-5_reason_minimal_verbosity_low_news_with_summary.csv
│   │   ├── gpt-5_reason_minimal_verbosity_medium_news_with_summary.csv
│   │   ├── gpt-5_reason_minimal_verbosity_high_news_with_summary.csv
│   │   ├── gpt-5_reason_low_verbosity_low_news_with_summary.csv
│   │   ├── gpt-5_reason_low_verbosity_medium_news_with_summary.csv
│   │   ├── gpt-5_reason_low_verbosity_high_news_with_summary.csv
│   │   ├── gpt-5_reason_medium_verbosity_low_news_with_summary.csv
│   │   ├── gpt-5_reason_medium_verbosity_medium_news_with_summary.csv
│   │   ├── gpt-5_reason_medium_verbosity_high_news_with_summary.csv
│   │   ├── gpt-5_reason_high_verbosity_low_news_with_summary.csv
│   │   ├── gpt-5_reason_high_verbosity_medium_news_with_summary.csv
│   │   └── gpt-5_reason_high_verbosity_high_news_with_summary.csv  ★主要使用
│   ├── risk/
│   │   ├── risk_gpt-5_minimal_by_o3_summary.csv
│   │   ├── risk_gpt-5_low_by_o3_summary.csv
│   │   ├── risk_gpt-5_medium_by_o3_summary.csv
│   │   ├── risk_gpt-5_high_by_o3_summary.csv
│   │   ├── risk_gpt-5_R_minimal_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv
│   │   ├── risk_gpt-5_R_low_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv
│   │   ├── risk_gpt-5_R_medium_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv
│   │   └── risk_gpt-5_R_high_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv
│   └── sentiment/
│       └── (同上結構)
│
├── gpt-5-mini/
│   ├── summary/                         # 12 種配置 (同 gpt-5)
│   ├── risk/
│   │   └── risk_gpt-5-mini_with_R_high_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv
│   └── sentiment/
│       └── sentiment_gpt-5-mini_with_R_high_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv
│
├── gpt-5.1/
│   └── summary/
│       └── gpt-5.1_reason_high_verbosity_high_news_with_summary.csv
│
└── claude/
    ├── risk/
    │   ├── risk_haiku_by_gpt5_summary.csv
    │   ├── risk_sonnet_by_gpt5_summary.csv
    │   └── risk_opus_by_gpt5_summary.csv
    ├── sentiment/
    │   ├── sentiment_haiku_by_gpt5_summary.csv
    │   ├── sentiment_sonnet_by_gpt5_summary.csv
    │   └── sentiment_opus_by_gpt5_summary.csv
    ├── finrl_claude_all_scores.csv      # 合併檔
    └── finrl_claude_all_scores.parquet  # Parquet 格式
```

---

## 附錄: 資料流程圖

```
huggingface_datasets/
├── FinRL_DeepSeek_sentiment/sentiment_deepseek_new_cleaned_nasdaq_news_full.csv
└── FinRL_DeepSeek_risk/risk_deepseek_cleaned_nasdaq_news_full.csv
    │
    │ ┌─────────────────────────────────────────────────────────────────────┐
    │ │  Phase 1: Summary Generation (openai_summary.py)                    │
    │ └─────────────────────────────────────────────────────────────────────┘
    │
    ├──[o3]──────────────→ o3/summary/o3_news_with_summary.csv
    │                           │
    ├──[gpt-5]───────────→ gpt-5/summary/gpt-5_reason_*_verbosity_*.csv (×12)
    │                           │
    ├──[gpt-5-mini]──────→ gpt-5-mini/summary/... (×12)
    │                           │
    └──[gpt-5.1]─────────→ gpt-5.1/summary/...
                                │
    ┌───────────────────────────┴───────────────────────────────────────────┐
    │  Phase 2: Risk/Sentiment Scoring (score_*_openai.py, score_*_anthropic.py)  │
    └───────────────────────────────────────────────────────────────────────┘
                                │
    ┌───────────────────────────┼───────────────────────────────────────────┐
    │                           │                                           │
    │  ┌─ o3_summary ──────────►├─→ o3/{risk,sentiment}/*_by_o3_summary.csv │
    │  │                        ├─→ o4-mini/{risk,sentiment}/*_by_o3_summary.csv
    │  │                        ├─→ gpt-4.1/{risk,sentiment}/*_by_o3_summary.csv
    │  │                        ├─→ gpt-4.1-mini/{risk,sentiment}/*_by_o3_summary.csv
    │  │                        ├─→ gpt-4.1-nano/{risk,sentiment}/*_by_o3_summary.csv
    │  │                        └─→ gpt-5/{risk,sentiment}/*_by_o3_summary.csv
    │  │
    │  ├─ gpt_5_summary ───────►├─→ gpt-4.1-mini/{risk,sentiment}/*_by_gpt-5_*.csv
    │  │  (主要用 high_high)    ├─→ gpt-5/{risk,sentiment}/R_*_V_low_by_gpt-5_*.csv
    │  │                        ├─→ gpt-5-mini/{risk,sentiment}/*_by_gpt-5_*.csv
    │  │                        ├─→ o3/{risk,sentiment}/*_by_gpt-5_*.csv
    │  │                        └─→ claude/{risk,sentiment}/*_by_gpt5_summary.csv
    │  │
    │  └─ Lsa_summary ─────────►├─→ o3/{risk,sentiment}/*_{1,2,high_4,medium_2}.csv
    │     (原版，早期實驗)       └─→ o4-mini/{risk,sentiment}/*_{high_1,medium_2}.csv
    │
    └───────────────────────────────────────────────────────────────────────┘
```

---

*文檔更新日期: 2025-12-27*