# Security Lifecycle Resolution and Translation Continuation Design

**Status:** Approved design for implementation planning. Provider calls,
production access or migration, merge, live cutover, and push remain separate
authorization gates.

**Date:** 2026-08-26

**Base:** `fb586b02`

**Depends on:**
`docs/superpowers/specs/2026-08-24-trusted-lifecycle-automation-design.md`
and its completed live cutover. This continuation does not rewrite the prior
design or its migration authority.

## 1. Goal

Finish the user-facing automation contract around two observed gaps:

1. lifecycle evidence translation must be reusable, diagnosable, and suitable
   for source verification; and
2. cases must leave the attention queue automatically when SEC, IBKR, and
   professional-source evidence can establish a result or a bounded monitoring
   state.

The product should perform the same evidence gathering a careful person would
perform. A person handles genuine ambiguity, source conflict, or unavailable
required evidence. A person is not a mandatory final step when independent
source families agree.

## 2. Decisions

### 2.1 Translation is shared, but presentation is surface-specific

The existing fixed task ID `card_translation` remains stable for stored routing
and runtime compatibility. Its user-facing name becomes **Content translation**
or **內容翻譯**, because both analysis cards and lifecycle evidence use it.

There is one provider/model/effort/runtime setting. Lifecycle does not add a
second translation route.

Presentation differs by purpose:

- Analysis cards retain their existing English/Traditional Chinese switch.
- Lifecycle evidence always renders the verbatim source-language excerpt.
- A requested translation renders adjacent to the original, not instead of it.
- The translation is labeled machine-generated and shows provider, model, and
  harness provenance.

Side-by-side evidence is intentional. The lifecycle surface is a verification
surface, so the reviewer must be able to compare the derived translation with
the authoritative source without toggling context away.

### 2.2 Translation is hash-bound and not repeated automatically

The existing cache identity remains:

```text
(evidence_id, evidence_content_sha256, target_locale)
```

For an unchanged excerpt and locale:

- a successful translation is reused without a provider call;
- re-rendering, reopening a case, changing UI language, or restarting the app
  does not request a new translation;
- a failed attempt may be retried explicitly because no translation artifact
  was stored; and
- changed source content receives a new hash identity and may be translated.

Automatic retranslation merely because a different model is selected is out of
scope. A future explicit **Retranslate** action must preserve revisions and
provenance rather than overwrite the existing artifact.

### 2.3 Deterministic product copy does not consume translation models

Automation conclusions, impact summaries, blocker explanations, and queue
labels are generated from `rule_id`, structured fields, and closed reason codes.
The UI localizes them through normal English and Traditional Chinese resources.
It does not send those deterministic strings through an LLM.

Only arbitrary source excerpts use the Content translation task.

### 2.4 Source convergence drives automation

The primary source order is:

1. `regulator`: SEC filing chain and explicit event/effective-date facts;
2. `market_infrastructure`: IBKR contract identity, listing venue, market-data
   status, quote freshness when entitled, and current operational state; and
3. `publisher`: local professional or issuer news for completion, cancellation,
   and impact context.

General web search remains a typed fallback for a specific evidence gap. It is
not the default source and is not required when regulator and market evidence
already establish the answer.

Multiple publisher vendors or syndicated copies remain one source family. They
cannot imitate independent corroboration through article count.

## 3. Evidence Strength

### 3.1 Positive evidence, not a price alone

A price value is supporting evidence, not proof that the security remains
listed on its previous exchange. A quote may be delayed, frozen, stale, or for
an instrument that continues trading OTC after an exchange delisting.

Every market snapshot used for a lifecycle decision records, when available:

- contract ID;
- symbol and local symbol;
- security type and currency;
- listing/primary exchange and valid exchanges;
- market-data type or entitlement state;
- quote retrieval time and provider timestamp;
- last price and whether it is live, delayed, frozen, or unavailable; and
- the adapter version that normalized the snapshot.

