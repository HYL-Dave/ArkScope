# Lifecycle Honesty Repair Design

**Status:** Revised design amendment awaiting confirmation before implementation
planning. Provider calls, production database access, App restart, merge, and
push remain separate authorization gates.

**Date:** 2026-08-27

**Repair base:** `11e7a5d4f6856062a5ac00a8d90ed97b5c2e56cb`

**Amends:**
`docs/superpowers/specs/2026-08-26-lifecycle-resolution-and-translation-continuation-design.md`

## 1. Goal

Repair five independently reproduced honesty gaps before the lifecycle
resolution branch may be admitted for merge:

1. source-deadline citations are not validated against their evidence;
2. source-deadline extraction accepts historical, negated, and superseded
   dates;
3. a case that was never confirmed can be labeled `confirmed_effective`;
4. an operationally failed run cannot be replayed under an unchanged semantic
   policy after a code repair; and
5. the exact `not_confirmed_as_of` date is discarded before presentation.

The repair preserves the already verified translation, IBKR evidence-strength,
pure-projection, v2-preservation, and transition fail-closed contracts. It does
not introduce a second lifecycle state machine or a profile-schema migration.

## 2. Governing Failure Direction

The product must prefer an active, bounded monitoring state over a false claim
that an event is complete or permanently resolved.

- Invalid provenance is a product defect and fails loudly and atomically.
- Ambiguous filing prose is an evidence limitation and yields no deadline.
- A missed deadline is safer than a false deadline. A missed deadline leaves the
  case in Monitoring; a false past deadline could remove a live case from active
  review.
- Operational replay authority is separate from semantic policy authority.

## 3. Citation Validation At The Persistence Boundary

### 3.1 One validator contract

The fact kernel owns one byte-exact citation validator. It receives an evidence
row, byte start, byte end, and cited-text SHA-256, then verifies:

- the evidence ID resolves to evidence owned by the same automation run;
- `0 <= start < end <= len(excerpt.encode("utf-8"))`;
- the selected bytes are valid UTF-8; and
- SHA-256 of those exact bytes equals the supplied digest.

Both automation facts and every blocker carrying source-deadline citation
fields use this validator. Producer self-consistency is not sufficient: tests
must feed the producer's real output through
`SecurityLifecycleFactKernel.complete_run`.

### 3.2 New and retained evidence

Validation resolves citations across the union of:

- evidence normalized in the current `complete_run` call; and
- evidence already persisted for the same automation run.

A deadline may not cite evidence from another run or case. The blocker context
uses the producer-local evidence ID before persistence and is rewritten to the
persisted evidence ID in the same transaction.

### 3.3 Trigger and closed scope

The complete deadline-provenance set is:

```text
source_deadline
source_deadline_evidence_id
source_deadline_span_start_byte
source_deadline_span_end_byte
source_deadline_cited_text_sha256
source_deadline_rule_id
source_deadline_rule_version
```

At the `complete_run` boundary, the presence of **any** member of this set
triggers deadline-citation validation and requires all members. This rule is
independent of `monitoring_reason`:

- pre-deadline `event_completion_not_confirmed` may omit the entire set, but a
  supplied set must validate; and
- final `not_confirmed_as_of` requires the complete validated set plus a valid
  completed-check `as_of` date.

This means a producer defect before the deadline fails loudly rather than
persisting an unverified citation until the final tick.

The kernel-generated `source_conflict` blocker and
`defer_transition_revalidation` blockers remain closed, citation-free shapes.
They are outside this deadline validator by design: the former is synthesized
from already validated facts after `_normalize_blockers`, and the latter is
inserted only for the two typed transition-revalidation reasons with `{}`
context. Neither path may acquire source-deadline fields without first being
routed through the shared citation validator.

### 3.4 Atomicity and errors

A missing evidence ID, invalid byte boundary, invalid UTF-8 boundary, forged
digest, missing required deadline field, or mismatched rule identity raises a
typed `ValueError("blocker_citation")` before blocker/run terminal state is
committed. The worker records the operational failure through its existing
persist-phase failure path. No partially persisted evidence, fact, blocker, or
terminal run state is allowed.

