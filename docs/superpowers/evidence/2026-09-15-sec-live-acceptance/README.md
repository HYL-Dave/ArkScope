# SEC Live Research Acceptance

Status: live SEC checks passed. Real logged-in SA hand tests exposed an
article-body capture defect; the repaired parser now passes the same-article
foreground retest. Fixed-revision backend/frontend acceptance now passes at
`bf730ea2`. The user also requires foreground/background comparison before the
integration decision; background collection is not yet accepted.

Base revision: `4d4a5e2c997576acb3f2d98141b641612e029c95`.
Last fully tested product: `bf730ea2a133ba6c4f7405d7be23d129a305df9a`.
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

The user loaded and logged into the original extension in this private Chrome;
its actual native-host registration and browser-originated sync succeeded.
Quick Update completed four phases in 66,860 ms, refreshing 60 article metadata
rows, adding one comment and one article link. The comment and a retained
5,704-character body matched the actual API. All article bodies were already
cached, so this did NOT exercise a fresh article-body download.

Sync Latest News completed five phases in 150,198 ms, adding 49 metadata rows
and 18 bodies totaling 24,655 characters. All 18 bodies matched actual API
readback. Existing article/news IDs and bodies were preserved; market main/WAL
hashes were unchanged. Checkpoints are `data/evidence/after-quick-4sk875d2` and
`data/evidence/after-news-da9bqf8y` under the private fixture.

### Background Experiment And Fresh-Body Finding

The user separately approved a disposable background-tab experiment. A private
copy adds an observation wrapper and suppresses only collector-owned activation
requests. It changes no collector/parser/scroll logic, Chrome permissions or
throttling flags. The original source inventory remains pinned and unchanged;
this instrumentation is not a product patch or a release build. All browser
login and native-host changes are confined to the private HOME.

Exactly one previously cached, current-pick-linked article was made missing in
the disposable DB, preserving its metadata, comments and links. This prevents
a warm-cache no-op from being counted as successful body acquisition. Before
the subsequent foreground control, only that same body was reseeded. Other
updated inputs were retained, so this is not a whole-DB matched-input A/B test.

The background Quick run lasted 51,943 ms. The user reported no focus stealing;
the actual Chrome receipt records zero collector activations, four suppressed
activation requests, 72 inactive-tab samples and 64 hidden/unfocused document
samples, with no observation errors or truncation. These are sampled states,
not proof of continuous visibility or indefinite reliability. The missing
3,684-character article body matched its original hash and actual API. However,
the job was `failed / degraded`, with two durable `comment_scan_failed`
diagnostics, and only 20 article metadata rows updated. The seeded article's
retained comments remained readable but its scan timestamp did not advance.
The aggregate `detail_save_failed` phase reason is a fallback label, not proof
of a database write error. **Background collection is not accepted.**

The same-extension foreground control lasted 82,417 ms. Its receipt confirms
foreground mode and one collector activation. All four job phases report
complete; 60 article metadata rows updated, five new comments were saved and
all old comments were preserved. Both previously failed comment targets now
advanced their scan timestamps; their retained 646 and 475 comments matched the
API exactly. The seeded article's comment scan also advanced.

**Despite the successful job label, its newly captured article body is wrong:**
5,660 characters of comments/replies, starting with `COMMENTS (68)` after the
article title, replaced the original 3,684-character body. The API serves that
wrong text unchanged. API/DB equality and a nonempty body therefore do not
establish content acceptance. Original/background SHA-256:
`a5c4bf3c0c2d5526f41f6e4ab32691e7f0fec9882a47edb57e6ce72b9e16bd40`;
foreground SHA-256:
`ceecba36c451353a5c4e9b00f7bba3534ed772858d978cacfe0b1d4d18b53b8a`.

Code inspection found unfiltered text-length ranking among provider containers,
no selected-root exclusion, and comment rows not recognized by the body
scraper's exclusion rules. Nested `article` / `main` fallback also bypasses
recursive filtering. No live DOM snapshot was captured: the exact winning
selector/ancestry is not established. Existing identity/scraper tests still
pass (10 cases in an isolated baseline), demonstrating missing coverage rather
than remediation. A bounded structure-aware fix and same-article live retest
were proposed at that checkpoint; the subsequent approved repair is recorded
below. Those earlier passing tests did not establish remediation.

