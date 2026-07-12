# AI Execution Usage Observability Design

> **Status: ADOPTED DESIGN, IMPLEMENTATION DEFERRED, 2026-07-12.**
> This document records a future product slice. It does not authorize an
> implementation plan or interrupt the current priority queue.

## 1. Problem

ArkScope can report token usage for some agent paths, but it cannot currently
answer the product-level questions the user needs:

- How much model usage did one user request cause in total?
- Which feature and operation initiated that usage?
- How many provider calls, retries, and subagent calls belonged to the request?
- How much time and how many input, output, cache, or reasoning tokens did each
  call consume?
- How much usage occurred today, this week, or during a selected period?

The fixed-task timeout live gate exposed the gap directly. Card synthesis and
translation completed successfully, but ArkScope discarded the Claude SDK's
duration and usage metadata, so the backend could not reconstruct the exact
per-task time or token split afterward.

## 2. Existing Grounding

This is an observability consolidation, not a new token-counting invention.

- `src/agents/shared/token_tracker.py` already extracts OpenAI and Anthropic
  input/output/cache usage for agent loops.
- `research_runs` and `research_messages` already persist AI Research usage;
  Research displays total tokens, turns, cache use, and elapsed time.
- Claude and ChatGPT OAuth research drivers already normalize provider usage.
- `research_reports` and `agent_queries` have older token and duration columns,
  but they are not an app-wide execution authority.
- `ai_card_runs`, card translations, calibration, model tests, and several
  other fixed model tasks have no shared usage ledger.
- The desktop carryover audit explicitly preserves token tracking, while the
  post-PG-exit UI plan explicitly deferred the token-monitoring UI.
- Historical `scripts/token_usage_summary.py` summarized offline CSV columns;
  it was retired as dead runtime code and is not the missing product feature.

Therefore the existing capability is partial and fragmented. There is no
canonical daily aggregation API or complete all-feature coverage contract.

## 3. Goals

1. Record every ArkScope-initiated LLM call, including desktop UI, CLI,
   background jobs, calibration, fixed tasks, retries, and subagents.
2. Group all calls caused by one user or system request under one root
   execution while preserving each call independently.
3. Classify initiating behavior with stable, reviewable product semantics.
4. Persist provider-reported token and duration metadata without inventing
   missing values or pretending providers use identical accounting.
5. Support daily and period aggregation plus drill-down from a root execution
   to its call tree.
6. Keep the ledger local-first, metadata-only, portable with the profile, and
   independent from raw prompts and generated content.

## 4. Non-Goals For V1

- Dollar-cost estimation or a pricing registry.
- Subscription quota prediction.
- Soft warnings, budgets, or hard execution limits.
- Prompt, response, tool-result, or reasoning-text storage.
- Cloud telemetry, multi-user billing, or external analytics export.
- Historical backfill from incomplete legacy records.
- A broad Settings or shell redesign.

## 5. Vocabulary And Classification

### 5.1 Execution

An execution is one meaningful initiating behavior. A user click or question,
a scheduled job, a CLI command, or a system recovery action creates an
execution before its first model call.

Every execution uses three independent classification axes:

- `feature`: the product area, such as `ai_research`, `ai_card`,
  `investor_profile`, `notes`, or `system`.
- `operation`: the requested action, such as `research`, `synthesis`,
  `translation`, `calibration`, `summarize`, or `model_test`.
- `trigger`: who initiated it, such as `user`, `scheduler`, `cli`, `extension`,
  or `system`.

These registries are code-reviewed authorities. Free-text classification is not
allowed because it would make aggregation drift silently.

### 5.2 Usage Event

A usage event is one observable provider/model call or attempt within an
execution. Every retry is a separate event. A subagent is represented as a
child execution whose events still share the original root execution.

### 5.3 Root, Parent, And Artifact Lineage

- `root_execution_id` groups the complete work caused by the initiating action.
- `parent_execution_id` represents nested work such as a subagent.
- `source_execution_id` links a later, separately initiated action to the
  execution it builds on without merging their root totals.
- `parent_event_id` represents nested or retry call relationships when useful.
- `artifact_type` and `artifact_id` link usage to an existing card, research
  run, calibration session, job run, note, or report without copying content.

A later user-triggered card translation, rerun, or regeneration is a new
root execution. It links to the original card and may use the generation
execution as its `source_execution_id`; it is not a child of the earlier user
action. Automatic provider or effort retries remain separate events inside the
execution that initiated them. This preserves both per-action usage and
whole-artifact lifecycle totals.

