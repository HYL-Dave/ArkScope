# FNSPID News Extraction (historical)

> Historical record of the FNSPID news extraction that fed the open dataset
> **[HYL/NASDAQ-News-Multi-LLM-Scores](https://huggingface.co/datasets/HYL/NASDAQ-News-Multi-LLM-Scores)**.
> The processing scripts (a local FNSPID + OpenAI o3/Flex pipeline under
> `NewsExtraction/`) were retired in the 2026-05 local-first pivot; this page
> preserves the WHAT/WHY. The published dataset's column/score provenance lives in
> [`../../scripts/huggingface/column_mapping.md`](../../scripts/huggingface/column_mapping.md)
> and [`../../scripts/huggingface/SCORING_PROMPTS.md`](../../scripts/huggingface/SCORING_PROMPTS.md).

## Source

Articles originate from **FNSPID** ([Zihan1004/FNSPID](https://huggingface.co/datasets/Zihan1004/FNSPID))
and the **FinRL_DeepSeek** subset (benstaf/FinRL_DeepSeek, arXiv:2502.07393).

## Ticker universe: 89 → 75 → 130+

- The target NASDAQ universe was **89 tickers**; the exact list is preserved at
  [`artifacts/fnspid_tickers_89.json`](./artifacts/fnspid_tickers_89.json). The
  published FinRL_DeepSeek dataset covers all **89**.
- This local FNSPID re-extraction cleaned to **75 usable tickers** — a subset of the
  89. The other **14** were dropped because their FNSPID data ended around
  **2020-06-10** with all-zero (placeholder) sentiment:
  `CSCO, GOOGL, IDXX, ILMN, INTU, JD, LULU, MAR, MCHP, MDLZ, NFLX, NXPI, SGEN, SNPS`.
- The main project's `config/tickers_core.json` has since grown into its own **130+
  tiered universe** — independent of, and not bounded by, this original 75/89.

> Note: the `fnspid_89_*` filenames refer to the 89-ticker *universe*; the cleaned
> data itself contains 75 usable tickers.

## FNSPID vs FinRL_DeepSeek (verified 2025-12-30)

| metric | FNSPID (local clean) | FinRL_DeepSeek (published) |
|---|---|---|
| articles | 218,654 | 127,176 |
| date range | 2013-01-02 → 2023-12-31 | 2009-07-07 → 2024-01-09 |
| unique tickers | 75 | 89 |
| article text | 100% | 61.2% (77,871) |
| sentiment | all-0 placeholder | `sentiment_deepseek` 99.3% |

Ticker overlap: common **75**, FNSPID-only **0**, FinRL-only **14** (the 75 ⊂ 89).
Article overlap (MD5 of title + first 200 chars): ~**143,373** articles (≈65.6%) are
FNSPID-only; overlap ≈34.4%. The published score dataset re-scores the 127,176 set.

## How it worked (retired)

The local `NewsExtraction/` pipeline downloaded FNSPID from HuggingFace, cleaned and
validated records, ran a 17-dimension LLM quality analysis (o3 / o4-mini via OpenAI
Flex), and exported Parquet / CSV / DuckDB. That tooling is **retired** — recover it
from git history if ever needed; do not re-add it to an active module path. The
sentiment/risk **scoring** prompts (a separate pipeline) are preserved verbatim in
`SCORING_PROMPTS.md`.

## Why it was de-focused

Single-article LLM sentiment showed little next-day predictive value (r < 0.03), which
— together with the RL out-of-sample results — moved the project off the RL-first
thesis (see [`../PROJECT_HISTORY.md`](../PROJECT_HISTORY.md)). The dataset remains
published as a standalone research contribution.