Private evidence: `FOCUS-PROBE.md`; checkpoints
`data/evidence/after-focus-background-quick-cz4dt24g` and
`data/evidence/after-focus-foreground-quick-1q8la3oa`, each retaining its own
`comparison.json`, `api-focus-readback.json` and `probe-artifact.json`; Chrome
receipts under `data/evidence/focus-probe/`. No private article/comment text,
databases or credentials are committed. Both working DB integrity checks are
`ok`; market main/WAL hashes are unchanged. Production data did not receive
these test writes. The private `stop.sh` still targets only this fixture.

### Approved Body Repair, September 16

The user approved repairing article-body selection and retesting the same
article in the disposable copy, without shipping the no-focus experiment.
The product change is confined to `scrape_detail.js`, with 50 new regression
cases in `tests/test_sa_extension_article_body.py`.

Known comment rows anchor bottom-up sibling groups. Recognized heading/control
units join those groups only with row evidence; unclassified prose stops their
growth and mixed parents remain available. Root/ancestor checks prevent a
provider-marked descendant from re-entering a rejected comment context. Ranking
uses retained text instead of the raw comment-inflated length, preserves the
provider-first tiers and keeps the existing 200-character threshold. Row-bearing
contexts additionally require retained narrative structure; ambiguous div/span
UI without such evidence returns unavailable. This is not a claim that arbitrary
unmarked UI prose can always be distinguished from article prose.

Review exposed and tests reproduced nested-candidate bypass, incidental class
substring rejection (`no-sidebar`, `commentary-layout`), lost direct/inline prose,
nested comment-table cells, the first retained table-row separator, and rendered
text reconstruction problems. The correction uses semantic class tokens,
preserves direct text around nested wrappers, enumerates table-owned rows/cells,
keeps rendered separators, treats HTML comments as non-rendering, and excludes
`display:none` content. Extraction does not mutate the DOM used afterward by
the comment scraper. No collector navigation, scroll, retry, save or scheduling
behavior changes in this repair.

Reproducible local evidence under `/tmp/arkscope-sa-body-repair.CGUODf5P`:

- `red-body.xml`: 20 failures / 18 passes, including the original ten passing
  identity/scraper cases. `red-groups.xml`: four additional failing cases.
- `red-review.xml`: eleven review regressions fail; `red-render.xml` confirms
  the table-separator defect with a whitespace-insensitive expectation and the
  added hidden-content defect. `red-separators.xml`: the added duplicated-block
  separator regression fails. These overlapping runs are not summed as a suite.
- `related-final.xml`: one serial run, **266 passed, zero failures/skips**,
  55.26 seconds, over `tests/test_sa_extension*.py` and `tests/test_sa_tools.py`.
- `rendered_probe.py` / `run-browser.sh`: actual Chrome 151.0.7922.137 via
  Playwright, fresh disposable profile, network disabled, Chrome sandbox enabled,
  no logged-in browser/private-data mounts. Native `innerText` tests initially
  passed 1/5, then 3/5; the final identical five cases all pass in
  `native-final.json`. They cover HTML-comment/BR handling, pruned inline/block
  separators, hidden text, row-anchored grouping, all article paragraphs exactly
  once, and unchanged DOM. These are synthetic rendering checks, not live-site
  or background-tab stability acceptance.

The last bounded review caught three additional paths: inherited rejection
through shared page ancestors, HTML-comment nodes flushing a direct-text group,
and block-styled spans being joined as inline text. `red-final-review.xml`
reproduces all five added regression cases. Rejection now follows recognized
extraction containers, not arbitrary shared page ancestors; non-rendering nodes
are skipped before flushing; computed block display overrides inline tag names.
The reviewer statically confirmed those three corrections, with no remaining
blocker from those findings. This is not an exhaustive guarantee about unseen
site DOM variants.

Final same-revision verification: `related-reviewed.xml`, **271 passed, zero
failures/skips**, 58.35 seconds, one serial related-suite run. Two further native
Chrome rendering cases were first observed failing in `native-followup-red.json`;
all seven cases pass in `native-reviewed.json`, including unchanged DOM and all
article paragraphs. Parser SHA-256 verified by that final native-browser run:
`ebf8fa9a83ffad51662a2c4feefc5e151f9792e9cbbdcfe99e50fe69baa18367`.
The earlier 11,360-test full-suite result belongs to `13248718`. At this repair
checkpoint only the related suite had been rerun; the subsequent logged-in
retest and new fixed-revision full acceptance are recorded below.

### Same-Article Repair Retest, September 16

