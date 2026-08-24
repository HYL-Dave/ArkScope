# Tavily Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire every executable Tavily lifecycle and generic-agent surface while preserving manual evidence, Playwright browsing, hosted-search policy, generic compressor coverage, and the current production schema until its separately authorized migration.

**Architecture:** Remove Tavily at the product boundary first: no route, button, API client, registry entry, bridge wrapper, dispatcher, prompt, skill dependency, package import, or configuration reader remains. Keep the current `manual | tavily` SQLite CHECK only as dormant legacy storage authority so this stage can run against the already-migrated production database without DDL; a new explicit read-only preflight proves whether any legacy Tavily rows exist before Stage 2 rebuilds that schema. Split manual evidence into its own module and retarget generic compressor fixtures to the surviving `web_browse` tool rather than deleting unrelated coverage.

**Tech Stack:** Python 3.10, FastAPI, SQLite, pytest, React 19, TypeScript, Vitest, i18next, existing ArkScope ToolRegistry and agent bridges.

**Spec:** `docs/superpowers/specs/2026-08-24-trusted-lifecycle-automation-design.md`

## Global Constraints

- Base product tree is exactly `64af5092dd22523c672b8c42e3b84eaba04bec1f`; design amendments are `d77e24de` and `285a046a`.
- Work only in branch/worktree `security-lifecycle-automation` at `/tmp/arkscope-lifecycle-automation`.
- This stage makes zero provider/network calls and performs zero reads or writes against production databases.
- Do not read, print, edit, delete, or migrate `config/.env`; private `TAVILY_API_KEY` cleanup is user-owned.
- Do not merge, push, run a provider canary, or execute live migration/preflight under this plan.
- Preserve `web_browse`, `web_playwright`, `web_claude_search`, `web_openai_search`, and their existing provider-specific behavior.
- Preserve historical plans/specs and prior approval artifacts byte-for-byte. Update only current catalogs, current skill manifests, and the active priority map.
- Keep `RUN_ADAPTERS = {"manual", "tavily"}` in `src/security_lifecycle_schema.py` during this stage. It is exact legacy storage vocabulary, not an active adapter list. Stage 2 removes it under a live schema migration.
- Keep `GET /security-lifecycle/investigations/{run_id}` and run/evidence readers so any pre-existing history remains inspectable.
- Remove `POST /security-lifecycle/cases/{case_id}/investigations`; no compatibility alias, hidden fallback, or generic agent dispatch may recreate it.
- Generic tests that merely use a Tavily-shaped tool payload must be retargeted to `web_browse`; only tests of Tavily-specific behavior are removed.
- Expected mechanical inventories after this plan: 50 registry tools, 51 tools in each handwritten agent bridge, 184 runtime routes, lifecycle i18n subtree 194, Explore namespace 581, all-namespace leaf total 2080.
- Backend collection arithmetic is `4324 - 34 + 4 = 4294`; native execution is `4282 passed / 12 skipped` if no unrelated baseline changes occur. Frontend remains `104 files / 1220 tests` because the retired button node is replaced one-for-one by an absence/manual-path assertion.

---

## File Map

### New ownership

- `src/security_lifecycle_manual_evidence.py`: manual text/URL normalization and persistence only.
- `src/security_lifecycle_retirement.py`: explicit-path, read-only no-stored-Tavily preflight.
- `tests/test_security_lifecycle_manual_evidence.py`: manual evidence and URL-boundary coverage moved out of the retired search module.
- `tests/test_tavily_retirement.py`: storage preflight and no-default-path contract.

### Retired ownership

- `src/security_lifecycle_search.py`: lifecycle Tavily adapter, query planner, fetch normalization, and mixed manual helper.
- Tavily sections in `src/tools/web_tools.py`; the file remains the `web_browse` owner.
- Tavily schemas/wrappers/dispatch in `src/tools/registry.py`, `src/agents/anthropic_agent/tools.py`, and `src/agents/openai_agent/tools.py`.
- Lifecycle POST route and injected Tavily transport in `src/api/routes/security_lifecycle.py` and `src/api/dependencies.py`.
- Frontend request/button/copy in `apps/arkscope-web/src/api.ts`, `LifecycleView.tsx`, and both Explore resource files.
- Tavily-specific reducer and alias in `src/agents/shared/compressor/reducers.py` and `__init__.py`.

