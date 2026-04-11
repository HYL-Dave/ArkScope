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

## Naming Convention

Score columns: `{sentiment|risk}_{model}_{effort}_{input_source}`

- `effort`: reasoning effort level of the scoring model (high/medium/low/minimal)
- `input_source`: what text the model scored
  - `fulltext` — original full article text
  - `gpt5sum` — GPT-5 generated abstractive summary
  - `o3sum` — o3 generated abstractive summary
  - `title` — article title only

When a model has only one effort level or input source, those parts are omitted.

All scores are integer 1-5 scale (1=most negative/highest risk, 5=most positive/lowest risk).

---

## scores.parquet — Score Columns

### Metadata (shared across all rows)

| Column | Type | Description |
|--------|------|-------------|
| Date | str | Publication date (YYYY-MM-DD) |
| Article_title | str | Article headline |
| Stock_symbol | str | Ticker symbol |
| Url | str | Source URL |
| Publisher | str | News publisher |
| Author | str | Article author |

### Full-text Models (scored directly from article text, 61.2% coverage)

| Column | Model | Effort | Input | Source File |
|--------|-------|--------|-------|-------------|
| sentiment_o3_high_fulltext | o3 | high | full article | o3/sentiment/sentiment_o3_high_4.csv |
| risk_o3_medium_fulltext | o3 | medium | full article | o3/risk/risk_o3_medium_2.csv |

### Claude Models (all scored from GPT-5 summary, 61.2% coverage)

| Column | Model | Effort | Input | Source File |
|--------|-------|--------|-------|-------------|
| sentiment_opus_gpt5sum | Claude Opus | default | gpt_5_summary | claude/sentiment/opus*.csv |
| risk_opus_gpt5sum | Claude Opus | default | gpt_5_summary | claude/risk/opus*.csv |
| sentiment_sonnet_gpt5sum | Claude Sonnet | default | gpt_5_summary | claude/sentiment/sonnet*.csv |
| risk_sonnet_gpt5sum | Claude Sonnet | default | gpt_5_summary | claude/risk/sonnet*.csv |
| sentiment_haiku_gpt5sum | Claude Haiku | default | gpt_5_summary | claude/sentiment/haiku*.csv |
| risk_haiku_gpt5sum | Claude Haiku | default | gpt_5_summary | claude/risk/haiku*.csv |

### GPT-5 (scored from GPT-5 summary, 4 effort levels)

