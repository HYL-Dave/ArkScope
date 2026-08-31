# Lifecycle Control-Plane Repair — Delegation

> **To**: implementer (codex). **Reviewer**: Opus 5. **Decisions**: user.
> **Source branch**: `lifecycle-automation-control-plane`, tip `b7cf3c0b` (docs seal);
> **product/test authority `daa3a408`**. Clean, unmerged, unpushed.
> **Register**: `docs/superpowers/plans/2026-08-31-lifecycle-control-plane-review.md`
> (§6 records the round-3 adjudication — your two corrections are accepted).
> **Consensus reached 2026-09-01** on all seven defects, both unowned guards, the
> zero-migration constraint, the `market_confirmation_missing` slot, and the
> `enabled=False` default.
> **Final user ruling 2026-09-01**: T7 uses the new `deferred` status contract
> below, including reason validation, tolerant unknown-version readback,
> strict present-but-malformed field validation, re-enable/repeat-deferral
> owners, and preservation of attended-user execution.

Nine tasks. **T1–T4 are merge blockers.** Do them in order: the earlier ones make
the later ones observable, and today the system is silent on failure and
misreports recovery 30 seconds later.

---

## Standing rules for every task

1. **RED first.** Write the failing test before the fix. Record the exact RED
   output (which node failed, on what assertion) and the exact GREEN output.
2. **Prove every new guard is owned.** Reverse-mutate it, name the test that goes
   RED, restore the file **byte-identically**, and verify with
   `git diff --exit-code`.
3. **Run the full focused set, not one file.** A single-file run is not evidence
   of ownership — two guards in this branch survived their own file and died only
   against the full set (see T8). The 21-file focused set is in
   `docs/superpowers/evidence/2026-08-30-lifecycle-automation-control-plane/commands.txt`.
4. **Zero schema migration this round.** No new table, column, index, `CHECK`, or
   schema version. `AUTOMATION_BLOCKER_CODES` is baked into a table `CHECK`
   (`security_lifecycle_schema.py:489`) — adding a code is a migration. Both
   schema authority files must stay byte-identical to `master`.
5. **Every mocked seam needs a real-function test** on real-shaped input.
6. **A negative result needs a positive control.** If a test asserts "no findings"
   or "nothing happens", show the harness can fail.
7. **Hard stops, each needing separate authorization**: no provider call, no
   production database read/write/backup/restore/migration, no App restart, no
   merge, no push.
8. Do not modify `docs/design/PROJECT_PRIORITY_MAP.md`.
9. Stop after each task for independent review. Report RED/GREEN output, the
   mutation ledger delta, and the focused-set count.

---

## Task 0 (T0) — Ship `enabled=False` as the automation default

Independent of everything else, and it removes the sequencing hazard immediately,
so it goes first.

**Why**: the automation tables are not in the profile bootstrap and the migration
module has zero callers outside `tests/`, so merging alone contacts no provider.
But `DEFAULT_SECURITY_LIFECYCLE_AUTOMATION_CONFIG` ships `enabled=True`,
`interval_minutes=5`, `batch_limit=2`, the parser falls back to those defaults for
any *absent* key, and the tick is already wired into the periodic loop
(`data_scheduler.py:1618`). So the instant the tables exist, unattended automation
starts on a five-minute cadence — **before** the single-case canary meant to
precede it.

**Change**: `security_lifecycle_automation_config.py:53-58` → `enabled=False`.

**RED first**: extend the existing
`test_absent_settings_resolve_to_the_complete_safe_default` so it asserts
`enabled is False`, and add a test that an empty `profile_settings` snapshot
yields a config on which `_security_lifecycle_automation_is_due` returns `False`
regardless of clock.

**Mutation**: flip the default back to `True` → the named test must go RED.

**Do not** change `interval_minutes` or `batch_limit`; they only matter once
enabled, and they are already owner-tested.

---

## Task 1 (T1) — F1: get the chain walk off the recovery path, and fault-isolate reclamation — **BLOCKER**

The only defect with cross-case blast radius. It disables the exact orphan
reclamation this branch was built to add.

