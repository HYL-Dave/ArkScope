# Lifecycle Automation Repair Plan (標的事件調查)

**Status:** Review conclusion handed to the implementer. No product code changed
by the review. Ordered by dependency, not by severity — earlier items make later
items observable.

**Date:** 2026-08-30

**Base:** `947a51fc` (master, pushed to origin at 2026-08-30T12:38:07+08:00)

**Review basis:** three independent verification lanes plus reviewer probes. All
probes ran read-only against the repo, on `:memory:` or `/tmp` SQLite databases
with `ARKSCOPE_PROFILE_DB` redirected. No production database was opened, no
provider was called, no file in the repo was modified. Mutation probes ran on a
`git archive 947a51fc` export or via an import-time source rewrite, and every
mutated copy was restored byte-identically with the suite re-run green.

---

## 1. Adjudication of the implementer's counter-review

Seven claims were checked. The counter-review is upheld on all seven; two are
upheld with a correction that widens the defect.

| Claim | Verdict | Evidence |
| --- | --- | --- |
| `raise ValueError("source_deadlines")` is unreachable on the live SEC path | **CONFIRMED** | `collect_sec_evidence` clears `deadline_rows = ()` and appends `sec_evidence_insufficient` at `src/security_lifecycle_sec_evidence.py:1191-1195`; the only other return path (`:1084`) hard-codes `source_deadlines=()`. Probe over all 15 combinations of the four real deadline sentences on the fixture transport: max distinct dates = 1, combinations with >1 = 0, predicate fires 0/15. Positive control: a fabricated two-element tuple does fire it. |
| The extension date is discarded wholesale | **CONFIRMED, understated** | See §2.7. |
| A `failed` run is never re-executed, automatically or manually | **CONFIRMED** | `src/security_lifecycle_fact_kernel.py:1220`. Probe: ticks 2–4 with a healthy loader returned `skipped_current=1`; `evidence_loader` was invoked exactly once in total. Positive control: bumping `AUTOMATION_EXECUTION_REVISION` creates a new run that succeeds. |
| False recovery also affects `blocked` cases | **CONFIRMED** | Executed tick sequence: after a non-retryable block, tick 2 writes `security_lifecycle_automation_recovered` while the runs table still reads `('blocked', NULL)`. |
| Listing retry re-fetches SEC; new filings can still be valuable | **CONFIRMED, with a bound** | Retry deletes evidence/facts/blockers and re-acquires everything (`fact_kernel.py:1182-1210`; measured evidence 0→3, facts 0→13). But the filing window is anchored on the **observation** `filing_date`, not today (`sec_evidence.py:346-350`), so re-fetch value provably expires at `anchor + 120 days`. |
| The decision path is entirely deterministic, no LLM | **CONFIRMED** | A full worker tick completed with a `builtins.__import__` guard raising on `anthropic`/`openai` and `capability_for` poisoned: zero provider imports. Positive control: the guard trips on an explicit import. Translation is reachable only from `src/api/routes/security_lifecycle.py:270` and its output is read only by `list_evidence`. |
| News/publisher evidence has exited the production path | **CONFIRMED, stronger** | Exclusion is structural, not merely absence of a producer: `_current_decision_material` (`src/security_lifecycle_decision_policy.py:751-778`) admits only regulator, selected listing and selected market rows. A/B on the real policy: an injected publisher-family `successor_ticker` left the decision byte-identical; the same fact on a regulator row flipped it to `lifecycle.source_conflict`. |

**Reviewer correction on record:** the original review claimed the deadline
guard was a live permanent-failure trigger. That was wrong — it traced producer
and consumer but not the intermediary aggregation in `collect_sec_evidence`. The
permanent-park mechanism itself stands; its reachable triggers are listed in
§2.5.

---

## 2. Defect register

Severity reflects the contract violated, not the frequency.

### 2.1 Orphaned `running` run after a process kill — BLOCKING

