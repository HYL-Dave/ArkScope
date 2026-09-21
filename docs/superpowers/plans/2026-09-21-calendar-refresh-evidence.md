# Calendar Evidence and Refresh Decisions

Durable cross-source policy:
[Data Acquisition And Updates](../../../DATA_ACQUISITION_AND_UPDATES.md).
This dated plan owns the bounded implementation and acceptance evidence, not a
separate version of the ongoing trigger/freshness contract.

## Decision

The financial seven-day reuse window is a fallback, not the final refresh model.
Neither a successful fetch nor a cache read establishes the latest available
period. A repeated fetch of the same financial version must not move a known
next-publication anchor another quarter into the future.

Refresh decisions need dataset-specific evidence:

| Data | Decision | Explicit control |
| --- | --- | --- |
| Period financials | Reuse an identified provider/period/version. Calendar events are hints to check provider availability, not proof that normalized statements are ready. | Stored / automatic / force refresh; paid admission remains independent. |
| News | Incremental collection for a source, symbol and covered interval, with overlap/deduplication. A completed empty response can advance checked coverage; a failed response cannot. | Scheduled collection or requested catch-up; join only an equivalent in-flight scope. |
| SA captures | Reuse the latest completed local capture; article body and comments have separate outcomes. Browser collection is not an instantaneous API. | Explicit collection when needed and possible. |
| Current quotes / portfolio | Live observations or a declared short tolerance, with feed type and observation time. | Never inherit quarterly financial reuse rules. |

For a later event-aware financial slice, keep `last_checked_at`, data period and
version, and an absolute `next_check_at` distinct. Before extending reuse to a
future earnings event, establish that the requested provider/dataset covers the
latest relevant released period. Otherwise remain in a pending/unknown state and
perform bounded, authorized checks. A new calendar date, a provider revision or a
missing statement may invalidate that decision. No anchor means the configured
fallback interval, not an invented 90-day publication schedule. Force refresh
remains possible, but the same period returned again is not evidence of the next
quarter's availability. Do not promise a maximum provider lag or request saving
without measurement.

## Verified Starting Point

Read-only production inspection on September 21 found zero earnings events and
zero revisions. Job 29571 (`fetch_earnings_calendar`, September 18) records
`trigger_source=api`, success, and four zero counters, with no raw-response or
query-scope evidence. This does **not** prove a failed scheduled collection:
genuine empty windows and unchanged data are legitimate successful outcomes.
The existing default request covers today through 30 days ahead, so it cannot
establish an earnings date 70 or 90 days away.

Offline reproductions did prove two defects:

1. Missing envelopes, HTTP-200 error objects and rejected rows can collapse to an
   empty calendar, making the persisted result indistinguishable from no events.
2. `report_date` changes for the same symbol/year/quarter are treated as unchanged.
   Updating only the canonical date would also rewrite as-of history, since that
   read currently takes its date from the canonical row.

## This Slice

- [x] RED-first malformed/empty/partial response and date-revision tests (43 failed, 1 passed before repair).
- [x] Validate calendar envelopes; retain accepted/rejected row counts.
- [x] Persist sanitized per-request scope and response receipts through job normalization.
- [x] Track corrected earnings dates; as-of filtering uses the observed revision date.
- [x] Related regression (698 passed) and one standalone complete backend run (11,911 passed / 12 unchanged skips).
- [x] Commit, merge and remove only this slice's temporary branch/worktree after verification.

Frozen implementation: `30682b5199e4f13e8f91215f6bc037ee6a30b34c`. Frontend:
1,867 passed / 124 files; typecheck/build, i18n and eight desktop tests pass.
Evidence: `docs/superpowers/evidence/2026-09-21-calendar-refresh-evidence/README.md`.
Master fast-forwarded to `86937e34` and passed 758 related/document-contract
checks. Product, configuration and test bytes match the frozen revision. This
slice's detached worktree and branch are removed; no push was performed.

Keep the existing schema: the earnings revision's structured `source_payload`
already stores the provider's `date`. Ensure new writes include a consistent date;
do not infer an unavailable old revision date from a newer canonical row. Missing
historical date evidence must be reported unavailable rather than fabricated.

This slice does **not** enable calendar-based financial expiry, implement a new
generic refresh engine, activate paid requests/webhooks, change news retention,
start the App, or mutate production data. Event-aware financial integration and
scope-aware scheduled/on-demand catch-up remain explicit subsequent work.

## Provider Availability

Official FD documentation distinguishes earnings events from processed statement
events (`income_statements.created`, `balance_sheets.created`, and
`cash_flow_statements.created`). Provider-native availability events could be
better evidence than estimating when a calendar event becomes normalized data.
They are not assumed available under this user's credit balance; account access,
cost, receiver lifecycle and revision handling need separate verification.

Sources checked September 21:
- [FD event types](https://docs.financialdatasets.ai/webhooks/events)
- [FD company earnings](https://docs.financialdatasets.ai/api/earnings)
- [FD provenance](https://docs.financialdatasets.ai/data-provenance)

No provider API or billable availability probe was called for this inspection.
