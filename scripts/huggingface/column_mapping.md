# HuggingFace Dataset: Column Mapping

## Source: FNSPID / FinRL_DeepSeek (127,176 articles, 89 NASDAQ tickers, 2009-2024)

This dataset re-scores the same articles from benstaf/FinRL_DeepSeek using multiple
state-of-the-art LLMs with different reasoning effort levels and summary inputs.

**Original dataset (NOT included here, already open-source):**
- DeepSeek V3 scores → benstaf/FinRL_DeepSeek
- Llama scores → benstaf/FinRL_DeepSeek

**Coverage:** 77,871 of 127,176 articles (61.2%) have LLM-generated summaries
and summary-based scores. The remaining 38.8% lack article content in the source data.
GPT-5.4-nano scores are 100% complete (title-only, no article text needed).

All scores are integer 1-5 scale (1=most negative/highest risk, 5=most positive/lowest risk).

---

## File Structure

| File | Size | Description |
|------|------|-------------|
| `scores.parquet` | 11.6 MB | All 60 score columns + metadata |
| `summaries.parquet` | 329 MB | Article text + core summaries used for scoring |
| `summaries_gpt5_grid.parquet` | 322 MB | GPT-5 summary variants (4 reasoning × 3 verbosity) |
| `summaries_gpt5mini_grid.parquet` | 320 MB | GPT-5-mini summary variants (4R × 3V) |

---

## Scoring Pipeline

```
Article (full text) ─────────────────→ o3-high, o4-mini-high (fulltext)
    │
    ├─→ 4 extractive summaries ─────→ (included in summaries.parquet, not used for LLM scoring)
    │
    ├─→ GPT-5 summary ──┬──→ Claude Opus/Sonnet/Haiku
    │   (R=high V=high)  ├──→ GPT-5 {high,med,low,min}
    │                    ├──→ o3-high
    │                    ├──→ GPT-5-mini
    │                    └──→ GPT-4.1-mini (5 summary variants tested)
    │
    ├─→ o3 summary ─────┬──→ GPT-5 {high,med,low,min}
    │                    ├──→ o3 {high,med,low}
    │                    ├──→ o4-mini {high,med,low}
    │                    ├──→ GPT-4.1
    │                    ├──→ GPT-4.1-mini
    │                    └──→ GPT-4.1-nano
    │
    └─→ Title only ─────────→ GPT-5.4-nano (100% coverage)
```

---

## Naming Convention

Score columns: `{sentiment|risk}_{model}_{effort}_{input_source}`

- `model`: scoring LLM (opus, sonnet, haiku, gpt5, o3, o4mini, gpt41, gpt41mini, gpt41nano, gpt5mini, nano)
- `effort`: reasoning effort (high/medium/low/minimal) — omitted when model has single effort
- `input_source`: what text the model scored
  - `fulltext` — original full article text
  - `gpt5sum` — GPT-5 generated summary (R=high, V=high unless specified)
  - `gpt5sum_R{x}_V{y}` — GPT-5 summary with specific reasoning/verbosity
  - `o3sum` — o3 generated summary
  - `title` — article title only

---

## scores.parquet — 60 Score Columns

### Metadata

| Column | Type | Description |
|--------|------|-------------|
| Date | str | Publication date (YYYY-MM-DD) |
| Article_title | str | Article headline |
| Stock_symbol | str | Ticker symbol |
| Url | str | Source URL |
| Publisher | str | News publisher |
| Author | str | Article author |

### Full-text Scores (scored directly from article, 61% coverage)

| Column | Model | Effort | Notes |
|--------|-------|--------|-------|
| sentiment_o3_high_fulltext | o3 | high | |
| risk_o3_medium_fulltext | o3 | medium | asymmetric — cost limited |
| sentiment_o4mini_high_fulltext | o4-mini | high | |
| risk_o4mini_medium_fulltext | o4-mini | medium | asymmetric — cost limited |

### Claude Models (by GPT-5 summary, 61% coverage)

| Column | Model |
|--------|-------|
| sentiment_opus_gpt5sum, risk_opus_gpt5sum | Claude Opus |
| sentiment_sonnet_gpt5sum, risk_sonnet_gpt5sum | Claude Sonnet |
| sentiment_haiku_gpt5sum, risk_haiku_gpt5sum | Claude Haiku |

### GPT-5 (4 effort levels × 2 summary sources, 61% coverage)

| Column pattern | Summary |
|----------------|---------|
| {s\|r}_gpt5_{high\|medium\|low\|minimal}_gpt5sum | GPT-5 summary |
| {s\|r}_gpt5_{high\|medium\|low\|minimal}_o3sum | o3 summary |

8 sentiment + 8 risk = 16 columns

### o3 (3 effort levels × 2 summary sources + gpt5sum, 61% coverage)

| Column pattern | Summary |
|----------------|---------|
| {s\|r}_o3_{high\|medium\|low}_o3sum | o3 summary |
| {s\|r}_o3_high_gpt5sum | GPT-5 summary |

6 + 2 = 8 columns

### o4-mini (3 effort levels, by o3 summary, 61% coverage)

| Column pattern | Summary |
|----------------|---------|
| {s\|r}_o4mini_{high\|medium\|low}_o3sum | o3 summary |

6 columns

### GPT-4.1 family (61% coverage)

