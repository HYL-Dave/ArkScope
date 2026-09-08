# Lifecycle Web Investigation And Human Review

Task 8 on `codex/lifecycle-tracking-first`, base
`0b66732ba4a77c4ba823537001828c1a75563c5d`. Offline implementation and tests are
complete; admission requires `verification.json` and a valid `files.sha256.json`.
This is not a live provider/bundled-binary canary or a production installation.

## Delivered Contract

- One public investigation contract supports OpenAI API key, ChatGPT OAuth,
  Anthropic API key and Claude Code OAuth. The selected Research route and its
  active profile credential are bound before launch and at dispatch. OAuth never
  changes into API billing. Spark remains translation-only; the Fable 5.1/Claude
  OAuth release policy is unchanged, not evidence that all Claude OAuth is blocked.
- Opening a case, reading a result or preparing a review does not dispatch a
  model. An explicit launch confirms the account/model/auth and work envelope.
  The two phases are source discovery and analysis of captured public pages.
  No arbitrary user prompt, local tool, filesystem, shell, ambient browser,
  general subagent or alternate credential enters this route.
- API clients use the exact selected key and explicit endpoints, with SDK retries
  disabled and ambient custom/auth/proxy headers excluded. OAuth uses the reviewed
  bundled runtimes only. Its restricted purpose does not expand ordinary Research
  or Spark tools. ChatGPT token refresh is same-account and explicit-launch-only;
  cancellation during refresh prevents a later model submission.
- Public-source retrieval pins admitted public DNS addresses while verifying TLS
  against the original hostname; it checks every redirect, byte limit and deadline.
  SEC requests reuse the existing contact/governor policy, including cancellable
  waits. Unsupported or unread sources are visible incompleteness. Pages are not
  silently truncated and search snippets do not become evidence.
- Exact source passages identify the security, class, venue and action-specific
  date. Contradictions, missing conditions, unsupported successor links and active
  OTC evidence block action. An acquisition announcement does not remove tracking
  or redirect it to the acquirer. Syndication is not independent corroboration.
- A human-approved packet uses the existing atomic tracking writer. It binds
  evidence, finding, affected sources/memberships, options, date and profile effects.
  Changed inputs, open positions and newer positive trading evidence prevent
  application. The model remains the finding's author; the later adoption has
  human authority. Confirmation/approval failures cannot partially adopt a finding.
- Durable per-case runs own progress and immutable source/results. Interrupt
  acknowledgements or local process cleanup are not remote cancellation. Lost
  outcomes remain unknown and do not automatically retry. The UI, current-review
  API and Research read tool share a closed saved-finding projection; no token,
  private credential ID, full page or internal worker/remote ID is exported.
- The overview's provider listing state is still a provider observation. A Web
  finding or applied tracking receipt is not labeled a successful provider check.
  Both remain inspectable when a listing endpoint is unavailable.

## Installation Boundary

The independent `lifecycle_web_*` journal adds seven tables, including its version
marker. Existing manual/automation/identity/membership schema contracts are not
relaxed. An explicit installer requires a stopped App, digest-bound approval and
create-only private backup; it rechecks inputs under a transaction and verifies
all preexisting data unchanged. The profile bootstrap and reads never install it.
The population manifest retains dependency metadata, not full Web content.

Only temporary stores have been installed in this work. The installed-system
rehearsal covers idempotence, stale approvals, BLOB preservation, backup collision
and rollback. Production installation and complete existing-case cutover remain
separate approvals. An old backup must not be restored over unrelated later writes.

## Verification Method

The complete backend passes 6,584 tests with 12 skips and three existing warnings
(6,596 collected). The restored 62-file focus passes 1,919 and the 110-file
integration passes 2,738. All 23 backend and 11 frontend independent mutants fail
named owners. The complete restored frontend passes 1,547. Relative to Task 7,
backend adds 339 nodes and frontend adds 31, with no removals. Integration adds
671 nodes without removals: the 339 new tests plus 332 existing tests added to its
scope. The sealer independently rechecks typecheck, build and the i18n scanner
before publishing results. A complete packet records all final gate outputs.