### Evolved ownership

- Exact count/inventory tests in `tests/test_api.py`, `tests/test_agents.py`, `tests/test_tools.py`, `tests/test_analyst_tools.py`, `tests/test_memory_tools.py`, `tests/test_sec_tools.py`, `tests/test_portfolio_tools.py`, `tests/test_sa_tools.py`, and `tests/test_web_tools.py`.
- Generic compressor tests/fixtures in `tests/test_compressor_*.py`, `tests/fixtures/p1_4_compressor/l1_minify_wrapped_json.json`, and `tests/replay_fixtures/p1_4_l0_overflow.json`.
- Subagent/prompt/config owners in `src/agents/shared/prompts.py`, `src/agents/shared/subagent.py`, `src/agents/config.py`, `config/user_profile.yaml`, `config/.env.template`, and `requirements.txt`.
- Current skill manifests under `resources/skills/**/SKILL.md` and current provider/tool/product catalogs under `docs/design/`.

## Test Identity Ledger

The 34 backend removals are feature-specific and closed:

- 11 nodes in `tests/test_security_lifecycle_search.py`: every node except `test_manual_adapter_adds_bounded_text_and_https_urls_with_zero_network`.
- 17 nodes in `tests/test_web_tools.py`: all four `TestDaysToTimeRange`, all eight `TestTavilySearch`, all three `TestTavilyFetch`, `TestBridgeIntegration::test_execute_tool_tavily_search`, and `TestConfigIntegration::test_config_disabling_tavily`.
- 5 nodes in `tests/test_compressor_reducers.py::TestTavilySearchReducer`.
- 1 node: `tests/test_security_lifecycle_routes.py::test_investigation_route_requires_one_explicit_attended_command`.

The manual-evidence node relocates one-for-one to the new manual test file and does not change collection. The four additions are:

```text
tests/test_tavily_retirement.py::test_preflight_requires_explicit_existing_profile_path_and_never_creates
tests/test_tavily_retirement.py::test_preflight_accepts_empty_legacy_storage_without_writes
tests/test_tavily_retirement.py::test_preflight_rejects_stored_tavily_runs_with_exact_counts
tests/test_tavily_retirement.py::test_preflight_rejects_stored_tavily_evidence_with_exact_counts
```

Any other removed node, new node, or unplanned failure is a stop requiring a plan amendment.

---

### Task 1: Add the Explicit No-Stored-Tavily Preflight

**Files:**
- Create: `src/security_lifecycle_retirement.py`
- Create: `tests/test_tavily_retirement.py`

**Interfaces:**
- Consumes: `verify_profile_connection(sqlite3.Connection)` from `src.security_lifecycle_schema`.
- Produces: `preflight_tavily_retirement(*, profile_path: str | Path) -> TavilyRetirementPreflight` and typed failures `TavilyRetirementUnavailable` / `TavilyRetirementBlocked`.

- [ ] **Step 1: Write the four failing preflight tests**

Use current `create_profile_schema()` to seed scratch databases. Assert the function signature has one keyword-only parameter with no default, a missing path stays absent, and empty storage preserves file bytes/inode/mtime. Seed a Tavily run and a Tavily evidence row separately and assert the exception carries both exact counts:

```python
with pytest.raises(TavilyRetirementBlocked) as caught:
    preflight_tavily_retirement(profile_path=path)
assert caught.value.code == "stored_tavily_rows_present"
assert caught.value.run_count == expected_runs
assert caught.value.evidence_count == expected_evidence
```

- [ ] **Step 2: Run the exact RED**

Run:

```bash
pytest -q tests/test_tavily_retirement.py
```

Expected: collection succeeds and all four nodes fail because `src.security_lifecycle_retirement` does not exist. No database outside pytest `tmp_path` is opened.

- [ ] **Step 3: Implement the read-only preflight**