The user reloaded the disposable extension and completed one foreground Quick
Update with parser commit `0a60b73410a97879c7fd2c93229c52a1fc2934f3`.
Post-run verification checks all 27 extension files against the prepared overlay
inventory and all 412 readonly base files against `13248718`. Only the parser
was overlaid; API, collector flow and foreground instrumentation stayed on the
previously recorded base. This is a hybrid component test, not whole-revision
App acceptance or acceptance of background collection.

The same seeded article, whose body and detail checkpoint were NULL before the
run, now contains **3,684 characters, byte-for-byte equal to the original
article**. Its SHA-256 is
`a5c4bf3c0c2d5526f41f6e4ab32691e7f0fec9882a47edb57e6ce72b9e16bd40`.
All ten original long paragraphs are present exactly once. There is no
`COMMENTS (n)` heading or full-comment match of at least 50 non-whitespace
characters; it is not the previously rejected 5,660-character comment body.
Actual authenticated API readback returns the identical article body. This
establishes a passing same-article content retest, not just a nonempty-body or
successful-job check.

Its comment scan advanced, retaining all 61 prior comments and adding one.
The two earlier failed-comment targets also advanced their scan timestamps,
retaining 646 and 479 comments (the latter adds four). All three targets' full
comment collections match actual API readback; no prior comment IDs were lost.

Job 5 reports `succeeded / complete`, all four phases complete, with zero
recorded or omitted diagnostics. Duration: 94,901 ms (collector: 94,847 ms).
The Chrome receipt records foreground mode, one activation, zero suppressions,
111 samples, 97 active-tab samples, 89 visible and 11 hidden document samples,
with no navigation/script/observation errors, truncation or removal failure.
These samples do not prove continuous visibility or repeated-run reliability.

Across this Quick run, 59 existing article rows changed and one new article was
added. Two bodies were acquired: the deliberately missing body and the new
article. Only the former has the original-body comparison described above;
do not infer independent semantic validation of the second from its length.
Thirty-eight comments were added; all previous comment rows are unchanged.
All previous article/news IDs are preserved, and no pre-existing nonempty body
changed. News rows and other retained SA tables are unchanged except pick and
refresh metadata. Profile changes are limited to the new job. Both copied DB
integrity checks return `ok`; private market main/WAL hashes remain identical.
These writes stayed in the disposable fixture, not production stores.

Private evidence under `/tmp/arkscope-sa-manual.CYHtVYUy`:

- Baseline: `data/evidence/before-body-repair-quick-f5q__vwz`.
- Result: `data/evidence/after-body-repair-quick-hk1hs4oa`, containing the
  checkpoint receipt, row comparison, `api-body-repair-readback.json` and the
  verified `probe-artifact.json`.
- Chrome receipt: `data/evidence/focus-probe/5e68601f-22d1-4891-8618-3479d3bc3a6a.json`.
- `body_repair_readback.py` checks session/controller/listener identity, uses
  only authenticated loopback GETs without proxies or redirects, and reads
  query-only checkpoint copies. Its write sandbox permits only the new evidence
  directory and scratch; private article/comment text is not printed or committed.

## Pending

- Complete the newly requested matched-local-input foreground/background
  comparison. The prior background Quick failure remains a failure; no
  background News run or repeated-run stability claim has been made.
- Integration decision after acceptance.

No merge, push, production App restart or interpreter switch was performed.

## Fixed-Revision Acceptance, September 16

Tested revision: `bf730ea2a133ba6c4f7405d7be23d129a305df9a` (including the repaired
parser). One complete backend invocation, default pytest order, no concurrent
tests or scans in that fixture: **11,410 passed / 12 skipped, zero failures or
errors**, exit 0. Pytest reported 1,455.47 seconds. All 11,422 collected case
identities and outcomes agree between the full log and JUnit; no duplicates,
partition sums, new deselections or added skips. The skips are the existing
two live SEC cases and ten manual IBKR cases.

All 12,005 tracked files were verified against raw Git blobs before and after,
with no source drift. Installed dependency locks and older failed-baseline
evidence remain unchanged. Source manifest SHA-256:
`a69ec21d564da85b47669159d9a6ab4bfe9416ff9cb173031956bf76a37d85c6`.
The runtime stayed Python 3.10.12 / SQLite 3.37.2 / Node 22.14.0. There were no
production databases, provider credentials or browser profiles mounted in the
backend acceptance sandbox; external networking was unavailable.

