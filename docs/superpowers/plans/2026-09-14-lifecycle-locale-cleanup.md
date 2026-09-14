# Lifecycle Locale Cleanup Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task-by-task.

**Goal:** Resolve CENSUS-I18N-001's original 100 candidates without deleting
labels reached through current presenters or provider-indexed lookups.

**Architecture:** Remove 41 obsolete Explore leaf keys in each locale. Retain
nine keys in each locale whose consumers the literal scanner misses. No UI,
API, model route, translation execution, or tracking behavior is changed.

**Tech Stack:** TypeScript resources, Vitest, existing i18n source census.

**Spec:** Cleanup audit `CENSUS-I18N-001`; original census compared with
`2026-09-14-anthropic-child-async/checks/accepted-census/census.json.gz`.

## Constraints

- Resolve original candidate IDs, not all current unresolved i18n results.
- Keep both `lifecycle.current.check*` strings used in `InvestigationView`;
  both `fields.successorTicker/effectiveDate` narrative labels;
  three `listingEvidence.authorities` labels; and both `translation.providers`
  labels used in `TrackingDecision`. Their nine-key inventories must match.
- Retain current provider/model attribution, original evidence, activity and
  review behavior. Historical data and documents are outside this change.

## Task 1: Remove Obsolete Copy

Modify `apps/arkscope-web/src/i18n/resources/{en,zh-Hant}/explore.ts`,
`src/i18n/resources.test.ts` and `src/lifecycle/legacySurfaceRemoval.test.ts`
(test paths relative to `apps/arkscope-web`).

- [x] Add a paired-locale missing-key guard for the explicit 41-key removal
  inventory. Run it first; expect two locale failures because old keys remain.
- [x] Delete those leaves and empty objects, with no replacement aliases.
  Retain the nine shared keys. Update existing exact counts from 1219 to 1178
  for both Explore inventories, 662 to 621 for its lifecycle subtree, and
  3009 to 2968 for the whole-resource count. The first focused run exposed
  the second namespace and total counts; retain that failed run in evidence.
- [x] Run the two locale guards, resource inventory, current investigation,
  activity, narrative and provider-label tests; expect zero failures. Check all
  frontend tests, type checking, build and visible-literal scanner in sequence.
- [x] Re-run source census, record the original 100 dispositions as 82 removed
  and 18 retained with consumer names. Do not treat new SEC/Research labels or
  dynamic unresolved candidates elsewhere as obsolete by association.
- [x] Record evidence and commit this scope independently of SQLite deployment.

Completed at `4d121b17`; paired disposition manifest, retained consumers and
acceptance: `docs/superpowers/evidence/2026-09-14-runtime-cleanup-closeout/README.md`.