Implement these exact public shapes:

```python
@dataclass(frozen=True)
class TavilyRetirementPreflight:
    profile_path: str
    tavily_run_count: int
    tavily_evidence_count: int
    storage_empty: bool

class TavilyRetirementUnavailable(RuntimeError):
    code = "tavily_retirement_preflight_unavailable"

class TavilyRetirementBlocked(RuntimeError):
    code = "stored_tavily_rows_present"
    def __init__(self, *, run_count: int, evidence_count: int):
        self.run_count = int(run_count)
        self.evidence_count = int(evidence_count)
        super().__init__(self.code)

def preflight_tavily_retirement(
    *, profile_path: str | Path
) -> TavilyRetirementPreflight:
    candidate = Path(profile_path)
    if not candidate.is_file():
        raise TavilyRetirementUnavailable(
            "tavily_retirement_preflight_unavailable"
        )
    connection = None
    try:
        connection = sqlite3.connect(
            f"{candidate.resolve().as_uri()}?mode=ro", uri=True
        )
        verify_profile_connection(connection)
        connection.execute("BEGIN")
        run_count = int(connection.execute(
            "SELECT COUNT(*) FROM security_lifecycle_investigation_runs "
            "WHERE adapter='tavily'"
        ).fetchone()[0])
        evidence_count = int(connection.execute(
            "SELECT COUNT(*) FROM security_lifecycle_evidence "
            "WHERE adapter='tavily'"
        ).fetchone()[0])
    except (OSError, sqlite3.Error, LifecycleSchemaMismatch) as exc:
        raise TavilyRetirementUnavailable(
            "tavily_retirement_preflight_unavailable"
        ) from exc
    finally:
        if connection is not None:
            connection.close()
    report = TavilyRetirementPreflight(
        profile_path=str(candidate.resolve()),
        tavily_run_count=run_count,
        tavily_evidence_count=evidence_count,
        storage_empty=(run_count == 0 and evidence_count == 0),
    )
    if not report.storage_empty:
        raise TavilyRetirementBlocked(
            run_count=run_count, evidence_count=evidence_count
        )
    return report
```

Open only `file:{resolved}?mode=ro`, call `verify_profile_connection`, begin a read transaction, count `adapter='tavily'` in `security_lifecycle_investigation_runs` and `security_lifecycle_evidence`, then close. Missing/unopenable/schema-mismatched inputs raise `TavilyRetirementUnavailable` without creating a file. Any nonzero count raises `TavilyRetirementBlocked`; no row content, URL, excerpt, or secret enters the exception.

- [ ] **Step 4: Run GREEN and prove no path default**

Run:

```bash
pytest -q tests/test_tavily_retirement.py
python -c "import inspect; from src.security_lifecycle_retirement import preflight_tavily_retirement as f; p=inspect.signature(f).parameters['profile_path']; assert p.default is inspect.Parameter.empty and p.kind is inspect.Parameter.KEYWORD_ONLY"
```

Expected: `4 passed`; the signature assertion exits 0.

- [ ] **Step 5: Commit**

```bash
git add src/security_lifecycle_retirement.py tests/test_tavily_retirement.py
git commit -m "feat: add Tavily retirement preflight"
```

---

### Task 2: Retire the Lifecycle Adapter and Preserve Manual Evidence