A kill during `_load_evidence`'s network I/O leaves the run at
`status='running'` permanently. `reserve_run` returns `should_execute=False` for
any status other than `failed` (`fact_kernel.py:1220-1226`), and there is **no
lease, reaper, or `started_at` expiry** anywhere in the kernel or scheduler.

`_bounded_result` derives status only from failed/blocked counts, so
`skipped_current=1` yields `('succeeded', None)` (`scheduler.py:1063-1069`) and
**no `job_runs` failure witness is written**. The disposition surface reports
`automation_running` with `next_check_at=None` (`disposition.py:672-677`).

The failure is silent *and* actively misreports progress. Recovery today
requires the observation fingerprint or policy version to change on its own.

### 2.2 A human accepting a post-crash draft wedges the run forever — BLOCKING

`accept_assessment` permits `allowed_authorities['automation'] = {'human',
'automation_policy'}` (`investigation.py:1136-1142`) — accepting an automation
draft is a supported action. But after a crash inside the finalize phase,
`reserve_run` keeps returning `should_execute=True` while terminal finalization
is pending (`fact_kernel.py:315-323, 1214-1219`), `_process_claim` raises
`automation_assessment_not_accepted` at `worker.py:464`, and the
`if phase == "finalize": return "failed"` branch (`worker.py:524-525`) **skips
`fail_run` entirely**.

Measured: ticks 0–3 each returned `selected=1 failed=1 accepted=0`, with
`run.status='succeeded'`, `failure_code=NULL`, no typed artefact anywhere. One
of only `_MAX_CASES_PER_TICK = 2` slots is consumed every tick, permanently.

The existing boundary-recovery test does not cover this: `_InjectedFinalizationCrash`
is a `BaseException` (`tests/test_security_lifecycle_automation_worker.py:733`)
and bypasses the whole `except` clause.

### 2.3 False recovery witness, then permanent silence — BLOCKING

Two coupled defects in `record_security_lifecycle_automation_result`:

1. A tick that selects zero cases writes `security_lifecycle_automation_recovered`
   whenever the previous `job_runs` row was `failed` (`scheduler.py:1326-1332`).
   Because a failed or non-retryably-blocked case drops out of the selection set
   on the next tick, the all-clear fires **30 seconds after the case dies**.
   Executed for both the `failed` and the `blocked` shape.
2. `_failure_incident_key = (status, reason, sorted case_ids)`
   (`scheduler.py:1201-1207`). A wedged case produces the identical key every
   tick, so exactly **one** failure row is ever written and then the incident
   goes silent — no repeat, no escalation, no tick count.

The same key also causes churn in the opposite direction: a healthy case joining
or leaving the selected set changes `case_ids` and fires a fresh witness.

### 2.4 IBKR alias overflow permanently parks the highest-value cases — BLOCKING

The scheduler admits far more identity candidates than the IBKR reader accepts,
and the reader **raises** rather than truncating:

```
scheduler.py:106      _MAX_ALIASES_PER_TICKER = 64
scheduler.py:108      _MAX_IBKR_CONIDS_PER_TICKER = 32
ibkr_evidence.py:443  max_queries: int = 8
ibkr_evidence.py:265  if len(queries) > max_queries: raise ValueError(...)
scheduler.py:600-606  read_ibkr_contract_evidence called with NO max_queries
```

`_identity_context` (`scheduler.py:481-483`) passes `case["ticker_aliases"]` and
`case["ibkr_conids"]` straight through. Measured threshold:

```
aliases=6 -> ok (8 queries)
aliases=7 -> ValueError(ibkr_identity_candidates_exceed_max_queries)
          -> _failure_code(..., phase='acquire') = 'source_payload_invalid'
          -> run status 'failed' -> never re-executed
```

Seven aliases is enough. The IBKR branch is entered only when a successor,
terminal delisting, or pending market check exists (`scheduler.py:934`) — that
is, **only on the cases this feature exists to handle**. The longer a ticker's
rename history, the more certain the permanent park.

Second-order: `_alias_closures` raises `ticker_aliases_exceed_limit` above 64
(`scheduler.py:269`), and it runs inside `_load_cases()` — outside any per-case
`try`. One ticker with 65 aliases therefore returns
`automation_scheduler_failed` for the **entire batch**, every tick.