## 6. Storage Model

The usage ledger lives in `profile_state.db` and follows the repository's
SQLite WAL and busy-timeout discipline.

### 6.1 `ai_usage_executions`

Conceptual fields:

- `id` - UUID generated before model work begins.
- `root_execution_id` - self for roots; inherited by descendants.
- `parent_execution_id` - nullable self-reference.
- `source_execution_id` - nullable cross-root lineage for later user actions.
- `feature`, `operation`, `trigger` - canonical classifications.
- `status` - `running`, `succeeded`, `failed`, `timeout`, `cancelled`, or
  `interrupted`.
- `artifact_type`, `artifact_id` - nullable heterogeneous reference.
- `started_at`, `completed_at` - UTC timestamps.
- `instrumentation_version` - identifies the coverage contract in force.

### 6.2 `ai_usage_events`

Conceptual fields:

- `id`, `execution_id`, `parent_event_id`, `sequence`, and `attempt`.
- `provider`, `requested_model`, `resolved_model`, `effort`, `auth_mode`, and
  local `credential_id` where known.
- `status`, `error_code`, `started_at`, and `completed_at`.
- `duration_ms` measured by ArkScope and nullable `provider_duration_ms`.
- Nullable `input_tokens`, `output_tokens`, `total_tokens`,
  `cache_creation_tokens`, `cache_read_tokens`, and `reasoning_tokens`.
- `usage_source` such as `provider_response`, `sdk_result`,
  `derived_input_output`, or `unavailable`.
- Optional numeric-only provider/model usage breakdown for SDKs that report
  multiple internal models. Arbitrary provider payloads are not persisted.

The tables are append-oriented. Rows may transition once from `running` to a
terminal status and receive their final metrics, but completed records are not
rewritten or silently deleted.

Indexes cover UTC start time, classification axes, provider/model, status,
root execution, and artifact reference.

## 7. Correlation And Capture

1. The outer product action creates an execution before its first provider
   call. Existing `research_run`, `job_run`, calibration-session, and CLI
   session IDs become lineage anchors rather than competing usage stores.
2. A typed `UsageContext` carries execution identity. In-process async and sync
   work may use `ContextVar` as a convenience, but explicit IDs are required at
   worker, subprocess, or serialization boundaries.
3. Each provider adapter records an event before dispatch and finalizes it after
   success or failure. Provider wrappers, not UI routes, own token extraction.
4. Retries create new attempts under the same execution. Hidden provider retries
   are reported only when the SDK exposes them; ArkScope does not fabricate
   attempts.
5. Subagents create child executions and retain the root ID of the originating
   user request.
6. If the process restarts with `running` rows, startup reconciliation marks
   them `interrupted`.

Existing `TokenTracker` and Research persistence remain compatibility consumers
during migration, but normalized extraction converges on one recorder. The
system must not permanently maintain two independent token-accounting rules.

## 8. Metric Semantics

- Provider-reported fields are preserved under their actual meaning.
- `total_tokens` uses a provider-reported total when available. Otherwise it is
  derived as input plus output and marked `derived_input_output`.
- Cache creation/read and reasoning tokens remain separate. They are not folded
  into a cross-provider total with guessed semantics.
- Missing fields are `NULL`, never zero.
- ArkScope wall-clock duration is measured for every event that reaches a
  terminal state. Provider duration is stored separately when available.
- Root execution elapsed time is `completed_at - started_at`. Provider-call
  time is the sum of event durations and is reported under a different label;
  it may exceed elapsed time when calls overlap or child work runs in parallel.
- A failed or timed-out call still records duration and status even when no
  token usage is returned.
- No V1 field claims dollar cost. Future cost calculation can join historical
  usage with a separately approved, versioned pricing registry.

## 9. Coverage Contract

Implementation begins with an uncapped inventory of every model-call seam. A
code-reviewed coverage registry marks each seam `instrumented` or records a
specific exclusion and reason.

At minimum the inventory covers:

- API-key and subscription AI Research loops.
- Card synthesis and translation across both providers and auth modes.
- Investor-profile calibration.
- Model/task canaries and probes that perform real calls.
- CLI agent runs and subagents.
- Background summarization, scoring, skills, and future note assistance.
- Provider retries and effort retries observable by ArkScope.

The UI must not display an unqualified "ArkScope total" until the active
coverage version is complete. During staged rollout it displays the coverage
state and the tracking start timestamp.

## 10. Query API

The read surface is additive and read-only:

- `GET /ai/usage/summary`
- `GET /ai/usage/executions`
- `GET /ai/usage/executions/{execution_id}`

Summary and list queries support UTC ranges plus an explicit IANA timezone,
feature, operation, trigger, provider, model, and status filters. The summary
returns execution count, call count, token breakdowns, root elapsed time,
provider-call time, success/failure/timeout counts, and coverage metadata.

Detail returns one execution, child executions, and an ordered usage-event
tree. It never hydrates prompt or response content from linked artifacts.

## 11. Product Surface

The global dashboard belongs under **System -> AI Usage**, not Settings.
Settings remains the future home for controls such as retention, warnings, or
pricing policy if those features are separately approved.

V1 dashboard:

- Time ranges: today, 7 days, 30 days, and custom.
- Explicit display timezone; default to the desktop/browser timezone.
- Filters for the three classification axes, provider, model, and status.
- Compact totals for executions, calls, input/output/cache/reasoning tokens,
  root elapsed time, provider-call time, and terminal outcomes.
- One row per execution, expandable to its provider-call and subagent tree.
- Clear `unavailable` and partial-coverage states instead of zero-filled data.

Contextual surfaces remain small:

- AI Research shows the execution summary already associated with the run.
- AI Card shows separate generation and translation executions.
- Other features may show a short usage summary and link to the System detail.

No dashboard is added to the current oversized Settings surface.

## 12. Failure And Health Behavior

Usage recording is best-effort relative to the user's model task: a local
telemetry write failure must not turn a successful research/card result into a
failure. It also must not remain invisible.

- Health reports `ok`, `degraded`, or `unavailable` usage recording state.
- Recorder errors are secret-safe and rate-limited in logs.
- The dashboard shows recording gaps and the last successful event timestamp.
- A provider failure still finalizes its usage event when possible.
- Usage instrumentation never introduces provider/model/credential fallback.

## 13. Time, Retention, And History

- Store all timestamps in UTC.
- Aggregate calendar days using the explicit requested IANA timezone.
- V1 retains metadata indefinitely; no deletion or retention control ships.
- Usage remains part of the local profile and follows profile portability.
- Do not backfill legacy records. Existing Research usage is incomplete across
  product features and has multiple historical shapes. The dashboard displays
  "tracking since" the first complete coverage version instead.

## 14. Deferred Decisions

- Soft warnings and daily/monthly budgets.
- Hard execution limits.
- Versioned model pricing and historical dollar estimates.
- Subscription quota semantics.
- Retention controls and export formats.
- Any content-level analysis beyond artifact references.

## 15. Future Implementation Slices

Implementation is deliberately not next in the queue. When reprioritized, use
three separately reviewed slices:

1. **Capture foundation**: schemas, recorder, correlation context, full seam
   inventory, all-call coverage, reconciliation, and health.
2. **Read surface**: aggregation queries, APIs, timezone behavior, and
   contextual execution summaries.
3. **System UI**: period dashboard, filters, execution tree, and links from
   existing features.

Do not open an implementation plan until the priority map explicitly promotes
slice 1.

## 16. Acceptance Criteria

1. Every inventoried ArkScope LLM seam is instrumented or explicitly excluded.
2. One AI Research request groups every turn, retry, and subagent beneath one
   root execution without losing individual call records.
3. A user-triggered translation is a separate root execution linked to its
   source card and generation execution without merging their root totals.
4. Feature, operation, and trigger values come from canonical registries.
5. Unknown token fields remain null and provider semantics remain distinguishable.
6. No prompt, response, tool output, authentication token, credential secret,
   or arbitrary raw provider payload is copied into usage metadata. Token
   counts and the local non-secret `credential_id` remain allowed.
7. Recording failure does not fail the user task and is visible in health/UI.
8. UTC storage and timezone-aware daily boundaries have direct tests.
9. Every event, including each retry attempt, is counted exactly once; legacy
   compatibility rows are not added to the same aggregate again.
10. The dashboard identifies its coverage version and tracking start time.

## 17. Decision Record

The user approved the following on 2026-07-12:

- Track all ArkScope LLM calls, not only desktop-visible calls.
- Preserve one root user request plus independently inspectable child calls.
- Use `feature / operation / trigger` classification.
- Treat later translation/retry/regeneration as new linked executions.
- Keep usage metadata-only.
- Defer all dollar-cost, pricing, warning, and limit decisions.
- Ship observation before control.
- Record this design now but defer implementation so unfinished core product
  work retains priority.
