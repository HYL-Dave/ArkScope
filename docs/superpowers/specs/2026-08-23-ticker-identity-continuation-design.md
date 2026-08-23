# Ticker Identity Continuation Design

**Status:** Design authority for the P0-E action-executor follow-on. This
document does not authorize production writes, provider calls, or a live
migration.

**Date:** 2026-08-23

**Implementation:** Tasks 0-7 and the first five independent-review repairs
reached self-admission through `2118f0ab`, but independent re-review returned
RED. A provider-observation change can still fail before durable
`needs_review`, and a request carrying an old approval digest can apply a plan
that was concurrently re-approved under a new digest. TEMP side-effecting
schema objects and crash-durable restore publication are in the same bounded
second repair. Earlier GREEN counts are historical evidence only. No live
preflight, backup, migration, provider call, merge, or push has been performed
for this slice.

**Depends on:**

- `docs/superpowers/specs/2026-08-19-security-lifecycle-investigation-design.md`
- the completed P0-E investigation migration and UI at `master`

## 1. Goal

Turn an explicitly accepted security-lifecycle conclusion into a safe,
reviewable tracking transition:

- a terminal delisting can retire the user's obsolete tracking state;
- a simple `A -> B` symbol continuation adds or restores `B` before archiving
  user-owned tracking for `A`;
- a same-symbol venue transfer remains tracked and produces no fake symbol
  remap;
- notes, research, market history, broker positions, and provider-owned facts
  retain their original ticker identity and remain discoverable through a
  durable lineage link.

The feature closes the original failure mode: a disappeared ticker must not
remain unexplained, and a genuine rename must not remove `A` without preserving
the user's tracking intent on `B`.

## 2. Product Boundary

### 2.1 In scope

1. Previewing the exact profile-owned effects of an eligible lifecycle
   proposal.
2. Explicit human approval of a dated transition plan.
3. A scheduler-safe, idempotent, single-database transaction that applies the
   approved profile transition after its effective date.
4. Cancellation before application and fingerprint-gated reversal afterward.
5. Durable old/new ticker lineage and linked historical notes/research.
6. In-app visibility for approved, needs-review, applied, cancelled, and
   reversed transitions.
7. Terminal-delisting retirement when no open broker position blocks it.

### 2.2 Out of scope

- automatic acceptance of an assessment;
- model-authored judgments;
- hosted web search, Tavily, or a provider canary;
- order placement or broker-position mutation;
- rewriting Seeking Alpha capture truth;
- rewriting historical prices, news, filings, notes, research threads, or
  reports from `A` to `B`;
- using `market_data.db.ticker_aliases` as corporate-action lineage;
- automatically treating acquisitions, cash-outs, spin-offs, or ambiguous
  legacy outcomes as simple renames;
- external notification-channel delivery; the first slice provides durable
  in-app state and scheduler results.

Tavily retirement, hosted-search capability work, the Anthropic setup-token
quota-probe retirement, and provider capability modeling remain independent
workstreams. None is a dependency of this design.

## 3. Grounded Current State

The completed investigation layer already provides:

- immutable provider observations in `market_data.db`;
- profile-side cases, evidence, accepted assessments, and inert action
  proposals;
- accepted assessment fields for `successor_ticker`, `destination_venue`, and
  `effective_date`;
- proposal fingerprints and stale-assessment projection;
- active-universe source snapshots;
- an explicit guarantee that proposals are not actions.

Current production has 36 observations, 37 event kinds, four accepted legacy
assessments, and zero action proposals. The four legacy assessments contain the
ambiguous `symbol_or_venue_changed` outcome and no successor ticker, so none is
eligible for this executor.

Profile-owned mutable state is in one SQLite database:

- `watchlist_memberships`;
- `universe_source_memberships` for `legacy_config_seed`;
- `ticker_meta` priority and suppression;
- editable `ticker_tags` whose source is `user` or `legacy`;
- lifecycle proposals and assessments.

The following are facts owned elsewhere even when their tables share the same
physical database:

- `portfolio_open` is derived from broker positions;
- `sa_alpha_picks_current` is derived from `sa_capture.db`;
- `system`, `provider:*`, `sec`, and `broker` tags are provider facts.