Artifacts:
`/tmp/arkscope-current-corrected.DRLG4b3f/final-bf730ea2a133ba6c4f7405d7be23d129a305df9a/`,
including `results/summary.json`, `pytest.log`, `pytest.xml`, `test-outcomes.json`,
`evidence-manifest.json`, the exact invocation, and the unchanged containment
and source-verification helpers reused from the earlier final run.

After the backend finished, a separate frontend sandbox tested the same
revision: **1,853 passed in 124 files, zero failures/errors/skips**; TypeScript
`--noEmit` and Vite production build both exit 0. The 296 tracked web files are
unchanged after every stage. Installed dependencies were readonly; copied App
files, Vite caches and build outputs were disposable, not master write targets.
Vite reports a chunk-size warning for the 1,193.62 kB JavaScript bundle; that
warning is not hidden or counted as a test failure. Frontend artifacts:
`/tmp/arkscope-final-web.tqyxgd63/results/` and its `run.py` wrapper.

These results close the repaired revision's automated acceptance. They do not
establish foreground/background live equivalence. The latter is a separate
explicit user request with matched private starting stores and actual browser
acquisition; no merge is authorized by claiming those two results interchangeable.

## Matched Foreground/Background Preparation, September 16

The user explicitly requires both modes to be accepted before choosing the less
disruptive behavior. The earlier background Quick failure is not overwritten by
the repaired foreground pass. Universal equivalence, reliability when minimized,
and other-platform behavior are not established by this comparison.

`/tmp/arkscope-sa-manual.CYHtVYUy/data/matched-ab` contains an immutable common
baseline and two independent disposable cases. SA/profile inputs come from the
passing repaired foreground checkpoint; market input is the existing immutable
fixture input. All three databases initially match byte-for-byte between cases,
without hard links. Each case has its own identical 412-file runtime copy,
source/data fallback root, HOME, locks, token and scheduler-disabled API. The
27-file extension overlay remains unchanged, including the repaired parser.

Both copies deliberately need the same known article body, three comment scans,
and one recent retained news body. Existing IDs, article/news/comment rows and
other bodies are preserved. The three comment targets have NULL
`provider_comments_count_at_last_scan`, not only NULL timestamps: Quick uses the
provider-count checkpoint rather than the full/backfill timestamp TTL. No fake
provider counts or full-history request is introduced.

Post-start checkpoints verify equal SA capture inputs and retained records. The
only permitted startup difference is
`scheduler_state[source='security_lifecycle.automation'].updated_at`: that one
timestamp advances during the existing startup reconciliation. Every other
column in that row and all other retained rows are compared exactly. Both copied
database integrity checks return `ok`. Successful checkpoints are listed in
`preflight.json`, under `preflight-attempt-2alcdfl6`; their SA SHA-256 is identical:
`a8bbe4ce7fe6bb8d8d9c899241f2a4dc9104f8dd262f6b01c6977234deb56805`.

The private native config now changes only `host_script` to the acceptance
wrapper. The unchanged product shell launcher and native host were actually run
with framed `ping` and `get_market_news_recent_ids` messages. Both pass, and
synthetic inherited API/DB targets are replaced by the selected case environment.
The selected authenticated API must be available before native admission;
readiness and selection are rechecked. API teardown invalidates readiness before
stopping the child. Failed post-redirect checks remove the active selector rather
than falling back to the original store. Eight synthetic harness tests pass,
including stopped/stale/unavailable API rejection, exact-frame replay, and three
failed-activation stages. These are separate from the full-suite counts above.

The wrapper records content-free hashes/counts of actual submitted comment
collections, then replays the exact original frame to the unmodified native
host. Those observations prove fresh submitted input, not successful saving:
acceptance also requires native save results, exact API/DB readback, advancing
checkpoints, persisted job receipts and no unexplained omissions. Retained cache
totals alone cannot pass the comparison. Website data and browser HTTP-cache
state are not pinned; source-time changes must be separated from capture loss.

The bounded independent source review found and then checked the corrected
admission/teardown/failed-activation guards. It performed no live operations and
does not establish mode equivalence. Preparation failures are retained privately:
the initial readonly-copy permission error, the too-strict startup timestamp
comparison, Python 3.10's `Z` timestamp parsing mismatch, and a native smoke mount
ordered after the readonly-root remount. They stopped before browser redirection;
no product code or original database was changed to make them pass. Two owned,
uncollected case APIs were explicitly restarted after the guard correction.

