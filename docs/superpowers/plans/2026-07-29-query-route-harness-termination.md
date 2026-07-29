# Query Route Harness Lifespan-Exposure Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the two existing query-route HTTP contracts while removing
their structural dependency on the full application lifespan, with zero node
delta and diagnostic stack dumps for any future full-suite stall.

**Architecture:** Replace only `TestQueryEndpoint`'s full-app `TestClient`
fixture with a minimal `FastAPI` app containing the real query router and an
`httpx.ASGITransport` request helper. Keep synchronous pytest nodes by wrapping
the async transport in `asyncio.run()`, and use deterministic async dependency
and personalization stubs so the route-unit tests do not read ambient profile
state.

**Tech Stack:** Python 3.10, pytest 8, FastAPI, httpx 0.28.1,
`asyncio.run()`, Git normalized-node accounting.

---

> **Status:** IMPLEMENTED - INDEPENDENT IMPLEMENTATION REVIEW NEXT
>
> **Product base:** `542776c2e00ae1737d5b424a3b8858b079a63e38`
>
> **Approved spec tip:** `3216c1b9`
>
> **Branch:** `codex/query-harness-termination`
>
> **Worktree:** `/tmp/arkscope-query-harness-termination`

## 1. Scope And File Map

Implementation owner:

```text
tests/test_agents.py
```

Authority owners:

```text
docs/superpowers/specs/2026-07-29-query-route-harness-termination-design.md
docs/superpowers/plans/2026-07-29-query-route-harness-termination.md
docs/superpowers/evidence/2026-07-29-query-route-harness-termination.md
docs/design/PROJECT_PRIORITY_MAP.md
```

Responsibilities:

- `tests/test_agents.py` retains the two real HTTP route-unit contracts and
  owns the minimal lifespan-free ASGI harness.
- The design spec remains the behavior and scope authority.
- This plan owns execution order, exact code, accounting, and stop rules.
- The evidence packet records RED/GREEN, collection, full-suite, protected
  boundary, and integration results.
- The priority map remains the single active-work owner.

No product source, frontend, global pytest fixture/configuration, or other
`TestClient` family is modified.

## 2. Grounded Baseline And Accounting

The independently reviewed docs tip reproduces:

| Collection | Count | SHA-256 |
|---|---:|---|
| backend full | `4722` | `fcdb1b7dc197c35d43684e7dde846ea82dc975ca6bb688162e88c5f312d43ff0` |
| `tests/test_agents.py` | `31` | `78d7cdbebb60be09616fa13f3a8b85d42373fe46e4ac896d28d7c9900cf48f1e` |
| `TestQueryEndpoint` | `2` | `5e1e62ac3baf8d2d47558d3c43679ab4423cf6eb842e3c68edea447433adf4f7` |

The owned nodes are exactly:

```text
tests/test_agents.py::TestQueryEndpoint::test_providers_endpoint
tests/test_agents.py::TestQueryEndpoint::test_query_endpoint_bad_provider
```

Target accounting is exact `+0/-0`. All three collection counts and hashes
must remain byte-identical. No frontend/resource/scanner/tool/no-PG count
changes.

The old full-suite incident is intermittent. The base run stopped for more
than 70 seconds at the first owned node; a bounded single-node run exited
`124`; a later independent run passed in 2.59 seconds. Neither observation is
an allowlist or a universal claim.

## 3. Stop Conditions

Stop and amend the authority before continuing if any one occurs:

1. either owned node ID changes, disappears, or is collected more than once;
2. any helper is collected as a test or any node is added;
3. an existing HTTP assertion must be removed or weakened;
4. the minimal route harness cannot return the existing `200`/`400` contracts
   without product-code changes;
5. implementation needs `create_app`, `TestClient`, app lifespan, a real DAL,
   profile data, provider calls, Gateway, scheduler, browser, or production
   storage;
6. implementation needs the SA test's `run_in_threadpool` patch;
7. any product, frontend, `conftest.py`, pytest configuration, or other
   `with TestClient(...)` test family must change;
8. either main-worktree untracked document is copied, edited, staged, or used
   as authority;