An identity transition may read those facts but may not rewrite them.

## 4. Vocabulary

### 4.1 Transition kinds

```text
symbol_continuation
terminal_delisting
```

`symbol_continuation` means the tracked security continues under a distinct
successor ticker. It is narrower than acquisition, issuer succession, or a
generic corporate relationship.

`terminal_delisting` means the accepted conclusion says the tracked security's
listing ended and no successor security is being continued by this plan.

### 4.2 Transition states

```text
approved
needs_review
applied
cancelled
reversed
```

- `approved`: user approved the exact preview and the plan may run on or after
  `execute_on`.
- `needs_review`: a revalidation gate changed or failed; the scheduler cannot
  apply the plan until the user approves a fresh preview.
- `applied`: all profile-owned effects committed in one transaction.
- `cancelled`: user cancelled before application.
- `reversed`: a fingerprint-gated reversal restored the exact pre-application
  profile rows.

`needs_review` is not a partial application. No profile-owned mutation occurs
when a gate fails.

### 4.3 Attempt states

Every attended or scheduled attempt is append-only:

```text
blocked | applied | already_applied | reversed
```

The transition row stores current state; attempts preserve operational history.

## 5. Eligibility

### 5.1 Symbol continuation

Approval is allowed only when all of the following are true:

1. the case has a current `proposed` `remap_symbol` recommendation;
2. its assessment is the current accepted assessment for the current provider
   observation fingerprint and evidence-set digest;
3. relevance is `direct_tracked_security`;
4. outcomes include `symbol_changed`, optionally with `venue_transfer`;
5. outcomes do not include an acquisition outcome, `listing_ended`,
   `symbol_or_venue_changed`, or `undetermined`;
6. the canonical successor ticker is present and differs from the source
   ticker;
7. the assessment cites the current provider observation;
8. an execution date is explicit, using the accepted assessment's
   `effective_date` or a user-confirmed replacement date.

The ambiguous migrated value `symbol_or_venue_changed` is never executable.

### 5.2 Same-symbol venue transfer

An assessment that only changes venue, or whose successor equals the source
ticker, produces `notify` plus `keep_tracking`. It does not create an identity
transition. Venue history remains assessment evidence.

### 5.3 Terminal delisting

Approval is allowed only when:

1. the current accepted direct assessment includes `listing_ended`;
2. no successor ticker is asserted;
3. no acquisition or ambiguous outcome is present;
4. the source has at least one current active-universe source;
5. the execution date is explicit.

An open broker position blocks terminal-delisting approval and execution. The
user must resolve or refresh that broker fact first. This prevents the app from
hiding a security that remains an open position.

### 5.4 Acquisition boundary

`acquisition_stock`, `acquisition_mixed`, `acquisition_cash`, and
`acquisition_terms_unknown` may still produce explanatory proposals, but this
executor rejects them. A stock-for-stock transaction is not assumed to be a
one-to-one ticker rename; consideration ratios, fractional treatment, taxes,
and multiple successor securities require a separate action design.

## 6. Source-Aware Effects

### 6.1 Symbol continuation `A -> B`

The committed transaction performs these steps in order:

1. insert or reactivate `B` in every active watchlist membership containing
   `A`;
2. insert or reactivate `B` in active `legacy_config_seed` memberships
   containing `A`;
3. copy editable `user` and `legacy` tags from `A` to `B` with
   `INSERT OR IGNORE`;
4. resolve and write `B`'s user priority;
5. write the durable `A -> B` identity link;
6. archive `A`'s active watchlist and `legacy_config_seed` memberships;
7. suppress `A` only when no open portfolio position requires it to remain
   visible;
8. persist the exact before snapshot, after digest, and applied receipt.

If `B` is already active in a list, its position wins. Otherwise `B` inherits
`A`'s position. Archived `B` memberships are reactivated at their existing
position. Duplicate memberships and duplicate tags are impossible by schema.

Broker positions are not changed. If `A` remains in `portfolio_open`, `A` may
remain visible as a broker-owned fact after manual tracking has moved to `B`.
The transition receipt and UI must say so explicitly. This is not reported as
full removal.

Seeking Alpha rows are not changed. If a stale current pick still emits `A`, the
approved profile suppression may hide `A` only when no open portfolio position
exists. The source fact remains queryable.

