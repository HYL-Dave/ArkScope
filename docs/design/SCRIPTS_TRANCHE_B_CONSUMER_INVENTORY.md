# Scripts Tranche B Legacy Score Consumer Inventory

> **Status:** INDEPENDENT REVIEW GREEN; INPUT TO PRODUCT DECISION SPEC
> **Date:** 2026-08-08
> **Base:** `7257699171a81294b74ff8cde61fb90bb065a2b4`
> **Authority boundary:** This document inventories current behavior and proposes
> review questions. It does not authorize code deletion, score-row deletion,
> secret changes, or Tranche B implementation.

## 1. Question this inventory answers

Tranche A reduced root `scripts/` from 52 files to the nine-path scoring
transition layer. Tranche B can remove that final directory only after every
consumer of the old per-article 1-5 sentiment/risk score contract has a named
disposition.

The deciding product question is not merely "does a script still import?" It
is:

> If the legacy score contract disappears, what continues to work for the user
> and the model, what must be rewritten as raw-news behavior, and what capability
> must honestly disappear until a new semantic is designed?

This inventory covers storage, readers, DTOs, tools, prompts, routes, monitors,
frontend types, tests, authorities, data and local-secret ownership.

## 2. Dated production facts

All observations below used SQLite read-only mode plus `PRAGMA query_only=ON` on
2026-08-08. They are dated evidence, not permanent acceptance constants.

### 2.1 Stored population

| Observation | Value |
|---|---:|
| `news_article_scores` rows | 491,808 |
| distinct scored article ids | 140,152 |
| score pairs | sentiment/risk x `haiku`, `gpt_5_2`, `gpt_5_4` |
| score operation time range | 2026-06-07 06:03-06:06 UTC |
| newest article represented by a score | 2026-04-27 00:17 UTC |
| normalized `news_articles` rows | 332,904 |
| normalized rows with direct `sentiment_score` | 0 |
| newest normalized article | 2026-08-07 18:15 UTC |

The score table is a frozen historical batch. No active product writer has
extended it since 2026-06-07. The only tracked write path is the manual local
import core plus its root-script wrapper.

### 2.2 Current-window coverage

Using canonical normalized article ids and a fixed `2026-08-08` observation
date:

| Lookback | canonical news articles | articles with any legacy score |
|---:|---:|---:|
| 7 days | 8,037 | 0 |
| 30 days | 34,589 | 0 |
| 90 days | 86,907 | 0 |
| 180 days | 160,237 | 3,492 |

Therefore neither of these statements is accurate:

- "the current UI is showing June scores as today's score"; or
- "the old score contract is harmless because no live consumer can reach it".

The current web components do not render the score-derived fields, and common
7/30/90-day requests return no scored rows. However agent-callable tools accept
large lookbacks (up to 9,999 days on signal routes), old scores remain reachable,
and neither score DTOs nor tool copy carries freshness/coverage metadata.

## 3. Complete consumer map

### 3.1 Storage and writers

| Owner | Current role | Required Tranche B ruling |
|---|---|---|
| `src/news_normalized/schema.py` | creates `news_article_scores` and indexes | stop creating the retired table after reader/writer cutover; existing physical table is a later manifest operation |
| `src/news_normalized/scores.py` | score key/model validation and latest-score helpers | remove if no new-semantic consumer remains |
| `src/news_normalized/score_import.py` | only tracked insert/upsert owner | retire with the old semantic |
| `scripts/scoring/import_news_scores_local.py` | root wrapper for the import core | retire |
| remaining `scripts/scoring/*.py` | batch scoring, summary and validation executables | retire; historical method belongs in existing history/decision docs, not runnable code |
| `src/daily_update.py` score option/error copy | operator tombstone that still names the importer | remove atomically with scorer retirement |
| `config/scoring_keys.txt` | local `0600`, gitignored credential pool owned by the scorer | do not inspect; migrate to a named credential owner or delete only with separate explicit user approval |

