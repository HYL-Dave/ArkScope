# Anthropic Child Async Follow-Up

Source baseline: `bf7831b870cd051bd4969abceb647f8b8d195885`.

This bounded follow-up implements the async child direction approved on
2026-09-14. It closes N1 from the release-integration checkpoint, not the
unrelated cleanup/runtime deployment backlog. Initial status: in progress.

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
- [ ] Re-run one complete backend suite after the fixture correction.
- [ ] Seal evidence and update the release checkpoint.

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
