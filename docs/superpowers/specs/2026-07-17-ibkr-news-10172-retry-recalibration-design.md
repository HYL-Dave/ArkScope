# IBKR News 10172 Retry Recalibration Design

> **Status:** MERGED — `master` through `80dd6e8`; automated merged-tree gates
> pass. Desktop restart and one natural due-cycle read-only verification remain
> before LIVE COMPLETE.

## 1. Purpose

Stop repeatedly spending IBKR Gateway calls on article bodies that the provider
continues to reject with typed error `10172`, while retaining one delayed
re-probe for a potentially transient first rejection.

This is a bounded correction to the live durable-retry policy. It does not
change normalized-news authority, headline capture, provider-entitlement
filtering, fresh-ingestion budgets, scheduler cadence, or PostgreSQL-exit
boundaries.

## 2. Ground Truth

### 2.1 User-visible reproduction

On 2026-07-17 the durable Settings projection changed from:

- `32` bodies due now;
- `83` scheduled later; and
- `78` blocked by a currently unavailable provider entitlement

to `7 / 108 / 78` after a manual run. The arithmetic is exact: the worker used
its independent `25`-body retry budget, fetched none of those bodies, and moved
all `25` failures to their next six-hour retry time.

The next manual run began as another batch reached its due time. It also
attempted `25`, fetched `0`, and received typed `10172` for every retry. It did
not bypass backoff or retry the same future-due rows immediately.

### 2.2 Read-only database evidence

Read-only inspection of the real `market_data.db` found:

- no `fetched` IBKR body with `fetch_attempts >= 2`;
- `96` rows at `failed / attempts=2 / error_code=10172`;
- `136` rows at terminal `unavailable / attempts=3 / error_code=10172`;
- therefore `0` successful retries among the `232` rows that had reached at
  least a second attempt;
- `12` rows after one typed `10172`, six published within the last day and six
  historical; and
- seven historical due rows with legacy missing error/timestamp evidence that
  still require one provider classification attempt.

The same three recent worker runs fetched `110`, `2`, and `2` fresh bodies.
Gateway connectivity and the body API therefore worked while the selected
retry cohort remained unavailable.

These counts are an observation snapshot, not migration acceptance constants;
normal ingestion may change them before implementation.

A later read-only review observed the exact next budget transition: the
`failed / attempts=2 / 10172` cohort moved from `96` to `71`, terminal
`unavailable` moved from `136` to `161`, and fetched bodies at attempts two or
more remained zero. The `-25 / +25` movement is one complete retry budget with
no recovery. It strengthens the policy evidence without turning either count
into a migration constant.

### 2.3 Provider boundary

IBKR documents that API news entitlements are distinct and that an article
body is requested with the provider code and article ID returned by headline
discovery. It does not document an eventual-success guarantee after an
article-unavailable response:

- <https://interactivebrokers.github.io/tws-api/news.html>

ArkScope therefore treats one delayed retry as a conservative hedge, not as a
provider promise.

## 3. Locked Policy

### 3.1 Typed 10172 state machine

For an IBKR body request that returns typed error `10172`:

1. The first total fetch attempt records `failed`, `fetch_attempts=1`, the
   sanitized code, attempt time, and `next_retry_at = attempted_at + 6 hours`.
2. The second total fetch attempt records terminal `unavailable`,
   `fetch_attempts=2`, the sanitized code, `unavailable_at`, and clears
   `next_retry_at`.
3. Scheduled work never automatically requests a terminal row again.
4. Existing explicit operator re-probe recovery remains the only route from
   `unavailable` to `fetched`.

The cap is based on total persisted fetch attempts, matching the current store
contract. A legacy row with one preserved but incompletely classified attempt
therefore receives one new classification request; if it returns `10172`, that
second total attempt is terminal.

### 3.2 Existing-row reconciliation

Implementation performs one idempotent, short SQLite reconciliation:

```text
source = ibkr
body_status = failed
last_error_code = 10172
fetch_attempts >= 2
```

Matching rows become terminal `unavailable`. The update:

- preserves article rows, titles, ticker relationships, provider identity,
  attempts, last error evidence, and any body fields byte-for-byte;
- clears only `next_retry_at`;
- uses the existing `last_attempt_at` as `unavailable_at` when present, with
  reconciliation time only as a missing-value fallback;
