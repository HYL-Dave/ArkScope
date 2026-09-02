# Lifecycle SEC Admission and Detail Clarity Design

## Goal

Keep lifecycle automation deterministic and auditable while preventing broad
SEC candidate collection, repeated evidence history, and storage-shaped API
payloads from overwhelming or breaking the operator interface.

## Delivery Boundaries

The work ships as three independently reviewable changes:

1. repair the proposal API/UI contract that crashes BLBD and CCL;
2. separate broad SEC candidate discovery from lifecycle-case admission; and
3. simplify the case detail into a current decision summary with lazy audit
   detail.

The first change must not wait for either policy or layout work. No change in
this design deletes the 36 stored source observations or rewrites production
profile data. Migration, production canary, App restart, merge, and push remain
separately authorized operations.

## Proposal Contract

`security_lifecycle_action_proposals` remains the durable internal record. The
public proposal projection is a closed DTO containing only:

- `proposal_id`;
- `action_type`;
- `status`;
- `projected_block_reason`;
- `replacement_ticker`.

The current UI does not use the historical tracking-source snapshot to decide
or execute a proposal. It must not render that field. Storage-only identifiers,
fingerprints, dedupe keys, raw JSON, reasons, and timestamps do not cross the
case-detail boundary.

The browser client validates the case-detail response at runtime. Declared
array fields must be arrays, proposal entries must match the closed DTO, and a
malformed payload fails with a typed response error instead of crashing during
React rendering.

## SEC Candidate and Admission Model

SEC collection has two distinct stages:

1. **candidate discovery** retains the source observation and an auditable
   screening result;
2. **case admission** promotes only direct or deterministically material
   tracked-security events into the active lifecycle queues.

Direct candidates are Form 25/25-NSE, 8-K/8-K/A Item 3.01, 8-A12B, and 8-K12B.
Form 25 and registration forms still require an exact tracked ticker/security
class or explicit successor binding; same CIK alone is insufficient.

8-K Items 1.01, 2.01, and 5.01 plus DEFM14A/DEFA14A are conditional candidates.
They are admitted only when deterministic extraction establishes a
tracked-security effect, an explicit old/new symbol, a source/destination
venue, an identity-bound effective date, or a transaction structure that
proves the tracked registrant's identity is unchanged.

Items 2.03, 3.02, 3.03, 5.03, 7.01, 8.01, and 9.01 never admit a case by
themselves. They may remain locators on an already admitted filing.

Unknown candidate forms are never silently discarded. They remain visible in
the candidate audit with a counted `unknown_form` reason. Known candidates that
do not produce a material fact remain source observations with a closed
screening reason; they do not remain indefinitely in an active queue.

The candidate audit must answer why an observation was admitted, screened out,
or left unclassified. It exposes a closed DTO and never a database row.

## Extraction Capability and Date Bounds

BLBD and CCL are frozen positive-control fixtures for material promotion. CDE
is a negative date-control fixture. Removing the relevant extraction behavior
must make a named test fail.

An effective date must be tied to an identity-bearing sentence and fall within
the bounded filing-chain window. A date outside that window is recorded as a
typed ambiguity and is not emitted as an `effective_date` fact. Absence of a
material fact is trusted as screening only when the positive-control suite
proves the extractor remains capable.

## Primary Detail

The default case view answers only:

1. what happened;
2. the effect on the tracked security;
3. effective date;
4. successor ticker or destination venue;
5. SEC form, filing date, relevant items, and filing link;
6. Nasdaq, Massive, and IBKR corroboration state; and
7. what is still missing and the next verification time.

The seventh item is mandatory. A quiet queue without an explanation of its
next action is not an honest automation surface.

CIK, accession, hashes, rule IDs, raw facts, repeated filing-chain excerpts,
prior runs, and storage provenance move to a lazy audit view. That endpoint
also uses closed projections. Original SEC excerpts remain available for
citation and on-demand translation; they are not repeated in the primary
summary.
