# Scripts Tranche B Legacy Score Product Decision

> **Status:** PRODUCT DECISION AND TRAINING RULING APPROVED; TASK 0 PHASE D/
> POSTGRESQL OWNER-CLOSURE AMENDMENT REVIEW PENDING
> **Date:** 2026-08-08
> **Base inventory:** `098dff564faea1fc2617e198414ccde6067f23f8`
> **Scope:** Per-surface disposition of the frozen 1-5 news score contract, the
> remaining `scripts/scoring/` transition layer, the separately approved
> retirement of the disconnected offline `training/` lineage, and Task 0's
> proposed no-tail disposition of the current recommendation-shaped Phase D
> scaffold. This document
> does not authorize implementation, score-row deletion, or secret deletion.

## 1. Decision to make

Tranche A removed spent root scripts and deliberately retained the nine-path
scoring transition layer until product consumers could be judged together.
The reviewed inventory now establishes:

- 491,808 score rows are one frozen 2026-06-07 batch whose newest represented
  article is 2026-04-27;
- current 7/30/90-day normalized news has zero legacy-score coverage;
- no current web component renders the legacy score fields;
- agent prompts, tools, schemas, wide lookbacks, morning brief, monitors, and
  composite signal routes still teach or consume that semantic; and
- missing score values can suppress raw news or be fabricated as neutral `3.0`.

The product choice is therefore not whether to preserve old data for its own
sake. It is which user/model capabilities survive after an obsolete semantic is
removed, and what must remain absent until a valid replacement exists.

## 2. Authority reconciliation

### 2.1 Reviewed evidence input

`docs/design/SCRIPTS_TRANCHE_B_CONSUMER_INVENTORY.md` at `098dff56` is the
complete read-only input. Its production counts are dated observations, not
acceptance constants. Implementation must repeat the consumer census and build
an exact node ledger.

### 2.2 Product authorities

The following current rules govern this decision:

1. `ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md` section 2 requires objective,
   source-labeled evidence and forbids hidden re-scoring.
2. Its Signals section defines future signals as ephemeral opportunity/risk
   events with `as_of`, `expires_at`, source coverage, and evidence references;
   a black-box composite is not objective evidence.
3. `ARKSCOPE_TOOL_CATALOG.md` rule 9 excludes ArkScope-generated LLM scores from
   the AI-card EvidencePacket by default and explicitly reserved their final
   disposition for this later pass.
4. The Tool Catalog's older `synthesize_signal = preserve-adapt` ruling is
   conditional on adaptation into a clean, traceable evidence signal. The
   inventory proves the current implementation does not meet that condition.
5. The Priority Map records that signal validation and entry/exit semantics were
   deferred, and that signal work requires a written hypothesis, out-of-sample
   plan, kill criteria, and cost-versus-value evidence.
6. `evidence_packet.py` is an existing negative contract: legacy score and
   composite outputs do not enter objective evidence.

This spec does not reject a future signal capability. It rejects reusing the
frozen score scale and unvalidated composite as if that future capability had
already been built.

## 3. Proposed product decisions

The following are recommendations for one explicit user ruling. They are not
implementation authorization until the status changes after review and user
approval.

### PD 1 - Retire the legacy score semantic atomically

Retire as one reviewed product cutover:

- `news_article_scores` as a runtime contract;
- the 1-5 sentiment/risk model-selection and aggregation helpers;
- `scored_only`, `min_sentiment`, `max_risk`, score-model selectors, and score
  fields in ordinary-news interfaces;
- `get_news_sentiment_summary` and `GET /news/{ticker}/sentiment`;
- score import/scoring/validation executables and the final tracked
  `scripts/scoring/` package;
- prompt/tool/example copy claiming current scored-news availability; and
- `src/daily_update.py` score importer options/tombstones.

No compatibility endpoint may return permanent zeros while retaining the old
capability name. No new provider-native or on-demand sentiment may reuse these
field names, table, 1-5 scale, or cache identity.

### PD 2 - Preserve ordinary news without score-bearing DTOs

Keep and evolve:

- ticker news retrieval;
- keyword/full-text search;
- source/ticker/date filters and pagination;
- article count, earliest/latest date, source breakdown, title, timestamp,
  source, URL, and excerpt;
- normalized-news and Seeking Alpha surfaces; and
- EvidencePacket's objective raw-news rows.

`NewsArticle`, `NewsBrief`, `NewsQueryResult`, DAL protocols/backends, API DTOs,
frontend DTOs, registry schemas, and both model bridges remove legacy
sentiment/risk fields together. A raw-news request cannot acquire old scores
merely because a historical row happens to exist.

### PD 3 - Preserve morning brief; rewrite notable news from raw activity

`get_morning_brief` stays. Its `notable_news` is rebuilt from the same score-free
news-stat authority as ordinary overview behavior:

- one batch query over the tracked/watchlist universe;
- fixed one-day window under the existing news date contract;
- include only tickers with raw `article_count > 0`;
- deterministic order: `article_count DESC`, then `latest_date DESC`, then
  `ticker ASC`;
- return at most five rows with `ticker`, `count`, and `latest_date`;
- remove `sentiment_mean` and every inferred direction label.

An empty list means no raw articles in the selected tracked universe/window, not
"no scored articles". Price holdings and sector-highlight behavior remain
outside this decision.

### PD 4 - Preserve watchlist/profile overview; remove score fields

`get_watchlist_overview` keeps price change and raw seven-day news count.
Profile/watchlist/universe APIs and TypeScript DTOs remove
`sentiment_mean`/`bullish_ratio`. Current GUI behavior is preserved because
those fields are not rendered. No replacement neutral/zero sentiment field is
added.

### PD 5 - Preserve raw news-volume detection under an honest name

Split the mixed anomaly/monitor contract:

- preserve deterministic news-volume spike/anomaly behavior based on raw
  article counts;
- rename `SentimentWatcher` to `NewsVolumeWatcher` and emit a news-volume alert
  type/title, not a sentiment alert;
- evolve `detect_anomalies` into a score-free `detect_news_volume_anomaly`
  contract; the old tool name leaves the registry and both bridges;
- remove sentiment-shift branches, scored-only preload, and score thresholds;
- keep price and other independent monitor families untouched.

This is an explicit tool/schema rename, not a hidden semantic swap under a
sentiment name.

### PD 6 - Preserve event-chain sequence; make numeric impact unavailable

Title-based event tagging and deterministic sequence detection remain useful.
`detect_event_chains` therefore survives, but its output changes:

- keep `pattern`, `event_count`, `start_date`, `end_date`, `ticker`, and each
  event's `date`, `event_type`, and `title`;
- remove numeric `impact_score` and per-event `sentiment_impact`;
- add one closed typed field on each chain:

```json
{
  "impact": {
    "status": "unavailable",
    "reason": "legacy_score_retired"
  }
}
```

Do not fill missing evidence with `3.0`, derive direction from title words, or
invent another score in this slice. A future impact semantic requires its own
source/provenance/validation design and a new versioned field.

### PD 7 - Retire the current composite signal and ranking surfaces now

Retire atomically:

- `synthesize_signal`;
- `get_signal_factors`;
- `_SignalContext` and current score-coupled synthesizer orchestration;
- `SignalWatcher`;
- `/signals/{ticker}` and `/signals/factor-rank` composite/factor contracts;
- recommendation-shaped `TradingSignal` use owned only by this line;
- registry, Anthropic/OpenAI bridge, subagent/prompt/example exposure; and
- tests that pin the retired recommendation/rank semantic.

The `/signals` router may be removed entirely. Preserved raw volume and event
chain reads may live as tools and, only if a current HTTP consumer exists, move
to score-free `/news/...` routes in the same atomic cutover. Do not keep a dead
`/signals` namespace solely for compatibility.

The future Signals product remains committed conceptually, but reopens only
under a new semantic id after all of these exist:

1. written hypothesis and intended regime/universe;
2. objective source-labeled inputs and coverage contract;
3. explicit `as_of`, expiry, freshness, and evidence references;
4. out-of-sample validation plan and thresholds;
5. kill criteria;
6. no recommendation/prediction claim beyond demonstrated evidence.