Current receipts: `preparation.json`, `comment-work-preparation.json`,
`environment-check.json`, `restart-before-admission-guard.json`, `preflight.json`,
`activation.json`, and `launcher-preflight.json`. The original fixture guard
checkpoint is `data/evidence/before-matched-ab-original-0yaibzr9`; its SA/profile
integrity checks pass. Original, foreground and background job counts all remain
five after launcher verification. Production stores are not used by these cases.

Next manual action: reload the same disposable extension and run foreground
Quick Update once. Verify it before News, then perform background Quick/News on
the untouched second case. Successful bounded repetitions are still needed for
a stability claim. No matched live run, merge, push or interpreter switch has
occurred at this checkpoint.

## Matched Foreground Quick Readback, September 16

The user reloaded the disposable extension and completed the foreground Quick
control. The 27-file extension overlay and 412 readonly base files still match
their inventories. Only this foreground case received the new capture; the
background case remains at the matched starting state.

Persisted job 6 is `sa_alpha_picks_refresh`, `quick`, `succeeded / complete`,
82,061 ms, all four phases complete, zero recorded or omitted diagnostics. The
native host's single completed-event receipt reports `persisted=True`, run 6,
and its client event identity matches the stored `extension_event`. The private
save-check helper initially assumed separate start/finish events; source review
and the actual log establish one completed event containing both timestamps.
The check was corrected to that existing contract, without product or DB edits.

The seeded article's 3,684-character body is byte-identical to the original,
SHA-256 `a5c4bf3c0c2d5526f41f6e4ab32691e7f0fec9882a47edb57e6ce72b9e16bd40`.
All ten long paragraphs appear exactly once; no comment heading or complete
comment text is included. The body was NULL before the run, so this is actual
acquisition. Authenticated API readback matches the stored body exactly.

Four fresh comment submissions were observed: the seeded body target (62 rows),
the two previously failed comment targets (124 and 92), and one additional
incremental comment target (48). Native save logs independently report the same
prepared counts: **326 submitted/prepared rows, 50 net new comments**. Every
submitted text hash is present in the stored collection and exact API readback;
all prior comment IDs and rows remain. The three seeded targets' checkpoints
advance. Scraper IDs use `syn_...` while the native host/backend deliberately
normalize them into persistent IDs. Consequently raw-vs-stored ID hashes all
differ; the unmodified raw mismatch metrics are retained, not misrepresented as
lost comments. Cross-mode comparison must compare like identity namespaces.

This is a **passing bounded foreground Quick acquisition/save control**, not
complete historical-comment coverage. The two previously pending recovery
targets remain pending. The additional target changes `repaired -> pending`:
48 fresh texts have no overlap with its 23 older retained comments; all 23 remain,
giving 71 stored comments against an observed provider count of 77. The absence
of overlap is real new content, not merely regenerated IDs for identical text.
It is preserved as a coverage observation for the background comparison, not
silently cleared, diagnosed as data loss, or counted as fully recovered history.

The foreground focus receipt is
`e7ae248e-c8a3-4d4f-b815-2425173a6a91`: one collector activation, zero suppressed
activations, 97 samples (82 active, 75 visible, 12 hidden), no navigation/script/
observation errors, no truncation or removal failure. Its interval and all four
fresh submissions bind to the persisted job window. Samples do not establish
continuous visibility between observations or background equivalence.

All six copied SA/profile databases pass `integrity_check`. Full retained-row
and schema comparisons show **no changes to the background case or original
fixture**. The original market main/WAL hashes are unchanged; foreground and
background market hashes match. Foreground changes comprise 50 added comments,
60 updated article rows, pick/refresh metadata and one added pick/link/lineage;
its profile changes only by job 6. No prior article/news IDs or nonempty bodies
are lost or changed, and news rows remain unchanged.

Private readback:
`data/matched-ab/foreground/evidence/after-quick-g89moqb9/` under the existing
private fixture, with six checkpoint copies, `readback.json`,
`fresh-submissions.json`, `native-save-check.json` and
`comment-window-check.json`. `ab_quick_readback.py` verifies host-side API
ownership before its contained worker, uses query-only sources/WAL-safe copies
and authenticated loopback GETs, and emits no article/comment prose.
`ab_quick_savecheck.py` correlates the native saves and persisted receipt;
`ab_comment_windows.py` compares only closed checkpoints. No provider credential,
production DB, source parser, browser mode or production configuration changed.

Next: foreground `Sync Latest News`, then background Quick/News on the untouched
case. Background equivalence and repeated-run stability remain unaccepted; no
merge or interpreter switch has occurred.

## Matched Foreground News Readback, September 16

