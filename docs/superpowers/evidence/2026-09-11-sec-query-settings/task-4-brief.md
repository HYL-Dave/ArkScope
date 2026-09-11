# Task 4: Settings SEC Structured-Data Management

Worktree: /tmp/arkscope-listing-sec-macro-convergence
Read approved plan docs/superpowers/plans/2026-09-11-sec-query-settings.md (global
constraints and Task 4). Task 3 report is not written yet: this is an independent
frontend task using the fixed API interfaces in the plan, not a claim of complete
HTTP wiring. Parent will run real-API fixture browser integration after Task 3.
For existing status/refresh shapes read src/api/routes/sec_research.py, for capacity
fields read src/sec_research/captures.py::status. No provider or live sidecar.
Implement Task 4 only, RED-first, no subagents; scope below. Use apply_patch.

Backend tasks run in disjoint Python files; do not modify those files or their
tests. Parent owns all plan/ledger/evidence scripts outside your task-4 artifact
directory. Do not commit the entire worktree/index: stage only your explicit
frontend files, and coordinate commit timing by reporting ready-to-commit first.
Public page rows: filings expose filing_id, accession, form, filed_date,
report_date, accepted_at, primary_document, primary_url. Facts expose fact_id,
namespace, concept, value (exact string), unit, start, end, filed_date, accession.
Both retain source metadata; display only present real fields, no invented names.
Envelope status/data(list)/gaps(code-bearing records)/observed_at/coverage/object
and nullable next_cursor. GET stored status is existing data{cik,snapshots} shape;
POST refresh is existing receipt shape incl completed/pending/gaps/status.

Files: apps/arkscope-web/src/api.ts (typed helpers), settings/SecResearchPanel.tsx
plus focused test, settings/DataStorageSection.tsx, settings registry/copy and
en/zh-Hant i18n/resources/*/settings.ts. Add narrow CSS in a dedicated adjacent
stylesheet or existing stylesheet; preserve current design. Relevant existing
tests may need added GET fixtures/anchor inventories, never weaker assertions.

Settings now physically lacks obsolete SEC event intake. This panel is REAL local
structured-storage administration, NOT the complete SEC Research first release.
No future-feature placeholder, tool/schedule activation, dormant retired wrapper,
network on mount or ticker guessing. Explicit CIK input, load-local command,
refresh and resume distinct actions, catalog/facts tabs, actual whole-record page
navigation, observed statuses/coverage/time, budget editing and actual charged
object/reservation/orphan totals. File/document links may show provider-supplied
catalog URL if safe, never claim a retained filing capture exists.

Use Button/IconButton with lucide and tooltip labels; text commands where needed,
icons for page arrows/refresh. Compact unframed section, no nested cards. Existing
dark utility style, no giant headings, no negative letter spacing or responsive
font scaling. Long decimal values preserved as strings, horizontal table scrolling
inside bounded container okay, page itself must not overflow on 390px/mobile.
All visible text i18n with selector pattern, Traditional Chinese and English.

Budget: existing API accepts whole bytes <=Number.MAX_SAFE_INTEGER. Allow friendly
GiB input plus exact unit conversion, no rounding away invalid fractional bytes;
never clamp at100GiB. If persisted bytes not exactly represented in chosen unit,
display exact bytes or exact decimal string, not rounded value later re-saved.
Save only budget; no refresh/acquisition side effect, preserve dirty budget during
data refresh, report actual save error and confirm server value. Quota below usage
does not disable stored reads. Configuration error cannot masquerade as default.

Races: CIK/filter change invalidates cursor history; old pending request or old
refresh response must not paint another issuer. Pass server next_cursor unchanged.
After explicit acquisition refresh, reset pages to start to show new receipt;
ordinary page navigation remains pinned. Abort on unmount or ignore stale response.
Disable duplicate refresh for same panel, clear busy correctly when selection
changes. Unknown/partial/empty must remain visibly distinct.

Refresh needs a longer request wait than the generic15s helper: source transport
allows30s per request plus one bounded429 retry, and max_sources defaults4.
Use an explicit10-minute client wait allowance for that bounded command; this is
NOT a claim of server cancellation/wall-clock bound. On client timeout/connection
loss show outcome unconfirmed and offer stored-status reread, never automatic
POST retry or false cancelled/failed-complete claim. Existing postJSON supports a
custom timeout argument; do not change every API request's global timeout.

Use run_checks.py frontend (offline_node.cjs denies real TCP/DNS; mock all routes).
Important: existing DataStorageSection tests use importOriginal API mocks, so new
GET helper must be fixture-covered rather than accidentally hitting live8420.
Baseline frontend is119files/1692pass at declared TZ=Asia/Taipei. The first parent's
baseline forced UTC and caused4 timestamp assertions, fixed only runner timezone.
Do not alter those assertions or unrelated time display code.

RED/GREEN own task-4 artifacts: initial read-only GET, exact setting save and
errors, refresh/resume, delayed CIK response rejection, cursor change and UI
unavailable/empty/partial distinctions; helpers verify actual URL/query parameter
encoding and response errors. Run full frontend/typecheck/i18n after focused green.
Write task-4-report.md with commit, exact test counts/commands/raw files, changed
files, named owners and any concerns. Parent owns Playwright screenshot harness
and whole-change verification; do not run a live App or restart anything.