`scripts/verify.py` creates an external source-only copy, excluding data, .env and
developer settings. Each backend mutation is independent and runs all 1,919
affected tests in four isolated shards; shard manifests and XML are retained.
The aggregate must have exactly the baseline nodes, no collection/setup errors
and a failure in the declared owning test. All product/test bytes are checked
before/after restoration. Integration and a separate single-process full backend
run follow. Frontend mutations run the entire 1,547-test suite, not one file.
An explicit `--recheck-restored` may rerun that complete frontend only after all
mutants were owned and both the copied source and worktree still match every
original source hash. It cannot reuse a campaign after a product/test edit. The
failed restored result remains in `restored_attempts` with its original JSON;
the fresh run uses a different filename and the same four-worker/test-timeout
configuration. Sealing independently verifies both attempts and all their nodes.

`scripts/run_browser.py` drives the real UI/parsers against intercepted synthetic
HTTP: all four channels, rename, contrary evidence, cancellation/unknown outcome,
changed review and unadmitted model, in EN/zh-Hant at 1440/390/320 pixels.
All 54 scenarios, 156 screenshots, geometry and pixel checks are source-bound.
The private preview server is stopped after each run. No production App starts.
This validates interactions and shapes, not factual search quality or live accounts.

Actual SDK serializers and a real network-free JSONL subprocess have additional
wire tests. They are stronger than constructor mocks but do not attest that an
unexercised remote service or bundled binary will behave as the fixture does.
Native hosted internals are not counted as observed HTTP requests. Two ArkScope
submissions per investigation are not two internal harness turns. Cancellation
may leave already-submitted remote work unknown. The live gate/envelope is in
`docs/superpowers/plans/2026-09-06-lifecycle-web-auth-adapters.md`.

## Historical Results

`historical-foundation.json` preserves the earlier 1,636/21/2,455 W1 component
proof with its different source hashes. It is not relabeled as current runtime
admission. `incremental/` preserves actual earlier RED/GREEN XML, including failed
fixture adjustments; it is not a reconstruction of RED from later mutations.
The Task 5/6/7 seals remain unchanged.

Earlier current-runtime attempts are not combined into final admission:
the first frontend baseline found two i18n-scanner false positives in internal
state expressions, and the first complete backend focus found two stale route
counts (206 versus 213). State naming/expression placement and the exact seven
new route entries were corrected without adding i18n exemptions or dropping tests.
Campaigns were stopped while sources changed. A later header mutant failed its
real serialized-request test, not the mistakenly assigned constructor test;
that campaign was rejected, the owner was corrected, and the campaign restarted.
Earlier browser harness runs corrected a translated button label, clipping-aware
geometry and inconsistent synthetic dates. Only the final frozen-source run is
admission. Geometry has a visible-overlap negative control and a clipped-control
positive control.

A subsequent UI review found that the stop-request explanation still said the
investigation had stopped, even beside an unknown remote outcome. A 9-test
component RED run fails its cancellation owner; both translations now describe
the request, and the same 9 tests pass. The owner checks both languages without
dropping the pending/unknown/no-retry assertions. Separate English and Chinese
mutations restore the misleading wording. The prior backend campaign was stopped
after 20 owned mutants, its copied source bytes were restored, and it is not final
admission. All final campaigns and browser scenarios use the corrected copy.

The final frontend's first restored run passed 1,546 tests and failed the existing
`visible literal scanner allows legacy debt only to shrink and requires zero in
migrated scopes` test at 5,021 ms. All 11 mutants had already failed their named
owners. Both source trees were byte-identical before the explicit full-suite
restored recheck; no assertion, timeout, worker count or product/test file changed.
The original failed run is retained, not overwritten by the recheck.

## Still Unexecuted

No live provider/model call, production DB read/write/install, App restart,
commit, merge or push occurs here. The earlier ARCH/LTHM/TA treatment and recent
price repair are not repeated. Request bounded live canaries and production
installation/case cutover separately before final user hand testing.
