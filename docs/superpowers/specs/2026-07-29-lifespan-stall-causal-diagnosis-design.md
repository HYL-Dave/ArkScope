# Full-Suite Lifespan Stall Causal Diagnosis Design

> **Status:** DRAFT - INDEPENDENT SPEC REVIEW NEXT
>
> **Date:** 2026-07-29
>
> **Diagnosis base:** `2edf12e11a8ff9299a9b65b900309c8ed218b717`
>
> **Blocked caller:** price-collection partial-truth Task 0 at
> `f7458727b8c7828e9372be29e7698b986e1db757`

## 1. Purpose And Product Boundary

The price-collection partial-truth line requires a terminating, reproducible
full-suite baseline before it may change product code. Its restarted Task 0
again stalled at the first remaining full-application lifespan entry,
`tests/test_api.py::TestHealth::test_status`.

This slice determines whether a known import-time side effect causally
contributes to that intermittent stall. It does not authorize a fix.

The goal is not merely a quieter test run. This design must:

1. preserve tests of real application startup and shutdown, which are
   user-relevant product behavior;
2. avoid hiding a startup defect by converting every `TestClient` test to a
   lifespan-free harness;
3. avoid retaining or deleting an SEC research capability merely because its
   dependency has an import-time side effect; and
4. restore a trustworthy gate for the price-truth fix, which addresses a live
   data-integrity problem.

This slice ends at a reproducible causal verdict plus raw evidence. A later
user-approved fix decision must separately consider the implicated seam, the
value of the affected capability, and the coverage consequences.

It does not pre-authorize an import move, another TestClient conversion,
lifespan or conftest changes, dependency changes, or SEC capability retirement.

## 2. Grounded Incident Facts

### 2.1 Observed blocking boundary

Three captured stall dumps, including the restarted price Task 0 run, share the
same relevant shape:

1. pytest waits in `TestClient.__enter__ ->
   BlockingPortal.start_task_soon -> _spawn_task_from_thread -> Future.result`;
2. the AnyIO portal thread is idle in its asyncio selector; and
3. a daemon thread named `PyrateLimiter's Leaker` runs a separate asyncio loop.

The portal has not completed the cross-thread spawn handshake, so the app
lifespan task has not yet been created in the observed dump. This locates the
stall but does not prove that the leaker thread caused it.

The event is intermittent. The same target later passed alone, and historical
full suites completed with this dependency installed. Neither a later pass nor
an earlier stall may erase the other observation.

### 2.2 The prior conversion moved, but did not solve, exposure

Before the query-route harness conversion, the full run stalled at
`tests/test_agents.py::TestQueryEndpoint::test_providers_endpoint`.

After conversion, both query nodes passed in full-suite context. The run then
stalled at `TestHealth::test_status`, the next untouched lifespan family. This
proves the bounded conversion removed that pair's exposure; it also proves that
converting lifespan tests one by one is not a causal diagnosis.

### 2.3 The immediately preceding node is a separate factor

This node passes immediately before the target:

```text
tests/test_api.py::test_fixed_task_runtime_routes_mount_on_real_app
```

It calls `create_app().routes` but does not enter lifespan. The experiment must
vary this real-app mount and SEC collection independently so its process-state
effect is not confused with the import effect.

## 3. Import And Capability Inventory

### 3.1 Known import-time effect

`data_sources/sec_filings.py` imports at module scope:

```python
from edgar import set_identity, Company
```

In the installed environment, bare `import edgar` immediately adds one daemon
`PyrateLimiter's Leaker` thread. The grounded chain is:

```text
edgar -> edgar.httpclient -> module HTTP manager
      -> httpxthrottlecache -> pyrate_limiter -> leaker thread
```

The import also initializes cache/HTTP machinery and patches
`HttpxThrottleCache` transport parameters. A local probe found no event-loop
policy or `asyncio.run` identity change. The experiment must initially name the
broader `edgar` import side effect, not assume the leaker is the mechanism.

Grounded package versions are:

```text
edgartools 5.0.2             httpxthrottlecache 0.3.0
pyrate-limiter 3.9.0         httpx 0.28.1
starlette 0.47.2             anyio 4.9.0
pytest 8.4.1
```

The three import-chain dependency directories have local installation
timestamps from 2025-12-12. That neither explains the 2026-07-28 onset nor
exonerates the import effect.

### 3.2 All repository import sites

There are two imports of `data_sources.sec_filings`:

1. `tests/test_sec_filings.py:19` imports `SECFilingsClient` at module scope.
   Its file-level skip does not prevent collection-time import.