Physical deletion of 491,808 rows is not implied by Git removal. It requires a
fresh exact-key/table manifest, stopped writers, rollback proof, independent
review and the user's separate approval.

### 3.2 Backend projection

| Owner | Score dependency | Candidate disposition |
|---|---|---|
| `SqliteBackend._news_score_tables_available`, `_score_map_joins`, `_score_lookup_expr` | bridges normalized articles to the legacy table | remove |
| `query_news` / `query_news_search` | projects sentiment/risk/model and filters `scored_only` | preserve raw-news query; remove old score projection/filter arguments or return a typed unsupported result during compatibility window |
| `query_news_stats` | mixes raw article count with legacy score aggregates | preserve article count/date range; remove scored aggregates |
| `LocalMarketBackend` score-specific no-PG branches | protects the legacy score read contract | simplify after score arguments leave the protocol |
| `FileBackend` score-column detection and score projection | reads old parquet column families | retire; raw file fallback must not keep the semantic alive |
| `DatabaseBackend` score-shaped protocol methods | legacy/import surface, no PG runtime authority | remove score-specific shape while preserving raw news protocol |

Several backend docstrings still say `news_scores RETIRED` while current code
actively reads `news_article_scores`. Tranche B must remove this contradiction,
not replace it with another compatibility fiction.

### 3.3 DTO and ordinary news behavior

`NewsArticle`, `NewsBrief`, `NewsQueryResult`, `DataAccessLayer.get_news`, and
`DataAccessLayer.search_news` carry score-derived fields even when callers ask
for ordinary news.

| Surface | Current behavior | Candidate disposition |
|---|---|---|
| `get_ticker_news` | raw-news query (`scored_only=False`) but old rows may carry legacy scores | preserve articles; remove legacy score fields |
| `search_news_by_keyword` | raw search, same score-bearing DTO | preserve articles; remove legacy score fields |
| `search_news_advanced` | explicitly advertises `scored_only`, `min_sentiment`, `max_risk` | preserve query/ticker/date search; retire old score filters |
| `get_news_brief` | raw counts plus score aggregates | preserve article counts/date range; remove score aggregates |
| `analysis/context_builder.py` | includes sentiment/risk in otherwise raw 7/14/30-day context | preserve raw context; remove legacy fields |
| `evidence_packet.py` | explicitly strips ArkScope scores | retain as a protected negative contract |

Provider-native sentiment and a future on-demand analysis are new semantics.
They require distinct field names, provenance, scale and freshness. They may not
reuse `sentiment_score`, `risk_score`, `scored_only` or the old table merely to
avoid a schema change.

### 3.4 Explicit score tools and routes

| Surface | Current behavior | Inventory verdict |
|---|---|---|
| `get_news_sentiment_summary` | defaults to 7 days, queries only scored rows, and labels the scored population `article_count` | legacy contract; retire rather than return a permanent zero capability |
| `GET /news/{ticker}/sentiment` | direct route to the same summary | retire with the tool |
| `search_news_advanced` score options | can expose old rows in a wide window without freshness | retire score options; preserve raw advanced search |
| tool registry + Anthropic/OpenAI bridges | advertises all of the above to the model | remove/evolve atomically; no dead advertised tool |

The default summary currently returns zero because coverage is zero, not because
there is no news. That distinction is absent from the response and is the most
direct user/model-facing contract defect.

### 3.5 Overview, profile and morning brief

| Surface | Current behavior | Candidate disposition |
|---|---|---|
| `get_watchlist_overview` | correctly obtains raw 7-day article counts, then also emits `sentiment_mean`/`bullish_ratio` | preserve price + raw news count; remove legacy fields |
| profile watchlist/universe routes | forward those two fields | remove fields after frontend DTO evolution |
| `get_morning_brief` | calls the score-only summary for one day; zero scored rows means recent raw news is omitted from `notable_news` | rewrite notable-news selection from raw news activity; do not retire the morning brief |
| Home/Watchlist/Universe TypeScript DTOs and fixtures | still carry sentiment fields | remove/evolve |