9. the tip full suite stalls again at either owned node after the conversion;
10. a full-suite transcript is partial but is treated as a completed A/B
    baseline; or
11. a rebase conflict is resolved by dropping or rewriting either branch's
    independently reviewed decision-log history.

If a tip full suite stalls at a different node, wait for the 120-second stack
dump, interrupt it, preserve the complete dump and last node, and stop product
expansion. That is acceptable diagnostic evidence for this bounded slice but
does not authorize claiming that full-suite termination is globally fixed.

## 4. Task 0 - Reground After Plan Clearance

**Files:**
- Create: `docs/superpowers/evidence/2026-07-29-query-route-harness-termination.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [x] **Step 1: Record branch and clearance identity.**

  Run:

  ```bash
  git status --short --branch
  git rev-parse HEAD
  git merge-base --is-ancestor 542776c2 HEAD
  git diff --name-only 542776c2...HEAD
  ```

  Expected: branch `codex/query-harness-termination`; the product base is an
  ancestor; only the reviewed design, plan, and priority-map documents differ.
  Record the exact reviewed plan SHA as `PLAN_REVIEW_CLEARANCE_COMMIT` in the
  evidence packet before touching `tests/test_agents.py`.

- [x] **Step 2: Reconfirm worktree isolation.**

  Run:

  ```bash
  test "$(git rev-parse --show-toplevel)" = "/tmp/arkscope-query-harness-termination"
  test ! -e docs/data/IBKR_PACING_AND_ERROR_SEMANTICS.md
  test ! -e docs/design/SCRIPTS_RETIREMENT_DECISION.md
  test -z "$(find data -type f -print -quit 2>/dev/null)"
  git status --short
  ```

  Expected: neither main-worktree draft exists here, no isolated data file
  exists, and only reviewed authority documents differ.

- [x] **Step 3: Reproduce all three normalized collections.**

  Backend full:

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
    | sed -n '/^\(tests\|scripts\/testing\)\/.*::/p' \
    | LC_ALL=C sort \
    | tee /tmp/query-harness-base-full.nodes \
    | sha256sum
  wc -l /tmp/query-harness-base-full.nodes
  ```

  Agents file and owned nodes:

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
    tests/test_agents.py \
    | sed -n '/^tests\/.*::/p' \
    | LC_ALL=C sort \
    | tee /tmp/query-harness-base-agents.nodes \
    | sha256sum
  wc -l /tmp/query-harness-base-agents.nodes

  rg '^tests/test_agents.py::TestQueryEndpoint::' \
    /tmp/query-harness-base-agents.nodes \
    | LC_ALL=C sort \
    | tee /tmp/query-harness-base-owned.nodes \
    | sha256sum
  wc -l /tmp/query-harness-base-owned.nodes
  ```

  Expected: the exact counts and hashes in Section 2; each owned ID appears
  exactly once.

- [x] **Step 4: Observe the existing two-node runtime without using it as RED.**

  Run:

  ```bash
  timeout 30s /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_agents.py::TestQueryEndpoint::test_providers_endpoint \
    tests/test_agents.py::TestQueryEndpoint::test_query_endpoint_bad_provider
  ```

  Record either `2 passed` or timeout `124` as an observation. A pass is
  compatible with the known intermittent incident and does not satisfy the
  structural RED in Task 1.

- [x] **Step 5: Attempt one instrumented base full run.**

  Run in a controllable PTY:

  ```bash
  set -o pipefail
  PYTHONUNBUFFERED=1 /home/hyl/.virtualenvs/llm_app/bin/python -m pytest \
    -vv --tb=short -o faulthandler_timeout=120 \
    2>&1 | tee /tmp/query-harness-base-full.txt
  ```

  If it terminates, normalize and record the dated non-passing set:

  ```bash
  sed -n 's/^FAILED \([^ ]*::[^ ]*\).*/\1/p; s/^ERROR \([^ ]*::[^ ]*\).*/\1/p' \
    /tmp/query-harness-base-full.txt \
    | LC_ALL=C sort -u \
    | tee /tmp/query-harness-base-nonpassing.nodes \
    | sha256sum
  wc -l /tmp/query-harness-base-nonpassing.nodes
  tail -80 /tmp/query-harness-base-full.txt
  ```

  If it stalls, do not interrupt before the 120-second faulthandler dump.
  Then interrupt, preserve the dump and final active node, and record that no
  completed base non-passing set exists. Partial output is diagnostic only.

  After pytest has terminated, inspect only this worktree's ignored data
  directory:

  ```bash
  find data -type f -printf '%p %i %s %TY-%Tm-%TdT%TH:%TM:%TS\n' \
    2>/dev/null
  find data -type f -print0 2>/dev/null \
    | LC_ALL=C sort -z \
    | xargs -0 -r sha256sum
  ```

  If a test-created file exists, verify no pytest process remains, record its
  path/inode/size/hash, and move the entire ignored directory reversibly:

  ```bash
  test ! -e /tmp/query-harness-base-data
  mv data /tmp/query-harness-base-data
  mkdir data
  ```

  Never delete or compare it to production by basename alone. The absolute
  worktree path and inode establish that it is an isolated test artifact.

- [x] **Step 6: Create the initial evidence packet.**

  Create this exact structure:

  ```markdown
  # Query Route Harness Lifespan-Exposure Reduction Evidence

  > **Status:** TASK 0 GROUNDED - STRUCTURAL RED NEXT
  > **Product base:** `542776c2...`
  > **Plan-review clearance:** recorded from Task 0 Step 1

  ## 1. Scope And Authorities
  ## 2. Canonical Collections
  ## 3. Runtime Observations
  ## 4. Structural RED
  ## 5. GREEN And Repetition
  ## 6. Full-Suite Diagnostics
  ## 7. Protected Boundaries
  ## 8. Node Accounting
  ## 9. Integration
  ```

  Record exact commands, exits, counts, hashes, and whether the base full run
  terminated. Do not describe a later pass as disproving the incident.

- [x] **Step 7: Commit Task 0 docs only.**

  ```bash
  git add \
    docs/superpowers/evidence/2026-07-29-query-route-harness-termination.md \
    docs/design/PROJECT_PRIORITY_MAP.md
  git commit -m "docs: ground query harness termination slice"
  ```

  Expected: still no change to `tests/test_agents.py` or product code.

## 5. Task 1 - Structural RED And Minimal Harness Conversion

**Files:**
- Modify: `tests/test_agents.py:485-520`
- Modify: `docs/superpowers/evidence/2026-07-29-query-route-harness-termination.md`

- [x] **Step 1: Run the deterministic structural RED.**

  Run:

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python - <<'PY'
  from pathlib import Path

  source = Path("tests/test_agents.py").read_text(encoding="utf-8")
  owned = source.split(
      "# API Endpoint Tests (without actual LLM calls)", 1
  )[1].split("# Registry Integration Tests", 1)[0]
  for forbidden in ("TestClient", "create_app"):
      assert forbidden not in owned, (
          f"TestQueryEndpoint still enters the full-app harness via {forbidden}"
      )
  PY
  ```

  Expected: exit nonzero with
  `TestQueryEndpoint still enters the full-app harness via TestClient`.
  A SQLite, import, profile, provider, or timeout failure is the wrong RED and
  must be corrected at the test-command layer without editing product code.