**Defect**: `_MAX_PREDECESSOR_CHAIN = 32`; `_attempt_chain` raises
`automation_predecessor_chain_limit` on the 33rd link. Both rescue paths call it
unconditionally via `_automatic_retry_for_failure` — `fail_run`
(`fact_kernel.py:2624`) and `reconcile_running_runs` (`:2559`) — and the worker
swallows both raises (`worker.py:790`, `:799`). The reconcile loop is not per-row
guarded and runs inside one `_immediate_transaction`, and with
`execution_owner_id=None` the owner `continue` never fires, so one poisoned row
withholds reclamation from **every** case.

Reachability: a link is appended whenever the previous attempt is terminal —
`{failed, blocked, succeeded}`, so **successful** runs chain too — and
`allow_new_attempt=True` is unconditional for the per-case Run button
(`api/routes/security_lifecycle.py:524`). Nothing prunes the chain. ~32 clicks on
one case with an unchanged fingerprint is enough.

**Two independent repairs; both are required.**

**(a) Retry derivation must not raise on an over-long chain.** Bound the walk and
treat "chain longer than the bound" as *retries exhausted* — a typed terminal
state — rather than an exception. Do not raise, and do not silently grant an
unbounded retry.

**(b) `reconcile_running_runs` must be per-row fault-isolated.** One row that
cannot be classified must be recorded as such and skipped; every other running
row still gets reclaimed. Decide deliberately whether a failed row keeps the
transaction — per-row savepoints are acceptable — but the outcome must be that
sibling rows are never starved.

**RED first, four named owners:**

- `test_over_long_predecessor_chain_exhausts_retries_without_raising` — build a
  33-link chain, call `fail_run`, assert it returns a typed terminal state and
  the row is no longer `running`.
- `test_reconcile_reclaims_healthy_rows_despite_one_unclassifiable_row` — one
  poisoned row plus one healthy row from a **different case**; assert the healthy
  row is reclaimed. This is the cross-case contract and it is the important one.
- `test_reconcile_records_the_unclassifiable_row_rather_than_skipping_silently` —
  the poisoned row must leave a typed, readable trace.
- `test_per_case_run_button_cannot_grow_an_unbounded_predecessor_chain` — the
  reachability contract, driven through the same entry point the route uses.

**Mutations** (each must kill a named test): remove the bound and restore the
raise; remove the per-row isolation so one bad row aborts the pass; make the
"retries exhausted" state indistinguishable from a fresh failure.

**Positive control required** for the cross-case test: show it fails when the
isolation is absent, so a green result is not an artifact of the harness never
reaching the poisoned row.

---

## Task 2 (T2) — F2: stop the startup fallback poisoning the lifecycle state row — **BLOCKER**

**Defect**: `data_scheduler.py` calls `reconcile_interrupted_running` twice —
line 1486 passes `excluded_sources=("security_lifecycle.automation",)`, **line
1505 does not.** The fallback therefore writes a generic
`{source,status,error,last_attempt}` blob into the lifecycle source's
`last_result`. `_state_envelope` then raises `automation_scheduler_state` on it,
and because `_load_active_incident` (`scheduler.py:2892`) runs **before**
`_write_automation_state` (`:2945`) and its raise is caught at `:2953` with a
**rollback**, the repairing write never happens. Every later
`record_security_lifecycle_automation_result` returns `False`, forever. The
`not_installed` early return (`:2867`) writes only `last_status`, so it does not
clear it either.

**Two repairs:**

**(a)** Pass the same `excluded_sources` at line 1505.

**(b)** Make `_load_active_incident` tolerate a foreign blob — treat it as "no
prior incident" rather than raising — so a row poisoned by any means self-heals on
the next write. Keep the strictness where it belongs: a *malformed lifecycle*
envelope is still an error; a *recognisably foreign* blob is not.

**RED first:**

- `test_startup_fallback_never_writes_a_foreign_blob_to_the_lifecycle_source`
- `test_typed_write_recovers_a_lifecycle_state_row_poisoned_by_a_foreign_blob` —
  the self-healing contract.
- `test_malformed_lifecycle_envelope_is_still_rejected` — the positive control
  that (b) did not simply delete the guard. Note the guard is well owned today
  (neutralising `automation_scheduler_state` reddened 129 tests), so keep that
  ownership intact and do not weaken it into a blanket `return None`.

**Mutations**: drop `excluded_sources` again; make the tolerant path swallow a
malformed lifecycle envelope too.

---

