# Anthropic Child Async Follow-Up

Source baseline: `bf7831b870cd051bd4969abceb647f8b8d195885`.

This bounded follow-up implements the async child direction approved on
2026-09-14. **N1, the subsequent P2 cleanup finding, and the two route-inventory
regressions are closed. Linux complete-backend acceptance is GREEN.** This does
not close the unrelated cleanup/runtime deployment backlog or declare a complete
cross-platform SEC release.

Implementation: `e447d394` (async child and route inventory), `24c10280`
(pre-stream error cleanup and inspected SDK floor), `39b6587f`
(missed output-lifetime fixture collateral). The final frozen source anchor is
`39b6587f76deb79b22bf819f084c09985c560b4c`.

## Scope And Acceptance

- Reproduce the two route-inventory failures; include the schedule endpoint's
  method, path, module and handler as well as the exact SEC route set.
- Use the existing captured `RuntimeAuthBinding.api_client(asynchronous=True)`
  authority. Keep sync callers sync and OAuth child delegation fail-closed.
- Await real Anthropic SDK stream aggregation. The installed SDK exposes async
  `close()`, not `aclose()`; no new parser, model policy or retry policy.
- Prove a heartbeat during model I/O, external cancellation, repeated cancel
  during response/client finalization, completed SEC reference retention,
  absence of subsequent dispatch, and concurrent child isolation.
- Preserve all previous delegated dispatch/trace, auth, Fable and output-boundary
  owners; change only their affected SDK fixture surface when needed.
- Run a single complete backend `pytest tests/` invocation alone. The existing
  offline launcher provides temporary stores and denies production data and
  external provider access; it does not select partitions or waive failures.

No production DB/config/credential reads, provider calls, runtime install,
restart, merge or push. The existing linked worktree is reused. Disposable
checks live in `.superpowers/sdd/2026-09-14-anthropic-child-async/`; the three
runner helpers were copied byte-for-byte from the preceding reviewed checkpoint.

## Checklist

- [x] Verify baseline and SDK implementation.
- [x] Reproduce route inventory: 2 failed, actual 224 versus expected 223.
- [x] Route inventory GREEN (2 cases in `child-red`).
- [x] Model-I/O RED (2 heartbeat failures) then GREEN.
- [x] Repeated-cancel RED: all 4 real SDK cases close the client before the
  response finalizer has joined. Owned model-I/O task fixes this; 54 related
  cases pass, including unchanged delegated envelopes and retained references.
- [x] Expanded authority/concurrency controls GREEN (289 then 291 cases).
  The first covering run
  has 283 passes and 4 fixture-assertion failures: SQLite returns `sqlite3.Row`,
  while the added integrity assertion compared it directly to a tuple. The
  assertion now normalizes rows, without changing the expected `ok` result.
- [x] Pending response-header cancellation and `wait_for` timeout are covered.
- [x] First cancellation during already-started normal response cleanup:
  four RED failures. HTTPX sets `response.is_closed` before awaiting transport
  cleanup; the owner now joins that phase without cancelling it. This uses the
  SDK's public response property and keeps actual SDK tests as its regression
  owner, not a replacement parser or a transport monkeypatch in product code.
  Final focused verification: **295 passed**, including the two route owners.
- [x] First independent review: one P2, error-response cleanup during SDK entry.
- [x] Reproduce P2 with real SDK: 16 failures (429/500 close, 400 body/close).
- [x] Public SDK middleware now retains pre-entry responses and wraps only
  their byte-stream finalizers. Reads and retry policy remain SDK-owned;
  cancellation waits for cleanup then propagates, preventing another retry.
  Observed responses are released after each model turn. The intermediate
  `is_closed` cancellation workaround is removed, not stacked as another policy.
  First covering run: 145 passed. The middleware client shares the original
  HTTP client; it does not construct a second connection pool or select auth.
  Expanded covering: **317 passed**, including six unchanged-retry controls
  (400 once, 429/500 three attempts with a two-retry budget, both native parents).
- [x] Scoped independent re-review at `24c10280`: P2 addressed, no new
  actionable findings. This was source/evidence review, not a full-suite run.
- [x] First complete backend run: **11049 passed / 1 failed / 12 skipped**.
  The delayed-child output-guard test still replaced only the synchronous
  Anthropic resolver; its async child therefore missed the mocked HTTP entry.
  Isolated rerun reproduced that failure (1 pass / 1 failure). Both resolver
  surfaces now use actual SDK clients over the same mocked response handler;
  every original boundary assertion remains, with explicit request/guard
  controls added. Expanded output-lifetime/delegation covering: **593 passed**.
  This is a real missed test collateral, not an environmental waiver or a
  product connection-error fix. No product source changed after `24c10280`.