**Files:**
- Create: `src/security_lifecycle_manual_evidence.py`
- Create: `tests/test_security_lifecycle_manual_evidence.py`
- Delete: `src/security_lifecycle_search.py`
- Delete: `tests/test_security_lifecycle_search.py`
- Modify: `src/api/dependencies.py`
- Modify: `src/api/routes/security_lifecycle.py`
- Modify: `tests/test_security_lifecycle_routes.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `SecurityLifecycleInvestigationStore.add_evidence()` and current manual evidence schema.
- Produces: `canonical_manual_https_url(value: object) -> str` and `add_manual_evidence(*, store: SecurityLifecycleInvestigationStore, case_id: str, text: str | None, url: str | None, at: str, case_identity: Mapping[str, object] | None = None) -> str`; preserves `GET /security-lifecycle/investigations/{run_id}`.

- [ ] **Step 1: Evolve route and manual tests before product code**

Move the existing manual evidence node into the new test file and add these assertions to the exact route-surface owner:

```python
assert ("POST", "/security-lifecycle/cases/{case_id}/investigations") not in rows
assert ("GET", "/security-lifecycle/investigations/{run_id}") in rows
assert len(rows) == 184
```

Remove `_SearchAdapter` and search dependency overrides from the route fixture. Delete only the explicit investigation-route test. In the DB-write ordering test, remove the investigation POST and its three permission-count assertions; retain exact assertions for all six surviving write commands. In the source-missing test, keep assessment and acknowledgement as the two guarded attempts and require `[422, 422]`.

- [ ] **Step 2: Run the focused RED**

Run:

```bash
pytest -q tests/test_security_lifecycle_manual_evidence.py tests/test_security_lifecycle_routes.py tests/test_api.py
```

Expected failures: missing manual module, still-mounted investigation POST, and route count `185 != 184`. Surviving manual/assessment routes must not introduce unrelated failures.

- [ ] **Step 3: Split manual evidence and remove lifecycle search**

Move only these behaviors into `security_lifecycle_manual_evidence.py`:

```python
def canonical_manual_https_url(value: object) -> str:
    # HTTPS only; no credentials; reject localhost and non-global literal IPs;
    # normalize host/port/path/query and discard fragments.

def add_manual_evidence(
    *, store: SecurityLifecycleInvestigationStore, case_id: str,
    text: str | None, url: str | None, at: str,
    case_identity: Mapping[str, object] | None = None,
) -> str:
    # Exactly one of text/url; strip script/style and collapse whitespace;
    # text <= 16,000 chars; URL is validated but never fetched;
    # persist adapter="manual" and run_id=None.
