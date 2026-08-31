# Lifecycle Automation Control-Plane — Independent Review (Round 2)

> **Subject**: branch `lifecycle-automation-control-plane`, product/test authority
> `daa3a408`, evidence seal `b7cf3c0b`, base `947a51fc`.
> **Verdict**: mechanical claims all true; **1 BLOCKING + 3 MAJOR + 3 MINOR defects
> found**, every one re-verified by execution. **Merge not recommended until F1–F4
> are repaired.**
> **Round 3 (2026-09-01)**: the implementer independently reproduced all seven and
> corrected two of this review's conclusions. Both corrections are accepted — see §6.
> **Status of this document**: docs-only. No merge, push, provider call, production
> database operation, or App restart was performed.

---

## 0. What was verified, and how

Every mechanical claim in the implementer's report was re-derived independently
rather than read from the summary:

| Claim | Independent check | Result |
| --- | --- | --- |
| Manifest digest `8e6b7e7f…` | own `sha256sum SHA256SUMS` | identical |
| Packet 34/34 | own `sha256sum -c`; plus set-difference of directory vs manifest | 34/34, **zero unsealed files** |
| Backend A/B `5223P/12S` | both raw gate logs | matches |
| Focused `931` | **own re-run** | `931 passed in 46.20s` |
| Frontend A/B `108 files/1324` | both raw logs | matches |
| Node manifests byte-identical | own hashes of both files | both `22363e5d…`, 5235 nodes |
| Schema authorities untouched | own hash of both files vs `master` | identical |
| Unmerged, unpushed | `master == origin/master == 947a51fc`, zero merge commits | confirmed |
| Mutation method is real | **own reverse mutations** on the three load-bearing fixes | 3/3 went RED, all restored byte-identically |
| Browser geometry zero-findings | read `calibrate_geometry()` source | computed, not hardcoded; raises `geometry_observer_inactive` if the observer is blind |

The nine repair items and the six §7 corrections from the round-1 review all
landed, and landed **in the corrected form**: the finalize wedge is fixed at
`worker.py` acceptance-authority (not via `fail_run`), IBKR returns a typed
ambiguity (not a silent truncation), retry depth is **derived** by walking
`predecessor_failed_run_id` rather than stored, and no DDL was added.

**Not verified, still open**: the production read-only inventory, including
whether automation has ever self-approved. That claim remains unverified and
none of the conclusions below depend on it.

---

## 1. Defect register

Severity is by consequence, not by novelty. `CONFIRMED` means reproduced by
running code; the reproduction script is named where one exists.

### F1 — 33-link predecessor chain permanently wedges a run *and* blocks orphan reclamation for every other case — **BLOCKING / CONFIRMED**

`_MAX_PREDECESSOR_CHAIN = 32`. `_attempt_chain` raises
`automation_predecessor_chain_limit` on the 33rd link, and **both** paths that
can rescue a `running` row route through it unconditionally:

```
fact_kernel.py:2624  fail_run               → _automatic_retry_for_failure → _attempt_chain
fact_kernel.py:2559  reconcile_running_runs → _automatic_retry_for_failure → _attempt_chain
```

The worker swallows both raises (`worker.py:790`, `:799`).

Reproduced (`repro/f1_chain.py`):

```
*** fail_run RAISED at chain depth 33: ValueError(automation_predecessor_chain_limit)
rows left status='running' = 1
*** reconcile_running_runs RAISED: ValueError(automation_predecessor_chain_limit)
healthy case2 row: before=running after=running  -> STILL STUCK (collateral damage)
```

Two aggravating facts found during verification:

1. **Cross-case blast radius.** The reconcile loop is not per-row guarded and
   runs inside one `_immediate_transaction`. With `execution_owner_id=None` —
   the startup and per-tick call — the owner `continue` never fires, so
   `_automatic_retry_for_failure` is invoked for *every* running row. One
   poisoned row means no case anywhere gets its orphan reclaimed. Proven above:
   an unrelated healthy case's `running` row was left stuck.
2. **Reachability is worse than a failure loop.** The link is appended whenever
   the previous attempt is terminal — `{"failed", "blocked", "succeeded"}`. A
   fully successful run therefore also chains (`repro/f1c_success_chain.py`
   reaches depth 33 using only succeeded rows). `allow_new_attempt=True` is set
   unconditionally for the per-case Run button
   (`api/routes/security_lifecycle.py:524`), and **no code anywhere prunes the
   chain**. So ~32 per-case Run clicks on one case with an unchanged
   observation fingerprint — any mix of outcomes — is sufficient.

