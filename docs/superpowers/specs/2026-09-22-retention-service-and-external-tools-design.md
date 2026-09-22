# Retention, Persistent Service And External Research Tools

Status: proposed design for user review, not implemented behavior. The user
reconfirmed all three capabilities on September 22. They are independent active
workstreams, not conditional on completion of the company/SA workflow.
The separately authorized obsolete-backup cleanup is already executed; its
[receipt](../evidence/2026-09-22-retention-delivery-reset/README.md) does not
authorize a general production-news purge or service installation.

## Product And Delivery Boundary

ArkScope remains a research workbench **with** unattended data collection and
external-agent access. It is not being reduced to a collection pipeline. New
research-notebook and token-monitoring products are out; existing research
threads, card translation, account-usage display and useful tools stay.

Use three independently verifiable delivery lanes. Retention and service
lifetime can proceed independently. The external adapter can be developed
against the agreed service contract while the service is implemented, but live
external admission requires that contract and its authorization tests to pass.
SA browser acceptance blocks only claims about that browser integration and
replacement-dependent retirements, not these three lanes.

## Verified Starting Point

- Frozen product/test revision `e0bce862` has 12,306 backend passes / 12 existing
  skips. HEAD `80c63b95` adds documentation only. This is historical acceptance,
  not validation of the new design. Twelve commits over master retain individual
  history; dependency-aware rollback is not the same as arbitrary cherry-picking.
- Real signed-in SA page observations and retained-source replays exist.
  Installed Chrome/Firefox extension-to-host and live operator research
  acceptance remain open. Neither fixture rejection nor a transport replay
  certifies the installed end-to-end flow.
- The source comparator excludes old ratios. The legacy D/E bug remains in its
  own consumers: the numerator uses total liabilities, not interest-bearing
  debt. Period/growth and earnings-release/window repairs also remain.
- Electron owns the API process and stops it on window close. API lifespan owns
  schedulers. Existing per-source locks do not elect one service per profile.
- The SDK-local MCP bridge owns a DAL inside ArkScope's agent. There is no
  external, independently authorized stdio service. The current API token is
  optionally enforced and has no external read-only capability distinction.
- Ordinary-news references, legacy projections, body retries and FTS are shared
  state. No complete ordinary-news archive/restore/purge owner or reference
  closure was found. A date predicate alone cannot authorize deletion.

Owners: [Desktop](../../../apps/arkscope-desktop/main.js),
[API lifespan/authentication](../../../src/api/app.py),
[internal bridge](../../../src/auth_drivers/claude_code_sdk_driver.py),
[news schema](../../../src/news_normalized/schema.py),
[projection](../../../src/news_normalized/legacy_projection.py),
[investigation readers](../../../src/lifecycle_investigation/news.py),
[SA store](../../../src/sa_capture_store.py).

## A. One News Archive, Bounded Active Storage

### Recommendation And Alternatives

Use archive-first tiering: retain one deduplicated local archive of old content,
remove eligible old payloads and full-text search material from active storage,
and retain small source/identity/title/date/URL metadata and archive locators.
This preserves deduplication, old links and investigation identities without
keeping a duplicate full market database each time maintenance runs.

Deleting complete article rows immediately would require rewriting legacy
migration/projection relationships and proving every historic reference. It is
not the first release. Limiting FTS alone is simpler but leaves all active body
payloads and does not meet the requested archive-then-remove behavior.

### Scope And Eligibility

- Default candidate window: approximately 90 days, configurable by the operator.
  Freeze an explicit UTC cutoff per preview. Publication time determines age;
  fetch/retry time must not reset it. Parse timezone-aware values, including
  legacy `+0000`, rather than relying on SQLite `julianday()` alone. Unknown or
  naive dates are retained and counted, not guessed or dropped.
- Cover ordinary market news and SA market news through separate store-owned
  adapters. Exclude Alpha Picks analysis, article comments, recommendation
  lineages, holdings, prices, SEC citations and research conversations.
- Keep manually retained/cited/investigation evidence and unresolved or active
  retry/repair dependencies in active storage. Introduce an explicit retention
  hold/reference owner where missing. Unknown protection cannot mean unreferenced.
  Historical references without a complete index remain readable through the
  archive locator; archive-only reads must be proven before clearing payloads.
- Inventory old `data/news` ingest files separately. A file's age or the presence
  of similar DB rows is not proof that its unique contents were archived.
- Job history needs a separate rule: terminal diagnostics can be aged only after
  durable scheduler frontiers and outstanding repair references are preserved.
  Do not apply an unconditional 90-day `DELETE` to `job_runs`.

### Archive And Read Contract