```

Update the manual route import. Delete `InvestigationRequest`, the Tavily POST handler, `_LifecycleTavilyClient`, `_lifecycle_https_pool`, `_lifecycle_fetch_transport`, `get_security_lifecycle_search_adapter`, and `get_security_lifecycle_resolver`. Remove now-unused `socket`/urllib imports. Delete the retired search module after its one manual node is preserved.

- [ ] **Step 4: Run focused GREEN and exact route inventory**

Run:

```bash
pytest -q tests/test_security_lifecycle_manual_evidence.py tests/test_security_lifecycle_routes.py tests/test_api.py
python -c "from src.api.app import create_app; rows={(m,r.path) for r in create_app().routes for m in (r.methods or ()) if m not in {'HEAD','OPTIONS'}}; assert len(rows)==184 and ('POST','/security-lifecycle/cases/{case_id}/investigations') not in rows"
```

Expected: all pass; route count exactly 184.

- [ ] **Step 5: Commit**

```bash
git add src/security_lifecycle_manual_evidence.py src/security_lifecycle_search.py src/api/dependencies.py src/api/routes/security_lifecycle.py tests/test_security_lifecycle_manual_evidence.py tests/test_security_lifecycle_search.py tests/test_security_lifecycle_routes.py tests/test_api.py
git commit -m "refactor: retire lifecycle Tavily investigation"
```

---

### Task 3: Retire Generic Tavily Tools Across Every Live Registration Point

**Files:**
- Modify: `src/tools/web_tools.py`
- Modify: `src/tools/registry.py`
- Modify: `src/agents/anthropic_agent/tools.py`
- Modify: `src/agents/openai_agent/tools.py`
- Modify: `src/agents/config.py`
- Modify: `src/agents/shared/prompts.py`
- Modify: `src/agents/shared/subagent.py`
- Modify: `src/api/routes/config_routes.py`
- Modify: `docs/design/ARKSCOPE_TOOL_CATALOG.md` (live tool table only)
- Modify: `config/user_profile.yaml`
- Modify: `config/.env.template`
- Modify: `requirements.txt`
- Modify: `tests/test_web_tools.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_agents.py`
- Modify: `tests/test_subagent.py`
- Modify: `tests/test_tools.py`
- Modify: `tests/test_analyst_tools.py`
- Modify: `tests/test_memory_tools.py`
- Modify: `tests/test_sec_tools.py`
- Modify: `tests/test_portfolio_tools.py`
- Modify: `tests/test_sa_tools.py`

**Interfaces:**
- Consumes: surviving `web_browse()` and provider-native hosted-search flags.
- Produces: exact 50-tool registry and exact 51-tool Anthropic/OpenAI bridge inventories with no Tavily dispatch.

- [ ] **Step 1: Evolve exact inventories and remove feature-specific tests**

Delete the 17 closed Tavily nodes from `test_web_tools.py`. Evolve surviving bridge/registry tests to assert:

```python
assert "web_browse" in names
assert {"tavily_search", "tavily_fetch"}.isdisjoint(names)
assert len(registry.list_by_category("web")) == 1
assert not hasattr(AgentConfig(), "web_tavily")
```

Change every exact registry/schema count from 52 to 50 and each handwritten bridge count from 53 to 51. Remove Tavily names from `TestAnthropicToolSchemas.test_tool_names`. Evolve the subagent owner so every configured tool resolves and no config contains either retired name.

- [ ] **Step 2: Run the registration RED**

Run:

```bash
pytest -q tests/test_web_tools.py tests/test_api.py tests/test_agents.py tests/test_subagent.py tests/test_tools.py tests/test_analyst_tools.py tests/test_memory_tools.py tests/test_sec_tools.py tests/test_portfolio_tools.py tests/test_sa_tools.py
```

Expected: failures are confined to still-present Tavily symbols, old counts, stale subagent lists, and stale config attributes. A missing `web_browse` or hosted-search regression is not an admitted RED.

- [ ] **Step 3: Remove Tavily implementation and registrations**

In `web_tools.py`, retain only Playwright `web_browse`; remove `_tavily_client`, `_get_tavily_client`, `_days_to_time_range`, `web_search`, `web_fetch`, and unused imports. Rewrite its docstring and browser description without naming Tavily.

In the three registration owners:

- registry imports/registers only `web_browse` in category `web`;
- Anthropic schema and dispatch contain only `web_browse` for this local web module;
- OpenAI defines/appends only `tool_web_browse` from this local web module.

Remove `web_tavily` from `AgentConfig` and YAML loading. Remove the YAML toggle, `.env.template` key, config-status `data_keys.tavily`, and `tavily-python` requirement. Keep Claude/OpenAI hosted search and Playwright fields byte-for-byte except correcting adjacent comments that falsely describe Tavily as available.

Remove Tavily from subagent tool lists. Code analyst remains local/numerical; deep researcher uses internal news/SEC/fundamentals plus `web_browse` for a known URL; reviewer uses internal ticker news. Rewrite prompt instructions to prefer ArkScope structured tools and browse only a known URL, without claiming generic search exists.

Synchronize the Tool Catalog's live table in this task. The existing
`test_tool_catalog_live_table_matches_registry` owner is part of the Task 3
focused stream and requires the live table to change atomically with the
registry. Leave provider-retirement history and broader catalog prose to Task
6. This amendment follows a measured pre-implementation replay: after the
product edits, the original Task 3 stream produced `1 failed / 323 passed`,
with that catalog owner as the only failure.

- [ ] **Step 4: Run registration GREEN and inventory scripts**

Run:

```bash
pytest -q tests/test_web_tools.py tests/test_api.py tests/test_agents.py tests/test_subagent.py tests/test_tools.py tests/test_analyst_tools.py tests/test_memory_tools.py tests/test_sec_tools.py tests/test_portfolio_tools.py tests/test_sa_tools.py
python -c "from src.tools.registry import create_default_registry; r=create_default_registry(); assert len(r.list_all())==50; assert {t.name for t in r.list_by_category('web')}=={'web_browse'}"
python -c "from src.agents.anthropic_agent.tools import get_anthropic_tools; n={x['name'] for x in get_anthropic_tools()}; assert len(n)==51 and not n & {'tavily_search','tavily_fetch'}"
```

Also instantiate `create_openai_tools(DataAccessLayer())` and assert 51 unique names with neither retired tool.

- [ ] **Step 5: Commit**

```bash
git add src/tools/web_tools.py src/tools/registry.py src/agents src/api/routes/config_routes.py docs/design/ARKSCOPE_TOOL_CATALOG.md config/user_profile.yaml config/.env.template requirements.txt tests/test_web_tools.py tests/test_api.py tests/test_agents.py tests/test_subagent.py tests/test_tools.py tests/test_analyst_tools.py tests/test_memory_tools.py tests/test_sec_tools.py tests/test_portfolio_tools.py tests/test_sa_tools.py
git commit -m "refactor: retire generic Tavily tools"
```

---

### Task 4: Remove the Tavily-Specific Compressor Without Losing Generic Coverage

**Files:**
- Modify: `src/agents/shared/compressor/reducers.py`
- Modify: `src/agents/shared/compressor/__init__.py`
- Modify: `tests/test_compressor_reducers.py`
- Modify: `tests/test_compressor_layers.py`
- Modify: `tests/test_compressor_integration.py`
- Modify: `tests/test_compressor_observability.py`
- Modify: `tests/fixtures/p1_4_compressor/l1_minify_wrapped_json.json`
- Modify: `tests/replay_fixtures/p1_4_l0_overflow.json`

**Interfaces:**
- Consumes: `truncate_with_marker`, generic wrapped tool-result handling, and surviving tool name `web_browse`.
- Produces: unchanged generic compaction behavior with no Tavily-only reducer/export/alias.

- [ ] **Step 1: Evolve tests by semantic ownership**

Delete only `TestTavilySearchReducer` (five nodes). Evolve registry tests to assert `tavily_search` is absent and `web_browse` resolves to the default reducer. Replace incidental `tavily_search` fixture/tool names with `web_browse` in layer, integration, observability, minifier, and replay fixtures while preserving each payload size, wrapper shape, expected round trip, ordering, digest field, and overflow assertion.

Do not delete tests of Layer 0 overflow, Layer 1 minification, wrapper unwrapping, capture observability, or byte-perfect restore merely because their sample tool was Tavily.

- [ ] **Step 2: Run the compressor RED**

Run:

```bash
pytest -q tests/test_compressor_reducers.py tests/test_compressor_layers.py tests/test_compressor_integration.py tests/test_compressor_observability.py
```

Expected: failures identify the still-exported/registered Tavily reducer or stale fixture expectations; all generic `web_browse` paths must collect.

- [ ] **Step 3: Remove only the provider-specific reducer**

Delete `tavily_search_reducer`, the unused `web_result_reducer` compatibility alias, their `__init__.py` exports, and `_DEFAULT_REGISTRY["tavily_search"]`. Do not change `truncate_with_marker`, other reducer algorithms, thresholds, overflow storage, wrapper parsing, or replay contracts.

- [ ] **Step 4: Run compressor GREEN and fixture replay**

Run:

```bash
pytest -q tests/test_compressor_reducers.py tests/test_compressor_layers.py tests/test_compressor_integration.py tests/test_compressor_observability.py tests/test_replay.py
```

Expected: all pass; generic fixtures still execute rather than being removed.

- [ ] **Step 5: Commit**

```bash
git add src/agents/shared/compressor tests/test_compressor_reducers.py tests/test_compressor_layers.py tests/test_compressor_integration.py tests/test_compressor_observability.py tests/fixtures/p1_4_compressor/l1_minify_wrapped_json.json tests/replay_fixtures/p1_4_l0_overflow.json
git commit -m "refactor: remove Tavily compressor specialization"
```

---

### Task 5: Remove the Lifecycle Button, API Call, and Provider-Specific Copy

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx`
- Modify: `apps/arkscope-web/src/lifecycle/lifecyclePresentation.test.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/explore.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts`
- Modify: `apps/arkscope-web/src/i18n/resources.test.ts`