2. `tests/test_sec_user_agent.py:44` imports the module inside the active
   canonical user-agent test. It runs after `tests/test_api.py` and before
   `tests/test_signal_factors_p1.py`.

Changing only the skipped test's import could therefore move the thread spawn
to the suite's middle rather than remove it.

No active `src/` runtime path imports `data_sources.sec_filings` or constructs
`SECFilingsClient`.

### 3.3 SEC capability is not binary

Current live SEC paths are independent of `SECFilingsClient`:

- the fundamentals route uses the DAL-backed
  `src/tools/analysis_tools.py::get_sec_filings`;
- the registered agent SEC tool lazily imports `sec_edgar_financials`; and
- the registered insider tool lazily imports `sec_insider_trades`.

`SECFilingsClient` separately advertises structured XBRL data, financial
statements, and parsed 10-K/10-Q sections such as business, risk factors, and
MD&A. Product documents express intent for SEC material, but this class has no
active runtime consumer.

The later product question is whether edgartools-backed filing-content parsing
belongs in the research workbench, not whether all SEC support stays or goes.
Test hygiene must not decide that question.

### 3.4 Lifespan coverage is product evidence

App lifespan applies provider configuration, migrates and reconciles profile
state, reconciles scheduler and portfolio state, owns enabled background tasks,
and clears DAL state at shutdown. The suite disables scheduler work and
redirects mutable profile, lock, macro, and SA paths, but the startup contract
remains meaningful.

These untouched lifespan families are protected:

```text
tests/test_api.py
tests/test_events.py
tests/test_portfolio_activity_routes.py
tests/test_portfolio_capture_routes.py
tests/test_signal_factors_p1.py
```

## 4. Hypotheses

- **H-A:** collecting `tests/test_sec_filings.py` changes the later stall
  outcome.
- **H-B:** running the real-app mount predecessor changes the outcome.
- **H-AB:** the two factors interact.
- **H-E:** the `edgar` import side effect is the relevant part of any H-A
  association.
- **H-O:** another ambient or machine-state factor dominates.

A verified stall without a factor proves that factor is not necessary for
every observed stall. A finite stall-free sample cannot prove a factor harmless
or prove that the incident has disappeared.

## 5. Phase 1: Two-Factor Minimal Pair

### 5.1 Matrix

Every trial is a fresh pytest subprocess. The fixed target is:

```text
tests/test_api.py::TestHealth::test_status
```

Factor A includes or omits collection of `tests/test_sec_filings.py` before the
target. Factor B includes or omits the mount predecessor.

| Cell | SEC collected | Mount executed | Collection identity |
|---|---:|---:|---|
| A0B0 | no | no | `1 / 4e385828ffa504640d8d50a65c2602fc9c6e06530d23127292bdab198ce3d71f` |
| A0B1 | no | yes | `2 / c5743e0d97cedb58531de047f90413f6284e33306d203df08620b4e4c2959cbc` |
| A1B0 | yes | no | `7 / a3af106460307042ae13af1a2b6759c34e25788102cee94b3115346a8afcb484` |
| A1B1 | yes | yes | `8 / 7d7b4d75fee81eb9305cb3651c7940e7ca87afe3539a198d5ec45eefea547644` |

The A1 count includes six skipped SEC nodes. Their collection/import effect is
intentional; Phase 2 removes the skipped-node confound.

### 5.2 Budget and order

The maximum is 20 trials per cell. Trials run in complete, counterbalanced
four-cell blocks using a deterministic schedule whose seed and SHA-256 are
recorded before results are read.

The implementation plan must pre-register exact early-truncation criteria.
Truncation may be evaluated only after 10 or 15 complete blocks and only when a
repeated separation already determines the next diagnostic stage. It may not:

- stop because no stall has occurred;
- upgrade finite observations into a universal claim;
- change criteria after results are visible; or
- hide mixed or invalid trials.

All other outcomes run to 20 blocks.

### 5.3 Hermetic execution

Every trial must:

1. run only in the isolated diagnosis worktree;
2. use a unique temporary root and fresh process;
3. set `ARKSCOPE_DISABLE_SCHEDULER=1`;
4. retain the suite's temporary DB/lock isolation;
5. direct `EDGAR_LOCAL_DATA_DIR` into the trial root;
6. begin with an empty worktree `data/` directory;
7. make no provider, Gateway, HTTP, browser, or production-DB call; and
8. preserve package and machine state across cells.

The isolated `/status` assertion may terminate with a missing-data failure. That
is not a stall and must not be "fixed" by mounting production data.

