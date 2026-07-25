# Engineering Issue Register

> **Status**: ADOPTED - INDEPENDENT REVIEW GREEN 2026-07-25
> **Created**: 2026-07-25
> **Purpose**: Single owner for small, evidenced engineering debt that does not
> yet justify a dedicated workstream in `PROJECT_PRIORITY_MAP.md`.

## 1. Boundary

This register is not a second priority map and is not an exception list for
known failures. It owns only bounded issues that can be reproduced today and
can normally be repaired in a grouped maintenance batch.

The following do not belong here:

- product ideas or unverified reports;
- active slices and workstreams already owned by `PROJECT_PRIORITY_MAP.md`;
- permanent verification rules already owned by a spec or test;
- historical observations that have already been resolved; and
- contract violations, unresolved design decisions, database/schema changes,
  authority changes, or protected-boundary changes. Those must be promoted to
  a reviewed slice before implementation.

`PROJECT_PRIORITY_MAP.md` remains the resolver for what happens next. It links
here rather than duplicating individual small issues.

## 2. Admission And Lifecycle Rules

### 2.1 Admission requires evidence

An issue enters only when it has both:

1. a deterministic reproduction command or a stable `file:line` source fact;
2. a concrete impact statement.

An unverified observation remains outside the register until those facts
exist. A reviewer must be able to reproduce the evidence without relying on
conversation history.

### 2.2 Counts are dated observations

Every count, ID set, timestamp, or database-derived quantity records its
`observed_at` date. It is never an acceptance constant. The implementing batch
must rederive it before changing product code and stop if the issue shape has
materially changed.

### 2.3 Promotion is mechanical

Promote an entry to a separately reviewed slice when any one is true:

1. it violates an existing product or safety contract;
2. it needs a product/design decision;
3. it touches a byte-gated owner, authority source, database schema, migration,
   or another protected boundary.

Promotion removes the implementation details from this register. The entry
keeps only a link to its new canonical owner and moves to `promoted`.

### 2.4 Batching does not waive tests

Batching removes repeated spec/plan overhead. Every repaired behavior still
requires a named regression test or a documented reason why an existing named
test already owns it. A batch may not use this register to bypass review.

### 2.5 Closure requires evidence

An entry closes only with the commit that repaired or deliberately retired it,
the exact verification command, and the observed passing result. `Fixed`,
`cannot reproduce`, and `obsolete` without evidence are not closure states.

### 2.6 Open entries need a next owner

Every `open` entry has an owning batch or a concrete revalidation trigger plus
a next action. An entry with neither is invalid and must be promoted, closed,
or removed as unverified. This is the anti-graveyard rule.

## 3. Fields And Statuses

Each entry records:

| Field | Meaning |
|---|---|
| `id` | Stable `EIR-NNN` identifier. Never reuse a retired ID. |
| `status` | `open`, `promoted`, `closed`, or `invalidated`. |
| `observed_at` | Date of the currently cited observation. |
| `impact` | User, correctness, operability, or maintenance consequence. |
| `evidence` | Reproduction command and/or canonical source reference. |
| `owner` | Owning maintenance batch or promoted workstream. |
| `next_action` | Smallest concrete action that advances the entry. |
| `closure_evidence` | Empty while open; commit, command, and result at close. |

## 4. Open Entries

### EIR-001 - Retire unreachable `.page-head*` CSS

- `status`: `open`
- `observed_at`: `2026-07-25`
- `impact`: Dead selectors preserve a second, obsolete page-header vocabulary
  beside the shipped `.ui-page-header*` primitive and make responsive CSS
  audits noisier.
- `evidence`:
  - definitions remain in `apps/arkscope-web/src/styles.css:923-938` and
    `apps/arkscope-web/src/styles.css:1119-1125`;
  - I18N-6 independently recorded both selectors as dead in
    `docs/superpowers/specs/2026-07-25-i18n-6-release-design.md:622`;
  - reproduce the live-owner census with:

    ```bash
    rg -n 'className="page-head|className="page-head-actions' \
      apps/arkscope-web/src --glob '*.tsx' --glob '!*.test.tsx'
    ```

    Expected on the observation date: no output. `detailpage-head` and
    `.ui-page-header*` are different owners and do not count.