**Fix direction**: the chain walk must not be on the recovery path. Either bound
the derivation (walk at most N links and treat an over-long chain as "retries
exhausted" rather than raising), or catch the two chain errors at the
`fail_run`/`reconcile` boundary and degrade to a typed terminal state. Whatever
the mechanism, `reconcile_running_runs` must be **per-row fault-isolated** so one
row can never withhold reclamation from the rest.

### F2 — startup fallback poisons the lifecycle telemetry row permanently — **MAJOR / CONFIRMED**

`data_scheduler.py` has two calls to `SchedulerStateStore.reconcile_interrupted_running`.
Line 1486 passes `excluded_sources=("security_lifecycle.automation",)`; **line
1505 does not.** That exclusion exists precisely because the lifecycle source's
`last_result` carries a different blob shape.

Reproduced (`repro/f2_envelope.py`):

```
_state_envelope(foreign blob)                 -> *** RAISED ValueError(automation_scheduler_state)
_state_envelope(well-formed lifecycle blob)   -> OK
```

The consequence is permanent, and I confirmed the ordering that makes it so:
`_load_active_incident` runs at `scheduler.py:2892`, **before**
`_write_automation_state` at `:2945`; its raise is caught by the
`except (OSError, TypeError, ValueError, sqlite3.Error)` at `:2953`, which
**rolls back**. So the write that would repair the row never executes, and every
later `record_security_lifecycle_automation_result` returns `False`. The
`not_installed` early return at `:2867` writes only `last_status`, so it does not
clear `last_result` either. No in-product path recovers it.

Reachability is gated: line 1505 is only reached when *both* the lifecycle
reconcile and its failure-telemetry write raise. Low probability, permanent
consequence, two-line fix.

**Fix direction**: pass the same `excluded_sources` at line 1505. Separately,
consider making `_load_active_incident` tolerate a foreign blob by treating it as
"no prior incident" instead of raising, so a poisoned row self-heals on the next
write.

### F3 — IBKR: one blocker code carries two opposite meanings; the 9..64 alias band asserts a conflict that was never observed — **MAJOR / CONFIRMED**

This is **instance #9** of the producer/validator asymmetry family, in its purest
form: the *same* code is emitted from two sites that mean opposite things.

```
ibkr_evidence.py:481   plan refused, BEFORE any gateway call   requests_made=0   "I never asked"
ibkr_evidence.py:523   several contracts found AFTER querying  requests_made=N   "I asked; the answer isn't unique"
```

Measured with the real functions (`repro/f3`):

```
producer bound (_MAX_ALIASES_PER_TICKER)   = 64
consumer bound (_DEFAULT_IBKR_MAX_QUERIES) = 8      → dead band 9..64 (canary: 4..64)
  8 distinct tickers -> 8 contracts        (fine)
  9 distinct tickers -> None (plan refused)

refusal result: blockers=('ibkr_contract_ambiguous',) requests_made=0 contract_status='ambiguous'
_provider_state(('ibkr_contract_ambiguous',), 'market_infrastructure') = 'conflict'
retryable? False        (compare ibkr_contract_missing: True)
```

So a case in the dead band is told **"IBKR contract data conflicts"** with zero
IBKR contact, and because the code is not in `_RETRYABLE_BLOCKERS`, `retry_at` is
`NULL` and it never retries. The same run writes `ibkr_requests=0` and
`ibkr_conflict=1` simultaneously.

**Correction to the round-1 review.** The §7.2 severity note sized this as
"degrades toward `review_suggested`; manufactures human work, does not authorise
an unsafe change". That note was about a `contract_missing` outcome. The
implemented fix emits `ambiguous`, which maps to `conflict` and is
**non-retryable** — so the note does not apply and the severity is higher than
stated. The fix direction in §7.2 was right; the sizing was wrong.

**Fix direction — corrected in round 3.** The first draft said "give the
plan-overflow case its own code". **That violates the zero-migration constraint**:
`security_lifecycle_schema.py:489` bakes the allowed set into the table itself —
`blocker_code TEXT NOT NULL CHECK (blocker_code IN (…))` — and SQLite cannot
`ALTER` a `CHECK`, so any new code forces a migration. The implementer caught
this; the correction is his.

Use the existing-but-unused `market_confirmation_missing` for the plan-overflow
case: retryable, absent from `_PROVIDER_CONFLICT_CODES`, and carrying a
`candidate_budget_exceeded` context. Keep `ibkr_contract_ambiguous` only for a
multiplicity actually observed after querying. Verified for that slot:

- Of the 19 allowed codes, only `market_confirmation_missing` and
  `impact_context_requested` have zero references outside `schema.py`, so the
  slot is genuinely free.
- It **already has both locale labels** — `marketConfirmationMissing`
  ("Market confirmation is missing" / 「缺少市場確認」), mapped at
  `lifecyclePresentation.ts:414`. Picking a label-less code would have
  reproduced F7 on the spot.

**One gap in that fix, added by this review.** The blocker projection carries
`{blocker_code, retryable}` only — `api.ts:2703` has no `context` field — so
`candidate_budget_exceeded` would be persisted and never reach the operator. The
label alone ("Market confirmation is missing") is *true but uninformative* for a
case whose real problem is local alias ambiguity that was never queried; it trades
a false conflict for a vague truth. This is the same shape as the dated
2026-08-27 defect where blocker context was stripped to `{blocker_code,
retryable}`.

So the same slice must widen the blocker projection to carry context — route,
frontend type, and label — which needs **no migration** because `context_json`
already exists on the table (`CHECK (length(context_json) BETWEEN 2 AND 4096)`).
If that is deliberately deferred it must be filed explicitly, not left silent.

Optionally also align the producer bound with the consumer's so the dead band
cannot exist at all.

### F4 — a genuinely recovered case stays pinned as an active incident forever — **MAJOR / CONFIRMED / MERGE BLOCKER**

`_case_failure_marker` (`scheduler.py:2295`) classifies recovery as
`"finalization"` only when a finalization-failure **record** exists; otherwise
`"new_attempt"`. But recovery for a `succeeded` + pending run is finalization
**in place, on the same `run_id`**. When the failure record could not be written
— the worker swallows exactly that at `worker.py:770-777` — the two disagree.

Reproduced (`repro/f4`), with a positive control:

```
A: failure record WAS persisted
   marker = {'run_id': 'slar_R', 'recovery': 'finalization'}
   after a GENUINE in-place recovery -> still_active = False   (clears correctly)

B: failure record could NOT be written
   marker = {'run_id': 'slar_R', 'recovery': 'new_attempt'}
   after a GENUINE in-place recovery -> still_active = True    <== PINNED FOREVER
```

`_case_failure_is_active` hits `if latest_run_id == baseline_run_id: return True`
and the automation status surface never clears. Two independent review lanes
found this same line.

**Fix direction**: derive `recovery` from the run's *state* (succeeded + terminal
finalization pending ⇒ in-place finalization), not from whether a failure record
happened to be persisted.