Current `Home.tsx`, `Watchlist.tsx`, and `Universe.tsx` do not render these
sentiment fields. Watchlist explicitly replaced the old LLM sentiment column
with analyst consensus. Frontend impact is therefore DTO/test cleanup, not loss
of a visible feature.

### 3.6 Monitor and signal surfaces

These are mixed features and must not be deleted wholesale.

| Surface | Score-bound part | Score-free part | Candidate disposition |
|---|---|---|---|
| `SentimentWatcher` | 7d-vs-30d average score shift | raw news-volume spike | split/rename; preserve volume alert, retire score shift |
| `detect_anomalies` | sentiment anomaly and its scored-only preload | news-volume anomaly algorithm | redesign input split so raw volume can survive without scores |
| `detect_event_chains` | fills missing sentiment with fabricated neutral `3.0` for impact | title-based event tagging and sequence detection | preserve event sequence only if impact semantics can become score-free/typed unavailable; never keep fake neutral as replacement evidence |
| `synthesize_signal` / `get_signal_factors` | sector, anomaly, risk and composite are built from legacy-scored news | no independent validated signal foundation in this implementation | likely retire until a new signal semantic is designed; product ruling required |
| `SignalWatcher` and `/signals/*` | expose the synthesis contract | none beyond the mixed helpers above | retire or narrow atomically with the chosen signal ruling |
| factor-rank | correctly reports `no_scored_news`, but still advertises a rank capability whose default input is empty | explicit missing-data mechanics | remove legacy factors; retain only if a separately meaningful factor remains |

At today's default 14/30-day windows the score-preloaded signal data frame is
empty. `synthesize_signal` can consequently return a HOLD-shaped object with a
failure explanation, while factor-rank routes everything to missing data. A
neutral-looking fallback must not survive Tranche B as if it were a valid
signal.

### 3.7 Model-visible contracts

The score capability is actively taught to the model even though current
coverage is zero:

- `src/agents/shared/prompts.py` lists news sentiment scores as available data,
  instructs scout-by-sentiment and recommends the sentiment summary;
- `src/agents/shared/subagent.py` repeats the same strategy;
- registry descriptions advertise sentiment summaries, scored filters,
  sentiment anomalies, synthesis, watchlist sentiment and sentiment alerts;
- Anthropic and OpenAI bridge schemas expose the same tools/arguments;
- `scan_alerts` copy advertises sentiment and signal scanning; and
- example query copy asks for current ticker sentiment.

This is the reason Tranche B remains product work despite the absence of a
visible web sentiment column. A model can select the capability, receive empty
or stale wide-window results, and turn those results into user-facing prose.

All model-visible descriptions, tool lists, schemas, allowlists and examples
must be part of the atomic consumer ledger.

### 3.8 Current authorities and tests

Tranche B must explicitly supersede/reconcile at least:

- `SCRIPTS_RETIREMENT_DECISION.md` section 5.3/6.2;
- `ARKSCOPE_TOOL_CATALOG.md` rule 9;
- `DESKTOP_APP_CARRYOVER_ANALYSIS.md` score preserve-adapt ruling;
- the obsolete 2026-06-23 score-retirement decision inside
  `DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md`;
- `ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md` Signals section's source-labeled,
  ephemeral, non-black-box contract;
- `PROJECT_PRIORITY_MAP.md` signal-validation deferral and its written
  hypothesis / OOS plan / kill-criteria gate;
- current layout/governance docs that keep `scripts/scoring`; and
- model/tool copy in current design authorities.