Removing an unvalidated implementation does not retire the product goal.

### Post-approval implementation ruling - preserve capability, remove the legacy namespace

The user clarified after approving PD 1-PD 8 that retirement must not leave a
compatibility-shaped architecture tail. The approved PD 5 and PD 6 behaviors
survive as capabilities, not as an excuse to preserve the old Signals package:

- move deterministic raw news-volume, title-event tagging, and event-sequence
  logic into the score-free `src/news_analytics.py` owner;
- expose the two surviving agent contracts from
  `src/tools/news_event_tools.py`;
- delete the complete `src/signals/` package and
  `src/tools/signal_tools.py`, including their README, exports, old scorer
  recommendations, numeric-impact machinery, and composite helpers;
- add no compatibility import, re-export, alias module, dead `/signals` route,
  or old `TestSignalTools` test namespace; and
- update `evidence_packet.py` comments/current copy that name the retired module
  while preserving its negative evidence contract.

The replacement core keeps only the behavior PD 5-PD 6 approved. It does not
carry `LLM_TAGGING_PROMPT`, same-direction sentiment fallback, neutral `3.0`,
numeric impact thresholds/multipliers, `SentimentAnomaly`, or sector sentiment.
Event chains remain tool-only unless a later product requirement establishes an
honest HTTP owner. A future Signals product starts from a new semantic and new
owners under the six gates above; it does not reopen these namespaces.

Task 0's exact owner census also closed a broader tail that the first plan named
only partially. The current `src/analysis/` Phase D scaffold is not a generic
evidence pipeline: its default chain consumes the retired 1-5 sentiment field,
computes a weighted composite, and emits `buy`/`hold`/`sell` recommendations
through an enabled API route, scheduled job, and CLI commands. Retiring only
`pipeline.py`, `DecisionStrategy`, and `SentimentStrategy` would leave the
factory, service, renderer, route, job, CLI, feature flag, templates, and tests
broken or ownerless. The cutover therefore retires that complete scaffold and
its current surfaces. It does not opportunistically replace it with a new
analysis semantic in this line. A future on-demand analysis product follows the
same new-design, provenance, validation, and kill-criteria discipline as future
Signals.

The same census found two executable PostgreSQL authorities omitted from the
first grouped owner map. `sql/002_add_news_scores.sql` leaves completely, while
`sql/001_init_schema.sql` remains only after its news score columns, `signals`
table/index/RLS example, and sentiment-summary function are removed. Existing
production databases remain outside this source-only cutover.

The only physical artifacts temporarily unchanged by this code cutover are the
491,808 production rows and `config/scoring_keys.txt`, because the user
explicitly reserved their destructive disposition for later exact approval.
They are not future Signals dependencies, are not runtime compatibility
surfaces, and may not be read by the cutover.

### PD 8 - Model-visible and UI-visible contracts leave together

The product cutover must update in one reviewed change:

- tool registry names/descriptions/parameters;
- Anthropic and OpenAI bridge schemas and dispatch;
- shared prompts, subagent allowlists/strategy copy, examples, and tool counts;
- route registration and DTOs;
- morning brief/watchlist/profile behavior;
- monitor configuration/copy;
- frontend types/fixtures even where fields are not rendered;
- current design/layout/tool authorities; and
- all tests that teach the model or developer the retired capability.

The agent-facing surface is a user-facing surface. It cannot continue teaching
dead score tools after the GUI appears clean.

## 4. Data, credential, and history disposition

### 4.1 Tracked code and history

Tracked scoring executables are deleted rather than archived in-tree. Git
history plus the existing scoring history/decision docs are the archive. Root
`scripts/` disappears after the last package marker and scoring files have no
consumer.

Historical docs may describe the old pipeline but must be marked historical;
current authorities must not instruct operators or models to run it.

### 4.2 Production score rows

Product cutover first stops all table readers/writers and stops creating the
table in fresh schemas. Existing `news_article_scores` rows remain physically
untouched through implementation and merge.