**Promoted to merge blocker in round 3.** The first draft listed F1–F3 as the
blocking set and put F4 fourth. That was inconsistent on this review's own
reasoning: F4 is the same class as F2 — a permanent, non-self-healing false state
on the status surface — and its **reachability is higher**, since F2 needs a
nested double failure while F4 needs only one swallowed write. The implementer
raised this; the correction is his and it is accepted.

### F5 — the finalization-recovery path destroys its own progress row — **MINOR / CONFIRMED**

`_begin_progress(finalization_only=True)` seeds the registry at `"finalize"`
(index 7). The shared tail at `worker.py:665-668` then emits
`progress_callback("approve")` (index 6) whenever the persisted terminal decision
is `verified_automatic` + `transition_requested` and mutation is allowed. The
registry requires strictly increasing stages.

Reproduced through the real worker wrapper, with a positive control:

```
rows before = 1
security lifecycle progress observer disabled operation=advance
rows after  = 0 -> PROGRESS ROW DESTROYED
control: legitimate forward advance -> rows = 1 (kept)
```

The registry raises `automation_progress_stage_order`; `_CaseProgress.advance`
catches it and `_disable("advance")` calls `registry.clear`, deleting the entry.
`GET /automation`'s `current_progress` loses the case for the rest of a run that
is still executing — on the branch whose stated goal is truthful progress.

**Fix direction**: on the finalization-only path, do not emit `approve` after
seeding at `finalize`; or seed that path at `approve` when an approval stage is
actually going to run.

### F6 — a deliberate policy stop is reported as an execution failure — **MINOR / CONFIRMED**

`AutomationTransitionMutationDisabled` is raised inside `before_write`
(`ticker_identity_scheduler.py:391`). `execute_transition` calls `before_write()`
bare (`ticker_identity_service.py:385`), so it propagates to the loop's generic
`except Exception` at `:417`, lands in `failed_transition_ids`, and the tick
reports `status="partial"`, `reason="transition_execution_failed"`.

Two ways in: the operator turns off *apply profile transitions* after the batch
was listed, or `_mutation_allowed` swallows a transient profile-store read error
into `False` (`:36-39`). Either way an intentional, correct refusal is recorded
as a failure.