This is instance #8 of the producer/validator asymmetry family: the producer
emits one shape, a downstream consumer validates against a different one.

### 2.5 Transient causes are permanently retiring — MAJOR

All five `AUTOMATION_FAILURE_CODES` (`schema.py:380-388`) produce the same
permanent `failed` run. Three have transient real-world causes:

| Code | Live trigger | Nature |
| --- | --- | --- |
| `source_payload_invalid` | `sec_invalid_json` reaching `_normalize_sec_blocker` (`scheduler.py:495-496`); also `submissions_payload` / `submissions_recent` on a 200 body of unexpected shape | **transient** |
| `persistence_failed` | any `sqlite3.Error` — a lost 10 s busy-timeout on `complete_run`'s `BEGIN IMMEDIATE` while the desktop/web app writes `profile_state.db` | **transient** |
| `internal_error` | `TypeError`/`AttributeError`, plus any other type such as a `RuntimeError` from the IBKR gateway lock | mixed |

`sec_invalid_json` was executed end-to-end with no network: real `SecTransport`
plus a fake session returning HTTP 200 with an HTML body →
`blockers=('sec_invalid_json',)` → `_normalize_sec_blocker` raises →
`source_payload_invalid` → permanently failed. Positive control: a well-formed
JSON body yields only `sec_evidence_insufficient`.

`sec_url_unsupported` is **REFUTED** as a live trigger — both URLs are built
internally from a validated 10-digit CIK, and four hostile `primaryDocument`
values all resolved to `host=www.sec.gov`.

Note also that `persistence_failed` is mislabelled: `_failure_code` maps every
`sqlite3.Error` to it regardless of phase (`worker.py:204-205`), so a read-side
preview lock is reported as a persistence failure.

### 2.6 Two cause-collapse sites — MINOR

1. Every `ValueError` in `phase='approve'` collapses to
   `transition_approval_changed` (`worker.py:501-506`), including
   `_transition_request`'s own `automation_transition_request` — a
   worker/policy inconsistency is reported to the operator as "the approval
   drifted".
2. The worker calls `next_lifecycle_recheck_at(run, candidate)` with two
   arguments (`worker.py:272`) while `project_lifecycle_disposition` calls it
   with three, passing the transition (`disposition.py:752-756`). The
   transition branch and the `_automation_transition_is_stale` policy-version
   check are unreachable from the worker: the UI's `next_check_at` and the
   worker's actual recheck derive from different inputs, and the worker can
   never notice a policy-version-stale approved transition.

### 2.7 Discarding the deadline set costs three capabilities — MAJOR

A/B on an identical `merger_agreement` case at `at=2026-08-30`, differing only
in `source_deadlines`:

| | one deadline | cleared |
| --- | --- | --- |
| IBKR queried | **True** | False |
| blocker retryable | **False** | True |
| monitoring reason | `not_confirmed_as_of` | `event_completion_not_confirmed` |
| `retry_at` | None | 2026-09-06T12:00:00Z |
| context keys | 9 | 2 |

1. `deadline_due` is the **only** gate that triggers the IBKR market check when
   no `effective_date` fact exists (`scheduler.py:921-932`) — market-infrastructure
   evidence is never acquired.
2. The terminal fail-closed branch requires `deadline_date is not None`
   (`scheduler.py:737-744`), so the non-retryable `not_confirmed_as_of` verdict
   is unreachable and the case loops on a 7-day retry indefinitely.
3. All seven byte-span and hash citation keys vanish — the deadline has no
   auditable provenance.

The extractor already distinguishes `_CURRENT_DEADLINE` from
`_EXTENDED_DEADLINE`, and `_EXTENDED_DEADLINE` carries an optional `from <date>`
group. A resolvable supersession is being treated as an unresolvable conflict.

### 2.8 Refuted candidate, recorded so it is not re-raised