This citation enforcement and the failed-run replay authority in Section 6 are
one inseparable delivery unit. The citation validator may not ship on its own,
because its intended atomic failures require the new execution-revision replay
path after a producer repair.

## 4. Conservative Source-Deadline Extraction

### 4.1 Accepted clauses

The deterministic extractor accepts one date only when the date is attached to
an affirmative current clause such as:

- `may be terminated if ... by <DATE>`;
- `outside date is|shall be|remains <DATE>`;
- `termination date is|shall be|remains <DATE>`; or
- `outside date|termination date has been|was extended to <DATE>`.

The accepted span is the exact source sentence. An explicit directional
extension such as `extended from <OLD_DATE> to <NEW_DATE>` emits exactly the
date governed by `to`; the old `from` date is not a target candidate. After the
accepted grammar identifies its target position, more than one target date
(for example, `extended to <DATE_A> or <DATE_B>`) or no target date emits no
deadline.

### 4.2 Rejected clauses

The extractor emits no deadline for:

- original, former, previous, or superseded dates;
- dates that only establish an `as of` observation;
- negated or hypothetical statements such as `do not expect`;
- statements saying a date was extended without naming the new date;
- historical statements whose only date precedes an extension; or
- any prose outside the closed accepted grammar.

This is intentionally precision-first. A real clause outside the grammar leaves
the case in Monitoring; it never moves the case to History.

The deadline rule remains
`sec.explicit_transaction_termination_date`. Introduce a dedicated
`_SOURCE_DEADLINE_RULE_VERSION = "4"` used only when constructing
`SecSourceDeadline`. Keep the existing shared `_RULE_VERSION = "3"` unchanged
for every SEC fact and SEC evidence `source_locator`. Do not add this extractor
version to decision-policy `RULE_VERSIONS`.

The deadline version therefore changes blocker citation metadata only. It does
not change persisted evidence identity, fact identity,
`decision_provenance_sha256`, assessment authority, or transition authority.

## 5. Truthful History Projection

A validated, fully checked `not_confirmed_as_of` result projects as:

```text
disposition = not_confirmed_yet
queue_bucket = history
reason_code = not_confirmed_as_of
disposition_as_of = <date of the completed final check YYYY-MM-DD>
next_check_at = null
```

`not_confirmed_yet` and `history` are intentionally orthogonal here. The event
was not confirmed, while active checking has ended at the validated
source-defined boundary. A new observation or stale evidence still reopens the
case through the existing projection rules.

`LifecycleDispositionProjection`, the read API, and frontend API types gain the
nullable derived field `disposition_as_of`. It is not stored in SQLite.

The validated `source_deadline` triggers the final check. `disposition_as_of`
records the date on which that check actually completed. They may differ after
App downtime; the product must not backdate a later catch-up check to the source
deadline.

Concretely, `_pending_event_monitoring` must replace the existing
`context["as_of"] = deadline_date.isoformat()` assignment with
`context["as_of"] = today.isoformat()` when the final check completes. It keeps
`context["source_deadline"]` as the separate source-defined boundary.
`disposition_as_of` derives only from the validated `as_of` field and never
falls back to `source_deadline`.

The History presentation must combine disposition, reason, and date so it reads
as:

```text
Not confirmed as of 2026-08-27; active checking stopped.
截至 2026-08-27 尚未確認；已停止主動追查。
```

The general disposition label remains the existing `Not yet confirmed` /
`尚未確認發生`. Rendering History never acknowledges the row.

## 6. Deploy-Time Failed-Run Replay Authority

### 6.1 Separate axes

Add a closed module constant named `AUTOMATION_EXECUTION_REVISION`. It identifies
the deployed automation implementation, not decision semantics.

The execution revision:

- participates in automation run identity and is recorded in query/audit
  context;
- never changes `AUTOMATION_POLICY_VERSION`;
- never participates in `decision_provenance_sha256`;
- never participates in assessment acceptance authority; and
- never participates in ticker-transition approval or apply checks.

### 6.2 Semantic run identity

The existing semantic identity remains:

```text
case_id
observation_fingerprint_sha256
policy_version
mode
input_evidence_set_sha256
```