## Task 3 (T3) — F3: separate "never asked" from "asked, answer not unique" — and surface the reason — **BLOCKER**

**Defect**: the same blocker code is emitted from two sites that mean opposite
things — `ibkr_evidence.py:481` (plan refused before any gateway call,
`requests_made=0`) and `:523` (multiple contracts found after querying). Measured:
producer bound 64 vs consumer bound 8, so the band **9..64** (canary **4..64**) is
legal to produce and impossible to consume. A case in that band gets
`contract_status='ambiguous'`, which `_provider_state` maps to **`conflict`**, and
which is **not** in `_RETRYABLE_BLOCKERS` — so `retry_at` is `NULL` and it never
retries. The run writes `ibkr_requests=0` and `ibkr_conflict=1` at once.

**Approved fix (yours, verified by review):** use the existing-but-unused
`market_confirmation_missing` for the plan-overflow case — **retryable**, absent
from `_PROVIDER_CONFLICT_CODES`, carrying a `candidate_budget_exceeded` context.
Keep `ibkr_contract_ambiguous` only for multiplicity actually observed after
querying. No migration: the code is already in the table `CHECK`, and review
verified the slot is genuinely free (only it and `impact_context_requested` have
zero references outside `schema.py`) **and already carries both locale labels**
(`marketConfirmationMissing`, mapped at `lifecyclePresentation.ts:414`) — so it
does not reproduce F7.

**Condition added by review — the diagnostic must reach the operator.** The
operator would otherwise read only "Market confirmation is missing" / 「缺少市場
確認」 for a case whose real problem is local alias ambiguity that was never
queried — **true but uninformative**, trading a false conflict for a vague truth.

**This condition was mis-specified in the first draft, and the implementer's
correction is adopted.** The draft said "widen the projection to carry context"
and named a test `test_blocker_projection_carries_context_to_the_api`. Verified:
that instruction was wrong on the facts and the test would have been worthless.

The actual data flow, confirmed by reading all three ends:

| Surface | Blocker context today |
| --- | --- |
| store → HTTP route | **already passes through** — `investigation.py:499-503` does `dict(blocker)` over `SELECT *`, and `api/routes/security_lifecycle.py` has zero blocker handling |
| AI tool | **explicitly stripped** to `{blocker_code, retryable}` — `tools/security_lifecycle_tools.py:405` |
| frontend type / UI | **consumes only** `{blocker_code, retryable}` — `api.ts:2702` |

So the named test would have **passed trivially, today, with the operator still
seeing nothing** — false assurance. Worse, the raw `context_json` is *already*
reachable over HTTP, and "widen the projection" would have entrenched an
arbitrary-blob surface.