The suspected lock-ordering hazard between the worker's connection and the
separate preview/approver connections **does not exist** on today's path.
Instrumented probe recorded `conn.in_transaction` at every crossing:
`[('preview', False), ('preview', False), ('approver', False)]`. Every store
write is wrapped in `with self.conn:` and every kernel write in
`_immediate_transaction`, which itself raises
`automation_kernel_requires_transaction_boundary` if a transaction is already
open (`fact_kernel.py:1045-1056`).

Blast radius if that invariant is ever broken, measured on a throwaway WAL DB
with the exact connect arguments: a second writer blocked **10.01 s** then
raised `database is locked`; reads were never blocked. Residual exposure is
cross-process only and lands in `phase='approve'` →
`transition_approval_unavailable`, which is fail-closed.

---

## 3. Assessment of the proposed revision

All six proposals are implementable in spirit; none is correct exactly as
stated. Two cross-proposal conflicts dominate.

### 3.1 "No new migration" and "failed runs carry `retry_at`" are mutually exclusive — BLOCKING

```sql
security_lifecycle_schema.py:475
CHECK (retry_at IS NULL OR status = 'blocked')
```

SQLite cannot `ALTER` a `CHECK`; only a table rebuild. The verifier compares
live `sqlite_master.sql` against expected DDL by normalized text
(`schema.py:787`). Executed on `:memory:`: pristine schema verifies; rebuilding
`automation_runs` with the CHECK relaxed to `status IN ('blocked','failed')`
raises `LifecycleSchemaMismatch`; reverting to the original DDL verifies again.
`_detect_schema_version` knows only v1/v2 and raises `unknown_schema_version`
otherwise, so a new version must also be registered.

Enforcement is triple-layered — `reserve_run:1169`, `complete_run:1505-1511`
(raises `ValueError('retry_at')` unless `all_retryable == (retry_timestamp is
not None)`), and `fail_run:1804-1806` (hard-sets `retry_at=NULL`).

**Decide one:** accept a real migration, or keep the retry state outside the
runs table.

### 3.2 The `reserve_run` guard is an owned invariant, not dead code — BLOCKING

Deleting `or existing_revision == execution` fails three named tests:

```
test_current_policy_retries_a_failed_run_without_deleting_v1_history
test_current_execution_revision_does_not_replay_failed_semantic_run_later
test_cross_revision_due_blocked_failure_does_not_replay_same_attempt_revision
```

The second asserts `should_execute is False` and an unchanged `run_id` at both
+1 day and +1 year, plus `len(store.list_automation_runs(case_id)) == 1`.
No-auto-replay is deliberate for the scheduler path.

**Correct shape:** add an explicit opt-in parameter (e.g. `allow_new_attempt`)
that only a manual caller passes, leaving the automatic path guarded. Do not
delete the clause.

**The mechanism itself needs no redesign.** `_execution_run_key`
(`fact_kernel.py:468-481`) already hashes `predecessor_failed_run_id`. Executed:
`key(pred=None)` equals attempt A's stored key; `key(pred=A_run_id)` differs
with `execution_revision` unchanged. A mutation removing only the guard produced
three chained attempts, three distinct `run_id`s, all three failed rows
preserved, zero UNIQUE violations. Evidence and fact dedupe keys are
`run_id`-namespaced (`kernel:1545`, `kernel:1614`), and
`assessments.automation_run_id ... ON DELETE RESTRICT` (`schema:591`) protects
the preserved run. Forced-collision probe on the 32-hex `run_id` slice: the
insert no-ops and `RuntimeError('automation_run_insert_lost')` is raised — loud
failure, never silent row reuse.

**Scope gap:** the proposal covers only `failed`. `succeeded` and
non-retryably-`blocked` cases still return `should_execute=False`, and
`grep "automation" src/api/routes/*.py` returns **zero hits** — a new route and
a new kernel entry point are both required.

**Supporting argument the proposal understates:** using
`AUTOMATION_POLICY_VERSION` as the rerun lever would also mark every previously
approved automation transition stale (`disposition.py:527`). Avoiding that is a
correctness reason, not a cosmetic one.