- [x] Re-run one complete backend suite after the fixture correction:
  **11050 passed / 12 skipped**, zero failures or errors.
- [x] Reconcile all 11062 collected/executed identities, unchanged skip IDs,
  required safety owners and unchanged source/runtime/runner identities.
- [x] Seal evidence and update the release checkpoint.

## Final Verification

| Check | Observed result |
| --- | --- |
| Single complete backend at `39b6587f` | 11050 passed / 12 skipped; pytest 1375.50s, launcher wall time 1379.518s |
| Collection/execution | Exact 11062-node equality; no duplicates or missing nodes |
| Earlier maintenance full-suite baseline | 10827 passed / 12 skipped; +223 nodes / -0, same 12 skip identities |
| This follow-up's release checkpoint | 11023 collected at `bf7831b8`; +39 tests, none removed |
| Source/runtime/runner freeze | 1160 source files unchanged before/after the complete run |
| Focused auth/retry/cancellation covering | 317 passed; later output-lifetime/delegation covering 593 passed; not additive |
| Frontend at `e447d394` | 1833 passed / 126 files; all 297 recorded frontend paths unchanged through `39b6587f` |
| Typecheck, build, i18n literal check | Passed; bundle-size and existing raw test warnings retained |
| Current-source census | 4400 candidates / 3579 uncertainties / 1176 files read; zero new candidates, uncertainties, reductions or untracked paths versus the previous integration census |
| Independent scoped re-review | P2 addressed; no new actionable findings; source/evidence review, not another full test run |
| Receipt ledger | 26 finished runs, 8 nonzero attempts, each classified; no unfinished runs |

The accepted source collection SHA-256 is
`ead0eaac7d2aa87282b7151e4ac0af8b37e82f859ba0db4001683c06f3ce7b88`.
See [node and runtime reconciliation](checks/accepted-validation.json),
[all check outcomes](checks/checks-summary.json), the
[original review](checks/review.md) and [scoped re-review](checks/rereview.md).
The first failed full run and isolated reproduction remain in `checks/`, not
replaced by the successful run. The read-only comparison's `review_required:
false` applies only to this delta; it does not close existing cleanup queues.
Its unchanged dependency-import metadata is not a claim that the requirement
version string stayed unchanged; the deliberate Anthropic floor is below.

The create-only [archive manifest](checks/manifest.json) binds 89 selected files
and 3055820 stored bytes, with both original and stored SHA-256 values. Generated
databases, HOME/credentials, binaries and unrelated scratch are excluded. Review
readback and replay helpers are included, not only result summaries.

The real SDK tests cover standard and beta heartbeat behavior, pending headers,
200 body/finalizer cancellation and 400/429/500 pre-entry cleanup, including
repeated cancellation and cleanup errors. Both native parents retain completed
SEC references, release operation ownership only after cleanup, and send no
post-cancel request. Concurrent child runs retain distinct calls/references and
pass the disposable profile's `integrity_check`. No live provider behavior or
exhaustive low-level network/redirect shutdown proof is inferred.

Earlier workflow/browser/inverse receipts retain their original source anchors
in the [release-integration checkpoint](../2026-09-12-sec-research-release-integration/README.md).
They are not re-labelled as fresh browser or inverse runs at `39b6587f`. This
packet owns the reproduced N1/P2 fixes and the new complete Linux regression
gate; it does not silently waive the broader release checklist.

## Remaining Scope

The native Anthropic *parent* still has its pre-existing synchronous model
stream; this repair is specifically the async delegate composition N1 and does
not claim a repository-wide async conversion. OAuth delegated model execution
remains unsupported, without falling back to a billable API key. No SEC data
schema, source transport, output policy or selected model/effort changed.

SQLite activation, C12/C15/C20, locale/SQL census queues, production disposition
and Windows/macOS acceptance remain separate work. A successful Linux offline
suite will not be reported as those tasks being completed.

The dependency floor is deliberately raised from `anthropic>=1.2.0` to
`anthropic>=1.4.0`, the installed version whose public `with_middleware` contract
and client-copy behavior were inspected and exercised. No support claim is made
for that interface on untested older versions; no installed package changed.
The requirement does not alter Claude Code SDK/OAuth admission.