| Column | Model | Summary |
|--------|-------|---------|
| {s\|r}_gpt41_o3sum | GPT-4.1 | o3 summary |
| {s\|r}_gpt41mini_gpt5sum_Rhigh_Vhigh | GPT-4.1-mini | GPT-5 (R=high, V=high) |
| {s\|r}_gpt41mini_gpt5sum_Rhigh_Vmed | GPT-4.1-mini | GPT-5 (R=high, V=medium) |
| {s\|r}_gpt41mini_gpt5sum_Rmed_Vhigh | GPT-4.1-mini | GPT-5 (R=medium, V=high) |
| {s\|r}_gpt41mini_gpt5sum_Rlow_Vhigh | GPT-4.1-mini | GPT-5 (R=low, V=high) |
| {s\|r}_gpt41mini_gpt5sum_Rmin_Vhigh | GPT-4.1-mini | GPT-5 (R=minimal, V=high) |
| {s\|r}_gpt41mini_o3sum | GPT-4.1-mini | o3 summary |
| {s\|r}_gpt41nano_o3sum | GPT-4.1-nano | o3 summary |

16 columns

### GPT-5-mini (61% coverage)

| Column | Model | Summary |
|--------|-------|---------|
| sentiment_gpt5mini_high_gpt5sum | GPT-5-mini | GPT-5 (R=high, V=high) |
| risk_gpt5mini_high_gpt5sum | GPT-5-mini | GPT-5 (R=high, V=high) |

### GPT-5.4-nano (title only, 100% coverage)

| Column | Model | Input |
|--------|-------|-------|
| sentiment_nano_title | GPT-5.4-nano | Article title only |
| risk_nano_title | GPT-5.4-nano | Article title only |

---

## summaries.parquet — Core Summaries

These are the summaries actually used as input for the scoring models above.

| Column | Generator | Description | Coverage |
|--------|-----------|-------------|----------|
| Date, Article_title, Stock_symbol | — | Join keys | 100% |
| Article | — | Original full article text | 61% |
| Lsa_summary | LSA | Latent Semantic Analysis extractive | 61% |
| Luhn_summary | Luhn | Keyword-based extractive | 61% |
| Textrank_summary | TextRank | Graph-based extractive | 61% |
| Lexrank_summary | LexRank | Eigenvector-based extractive | 61% |
| gpt_5_summary | GPT-5 (R=high, V=high) | Abstractive summary | 61% |
| o3_summary | o3 | Abstractive summary | 61% |

Note: 4 extractive summaries are from the upstream FNSPID dataset.
gpt_5_summary and o3_summary are our contributions.

---

## summaries_gpt5_grid.parquet — GPT-5 Summary Variants

12 columns: 4 reasoning levels × 3 verbosity levels.
All summaries generated by GPT-5 with different parameter combinations.

| Column | Reasoning | Verbosity |
|--------|-----------|-----------|
| gpt5_Rhigh_Vhigh | high | high |
| gpt5_Rhigh_Vmedium | high | medium |
| gpt5_Rhigh_Vlow | high | low |
| gpt5_Rmedium_Vhigh | medium | high |
| gpt5_Rmedium_Vmedium | medium | medium |
| gpt5_Rmedium_Vlow | medium | low |
| gpt5_Rlow_Vhigh | low | high |
| gpt5_Rlow_Vmedium | low | medium |
| gpt5_Rlow_Vlow | low | low |
| gpt5_Rminimal_Vhigh | minimal | high |
| gpt5_Rminimal_Vmedium | minimal | medium |
| gpt5_Rminimal_Vlow | minimal | low |

Note: `gpt5_Rhigh_Vhigh` is the same summary as `gpt_5_summary` in summaries.parquet.

---

## summaries_gpt5mini_grid.parquet — GPT-5-mini Summary Variants

Same 4×3 grid structure as GPT-5, generated by GPT-5-mini.

| Column | Reasoning | Verbosity |
|--------|-----------|-----------|
| gpt5mini_Rhigh_Vhigh | high | high |
| gpt5mini_Rhigh_Vmedium | high | medium |
| gpt5mini_Rhigh_Vlow | high | low |
| gpt5mini_Rmedium_Vhigh | medium | high |
| gpt5mini_Rmedium_Vmedium | medium | medium |
| gpt5mini_Rmedium_Vlow | medium | low |
| gpt5mini_Rlow_Vhigh | low | high |
| gpt5mini_Rlow_Vmedium | low | medium |
| gpt5mini_Rlow_Vlow | low | low |
| gpt5mini_Rminimal_Vhigh | minimal | high |
| gpt5mini_Rminimal_Vmedium | minimal | medium |
| gpt5mini_Rminimal_Vlow | minimal | low |

---

## Summary Statistics

- **Score columns:** 60 (30 sentiment + 30 risk)
- **Scoring models:** 11 (Claude Opus/Sonnet/Haiku, GPT-5, o3, o4-mini, GPT-4.1, GPT-4.1-mini, GPT-4.1-nano, GPT-5-mini, GPT-5.4-nano)
- **Summary variants:** 26 (1 o3 + 12 GPT-5 grid + 12 GPT-5-mini grid + 4 upstream extractive)
- **Rows:** 127,176 articles
- **Unique tickers:** 89 NASDAQ stocks
- **Date range:** 2009-07-07 to 2024-01-09
- **Score coverage:** 61% for summary-based, 100% for title-based (nano)