**Do this instead: one closed, typed operator DTO, shared by all three
consumers.** Shape (the implementer's, adopted):

```
operator_detail:
  code: candidate_budget_exceeded
  candidate_count: 9
  query_limit: 8
  provider_contacted: false
```

Rules:

- Closed vocabulary for `code`, validated on the way out, with a label in both
  locales — the same discipline T5 enforces.
- **The same projection serves HTTP, the AI tool, and the UI.** Never expose
  arbitrary `context_json` on any of them; the AI tool's existing strip stays, it
  just gains the closed DTO.
- No migration: the data lives in the existing `context_json` column
  (`CHECK (length(context_json) BETWEEN 2 AND 4096)`); this is a projection and
  presentation change only.

**Replace the bad test** with, at minimum:
`test_operator_detail_is_a_closed_dto_and_rejects_unknown_codes`,
`test_operator_detail_reaches_http_ai_tool_and_ui_identically`,
`test_raw_context_json_is_never_exposed_on_any_surface`, and a frontend test that
the cause renders in **both** locales. Each needs a positive control: prove the
test fails when the DTO is bypassed.

If you judge the DTO should be a separate slice, say so explicitly and it goes to
the user as a decision; do not land T3 with the diagnostic unreachable.

**RED first:**

- `test_candidate_budget_overflow_is_retryable_and_not_a_market_conflict` —
  9 candidates ⇒ `market_confirmation_missing`, `retryable=1`,
  `_provider_state(...) != 'conflict'`, `retry_at` not null.
- `test_observed_multiplicity_remains_a_non_retryable_ambiguity` — the boundary
  in the other direction: after a real query returning several contracts, still
  `ibkr_contract_ambiguous`.
- `test_budget_overflow_records_candidate_budget_exceeded_context`
- the four operator-DTO tests listed above.
- Keep the existing boundary test alive: 8 candidates still query and can return
  a retryable `missing`.

**Mutations**: emit `ibkr_contract_ambiguous` for the overflow case again; mark
the overflow code non-retryable; add it to `_PROVIDER_CONFLICT_CODES`; admit an
unknown `operator_detail.code`; leak raw `context_json` on any one of the three
surfaces.

**Also assert** that `AUTOMATION_BLOCKER_CODES` and both schema authority files
are byte-identical to `master` after this task.

---

## Task 4 (T4) — F4: derive incident recovery from run state, not from a persisted record — **BLOCKER**

Promoted to blocker in round 3 on your argument: same permanence class as F2,
higher reachability (F2 needs a nested double failure; F4 needs one swallowed
write).

**Defect**: `_case_failure_marker` (`scheduler.py:2295`) classifies recovery as
`"finalization"` only when a finalization-failure *record* exists, else
`"new_attempt"`. But recovery for a `succeeded` + pending run is finalization **in
place, on the same `run_id`**. When the record could not be written — swallowed at
`worker.py:770-777` — `_case_failure_is_active` hits
`if latest_run_id == baseline_run_id: return True` and the incident is pinned
forever with `last_status=failed`.

**Fix**: derive `recovery` from the run's state — `succeeded` plus terminal
finalization pending ⇒ in-place finalization — independent of whether a failure
record happened to persist.

**RED first:**

- `test_recovery_marker_is_derived_from_run_state_without_a_failure_record` — the
  exact reproduction: succeeded + pending, no record, in-place recovery, assert
  the incident clears.
- `test_recovery_marker_still_clears_when_a_failure_record_exists` — the positive
  control (this path works today; it must keep working).
- `test_incident_stays_active_while_the_case_has_genuinely_not_recovered` — the
  guard against over-clearing, which is the risk this fix introduces.

**Mutations**: restore the record-presence branch; make the derived marker clear
an incident whose case has not actually recovered.

---

## Task 5 (T5) — F7: close the disposition vocabulary, and add the parity test

**Defect**: the branch adds a 21st backend reason,
`automation_finalization_failure`, with no consumer. Frontend union = 20, label
map = 20, and **neither locale** has the string. `disposition_reason` has no
runtime validator, so the row parses and
`lifecycleDispositionReasonLabel` falls through `closedLifecycleLabel` to
`states.unknownValue` — the reason column reads "Unrecognized value" / 「未識別的
值」, byte-identical to a garbage string, exactly when the operator needs it.

**Fix**: add the union member, the label-map entry, and both locale strings.

**The parity test is the real deliverable.** Nothing caught this: TypeScript
passes because the frontend never *produces* the value, and the backend test only
asserts `reason_code in LIFECYCLE_DISPOSITION_REASONS`, which is self-referential.
There is no backend↔frontend vocabulary parity test in the repository.

Add one that reads the backend closed set and the frontend closed set from source
and asserts **set equality** — not containment, both directions — for at minimum:
disposition reasons, disposition values, queue buckets, blocker codes, automation
stages, automation triggers, failure reasons, source-family states.

**Positive control required**: the parity test must go RED when a member is
removed from either side. Prove both directions.

Review already verified stage vocabulary (8=8=8) and failure reasons (no
backend-only members) are clean, so expect those two to pass on the first run —
if they fail, something else changed and stop.

---

## Task 6 (T6) — F5: no backwards stage on the finalization-only path

**Defect**: `_begin_progress(finalization_only=True)` seeds the registry at
`finalize` (index 7); the shared tail at `worker.py:665-668` then emits
`progress_callback("approve")` (index 6) when the terminal decision is
`verified_automatic` + `transition_requested` and mutation is allowed. The
registry requires strictly increasing stages, so it raises
`automation_progress_stage_order`; `_CaseProgress.advance` catches it and
`_disable("advance")` **clears the entry**. `GET /automation` loses the case for
the rest of a run that is still executing.

**Fix**: do not emit `approve` after seeding at `finalize` — or seed the
finalization-only path at `approve` when an approval stage will actually run.
Choose one and say which; do not make `advance` tolerant of backwards stages,
because that ordering guard is doing real work elsewhere.

**RED first:**

- `test_finalization_only_recovery_keeps_its_progress_row`
- `test_progress_registry_still_rejects_a_backwards_stage` — positive control
  that the ordering guard was not weakened instead.

**Mutation**: re-emit the backwards stage.

---

## Task 7 (T7) — F6: split the policy stop from the transient failure — including the test

**This is a pinned contract, not an unowned regression** — you are right, and
review verified it: `tests/test_ticker_identity_scheduler.py:637` asserts
`failed_transition_ids == ["slt_automation"]`. So this is a deliberate change of
an intentional contract.

**And the pinning test is the source of the dishonesty.** It is
`@pytest.mark.parametrize("authority_state", ("disabled", "unavailable"))` — it
binds a **deliberate policy stop** and a **transient store read failure** to the
same outcome. Two orthogonal axes in one state.

**Fix**: split them. `AutomationTransitionMutationDisabled` (policy) ⇒ a deferral
with its own reason, caught **ahead** of the generic `except Exception` at
`:417`. A transient read error ⇒ still a typed failure.

**There are TWO squash layers, not one — the implementer's correction, adopted.**
The first draft named only `ticker_identity_scheduler._mutation_allowed`
(`:36-39`). Verified there is a second, on the production path:

```
src/service/data_scheduler.py:392-397
def _security_lifecycle_profile_mutation_allowed() -> bool:
    try:
        return (...).effective_apply_profile_transitions
    except Exception:
        return False          # ← squashes a config-read error into "disabled"
```

That callable is what production passes in. Fixing only the scheduler layer
leaves the real path unable to tell *disabled* from *unavailable*, so **both
layers must carry the distinction** — a tri-state or a typed exception, not a
bool.

**Durable semantics to pin explicitly** (all four are owner-test requirements):

1. **disabled** ⇒ deferred. Not counted as a failure.
2. **disabled must not clear an existing failure incident.** If a previous tick
   genuinely failed and this tick merely policy-deferred,
   `record_ticker_identity_scheduler_result` (`ticker_identity_scheduler.py:256`,
   "Persist one deduplicated failure or **recovery**") must **not** write a
   recovery witness. This is the same false-recovery class as F4 — the
   implementer named it and it is a required owner:
   `test_policy_deferral_after_a_real_failure_never_records_recovery`.
3. **unavailable** ⇒ typed failure, distinct from a policy deferral in the
   persisted summary.
4. **Previously persisted summaries stay readable.** The reader must accept the
   old shape; no migration, no silent reinterpretation of historical rows.
   **Absent vs malformed:** a *missing* `deferred` field reads as the empty set;
   a field that is *present but wrong-shaped* must still raise. Do not let the
   backward-compat tolerance become an `else {}` that turns a shape mismatch into
   "no data".

**BLOCKING sub-finding — the summary validator will reject the new shape, and the
rejection is a worse lie than the bug.** Verified in `_bounded_result`
(`ticker_identity_scheduler.py:105-162`):

```python
terminal_count = applied + needs_review + already_applied + len(failed_ids)
if bounded["due"] != terminal_count:
    raise ValueError("due")
```

Every due transition must land in **exactly one of four buckets**, and
`failed_transition_ids` is the only non-success bucket. Move a policy-deferred
transition out of `failed_transition_ids` into a new `deferred_transition_ids`
and `due` still counts it while `terminal_count` no longer does — so
`_bounded_result` raises `ValueError("due")`. The caller
(`record_ticker_identity_scheduler_result`) catches that and substitutes
`ticker_identity_scheduler_failure("ticker_identity_scheduler_failed")`. **The
naive fix turns a deliberate policy deferral into a scheduler-failed witness** —
strictly worse than today's `transition_execution_failed`.

Two more constraints from the same read:

- **No honest status exists yet for a deferral-only tick.** `_RUNNER_STATUSES` is
  the closed set `{succeeded, partial, unavailable, not_installed}`; `partial`
  *requires* a non-empty `failed_ids` (`:144-147`) and any other status *requires*
  it to be empty. A tick whose only event is a policy deferral is therefore
  neither `partial` nor honestly `succeeded`. Decide this deliberately — extend
  the closed set (Python only, no migration) or define the mapping explicitly —
  and say which in the report.
- **The dedup key is where the false recovery gets in.**
  `_failure_incident_key` (`:165`) is `(status, reason, failed_transition_ids)`.
  If deferrals leave `failed_transition_ids`, a previously-failed case's key
  changes to a clean one, and the "prior incident present, now absent" branch
  writes a **recovery witness** — the exact false recovery this task exists to
  prevent. So requirement 2 above is not satisfied by moving the ids alone; the
  incident key and the recovery branch must both be updated with it.

So T7's scope is: two squash layers **plus** the summary contract
(`terminal_count`, status vocabulary, incident key, recovery branch). Do not land
the id-bucket change on its own.

### T7 contract — adopted, with two additions

The implementer's proposed contract is adopted: a new `deferred` status,
`deferred_transition_ids` alongside `failed_transition_ids` (both subsets of
`transition_ids`, non-overlapping), `terminal_count` extended by the deferred
count, `partial` when anything failed, `deferred` +
`transition_mutation_disabled` when only deferrals, `succeeded` when neither, an
authority *read failure* staying a failure under
`transition_mutation_authority_unavailable`, deferrals writing neither a failure
nor a recovery witness and leaving an existing incident untouched, only a genuine
`succeeded` clearing an incident, and old summaries reading a missing `deferred`
field as the empty set while a present-but-wrong one fails closed.

Reviewed against the three alternatives: mapping to `succeeded` claims every due
transition completed, and mapping to `partial` is worse than "the recorder treats
it as a failure" — `_bounded_result:144` **requires** `status == "partial"` to
carry a non-empty `failed_ids`, so that mapping forces the deferral straight back
into `failed_transition_ids`, which is the bug. A new status is the only option
that closes.

**Addition 1 — the reason gate will reject the new status.**
`_bounded_result:113-117` reads:

```python
if status in {"partial", "unavailable", "not_installed"}:
    if reason not in _RUNNER_REASONS: raise ValueError("reason")
elif reason is not None:
    raise ValueError("reason")
```

A `deferred` status carrying `reason="transition_mutation_disabled"` falls into
the `elif` and raises. So `deferred` must join the reason-requiring set, and both
new reasons must join `_RUNNER_REASONS` (`:27-29`) — Python frozensets, no
migration.

**Addition 2 — `result_version` must never be a rejection lever.** Adding the
field is fine, but the reader must treat an absent version as v1 and an
*unrecognised* version as a degraded read, never a raise. F2 is exactly this
failure: a reader that raises on an unexpected shape, inside a path that rolls
back, freezes the surface permanently. Do not hand-build the next F2.

**Verified favourable, so no work is needed on these:**

- **No F7 parity trap.** The frontend mirrors none of these vocabularies —
  `transition_execution_failed` has zero non-Python references anywhere in the
  repo — so adding a status and two reasons cannot produce an unknown-value
  render.
- **No silent permanent skip.** `list_due` selects
  `WHERE status='approved' AND execute_on<=?` (`ticker_identity_transition.py:1676`)
  and a deferral does not mutate the transition, so a deferred row is re-listed
  every later tick and applies once policy is back on. Still add one owner:
  `test_deferred_transition_is_reapplied_after_policy_is_re_enabled`, plus
  `test_repeated_deferral_across_ticks_writes_no_witness_each_time`.
- **The deferral path is narrow by construction.** With policy off at *listing*
  time, `allow_automation_approved=False` adds
  `AND approval_authority='attended_user'` (`:1669-1673`), excluding automation
  rows entirely. So the deferral only fires on the flip-between-listing-and-write
  race or on an authority read error — which is consistent with the design and
  bounds its blast radius.
- **Attended-user transitions are already unaffected** (`before_write` gates only
  `approval_authority == "automation_policy"`), so that clause is a *preservation*
  contract, not a change. Pin it with a test regardless.

**Visibility, stated plainly:** this task makes the durable *record* honest; it
does not add an operator surface. `ticker_identity.transitions` is referenced
nowhere outside its own module, so the summary is readable only through generic
job history. That is acceptable — the operator turned the toggle off themselves,
so a deferral needs no alert; the case that must stay visible is `unavailable`,
which remains a typed failure.

**Split the parametrized test** at `tests/test_ticker_identity_scheduler.py:637`
into two named tests with different expected outcomes. Say plainly in your report
that a pinned contract changed, and why.

**Mutations**: collapse the two branches back into one outcome; re-squash the
transient error into `False` at *either* layer; let a policy deferral write a
recovery witness; break old-summary readback.

---

## Task 8 (T8) — Own the two confirmed-unowned guards, and triage the rest

The 32-mutation ledger is a **sample** of ~4,000 new product lines, not a census.
Review's bounded census: of 63 new `raise` string constants, **22 have no mention
anywhere in `tests/`**. Three were mutation-tested against the full 931-test
focused set:

| Guard | Mutation | Result |
| --- | --- | --- |
| `automation_scheduler_state` | accept a foreign state blob | **OWNED** — 129 failed |
| `transition_approval_authority` | admit any approval authority | **UNOWNED** — 931 passed |
| `terminal_finalization_not_pending` | record a failure on a non-pending run | **UNOWNED** — 931 passed |

You independently corroborated the two unowned results by removing both together
in a separate copy — still `931 passed`.

**Do**: add a named owner test for each of the two, proven by reverse mutation.
Start with `transition_approval_authority` — it is an **authority** guard.

**Then triage the remaining 19.** For each, state one of: (a) owned by an existing
test that asserts its effect without naming the string — name that test; (b)
unreachable defensive code — say why, and whether it should stay; (c) genuinely
unowned — add an owner. A bare "no test mentions it" is a signal, not a verdict;
resolve each one.

Do **not** mass-add tests that merely assert the error string. An owner test must
assert the guard's *effect*.

---

## Closing gates for the whole batch

- Full backend A/B, both runs, with the collected node manifest byte-identical
  between them.
- Full frontend A/B, typecheck, production build, i18n literal scanner.
- Both schema authority files byte-identical to `master`; zero DDL diff.
- A rebuilt mutation ledger covering every new guard from T0–T8, each with
  baseline/mutant output hashes, the named owner that died, and a
  byte-identical-restoration receipt.
- Browser matrix for the T3 and T5 surfaces, with the geometry positive
  calibration retained.
- Secret scan.
- Confirmation that no provider call, production database operation, App restart,
  merge, or push occurred.

## Explicitly out of scope this round

- The production read-only inventory, including whether automation has ever
  self-approved. **Review asserted that claim in round 1 without verifying it and
  has withdrawn it**; it needs its own authorization and none of the repairs
  depend on it.
- The live single-case canary, the migration, and the App restart.
- Any schema migration. If a repair appears to need one, **stop and report**
  rather than adding it — that is a decision for the user.
- The seven-stage progress display (deferred in round 1; needs `_load_evidence`
  restructured).

---

## Revision log

**r2 — 2026-09-01, after implementer review of r1.** Four corrections, all his,
all verified before adoption:

| # | r1 said | Corrected to | Verified how |
| --- | --- | --- | --- |
| 1 | T3: "widen the projection to carry context", test `test_blocker_projection_carries_context_to_the_api` | **Closed typed `operator_detail` DTO**, one projection shared by HTTP + AI tool + UI; raw `context_json` never exposed | Read all three ends: the store already passes context through (`investigation.py:499-503`, `dict(blocker)` over `SELECT *`) and the route does not touch blockers, so the named test would have passed trivially while the operator saw nothing. Only `tools/security_lifecycle_tools.py:405` strips; `api.ts:2702` consumes two fields. |
| 2 | T7: fix `_mutation_allowed` (`ticker_identity_scheduler.py:36-39`) | **Both** squash layers, plus four pinned durable semantics including "policy deferral must never write a recovery witness" | Confirmed the second layer at `data_scheduler.py:392-397` — the callable production actually passes in — squashes any config-read exception to `False`. `ticker_identity_scheduler.py:256` is the recovery-witness writer, so the false-recovery risk is real and is F4's class. |
| 3 | Branch "@ `daa3a408`" | tip `b7cf3c0b`; product/test authority `daa3a408` | `git rev-parse` |
| 4 | focused set at `…/commands.txt` | `docs/superpowers/evidence/2026-08-30-lifecycle-automation-control-plane/commands.txt` | path exists |

Correction 1 is the load-bearing one: r1 specified a test that would have given
**false assurance**, and an instruction that would have entrenched an
arbitrary-blob surface which is already reachable over HTTP. T0–T2, T4–T6 and T8
are unchanged and were not disputed.
