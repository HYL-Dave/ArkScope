# SEC Live Research Acceptance

Status: backend and live SEC checks passed; real logged-in SA hand test pending.

Base revision: `4d4a5e2c997576acb3f2d98141b641612e029c95`.
Final tested product: `13248718b0a91fede0219c8b6ca742d74eb12627`.
Current interpreter: Python 3.10.12, linked SQLite 3.37.2. No runtime replacement.
The user explicitly approved reuse of existing API credentials and App OAuth.

## Boundaries

- The actual Electron Desktop and sidecar run from the integration worktree in
  an isolated HOME/config/data tree. Production filesystem access is read-only,
  and schedules are disabled. Test writes never target production stores.
- Before retained-data checks, the existing SQLite backup API created private
  WAL-safe copies of profile, market and SA stores. Full `integrity_check` on all
  three copies returned `ok`. Production main-file sizes and mtimes were
  unchanged by this backup. Do not infer that every possible WAL-sidecar byte
  was unchanged.
- Backup profile counts: 2 reports, 2 memories, 23 threads, 108 messages, 33 runs,
  32,887 run events; obsolete `agent_queries` absent. Private contents, backup
  files and credentials are not committed.
- API secrets are supplied only to the isolated child environment. The existing
  valid ChatGPT access token is read from the authorized keyring record and
  supplied through a read-only in-memory mount, without a refresh token or
  production credential-selection changes.
- Live prompts contain only public Apple SEC data. The model is
  `gpt-5.6-luna`, per-run effort `medium`; normal production routes remain intact.
- A private observer records request time/host/path/status, never headers,
  query strings or response bodies. Installed provider SDKs use `httpx2`; the
  initial `httpx`-only observer did not observe their requests. Transport claims
  below use the corrected observer. A separate temporary public-only protocol
  trace isolates function-call event shape, not model prose or credentials.

## Findings Before Acceptance

1. The first OpenAI API run correctly rejected a bare primary-document filename
   passed as `document_id`. Its tool documentation was ambiguous. The shared
   `read_sec_filing` docstring now explicitly distinguishes literal `primary`
   from an observed `file:<name>` ID and explains how to request quoted passages.
   The same prompt subsequently produced a valid document citation. File/URL
   validation was not relaxed.
2. Real ChatGPT OAuth returned `response.completed` with `output: []`, after
   sending both `output_item.added` and `output_item.done` for each call. The
   fallback concatenated those items and invoked each tool twice, first with
   empty arguments. Arguments-done also identified the item by `fc_...`, not
   its distinct `call_...` output identifier.