- `owner`: future frontend CSS hygiene batch.
- `next_action`: RED-first selector-absence coverage, remove both desktop and
  `max-width:760px` rules, then run frontend tests/build and the affected
  responsive visual gate.
- `closure_evidence`: none.

### EIR-002 - Eliminate the environment-dependent non-green backend baseline

- `status`: `open`
- `observed_at`: `2026-07-25`
- `impact`: The full backend suite is not green and changes classification
  across mounted-data/config environments. That forces every change review to
  reconstruct failure-set equivalence and can conceal a new failure inside
  familiar noise.
- `evidence`:
  - `docs/superpowers/evidence/2026-07-25-sa-extension-reliability-control-clarity.md:188-200`
    records matched implementer A/B at `30 failed / 7 errors` and matched
    data-bearing reviewer A/B at `31 failed / 0 errors`;
  - `docs/design/PROJECT_PRIORITY_MAP.md:527` records that the two 31-ID sets
    were byte-identical while the absolute classification was environment
    dependent;
  - rederive before work in two clean, equally configured archives with:

    ```bash
    pytest -q
    ```

    Capture normalized failed/error node IDs, environment inputs, and the run
    date. Neither `31` nor any historical family count is an allowlist.
- `owner`: backend test-reliability maintenance batch.
- `next_action`: perform a fresh virgin census, group failures by root cause,
  and promote any group that requires a data-authority or fixture-contract
  decision. Fix only genuinely independent fixture defects in one batch.
- `closure_evidence`: none.

### EIR-003 - Audit the 89 I18N-2-era Settings copy rewrites

- `status`: `open`
- `observed_at`: `2026-07-25`
- `impact`: These are copy-quality candidates, not known correctness defects.
  They predate the I18N-3 Traditional-Chinese byte-preservation rule, so awkward
  or unnecessary rewrites could remain without an explicit linguistic review.
- `evidence`:
  - `docs/design/PROJECT_PRIORITY_MAP.md:533` records the post-release audit and
    the dated `89` observation;
  - `docs/superpowers/specs/2026-07-20-app-wide-i18n-decision.md:234-240`
    records that I18N-2 predates the general byte-preservation rule;
  - original visible literals remain recoverable from commit `ac578581`.
- `owner`: future bilingual copy-quality maintenance batch.
- `next_action`: regenerate the I18N-2 comparison from `ac578581`, produce an
  exact key-by-key ledger, classify each difference as intentional,
  terminology-required, recomposed, or review-needed, and change only the
  reviewed subset. Do not bulk-revert resources.
- `closure_evidence`: none.

## 5. Seed Triage: Items Not Opened

These observations were considered while creating the register and are not
duplicate entries:

| Observation | Canonical disposition |
|---|---|
| jsdom popup contrast gate must remain paired with real Chrome computed styles | Permanent release rule already recorded in `2026-07-25-sa-extension-reliability-control-clarity-design.md:101-107`. |
| Partial-status `#b45309` on `#fff3e0` measured `4.58:1` | Dated accepted boundary already recorded in the same spec at lines 98-99; changing either color must rerun its gate. |
| Identical zh/en resource values | Not admitted. A fresh recursive resource comparison reproduces `160` identical leaves. The review additionally reported `24` multi-word non-CJK leaves and proposed `2` aria, `6` routing, and `5` runtime candidates, but that exact key ledger and its classification rule are not persisted in the repo and therefore are not independently reproducible yet. Equal identifiers and professional terms may be deliberate. Persist and review the exact candidate keys before opening an issue; none of these counts is an acceptance constant. |
| SA evidence used different absolute full-suite summaries | Resolved and documented in the evidence packet and priority-map decision log; no open repair remains. |
| Coverage v2 blunt 15-minute threshold | Formal queued workstream, not a small issue. `PROJECT_PRIORITY_MAP.md` is its owner. |
| Calibration Anthropic refusal seam | Existing-contract violation promoted directly to the dedicated micro-slice plan; it never enters this register. |