One logical private news archive is the authority for moved content. Store
provider identity, original IDs, content version/hash, bodies/variants, source
metadata and the relationships needed for exact reopening. A unique content
receipt prevents repeated maintenance from making duplicate archives. Historical
content is not overwritten by a later provider revision. A manifest records each
completed batch; it is not another copy of the payload.

The normal result reports active versus archived storage without pretending an
archived body is unavailable from the provider. Exact article/citation reads may
read the archive locally; they do not download, spend, or silently restore the
entire active dataset. Ordinary full-text search covers its declared active
window. Historical metadata discovery remains possible; do not promise historical
full-text search without implementing a separate archive index.

Never overload the existing `archived_at` field without updating its consumers:
current investigation readers filter it out. Do not turn moved bodies into
`pending`, `failed`, or `expired` acquisition work. Retain identity/frontier and
archival state so an overlapping collection does not repeatedly rehydrate old
content. A genuinely changed source version may be admitted under an explicit
policy while preserving the previous archived version.

### Mutation And Recovery Contract

Preview counts, protections, storage estimate and archive location first. Export
and verify hashes/counts, then prove restore/reopen on an isolated store before
clearing any active payload. Recheck versions/protections under the existing
store writer discipline immediately before bounded transactional removal.
Coordinate publication of new evidence and pruning; do not let a concurrent
reference become unprotected between preview and commit.

Canonical-row changes own FTS updates. Never delete FTS shadow tables directly.
Archive failure, corruption, unavailable protection stores or changed candidates
must leave the corresponding active data intact. Journal progress separately for
each DB; no pretend cross-database atomicity. Re-running after any crash must not
duplicate content or lose the only copy. Restores preserve original provenance
and timestamps and reject identity/version conflicts rather than overwrite newer
observations.

Automatic retention is opt-in after a successful attended run. Ordinary reads
never trigger deletion. SQLite freed pages are reusable space, not automatically
returned filesystem bytes. Any physical compaction is a separate, stopped-writer
operation with sufficient temporary disk space; never promise the preview's
payload estimate as bytes already reclaimed.

### Acceptance

Archive/restore and old-link reopening; corrupted/missing archives; repeated and
interrupted runs; concurrent new citations; multi-ticker and cross-provider
projection collisions; unknown dates; protected and pending evidence; unchanged
Alpha Picks/comments; ingest frontiers and retries; all affected FTS owners;
preserved publication/fetch times. Validate both ordinary-news stores, not just
a synthetic single-table fixture.

## B. Persistent Local Service And Failure Delivery

Reuse the existing API/DAL/scheduler composition under one long-lived local
service per profile. Do not implement unattended operation by merely hiding an
Electron window, and do not move collectors into each MCP client.

- A profile-scoped OS-held owner lock is acquired before schema/recovery/startup
  reconciliation or scheduler construction. Single worker, no production reload.
  Simultaneous Desktop/native-host/external client starts find the same owner.
- The service owns private atomic endpoint/identity discovery and readiness;
  discovery alone is not proof a process is healthy. Authenticate the expected
  profile/instance, reject stale endpoints and rotate credentials on replacement.
  Never attach to an arbitrary process merely because its port answers.
- Electron attaches and may ask the service manager to start the owner. Closing
  a window detaches; only an explicit service-stop operation stops collection.
  Reopening does not restart jobs or reconcile a still-running owner's work.
- First deployment targets Linux user-session supervision for start/status/stop
  and crash restart. Login autostart is explicit. Survival across logout/suspend
  is not implied; lingering/system-wide installation requires its own decision.
  Windows/macOS adapters remain separate work, not silently certified.
- Protect provider credentials and spending policy in the service. Native-host
  integration uses the same discovered profile owner; multiple browser clients
  must not start duplicate schedules. Browser-dependent SA tasks honestly require
  a running, logged-in browser even when the service itself remains alive.
- Persist failure reasons and delivery outcomes separately. Support an opt-in
  notification transport with deduplication/backoff and recovery notification;
  a failed notification is not a delivered alert or a successful collection.
  Local retained failures remain inspectable when transport delivery fails.
  Do not resurrect the retired bot/alert implementation.

Acceptance: real service process survives Desktop exit and performs a scheduled
fixture job; Desktop reattaches to that instance; concurrent starts elect one
owner; crash recovery runs once; stale discovery and unauthorized stop fail;
notification failure/retry is observable. An in-process scheduler unit test alone
does not certify unattended lifetime. Production activation is a separate
attended transition, not a side effect of accepting this design.

## C. External Read And Analysis MCP

