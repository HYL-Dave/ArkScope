# Lifecycle Web Investigation: Four Auth Channels

**Current status (September 7):** Instrument-bound event/date validation and larger
Claude OAuth defaults pass 6,931 backend tests / 12 skips, 2,266 whole-focus,
3,085 integration and 25 named reverse mutants. A fresh Sonnet 5 run completes
search/read/analysis/journal/frontend-parser readback, but is not action-ready.
The renewed allowance uses four SDK calls and nine of twenty-four source HTTP
attempts including public-original diagnostics; every SDK call has exact Sonnet
and literal subscription witnesses. The source preview omitted decisive text
available in its public original. Extra analysis still exposes output/grounding
gaps. A bounded-round workflow needs a journal schema decision; it is proposed,
not implemented. The other three channel budgets are unchanged and no other
channel ran live. No production installation/restart/merge/push. See
`docs/superpowers/evidence/2026-09-07-lifecycle-web-instrument-scoping/RESULTS.md`.

**Historical status:** Task 8's four-channel implementation passed offline verification.
The first September 7 Claude OAuth canary failed on mixed selected-model/Haiku
usage. The separately renewed Sonnet-only attempt now verifies exact main/helper
usage, literal subscription auth and matching sessions for search. It fails
after four public-source reads and submits no analysis. A reproduced local HTTP
response-ownership bug is corrected offline; complete live investigation is
still unverified. Production installation is not authorized.
Historical admission is in `docs/superpowers/evidence/2026-09-07-lifecycle-web-runtime/`;
the read-only inventory and failed live attempt are in
`docs/superpowers/evidence/2026-09-07-lifecycle-web-oauth-canary/`.
The renewed attempt and source correction are separately retained in
`docs/superpowers/evidence/2026-09-07-lifecycle-web-sonnet-canary/`.

## Scope

The September 6 user ruling requires OpenAI API key, ChatGPT OAuth, Anthropic
API key and Claude Code OAuth in the same delivery. Do not ship an API-key-only
version, route a subscription failure to an API key, or require a subscription
upgrade merely to complete offline implementation. Existing model/account
admission remains independent from whether an adapter is implemented.

Use a purpose-specific Web investigation contract. Ordinary Research, Spark
Content Translation and their tool restrictions are not changed. Credentials
come from the selected profile credential/token store only; none are included
in the public question or source text. No ambient browser, filesystem tool,
shell, general subagent, provider fallback or automatic investigation is allowed.

## Observed Interfaces

Local preflight: OpenAI 3.8.0, Anthropic 1.3.0, Claude Agent SDK 0.2.151 and
bundled Claude CLI 2.1.258; openai-codex 0.147.0. Existing runtime admission
still owns allowed binaries. Latest online documentation is not proof that an
installed binary supports every documented feature.

| Channel | Purpose-specific transport | Enforceable versus observed work | Stop evidence |
| --- | --- | --- | --- |
| OpenAI API key | Responses with hosted `web_search`; selected key only, SDK retries zero | Wire Responses `max_tool_calls` for the search response. This is not general Research's `max_turns`. Count submitted model requests separately from search actions. | Background cancellation needs a known response ID and terminal readback. Lost IDs or failed cancellation remain unknown, not cancelled. Background retention must be disclosed before live use. |
| ChatGPT OAuth | Reviewed bundled Codex app-server in a fresh private home/cwd; no PATH executable | Enable Web only for this purpose. The examined thread/turn schema has no native `max_tool_calls`; do not invent a hard search-request budget. App-submitted turns, observed Web actions and deadline are separate quantities. Reject shell, file, MCP, subagent, approval and model reroute activity. | `turn/interrupt` acknowledgement alone is not terminal. Require the matching interrupted `turn/completed`; transport loss/process termination alone leaves remote stop unknown. |
| Anthropic API key | Messages with basic `web_search_20250305`; selected key only, SDK retries zero | `max_uses` bounds search. Do not use the general Research `20260209` default, which may provision dynamic code execution. `pause_turn` is incomplete, not an implicit extra request. | Closing a stream is not an observed remote cancellation. Preserve incomplete/unknown when a terminal result is absent. No automatic continuation. |
| Claude Code OAuth | Reviewed bundled Claude SDK client, fresh cwd/config and exact subscription auth witness | Expose only WebSearch, with per-call PreToolUse admission and budget reservation. The host-owned common source reader runs after search, not as another CLI/MCP tool. `allowed_tools` alone is not an exclusive tool list. Keep exact built-in availability, deny rules and strict MCP/settings isolation. | Send `interrupt`, then drain through the matching result. A missing terminal result is unknown. Existing one-shot `query()` cleanup is not sufficient evidence. |