**Fix direction**: catch `AutomationTransitionMutationDisabled` ahead of the
generic handler and count it as a deferral with its own reason.

**Refined in round 3 — this is a pinned contract, not an unowned regression.**
The implementer is right that the current semantics is deliberately fixed by
`tests/test_ticker_identity_scheduler.py:637`, which asserts
`failed_transition_ids == ["slt_automation"]`. So repairing F6 means changing an
intentional contract, with the decision made explicitly rather than treated as a
bug fix.

**And the pinning test is itself the source of the dishonesty.** It is
`@pytest.mark.parametrize("authority_state", ("disabled", "unavailable"))` — it
binds a **deliberate policy stop** and a **transient read failure** to the same
outcome. Those are two orthogonal axes conflated into one state. The repair must
split them — policy stop ⇒ deferral, transient error ⇒ failure — and the
parametrized test must split with them.

### F7 — the new attention state renders as "Unrecognized value" in both locales — **MINOR / CONFIRMED**

The branch adds a 21st backend disposition reason,
`automation_finalization_failure`, and adds no consumer for it:

```
backend reasons        = 21
frontend type union    = 20
frontend label map     = 20
missing from both      = ['automation_finalization_failure']
i18n en      : automationFinalizationFailure? False   (automationFailure? True)
i18n zh-Hant : automationFinalizationFailure? False   (automationFailure? True)
```

`disposition_reason` has **no runtime validator** in `api.ts`, so the row parses
fine; `lifecycleDispositionReasonLabel` goes through `closedLifecycleLabel`,
whose fallback is `states.unknownValue`. The bucket and disposition are correct —
the case does reach `exception_required` / `attention` — but the reason column
reads "Unrecognized value" / 「未識別的值」, byte-identical to what a garbage
string would print, exactly when the operator needs the reason.

Why no gate caught it: TypeScript passes because nothing in the frontend
*produces* the value; the backend test only asserts
`reason_code in LIFECYCLE_DISPOSITION_REASONS`, which is self-referential; no
mutation targeted the reason vocabulary. **There is no backend↔frontend
vocabulary parity test in the repository.**

**Fix direction**: add the union member, the label-map entry, and both locale
strings — and add the parity test, which is the deliverable that stops the next
recurrence. Verified clean by the same method: stage vocabulary (8=8=8 across
backend `Literal`, frontend type, frontend runtime validator) and failure-reason
vocabulary (no backend-only members).

---

## 2. Test-coverage gap on new guards

The 32-mutation ledger is a **sample**, not a census, of ~4,000 new product
lines. A bounded census of every new `raise ValueError/KeyError/RuntimeError`
string constant introduced by the branch:

```
new raise-string constants : 63
  mentioned in tests/      : 41
  NOT mentioned in tests/  : 22
```

Three of the 22 were mutation-tested against the **full 931-test focused set**:

| Guard | Mutation | Result |
| --- | --- | --- |
| `automation_scheduler_state` | accept a foreign state blob | **OWNED** — 129 failed |
| `transition_approval_authority` | admit any approval authority | **UNOWNED** — 931 passed |
| `terminal_finalization_not_pending` | record a failure on a non-pending run | **UNOWNED** — 931 passed |

Both unowned guards are defence-in-depth rather than live defects — no current
caller reaches them with a bad value. The problem is that a future refactor can
delete them silently. `transition_approval_authority` is an **authority** guard,
which makes it the one worth owning first.

The remaining 19 candidates were not mutation-tested. A no-test-mention result is
a signal, not proof — a guard's effect can be asserted without naming its string.

---

## 3. Recommended repair order

Same principle as round 1: earlier items make later items observable.

| # | Item | Blocker? | Why here |
| --- | --- | --- | --- |
| 0 | Ship `enabled=False` as the automation default | — | Independent, trivial, removes the §4 sequencing hazard immediately |
| 1 | **F1** — chain walk off the recovery path + per-row fault isolation in `reconcile_running_runs` | **yes** | The only defect with cross-case blast radius; it disables the very orphan reclamation this branch added |
| 2 | **F2** — `excluded_sources` at `data_scheduler.py:1505`; make `_load_active_incident` tolerant | **yes** | Two lines; unrecoverable in-product otherwise |
| 3 | **F3** — `market_confirmation_missing` for plan-overflow (retryable, non-conflict) **+ surface blocker context** | **yes** | Asserts an unobserved conflict on exactly the high-alias cases |
| 4 | **F4** — derive `recovery` from run state, not from the presence of a failure record | **yes** | Same permanence class as F2 with higher reachability |
| 5 | **F7** — union + label + both locales + **backend↔frontend parity test** | no | The parity test is the real deliverable |
| 6 | **F5** — do not emit a backwards stage on the finalization-only path | no | Progress row loss on the recovery path |
| 7 | **F6** — split policy stop from transient failure, **including the parametrized test** | no | Changes a pinned contract; needs the axis split, not just a rename |
| 8 | Own `transition_approval_authority` and `terminal_finalization_not_pending`; triage the other 19 | no | Stops silent deletion later |

