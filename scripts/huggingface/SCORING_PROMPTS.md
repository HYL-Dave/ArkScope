# Scoring Prompts — Open Dataset Provenance

> **Purpose.** This file records, verbatim, the exact LLM prompts used to generate the
> sentiment / risk scores and the summaries in the open dataset
> **[HYL/NASDAQ-News-Multi-LLM-Scores](https://huggingface.co/datasets/HYL/NASDAQ-News-Multi-LLM-Scores)**
> (FNSPID / FinRL_DeepSeek articles re-scored by multiple LLMs).
>
> It exists for **reproducibility / scientific provenance**: the scoring scripts that
> originally carried these prompts (`score_sentiment_openai.py`, `score_risk_openai.py`,
> their batch shells, and `OPENAI_SCRIPTS.md`) were a CSV/FNSPID-era pipeline and were
> retired in the 2026-05 local-first pivot. The prompts themselves are preserved here so
> the published scores stay interpretable after the code is gone.
>
> Column → model mapping and the scoring pipeline diagram: see
> [`column_mapping.md`](./column_mapping.md). Scores are integer **1–5**.

---

## ⚠️ Which prompt produced which scores

Two prompt *lineages* exist in this repo. **Only the first produced the open dataset.**

| Lineage | Scripts | Used for | In open dataset? |
|---|---|---|---|
| **Open-dataset (FNSPID re-scoring)** | `score_sentiment_openai.py`, `score_risk_openai.py` (retired); `score_sentiment_anthropic.py`, `score_risk_anthropic.py` (kept) | FNSPID articles → OpenAI/Anthropic scores | ✅ **yes** |
| **Live workbench** | `score_ibkr_news.py` (kept) | live Polygon/Finnhub/IBKR parquet | ❌ no — different prompt (see note below) |

The prompts below are the **open-dataset lineage**. They are reproduced exactly as they
stood in the scoring scripts at dataset-build time.

---

## Sentiment prompt

System prompt (used by `score_sentiment_openai.py` and `score_sentiment_anthropic.py`):

```
You are a sell-side equity strategist.
For each news headline about one stock, assign an integer sentiment score:
 1 = very bearish  (likely >5 % drop)
 2 = bearish       (2–5 % drop)
 3 = neutral / not relevant
 4 = bullish       (2–5 % rise)
 5 = very bullish  (>5 % rise)
Respond with only the integer sentiment score (1–5). **in JSON**:
{"score": <integer>}
If information is insufficient, respond with {"score": 3}.
```

- **Default on insufficient info:** `3` (neutral).
- The Anthropic variant is identical in meaning; cosmetic differences only (`>5%` without
  the space, ASCII hyphen instead of en-dash, and the JSON instruction phrased as
  *"Respond with ONLY a JSON object in this exact format: {"score": <integer from 1-5>}"*).

## Risk prompt

System prompt (used by `score_risk_openai.py` and `score_risk_anthropic.py`):

```
You are a financial risk officer.
Score each headline for downside risk of holding the stock:
 1 = very low risk
 2 = low risk
 3 = moderate / unknown
 4 = high risk
 5 = very high / catastrophic risk
Respond with only the integer risk score (1–5) in JSON format:
{"score": <integer>}
Use {"score": 3} when risk cannot be inferred.
```

- **Default on insufficient info:** `3` (moderate / unknown).
- Anthropic variant: same wording, JSON instruction phrased as the exact-format variant above.

## Summary prompt

Some score columns were computed on an LLM **summary** of the article rather than the raw
headline (see `column_mapping.md` "Scoring Pipeline"). Those summaries were produced by
`openai_summary.py` (kept in-tree) with:

```
You are a financial news summarization assistant.
Summarize the following news article in a concise paragraph, focusing on the core facts and implications.
Respond with only the summary text in JSON format:
{"summary": "<your summary>"}
If the article is too short or has insufficient content, still return a concise sentence describing that fact.
```

---

## User message templates

Filled per article and sent as the user turn:

- **Sentiment / risk:**
  ```
  TICKER: {symbol}
  HEADLINES:
  1. {headline}
  ```
  (When scored on a summary instead of a headline, the summary text is passed as `{headline}`.)
- **Summary:**
  ```
  TICKER: {symbol}
  ARTICLE:
  {text}
  ```

## Output contract & parsing

- The score was requested via a function/tool call `record_score` with schema
  `{"score": <integer, 1..5>}` — the OpenAI **Responses API** function tool for `gpt-5.4+`,
  and the Chat Completions `functions` format for o-series / `gpt-5`–`gpt-5.2`.
- Parse order: (1) the `record_score` tool arguments; (2) fall back to JSON
  `{"score": N}` in the text; (3) final fallback regex `\b([1-5])\b` over the raw output.
- Reasoning models (`o3`, `o4-mini`, `gpt-5` family) were run at the reasoning-effort /
  verbosity levels enumerated in `column_mapping.md` (the 4 reasoning × 3 verbosity grid
  for GPT-5 / GPT-5-mini, etc.).

---

## Note — the live-data risk prompt is intentionally different

`score_ibkr_news.py` (the surviving universal parquet scorer for the live workbench) uses a
**different** risk prompt and must NOT be cited as provenance for the open dataset:

```
You are an equity risk manager.
For each news headline about one stock, assign an integer risk score:
 1 = very low risk    (routine news, no impact)
 ...
 5 = very high risk   (major threat)
If information is insufficient, respond with {"score": 1}.
```

Differences from the open-dataset risk prompt: role ("equity risk manager" vs "financial
risk officer"), per-band descriptions, and the insufficient-info default (`1` vs `3`). Its
sentiment prompt, by contrast, matches the open-dataset sentiment prompt above.