### 3.3 Recovery must key off per-case rows, and the blob shape is a migration hazard — MAJOR

The stored blob's `case_ids` is the **selected** set, not the failed subset;
which case failed is not recoverable from it (outcomes are counters only,
`worker.py:663`).

Narrowing `case_ids` to the failed subset **silently breaks deduplication for
every already-persisted blob**: `_bounded_result` enforces
`len(case_ids) == selected` (`scheduler.py:1039-1041`), so `_stored_result`
returns `None` on the new shape, the dedupe comparison misses, and a duplicate
failure witness is re-inserted every tick. Executed both shapes.

**Correct shape:** derive recovery from the per-case row in
`security_lifecycle_automation_runs`, not from the tick summary. Any change to
the `case_ids` contract needs a versioned blob shape or a backfill.

### 3.4 The seven-stage display does not map onto the code — MAJOR

`phase` is a local in `_process_claim` with the exhaustive value set
`{acquire, approve, evaluate, persist, finalize}`; its only consumer is
`_failure_code` (`worker.py:526`). SEC, listing directory and IBKR all occur
inside a single `self._evidence_loader(...)` call under `phase='acquire'`
(`worker.py:349` → `scheduler.py:827-994`). IBKR is conditional
(`scheduler.py:934`), so a fixed seven-stage display would show a stage that
often never runs; `approve` has no proposed counterpart.

Nothing persists in-flight stage: `automation_runs` has no stage column,
`automation_running` is only `run["status"] in {"queued","running"}`, and
`_PROGRESS` is in-memory and rendered only for `SOURCES` entries — automation is
not a SOURCE.

**Implementation hazard:** the worker holds one rw connection for the whole
batch (`worker.py:579`, deferred isolation). An uncommitted mid-run stage write
poisons the next kernel call via
`automation_kernel_requires_transaction_boundary` (`fact_kernel.py:1046-1048`),
which falls through `_failure_code` to `internal_error`. Cost is up to ~14
`profile_state.db` writes per 30 s tick when cases are in flight, and
`set_setting` opens a fresh connection per call.

**Recommendation:** downgrade this item. Add a `phase` column to
`automation_runs`, written by the existing `complete_run`/`fail_run` calls, and
display the five real phases. A true seven-stage view requires restructuring
`_load_evidence` and belongs in a separate slice.

### 3.5 The proposed E2E caps are the production defaults, and their scoping differs — MINOR

All four numbers match the real constants exactly:

```
SecRequestBudget.max_attempts = 16      (sec_transport.py:41; also max_documents=12,
                                         max_document_bytes=1 MiB, max_total_bytes=12 MiB)
MAX_NASDAQ_REQUESTS  = 2                (listing_authority_transport.py:21)
MAX_MASSIVE_REQUESTS = 4                (listing_authority_transport.py:22)
IBKR 9 = max_queries default 8 + exactly one reqMktData
```

But the scoping is uneven: the **listing budget is per tick**
(`scheduler.py:1097`) while the **SEC budget is per case** (`scheduler.py:839`).
At the production `limit=2` hard-coded in `data_scheduler.py:1540`, one tick
allows **32 SEC attempts and up to 18 IBKR operations** against still-2/4
listing requests.

`limit=1` is supported (`scheduler.py:49, 1084-1085`) but `tick_once` never
passes it. A live E2E must pass `limit=1` explicitly, and its caps should be
**tighter** than the production defaults to mean anything.

IBKR is also the only provider in the path without a raising budget object — it
has a counter plus the `max_queries` check that raises (see §2.4).

### 3.6 Settings and state storage — feasible, with one correction

`profile_settings` (`profile_state.py:114-118`, accessors `:901-917`) and
`scheduler_state` (`scheduler_state.py:24-32`, no CHECK, no FK to `SOURCES`)
both live in the same `profile_state.db` as the automation tables, and a
non-`SOURCES` key is invisible to both `_snapshot` and `_seed_last_attempts`
(`data_scheduler.py:1650-1653`). So settings storage needs no migration.

