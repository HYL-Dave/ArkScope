# Independent Lifecycle Task: Routing Foundation

Status: routing foundation verified offline. This is not full-agent or live
admission, and the full feature is not ready for the requested hand-test gate.

Scope: the first implementation step of
`2026-09-07-lifecycle-web-bounded-followup.md`: independent task identity,
profile route, picker/admission, Settings save/reset/import/export, and one
explicit connectivity/schema check through the same four lifecycle adapters.

The built-in route is Anthropic / `claude-sonnet-5` / `high`, displayed as a
default, not automatically saved or copied from AI Research. The model is the
already exercised low-cost OAuth calibration choice, not a claim that a full
investigation has passed. The active profile credential still selects API-key
versus OAuth; there is no automatic change of credentials or billing source.
Opening Settings performs no model call. A failed route-store read for this
new task stops rather than falling back to another model/provider.

The short Settings check is one tool-free structured submission with the
existing 45-second test deadline. It does not search, fetch sources, inspect a
real target, write an investigation/acceptance record, or validate a complete
investigation. API-key output allowance is at most 8,192 tokens for this tiny
schema check (bounded by the exact model capability); OAuth output remains
provider-controlled. These are test bounds, not investigation runtime limits.

Not delivered by this foundation: adaptive orchestration, configurable
whole-run budgets, independent target/journal storage, local-news capability,
legacy-intake retirement, or production cleanup. Do not expose runtime knobs
until their actual dispatch boundaries enforce them. The old case endpoint is
only being detached from the Research model route here, not declared the new
target-first agent.

## Verification

- Initial backend RED: 43 failed, 5 passed. Failures expose the absent TaskId,
  borrowed Research route, absent four-channel task-test dispatch, and missing
  independent save/import/admission behavior.
- Additional backend RED owns custom-model eligibility and actionable
  route-read failure. Frontend RED owns the two localized task labels, the
  absence of a custom-model escape hatch, and selected-model-only diagnostics.
- Full backend: 6,981 passed, 12 skipped and three existing deprecation warnings
  (`backend-suite-r2.xml`). Full frontend: 1,610 passed (`frontend-suite-r7.json`).
  TypeScript/Vite build and the visible-literal scan pass, retaining the existing
  large-bundle warning. Final regression uses RAM-backed temporary test files;
  no product deadline, test timeout or assertion is relaxed.
- Nine backend mutants fail their named owners in the same 976-node focused
  set; four frontend mutants fail their owners in the full 1,610-node suite.
  Both restored baselines pass, and source hashes prove the worktree was not
  mutated. These are selected guards, not an exhaustive mutation claim.
- Browser r5 uses the actual Settings view and configuration routes with
  temporary profile/credential/discovery stores and synthetic adapter replies.
  Twelve scenarios cover both languages, 1,440/390/320px widths and all four
  channels: read without dispatch/save, independent selection, schema check and
  save. Twenty-four nonblank screenshots and geometry checks cover the new task
  card, not every pre-existing Settings panel. Actual provider calls: zero.
- Relative to the previous sealed source: 25 existing code/test files change,
  two test files are added, 50 backend and six frontend nodes are added, and no
  node is removed. Four relevant schema files retain their exact prior bytes.
  All 330 files in the previous instrument-scoping packet verify unchanged.
- No production data read/write, provider call, App restart, merge or push.

## Earlier Campaigns

Initial full frontend failures were vocabulary-count owners updated for the
five added keys, not removed assertions. The first backend suite still held an
old three-task discovery expectation; its correction was included in the final
full rerun. An initial unrestricted `pytest` invocation collected historical
evidence scripts and failed collection; the repository suite command is
`pytest tests`. Historical packets were not edited to fix that invocation.

Late negative controls exposed retained unknown-model promotion. The first
correction also trusted an old discovered row over the current retirement rule;
the unchanged retired-model owner caught that regression, and the correction
now preserves that rule. Frontend r4 and mutation r1 retain the failure.

Two scanner runs then exceeded their normal test deadline, and browser r4 did
not observe the save badge within five seconds. A contemporaneous test process
was observed in `jbd2_log_wait_commit`, with I/O pressure but no CPU/memory
pressure. Browser r5 passes all scenarios on the same product code; it adds
failure diagnostics, not a changed save contract. Frontend r7 and mutation r3
pass using RAM-backed temporary files and four workers. The earlier failures
remain here; this does not claim to fix or benchmark general App I/O latency.

## Deliberate Contract Changes

- The catalog now has four tasks. Exact catalog/discovery expectations are
  updated; the older tasks' model routes, auth rules and fallback behavior are
  not changed. Only the new task rejects unknown/custom models and route-read
  fallback. Older-sidecar frontend compatibility keeps this new route optional.
- Settings previously combined every disabled model's reason beneath the
  selected model, making a usable Opus selection appear blocked by Fable's OAuth
  policy. The paragraph now describes only the selected model. Disabled options
  retain their individual reasons; selected unsupported Spark still explains
  its own restriction. Both language tests own the deliberate display change.
- A retained unknown investigation route stays visible but cannot be tested;
  the frontend cannot promote a rejected/missing capability into eligibility.
  Explicit backend reasons survive, while a currently retired model remains
  disabled even if its old discovery entry said it was usable. Other tasks'
  existing custom-model positive controls remain unchanged.