The first-phase search locates source candidates. Its text/URLs/snippets alone
cannot support an action. A common HTTPS reader captures inspectable sources
with document/text digests. The pipeline now retains complete readable source
text and selects traceable passages for analysis with the same public identity.
Structured JSON/XML and prose with no recognized relevance remain complete;
selection is not a promise that every large input fits the model. Source retrieval has its own request,
redirect, byte and deadline envelope. It cannot inherit provider authorization,
cookies, proxies or a local browser profile. Successful retrieval is not proof
that a source's factual assertion is true.

Native hidden tool internals are not called "measured HTTP requests". Never
advertise a hard limit merely because a prompt requests one. Before a live
canary, derive its envelope from completed adapter tests and explicitly report
any dimension the selected hosted service does not let ArkScope bound. A stop
request prevents all subsequent local dispatch even when remote status is unknown.

The September 7 live attempt exposes an additional Claude CLI distinction:
WebSearch may use a small/fast helper even when every main assistant response
uses the explicitly selected model. The examined 2.1.258 binary has that
independent selection path. This adapter now sets both
`ANTHROPIC_DEFAULT_HAIKU_MODEL` and the higher-precedence legacy
`ANTHROPIC_SMALL_FAST_MODEL` to the selected model. Exact model-usage validation
remains enforced; this is not permission to accept Haiku or to change accounts.
It may use more quota/time than the default helper. The renewed Sonnet-only
search verifies the override live; analysis and complete investigation still
need a successful gate. The CLI's internal hosted search limit is not the count of admitted
WebSearch operations. See the [official background-model configuration](https://code.claude.com/docs/en/model-config#environment-variables).

Owned remote terminal status and result acceptance are independent facts. A
matching-session completed ResultMessage is persisted before rejecting invalid
model usage, turns, tool activity or output. Such a run is failed, not an orphan
with unknown remote outcome. Missing or foreign terminal evidence still stays
unknown and cannot authorize a subsequent analysis request.

The renewed attempt exposed an independent host-reader defect: the custom
`HTTPConnection.close()` forced shutdown during the standard `getresponse()`
ownership transfer for `Connection: close`, before reading its body. The source
correction inherits normal close behavior, retains an independent abort handle
and explicitly closes the response in final cleanup. Real HTTP framing and TLS
over local socket pairs must own both full-body preservation and prompt abort;
fake response objects alone missed this defect. Real short bodies remain errors.
No live headers were retained, so the offline reproduction is not a claim that
every failed URL becomes available. BP's non-200 rejection remains separate.

Claude SDK top-level usage must not be presented as whole-session consumption
when its per-model aggregate differs. Multi-turn model-usage calibration remains
open; the live packet records both counter surfaces without inventing totals.
New failed runs retain measured source-request counts and sanitized read receipts.
Old rows without receipts still report unknown, not zero. A failure receipt is
not a finding and cannot support adoption; population retention explicitly owns
that distinction. Model-phase/token accounting is not made complete by this
source-only diagnostic correction.

## Source Compatibility And Size Recalibration

### Goal-Directed Source Priority And Larger PC Budget

The later September 7 clarification removes the SEC-first search wording.
Massive/EODHD remain primary; Web/news search is an explicit supplement when
their structured observations cannot settle the tracking question. Both search
and analysis use the same meaning on all four auth paths: actual listing status
and same-security continuation, not filing volume. SEC is optional evidence;
its proposals/conditions/warnings are useful prospectively, and an explicit
completion notice remains useful retrospectively. Filing, announcement and
effective dates must not be conflated. An automatic SEC index/history resolver
is not a prerequisite for using other complete public reports.

The code revision now permits 32 MiB encoded / 128 MiB decoded per source and a
4 GiB measured RSS threshold, not an invented LLM token limit or guaranteed
whole-App RSS cap. New preflights also bind a 180-second shared reader deadline:
the old 45-second phase included local persistence and repeatedly retained only
three of four sources at the larger size. A succeeded analysis with missing
sources is not full-capacity admission. Model/request/redirect budgets are
unchanged; old approvals retain their stored limits. The first two-worker,
four-sources-each 128 MiB experiment
was stopped at 4,314,103,808 sampled RSS bytes. No conclusion was generated.
This falsified the assumption that changing constants alone was enough.
Source-sized escaped JSON copies in hashing/storage were removed with
byte-identical legacy fingerprints and mixed old/new journal readback owners.
Full-range context reuses retained text and model JSON avoids ASCII expansion
without changing parsed input. A densely relevant 512 MiB input per worker
remains whole; it is not claimed to fit a real model's native context.

The real controller/shared-journal benchmark also exposed write/read locks held
across large source validation. Finalization now validates outside owned
transactions and rechecks ownership, cancellation, model terminals and the
immutable source index at commit. Progress polling skips uncompleted source
bodies that the status DTO never used. Complete-result reads retain integrity
checks outside their owned transaction; explicitly caller-owned adoption
transactions retain their existing atomicity. No database mode or DDL change is
used to hide the failures. A later instrumented filesystem run independently
measured a 29.239-second commit after a 1.872-second source INSERT. That falsified
the separate five-second busy-wait assumption. Only Web journal-owned connections
now wait up to 45 seconds; the lease remains 60 seconds and unrelated stores keep
their policy. Real SQLite contention controls cover commit, cancellation and a
persistently held lock. This scoped calibration does not excuse retaining locks
across expensive Python validation, and is not an unlimited I/O guarantee.

Final two-worker runs include real heartbeat and two simulated UI progress
readers that must actually observe both terminal responses, not only background
completion. Both sparse and densely relevant four-source workloads complete
without poll errors; the largest measured child RSS is 3,021,426,688 bytes.
The separate 29-second held-commit control also preserves all eight sources and
both receipts, with an observed 32.783-second SQL wait and no SQL/poll errors.
Exact values, source manifests, failed experiments and the
complete regression/mutation ledger are recorded in the packet. HTTPS/model
replies are synthetic: this does not certify the whole App, SDK subprocesses,
other platforms or live model context acceptance. The earlier non-poll passing
suite is retained as historical, not substituted for the progress-read repair.
Terminal readbacks took 15.845 seconds and later 77.027 seconds; even an initial
60-second receipt budget was inadequate at maximum capacity. The six
source-validating local UI detail/result/review/receipt routes use a 180-second
wait instead of the general 15-second default. HTTP preflight/dispatch and model
budgets are unchanged; the shared reader budget is independently calibrated above.
Owners cover an 80-second success, a stalled 180-second read, no retry and the
unchanged general default. The maximum-source pressure
test does not execute an attended write concurrently with another model job;
that atomic-write concurrency measurement remains a production-cutover gate.
Final regression is 6,702 passed / 12 skipped in the full backend, 2,037 focused,
2,856 integration and 1,562 frontend tests. All 29 backend and six frontend
mutants fail named owners. The new evidence packet is
`2026-09-07-lifecycle-source-priority-capacity`;
the earlier source-context packet below must not be modified or relabeled.

The blanket `unread_source_count > 0` action blocker was a separate evidence
admission policy, not a memory safeguard. The September 7 user decision now
permits an otherwise supported LLM finding to proceed to attended confirmation
with explicitly disclosed unread references. The source-priority/capacity packet
above predates this decision and remains unchanged. This is an intentional
change to the old unread-candidate contract, not a reinterpretation of that
packet's test results.
The existing locator/identity-only JSON rule is also unchanged by this
capacity slice; it is not a restriction on Massive/EODHD structured authority.

### Attended Confirmation With Source Gaps

Human confirmation is the final safeguard, not a substitute for investigation.
The LLM returns a concise conclusion, decisive quoted evidence and any
action-changing uncertainty. A failed supplementary read alone is not an
unresolved action field. The host discloses each unread reference and its typed
read failure, rather than relying on the model to mention it. No claim is made
that unread content cannot contain contrary evidence.

- Complete model terminals, at least one complete supporting source, exact
  citations, issuer/security identity, supported event and effective date are
  still required. Material contradictions, active/OTC vetoes, essential missing
  conditions, stale findings and changed target effects still prevent adoption.
- Persist admitted public URLs alongside the existing source-failure map in
  result JSON. Present malformed metadata is rejected; legacy missing URL
  metadata becomes an explicit unknown URL, not zero failures or an invented
  address. No source-gap record becomes a citation.
- The closed `{url, reason}` list reaches the saved result, UI/Research readback,
  action preview and final confirmation. The internal packet digest binds it
  together with the result and exact profile effects. The central writer also
  compares the accepted disclosure with the validated journal. UI and Research
  do not receive worker, credential or remote/source binding identifiers.
- Preparing a review remains read-only. Only the explicit action-bound human
  confirmation can stage acceptance and use the existing atomic writer.
  A confirmation of nonempty source gaps requires literal
  `acknowledge_source_gaps=true`, sent by the existing final confirmation button
  after displaying the validated packet. There is no extra user checkbox. An
  older client that silently ignores the new DTO field cannot apply that action;
  missing/false acknowledgment returns a refreshable conflict. This does not
  waive any material blocker or substitute for the packet digest.
  Replays are idempotent; there is no automatic retry, fallback or application.
- No DDL, provider budget, source capacity, model-context policy or unrelated
  deterministic authority changes. Production reads/writes, live canaries,
  installation, App restart, merge and push require their separate approvals.

RED-first owners are `test_unread_supplement_does_not_block_an_otherwise_supported_attended_finding`,
`test_incomplete_web_finding_is_readable_but_has_no_action`,
`test_gap_disclosure_follows_finding_review_and_explicit_human_receipt`,
`test_confirmation_rejects_a_different_gap_disclosure_without_any_write`,
`test_central_writer_rechecks_gap_disclosure_even_if_an_acceptance_is_resigned`,
and `test_research_and_current_detail_share_readonly_web_findings_for_every_auth`.
Frontend owners cover both languages, last-confirmation disclosure, legacy URL
absence, closed runtime parsing and the no-gap/blocked positive controls.
Independent mutations must fail their named owners across the full affected
focus / complete frontend, not just the new test file. Full backend, UI,
typecheck/build/i18n and desktop/mobile browser checks precede the new seal.
The completed offline amendment is recorded in
`docs/superpowers/evidence/2026-09-07-lifecycle-attended-source-gaps/`:
6,772 passed / 12 skipped in the full backend, 2,107 focused, 2,926 integration,
1,578 frontend tests, 14 backend / ten frontend named-owned mutations and
24 bilingual desktop/mobile browser cases (42 screenshots). A unique-node audit
caught unpacked array-valued Vitest fixtures; the cases were corrected and both
campaigns fully repeated. Earlier incomplete/test-construction results remain
historical, not final admission. The ledger explicitly maps the old unread-only
contract and expanded with-gap/no-gap controls rather than hiding test renames.
Maximum-source attended-write concurrency was not covered by that policy
amendment; the next section records its separate measurement and correction.
Model-usage calibration and a fresh authorized live investigation remain gates.

### Attended Write Concurrency

The maximum-source test finds actual cross-job starvation: a human confirmation
holds two consecutive profile write transactions for 43.071 and 30.865 seconds,
while another controller's heartbeat and first page INSERT hit the unchanged
45-second journal busy limit. The human action applies, but the unrelated worker
exits with zero sources and a raw `reading_sources` journal state. The small
control passes. This is not an excessive-RAM finding or a live provider result.

The correction validates complete journal sources/finding before taking the
write lock, then explicitly carries one request-local verified read through
preview, approval and application. Inside every atomic write, recheck the exact
profile/run/header, model terminals, result, source index and SQLite schema
generation under the existing verified immutable triggers. Separately recheck
current observation, membership, open holdings, active/OTC vetoes, freshness,
human disclosure/digest and write authority. Separate commands validate again;
direct caller-owned transaction reads retain their original atomicity. There is
no persisted cache, new schema, changed timeout or weaker evidence requirement.

Disk-backed 1 MiB and exact 128 MiB decoded-per-source controls pass for removal
and rename with both jobs complete and all eight sources retained. Maximum
confirmations take 20.231 / 20.067 seconds, with each write transaction below
0.8 seconds and peak child RSS approximately 1.78 GiB. This does not promise
instantaneous review or certify native model context. The source-bound packet
`2026-09-07-lifecycle-attended-write-concurrency` records the full regression,
15 named-owned mutations, original RED, readback-regression correction and two
interrupted campaigns separately. The completed backend campaign uses RAM-backed
test databases after ordinary regression storage waits; the maximum-source
measurements remain disk-backed. UI/DTO files are unchanged, and the previous
browser evidence is referenced by exact hashes, not claimed as newly rerun.
Final admission is 6,798 backend passes / 12 skips / three existing warnings,
2,133 baseline/restored focused, 2,952 integration and 1,578 frontend tests.
The 26 added backend nodes remove no prior nodes. No production read/write,
provider call, migration, App restart, commit, merge or push occurs. Usage
calibration, fresh authorized live verification and production cutover remain.

### Previous Measured Baseline

The first September 7 clarification authorized offline implementation, not another
live canary. Its `LifecycleWebPreflight._material` permitted 16 MiB of encoded HTTP
body per source and 32 MiB after decompression, replacing the 2 MiB default.
Identity-encoded responses remain subject to both limits. These are revisable
PC resource protections, not SEC maxima, character limits or model capabilities.
Both values are exposed in preflight and bound into its confirmation digest.
Legacy option records without a decoded limit retain their original bound.

Keep four independent quantities explicit: HTTP body bytes before content
decompression, decoded bytes, retained readable text, and model tokens. The first
count excludes HTTP headers, chunk framing, TCP and TLS overhead. A synthetic
two-worker test retains four nearly 32 MiB, four-byte-Unicode HTML sources per
worker, including real decompression, journal completion, validated readback and
UI/Research projection. Its final process peaks at 1,530,957,824 bytes (about 1.43 GiB);
each temporary journal occupies about 384 MiB. This is a bounded workload
measurement, not an all-PC/platform or whole-App memory certification. No real
source, credential, provider or production database is read by the benchmark.

HTTP framing and error classification are corrected alongside the wider limit.
Real stdlib response owners cover fixed-length, chunked and close-delimited bodies,
identical repeated Content-Length, ordinary chunked whitespace and gzip members. A
conflicting Transfer-Encoding/Content-Length pair is a framing issue, not proof
that source prose is missing. A compressed response that the reader cannot
decode is a capability limitation, not an invalid factual source. Real short
fixed-length responses must remain distinguishable from size-budget exhaustion.
Bounded streaming gzip checks both encoded and decoded sizes and completion/CRC.
Only sanitized status/framing/encoding/length observations survive failure; raw
headers, cookies, URLs and credentials do not enter this diagnostic DTO. The UI
uses a collapsed detail area, and Research receives the same closed projection.

Supported JSON is strictly parsed without replacing its original representations.
XML uses a DTD/entity-disabled streaming parser and the standard canonical writer,
preserving namespaces, security-class fields, record boundaries and mixed content.
This replaces an initial flattening formatter that repeated long parent names;
the new regression reproduces 20,468 input bytes expanding to 2,120,086 bytes in
that formatter and owns preservation without arbitrary clipping. `defusedxml`
is an explicit pure-Python dependency, not an external program.

The existing SEC collector already uses Submissions metadata. A new automatic
Web resolver for directory indexes, primary documents, attachments and historical
Submissions files is **not implemented in this slice**; it would change request
planning and needs separate owners/budget review. Recognizing an index or JSON
record is not a replacement for actually retrieving its notice. JSON metadata
citations cannot support listing-action facts. This Web reader's new JSON support
is locator/identity-only; it does not restrict the separate structured
Massive/EODHD decision path. SEC primary-document identity and
class-specific Form 25 remain different from issuer-wide listing authority.
This is not a return to SEC-first lifecycle authority: issuer, security class,
event timing and active/OTC contradictions still require the existing checks;
Massive/EODHD keep their reviewed roles. The legacy SEC collector's distinct
limits and the 16,000-character domain storage contracts are not blanket-raised.

Prose selection retains every identity/lifecycle/date/negation match with two
neighboring units, plus document boundaries; it is not first-N/top-K clipping.
No recognized match falls back to full text, as do complete JSON/XML records.
Saved byte-range manifests bind the actual model input to full retained text;
citations must occur in the supplied ranges as well as match the retained source.
Unknown, dense or very large structured inputs can still exceed native model
context. All four auth adapters retain explicit context errors, no retry/fallback
and no invented local token limit. Selection is heuristic, not proof that every
semantic contradiction was found. Human confirmation and the existing factual
guards remain required. UI text distinguishes full retention from selected input.

Complete readable text and source/entity digests are retained, not a byte-for-byte
HTML/compressed archive. Existing citations retain their domain limits. Successful
larger reads, true truncation, compressed expansion, memory/deadline bounds and
source-to-analysis binding have positive and rejecting controls. A relevant final
paragraph or XML field must not disappear unnoticed. Overflow stays visible as an incomplete read/budget outcome,
not a false conclusion about listing status. Any new persisted setting requires
an explicit profile-DB design, not an environment-variable fallback.

The 14-backend/3-frontend whole-suite mutation campaign passes named owners.
Restored focus is 1,998 passed; integration is 2,817 passed; complete backend is
6,663 passed / 12 skipped with the same three warnings; complete frontend is
1,552 passed. Twelve bilingual browser cases and 24 screenshots pass. The node
ledger records 58 net backend additions, five frontend additions and one gzip
error-parameter rename, not a disappeared rejection test. Results are in
`docs/superpowers/evidence/2026-09-07-lifecycle-source-context/`.
No new DDL or Settings field is introduced here. Failure receipts extend the
existing journal result contract; old installed binaries must not be assumed
compatible with new failed-result rows merely because the DDL is unchanged.

This amendment precedes further live validation. It does not extend
the consumed canary's request/byte budget, authorize another source/model call,
alter production data, or rewrite the sealed historical evidence packets.

References: [HTTP framing](https://www.rfc-editor.org/rfc/rfc9112.html#section-6.3),
[SEC JSON APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces),
[SEC directory indexes](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).

Primary references actually read during preflight:

- [Responses create](https://developers.openai.com/api/reference/python/resources/responses/methods/create)
  specifies the built-in-tool limit; [background mode](https://developers.openai.com/api/docs/guides/background)
  describes cancellation/retention, not a guarantee from closing a stream.
- [Codex app-server](https://learn.chatgpt.com/docs/app-server) documents
  Web activity items and interrupt/terminal notifications. The
  [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
  distinguishes provider retries from tool availability.
- [Claude Web search](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)
  documents `max_uses`, result errors and limited citation text;
  [server tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)
  distinguishes pause/continuation and dynamic code execution.
- [Claude Python SDK](https://code.claude.com/docs/en/agent-sdk/python) and
  [hooks](https://code.claude.com/docs/en/agent-sdk/hooks) document exclusive tool
  configuration, PreToolUse and interrupt/drain behavior.

## Persistence Checkpoint

The current investigation-run adapter CHECK accepts only `manual`; the earlier
`manual|tavily` definition is historical V1. Do not relabel LLM execution as
manual. Current automation storage already has `hosted_search` citations and
`model_assisted` authorship, but its current validator admits deterministic
rules only, and its running-row reconciler also owns recovery. Reusing those
rows requires explicit ownership/recovery changes and positive controls; adding
a JSON key alone does not establish safe reuse.

Implementation uses the independent `lifecycle_web_*` journal. It records exact
adapter/model selection, dispatch reservations, remote terminal observations,
full retrieved public pages, validated findings and human-adoption links. The
existing manual-investigation and deterministic-automation enums are unchanged.
Installation is explicit, transactional and tested on temporary stores only;
ordinary reads and profile bootstrap must not install it. Production installation
requires separate authorization. The population manifest retains Web dependency
metadata/digests, not full pages, model prose or credential identifiers.

`lifecycle_web_migration.preview_web_installation` is read-only. The explicit
installer requires a stopped App and matching approval digest, creates a private
non-overwriting SQLite backup, rechecks the digest under the write transaction,
and proves every existing table/row unchanged before commit. An installed
matching journal is idempotent; changed inputs or any failed installation roll
back. Temporary-store rehearsal is not authorization to install in a real profile.

An explicit ChatGPT Web launch may refresh its selected expired token through
the existing scoped refresh function. Preparing/reading a finding never refreshes
or dispatches. A refresh cannot switch credential, model or billing source; the
worker renews its lease during refresh and rechecks cancellation before any model
submission. Refresh failures are redacted and do not reuse the expired token.
Existing OAuth observation metadata is updated; no hidden account-usage sync is
added. A live authorization must count that possible token grant separately from
model submissions.

Unknown share class/venue may enter the search request as null. Neither the UI
nor the operator is asked to invent those facts. The final cited notice must
identify the exact security/class/venue before an action can be offered.
The current overview's listing state remains the structured-provider observation;
the separate Web finding and committed tracking receipt are not relabeled as a
successful provider check. UI and AI Research detail share the closed Web DTO.

## RED-First Slices

### W1: Common Source And Execution Contract

- [x] Own a closed public request, exact provider/auth routing and honest
  budget/stop outcomes for all four channels. Unknown auth must not choose API.
- [x] A common source reader enforces HTTPS, public DNS addresses, pinned
  connection/TLS hostname, every redirect, a single attempt and no ambient
  credentials/cookies/proxies. Reject oversized/unsupported content explicitly.
- [x] Positive controls retrieve a complete public page and preserve Unicode,
  dates, source URL and exact cited text. Reject guessed/snippet-only citations,
  cross-document spans, hidden script text and rebinding/private redirects.
- [x] Test observed versus enforced search bounds, unknown cancellation,
  exact model/credential binding and no new dispatch after a stop request.
- [x] Run independent mutations against the complete affected focus and retain
  actual RED/GREEN output; do not reconstruct initial RED after implementation.

### W2: Four Restricted Runtime Adapters

- [x] Bind the W1 contract to each actual SDK/app-server interface, including
  selected credential loading, pre-dispatch admission, events and cleanup.
- [x] Cover successful API and OAuth execution with synthetic protocol fixtures,
  malformed/missing auth witnesses, budget exhaustion, provider tool errors,
  interrupted/unknown cancellation, model changes and zero paid fallback.
- [x] Independently preserve ordinary Research and Spark's closed surfaces.
  A mocked constructor test alone does not admit the bundled binary's behavior.

### W3: Durable Finding, Human Confirmation And UI

- [x] Persist run identity, true adapter/model/auth, source/document digests,
  usage and incomplete/cancellation states without private token material.
- [x] Validate exact security, event/effective dates, source passages,
  contradictions and syndication. A confident sentence is not an action.
- [x] Feed validated findings to Task 6's exact-action human packet independently
  from unavailable listing endpoints, with stale/replay/position/source guards.
- [x] Wire explicit per-case launch/cancel/readback to the existing compact UI.
  Show chosen model/auth and truthful work/stop status at that command, not in
  an unrelated global notification area. Reopening never repeats spending.
- [x] Verify complete backend/frontend focuses, independent mutations and
  desktop/mobile browser behavior before asking for separately budgeted canaries.

W1 historical component run: 1,636 focus tests, 21 independently owned mutants,
1,636 restored tests and 2,455 integration tests passed in the source-bound
`/tmp/arkscope-lifecycle-web-w1-admission-v2` snapshot. That is not a claim about
later W2/W3 edits. Current W2/W3 admission has 1,919 restored tests in 62 affected
files, 2,738 integration tests in 110 files, and a complete backend of 6,584 passed,
12 skipped and three existing warnings. All 23 backend and 11 frontend mutants
fail their named owners. The restored complete frontend passes 1,547 tests;
its first restored run's existing scanner timeout is retained alongside the
successful same-source full-suite recheck, with no test-timeout or assertion
change. All 54 bilingual desktop/mobile browser scenarios pass with 156 screenshots
and source/pixel/geometry checks. Backend adds 339 nodes, frontend adds 31, and
neither removes a node relative to Task 7. SEC reads use the existing contact
identity and shared request governor with cancellation/deadline-aware waits.

The post-canary correction separately passes 1,928 restored focus tests, 2,747
integration tests and 6,593 full-backend tests (12 skips; three existing warnings).
Five new independent mutants each fail their named owners across the whole
affected focus; nine tests are added and none removed. The prior 23 backend/11
frontend mutant campaign and browser checks remain historical evidence, not a
claim that those campaigns were rerun. Only the Claude Web adapter and its test
file change in product/test code; frontend bytes are unchanged.

The subsequent HTTP response-ownership correction passes 1,940 restored focus,
2,759 integration and 6,605 complete-backend tests (12 skips and the same three
edgartools warnings). Its five independent mutants each fail a named owner
across the full affected focus; twelve test nodes are added and none removed.
The initial full-suite process exceeded its 600-second verification limit and
is retained as incomplete. The successful same-source full recheck uses a
1,200-second process limit and private RAM-backed test storage, with no test
assertion or product-timeout change. Twenty-four plain/TLS wire tests and thirty
packet tests pass; frontend bytes remain unchanged. This does not establish
complete live investigation or erase either earlier canary failure.

## Live Gate Scope

The minimal all-channel functional gate follows directly from the pipeline:
one public-identity investigation on each of the four channels, each containing
one search and one analysis submission. That is at most **eight model submissions**,
not eight total HTTP requests or eight internal harness model turns. Claude's
search/query envelope separately sets six internal turns for search and two for
analysis, and checks the returned `num_turns`; Codex's native internal model-turn
count is not a hard envelope ArkScope can promise. No ArkScope retries,
substitute account/model, automatic
continuation or profile action is permitted; an incomplete result ends that
channel's attempt. It is not success-quality evidence merely because a request
completed.

The original live gate admitted at most four retrieved pages, eight source HTTP
attempts (including redirects), two redirects per page, 2 MiB per response,
45 seconds total source retrieval and 180 seconds per model phase. Its executed
receipts retain those original limits. A renewed live proposal must explicitly
bind the September 7 revision: 32 MiB encoded / 128 MiB decoded per source and
180 seconds of shared source reading, with the same page/request/redirect and
model-phase limits. This revision does not grant additional live calls. Search-phase
limits differ: OpenAI API `max_tool_calls=4`, Anthropic API `max_uses=4`, Claude
OAuth four admitted WebSearch uses. Codex OAuth has an observed action stop
threshold of four, **not a provider-enforced hard search bound**. Model-list,
config/thread setup, response polling, cancellation readback and a possible
same-account ChatGPT token refresh are separate control-plane operations. The
selected credentials and their eligibility must be confirmed before proposing
an actual live command; do not manufacture a fixed transport-request count.

Live evidence must record actual returned model/auth, submitted phases, observed
search work, captured source/quote identity, API usage when reported and true
terminal status. It must exclude token/key material. Missing terminal evidence
remains unknown, with no resubmission. Existing Fable 5.1/Claude OAuth policy is
not cleared by this gate; eligible existing models avoid a subscription upgrade.

## Remaining Authority

The scope ruling alone authorized no live execution. The later September 7
authorization covered the non-secret production inventory and one Claude OAuth
canary, at most search plus analysis, stopping on failure. It consumed one
submission, observed literal `apiKeySource=none`, and stopped before analysis or
source retrieval on mixed model usage. No other channel was invoked. The saved
failed/unknown result is not retroactively rewritten by the correction.

The inventory finds 39 cases (36 SEC plus three provider cases), zero unmatched
observation/case identities and no installed Web journal. No production data,
route or credential configuration was changed. Another canary on corrected code
needs a new source-bound plan and approval; the other three channels, journal
installation, existing-population cutover, merge/restart and push retain their
separate gates. Historical sealed packets remain unchanged. Final hand testing
is not ready merely because offline support or subscription login succeeded.