The user completed one bounded foreground `Sync Latest News`. Private readback
`data/matched-ab/foreground/evidence/after-news-5h44qmoq/readback.json` compares
six WAL-safe, integrity-checked SA/profile snapshots with the accepted Quick
checkpoint. The 412-file runtime base, 27-file extension overlay and native
control still match their inventories before mode switching. No product code,
production DB, normal browser profile or interpreter was changed.

Job 7 is `sa_market_news_refresh`, `quick`, `succeeded / complete`, 145,804 ms.
All five phases complete, no recorded/omitted diagnostics. The single native
completed-event receipt is persisted and matches the stored client event ID.
The native list save records 50 items saved, current detail limit 18, backfill
limit zero, 18 bodies requested. All 18 successful detail saves match newly
stored bodies in identity and character count; all 18 authenticated API bodies
are byte-identical to their DB values and have detail checkpoints. No acquired
body contains a comments heading. This is save/readback evidence, not an
independent semantic audit of every source article.

Exactly 50 news rows and 50 news-ticker links are added. No prior news/article
ID or nonempty body is lost or changed; other foreground SA tables are
unchanged. Its profile adds only job 7. Background and original-fixture SA/profile
schemas and retained rows remain unchanged, as do all three market main/WAL
hashes. The background SA/profile snapshot hashes still equal their original
matched preflight hashes.

The focus receipt `cc235877-2f6a-4707-8505-8d5ceeb02e49` binds to this job's
interval: one collector activation, zero suppressions, 86 observations (82
active, 61 visible, three hidden), no observation/navigation/script errors,
truncation or removal failure. Sampling does not prove continuous visibility.

This is a **passing bounded foreground News control**, not a claim that every
missing body was fetched. The older seeded news item remains body/checkpoint
NULL; it is visible among the latest 100 API items but was not selected by this
run. It therefore does not pass the originally desired same-seeded-news-body
reacquisition check. Keep that limit explicit, alongside the successful 18 fresh
bodies. The foreground Quick and News runs occurred hours apart; remote source
time and browser cache are not pinned. Compare common identities/content and
explicit coverage observations across modes, not raw counts alone.

`ab_news_readback.py` uses authenticated loopback GETs, query-only SQLite sources,
WAL-safe snapshots and a readonly filesystem outside the disposable data root.
All 17 checks passed. The receipt includes body identity/content hashes only,
not raw article prose, credentials or browsing history. Earlier failed background
and original-parser runs remain retained. Background equivalence, repeated-run
stability, merge and interpreter replacement remain pending.

### Background Case Selected, Awaiting Reload and Live Run

Only the disposable extension's `probe_mode.js` changes from foreground to
background; its parser and other 26 files remain identical. Selection was paused
first, with the foreground selector archived. The mode file was readonly; the
initial edit failed without changing it, then only that file's owner-write bit
was enabled for apply_patch and restored to 0444. No product source changed.

`select_background_case.py` verifies both owned APIs, native control/config,
all three runtime copies, the overlay and all six SA/profile stores against the
accepted News checkpoint. The background seeded article body remains missing,
ready for actual acquisition. After selection, the actual product shell launcher
passes framed `ping` and recent-news-ID reads against the background case, even
with synthetic inherited API/DB canaries. A second full guard passes afterward.
Job counts remain foreground 7, background 5, original 5; market hashes and all
retained records are unchanged by the switch.

Private receipts: `background-switch-preflight.json`,
`foreground-selection-ended.json`, `background-selection.json`. The latter is
the new 27-file overlay inventory; earlier inventories and `activation.json`
remain intact. A failed post-selection check removes/archives admission instead
of restoring original-store routing. This smoke is not a browser collector run.

Next manual action: reload the same disposable extension, keep an unrelated tab
selected and run one background Quick Update. Read back before background News.
Background equivalence and repeated stability remain pending; no merge, push,
production-data write or interpreter switch has occurred.

## Matched Background Quick Failed Acceptance, September 16

The user reloaded and completed background Quick without focus takeover. The
actual receipt confirms that the running worker used background mode, not merely
that its on-disk mode file changed. However, this run **fails collector acceptance**
and does not establish equivalence with foreground behavior.

Private evidence: `data/matched-ab/background/evidence/after-quick-ucbeiy_s/`,
containing six WAL-safe, integrity-checked snapshots, `readback.json`,
`fresh-submissions.json` and `comparison.json`. `ab_background_quick_readback.py`
returns exit 2 for the failed collector, although its 12 data-integrity,
isolation and evidence-correlation checks pass. The closed-checkpoint comparison
helper verifies the failure without changing the original receipt.

