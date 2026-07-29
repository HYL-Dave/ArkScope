# Query Route Harness Lifespan-Exposure Reduction Design

> **Status:** IMPLEMENTED - INDEPENDENT IMPLEMENTATION REVIEW NEXT
>
> **Date:** 2026-07-29
>
> **Product base:** `542776c2e00ae1737d5b424a3b8858b079a63e38`
>
> **Blocked caller:** price-collection partial-truth Task 0

## 1. Purpose

The price-collection partial-truth Task 0 could not establish its required
same-environment full-suite baseline. A full run stopped making progress for
more than 70 seconds at
`tests/test_agents.py::TestQueryEndpoint::test_providers_endpoint`; a bounded
single-node reproduction later exited `124` after 20 seconds at fixture setup.
An independent rerun of the same node subsequently passed in 2.59 seconds.

This is therefore not a claim that one deterministic application-lifespan
root cause has been found or repaired. This bounded harness slice does two
things only:

1. make the two `TestQueryEndpoint` route-unit nodes structurally independent
   of the full application's lifespan while preserving their HTTP contracts;
2. make any future full-suite stall emit all-thread diagnostics before the
   operator interrupts it.

The outcome reduces the full suite's exposure to ambient lifespan state. It
does not prove that the remaining five `with TestClient(...)` test families
cannot stall.

## 2. Grounded Facts

### 2.1 Current test shape

`tests/test_agents.py::TestQueryEndpoint` owns exactly two nodes:

```text
tests/test_agents.py::TestQueryEndpoint::test_providers_endpoint
tests/test_agents.py::TestQueryEndpoint::test_query_endpoint_bad_provider
```

Both currently depend on one class fixture that constructs the full app and
enters it through this equivalent two-line shape:

```python
app = create_app()
with TestClient(app) as client:
    ...
```

Entering that context runs the application lifespan before either route
assertion can execute. Verbose output from the bounded reproduction stopped at
fixture setup, not inside the `/query/providers` handler.

### 2.2 Route behavior does not require lifespan state

`GET /query/providers` is an `async def` handler. It performs SDK import
availability checks and returns a JSON object; it does not require a database,
provider request, scheduler, or startup resource.

`POST /query` is also an `async def` handler. The tested request uses provider
`unknown`, so the route must return HTTP `400` without invoking either model
provider. The handler currently resolves personalization before rejecting an
unknown provider, so a route-unit harness must replace that profile-store read
with a deterministic test stub rather than silently depending on ambient
profile state.

### 2.3 Existing repository precedent

`tests/test_sa_feed.py::test_route_returns_typed_200_for_every_unavailable_store_reason`
already uses a minimal `FastAPI` app, the real product router,
`httpx.ASGITransport`, and a synchronous pytest shell around `asyncio.run()`.
That pattern exercises real route registration, request parsing, HTTP status,
response serialization, and JSON without entering an application lifespan.

The SA test additionally patches `fastapi.routing.run_in_threadpool` because
its product handler is synchronous and this environment previously hung in an
AnyIO worker. This slice must not copy that patch: both query handlers and the
test DAL override are asynchronous and execute directly on the event loop.

### 2.4 Remaining lifespan users

Besides `tests/test_agents.py`, five test files currently use
`with TestClient(...)`:

```text
tests/test_api.py
tests/test_events.py
tests/test_signal_factors_p1.py
tests/test_portfolio_capture_routes.py
tests/test_portfolio_activity_routes.py
```

Some of those contracts may require startup behavior. There is no evidence in
this incident that authorizes changing them.

## 3. Decision

### 3.1 Replace only the two-node class harness

Keep the test file, class, and both method names byte-for-byte identical at
the node-identity level. Remove only the shared full-app `TestClient` fixture.

Each existing synchronous test must call a non-test helper that:

1. creates a minimal `FastAPI()` instance;
2. includes the real `src.api.routes.query.router`;
3. overrides `query.get_dal` with an async dependency returning a sentinel;
4. stubs `query._resolve_personalization` to return empty deterministic
   personalization for the unknown-provider request;
5. sends the real HTTP request with `httpx.ASGITransport` and
   `httpx.AsyncClient` inside `asyncio.run()`; and
6. closes the async client before returning the response to the synchronous
   test.

The helper name must not begin with `test_`. No bare async pytest test may be
introduced because this environment does not install `pytest_asyncio` and the
node ledger must remain unchanged.

This construction deliberately retains HTTP routing and serialization. A
handler-direct rewrite is rejected because it would no longer prove that
`GET /query/providers` and `POST /query` are registered or that FastAPI emits
the expected status and JSON response.

### 3.2 Preserve both existing contracts

`test_providers_endpoint` must continue to prove:

- HTTP status is `200`;
- the response has `providers`;
- `providers` contains both `openai` and `anthropic`.

`test_query_endpoint_bad_provider` must continue to prove:

- HTTP status is `400`;
- response `detail` contains `Unknown provider`.

No assertion may be dropped or weakened to make the harness conversion pass.

### 3.3 Full-suite diagnostics

After this micro-slice merges, the price-collection partial-truth branch must
rebase onto the merged product tip. Its implementation plan must then add:

```text
-o faulthandler_timeout=120
```

to exactly these two backend full-suite gates:

1. Task 0 Step 5, base non-passing-set capture;
2. Task 5 Step 3, tip non-passing-set capture.

Pytest's `faulthandler_timeout` emits all-thread stack traces after the stated
period; it does not terminate the process. The operator must still interrupt a
stalled run, preserve the dump and last active node, reject partial output as
an A/B baseline, and follow the existing stop condition.

The price plan's collection counts, node identities, expected deltas, and
predicted hashes do not change.

## 4. Accounting Contract

This slice has an exact backend node delta of `+0/-0`.

The complete normalized backend collection must remain:

```text
4722 nodes
SHA-256 fcdb1b7dc197c35d43684e7dde846ea82dc975ca6bb688162e88c5f312d43ff0
```

The before/after normalized node streams must be byte-identical. In
particular, both `TestQueryEndpoint` IDs in Section 2.1 must survive exactly
once. A helper accidentally collected as a test, a class/method rename, or a
new parametrization is a stop condition.

No frontend, resource, scanner, tool-count, or no-PG ledger changes.

## 5. Verification Contract

Implementation evidence must include:

1. the exact base and tip normalized backend collection hashes and an empty
   `comm` in both directions;
2. both existing query endpoint nodes passing together;
3. bounded repeated execution of both nodes without a stall;
4. a source-boundary check proving `TestQueryEndpoint` no longer imports or
   constructs `TestClient` or `create_app`, which is the structural proof that
   these two nodes no longer enter the full-app lifespan;
5. one completed backend full-suite run with
   `-o faulthandler_timeout=120`, or a fresh diagnostic stop with the emitted
   stack dump if another node stalls;
6. unchanged assertions for both HTTP contracts in Section 3.2; and
7. byte-identical protected files outside the single owned test file and
   authority documents.

A later passing run does not erase the recorded intermittent stall. Conversely,
the earlier stall is not evidence that every current full-suite run must hang.
Evidence must report the observed result without upgrading either direction.

## 6. Scope And Protected Boundaries

Owned implementation path:

```text
tests/test_agents.py
```

Owned authority paths:

```text
docs/superpowers/specs/2026-07-29-query-route-harness-termination-design.md
docs/superpowers/plans/2026-07-29-query-route-harness-termination.md
docs/superpowers/evidence/2026-07-29-query-route-harness-termination.md
docs/design/PROJECT_PRIORITY_MAP.md
```

Explicitly out of scope:

- all product code, including `src/api/app.py` and query handlers;
- `conftest.py` and global pytest configuration;
- the other five `with TestClient(...)` test families;
- changing app lifespan, scheduler, startup capture, Gateway, DNS, provider,
  database, or thread behavior;
- changing or excluding any full-suite node;
- weakening the price-truth A/B stop condition;
- adding an Engineering Issue Register entry; and
- the main-worktree drafts
  `docs/data/IBKR_PACING_AND_ERROR_SEMANTICS.md` and
  `docs/design/SCRIPTS_RETIREMENT_DECISION.md`.

The last two files must remain untracked, untouched, and outside this
worktree's implementation authority.

## 7. Ownership And Fallback

This micro-slice is the immediate owner of the reproduced harness incident,
so opening a duplicate EIR item would add a second owner and violate the
register boundary. The price-truth slice remains blocked until this owner is
implemented, independently reviewed, and merged, followed by its documented
rebase and plan amendment.

If this micro-slice is paused or abandoned before implementation, the incident
must then enter the Engineering Issue Register with the reproduction evidence,
an explicit harness owner, and a concrete revalidation trigger. It must not
become ownerless debt.

## 8. Integration Sequence

1. independently review this short design;
2. write and review a RED-first implementation plan;
3. implement only the two-node harness conversion on the isolated branch;
4. independently review the implementation and verification packet;
5. fast-forward `master` to the exact reviewed tip;
6. rebase `codex/price-collection-truth` onto merged `master`;
7. amend only its two full-suite commands and blocker-resolution status,
   then obtain focused plan confirmation; and
8. restart price-truth Task 0 from Step 1.

No price-collection product RED work begins until the restarted Task 0 in
Step 8 completes and authorizes it under the price-truth plan.