| Column | Model | Effort | Input | Source File |
|--------|-------|--------|-------|-------------|
| sentiment_gpt5_high_gpt5sum | GPT-5 | high | gpt_5_summary | gpt-5/sentiment/*R_high*gpt-5*.csv |
| sentiment_gpt5_medium_gpt5sum | GPT-5 | medium | gpt_5_summary | gpt-5/sentiment/*R_medium*.csv |
| sentiment_gpt5_low_gpt5sum | GPT-5 | low | gpt_5_summary | gpt-5/sentiment/*R_low*.csv |
| sentiment_gpt5_minimal_gpt5sum | GPT-5 | minimal | gpt_5_summary | gpt-5/sentiment/*R_minimal*.csv |
| risk_gpt5_high_gpt5sum | GPT-5 | high | gpt_5_summary | gpt-5/risk/*R_high*.csv |
| risk_gpt5_medium_gpt5sum | GPT-5 | medium | gpt_5_summary | gpt-5/risk/*R_medium*.csv |
| risk_gpt5_low_gpt5sum | GPT-5 | low | gpt_5_summary | gpt-5/risk/*R_low*.csv |
| risk_gpt5_minimal_gpt5sum | GPT-5 | minimal | gpt_5_summary | gpt-5/risk/*R_minimal*.csv |

### GPT-5 (scored from o3 summary, 4 effort levels)

| Column | Model | Effort | Input | Source File |
|--------|-------|--------|-------|-------------|
| sentiment_gpt5_high_o3sum | GPT-5 | high | o3_summary | gpt-5/sentiment/*high*o3*.csv |
| sentiment_gpt5_medium_o3sum | GPT-5 | medium | o3_summary | gpt-5/sentiment/*medium*o3*.csv |
| sentiment_gpt5_low_o3sum | GPT-5 | low | o3_summary | gpt-5/sentiment/*low*o3*.csv |
| sentiment_gpt5_minimal_o3sum | GPT-5 | minimal | o3_summary | gpt-5/sentiment/*minimal*o3*.csv |
| risk_gpt5_high_o3sum | GPT-5 | high | o3_summary | gpt-5/risk/*high*o3*.csv |
| risk_gpt5_medium_o3sum | GPT-5 | medium | o3_summary | gpt-5/risk/*medium*o3*.csv |
| risk_gpt5_low_o3sum | GPT-5 | low | o3_summary | gpt-5/risk/*low*o3*.csv |
| risk_gpt5_minimal_o3sum | GPT-5 | minimal | o3_summary | gpt-5/risk/*minimal*o3*.csv |

### o3 (scored from o3 summary, multiple efforts)

| Column | Model | Effort | Input | Source File |
|--------|-------|--------|-------|-------------|
| sentiment_o3_high_o3sum | o3 | high | o3_summary | o3/sentiment/*high*o3_summary.csv |
| sentiment_o3_medium_o3sum | o3 | medium | o3_summary | o3/sentiment/*medium*o3*.csv |
| sentiment_o3_low_o3sum | o3 | low | o3_summary | o3/sentiment/*low*o3*.csv |
| risk_o3_high_o3sum | o3 | high | o3_summary | o3/risk/*high*o3_summary.csv |
| risk_o3_medium_o3sum | o3 | medium | o3_summary | o3/risk/*medium*o3*.csv |
| risk_o3_low_o3sum | o3 | low | o3_summary | o3/risk/*low*o3*.csv |

### o3 (scored from GPT-5 summary)

| Column | Model | Effort | Input | Source File |
|--------|-------|--------|-------|-------------|
| sentiment_o3_high_gpt5sum | o3 | high | gpt_5_summary | o3/sentiment/*high*gpt-5*.csv |
| risk_o3_high_gpt5sum | o3 | high | gpt_5_summary | o3/risk/*high*gpt-5*.csv |

### GPT-5-mini (scored from GPT-5 summary)

| Column | Model | Effort | Input | Source File |
|--------|-------|--------|-------|-------------|
| sentiment_gpt5mini_high_gpt5sum | GPT-5-mini | high | gpt_5_summary | gpt-5-mini/sentiment/*.csv |
| risk_gpt5mini_high_gpt5sum | GPT-5-mini | high | gpt_5_summary | gpt-5-mini/risk/*.csv |

### GPT-5.4-nano (scored from title only)

| Column | Model | Effort | Input | Source File |
|--------|-------|--------|-------|-------------|
| sentiment_nano_title | GPT-5.4-nano | xhigh | title only | gpt-5.4-nano/sentiment/*.csv |
| risk_nano_title | GPT-5.4-nano | xhigh | title only | gpt-5.4-nano/risk/*.csv |

---

## summaries.parquet — Summary Texts

All summaries have 61.2% coverage (77,871/127,176), matching articles with text content.

| Column | Type | Generator | Description | Coverage |
|--------|------|-----------|-------------|----------|
| Date | str | — | Join key | 100% |
| Article_title | str | — | Join key | 100% |
| Stock_symbol | str | — | Join key | 100% |
| Article | str | — | Original full article text | 61.2% |
| Lsa_summary | str | LSA algorithm | Latent Semantic Analysis extractive summary | 61.2% |
| Luhn_summary | str | Luhn algorithm | Luhn keyword-based extractive summary | 61.2% |
| Textrank_summary | str | TextRank | TextRank graph-based extractive summary | 61.2% |
| Lexrank_summary | str | LexRank | LexRank eigenvector-based extractive summary | 61.2% |
| gpt_5_summary | str | GPT-5 (R=high, V=high) | GPT-5 generated abstractive summary | 61.2% |
| o3_summary | str | o3 | o3 generated abstractive summary | 61.2% |

Note: The 4 extractive summaries (LSA/Luhn/TextRank/LexRank) are from the upstream dataset.
The GPT-5 and o3 summaries are our contributions.

---

## Summary

- **Score columns:** 36 (18 sentiment + 18 risk) — excluding upstream DeepSeek/Llama
  - Note: fulltext scores are asymmetric (sentiment=o3_high, risk=o3_medium) due to cost
- **Summary columns:** 6 (4 upstream extractive + 2 new LLM abstractive)
- **Rows:** 127,176 articles
- **Score coverage:** 61.2% for summary-based, 100% for title-based (nano)
- **Unique tickers:** 89 NASDAQ stocks
- **Date range:** 2009-07-07 to 2024-01-09