- Background job 6: `sa_alpha_picks_refresh`, `quick`, `failed / degraded`,
  87,487 ms, three complete phases and failed `article_details`. Its summary
  reason is `detail_save_failed`; the five retained, retryable diagnostics are
  specifically `content_parse / comment_scan_failed / article_comments`.
  The single native completed event persisted and matches the stored job.
- The previously missing seeded body is freshly acquired: 3,684 characters,
  SHA-256 `a5c4bf3c0c2d5526f41f6e4ab32691e7f0fec9882a47edb57e6ce72b9e16bd40`,
  identical to foreground, all ten long paragraphs once, no comment heading or
  complete retained comment text. Authenticated API readback is exact.
- Six actual native submissions contain **zero fresh comments**, including the
  combined body/comments request. Five comment-only saves report `usable=False`.
  The four common foreground targets submitted 62/48/124/92 comments, 326 total;
  all four submit zero here. Two additional targets are selected as provider
  counts change. Do not equate the pre-existing cached comments with acquisition.
- All six comment checkpoints/provider checkpoints remain unchanged, as does
  the entire retained comments table. No prior IDs or nonempty article/news
  bodies are lost or overwritten. Stored/API comment readbacks are equal, but
  these are retained records, not successfully refreshed comments.
- The actual article-metadata save reports 20 rows rather than the foreground
  control's 60. Existing article IDs remain retained; this is reduced observed
  acquisition coverage, not deletion of 40 stored articles.
- All six submitted scroll-stop hashes resolve to the source-enumerated
  `stable_bottom`, not timeout or maximum-scroll termination. The scraper stops
  with no loaded comments before native persistence. This localizes the failure
  upstream of storage; it does not prove why the site failed to populate them.

Focus receipt `2f5b5770-95dc-45d6-8646-88b34d49aa0b`: zero collector activations,
seven suppressed activation requests, 117 samples with zero active/visible and
106 hidden observations, no navigation/script/observation errors, truncation or
removal failure. The interval binds to the persisted job and all six submissions.
This agrees with the user's observation; it is not continuous-focus proof.

Foreground and original-fixture SA/profile schemas and retained rows are unchanged
from the accepted foreground News checkpoint. All three market main/WAL hashes
are unchanged. Background profile adds only job 6; its news tables are unchanged,
ready for a separately assessed background News control. Source/overlay/control
inventories still match the background-selection receipt, with the same parser
as the foreground test. No product change, production write or mode fallback was
performed to turn the failure into success.

One readback field needs careful interpretation: `body_same_as_foreground=false`
on two targets means no foreground *capture-check entry* exists, not different
cached body text. `comparison.json` directly compares the closed DBs and verifies
all six retained bodies match; only the seeded one was freshly acquired here.
The original field is retained rather than silently rewritten.

Remote website state and browser cache are not frozen: provider counts differ
between runs six hours apart. We therefore do not claim exclusive focus-only
causality, absolute historical coverage, or a universal browser limitation.
We do have a concrete failed background run using the matched starting DB and
same parser. Earlier background failures remain retained. Do not ship the
focus-suppression probe or call it equivalent/stable on this evidence.

Next bounded check is background News, independently assessed against the accepted
foreground News and this unchanged-news checkpoint. Passing News cannot clear
the failed Quick/comments result. No merge or interpreter switch has occurred.

### Follow-Up: Combined Capture Failure Reporting

Source review of the actual empty combined submission identifies a separate
reporting gap in the current product, not only in the focus-suppression probe.
`sa_capture_backend._capture_comment_scan` returns `comment_scan_usable=False`
when a nonzero provider count produces no comments; it correctly retains prior
rows and checkpoints. The body can still be stored successfully. The native
`_handle_save_article_content` forwards both results, but the combined branch in
`background.js` checks only body `ok` and reconciliation, unlike its comment-only
branch. The seeded body's failed comment acquisition therefore has no sixth
`comment_scan_failed` entry. A combined-only run can consequently overstate
completion even though this particular run is already degraded by five other
failures.

This gap was independently source-reviewed; no product fix has yet been made.
Proposed bounded correction: preserve body success while recording unusable
comment scans as retryable `article_comments / comment_scan_failed`, with tests
for combined-only failure, genuine zero provider comments, and usable existing
comments with zero net-new rows. User confirmation is requested separately from
the background-mode experiment. Keep the private collector unchanged while
finishing the remaining News comparison; do not hide its failed Quick result.

