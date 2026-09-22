# Retention, Persistent Service And External Research Tools

Status: proposed design for user review, not implemented behavior. The user
reconfirmed all three capabilities on September 22. A subsequent clarification
prioritizes useful, efficient recent-news search over storage savings or permanent
archives. News retention is P2; service/access and correctness repairs proceed
first, independently of company/SA operator acceptance.
The separately authorized obsolete-backup cleanup is already executed; its
[receipt](../evidence/2026-09-22-retention-delivery-reset/README.md) does not
authorize a general production-news purge or service installation.

## Product And Delivery Boundary

ArkScope remains a research workbench **with** unattended data collection and
external-agent access. It is not being reduced to a collection pipeline. New
research-notebook and token-monitoring products are out; existing research
threads, card translation, account-usage display and useful tools stay.

Keep separate acceptance boundaries without treating all three as equally urgent.
Retention must not delay service lifetime or access. The adapter can be developed
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

## A. Recent News Search And Selective Retention (P2)

### Corrected Objective

The user clarified that the goal is relevant, efficient recent-news search, not
disk savings or a permanent historical corpus. This supersedes the earlier
mandatory archive-first tiering/reopening proposal. Old, unreferenced ordinary
news need not retain its body, title or archive locator forever.

Recommend selective retention: protect explicitly retained/cited/investigation
evidence, then allow eligible old ordinary news and its search entries to be
removed. A one-time export may be offered as an operational precaution, but a
permanent archive service or transparent cold-storage reader is not required.

### Search Before Storage Engineering

Existing market-news search filters publication dates while matching
`news_fts`; it does not maintain a recent-only physical index. SA market-news
search has a different contract. Audit the actual
[market-news](../../../src/tools/backends/sqlite_backend.py) and
[SA](../../../src/tools/backends/sa_capture_backend.py) readers, not only the size
of the normalized `news_articles_fts` storage.

Result relevance and latency are separate outcomes. Measure representative
queries, plans and latency, including counts/facets and ticker/source filters,
before choosing index-windowing, query changes or pruning. A date filter or
smaller DB is not a measured speedup. Approximately 90 days remains a configurable
candidate window, not a default already applied to all readers or proof that
every older article has no value. Search must disclose its coverage.

### Safe Removal When This Work Is Scheduled

- Scope ordinary market and SA market news through their store owners. Alpha
  Picks analysis/comments, recommendation lineages, prices, holdings, SEC
  citations and research conversations do not inherit this cutoff.
- Preserve manually retained/cited/investigation evidence and active retry/repair
  dependencies. Missing reference indexes are not proof of non-use. Resolve
  ambiguous protection before deleting affected rows; do not preserve all
  ordinary news forever as a substitute for that work.
- Preview eligible/protected counts against a frozen UTC cutoff. Parse aware
  dates, including legacy `+0000`; retain unknown/naive dates pending
  classification. Publication time, not repeated fetch time, determines age.
- Coordinate reference publication and owner-managed removal across legacy and
  normalized rows, projections and FTS. Never prune shadow indexes independently
  or disable foreign-key checks to bypass relationships.
- Preserve synchronization frontiers and only the operational state needed to
  prevent re-fetching deliberately removed history. This is not a permanent
  user-facing title/URL index. Do not turn removed bodies into fake retry work.
- Revalidate candidates under store writer discipline and use bounded,
  restart-safe transactions. If an export is selected, verify it first.
  Unresolved protection or failed prerequisites leave affected data intact.
  Ordinary reads never prune; any eventual automatic policy is separately enabled.
- Inventory old `data/news` ingest files separately. Job history needs its own
  policy preserving active repairs/checkpoints, not an unconditional age delete.

Physical SQLite compaction is not the objective and is not bundled into search
improvement. No current news deletion or index change is authorized by this
design clarification alone.

### Acceptance And Priority

Measure search latency and recent-result coverage before/after the chosen change.
Prove protected references reopen, expired unprotected content follows policy,
FTS/projections agree, repeated/interrupted cleanup is safe, and collection does
not recreate removed history. Cover unknown dates, concurrent citations,
multi-ticker/cross-provider relationships and active recovery.

Do not promise that every deleted article remains readable or certify search
performance from freed-byte counts. This P2 work follows service/external-access
and correctness delivery unless an observed search incident changes its priority.

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
| News search / selective retention (P2) | Market age inventory complete; no index change or news purge | Measure actual search paths, then recent-search policy and protected cleanup; no mandatory permanent archive |
| Unattended service / alerts | API-bound schedulers exist; UI owns lifetime; new delivery absent | One supervised profile owner, UI detach/reattach, persisted and delivered failures |
| External MCP | Internal bridges only | Thin external adapter plus server-enforced stored-read/calculation authority |
| SA/company workflow | Structured capture/read/comparison and four-channel retained readers implemented | Installed Chrome and Firefox acceptance, real research use and explicit comment-backlog processing |
| Analytical corrections | September 23 repair implements input/debt/period/cache guards and stored earnings release/session windows; [current evidence](../evidence/2026-09-23-research-tool-repairs/README.md) owns final regression | Real-provider coverage, remaining concept/TTM quality and scheduled event observation; no blanket all-tool certification |
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
