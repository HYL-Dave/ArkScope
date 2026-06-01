# Scoring Prompts — Open Dataset Provenance

> **Purpose.** This file records, verbatim, the exact LLM prompts used to generate the
> sentiment / risk scores and the summaries in the open dataset
> **[HYL/NASDAQ-News-Multi-LLM-Scores](https://huggingface.co/datasets/HYL/NASDAQ-News-Multi-LLM-Scores)**
> (FNSPID / FinRL_DeepSeek articles re-scored by multiple LLMs).
>
> It exists for **reproducibility / scientific provenance**: the scoring scripts that
> originally carried the OpenAI prompts (`score_sentiment_openai.py`,
> `score_risk_openai.py`, their batch shells, and `OPENAI_SCRIPTS.md`) were a CSV/FNSPID-era
> pipeline retired in the 2026-05 local-first pivot. The prompts are preserved here so the
> published scores stay interpretable after the code is gone.
>
> Prompts are reproduced **byte-for-byte** from the script source. The OpenAI and Anthropic
> model families used **different** prompt strings (punctuation, dash style, and whether the
> JSON example is fenced), so both are shown in full rather than collapsed. Column → model
> mapping and the scoring pipeline diagram: see [`column_mapping.md`](./column_mapping.md).
> Scores are integer **1–5**.
>
> *Whitespace note:* the OpenAI prompts are triple-quoted with the delimiters on their own
> lines, so each begins and ends with a newline; the Anthropic prompts open on the same line
> as `"""` and have no leading/trailing newline. The code-fence blocks below preserve the
> inner text exactly.

---

## ⚠️ Which prompt produced which scores

Two prompt *lineages* exist in this repo. **Only the first produced the open dataset.**

| Lineage | Scripts | Used for | In open dataset? |
|---|---|---|---|
| **Open-dataset (FNSPID re-scoring)** | `score_sentiment_openai.py`, `score_risk_openai.py` (retired); `score_sentiment_anthropic.py`, `score_risk_anthropic.py` (kept) | FNSPID articles → OpenAI/Anthropic scores | ✅ **yes** |
| **Live workbench** | `score_ibkr_news.py` (kept) | live Polygon/Finnhub/IBKR parquet | ❌ no — different risk prompt (see end) |

---

## Sentiment prompt

**OpenAI** (`score_sentiment_openai.py`) — produced the o3 / o4-mini / GPT-4.1 / GPT-5-family
sentiment columns:

````text
You are a sell-side equity strategist.
For each news headline about one stock, assign an integer sentiment score:
 1 = very bearish  (likely >5 % drop)
 2 = bearish       (2–5 % drop)
 3 = neutral / not relevant
 4 = bullish       (2–5 % rise)
 5 = very bullish  (>5 % rise)
Respond with only the integer sentiment score (1–5). **in JSON**:
```json
{"score": <integer>}
```
If information is insufficient, respond with {"score": 3}.
````

**Anthropic** (`score_sentiment_anthropic.py`) — produced the Claude Opus / Sonnet / Haiku
sentiment columns:

```text
You are a sell-side equity strategist.
For each news headline about one stock, assign an integer sentiment score:
 1 = very bearish  (likely >5% drop)
 2 = bearish       (2-5% drop)
 3 = neutral / not relevant
 4 = bullish       (2-5% rise)
 5 = very bullish  (>5% rise)

Respond with ONLY a JSON object in this exact format:
{"score": <integer from 1-5>}

If information is insufficient, respond with {"score": 3}.
```

- Both default to `3` (neutral) on insufficient info. Differences: OpenAI uses en-dashes
  (`2–5 %`, space before `%`) and a fenced ` ```json ` example; Anthropic uses ASCII hyphens
  (`2-5%`, no space) and an inline JSON example.

## Risk prompt

**OpenAI** (`score_risk_openai.py`) — produced the o3 / o4-mini / GPT-4.1 / GPT-5-family
risk columns:

````text
You are a financial risk officer.
Score each headline for downside risk of holding the stock:
 1 = very low risk
 2 = low risk
 3 = moderate / unknown
 4 = high risk
 5 = very high / catastrophic risk
Respond with only the integer risk score (1–5) in JSON format:
```json
{"score": <integer>}
```
Use {"score": 3} when risk cannot be inferred.
````

**Anthropic** (`score_risk_anthropic.py`) — produced the Claude risk columns:

```text
You are a financial risk officer.
Score each headline for downside risk of holding the stock:
 1 = very low risk
 2 = low risk
 3 = moderate / unknown
 4 = high risk
 5 = very high / catastrophic risk

Respond with ONLY a JSON object in this exact format:
{"score": <integer from 1-5>}

Use {"score": 3} when risk cannot be inferred.
```

- Both default to `3` (moderate / unknown) on insufficient info; same wording, differing only
  in the JSON-example formatting.

## Summary prompt

Some score columns were computed on an LLM **summary** of the article rather than the raw
headline (see `column_mapping.md` "Scoring Pipeline"). Those summaries were produced by
`openai_summary.py` (kept in-tree) with:

````text
You are a financial news summarization assistant.
Summarize the following news article in a concise paragraph, focusing on the core facts and implications.
Respond with only the summary text in JSON format:
```json
{"summary": "<your summary>"}
```
If the article is too short or has insufficient content, still return a concise sentence describing that fact.
````

---

## User message templates

Filled per article and sent as the user turn:

- **Sentiment / risk:**
  ```text
  TICKER: {symbol}
  HEADLINES:
  1. {headline}
  ```
  (When scored on a summary instead of a headline, the summary text is passed as `{headline}`.)
- **Summary:**
  ```text
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

````text
You are an equity risk manager.
For each news headline about one stock, assign an integer risk score:
 1 = very low risk    (routine news, no impact)
 2 = low risk         (minor concern)
 3 = moderate risk    (notable but manageable)
 4 = high risk        (significant concern)
 5 = very high risk   (major threat)
Respond with only the integer risk score (1–5). **in JSON**:
```json
{"score": <integer>}
```
If information is insufficient, respond with {"score": 1}.
````

Differences from the open-dataset risk prompt: role ("equity risk manager" vs "financial
risk officer"), per-band descriptions, and the insufficient-info default (`1` vs `3`). Its
sentiment prompt, by contrast, is byte-for-byte the open-dataset OpenAI sentiment prompt above.