### Approved Reporting-Only Correction, September 16

The user approved the bounded correction, explicitly retaining the private
collector unchanged and not adopting background capture. The earlier failed
Quick receipt remains evidence of failed acquisition; this change fixes reporting,
not the site's comment loading or background-mode stability.

`background.js` now checks `comment_scan_usable !== true` after successful combined
body/comment saves in both `doDetailFetch` and `doManualFetch`. Each unusable or
missing scan result records one retryable
`content_parse / comment_scan_failed / article_comments` diagnostic and increments
the existing failure count. Body success is still counted, manual reconciliation
acceptance still runs, and storage failures keep their separate classification.
No backend storage, scrolling, focus, protocol schema or runtime policy changes.

The existing protocol deliberately distinguishes the entrypoints: automatic
Quick/Full/Backfill has a failed `article_details` phase and `degraded` outcome;
manual capture has a fatal `manual_fetch` phase and `failed` outcome. Both yield
database status `failed` and are ineligible to advance a healthy sync anchor.
The correction does not redefine those contracts or rewrite historical receipts.

Regression owner: `tests/test_sa_extension_reconciliation_flow.py`, with 27 added
cases. Its Node VM executes the real queued job, capture functions, diagnostics
collector and protocol derivation, while browser/site/native/telemetry transport
boundaries are synthetic. It verifies the submitted job result and diagnostic,
all four modes, false/missing/null/string usability flags, usable existing comments
with zero net-new rows, authoritative zero provider comments, and independent
storage failures. The existing nested-reconciliation failure fixture now explicitly
supplies a usable zero-comment observation; its behavior assertions are unchanged.

Private offline receipts and logs are under
`/tmp/arkscope-sa-combined-reporting.1Agu5NYh/`. Tests ran sequentially through
`run.py` and the existing `offline_pytest.py`, with a network-isolated bwrap,
read-only product source/dependencies, synthetic writable data/config/home, and
no mounted production or browser data. The final broader run imports only
`config/user_profile.yaml` and `config/sectors.yaml` from git HEAD, not operator
configuration. Python/SQLite remain on the current engine; no provider is invoked.

| Checkpoint | Result | Interpretation |
| --- | --- | --- |
| `baseline-r2` | 19 passed | Existing reconciliation/diagnostics baseline |
| `red` | 8 failed, 5 passed, 11 deselected | All eight failures are the original missing failure increment, `0 != 1` |
| `green-first` | 5 failed, 27 passed | Four new manual assertions incorrectly expected `degraded`; one existing fixture omitted scan usability |
| `green-r2` | 46 passed | Corrected assertions follow the unchanged manual fatal-phase contract; four modes and job submission covered |
| `sa-regression` | 5 failed, 717 passed | Runner hid the two versioned default YAML files needed by data-access config tests |
| `sa-regression-r2` | 722 passed | Same full SA/data-access selection, only runner mounts corrected; no skips or failures |

The initial `baseline` attempt failed at bwrap setup, before pytest, because its
node_modules mount did not resolve the worktree's absolute symlink. Its log is
retained separately; it is not a product-test result. The five broader failures
also remain recorded rather than being relabeled as product regressions or
removed from the selection. Final selection: `tests/test_sa*.py` plus
`tests/test_data_access.py`, including backend body-preservation and comment
checkpoint/recovery tests, native diagnostics, telemetry, packaging and parsers.

The final run verifies unchanged product/test SHA-256 hashes across execution:

- `background.js`: `cae63cd0117a50045ae881e36c26991d5397b68aab442d9e2c3be449c28e24b5`
- `test_sa_extension_reconciliation_flow.py`: `dee9fb416eecf23289dda5eb6bc167d457a18d9a3fec0782fd2d257ed1fe5091`

Independent read-only review found no blocking issues and confirmed the manual
versus automatic outcome distinction against both JS and server contracts. Its
residual coverage limits are that the new queued-flow tests mock persistence
and delivery, and do not combine comment and reconciliation failures in one
case; existing separate tests cover those failure classifications. The reviewer
ran no concurrent tests and accessed no private state.

This is scoped automated regression acceptance, not a new full-backend run or
live-browser acceptance of the correction. The loaded private extension, Chrome,
and its DBs were not changed. Background News remains separately pending; its
eventual outcome cannot erase the failed background Quick/comments result.
No merge, push, production DB write or interpreter switch occurred.