**Interfaces:**
- Consumes: surviving manual evidence POST and legacy run-history display.
- Produces: lifecycle drawer with no Tavily command and unchanged manual evidence/review actions.

- [ ] **Step 1: Evolve the visible behavior test**

Replace the explicit Tavily-click node one-for-one with a test that opens the drawer and asserts no Tavily label/button is present while both manual evidence commands remain reachable. Keep the existing mock API object free of a replacement search call.

Update i18n exact counts to:

```typescript
lifecycle: 194,
explore: 581,
// all namespaces
expect(total).toBe(2080);
```

Keep `credentialMissing` as a provider-neutral historical/future run label and change its copy to `Search credentials are not configured` / `尚未設定搜尋憑證`.

- [ ] **Step 2: Run the frontend RED**

Run:

```bash
npm --prefix apps/arkscope-web test -- --run src/lifecycle/LifecycleView.test.tsx src/lifecycle/lifecyclePresentation.test.ts src/i18n/resources.test.ts
```

Expected: the current Tavily button violates the absence assertion and old resource counts/copy fail. No unrelated lifecycle action may fail.

- [ ] **Step 3: Remove the request and UI surface**

Delete `startSecurityLifecycleInvestigation` from `api.ts`; remove its import, Search icon import, button, `busy === "search"` branch, and `actions.search/searching` resources. Keep run-history status/error rendering, manual text/URL controls, assessment acceptance, transition preview, and reverse controls.