Each process uses `-o faulthandler_timeout=60`. Because faulthandler dumps but
does not terminate, an outer controller must preserve the dump and terminate
after a reviewed bound greater than 60 seconds.

Each trial receives one primary outcome:

```text
pass
terminated_nonstall_failure
stall_matching_portal_signature
timeout_without_expected_dump
invalid_trial
```

Only the matching portal signature enters causal counts. Invalid trials remain
in evidence and are replaced; they are not silently discarded.

### 5.4 Phase 1 interpretation

| Pattern | Permitted statement |
|---|---|
| Repeated A1 stalls with both A0 cells stall-free across B levels | SEC collection is an A-associated candidate |
| Repeated B1 stalls with both B0 cells stall-free across A levels | mount predecessor is a B-associated candidate |
| Repeated A1B1 stalls with the other three cells stall-free | A-by-B interaction is the candidate |
| Verified A0 or B0 stall | the absent factor is not necessary for every stall |
| Stalls in every cell without stable separation | neither factor isolates the event |
| No matching stalls | not reproduced in this bounded run; inconclusive |
| Invalid/nonmatching failures dominate | invalid or inconclusive |

Phase 1 reports raw counts, order, duration, and hashes. It may not name
`edgar`, pyrate-limiter, or the leaker as causal because A is an entire test
module.

## 6. Phase 2: Import-Only Control

### 6.1 SHA-pinned scratch plugin

One temporary pytest plugin outside the repository runs in both arms. An
environment flag controls only whether identical plugin bytes execute:

```python
import edgar
```

The plugin records thread names/identifiers before and after that conditional
import. The control must prove the plugin alone creates no target leaker; the
treatment must prove the expected import-time thread appears.

The plugin performs no HTTP request or behavior patch, writes only under the
trial root, never enters git, and is preserved in evidence by full source,
path, byte count, and SHA-256.

### 6.2 E-by-B matrix

Phase 2 replaces factor A with E:

- **E0:** plugin loaded, no `edgar` import;
- **E1:** identical plugin loaded, `edgar` imported.

Factor B, target, fresh-process rule, N=20 maximum, counterbalancing, timeout,
classification, and pre-registered truncation rules stay the same. The SEC
test file is absent from every Phase 2 cell.

Phase 2 runs even after a strong A result because it is required to isolate
`edgar`. It also runs if Phase 1 has no stalls as an independent direct probe.

Only repeated E1/E0 separation may support:

```text
The edgar import-time side effect is a causal contributor under the tested
process and predecessor conditions.
```

This still does not prove the leaker thread, rather than another import
mutation, is the mechanism. A bare-pyrate/leaker experiment is deferred to the
later fix gate, where it can inform seam selection without expanding this
diagnosis.

## 7. Conditional Machine-State Stage

If neither matrix isolates the event but matching stalls continue, a separately
reviewed diagnostic-plan amendment may inspect the AnyIO loop's thread,
wakeup-socket state, selector registrations, ready/scheduled queues, and
`asyncio.all_tasks(loop)` through a temporary observer.

The observer may not patch the portal, event loop, selector, lifespan, or
product. Its output is diagnosis only, never a passing baseline. Exact design
waits for the two matrix results and requires review before execution.

## 8. Verdict Contract

The evidence chooses one top-level verdict:

```text
V1 edgar_import_contributor_supported
V2 sec_collection_association_not_reduced_to_edgar
V3 mount_predecessor_contributor_supported
V4 sec_mount_interaction_supported
V5 tested_factor_not_necessary
V6 ambient_or_machine_state_dominates
V7 bounded_trials_did_not_reproduce
V8 experiment_invalid_or_inconclusive
```

Mixed facts remain visible as qualifiers. Raw observations are primary. The
packet must distinguish observation, controlled association, causal inference
under this harness, finite-sample uncertainty, and unmade product decisions.

No verdict means "the full suite is fixed." That requires a later reviewed fix
and a complete same-environment full-suite run.

## 9. Non-Binding Fix-Seam Inventory

This inventory gives the later decision coordinates but authorizes nothing.