After merged rollout proves zero current consumer/writer, a separate read-only
Task first records whether the frozen dataset has any concrete, named research
use. A claim of possible future usefulness is insufficient: the packet must
identify its provenance, reproducibility value, semantic limitations, research
owner/hypothesis, and why raw news plus Git history cannot satisfy that need.
The user receives those details before choosing one of two closed outcomes:

1. exact deletion, which is the default when no named use survives; or
2. an independently approved move out of the runtime DB into a versioned,
   explicitly historical research artifact with no product reader or writer.

Keeping the rows connected to the runtime DB is not an outcome. Neither outcome
reuses the old score as the semantic basis of the future Signals product.
Physical table/row deletion requires:

- fresh read-only counts and schema/DB identity;
- exact retained-table invariants;
- stopped writers;
- rollback snapshot/controller probe;
- independent review; and
- a separate user approval naming the exact manifest authority.

No wildcard, date-range guess, or this product ruling itself authorizes delete.

### 4.3 `config/scoring_keys.txt`

Never read, hash, print, or copy its contents into evidence. After tracked
scoring consumers are gone, inspect only metadata and consumer paths. The user
then chooses one of two closed outcomes:

1. exact-path delete with separate approval; or
2. migrate the secret to a named future credential owner whose active feature
   already exists.

"Keep without owner" is not an outcome. A hypothetical future sentiment feature
does not count as an owner.

## 5. Compatibility and migration rules

1. No permanent deprecated endpoint/tool that returns zero or unsupported
   while still advertising old sentiment capability.
2. No score table read after cutover, including wide lookbacks, file fallback,
   admin/status, monitoring, examples, or tests.
3. No replacement sentiment default (`0`, `3`, `neutral`, HOLD) where evidence
   is absent.
4. New provider-native sentiment, analyst labels, or on-demand model analysis
   must use a new provenance-bearing DTO/cache/schema and cannot enter this
   implementation opportunistically.
5. Raw news and score-free volume/event behavior must remain independently
   testable; deleting the composite cannot delete those primitives by accident.
6. Existing EvidencePacket exclusion remains a protected negative contract.
7. Tranche B does not add a new scheduler, scorer, model request, provider call,
   or paid feature.

## 6. Required RED-first implementation-plan contracts

The later implementation plan must collect exact backend/frontend identities
before edits and independently cover at least:

1. ordinary news DTOs contain no legacy score fields;
2. advanced raw search retains query/ticker/source/date behavior and rejects old
   score filters at the contract boundary;
3. score summary tool/route/registry/bridges are absent together;
4. morning brief with raw articles and zero score rows still lists notable news;
5. morning brief deterministic tie ordering;
6. watchlist/profile outputs keep raw counts and remove sentiment fields;
7. news-volume anomaly works with raw-only fixtures;
8. old sentiment anomaly/watcher names are absent;
9. event chains retain sequence fields and return exact typed unavailable
   impact without numeric substitutes;
10. composite/factor tools, watcher, routes, prompts, bridges, the complete
    `src/signals/` package, and `src/tools/signal_tools.py` are absent with no
    compatibility re-export;
11. the recommendation-shaped Phase D scaffold, `/analysis/run`, its scheduled
    job, CLI commands, feature flag, and current capability claims are absent;
12. model-visible capability census contains no score/sentiment/composite claim;
13. EvidencePacket still rejects generated score/composite input;
14. fresh SQLite and PostgreSQL source schemas create no legacy score storage,
    score columns, `signals` table, or sentiment-summary helper;
15. runtime consumer/writer census is closed and fail-closed;
16. final tracked `scripts/` tree is empty/absent;
17. production score rows and `scoring_keys.txt` remain byte/row untouched during
    product implementation.

Mutation tests must prove that reintroducing score projection, neutral `3.0`,
the old prompt/tool name, a composite route, or a scorer writer turns an owning
node RED.

## 7. Surface disposition table