- is transactionally idempotent; and
- never changes `fetched`, `empty`, `expired`, already-`unavailable`, generic
  failure, pending, or entitlement-blocked rows.

The isolated IBKR news worker invokes an explicit store reconciliation method
after successful provider discovery and before retry selection, under the
existing market-data write lock. Schema initialization, store construction,
status reads, and frontend polling never perform this mutation. The worker
does not hold the market-data lock during provider discovery or any other
Gateway wait.

This is a deliberate terminal classification from repeated explicit provider
evidence, not an age-based `expired` inference.

### 3.3 Orthogonal entitlement state

`provider_not_entitled` remains a derived, reversible capability block:

- blocked rows consume no retry budget;
- no body status or attempt is rewritten merely because the provider is absent;
- a later successful provider observation automatically restores eligibility;
  and
- the existing `78`-row live observation must not be folded into this policy.

## 4. Runtime and UI Semantics

- The retry budget remains `25` and stays independent from fresh ingestion.
- Manual `Run` continues to respect `next_retry_at`; it is not a force-retry
  command.
- A currently eligible request that returns `10172` makes that run `partial`,
  whether it schedules the first retry or becomes terminal on the second.
- A terminal row does not make later runs partial and does not appear in
  due-now or scheduled-later backlog counts.
- A future-due first rejection remains visible as scheduled later.
- Provider-entitlement-blocked rows retain the existing separate explanatory
  text.
- No new terminal-history count is added to the compact scheduler row in this
  bounded correction. A future news-coverage surface may report historical
  body-state coverage without overloading run status.

Repeated manual clicks are not a drain command. They may discover fresh
headlines, process rows whose backoff naturally expires between clicks, or do
no retry work when nothing is due.

## 5. Alternatives Rejected

### 5.1 Keep three total attempts

Rejected because the real retry cohort has produced zero successes while the
third attempt consumes Gateway time and repeatedly creates partial runs.

### 5.2 Terminal on the first 10172

Rejected for now because it removes the only hedge for a freshly published
headline whose body may not yet be available. The observed zero-success rate
supports revisiting this later, but the approved correction retains one delay.

### 5.3 Age-based expiry

Rejected because publication age is not provider evidence. The terminal state
is `unavailable`, based on repeated typed responses, never inferred `expired`.

## 6. Failure and Safety Boundaries

- No network request occurs during reconciliation.
- No database write lock is held while waiting on Gateway.
- Lock-busy and provider-discovery failure consume no attempt and retain their
  current fail-closed behavior.
- Generic transport/provider failures keep their existing policy.
- Raw provider article IDs, provider error text, and licensed content remain
  inside the existing child/SQLite boundary.
- Reconciliation failure rolls back the whole reconciliation and must not
  fabricate an empty backlog.
- Headline metadata remains available even when the body becomes terminal.

## 7. Verification Contract

The implementation plan must include RED-first tests proving:

1. first typed `10172` becomes `failed`, attempts `1`, due six hours later;
2. second typed `10172` becomes terminal `unavailable`, attempts `2`, with no
   next retry;
3. an existing typed `10172` row at attempts `2` is reconciled once and remains
   unchanged on a second reconciliation;
4. reconciliation preserves article identity, metadata, attempts, sanitized
   error evidence, and all body payload/hash fields;
5. generic failures, pending rows, fetched rows, and entitlement-blocked rows
   are not reclassified;
6. terminalized rows are absent from deterministic retry selection and backlog
   due/scheduled counts;
7. a second-10172 run is `partial`, while a later no-failure run is not degraded
   merely by terminal history;
8. retry/fresh budgets, six-hour first backoff, provider filtering, lock-busy,
   restart reconstruction, and child-output sanitization remain unchanged;
9. a copied-DB probe reports before/after aggregate transitions without body,
   title, provider-code, or article-ID disclosure and proves fetched-body
   digests/counts are unchanged; and
10. focused normalized-news/scheduler suites, no-PG smoke, and canonical A/B
    accounting pass before merge.

The live gate must not repeatedly force real Gateway calls. After merge and one
natural due cycle, read-only telemetry verifies that attempts-2 typed rows no
longer remain scheduled and that fresh body ingestion still succeeds.

## 8. Documentation Convergence

When implementation is reviewed and merged, update the older normalization and
partial-retry authorities that still say three attempts. Until then, this
document records the approved replacement policy but production behavior
remains the live three-attempt contract.
