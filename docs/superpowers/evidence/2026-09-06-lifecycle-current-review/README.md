# Current Review UI, API And Research

September 6 offline Task 7 continuation on `codex/lifecycle-tracking-first`,
base `0b66732ba4a77c4ba823537001828c1a75563c5d`. Measured gates are complete;
`verification.json` and the create-only `files.sha256.json` seal identify final
admission. This packet does not replace earlier sealed evidence.

## Measured Results

| Gate | Result |
| --- | --- |
| Backend focus, baseline and restored | 1248 passed each |
| Backend mutations | 14 independently killed by named owners over that complete focus |
| 80-file integration | 2067 passed |
| Full backend | 6245 passed, 12 skipped, three existing warnings |
| Full frontend, baseline and restored | 1516 passed each |
| Frontend mutations | 22 independently killed by named owners over the entire frontend |
| Browser | 36 EN/zh-Hant scenarios at 1440/390/320 widths, 120 screenshots |

Against the Task 6 packet, the complete backend adds 53 nodes and removes none.
The wider integration focus includes those and 59 previously existing agent/tool
nodes. Frontend adds 145 nodes and retires 61; every retired node has a ledger
entry. Unknown/malformed payload and real legacy-history controls are retained,
not replaced with cast-only fixtures. Typecheck, production build and i18n gates
are recorded by the sealer, which also verifies the three preceding seals and
unchanged lifecycle/identity/membership schema files.

## Product Contract

- The primary view answers current collection, listing, continuation, next action,
  outstanding condition and observation/next-check time. Healthy active coverage
  is separate from attention/history rows. Source-only and source-missing questions
  are not silently omitted; a reused ticker is not the historical security.
- UI, API and advertised Research tools share one closed read projection. Reads
  cannot contact a provider, create an assessment, grant consent or apply an action.
  Freshness, source consistency and actual receipt/effect checks prevent invented
  healthy counts and successful-looking transitions.
- Review preparation is read-only. One explicitly confirmed command uses Task 6's
  finding/effect binding. Changed dates/options need a fresh packet. Unknown write
  outcomes require readback, not automatic resubmission. A scheduled action is not
  applied; current effects changed after application are not a successful reversal.
- Provider rechecks require explicit confirmation. Durable running state does not
  depend on in-memory progress. Unrelated/stale job results cannot complete a
  pending request; a failed status read never creates another provider request.
- Audit/history is lazy, with explicit shared Content Translation, preserved source
  text, typed errors and closed tracking receipts. A manually confirmed receipt is
  not labeled automatic. Unknown reversal readiness remains unavailable, not true.
- The old manual assessment/evidence/proposal workflow is intentionally retired
  from the primary screen. The two old Python case readers remain unadvertised
  compatibility reads. Existing databases, history, receipt APIs and all other
  tools/credential transports retain their contracts.

## Verification Boundaries

`tests/fixtures/lifecycle_current_v1.json` is owned by a real temporary-store
prepare/confirm/readback workflow, including activity receipts. Only generated
resource IDs and digests are normalized; product field shapes are not mocked.
The React/browser fixtures consume that same projection. Browser request handling
is synthetic and rejects unexpected/external requests; it is not a live provider
or production UI canary.

`test-retirement.json` accounts for every removed old UI node. Synthetic legacy
review fixtures preserve the exact bilingual meaning of the old accepted result;
they are not claimed as a new live migration. Existing real migration tests remain.
The additional schema/array/identity and concurrency tests protect the new contract,
not merely old CSS classes. Guard mutations run independently against the whole
affected backend focus or entire frontend suite, never the one owning file alone.

The first backend campaign was deliberately interrupted after its 1,248-pass
baseline, during the first mutation, to strengthen legacy-meaning preservation.
Its source copy was restored and is retained separately; no partial result is
combined into final admission. Earlier frontend failures reflected retired
fixtures, i18n inventory/scanner alignment, and an incorrect test string
(`Unresolved` versus `Status unresolved`). They are not claimed as product RED
proof or as passing admission. Earlier browser runs are historical, not substituted
for the final frozen-source rerun. The last browser rerun adds mechanical binding
of all 265 frontend/fixture/harness source files before/after execution and
records screenshot pixel variance. The sealer checks those exact bytes against
both admitted test source copies, except the separately recorded browser harness.

During the `acknowledge_wrong_receipt` and `missing_reason_translation` frontend
mutants, the existing schedule-consumer test also exceeded its five-second test
deadline. Those extra failures are retained in the complete result, not counted
as mutation owners. Each mutant must still fail its named current-review owner,
and final admission requires the complete restored frontend to pass.
The first frontend campaign also hit that timeout during its restored run, so the
campaign is not admission despite all 22 named mutation owners failing correctly.
The replacement campaign caps Vitest at four workers and reruns baseline, all
mutants and restored tests; baseline and restored both pass 1516. No product/test
source, assertion or timeout is changed. Original pre-edit product RED output is
not reconstructed from later fixture-cleanup errors; the independently measured
mutation failures and retained controls are the executable regression evidence.

## Reproduction

Run `scripts/verify.py --repo <worktree> --kind backend|frontend --staging <new-dir>
--temp-root <new-dir>` with the project Python. It copies source without application
data or environment/developer configuration; all stores and mutations are external
temporary artifacts. The full backend uses the working tree and the suite's
temporary-store guards. Run `scripts/run_browser.py --output <new-dir>` with
Playwright/Chromium installed. Its isolated Vite server is always stopped.
`scripts/seal.py` checks source/delta/owner/previous-seal evidence, then runs
typecheck, production build and i18n gates before create-only publication.

## Still Open

The Web-backed finding/confirmation path and bounded Web adapter need the agreed
model/auth scope; API-key-only initial support remains a product question, not
provider-call authorization. Complete-population production cutover is still a
separate operation. No production read/write, provider call, migration, App
restart, commit, merge or push occurs in this Task 7 implementation. The earlier
authorized three-case retirement and 15-day price repair are not repeated.
Do not call the entire Lifecycle redesign complete or request final hand testing.
