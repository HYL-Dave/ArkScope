# ArkScope — Project History & Open Data

> A curated record of where this project came from, the open-source data it
> produced, and why it changed direction. This is **narrative / provenance**,
> not an architecture source — for current direction see
> `docs/design/PROJECT_PRIORITY_MAP.md` §1 and
> `docs/design/CURRENT_PROJECT_CONTEXT.md`. It is also **not a dumping ground**:
> superseded docs are deleted (recoverable via git history), not parked here.

## Origins — MindfulRL-Intraday

ArkScope began as **MindfulRL-Intraday**: a research project using reinforcement
learning (PPO / CPPO) on price data enriched with LLM-scored news sentiment and
risk, in the lineage of **FinRL-DeepSeek** (benstaf,
[arXiv:2502.07393](https://arxiv.org/abs/2502.07393)). The original thesis was
that LLM sentiment/risk signals on financial news could improve RL trading agents.

The GitHub repo was renamed to **ArkScope** on 2026-04-15 (Phase 1); the local
directory + code/docs references followed on 2026-05-31 (Phase 2). See
`docs/design/ARKSCOPE_RENAME_PHASE2.md`. Fork-lineage detail (FinRL_DeepSeek
import-path + env-version changes) lives in `training/UPSTREAM.md`.

## Open Data

We open-sourced the multi-LLM financial-news scoring dataset on HuggingFace:

**[HYL/NASDAQ-News-Multi-LLM-Scores](https://huggingface.co/datasets/HYL/NASDAQ-News-Multi-LLM-Scores)**

127,176 NASDAQ news articles (from
[FNSPID](https://huggingface.co/datasets/Zihan1004/FNSPID)) re-scored by 11 LLMs
for sentiment and risk:

- **Anthropic**: Claude Opus 4.5, Sonnet 4.5, Haiku 4.5
- **OpenAI**: GPT-5, GPT-5-mini, GPT-5.4-nano, GPT-4.1, GPT-4.1-mini, GPT-4.1-nano
- **OpenAI reasoning**: o3, o4-mini

Includes 60 score columns, 26 summary variants (GPT-5 / GPT-5-mini at 4 reasoning
× 3 verbosity levels), and cross-model analysis. Built upon
[FinRL-DeepSeek](https://github.com/benstaf/FinRL_DeepSeek).

This dataset stays published regardless of the project's direction — it is a
standalone research contribution.

## The 2026-05 pivot — why RL was de-focused

Two empirical findings moved the project away from the RL-first thesis:

1. **Single-news LLM sentiment scoring showed little predictive value** — the
   per-article sentiment-to-next-day-return correlation came out near zero
   (`r < 0.03`) across the LLM scoring models tested.
2. **The RL line could not demonstrate out-of-sample predictability** — after the
   `VecNormalize` fix, OOS performance was still not shown. Full diagnosis +
   resume criteria: `docs/design/RL_COLLAPSE_FINDINGS.md`.

The project formally repositioned (2026-05-02) into a **local-first financial
research agent workbench** — an LLM agent + the existing financial data layer + a
research GUI, with portability (zip-and-go across machines) as a first-class axis.
The full decision record is in `docs/design/PROJECT_PRIORITY_MAP.md` §10
(newest-first).

**RL is not deleted — it is paused (P3.1).** The training code stays exercisable;
if it resumes, the starting point is `RL_COLLAPSE_FINDINGS.md` plus a fresh design
on the local-first architecture, not the old PostgreSQL / service-first roadmap.

## What survived the pivot

Foundations that carried over into the workbench (not throwaway): the data-source
clients + collection pipeline, the LLM scoring tooling, the multi-factor signal
system (`src/signals/`), and the agent capability stack (tools, episodic memory,
reports, compression, replay, subagents). Current carry-over inventory:
`docs/design/DESKTOP_APP_CARRYOVER_ANALYSIS.md`.