- [x] **Step 2: Replace only the owned test harness with this exact code.**

  Replace the current `TestQueryEndpoint` fixture and methods with:

  ```python
  def _query_route_request(monkeypatch, method, path, **kwargs):
      import asyncio

      import httpx
      from fastapi import FastAPI

      from src.api.routes import query as query_routes

      app = FastAPI()
      app.include_router(query_routes.router)

      async def get_test_dal():
          return object()

      app.dependency_overrides[query_routes.get_dal] = get_test_dal
      monkeypatch.setattr(
          query_routes,
          "_resolve_personalization",
          lambda _assistant_stance: ("", {}),
      )

      async def request():
          transport = httpx.ASGITransport(app=app)
          async with httpx.AsyncClient(
              transport=transport,
              base_url="http://test",
          ) as client:
              return await client.request(method, path, **kwargs)

      return asyncio.run(request())


  class TestQueryEndpoint:
      def test_providers_endpoint(self, monkeypatch):
          """GET /query/providers returns provider info."""
          r = _query_route_request(monkeypatch, "GET", "/query/providers")
          assert r.status_code == 200
          data = r.json()
          assert "providers" in data
          assert "openai" in data["providers"]
          assert "anthropic" in data["providers"]

      def test_query_endpoint_bad_provider(self, monkeypatch):
          """POST /query with unknown provider returns 400."""
          r = _query_route_request(
              monkeypatch,
              "POST",
              "/query",
              json={"question": "Test", "provider": "unknown"},
          )
          assert r.status_code == 400
          assert "Unknown provider" in r.json()["detail"]
  ```

  Do not import `fastapi.routing`, patch `run_in_threadpool`, use a real DAL,
  or move imports into product code. Both handlers and the dependency override
  are async, so the SA sync-handler workaround is inapplicable.