3. The OAuth function schemas omitted `strict`. The Responses backend normalized
   optional, non-nullable strings into required strings, so the model supplied
   empty cursors/dates and SEC validation rejected them. Optional-key schemas
   require an explicit non-strict request, or a fully specified nullable strict
   contract; empty-string coercion is not a repair. See the
   [official function-calling contract](https://developers.openai.com/api/docs/guides/function-calling).
4. Independent review found two further streaming boundaries: ID-less,
   interleaved arguments could be attached to the last-added call, and EOF before
   `response.completed` could still produce terminal `done`. These require
   identity-safe association and an explicit premature-EOF error, respectively.
5. Follow-up review caught final-output authority and nullable-ID edge cases:
   a complete final output must supersede ambiguous provisional events without
   borrowing their arguments; a null ID in an indexed snapshot must not erase
   an already resolved identity. Both received dedicated regression cases.

The initial OAuth runs ended with Research status `succeeded` because the agent
answered with source gaps. Those are not passing acceptance runs. The first
repair deduplicates added/done events by call identity, rejects invalid JSON
instead of invoking with `{}`, requires completed tool input, and sends explicit
`strict: false`. The reviewed corrections bind call/item IDs and output_index,
reject ambiguous/conflicting identities, and return `incomplete_response` on
premature EOF instead of successful completion.

RED-first results: the initial fallback/schema regressions produced 42 failures
against the original driver; that first repair passed all 94 driver cases.
Identity-association review cases then produced 20 failures before repair and
114 passes afterward. The EOF cycle produced 7 failures before repair and
120 passes afterward. A separate parent rerun over ten relevant files passed
**896 tests in 38.88 seconds**, including four-channel SEC adapters, output
boundaries, captured authority, delegated citation traces and child cancellation.
No full-suite result is implied by these focused counts.

The final review cycle reproduced five failures across six new cases before
repair, then passed all 126 driver cases. The ten-file focused suite subsequently
passed **902 tests in 38.06 seconds**. The reviewer found no remaining actionable
issue in the corrected final-output/null-ID paths. Final source SHA-256:

- Driver: `237cd531b7d9336c89acb1a4ae0c4a035363e4a3c9649c594b1c35ac93619840`.
- Driver tests: `fcc7c338e7a0373d800f65b8356a504eac9af7af476770f0bfcf7474edd76703`.

## Observed Checks

### API Tools And Restart

Live run `6fd8acff-e679-42b7-aed3-9fc5a07f6530` executed all three SEC tools.
It retained one filing citation, two fact citations and one 1,800-character
document passage, without citation gaps. The exact reported decimal survived.
Comparative fact periods and unknown derived period classification were reported
honestly; the text search passage was not misrepresented as a numerical table.

All four citations were re-read through the actual API and Desktop Research
history/evidence controls before and after a real Electron/sidecar restart.
The entire citation-read result set was identical, not merely the visible quote:
SHA-256 `031027600229bf0127b8b956eb551ee8f0c3614c24fb4c55311fe0cac882fc53`.

### OAuth Tools

With the protocol/schema repair, the original prompt executed each tool once,
with valid optional arguments. Its `period="annual"` filter correctly excluded
stored observations classified as unknown. The model reported the source gap
but did not follow the documented `period="all"` inspection path. This is not
evidence of a missing revenue value or passing fact-citation acceptance.

A separately labelled prompt explicitly requests reported observations using
`period="all"`, retains reported start/end/fiscal_period and forbids inferred
annual/quarterly classification. Run `aab8f58e-84ab-418a-946c-22877ef33b25`
completed all three tools once and retained all four citations. It reported
`383285000000` and `391035000000` USD exactly, with their supplied periods and
the `period_unknown` gap, without attributing the numbers to an unrelated text
passage. This is a distinct scenario, not a rewritten result for the original
prompt. The shared tool docstring now explains the distinction; no financial
period inference/filter logic was changed.

Actual API and Desktop evidence controls read all four saved citations. Their
complete read-result hash equals the API run above, byte for byte. They remained
identical after an actual Electron/sidecar restart from process 1678670 to
1696773, loading the final identity/EOF corrections. All three citation views
were reopened through Desktop history/evidence controls, not just an API call.

The committed revision was then launched separately and exercised by live run
`6d4b8f75-6f06-4845-923b-ba13b916c935`. All three tools completed. There were
four distinct call IDs: the model first queried facts without an accession,
then made a second, accession-bound facts query. This is not a duplicated
invocation of the same call. Six retained citation references, including the
repeated fact references from those two queries, reopened successfully through
the API and Desktop before and after another actual restart (1707689 to
1710293), both running the final committed product. The complete read result
remained identical: SHA-256
`3aef0b0a8b0762100bb1bc5ad4c3a56e3a3c60375c9617975ddb46d024a373ad`.

### Cancellation

Live OpenAI API run `67bfa6f8-0b22-436c-b879-aa872cf5a08c` was stopped through
the actual Desktop button after a document tool completed and the next Responses
request started. Terminal `cancelled` was observed after 0.173 seconds. The
pending HTTP request raised `CancelledError`; the completed citation remained
in durable Research records. Local response latency observed was at most 0.019
seconds. No new provider/SEC request started during the five seconds observed
after terminal cancellation. This finite observation is not a claim about
unbounded future time.

The first OpenAI-parent/Anthropic-child attempt reached the real Anthropic API
but received HTTP 400, insufficient account credit, before any child SEC tool
could run. It was not counted as passing. The user then identified another
existing funded API key. Only the private child environment switched to that
credential; no purchase or production credential-selection change occurred.

Run `4daa54b1-e25e-434b-ad1f-c54b4d6e1a7b` then exercised the actual OpenAI
parent and `claude-sonnet-5` Anthropic child. The Desktop Stop button was pressed
after one child SEC document citation completed and a subsequent Anthropic
request started. Terminal cancellation took 0.124 seconds; observed local
response latency was at most 0.006 seconds. The completed child citation was
retained and no new provider/SEC request started during the five-second
post-terminal observation.

Both direct and delegated cancelled runs reopened their retained document
citations through the actual API and Desktop after a real App restart. Each
1,800-character passage and the complete read result remained identical:
SHA-256 `e05bf0596c9d3cfa76bd3eb5c73ed91bec66adfe6f4d4370202a7348427fc9a8`.

### Retained Data And Native Host

A separate isolated current-entrypoint API run passed 121 bounded checks over
backup copies: all 23 threads and 108 message public projections, both report
metadata records and memories, one retained SA article and 100 news bodies,
native-host framing from an unrelated cwd, synthetic incremental article/news/
comment ingestion and replay deduplication, and original-row preservation.
Three old error-message bodies intentionally use the current error sanitizer;
the other 105 bodies remain verbatim. All three working databases passed full
`integrity_check`. No production store received these test writes.

Both report bodies initially returned 404 because their separately referenced
Markdown files were absent from the database-only fixture, not from production.
A supplemental isolated API run using private copies of those two files passed
19 checks: `/reports/2` and `/reports/3` returned HTTP 200 with exact full-text
and UTF-8 byte equality (8,488 and 1,228 bytes). The original backups and prior
fixture were unchanged. Both disposable API processes were shut down.

These are separate earlier source snapshots, not a claim of final-revision
whole-suite coverage. Synthetic native-host replay does not establish that a
logged-in SA browser extension completed a fresh synchronization.

### Backend Baseline

The first full default-order run at immutable `4d4a5e2c` completed with
11,226 passed, 55 failed and 12 skipped. It is retained as a failed baseline,
not product acceptance. The fixture omitted `jsdom`, prevented tests from
creating generated files under source/data, and caused DAL to select the wrong
project root. A separate corrected fixture reran exactly those 55 identities
once, in their original order, against unchanged `4d4a5e2c`: **55 passed, zero
failures/errors/skips**, 27.98 seconds. Its complete locked Node dependencies,
writable disposable source/data mount and correct project root resolved all
three categories. All 12,003 tracked files and failed-baseline receipts remained
unchanged. No skip, assertion or product change accommodated that harness
mistake. This targeted rerun is separate from the final complete-suite run.

### Final Backend Acceptance

One complete, default-order session on immutable
`13248718b0a91fede0219c8b6ca742d74eb12627` completed with **11,360 passed,
12 skipped, zero failures/errors, exit 0**. All 11,372 collected identities
agree between log and JUnit, without duplicates or partition aggregation. The
12 skips are the existing manual SEC/IBKR cases, not newly skipped failures.
Pytest reported 1,421.61 seconds. No other tests or scans ran in that fixture
during the full session; all finite test/supervisor processes finished.

All 12,004 tracked source files were verified unchanged before/after; installed
dependency locks and the failed-baseline receipts were preserved. Source
manifest SHA-256:
`bfbaefbc1e8cf9cce0afd6d719f867e2df05fdecde3f4eafb9b787e4577485c1`.
Runtime stayed Python 3.10.12 / SQLite 3.37.2 / Node 22.14.0.

Private reproducibility artifacts remain under
`/tmp/arkscope-current-corrected.DRLG4b3f/final-13248718b0a91fede0219c8b6ca742d74eb12627/`:
`results/pytest.log`, `results/pytest.xml`, `results/summary.json`,
`results/completion.json`, `results/runtime.json`, `results/test-outcomes.json`,
`results/evidence-manifest.json` and `containment.sh`. No private databases,
credentials or research contents are copied into this repository.

There is no `apps/` or `extensions/` product delta from `f4925da9`. The prior
1,853 frontend tests in 124 files, typecheck and production build therefore
remain evidence for unchanged frontend inputs; they were not rerun or added to
the backend count in this session.

### SA Manual Fixture

The user confirmed the real logged-in extension sync has not been tested.
A separate fixture at `/tmp/arkscope-sa-manual.CYHtVYUy` uses a read-only
412-file runtime subset verified against the tested commit, disposable copies
of the market/SA backups, a fresh profile DB and a fresh browser HOME. It has
no production keyring/browser profile/config mount and no inherited provider
keys. A private environment-pinned sidecar URL prevents fallback to production.

The actual API startup, nonempty retained article/news reader gate, graphical
Chrome startup, owned-process stop and subsequent restart were exercised.
Chrome exited 0, the API shut down on SIGTERM, and no forced sandbox kill was
needed. The new private Chrome window is visually nonblank. Desktop-bus/udev
and machine-ID warnings in this restricted environment were not mistaken for
successful extension registration. No `--no-sandbox` workaround was added.

The fixture is left open for manual loading. Native-host registration is still
absent; user login, browser-originated native ping and incremental article/news
body readback remain unverified. Only load the extension from the sandbox-visible
`/fixture/source/extensions/sa_alpha_picks`, then register the actual displayed
extension ID in that fixture. Do not redirect the existing normal browser's
native host, copy login cookies or count the earlier synthetic replay as a
passing login/sync check. The private `stop.sh` targets only this fixture.

## Pending

- A real logged-in SA extension synchronization remains a separate hand test.
- Integration decision after acceptance.

No merge, push, production App restart or interpreter switch was performed.