| Surface | Decision | User/model result after cutover |
|---|---|---|
| raw ticker news/search/feed | preserve | same raw articles and filters, no score fields |
| sentiment summary route/tool | retire | capability no longer advertised; raw news remains |
| morning brief | rewrite/preserve | recent raw-news activity appears even without scores |
| watchlist/profile summaries | evolve | price + raw news count remain; hidden score DTO fields leave |
| sentiment anomaly | retire | no stale/empty score inference |
| news-volume anomaly/alert | rename/preserve | explicit raw count anomaly with score-free name |
| event chains | evolve/preserve | sequence remains; impact explicitly unavailable |
| composite signal/factors/rank | retire | no HOLD/score/recommendation from unvalidated empty inputs |
| future Signals product | separate | reopens only with new semantic and validation gate |
| score table rows | separate disposition gate | runtime-disconnected; exact delete by default unless concrete historical research value earns detailed approval |
| scoring secret | separate owner/delete gate | contents never enter tracked evidence |

## 8. Product approval requested

The recommended approval is one bundle:

1. approve PD 1-5 and PD 8 as the score-contract retirement/evolution core;
2. approve PD 6: keep event sequence, remove numeric impact, return typed
   `legacy_score_retired` unavailability;
3. approve PD 7: retire current composite/factor/rank implementation now while
   retaining the future Signals product behind a new semantic + OOS gate;
4. keep physical score-row and secret disposition behind their later exact
   approvals.

If any of items 2-3 is rejected, stop before an implementation plan. Do not
quietly preserve the old score semantic as a compromise.

### 8.1 Approval record

On 2026-08-08 the user explicitly approved `04dd9a67` PD 1 through PD 8 as the
single section 8 bundle. The normalized authority record is: execute PD 1-8;
the 491,808 rows and `scoring_keys.txt` still require later separate approval.
The user then clarified that implementation must remove the legacy Signals
namespace completely while retaining the future Signals research goal, and
that deferred data must be assessed by concrete use rather than retained by
default.

On 2026-08-09 the user superseded the older `paused-preserve` ruling for
`training/`. The offline RL implementation has no `src/`, app, scheduler, or
runtime consumer; its eight external test owners test only that implementation.
The complete lineage may therefore retire in the same reviewed cutover. The
authoritative disposition is direct Git deletion: no archive directory, copy,
compatibility package, disabled scaffold, preservation branch, or dedicated
tag. The parent commit already preserves the exact bytes, and eventual normal
repository publication preserves that history remotely. Future RL, options
estimation, and Signals research remain valid product goals, but must begin from
their then-current provider/data contracts and a new hypothesis/OOS/kill gate;
the retired implementation is not their scaffold.

The deletion must also be self-explanatory in ordinary Git history. Its atomic
product commit may not use a generic `cleanup` or `remove old code` description.
The commit subject/body must identify the disconnected training lineage and
legacy score/signal contract, the exact retirement ledger, the capabilities
that remain, the new-design rule for future research, and the production rows
and scoring secret that were deliberately not touched.

This approval authorizes an exact RED-first implementation plan and, after
independent plan review, the atomic product cutover described by PD 1-8. It
does **not** authorize reading or deleting the scoring secret, deleting or
mutating any production score row, or constructing a destructive manifest as
part of the product implementation.

## 9. Sequence after approval

1. OAuth lifecycle/quota, provider hygiene, and Settings navigation/warm-cache
   are merged and independently closed without adding or caching legacy score
   data.
2. The exact Tranche B RED-first plan and relative node/disposition ledger are
   independently GREEN. Its one-time post-handoff absolute-identity amendment
   requires focused review before Task 0 or product edits.
3. After focused review of the user-approved training-retirement expansion,
   finish Task 0 and execute one atomic product cutover without compatibility
   tails. The training family and legacy score/signal family leave together;
   neither may be parked in an archive branch or disabled namespace.
4. Merge and verify Tranche B product cutover before any destructive manifest.
5. Build, review, and approve physical score-row research-use/deletion and secret
   disposition separately; no row may remain connected to runtime.

Calendar-aware market scheduling, Financial Datasets metered policy, and future
fundamentals ingestion are independent and do not enter this line.