Only a fresh, identity-matched market snapshot can satisfy market
corroboration. Delayed or frozen data may support an explanation but cannot by
itself prove current listing status. This follows the distinction in IBKR's
[contract metadata](https://ibkrcampus.com/docs/web-api/api-reference/trading/trading-contracts/get-contract-info)
and [market-data snapshot](https://ibkrcampus.com/docs/web-api/api-reference/trading/trading-market-data/get-md-snapshot)
contracts: instrument/listing identity and quote availability are different
facts.

### 3.2 Absence has bounded meaning

Failure to find a completion filing does not prove an event will never occur.
It may mean the event is announced but not effective, a compliance period is
still open, a provider is lagging, or required access is unavailable.

Absence therefore produces a dated statement such as **Not confirmed as of
2026-08-26**, never the timeless statement **Did not happen**.

An explicit regulator or issuer record may establish stronger negative facts,
including cancellation, withdrawal, regained compliance, or no change to the
tracked security. Those facts may resolve a case automatically.

### 3.3 Models and translations are not evidence families

A model may summarize, classify, or draft an explanation. A translation may
make source text readable. Neither is a new independent source family, and
neither may satisfy a regulator or market-infrastructure gate.

## 4. Automated Dispositions

Every current case derives exactly one user-facing disposition. This is a
projection over accepted assessments, automation runs, action readiness,
transitions, and staleness; it is not a second competing assessment state
machine.

### 4.1 `confirmed_monitoring`

Use when authoritative evidence identifies the event, but either its effective
date is in the future or required post-date market confirmation has not yet
become current. The existing action-readiness reason distinguishes
`waiting_effective_date` from `waiting_market_confirmation`.

- Accept the verified assessment when its conclusion requirements pass.
- Show the event under **Monitoring** rather than **Needs attention**.
- Schedule the next check from the explicit effective date and typed retry
  policy.
- Notify the user of the announced event without mutating the Universe early.

### 4.2 `confirmed_effective`

Use when the event is effective and all action-specific evidence gates pass.

- Apply only an already-reviewed reversible transition policy.
- Keep the activity visible until explicitly acknowledged.
- Move the case to **History** after the conclusion/action is current.
- Reopen automatically if evidence, identity, transition post-state, or rule
  version becomes stale.

### 4.3 `not_confirmed_yet`

Use when the latest bounded source check does not establish completion and does
not contain an explicit cancellation or no-change fact.

- Do not manufacture a negative assessment from missing evidence.
- Do not place the case in the human attention queue.
- Show the checked-at time, source-family outcomes, and next automatic check.
- Keep it under **Monitoring** with bounded backoff.
- If a source-defined deadline or termination date passes, preserve the wording
  **Not confirmed as of <date>**. After one final bounded source-family check,
  move it to History rather than leaving it in the attention or prominent
  monitoring queue. A new observation automatically reopens it.
- If no source-defined deadline exists, there is no invented universal expiry.

### 4.4 `exception_required`

Only these conditions require human attention:

- current source families assert incompatible identity facts;
- the security class, successor identity, or transaction structure remains
  genuinely ambiguous;
- an M&A event could be cash, stock, mixed, spin-off, or class-changing and no
  non-mutating rule independently resolves it;
- required evidence remains unavailable after its bounded retry policy; or
- the preview/reversal safety contract reports a non-retryable blocker.

Provider downtime, a future effective date, or a normal pending market update
does not create human work by itself.

## 5. Event Policies

### 5.1 Symbol continuation `A -> B`

Automatic acceptance and scheduling require all existing deterministic gates:
explicit regulator old/new symbols and effective date, matching CIK and
security class, no consideration/class-change terms, matching IBKR successor
identity and venue, no conflicts, and an eligible transition preview.

The new symbol may first appear in regulator evidence; it need not already be a
local alias. It enters user-owned tracking state only through the approved
transition at or after the effective date.

### 5.2 Venue transfer with unchanged symbol

Regulator and market evidence may resolve this automatically. Notify and update
venue presentation as supported, but do not remove and re-add the symbol merely
because the venue changed.

### 5.3 Terminal exchange delisting

The conclusion requires the tracked-security Form 25/25-NSE chain, explicit
effective date, complete bounded chain, and no successor fact. Before the date,
the case is `confirmed_monitoring`. Form 8-K Item 3.01 is an earlier notice or
listing-compliance signal, not interchangeable with a completed delisting; the
official contracts are the [SEC Form 8-K](https://www.sec.gov/about/forms/form8-k.pdf)
and [Rule 12d2-2/Form 25 process](https://www.sec.gov/rules/final/34-52029.pdf).

Profile mutation additionally requires current IBKR evidence consistent with
the loss of the old listing, no open portfolio position, and an eligible
preview. A missing quote alone is insufficient; a present price alone does not
disprove delisting.

### 5.4 M&A and other issuer events

Agreement is not completion, and completion is not necessarily a rename. SEC
completion evidence, known consideration/security terms, current contract
identity, and professional-source context determine whether the tracked
security disappears, continues, changes symbol, or is unaffected.

Clear asset acquisitions or issuer events that do not alter the tracked
security may resolve automatically. Cash-outs, stock exchanges, mixed
consideration, spin-offs, and class changes remain fully prefilled exceptions
unless a separately reviewed deterministic policy is added.

## 6. Scheduling and Retry

The scheduler owns routine uncertainty:

- future-effective events recheck on the effective date;
- missing post-date market confirmation rechecks daily for seven calendar days,
  then weekly until a source-defined deadline or a new observation changes the
  evidence set;
- an event without an explicit effective date or deadline rechecks weekly and
  never receives an invented expiry;
- retryable SEC, IBKR, or publisher failures retain typed reasons and retry
  times;
- unchanged evidence does not create duplicate assessments, translations, or
  transitions; and
- app downtime is caught up from due dates on the next startup tick.

Every monitoring row exposes `last_checked_at`, `next_check_at`, source-family
status, and the reason for waiting. A run cannot report success while omitting
the scheduled follow-up required by its disposition.

## 7. Queue and History UI

The Lifecycle view gains four views:

- **Needs attention**: only `exception_required` and attended manual drafts;
- **Monitoring**: `confirmed_monitoring`, `not_confirmed_yet`, and
  retryable provider/transition revalidation states;
- **History**: resolved, applied, reversed, cancelled, explicit no-change, and
  acknowledged inconclusive cases; and
- **All**: complete searchable audit view.

The default is **Needs attention**. Settled delistings, symbol changes, venue
transfers, and no-change conclusions no longer occupy the active queue.

Nothing is physically deleted. Observations, evidence, assessments, activity,
and transition receipts remain queryable. A new observation or stale evidence
automatically returns the case to the appropriate active view.

## 8. Translation Failure Contract

The generic `translation_failed` response is not sufficient for user action or
support diagnosis. The translation boundary maps known failures to closed,
safe reason codes, including:

- `translation_route_unavailable`;
- `translation_credential_missing`;
- `translation_auth_rejected`;
- `translation_rate_limited`;
- `translation_quota_exhausted`;
- `translation_model_unavailable`;
- `translation_timeout`;
- `translation_output_invalid`;
- `translation_provider_error`; and
- `evidence_changed`.

The response and UI include the effective provider/model/harness and a suitable
action such as retrying later or opening Content translation settings. They do
not include credentials, prompts, provider response bodies, or source text.

There is no silent cross-provider fallback. A configured route failure remains
attributed to that route.

## 9. Compatibility and Storage

Prefer derived projections and existing authority where they remain truthful:

- retain the internal task ID `card_translation`;
- retain hash-bound translation storage;
- reuse existing decision tier, action readiness, assessment provenance,
  transition authority, and activity rows;
- add a derived disposition and queue reason to read APIs rather than storing a
  second mutable workflow state; and
- store any new market snapshot fields only in the typed evidence locator or a
  reviewed additive shape.

If implementation proves a new closed assessment outcome or CHECK value is
required, it becomes a separately reviewed profile-schema migration. It may not
be slipped into application startup or inferred from existing rows.

### 9.1 Automation policy-version cutover

`trusted-lifecycle-automation-v3` is a semantic policy change, not an
operational retry token. At the cutover:

- every assessment whose `author` is `automation` and whose owning run uses an
  older policy version becomes stale, including an automation-authored
  assessment accepted with `acceptance_authority = human`;
- no old assessment, evidence, proposal, or run row is physically deleted. A
  v2 draft remains a stale draft; a stale v2 accepted assessment remains
  accepted until a replacement is accepted, then receives only the existing
  `superseded` status and timestamp while its payload and provenance remain
  intact;
- human-authored and legacy-migrated assessments are unaffected by the policy
  bump;
- the worker reserves a new v3 run key and creates a new revision or a typed
  monitoring result; an old v2 result never becomes current merely because it
  was accepted before cutover; and
- a pending ticker transition authorized by an older automation policy must
  fail closed before profile mutation. It may be reapproved only from a current
  v3 assessment, preview, evidence digest, and decision provenance.

Before any live v3 restart, a separately authorized read-only inventory records
the exact counts and IDs by assessment status, acceptance authority, policy
version, and pending transition authority. The design does not hard-code the
currently observed count because the user may review a draft before cutover.
Until a v3 result exists, the current view treats the old automation result as
stale and places the case in Monitoring for reprocessing; the old result remains
visible in assessment history with stale/superseded provenance. A policy bump
alone does not create a human-attention task.

This slice does not add a `reprocess_generation` column. Future replay of an
unchanged policy after an operational defect must use a separately designed
retry/reset authority; it must not manufacture a policy-version bump. This v3
bump is justified by changed decision and monitoring semantics, so invalidating
old automation authority is intentional.

## 10. Verification

RED-first coverage must prove:

1. a cached translation causes zero provider calls;
2. failed translation can retry, while changed evidence cannot reuse a stale
   artifact;
3. lifecycle evidence renders original and translation simultaneously;
4. deterministic conclusion copy is bilingual without a translation call;
5. each typed translation failure reaches distinct UI copy without secrets;
6. a live/fresh matching IBKR snapshot and a frozen/delayed quote produce
   different evidence strength;
7. a price after an exchange delisting cannot by itself mark the old listing
   active;
8. a future effective date and missing current market confirmation enter
   Monitoring, not Needs attention;
9. source conflict enters Needs attention;
10. resolved/applied cases enter History and automatically reopen when stale;
11. provider retry and app downtime catch-up do not duplicate transitions;
12. English and Traditional Chinese desktop/mobile browser matrices preserve
    evidence/source links, avoid overlap, and never substitute translation for
    original text;
13. v2 automation drafts and human-accepted automation assessments remain in
    history, become stale, and are reprocessed under a distinct v3 run key;
14. a v2 automation-approved transition cannot mutate profile state after the
    v3 cutover and can be reapproved only from current v3 authority; and
15. schema-object and column inventories remain unchanged, with no persisted
    disposition, queue-bucket, or reason-code column.

Offline tests use provider-shaped fixtures. Any live SEC, IBKR, translation, or
hosted-search call remains separately authorized and bounded. Production reads,
writes, schema migration, merge, and push remain separate gates.

## 11. Non-Goals

- Treating price presence or absence as a complete listing decision.
- Treating publisher count, model prose, or translated text as independent
  corroboration.
- Requiring general web search for a conclusion already established by SEC and
  market infrastructure.
- Automatically turning ambiguous M&A into a ticker rename.
- Deleting resolved evidence or transition history.
- Automatically retranslating unchanged evidence when model settings change.