- [x] **Step 3: Run the structural gate and the two owned nodes.**

  Run the strengthened structural gate:

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python - <<'PY'
  from pathlib import Path

  source = Path("tests/test_agents.py").read_text(encoding="utf-8")
  owned = source.split(
      "# API Endpoint Tests (without actual LLM calls)", 1
  )[1].split("# Registry Integration Tests", 1)[0]
  for forbidden in ("TestClient", "create_app", "run_in_threadpool"):
      assert forbidden not in owned, forbidden
  for required in (
      "httpx.ASGITransport",
      "app.include_router(query_routes.router)",
      "app.dependency_overrides[query_routes.get_dal]",
      '"_resolve_personalization"',
      "asyncio.run(request())",
  ):
      assert required in owned, required
  PY
  ```

  Expected: exit `0`. This proves the owned source region removed the full-app
  harness and retained the reviewed minimal transport shape.

  Then run:

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_agents.py::TestQueryEndpoint::test_providers_endpoint \
    tests/test_agents.py::TestQueryEndpoint::test_query_endpoint_bad_provider
  ```

  Expected: `2 passed`, retaining the exact `200`/provider-key and
  `400`/detail assertions.

- [x] **Step 4: Repeat the owned harness under one outer bound.**

  Run:

  ```bash
  timeout 120s bash -c '
    for attempt in $(seq 1 20); do
      /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
        tests/test_agents.py::TestQueryEndpoint::test_providers_endpoint \
        tests/test_agents.py::TestQueryEndpoint::test_query_endpoint_bad_provider \
        || exit 1
    done
  '
  ```

  Expected: exit `0`; twenty iterations, `40` total owned-node executions,
  every iteration `2 passed`. Timeout or any failure is a stop.