| Candidate | Potential effect | Unresolved decision |
|---|---|---|
| Lazy `edgar` import at client construction or exact consuming method | removes import side effect from both import sites while retaining code | Is parsed filing content wanted, and what lifecycle owns it? |
| Move only the skipped test import | removes initial collection exposure | Active UA test still imports later; may only move the stall |
| Change the UA contract test import | removes/defer its exposure | Could weaken a real canonical-UA contract |
| Supported dependency shutdown | retains eager capability with explicit lifecycle | Does a public, reliable shutdown seam exist? |
| Dependency upgrade | may change lifecycle behavior | Needs changelog or measured evidence, not hope |
| Retire `SECFilingsClient` | removes an unconsumed integration | Requires a product decision on filing-content parsing and retained knowledge |
| App-owned SEC tool/service | exposes filing research with explicit lifecycle | New product work, not an incident hotfix |

The inventory must be refreshed before a fix spec. A newly found runtime
consumer stops a retirement proposal.

## 10. Product Fix Gate

Any later fix proposal must answer:

1. **Causal seam:** What did controlled evidence implicate or rule out?
2. **User value:** Does the workbench need parsed filings, structured SEC
   facts/metadata only, or neither?
3. **Coverage integrity:** Which real startup/shutdown behavior remains tested?
4. **Ownership:** If product code remains, who owns the side effect and its
   revalidation trigger?

The result may be a product lazy import, supported lifecycle fix, test
correction plus named product owner, or separate retirement. "Smallest diff" is
not sufficient until these product questions are answered.

## 11. Evidence And Accounting

The packet must include:

1. base, executable, OS/kernel, relevant package versions, and sanitized env;
2. all four Phase 1 collection streams/hashes;
3. pre-generated schedules and hashes;
4. one row per trial with phase/cell/order/time/duration/PID/exit/outcome and
   stdout/stderr hashes;
5. every faulthandler dump, including invalid/nonmatching trials;
6. Phase 2 plugin source/hash and both thread snapshots;
7. raw cell totals plus any exact early-truncation application;
8. proof of no production data, network, provider, Gateway, browser, or
   scheduler contact;
9. refreshed import-site and candidate-seam inventories;
10. one Section 8 verdict with explicit limits; and
11. a clean tracked worktree outside owned diagnosis docs.

The diagnosis-base collection remains:

```text
4722 nodes
SHA-256 fcdb1b7dc197c35d43684e7dde846ea82dc975ca6bb688162e88c5f312d43ff0
```

Bounded trials do not replace the blocked price line's full-suite baseline.

## 12. Scope, Stops, And Ownership

Owned tracked paths:

```text
docs/superpowers/specs/2026-07-29-lifespan-stall-causal-diagnosis-design.md
docs/superpowers/plans/2026-07-29-lifespan-stall-causal-diagnosis.md
docs/superpowers/evidence/2026-07-29-lifespan-stall-causal-diagnosis.md
docs/design/PROJECT_PRIORITY_MAP.md
```

Scratch controllers/plugins/logs live under a unique `/tmp` root and enter
tracked evidence only as content/hashes.

Protected:

- all product, test, conftest, and dependency files;
- the five lifespan families in Section 3.4;
- app/AnyIO/Starlette/httpx/event-loop behavior;
- package installation state;
- production data, browser profiles, Gateway, providers, and network;
- frozen price branch `f7458727`;
- untracked main-worktree drafts
  `docs/data/IBKR_PACING_AND_ERROR_SEMANTICS.md` and
  `docs/design/SCRIPTS_RETIREMENT_DECISION.md`; and
- merge, push, and price implementation.

Stop and amend the plan if:

1. production or external resources can be reached;
2. a collection identity differs;
3. Phase 2 arms use different plugin bytes;
4. the plugin control creates the target thread or treatment does not;
5. a timeout precedes the dump window;
6. artifacts cannot be attributed to one trial;
7. non-stall failures enter stall counts;
8. truncation criteria change after observation;
9. causality requires the deferred bare-leaker experiment;
10. continuation requires a product/test/dependency change;
11. a new runtime consumer changes the capability inventory; or
12. this work pauses without transfer to the Engineering Issue Register.

This micro-slice is the incident's sole owner. No duplicate EIR item is opened
while it proceeds. If paused or abandoned, the dumps, hypothesis status, owner,
and revalidation trigger must move into EIR.

## 13. Sequence

1. Independently review this design.
2. Write and review a bounded experiment plan.
3. Execute both matrices without tracked product/test changes.
4. Independently review evidence and verdict.
5. Ask the user to select the product/fix direction under Section 10.
6. Write, review, implement, and verify a separate fix or retirement spec.
7. Merge the exact reviewed fix.
8. Rebase the frozen price branch and restart Task 0 from Step 1.
9. Require a complete full-suite baseline before price product RED.

The diagnosis succeeds by making the next product decision truthful, not by
making a dashboard or test report look green.
