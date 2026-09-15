# SEC Live Research Acceptance

Status: in progress; do not merge on this partial record.

Base revision: `4d4a5e2c997576acb3f2d98141b641612e029c95`.
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
mistake. This targeted rerun is not the pending final complete-suite run.

## Pending

- Final committed-revision live rerun and complete backend session.
- A real logged-in SA extension synchronization remains a separate hand test.
- Integration decision after acceptance.

No merge, push, production App restart or interpreter switch was performed.