**Correction:** do not park manual-rerun state in `scheduler_state.continuation`.
`reconcile_interrupted_running` sets `continuation=NULL` for every row left
running by a prior process (`scheduler_state.py:152-156`, invoked on boot from
`data_scheduler.py:1443`), and `record_outcome` replaces `continuation` and
`last_result` wholesale (`:89-106`) with no per-case merge. A pending rerun
queue there is lost on restart and clobbered by any concurrent outcome write.

---

## 4. Authority default: split the axis

The open question was whether the default automation authority should become
"draft only" or stay "full automation". **Neither, as stated.**

### 4.1 What zero human action reaches today

```
worker self-accepts the assessment (acceptance_authority='automation_policy')
  -> generate_action_proposals
  -> auto-approves the ticker transition
  -> run_due_ticker_identity_transitions, in the SAME tick_once
  -> execute_transition(trigger='scheduler')
  -> rewrites watchlist_memberships, universe_source_memberships,
     ticker_tags, ticker_meta
```

Both `run_security_lifecycle_automation` (`data_scheduler.py:1540`) and
`run_due_ticker_identity_transitions` (`:1557`) are called **unconditionally** —
they are the only two scheduled jobs not behind `_is_due()` / `cfg['enabled']`.
The one nominal gate, `require_profile_state_write`, is documented as
`"Enforcement is a no-op today"` (`api/permissions.py:41-48`).

### 4.2 The 22 gates are real but two details matter

- The policy-time `transition_eligible` gate is evaluated against a **synthetic
  assessment the preflight fabricates as already accepted**
  (`ticker_identity_transition.py:949-990` hardcodes
  `{'status':'accepted','stale':False,...}` with synthetic `slp_preflight_*`
  proposal ids). The preview's own `assessment_not_accepted`,
  `assessment_not_direct` and `stale_assessment` blockers (`:772-780`) can
  therefore never fire at policy time. `decision.transition_requested == True`
  is a **projection, not a verification**; the entire mutation authority rests
  on the five re-validations inside `approve_automation_case`.
- Reversal is asymmetric with the mutation. The apply is automatic
  (`trigger='scheduler'`), but `reverse()` is reachable only from
  `TickerIdentityService.reverse_transition`, which hardcodes
  `trigger='attended_user'`, whose only caller is the HTTP route at
  `api/routes/ticker_identity.py:223`. There is no automatic or scheduled
  reversal anywhere. And reversal is permanently foreclosed by any later user
  edit to the affected rows: `reverse_readiness` appends `reverse_state_changed`
  on a digest mismatch and `reverse()` has **no override argument**
  (`transition.py:1753-1793, 2117-2147`). Adding a tag, reordering a watchlist
  or hiding the ticker after the apply permanently prevents reversing a mutation
  the user never approved.

### 4.3 Why naive draft-only is wrong

`generate_action_proposals` sits **inside** `if decision.decision_tier ==
'verified_automatic':` (`worker.py:449`, call at `:465`); the `review_suggested`
path returns `drafted` with zero proposals, including notify (`:495-499`).

Worse, the recheck clock dies with it. `next_lifecycle_recheck_at` returns a due
time only when `retry_at` is set or `action_readiness` is one of
`waiting_effective_date` / `waiting_market_confirmation` /
`waiting_transition_revalidation` (`disposition.py:471-504`) — and those three
values are produced **only** on `verified_automatic` branches
(`policy.py:1007-1032, 1068, 1218, 1269`). Every `review_suggested` branch emits
`action_blocked` (`policy.py:874, 890, 963, 1101, 1203, 1251, 1286, 1349`).

Four of seven rules would lose their automatic branch, but only two ever request
a transition (`policy.py:1032`, `:1346`). The largest volume loss would be
`lifecycle.no_identity_change`, which today auto-closes "this filing does not
change the tracked security" with **no mutation at all**.

### 4.4 Decision