- [ ] **Step 4: Run frontend GREEN, typecheck, scanner, and build**

Run:

```bash
npm --prefix apps/arkscope-web test -- --run
npm --prefix apps/arkscope-web run typecheck
npm --prefix apps/arkscope-web run check:i18n-literals
npm --prefix apps/arkscope-web run build
```

Expected: 104 files / 1220 tests, typecheck exit 0, literal scan exit 0 with no new debt, build exit 0. Existing bundle-size warning is informational only.

- [ ] **Step 5: Commit**

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/lifecycle apps/arkscope-web/src/i18n
git commit -m "refactor: remove Tavily lifecycle UI"
```

---

### Task 6: Retarget Current Skills and Catalogs

**Files:**
- Modify: nine Tavily-referencing `resources/skills/**/SKILL.md` files listed by `git grep`.
- Modify: `docs/design/AGENT_DATA_GAP_FALLBACK_PLAN.md`
- Modify: `docs/design/ARKSCOPE_PROVIDER_CATALOG.md`
- Modify: `docs/design/ARKSCOPE_TOOL_CATALOG.md`
- Modify: `docs/design/ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

**Interfaces:**
- Consumes: surviving registry names and the trusted lifecycle automation design.
- Produces: no current skill requires an absent tool and no current catalog claims Tavily is live/foundational.

- [ ] **Step 1: Adjust the existing packaged-skill validation owner**

Evolve `TestSkillRegistry.test_all_skills_have_required_fields` without adding a node: build `create_default_registry()`, require every packaged skill's `data_sources.required` name to resolve, and assert neither retired name appears in required or optional lists. Do not rely on `validate_skills()`, whose current empty-registry construction is outside this retirement scope.

- [ ] **Step 2: Retarget each skill by its existing internal data source**

Apply these exact replacements:

- earnings-prep, full-analysis, sector-rotation, earnings-analysis, idea-generation, comps-analysis, and dcf-model: remove `tavily_search`; retain their existing SEC/news/analyst/SA/price tools. The Task 6 RED also exposed the pre-existing required `get_iv_analysis` reference in earnings-prep after that tool was retired by `0c458aab`; replace that required source with the live `get_option_chain` tool so the packaged-skill invariant is truthful.
- catalyst-calendar: replace required `tavily_search` with `get_ticker_news` and describe local news as corroboration.
- competitive-analysis: replace required `tavily_search` with `get_peer_comparison` and `get_ticker_news`; keep fundamentals required.

Delete Tavily-specific workflow prose from those manifests rather than renaming a missing general-search tool.

- [ ] **Step 3: Correct current documentation without rewriting history**

Mark Tavily retired on 2026-08-24 in the provider catalog, remove its live tool rows from the tool catalog, remove claims that it is the product foundation, and point general-search follow-up to provider-neutral hosted adapters. Update the data-gap plan and workbench spec to say internal structured sources are primary and general search is optional/fallback. Update the active priority-map row/entry with the retired surface and exact counts.