Use a thin stdio MCP adapter forwarding authenticated requests to the service.
It owns protocol framing and discovery only: no DAL, provider credentials,
scheduler, direct SQLite handles, or second copy of tool implementations.
Use an existing maintained MCP implementation when implementation is admitted;
verify actual consumer compatibility, not just the internal SDK's server shape.

The service owns an external operation policy distinct from internal UI/agent
admission. Do not repurpose the UI's all-operation token for external clients.
First release permits characterized stored reads and pure calculations only.
Reject writes, arbitrary SQL/Python, model delegation, forced refresh, acquisition,
configuration changes and spending before dispatch, even if a caller crafts
arguments omitted from its schema. Authorization precedes execution and audit.

An internal `stored` option or a tool's name is not sufficient: characterize
hidden cache writes/schema initialization and all parameter variants. Missing
data returns a typed gap, not paid fallback. A future explicitly authorized
live-read/update capability is a separate policy, not implied by this release.

Reuse the registry's descriptions/parameter/result contracts, with service-owned
external exposure metadata and regression checks. Provide capability discovery
by category/search and bounded schemas/results rather than a fixed arbitrary
tool-count cap. Do not assume all external apps support identical lazy-loading.
Verify discovery and invocation in both Codex and Claude Desktop; clients can
have different integration adapters while sharing the same operation policy.

Record caller identity, tool/scope, admitted capabilities, result state and
duration without leaking credentials or copying entire private payloads into
logs. Audit detail cannot replace admission, and a service read must not be
misrepresented as a live broker observation.

Acceptance: two independent clients share one owner; no client-side DAL;
missing/wrong/expired credentials rejected; arbitrary privileged requests and
refresh variants rejected; unchanged data under missing/failed/read cases;
network/provider/model calls prohibited in stored-only tests; full bounded
article/comment continuation and source citations survive the external transport.

## Delivery Checkpoints And Remaining Work

| Workstream | State now | Next independently testable result |
| --- | --- | --- |
| Obsolete rollback snapshots | Completed: 12 snapshots and 16 sidecars removed, 13.32 GB; newer recovery material retained | No recurring age-only backup deletion |
| News retention | Inventory complete; archive/restore/protection/tiering absent | Attended preview, verified single archive and safe removal/reopen across both news stores |
| Unattended service / alerts | API-bound schedulers exist; UI owns lifetime; new delivery absent | One supervised profile owner, UI detach/reattach, persisted and delivered failures |
| External MCP | Internal bridges only | Thin external adapter plus server-enforced stored-read/calculation authority |
| SA/company workflow | Structured capture/read/comparison and four-channel retained readers implemented | Installed Chrome and Firefox acceptance, real research use and explicit comment-backlog processing |
| Analytical corrections | Legacy defects remain; comparator excludes old ratios | Consistent debt/period calculations including warm caches; actual earnings-release dates and complete trading windows |
| Broader source routing / freshness | Financial selection and category catalog exist | Dataset-specific source controls and evidence-based event refresh, without requiring a paid Finnhub plan |
| Earnings observation automation | Capability retained; not implemented | Schedule accurate event reactions after the repair, with deduplication and useful delivery |
| Research continuity | Atomic completion repaired | Native-session reuse remains separate; do not revive research notebooks |
| SEC/legacy retirement | Ticker entry fixed; redundant surfaces/algorithms remain | Retire only demonstrated replacements; preserve identity uses and retained citations |
| Runtime / platform / sandbox | Prebuilt-runtime evaluation exists; activation and platform/sandbox work pending | Separate compatibility, TLS, activation and platform-specific acceptance |

Retention and service-lifetime work do not require SA credentials, a new
subscription, the archived SEC report engine, or a SQLite interpreter switch.
The external adapter depends on service admission, not on retirement of SEC.

## Integration And Verification Discipline

Keep implementation commits separable by owner and delivery lane. New unrelated
runtime work should not keep accumulating on the unaccepted SA branch; start
from the accepted base or explicitly land only the shared prerequisite needed.
No merge is authorized merely because one new slice passed.

Use focused adversarial/behavior tests during work. Run the complete backend,
frontend and build on the frozen integration candidate before merging, not after
every metadata adjustment. Never overlap full pytest runs against the same
environment. Live provider/browser gates certify only their own capabilities.
Each handoff states delivered, partial, pending, operator gates and the exact
tested revision; test totals alone are not a progress report.

This document is the proposed cross-workstream design for review. It does not
claim that archive pruning, service installation or external tools have shipped.
The [priority map](../../design/PROJECT_PRIORITY_MAP.md) owns sequencing, and
the root [acquisition/update policy](../../../DATA_ACQUISITION_AND_UPDATES.md)
owns current-versus-planned behavior.
