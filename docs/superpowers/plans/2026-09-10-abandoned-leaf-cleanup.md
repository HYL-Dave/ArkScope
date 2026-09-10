# Abandoned Leaf Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Physically remove the first verified abandoned leaves without changing any active transport, data store or research capability.

**Architecture:** Delete executable residue and move tests to live behavior owners. The mechanical census supplies references and uncertainty, not automatic deletion approval. Coordinated old-SEC intake/web/schema removal follows this independently reviewable batch; the new SEC research service is a separate implementation.

**Tech Stack:** Python, pytest, existing provider transport fixtures, AST source checks and the maintenance census.

**Spec:** `docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/README.md` (C02, C07, C17-C19); `docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md` (removal/data-preservation boundary).

**Execution:** Task 1 committed as `300b7400`; Task 2 as `263c21a5`.
Both tasks and the final gates are complete, without merge or push. The full
backend selection and corrected-harness follow-up results are recorded separately in
`docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/leaf-cleanup.md`.

## Global Constraints

- Pre-release: remove abandoned execution, not a permanent `retired`/no-op wrapper.
- Preserve prices, news, SA records, credentials, profile configuration, memberships, receipts and research history. This plan has **zero DB DDL or row writes**.
- No provider calls, API keys, OAuth sessions, App restart, merge or push in this batch.
- Tests use temporary HOME/profile/market/SA/lock paths, disabled `.env` loading and external-network-denied execution. Loopback callback fixtures remain local tests, not provider calls. Do not use installed production state as a fixture.
- Keep the active EDGAR source/financials/insider-trades paths, exact auth matrix, bundled runtime admission and zero credential/model fallback.
- Do not delete untracked personal files, installed packages or historical evidence.
- Record each commit's removed tests and replacement owners; a lower test count is not unexplained success.

## Scope And Files

Task 1 deletes four leaves:

```text
data_sources/sec_filings.py                  C02 dormant edgartools module
data_sources/sec_earnings_releases.py        C18 unused parser/CLI
src/security_lifecycle_news_evidence.py      C17 retired acquisition adapter
src/news_identity_repair.py                 C19 unused standalone repair facade
```

`src/news_identity.py` remains the active identity planner/application owner.
`src/lifecycle_investigation/news.py::LocalNews` is the current local-news
search/read owner, injected by the investigation route/controller into the agent.
Its positive controls are `tests/test_lifecycle_investigation_news.py` and
`tests/test_lifecycle_investigation_agent.py`; no replacement local-news
implementation is needed.

Task 2 removes the auth factory's dead placeholder class/export/return branch,
not any driver. Other candidates remain in the priority-map cleanup workstream.

### Task 1: Delete Four Abandoned Leaves

**Files:**
- Create: `tests/test_abandoned_surface_cleanup.py`.
- Delete: the four paths in the scope table.
- Modify: `tests/test_sec_user_agent.py`, `tests/test_sec_transport.py`,
  `tests/test_security_lifecycle_news_evidence.py`, `tests/test_news_identity_repair.py`.
- Modify: `docs/design/ARKSCOPE_PROVIDER_CATALOG.md`, audit disposition/status.
- Positive controls: `tests/test_news_identity.py`, `tests/test_market_data_admin.py`,
  `tests/test_lifecycle_investigation_news.py`, `tests/test_lifecycle_investigation_agent.py`
  and the retained SEC transport tests.

**Interfaces:** No new product interface. Existing EDGAR and investigation
interfaces retain their signatures. The old acquisition facade and repair facade
cease to exist; no forwarding aliases replace them.

- [x] Add one separately named/parameterized absence owner per deleted file:

```python
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("relative", [
    "data_sources/sec_filings.py",
    "data_sources/sec_earnings_releases.py",
    "src/security_lifecycle_news_evidence.py",
    "src/news_identity_repair.py",
])
def test_abandoned_leaf_is_physically_absent(relative):
    assert not (ROOT / relative).exists(), f"abandoned leaf remains: {relative}"
```

- [x] Run `pytest -q tests/test_abandoned_surface_cleanup.py`. Expect **4 failed**,
  each naming its existing file. A collection/import failure is not accepted RED.
- [x] Delete the four product files. In `test_sec_clients_use_canonical_user_agent`,
  remove only imports/assertions of the two deleted SEC clients; preserve
  SECEdgarDataSource, SECEdgarFinancials and SECInsiderTrades identity checks.
  Remove deleted paths from the static transport list in `test_sec_transport.py`.
- [x] Replace `test_publisher_acquisition_adapter_is_retired_and_has_no_product_caller`
  with the new absence owner. Remove the old adapter-only extraction fixtures/tests;
  retain any design-supersession assertion that still governs current investigation.
  Remove standalone-facade-only tests from `test_news_identity_repair.py`, while
  keeping all active planner/collision/FTS/data-preservation tests in
  `test_news_identity.py` and administration tests.
- [x] Recheck source imports and literal dynamic module strings with the census.
  No runtime consumer may refer to a deleted path. Keep catalog entries for the
  active EDGAR source/financials/insider APIs; remove only dormant edgartools and
  earnings-parser connectivity claims. Do not advertise the new SEC tools yet.