Do not edit `docs/superpowers/plans/2026-08-19-security-lifecycle-investigation.md`, its ledgers, the 2026-08-19 design, `SLICE_7B3_SDK_DRIVER_DESIGN.md`, or other historical decision records.

- [ ] **Step 4: Run skill/catalog checks and the bounded grep**

Run:

```bash
pytest -q tests/test_skills.py
git grep -n -i tavily -- src apps config/.env.template config/user_profile.yaml requirements.txt resources
git grep -n 'TAVILY_API_KEY' -- src apps config/.env.template config/user_profile.yaml requirements.txt resources
```

Expected: the first grep is closed to three non-requesting ownership classes:

1. the dormant legacy storage authority in `src/security_lifecycle_schema.py`;
2. the explicit read-only retirement authority in
   `src/security_lifecycle_retirement.py`; and
3. UI tests that assert the retired name is absent.

No request client, route, tool, reducer, skill, configuration, resource copy, or
dependency may match. The second grep has no matches. Neither command may
inspect `config/.env`. This corrects the earlier impossible "schema only"
expectation, which conflicted with Task 1's required retirement API and Task 5's
required visible-absence assertions.

- [ ] **Step 5: Commit**

```bash
git add resources/skills docs/design tests/test_skills.py
git commit -m "docs: retire Tavily from current product contracts"
```

---

### Task 7: Mechanical Admission and Evidence Packet

**Files:**
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md` only if final measured identities differ from its staged entry.
- Create: `docs/superpowers/evidence/2026-08-24-tavily-retirement/` with text/JSON reports only; no database, secret, provider body, or environment dump.

**Interfaces:**
- Consumes: Tasks 1-6 commits.
- Produces: independently replayable offline evidence for Stage 1 review.

- [ ] **Step 1: Prove collection arithmetic**

Collect the full backend suite and compare node IDs to the base ledger. Required result is exactly 4294 nodes: 34 closed removals, four preflight additions, one manual node relocation, and no other identity drift.

- [ ] **Step 2: Run the complete backend twice without overlap**

Use separate basetemp directories and no concurrent pytest process:

```bash
pytest -q --basetemp=/tmp/arkscope-tavily-retirement-a
pytest -q --basetemp=/tmp/arkscope-tavily-retirement-b
```

Expected both times: `4282 passed, 12 skipped`, zero failures. The three existing `edgar.files.*` deprecation warnings may remain; no new warning is admitted.

- [ ] **Step 3: Run complete frontend and static gates**

```bash
npm --prefix apps/arkscope-web test -- --run
npm --prefix apps/arkscope-web run typecheck
node apps/arkscope-web/scripts/check-visible-literals.mjs
npm --prefix apps/arkscope-web run build
```

Expected: `104 files / 1220 tests`, then three zero exits.

- [ ] **Step 4: Verify runtime/tool/product absence**

Assert 184 routes, 50 registry tools, 51 tools in each bridge, one local web tool (`web_browse`), no lifecycle investigation POST, and no imports/attributes/functions named for Tavily outside dormant schema/history. Importing current product modules must not import the `tavily` package.

- [ ] **Step 5: Verify no unauthorized state or egress**

Compare git status and production database stat/hash metadata recorded before this plan's execution by the existing operator packet; no product test may open production paths. Confirm no provider-call receipt, live preflight report, migration report, `.env` diff, merge, or push exists.

- [ ] **Step 6: Write evidence and commit the closeout**

Store commands, exit codes, node-set diff, counts, route/tool inventories, grep output, and commit chain in the evidence directory. Update the active priority-map entry from staged to independently reviewable, then commit:

```bash
git add docs/design/PROJECT_PRIORITY_MAP.md docs/superpowers/evidence/2026-08-24-tavily-retirement
git commit -m "docs: close Tavily retirement admission"
```

Stop for focused review. Stage 2 evidence/fact schema work does not begin from a failed or unreviewed Stage 1 tip.