### 6.2 Terminal delisting

The transaction:

1. archives active watchlist memberships for the source ticker;
2. archives active `legacy_config_seed` memberships;
3. suppresses the source ticker from the active-universe projection;
4. retains notes, tags, research, market history, filings, and provider facts;
5. writes the applied receipt.

It never executes while `portfolio_open` contains the ticker.

### 6.3 Priority conflicts

If only one ticker has a priority, that value becomes `B`'s priority. Equal
values are idempotent. Different non-null values are a blocking conflict; the
approval request must explicitly choose `source` or `successor`. There is no
implicit severity ordering.

### 6.4 Hidden successor conflicts

If `B` is already suppressed, approval is blocked until the user explicitly
chooses to unhide it. The executor never silently reverses an earlier user
decision.

### 6.5 Historical content

The executor never rewrites `ticker_notes`, `research_threads`, `research_runs`,
`research_reports`, market data, or evidence. `ticker_identity_links` lets a
consumer request predecessor/successor history and display links from either
ticker.

## 7. Preview and Revalidation

The preview is a deterministic public projection, not a free-form explanation.
It contains:

- proposal, case, assessment, and observation fingerprints;
- source and successor tickers;
- transition kind and execution date;
- current active-universe sources;
- watchlist memberships to add/reactivate/archive;
- legacy memberships to add/reactivate/archive;
- editable tags to copy;
- source and successor priority values and any required resolution;
- source/successor suppression state;
- open-portfolio and provider-owned-source caveats;
- immutable blocker codes;
- a canonical `preview_sha256`.

Approval stores the literal preview and digest. Execution recomputes it from
current rows. Any changed profile-owned effect, accepted assessment, provider
observation fingerprint, or source snapshot moves the plan to `needs_review`
without mutation.

The profile dependency digest is recomputed after `BEGIN IMMEDIATE` and covers
every profile row that can change the active-universe decision, including open
portfolio positions and their account archive state. A broker refresh that
lands after service recomposition but before the write lock therefore blocks
the transition durably instead of allowing suppression of a held ticker.

SEC/market observations and Seeking Alpha capture are separate database
authorities. The service samples them before entering the profile transaction;
the executor does not claim atomicity across those databases. A changed sample
presented to the store produces `needs_review`. A provider update committed
after that sample is a later observation and is reconciled on the next preview
or collection cycle. Provider-owned rows are never rewritten by this executor.

The evaluator returns all blocker codes, not only a primary reason. UI copy is
derived from a closed mapping; unknown codes render as an explicit unknown
value and never as a different known reason.

## 8. Storage

Identity continuation is profile state, not provider evidence. It uses three
new tables whose names deliberately do not extend the exact
`security_lifecycle_%` schema authority:

### 8.1 `ticker_identity_transitions`

Stores one approved plan per case/assessment/transition kind. A terminal
delisting can derive several explanatory proposals (`notify`, archive, hide),
but it remains one atomic transition plan:

```text
transition_id PK
case_id
assessment_id
proposal_ids_json
transition_dedupe_key UNIQUE
kind
status
source_ticker
successor_ticker NULL for terminal delisting
execute_on YYYY-MM-DD
priority_resolution NULL | source | successor
unhide_successor 0 | 1
approved_observation_fingerprint_sha256
approved_assessment_fingerprint_sha256
approved_preview_sha256
approved_preview_json
before_snapshot_json NULL until applied
after_snapshot_sha256 NULL until applied
approved_at
updated_at
applied_at
cancelled_at
reversed_at
```

Checks enforce coherent terminal timestamps and kind/successor shape.

### 8.2 `ticker_identity_transition_attempts`

Append-only attempt records:

```text
attempt_id PK
transition_id FK
trigger attended_user | scheduler
status blocked | applied | already_applied | reversed
block_reasons_json
observed_preview_sha256
attempted_at
```

### 8.3 `ticker_identity_links`

Durable lineage:

```text
link_id PK
transition_id UNIQUE FK
source_ticker
successor_ticker
relationship = symbol_continuation
effective_date
created_at
reversed_at
```

The link is not a market-data canonicalization alias. Readers may traverse it;
writers may not use it to rewrite historical rows.