- [x] **Step 5: Reproduce byte-identical node accounting.**

  Run:

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
    | sed -n '/^\(tests\|scripts\/testing\)\/.*::/p' \
    | LC_ALL=C sort \
    | tee /tmp/query-harness-tip-full.nodes \
    | sha256sum
  wc -l /tmp/query-harness-tip-full.nodes

  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
    tests/test_agents.py \
    | sed -n '/^tests\/.*::/p' \
    | LC_ALL=C sort \
    | tee /tmp/query-harness-tip-agents.nodes \
    | sha256sum
  wc -l /tmp/query-harness-tip-agents.nodes

  rg '^tests/test_agents.py::TestQueryEndpoint::' \
    /tmp/query-harness-tip-agents.nodes \
    | LC_ALL=C sort \
    | tee /tmp/query-harness-tip-owned.nodes \
    | sha256sum
  wc -l /tmp/query-harness-tip-owned.nodes
  ```

  Compare all three streams:

  ```bash
  comm -3 \
    /tmp/query-harness-base-full.nodes \
    /tmp/query-harness-tip-full.nodes
  comm -3 \
    /tmp/query-harness-base-agents.nodes \
    /tmp/query-harness-tip-agents.nodes
  comm -3 \
    /tmp/query-harness-base-owned.nodes \
    /tmp/query-harness-tip-owned.nodes
  ```

  Expected: all three commands produce no output; counts and hashes remain
  exactly `4722/fcdb1b7d...`, `31/78d7cdbe...`, and `2/5e1e62ac...`.

- [x] **Step 6: Record GREEN and commit the test-only change.**

  Add the RED exit/message, exact diff, targeted result, repetition result,
  and three collection comparisons to the evidence packet. Run:

  ```bash
  git diff --check
  git diff --name-only HEAD
  git add tests/test_agents.py \
    docs/superpowers/evidence/2026-07-29-query-route-harness-termination.md
  git commit -m "test: isolate query routes from app lifespan"
  ```

  Expected changed files: only the owned test and evidence packet.

## 6. Task 2 - Full Verification And Protected Boundaries

**Files:**
- Modify: `docs/superpowers/evidence/2026-07-29-query-route-harness-termination.md`

- [x] **Step 1: Prove no product or adjacent harness change.**

  Run:

  ```bash
  git diff --quiet 3216c1b9..HEAD -- \
    src apps sql scripts data_sources extensions training
  git diff --quiet 3216c1b9..HEAD -- \
    conftest.py tests/conftest.py \
    tests/test_api.py \
    tests/test_events.py \
    tests/test_signal_factors_p1.py \
    tests/test_portfolio_capture_routes.py \
    tests/test_portfolio_activity_routes.py
  git diff --name-only 3216c1b9..HEAD
  ```

  Expected: both quiet commands exit `0`; only the one owned test and authority
  documents appear in the name list.

- [x] **Step 2: Run the final instrumented full suite.**

  Run in a controllable PTY:

  ```bash
  set -o pipefail
  PYTHONUNBUFFERED=1 /home/hyl/.virtualenvs/llm_app/bin/python -m pytest \
    -vv --tb=short -o faulthandler_timeout=120 \
    2>&1 | tee /tmp/query-harness-tip-full.txt
  ```

  If it terminates, normalize the result:

  ```bash
  sed -n 's/^FAILED \([^ ]*::[^ ]*\).*/\1/p; s/^ERROR \([^ ]*::[^ ]*\).*/\1/p' \
    /tmp/query-harness-tip-full.txt \
    | LC_ALL=C sort -u \
    | tee /tmp/query-harness-tip-nonpassing.nodes \
    | sha256sum
  wc -l /tmp/query-harness-tip-nonpassing.nodes
  tail -80 /tmp/query-harness-tip-full.txt
  ```

  If Task 0 obtained a complete base set, compare both directions:

  ```bash
  comm -13 \
    /tmp/query-harness-base-nonpassing.nodes \
    /tmp/query-harness-tip-nonpassing.nodes
  comm -23 \
    /tmp/query-harness-base-nonpassing.nodes \
    /tmp/query-harness-tip-nonpassing.nodes
  ```

  Expected when both runs completed in the same environment: no new or gone
  IDs. Absolute non-passing counts are dated observations, never an allowlist.

  If the tip stalls at either owned node, stop: the implementation failed its
  purpose. If it stalls elsewhere, wait for the 120-second dump, interrupt,
  preserve the dump and final node, and report that global termination remains
  unresolved without changing another test family.

  After pytest has terminated, inspect the ignored data directory:

  ```bash
  find data -type f -printf '%p %i %s %TY-%Tm-%TdT%TH:%TM:%TS\n' \
    2>/dev/null
  find data -type f -print0 2>/dev/null \
    | LC_ALL=C sort -z \
    | xargs -0 -r sha256sum
  ```

  If a test-created file exists, verify no pytest process remains, record its
  identity, and preserve it outside the worktree:

  ```bash
  test ! -e /tmp/query-harness-tip-data
  mv data /tmp/query-harness-tip-data
  mkdir data
  ```

  Expected before final source/focused gates: the worktree `data/` directory
  is empty. No production path is read, moved, or compared by basename.

- [x] **Step 3: Re-run final focused and source gates.**

  Run the complete structural gate from committed `HEAD`:

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python - <<'PY'
  from pathlib import Path

  source = Path("tests/test_agents.py").read_text(encoding="utf-8")
  owned = source.split(
      "# API Endpoint Tests (without actual LLM calls)", 1
  )[1].split("# Registry Integration Tests", 1)[0]
  for forbidden in ("TestClient", "create_app", "run_in_threadpool"):
      assert forbidden not in owned, forbidden
  for required in (
      "httpx.ASGITransport",
      "app.include_router(query_routes.router)",
      "app.dependency_overrides[query_routes.get_dal]",
      '"_resolve_personalization"',
      "asyncio.run(request())",
  ):
      assert required in owned, required
  PY
  ```

  Run both owned nodes and the bounded repetition:

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_agents.py::TestQueryEndpoint::test_providers_endpoint \
    tests/test_agents.py::TestQueryEndpoint::test_query_endpoint_bad_provider

  timeout 120s bash -c '
    for attempt in $(seq 1 20); do
      /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
        tests/test_agents.py::TestQueryEndpoint::test_providers_endpoint \
        tests/test_agents.py::TestQueryEndpoint::test_query_endpoint_bad_provider \
        || exit 1
    done
  '
  ```

  Recollect and compare all three node streams:

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
    | sed -n '/^\(tests\|scripts\/testing\)\/.*::/p' \
    | LC_ALL=C sort \
    | tee /tmp/query-harness-final-full.nodes \
    | sha256sum
  wc -l /tmp/query-harness-final-full.nodes

  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
    tests/test_agents.py \
    | sed -n '/^tests\/.*::/p' \
    | LC_ALL=C sort \
    | tee /tmp/query-harness-final-agents.nodes \
    | sha256sum
  wc -l /tmp/query-harness-final-agents.nodes

  rg '^tests/test_agents.py::TestQueryEndpoint::' \
    /tmp/query-harness-final-agents.nodes \
    | LC_ALL=C sort \
    | tee /tmp/query-harness-final-owned.nodes \
    | sha256sum
  wc -l /tmp/query-harness-final-owned.nodes

  comm -3 \
    /tmp/query-harness-base-full.nodes \
    /tmp/query-harness-final-full.nodes
  comm -3 \
    /tmp/query-harness-base-agents.nodes \
    /tmp/query-harness-final-agents.nodes
  comm -3 \
    /tmp/query-harness-base-owned.nodes \
    /tmp/query-harness-final-owned.nodes
  ```

  Expected: structural gate `0`, targeted `2 passed`, repeated `40/40`, and
  all three node streams byte-identical at the hashes in Section 2.