- [x] Run the new four-case owner plus `test_sec_transport.py`,
  `test_sec_user_agent.py`, `test_news_identity.py`, `test_market_data_admin.py`
  plus both investigation news/agent test files in the isolated offline environment.
  Expect zero failures; capture the actual pass/skip count, not a guessed total.
- [x] Negative mutation: temporarily reintroduce each deleted path as a minimal
  module in the isolated worktree. Its named absence test must fail. Restore the
  cleaned state and rerun the four-case owner (4 passed).
- [x] Commit this batch alone, with removed-file/test counts and preserved owners.

### Task 2: Remove The Auth Factory Placeholder

**Files:**
- Modify: `src/auth_drivers/factory.py`, `src/auth_drivers/__init__.py`.
- Modify: `tests/test_auth_factory.py`, `tests/test_api_key_drivers.py`,
  `tests/test_abandoned_surface_cleanup.py`.
- Retained positive controls: real-driver and credential behavior in both auth
  test files, including factory wiring for both OAuth drivers. The API-key test
  file is not unchanged: its two placeholder imports/assertions must be replaced
  in the same commit as the class removal.

**Interfaces:** `build_driver` keeps every keyword and resolves the same valid
provider/auth pairs. Return annotation becomes the existing `AuthDriver`
protocol. Unsupported pairs still raise `ValueError`; a future unhandled admitted
pair raises an explicit internal error instead of creating a fake usable driver.

- [x] Add an AST-only owner that does not import the obsolete symbol:

```python
import ast

def test_factory_has_no_placeholder_class_or_export():
    tree = ast.parse((ROOT / "src/auth_drivers/factory.py").read_text())
    assert not any(isinstance(node, ast.ClassDef)
                   and node.name == "NotImplementedDriver" for node in ast.walk(tree))
    exported = (ROOT / "src/auth_drivers/__init__.py").read_text()
    assert "NotImplementedDriver" not in exported
```

- [x] Run that owner together with the new unhandled-admitted-mode behavior test;
  expect **2 failed**: the class assertion and the existing early `ValueError`
  instead of the required internal `RuntimeError`. Preserve the six existing
  real-driver cases and two wrong-provider OAuth negative cases.
- [x] Delete `NotImplementedDriver`, its export, `_MODE_SLICE`, old skeleton
  prose and the unreachable placeholder return. Import `AuthDriver` instead of
  placeholder-only request/response types. Derive the known-mode validation set
  from `_ALLOWED_MODES`, preserving unknown-mode versus wrong-provider errors:

```python
known_modes = frozenset().union(*_ALLOWED_MODES.values())
if auth_mode not in known_modes:
    raise ValueError(f"unknown auth_mode: {auth_mode!r} (expected one of {sorted(known_modes)})")
# Existing provider-specific check and real constructor branches stay in place.
# After those exhaustive branches:
raise RuntimeError(f"unhandled admitted driver: {provider}/{auth_mode}")
```

- [x] Remove placeholder imports in both auth test files. The purported
  placeholder-conformance test already exercises the real ChatGPT OAuth driver;
  rename it and retain its two protocol assertions. Change real-driver
  assertions from `not isinstance(..., NotImplementedDriver)` to exact expected
  real driver types. Keep credential identity, injected token store, runtime
  limits, unknown modes, cross-provider OAuth rejection and missing-token tests.
- [x] Run `pytest -q tests/test_auth_factory.py tests/test_api_key_drivers.py
  tests/test_abandoned_surface_cleanup.py` offline. Expect zero failures; the
  six real-driver and two wrong-provider cases must still be collected.
- [x] Mutate the allowed matrix to admit cross-provider OAuth: the existing
  wrong-provider tests must fail. Reintroduce an inert placeholder class: the new
  absence owner must fail. Restore and rerun the focused tests.
- [x] Commit independently from Task 1, with the actual test-count ledger.

## Final Gate And Next Work

- [x] Rerun the full mechanical census with `--compare` against the checked-in
  observation. Review removed paths, new candidates and coverage changes; never
  automatically accept a new baseline merely to turn the command green.
- [x] Run backend regression tests in the isolated/external-network-denied
  harness. Run frontend tests/typecheck/build if SEC catalog or tool-facing
  product code changes beyond the permitted leaves. No live-provider claim.
  Full selection: 7,939 passed / 12 skipped / two temporary-runner false refusals;
  corrected whole-file rerun: 29 passed; final combined focus: 186 passed.
  The two failed node IDs were both verified in the successful rerun. This is
  full selection plus targeted follow-up, not a second full-suite green run.
- [x] Independent review of runtime consumer absence, exact auth matrix,
  retained current tests, current documentation and deleted-test accounting.
- [x] Update C02/C07/C17-C19 individually to implemented only after these gates.

This plan does **not** authorize dropping `agent_queries` or other live-store
objects; executing historical migration/census CLIs; removing `MonitorScheduler`
without moving its explicit preservation contract; or deleting deferred density
analysis/Python execution. Those have separate named dispositions in the audit.
Next comes coordinated SEC source/settings/web removal and retained-data schema
cleanup, followed by the new three-tool SEC research service and portable store.