### 8.4 Schema ownership

A dedicated module owns DDL, verification, migration, snapshotting, and
transition writes. Read paths never auto-create missing tables. The live
migration is additive but still requires a separate read-only preflight,
backup, approval manifest, and explicit production-write authorization.

Verification owns the complete SQLite object surface of the three identity
tables: approved tables and indexes must match exactly, and no additional
trigger, view, or arbitrary-named index may attach to an identity table.
SQLite-generated autoindexes with no user SQL are the only exception. The same
reserved namespace and side-effecting attachment checks apply to TEMP objects
on the caller connection. A differently named read-only view that selects from
an identity table is an external consumer, not part of the component's owned
schema surface; verification does not parse arbitrary consumer SQL.

### 8.5 Restore protocol

The restore utility is not a process-quiescence detector and must never replace
an existing profile database inode. The live rollback runbook must stop all app
and scheduler writers, move the failed target aside, and then invoke restore at
that absent path. Restore revalidates the backup, copies it to a same-directory
temporary file, revalidates the copy, and installs it with an atomic no-clobber
operation. Before publication it fsyncs the verified copy and rechecks the
target plus SQLite sidecars; after publication it fsyncs the parent directory
before reporting success. An existing or concurrently recreated target is a
typed refusal. Writer quiescence remains an explicit operator prerequisite.

## 9. API and Permissions

New routes:

```text
GET  /security-lifecycle/cases/{case_id}/transition-preview
POST /security-lifecycle/cases/{case_id}/approve-transition
POST /security-lifecycle/transitions/{transition_id}/cancel
POST /security-lifecycle/transitions/{transition_id}/retry
POST /security-lifecycle/transitions/{transition_id}/reverse
```

Approval, cancellation, retry, and reversal call
`require_profile_state_write` before mutation. Preview is pure read.

Approval is the durable authorization for the scheduler to perform the exact
previewed action on or after `execute_on`. It does not authorize a different
preview. A changed preview requires a new attended approval.

There is no agent write tool and no LLM-callable transition executor. Existing
agent lifecycle tools remain read-only and may expose transition state and
lineage.

## 10. Scheduler

The app-owned scheduler invokes a provider-free due-plan runner. It does not add
a fake data provider or call SEC, IBKR, SA, Tavily, or an LLM.

For each due `approved` plan, bounded by a fixed per-tick limit:

1. compose the current lifecycle case and active-universe source snapshot;
2. recompute the transition preview;
3. call the shared profile-state permission choke point using the existing
   approval as the attended authorization record;
4. acquire a SQLite `BEGIN IMMEDIATE` transaction;
5. re-read all profile-owned rows inside the transaction;
6. apply only if the digest still matches;
7. commit the transition, attempt, identity link, and all profile effects
   together.

The service must not turn a recomputed-preview mismatch into an ephemeral
exception before step 4. It passes that preview into the store so the store can
append the blocked attempt and persist `needs_review`. A request digest that
does not match the stored approved digest remains an immediate client conflict
and is never treated as a new approval. Both comparisons occur again after
`BEGIN IMMEDIATE`: a provider observation that invalidates the accepted
assessment produces durable `needs_review`, while a concurrent re-approval
causes the stale request to fail without invalidating or applying the new plan.

Concurrent scheduler/app attempts serialize on SQLite. Re-entry after commit
returns `already_applied`. A crash before commit leaves no partial profile
state.

Date comparison uses the New York market calendar date represented by
`execute_on`; it never compares timestamp strings. The first tick whose
`America/New_York` date is on or after `execute_on` may execute.

## 11. Reversal

Application stores a canonical before snapshot and after digest for exactly the
rows it owns. Reversal is allowed only when:

- the transition is `applied`;
- all currently owned rows still match the stored after digest;
- no later active identity link continues from the successor;
- the user explicitly confirms reversal.

The reversal transaction restores the exact before rows, marks the link
reversed, and records an attempt. If any row changed after application, reversal
is blocked rather than overwriting later user work.

## 12. UI

The `標的事件調查` proposal section gains a transition preview only for eligible
proposals. The approval modal shows:

- `A -> B` or terminal-delisting identity;
- execution date;
- exact lists, priority, tags, and suppression effects;
- open-position and provider-source caveats;
- any conflict controls;
- the statement that notes, research, broker positions, provider facts, and
  historical data are not rewritten.

Buttons are explicit commands: approve scheduled transition, cancel, retry
after review, and reverse. There is no generic `Apply` button.

The Universe ticker detail surface exposes `Previous ticker` and `Successor
ticker` links. Historical notes/research remain under their original ticker and
are reachable through those links.

Status copy must distinguish:

- approved and waiting for date;
- needs review and why;
- profile tracking moved while an old broker position remains;
- applied terminal removal;
- cancelled;
- reversed.

## 13. Detection Boundary

The existing SEC collector continues to create provider observations. This
executor does not infer a successor from security class, issuer name, CIK, or a
generic web result. The accepted assessment remains the authority for the
source/successor and outcome.

Future deterministic inputs may prefill investigation evidence or a candidate:

- SEC Form 25 plus a same-CIK registration or ticker-map change;
- Form 8-A12B;
- IBKR contract details and exchange metadata;
- normalized Seeking Alpha or IBKR news.

Those sources may reduce manual work, but none bypasses assessment acceptance.
General web search is optional corroboration, not the standing solution for
missing structured data.

## 14. Capability Vocabulary Note

Future hosted-search capability must key on separate facts:

```text
provider
credential_kind = api_key | setup_token | interactive_oauth | ...
harness
capability
tool_policy
requested_mode
```

The current legacy `auth_mode` strings are not capability truth. This axis is
recorded here only to prevent the identity executor from acquiring a false
hosted-search dependency; capability implementation belongs to its own design.

## 15. Verification Contract

The implementation must prove at minimum:

1. `A -> B` adds/reactivates `B` before archiving `A` in one transaction.
2. A forced failure at every mutation step rolls back every profile-owned row.
3. Repeated execution is idempotent and produces no duplicates.
4. Existing `B` memberships/tags merge without losing existing state.
5. Priority conflict and hidden-successor conflict require explicit resolution.
6. Only `user` and `legacy` tags copy; provider-owned facts do not.
7. Notes, research, broker positions, provider rows, and historical market data
   remain byte-for-byte unchanged.
8. An open portfolio position blocks terminal delisting but does not prevent
   safe successor tracking; it prevents suppression of the held old ticker.
9. Same-symbol venue transfer produces no identity transition.
10. Acquisition and ambiguous legacy outcomes cannot enter the executor.
11. A changed assessment, observation fingerprint, source snapshot, or profile
    preview produces `needs_review` and zero mutation.
12. Scheduler and attended retries cannot double-apply a plan.
13. Reversal succeeds only against the exact stored after digest.
14. API validation and permission checks happen before any write.
15. Read paths do not create schema or modify database metadata.
16. The bilingual UI renders every closed status, blocker, and effect without a
    misleading catch-all.
17. No provider/network call is made by preview, approval, scheduler execution,
    cancellation, or reversal.
18. Live migration remains separately authorized and preserves unrelated
    profile rows and schema.
19. A broker position/account change between preview recomposition and the
    profile write lock blocks with a durable `needs_review` receipt.
20. Stored approved effects and caveats remain visible in approved,
    `needs_review`, and applied case states.
21. Exact schema verification rejects side-effecting extensions attached to
    identity tables.
22. Restore refuses an existing target and cannot replace an active database
    inode.

## 16. Rejected Alternatives

### A. Write `ticker_aliases`

Rejected. That table canonicalizes market-data spellings and old seeded aliases;
it cannot represent review status, effective dates, source ownership, reversal,
or historical lineage.

### B. Rewrite every `A` row to `B`

Rejected. It destroys historical identity, corrupts provider/broker ownership,
and makes reversal unsafe.

### C. Block every rename while a portfolio position is open

Rejected. That is precisely when losing successor tracking is most dangerous.
The safe split is to move user-owned tracking while retaining the broker-owned
old position until IBKR reports otherwise.

### D. Auto-execute from SEC or model confidence

Rejected. Observation, assessment, approval, and execution remain distinct.
Provider confidence never replaces attended approval.

### E. Treat stock acquisitions as simple renames

Rejected. Consideration and security identity may be one-to-many or mixed.