RED-first throughout: write the failing test before the fix, and prove each new
guard is owned by reverse mutation with a named test, restoring byte-identically.

---

## 4. Sequencing note for Task 13 — the arming step is the migration, not the canary

Merging is safe on its own, and I traced why: the automation tables are **not** in
the general profile bootstrap (`profile_state.py` contains no
`security_lifecycle_automation_runs`), and the migration module has **zero callers
anywhere outside `tests/`**. So on a production profile the tick hits
`LifecycleAutomationNotInstalled` → records `automation_schema_absent` → contacts
no provider. A partial schema fails closed with `LifecycleSchemaMismatch` rather
than self-completing.

But the shipped default is:

```python
DEFAULT_SECURITY_LIFECYCLE_AUTOMATION_CONFIG = SecurityLifecycleAutomationConfig(
    enabled=True, interval_minutes=5, batch_limit=2, apply_profile_transitions=False,
)
```

and `parse_security_lifecycle_automation_config` falls back to those defaults for
any **absent** key. The tick is already wired into the periodic loop
(`data_scheduler.py:1618`). So the moment the tables exist, unattended lifecycle
automation begins on a 5-minute cadence — **before** the single-case canary that
is supposed to precede it. `apply_profile_transitions=False` means no profile
mutation, so this is a provider-traffic and sequencing question, not a data-safety
one.

Recommended order for Task 13: read-only inventory → authorize the migration
**and in the same session write `security_lifecycle.automation.enabled = false`**
(or change the shipped default to `False` with a named owner test) → single-case
canary → then enable deliberately.

---

## 5. Constraints observed during this review

- Read-only throughout. No merge, push, provider call, production database
  operation, or App restart.
- Every mutation was applied to the branch worktree and restored byte-identically;
  `git diff --exit-code` verified clean after each batch.
- `docs/design/PROJECT_PRIORITY_MAP.md` was not modified.
- Reproduction scripts live outside the repository, in the session scratchpad.
- Three review lanes were commissioned; **one completed, one completed, and the
  third (unowned-guard census) plus all nine adversarial verify agents died on a
  session limit.** The §2 census is my own bounded substitute for the dead lane.
  No finding below was refuted by an adversarial pass, because that pass never
  ran — each was instead re-verified by me directly, by execution.

---

## 6. Round-3 adjudication (2026-09-01)

The implementer independently reproduced all seven findings and independently
corroborated both unowned guards (removing `transition_approval_authority` and
`terminal_finalization_not_pending` together in a separate `/tmp` copy still gave
`931 passed`). He corrected two of this review's conclusions. **Both accepted.**

| Point | Adjudication |
| --- | --- |
| F3's fix direction violated zero-migration | **His correction stands, mine was wrong.** The allowed blocker set is baked into the table `CHECK` (`schema.py:489`); SQLite cannot `ALTER` a `CHECK`. I wrote the fix without re-reading that constraint. |
| F4 belongs in the blocking set | **His correction stands, my ordering was inconsistent.** Same permanence class as F2, higher reachability. Blocking set is now F1–F4. |
| F6 is a pinned contract, not an unowned regression | **Correct**, and verified: `test_ticker_identity_scheduler.py:637`. |
| `market_confirmation_missing` as the plan-overflow slot | **Verified and endorsed** — genuinely unused, and already carries both locale labels, so it avoids reproducing F7. |
| Ship `enabled=False` by default | **Agreed** by both. |

Two conditions this review adds to his proposal:

1. **F3's diagnostic must reach a surface.** `candidate_budget_exceeded` in
   `context_json` is invisible today — the projection is `{blocker_code,
   retryable}` only. Widening it needs no migration. Without it the fix trades a
   false conflict for a vague truth.
2. **F6 must split two axes, not rename one state.** The pinning test binds
   "policy disabled" and "store unavailable" to the same outcome; the repair has
   to separate them and split the parametrized test.

Delegation for the implementation is at
`docs/superpowers/plans/2026-09-01-lifecycle-control-plane-repair-delegation.md`.