The signal-subsystem separation authority is also load-bearing: the Workbench
Product Spec requires source-labeled ephemeral signals rather than a black-box
composite, while the Priority Map records signal validation as deferred and
requires a written hypothesis, OOS plan, and kill criteria before that research
line can claim a validated capability. The older Tool Catalog
`synthesize_signal = preserve-adapt` ruling is therefore conditional on a clean
replacement semantic; it is not authority to preserve the current frozen-score
implementation unchanged.

The affected test family includes, at minimum:

- backend/schema/import: `test_sqlite_backend.py`, `test_news_score_import.py`,
  `test_news_scores.py`, `test_news_normalized_schema.py`,
  `test_market_data_admin.py`, `test_news_pg_unreachable.py`;
- tool/agent/API: `test_tools.py`, `test_agents.py`, `test_subagent.py`,
  `test_api.py`, `test_news_score_tool_parity.py`;
- analysis/monitor/signals: `test_analysis_pipeline.py`, `test_monitor.py`,
  `test_signal_factors_p1.py`, `test_evidence_packet.py`;
- frontend DTO fixtures: `Home.test.tsx`, `Watchlist.test.tsx`,
  `Universe.test.tsx`, plus `api.ts`.

This is an inventory, not the final node ledger. The implementation plan must
collect exact node identities and precompute backend/frontend target streams
before editing.

## 4. Preliminary product disposition

The code-grounded default for the Tranche B spec should be:

### Preserve and evolve

- raw news retrieval, keyword search and ticker filtering;
- raw article counts and date coverage;
- news-volume alerts/anomaly logic;
- title/event tagging and event sequence data, only with honest score-free
  impact semantics;
- morning brief and watchlist overview after removing score dependency;
- evidence-packet exclusion of derived scores; and
- future provider-native/on-demand sentiment as a new, separately designed
  semantic.

### Retire

- the 1-5 legacy score table contract and import/scoring executables;
- `scored_only`, legacy score model selection and score thresholds;
- legacy sentiment-summary route/tool;
- score-based sentiment anomaly, score-based monitor alert and the current
  unvalidated composite signal contract unless a new owner is explicitly
  designed;
- score fields in ordinary news/profile/frontend DTOs;
- prompts and descriptions claiming current scored-news capability; and
- the final root `scripts/` package after all consumers leave.

### Separate explicit decisions

- physical deletion of 491,808 production rows;
- deletion or migration of `config/scoring_keys.txt` without reading its
  contents; and
- any future sentiment/signal implementation.

## 5. Priority verdict

This inventory does **not** find an emergency where the current GUI visibly
labels a June score as today's score. It does find an active model-facing
contract that advertises unavailable current scoring, exposes historical values
on wide lookbacks without freshness, suppresses raw-news morning-brief content,
and can emit neutral-looking signal degradation.

Therefore:

1. OAuth lifecycle truth remains the first implementation slice because it is
   an active authentication/state failure affecting normal use.
2. Tranche B should proceed to product spec immediately after this inventory is
   independently reviewed; it should not fall behind unrelated large features.
3. The broader Settings navigation/performance slice may land before Tranche B
   because the current web UI does not render the old scores, but no new signal
   or news-score feature should be built on this contract.

Escalate Tranche B ahead of Settings polish if runtime observation finds a
common/default agent path returning a historical non-null score without an
explicit as-of/coverage warning. The current dated 7/30/90-day census does not
show that condition.

## 6. Reproduction commands

Consumer discovery must be repeated from an unlocked tree or explicitly account
for git-crypt files:

```bash
rg -n "news_article_scores|scored_only|sentiment_score|risk_score|scored_count|\
get_news_sentiment_summary|search_news_advanced|detect_anomalies|\
synthesize_signal|get_signal_factors|SentimentWatcher|SignalWatcher" \
  src scripts tests apps docs
```

Production counts must use SQLite URI `mode=ro` plus
`PRAGMA query_only=ON`. The implementation plan must pin the exact census
producer rather than parse prose or `rg` output into a destructive manifest.
