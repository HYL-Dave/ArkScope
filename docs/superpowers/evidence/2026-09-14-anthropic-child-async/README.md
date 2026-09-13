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
- [ ] Independent review and complete backend acceptance.
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