- [x] **Step 4: Record exact final evidence.**

  Record:

  - product base, plan clearance, and implementation commit;
  - structural RED and GREEN outputs;
  - the exact `tests/test_agents.py` diff;
  - targeted and repeated results;
  - all three node counts/hashes/comms;
  - base and tip full-suite outcome, including any stack dump;
  - protected-boundary commands and exits; and
  - confirmation that the two main-worktree drafts and production data were
    absent and untouched.

## 7. Task 3 - Review-Ready Closeout

**Files:**
- Modify: `docs/superpowers/specs/2026-07-29-query-route-harness-termination-design.md`
- Modify: `docs/superpowers/plans/2026-07-29-query-route-harness-termination.md`
- Modify: `docs/superpowers/evidence/2026-07-29-query-route-harness-termination.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [x] **Step 1: Set truthful review-ready statuses.**

  Set the spec and plan header to this exact value:

  ```text
  > **Status:** IMPLEMENTED - INDEPENDENT IMPLEMENTATION REVIEW NEXT
  ```

  Set the evidence header to:

  ```text
  > **Status:** REVIEW READY - INDEPENDENT IMPLEMENTATION REVIEW NEXT
  ```

  Summarize whether the full suite terminated and avoid claiming a
  deterministic ambient root-cause fix.

- [x] **Step 2: Add a newest-first priority-map entry.**

  Record exact node hashes, targeted/repetition results, full-suite outcome,
  protected boundaries, implementation commit, and the sole next gate:
  independent implementation review. Do not edit an older decision-log entry.

- [x] **Step 3: Commit closeout documents.**

  ```bash
  git diff --check
  git add \
    docs/design/PROJECT_PRIORITY_MAP.md \
    docs/superpowers/specs/2026-07-29-query-route-harness-termination-design.md \
    docs/superpowers/plans/2026-07-29-query-route-harness-termination.md \
    docs/superpowers/evidence/2026-07-29-query-route-harness-termination.md
  git commit -m "docs: record query harness verification"
  git status --short --branch
  ```

  Expected: clean branch. Stop for independent implementation review; do not
  merge or rebase the price-truth branch yet.

## 8. Task 4 - Reviewed Integration And Price-Truth Handoff

This task is authorized only after independent implementation review returns
GREEN and the user explicitly approves integration.

- [ ] **Step 1: Fast-forward the main worktree.**

  Run:

  ```bash
  git -C /mnt/md0/PycharmProjects/ArkScope status --short --branch
  git -C /mnt/md0/PycharmProjects/ArkScope rev-parse master
  git -C /mnt/md0/PycharmProjects/ArkScope rev-parse \
    codex/query-harness-termination
  git -C /mnt/md0/PycharmProjects/ArkScope merge --ff-only \
    codex/query-harness-termination
  ```

  Before merge, the main worktree may contain exactly the two user-owned
  untracked drafts and no tracked change. The branch SHA must equal the exact
  independently reviewed tip recorded in evidence. Do not stage either draft.

- [ ] **Step 2: Verify merged node and route contracts.**

  On merged `master`, run:

  ```bash
  cd /mnt/md0/PycharmProjects/ArkScope
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
    | sed -n '/^\(tests\|scripts\/testing\)\/.*::/p' \
    | LC_ALL=C sort \
    | tee /tmp/query-harness-merged-full.nodes \
    | sha256sum
  wc -l /tmp/query-harness-merged-full.nodes

  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
    tests/test_agents.py \
    | sed -n '/^tests\/.*::/p' \
    | LC_ALL=C sort \
    | tee /tmp/query-harness-merged-agents.nodes \
    | sha256sum
  wc -l /tmp/query-harness-merged-agents.nodes

  rg '^tests/test_agents.py::TestQueryEndpoint::' \
    /tmp/query-harness-merged-agents.nodes \
    | LC_ALL=C sort \
    | tee /tmp/query-harness-merged-owned.nodes \
    | sha256sum
  wc -l /tmp/query-harness-merged-owned.nodes

  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_agents.py::TestQueryEndpoint::test_providers_endpoint \
    tests/test_agents.py::TestQueryEndpoint::test_query_endpoint_bad_provider
  ```

  Expected: `4722`, `31`, `2`, all three reviewed hashes, and `2 passed`.

- [ ] **Step 3: Rebase the price-truth docs branch.**

  Run:

  ```bash
  git -C /tmp/arkscope-price-collection-truth status --short --branch
  git -C /tmp/arkscope-price-collection-truth rebase master
  ```

  Rebase `codex/price-collection-truth` onto merged `master`. If the
  newest-first priority-map insertions conflict, preserve both reviewed
  histories in chronological order and submit the resolved docs diff for
  focused review. Do not use a conflict resolution that drops either entry.

- [ ] **Step 4: Amend exactly the two price full-suite commands.**

  In
  `docs/superpowers/plans/2026-07-28-price-collection-partial-truth.md`, add:

  ```text
  -o faulthandler_timeout=120
  ```

  to Task 0 Step 5 and Task 5 Step 3 only. Record explicitly that it emits
  stacks but does not terminate pytest, update the Stop-11 resolution and
  blocker evidence status, and leave every count, node ID, delta, and predicted
  hash unchanged.

- [ ] **Step 5: Obtain focused plan confirmation and restart Task 0.**

  Commit the docs-only rebase/amendment:

  ```bash
  git -C /tmp/arkscope-price-collection-truth diff --check
  git -C /tmp/arkscope-price-collection-truth add \
    docs/design/PROJECT_PRIORITY_MAP.md \
    docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md \
    docs/superpowers/plans/2026-07-28-price-collection-partial-truth.md \
    docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md
  git -C /tmp/arkscope-price-collection-truth commit -m \
    "docs: resume price truth after harness isolation"
  ```

  Obtain independent focused review, then restart price-truth Task 0 from
  Step 1. Price product RED remains blocked until that restarted Task 0
  completes.