Keep `decision_tier` computation unchanged — `verified_automatic` still emits,
proposals still generate, recheck clocks still run. Gate **only**
`transition_requested → approve → apply` behind the authority setting, and
default it to *propose, do not mutate*.

Rationale:

1. Only the profile mutation is irreversible; the decision tier is information.
   Downgrading the tier discards observability to control a different axis.
2. Only two sites in the whole policy set `transition_requested=True` — a narrow,
   defensible gate.
3. The auto-approval path is believed never to have executed in the production
   database. **This is recorded from an earlier session and was NOT re-verified
   here** — it requires a separately authorized read-only preflight before it
   may be stated as fact. The recommendation does not depend on it: the
   reversibility asymmetry in §4.2 carries the argument on its own.
4. Draft-only would never accumulate the evidence needed to promote it. Gating
   the mutation while keeping the tier does: the record shows what it *would*
   have done. Promote after N drafts accepted unchanged by a person.

**Precondition:** §2.1–2.3 make the automation fail silently and misreport
recovery. Fix observability before widening authority — otherwise the promotion
evidence in (4) is not trustworthy.

---

## 5. Repair order

Earlier items make later items observable. Each carries a RED-first requirement:
write the failing test before the fix, and prove the guard is owned by reverse
mutation with a named test.

| # | Item | Why here |
| --- | --- | --- |
| 1 | Lease / timeout reclamation for orphaned `running` runs (§2.1) | The only defect that actively misreports state |
| 2 | Let a human-accepted automation assessment complete finalization idempotently; leave a visible typed state for other finalize errors (§2.2, §7.1) | Consumes a tick slot forever with zero typed record |
| 3 | Recovery keyed off per-case run rows; failure dedupe must restate an ongoing incident (§2.3, §3.3) | Items 1 and 2 are invisible until this is fixed |
| 4 | IBKR: query exact conId, current ticker and SEC successor first; return a typed ambiguity when candidates exceed budget — never truncate silently, never raise (§2.4, §7.2) | Targets exactly the highest-value cases |
| 5 | `sec_invalid_json` becomes a typed retryable blocker instead of raising (§2.5) | A transient SEC condition must not retire a case |
| 6 | `allow_new_attempt` opt-in + new route + kernel entry point (§3.2) | The manual recovery lever |
| 7 | Deadline supersession: take the latest date when the sequence is resolvable; conflict only when it is not (§2.7) | Restores fail-closed and the IBKR market check |
| 8 | `retry_at` for failed runs — accept the migration, or keep retry state outside the runs table (§3.1) | Has an alternative; not on the critical path |
| 9 | Authority split + Settings enable/interval + explicit `limit=1` (§4.4, §3.5, §3.6) | Only meaningful once 1–8 land |

Deferred: the seven-stage display (§3.4) — ship a `phase` column showing the five
real phases; the seven-stage view needs `_load_evidence` restructured and belongs
in its own slice.

---

## 6. Constraints for the implementation

- The five hard stops remain in force: no provider call, no production database
  read/write/backup/restore/migration, no App restart, no merge, no push —
  each requires separate explicit authorization.
- Do not modify `docs/design/PROJECT_PRIORITY_MAP.md` (user-owned working copy).
- Every mocked seam needs a real-function test on real-shaped input.
- Every new guard must be proven owned: mutate it, name the test that goes RED,
  restore byte-identically.
- A negative result requires a positive control — show the harness can fail.

---

## 7. Corrections after implementer review

Three fix mechanisms proposed in the first draft of §5 were wrong. The defect
register in §2 and the ordering in §5 stand; these are corrections to the
*how*, verified against the code.

### 7.1 `fail_run` cannot repair the finalize wedge — CORRECTED

`fail_run` accepts only `status in {'running', 'succeeded'}` and, for a
`succeeded` run, raises `ValueError("automation_run_has_current_assessment")`
when any assessment was created at or after `started_at`
(`fact_kernel.py:1791-1802`). The wedged run is exactly that shape — succeeded,
with an assessment — so routing finalize failures through `fail_run` would
raise, be swallowed by `_process_claim`'s `except`, and return `"failed"` again.
It changes nothing.