Reservation first finds the latest run with that semantic identity, including
earlier replay runs.

- No matching run: create the first run under the current execution revision.
- Latest run is `queued`, `running`, `blocked`, `succeeded`, or `cancelled`:
  retain existing behavior and do not fan out a new run.
- Latest run is `failed` and already has the current execution revision: do not
  retry it again.
- Latest run is `failed` under an older or absent execution revision: create one
  distinct replay run bound to the current revision and predecessor run ID.

The replay run key includes the semantic identity, execution revision, and
predecessor failed run ID. The old failed row remains immutable. A successful
replay becomes the latest semantic run, so later deployments do not replay it
merely because their execution revision differs.

Rows created before this amendment have an absent execution revision and are
treated as legacy revision `unknown`, not guessed or rewritten.

### 6.3 Deliberate boundary

`AUTOMATION_EXECUTION_REVISION` is a deploy-time repair lever. It permits a new
release to replay unchanged evidence after fixing an operational defect without
manufacturing a policy bump.

This amendment does not add an operator endpoint, UI command, or attended reset
action. Operator-triggered replay remains a separately designed feature. The
absence of that operator control must remain explicit in closeout limitations.

No profile-schema change is required. Semantic matching reads existing indexed
run columns and the bounded query context, and remains limited by the existing
per-tick case budget.

Sections 3 and 6 must be implemented, mutation-tested, and admitted together;
neither one is a separately shippable partial repair.

## 7. Verification

RED-first coverage must prove:

1. producer-created valid deadline citations for both pre-deadline monitoring
   and final `not_confirmed_as_of` pass through the real kernel;
2. any partial deadline-provenance set, missing evidence, cross-run evidence,
   out-of-range span, invalid UTF-8 boundary, forged hash, or mismatched rule
   identity fails atomically at the kernel boundary;
3. the current simple accepted forms remain regression controls, while the true
   RED directional-extension case `extended from March 1, 2026 to June 1, 2026`
   emits exactly `2026-06-01` through the fixed extractor;
4. historical, original, superseded, negated, `as of`, ambiguous-target, and
   unsupported clauses emit none and retain Monitoring; a sentence with two
   target dates after `to` emits none, while a directional `from ... to ...`
   clause is not misclassified as ambiguous;
5. pre-deadline contexts carrying source-deadline fields are validated even
   though their `monitoring_reason` is not `not_confirmed_as_of`, while blockers
   with no deadline fields remain unaffected;
6. `not_confirmed_as_of` projects as `not_confirmed_yet + history`, exposes the
   exact completed-check date, renders truthful bilingual History copy, and
   does not backdate an overdue startup catch-up to the source deadline;
7. a failed semantic run is replayed once after the execution revision changes,
   is not replayed repeatedly at the same revision, and is not replayed after a
   successful replacement;
8. `_RULE_VERSION` remains `"3"`; introducing the deadline-only version leaves
   all existing SEC evidence/fact identities and decision provenance
   byte-equivalent;
9. changing execution revision leaves decision provenance and ticker-transition
   authority byte-equivalent;
10. kernel-generated `source_conflict` and transition-revalidation blockers
    retain their closed citation-free shapes;
11. no mutable disposition column or startup DDL is introduced; and
12. all repaired seams have explicit mutation owners.

After focused tests pass, rebuild the mutation ledger, bilingual desktop/mobile
browser matrix, schema comparison, offline replay authority, and evidence
manifest. The packet at product/test authority `f63a044c` remains an accurate
record of its inputs and tests but is not merge admission.

## 8. Repository Decision Log

The uncommitted 2026-08-27 RED entry currently present on `master` remains a
historical review record and must not be overwritten or folded into a final-only
summary. This worktree does not modify that user-owned change. After repair
admission, add a separate GREEN closeout entry that explicitly supersedes the
RED merge hold while preserving both records.

## 9. Hard Stops And Non-Goals

Until separately authorized, this amendment performs no:

- provider or general-web call;
- production database read, write, backup, restore, or migration;
- App restart or live scheduler replay;
- merge; or
- push.

Operator-triggered replay, broader legal-language extraction, new evidence
providers, general web search, and automatic retranslation remain out of scope.
