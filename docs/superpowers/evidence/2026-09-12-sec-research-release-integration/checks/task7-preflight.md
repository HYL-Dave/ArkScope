# Task7 Current-Code Preflight

This is a supplement to task-7-brief.md, not a second task/spec. Source inspected
atc4574800 while the disjoint Task6 publication repair proceeds. Do not start
Task7 product edits until that repair is independently reviewed and the
controller dispatches this task. Existing approved spec/plan are authoritative.

## Shared Interfaces And Rulings

| Tasks | Shared interface | Current finding / required disposition |
| --- | --- | --- |
| 1/7 | ResearchService.refresh, Store receipts | Today every refresh follows historical pointers and resumes latest receipt without scope. Add explicit recent acquisition and independently selected continuation; request count2 alone cannot implement this. |
| 1/3/7 | StoredQueries, ToolService, document catalog, pinned receipt IDs | Queries use latest receipt or an exact cursor receipt; ToolService uses latest for freshness/resume. Scheduled recent completion must be visible to stored readers with honest history coverage, while never satisfying/overwriting a pending full-history continuation. Preserve exact prior pins/citations. |
| 3/5/6/7 | Canonical schema, references, operations._verify_database and _COUNTS | New batch/continuation structures must participate in current shape/reset/backup/export verification. JSON-hidden bindings to issuer receipts must be validated, not just counted. No known-subset export that silently drops schedule scope. |
| 5/6/7 | research_operation, issuer_refresh, capture_writer | Use the existing operation lifetime for whole batch/reference publication and existing single-source scheduler exclusion. No second generic lock. Current writer publication-recovery repair precedes this task. |
| 7/scheduler | SourceDef / generic adapter dispatch | Generic adapter currently recognizes partial but treats failed/unavailable dicts as success. Add SEC-specific closed outcome mapping; leave news/macro contracts unchanged. |
| 7/scheduler | JobRunsLocalStore | Terminal enum is succeeded/failed, not partial. Preserve it: SEC partial remains partial in durable schedule/result, with audit failed plus bounded partial reason, as macro does. Do not broaden shared telemetry/schema just for this task. |
| 7/scheduler | source locks and market_writer_fired tick guard | Existing source threading/flock exclusion and per-tick market-writer backpressure already exist. Register the source with its declared flags and use these, not a new scheduler subsystem. |
| 7/universe | src.universe_scope.resolve_active_universe | It returns the authoritative list and propagates ActiveUniverseUnavailable. A valid empty list differs from read failure. Do not use the generic adapter's empty-is-failure ticker injection; the core owns this distinction. |
| 7/transport | SecTransport, IssuerStore.refresh/resolve | Map refresh is at most once per batch; resolve from that stored observation. Keep zero rate-limit retries and existing governor/checkpoints. Preserve16MiB metadata response limit; do not accidentally install the unrelated SecRequestBudget default12MiB total ceiling for a whole universe batch. |
| 7/UI | Settings data_sync provider / shared controls | Settings.tsx already wraps all data_sync sections in DataScheduleControlsProvider. DataStorageSection mounts SecResearchPanel inside it. Reuse the existing source-row toggle/interval/Run Now and poll lifecycle; no second enable key or independent schedule poller. |
| 7/UI | standalone SEC/document-reader fixtures | SecResearchPanel tests currently render without the shared provider. If consuming shared context, adapt those fixtures to the real owner contract rather than add a test-only production fallback. |
| 7/UI | config generation, dirty draft, remembered documents/cursors | A schedule terminal transition refreshes status/capacity only. Do not call readLocal/invalidate for pinned content and do not overwrite a dirty/saving budget. Ignore unrelated source completion. |
| 7/API | /sec-research/{cik} dynamic GET | Insert stored schedule-status before it. Reading status must not instantiate config/store constructors that install schema, contact SEC or launch work. Preserve actual write permission gates on commands. |

## Implementation Details Left To The Worker

Use a small SEC-owned batch store with explicit bounded shape validation and
durable intermediate/terminal receipts; pick the representation that fits the
existing immutable store. Implement current schema only, with explicit mismatch
on older shapes; no migration chain or auto-reset. Include all new structures
in verification/admin dependencies where their semantics require it.

Scope names: existing unqualified refresh remains full-history by default;
recent is explicit and used only by the new scheduler. Resume lookup must select
the requested scope, not the newest receipt of any scope. Stored unpinned reads
can show latest retained current data with history-not-requested coverage. Keep
old pinned results immutable even when a recent or full receipt arrives later.
Do not hide scheduled data from stored readers merely to avoid scope handling.

The declared15min wall budget controls checks before sources and through the
existing transport governor/body cancellation checkpoints. Safely unwind an
in-flight write rather than abandoning it at a hard timer. Do not claim that a
Python synchronous request is instantaneously preemptible. Record stop/defer
causes separately from confirmed acquisitions and retain a bounded timeout.
Request counts describe admitted source attempts, not successful HTTP responses;
map attempts count too. Check quota and deadline before any new source request.

Pending scope re-intersects fresh authoritative membership on every run. Retain
unresolved symbols separately from normalized/de-duplicated CIK dispatch. Finite
steady membership must not starve due to failing/deferred members or newly added
symbols; demonstrate rotation with small injected limits. Unavailable membership
does not clear previous continuation. Empty membership performs no map/issuer
request and does not advance the last actual acquisition timestamp.

Use failures with actual data truth: fully successful recent source acquisition
can be succeeded without pretending historical traversal happened; partial
committed issuer results stay partial; no current acquisition plus failure is
failed. Last attempted batch, latest committed successful acquisition and last
fully completed batch are distinct, not one timestamp. Unexpected/malformed
adapter results must never become succeeded.

## Known Collateral / Verification Owners

- tests/test_data_scheduler.py ACTIVE_SOURCE_IDS exact set, default-off loop and
  old-SEC journal-present/absent guards; add only the new source.
- tests/test_macro_scheduler_integration.py / test_macro_scheduler_outcomes.py,
  test_scheduler_state.py preserve unchanged mapping and writer coordination.
- SecResearchPanel.test.tsx, SecDocumentReader.test.tsx and relevant actual
  Settings integration fixtures if context is consumed.
- settingsBackendCopy.test.ts has an exact four non-macro source label inventory;
  add the new SEC source and localized copy, retain the old-source unknown guard.
- i18n/resources.test.ts exact namespace/total inventory: count actual new
  en/zh-Hant leaves, change only required counts, preserve exact equality guards.
- Existing SEC schema/receipt/cursor/fact/citation/trace/export/maintenance suites
  must cover new scope without changing registry/category/tool totals.
- New API owner checks stored status route placement, absence/invalid DB truth,
  current permissions and no acquisition; actual scheduler adapters test full
  and partial/failure results rather than stubbing run_source itself.
- Desktop/mobile, en/zh-Hant browser fixtures use real temporary HTTP/service/
  stores and injected remote bytes; no live App or supervisor start. Retain
  screenshots and measured overflow/overlap, dirty budget and pinned-reader
  stability across completion. Task-scoped full checks only; final backend run
  is controller-owned and must have no simultaneous runner or source edits.

No new provider/model/auth/dependency behavior, old SEC revival, actual schedule
enable or actual-store schema change is authorized. Worker owns product/index;
controller owns ledger/docs/evidence and independent review. No subagents.