**Correct fix:** the wedge is at `worker.py:452-464`, where an assessment
already accepted with `acceptance_authority='human'` falls into the `elif` and
raises `automation_assessment_not_accepted`. Human acceptance of an automation
draft is an explicitly supported action (`investigation.py:1136-1142`), so it
must be treated as a valid terminal state and allowed to complete finalization
idempotently. Other finalize errors still need a visible typed state, but not
via `fail_run` on a run that already carries an assessment.

### 7.2 Silent IBKR truncation is the wrong fix — CORRECTED

Truncating the candidate list can produce an empty result set, and
`read_ibkr_contract_evidence` then returns `_contract_missing` — an incomplete
query asserting absence.

**Correct fix:** prioritise exact conId, then the current ticker, then the SEC
successor; when candidates still exceed the budget, return a typed ambiguity.
Never truncate silently, and never raise.

**Severity note so this is sized correctly:** a false `contract_missing` does
**not** produce a wrong mutation. `_current_decision_material` admits market
evidence only when `source_locator['contract_status'] == 'found'`
(`decision_policy.py:757-761`), so a `missing` row is dropped from the decision
material entirely and the case degrades toward `review_suggested`. The defect
manufactures human work; it does not authorise an unsafe automatic change. It
must not outrank items 1–3.

### 7.3 Retry state in `query_context_json` is feasible — with a carry-forward trap

No migration is needed. `_query_context_value` accepts any dict that survives
`_safe_json_value`, bounded at `_QUERY_CONTEXT_LIMIT = 16_384` bytes — a budget
already shared with the persisted terminal-decision blob, so leave headroom.

**Trap:** a new attempt's context is built from the **caller-supplied**
`query_context` plus fixed keys (`query_json_for`, `fact_kernel.py:1119-1130`).
The predecessor's context is **not** merged. A retry counter stored there
therefore resets on every new attempt, and "bounded retry" silently becomes
unbounded.

**Recommendation:** do not store the counter. Derive it by walking the
`predecessor_failed_run_id` chain, which is already persisted and already
unique-keyed. No carry-forward, no drift.

### 7.4 Progress callbacks need a named landing place

A callback with no database write has nowhere to surface today. `_PROGRESS`
(`data_scheduler.py:333`) is in-memory and rendered only for `SOURCES` entries
(`:1677`), and automation is not a SOURCE. The design must name the registry and
the endpoint that expose it, and state plainly that live stage is lost on
restart — which means it does not survive the very crash §2.1 exists to handle.
Stage visibility and orphan detection are therefore separate mechanisms; the
lease in item 1 cannot be built out of the callback.

### 7.5 Three of four tightened E2E budgets are settable today; one is not

| Cap | Settable per run? | Mechanism |
| --- | --- | --- |
| SEC 8 attempts / 4 documents | **yes** | `SecRequestBudget` dataclass fields |
| Nasdaq 2 requests | n/a | already the module constant |
| IBKR 3 contract + 1 quote | **yes** | `read_ibkr_contract_evidence(max_queries=…)` |
| Massive 2 requests | **no** | `MAX_MASSIVE_REQUESTS` is a module constant read directly at `listing_authority_transport.py:73` |

Lowering the Massive cap for an E2E requires `ListingRequestBudget` to carry its
caps as instance fields. Do not monkeypatch the module constant, and do not
lower it globally — 4 is the production budget.

### 7.6 The retired news adapter is not the historical read path

Labelling `src/security_lifecycle_news_evidence.py` as "read-only historical
use" would be inaccurate: nothing reads through it. Historical publisher rows
are served by `list_evidence` (`investigation.py:812-828`); the module's only
export, `read_local_publisher_evidence`, has no caller outside its own test.

Keeping the file is acceptable — the first draft's suggestion to delete it was
not load-bearing and is withdrawn — but label it as a retired acquisition
adapter, not as a live read path. The deliverable that matters is the test
forbidding re-attachment to the decision path, which is agreed.
