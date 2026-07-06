# Scripts Runtime Consolidation Implementation Plan

> **Status: ✅ LIVE COMPLETE 2026-07-06.** FF-merged at `bde732d` (Tasks 1–5 + 4 reviewer
> amendment commits). Full A/B failure sets strictly identical (37=37; passed −6 = −14
> deleted / +8 added, fully accounted). Live cutover done: `host_script` re-pointed to
> `src/sa_native_host.py`, simulated host round-trip green, user Firefox Quick Refresh
> verified in `sa_capture.db` (`sa_refresh_meta` current 49+1 / closed 61+1). Scoping §5
> rewritten to final form with the survivor table. Closeout entry in map §10.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the ruled `scripts/` → `src/` consolidation: runtime never imports `scripts/`, every runnable app tool lives under `python -m src.*`, dead post-exit collectors are deleted with evidence, and `scripts/` retains ONLY app-unrelated/historical material. Zero residue: no compatibility wrappers, no tombstone scripts, no orphan stubs left at old locations.

**Architecture:** Four mechanical moves plus one deletion batch. The only live runtime→scripts coupling is the polygon/finnhub news collector pair (4 in-process import sites + 2 adapter tuples); everything else in `scripts/collection/` is dead-by-replacement or dead-by-precedence. `daily_update.py` is already the F6 thin CLI wrapper over `run_source()` — it only needs relocation. The smoke/audit harnesses and the SA native host are app-related tooling and move under `src/` per the finalized rule; the native host move carries an approval-gated OS manifest re-registration.

**Tech Stack:** Python 3, pytest, existing PG-unreachable smoke, Firefox native-messaging manifest (Task 5 only).

---

## Map Check / Authority

- User rulings 2026-07-06 (this thread): **D1** native host migrates but is sequenced AFTER the collector and daily_update moves; **D2** zero-residue — no wrappers survive a move, and app-related ops tooling (smoke/audit) also leaves `scripts/`; **D3** alphavantage/eodhd collectors retire now with a recorded backlog pointer (future Data Sources provider slice), delete>archive via git history.
- Standing rule being finalized: `PG_EXIT_REMAINDER_SCOPING.md` §5 ("Runtime imports `src/` only; subprocess targets are `python -m src.<module>`, never `scripts/*.py`") — this plan completes it and Task 6 rewrites §5 into its final form.
- Opening this multi-slice line adds a `PROJECT_PRIORITY_MAP.md` §10 plan-opened entry (committed with this plan).
- Protected boundaries unchanged: macro/SA capability locks, legacy `use_local_*` provenance keys, `scripts/huggingface`, `scripts/scoring`, `scripts/migration` (N9 gate evidence tooling), `scripts/p1_2` (macro lock §6.7).

**Out of scope:**

- No ingestion behavior change: collectors move verbatim (module relocation + import mechanics only); cadence, budgets, locking, telemetry untouched.
- No alphavantage/eodhd Data Sources provider implementation (backlog note only).
- No native-messaging host-id change (`com.mindfulrl.sa_alpha_picks` stays — locked naming).
- No touching `data_sources/` (the provider layer stays where it is by rule).

## Decisions Locked

1. **Zero residue.** A moved module's old path is DELETED in the same task. The existing S-A1 compatibility wrapper (`collect_ibkr_news_normalized.py`) retires in Task 1 — its own docstring already schedules this.
2. **Final `scripts/` semantics (Task 6 writes this into scoping §5):** `scripts/` holds only app-unrelated or historical material. `src/` never imports `scripts/`. Anything runnable that the app, its gates, or its operators depend on is `python -m src.<module>`.
3. **Collector destination:** `src/collectors/` package — `src/collectors/polygon_news.py`, `src/collectors/finnhub_news.py`. Contents move verbatim except: drop the script-mode `sys.path` shims (`collect_polygon_news.py:654-655`, `collect_finnhub_news.py:478-479`) — inside `src/` the package import is guaranteed; keep `load_env()` and all public names so callers only change the module path.
4. **`d.collector` plumbing is dead-by-precedence, remove it whole.** `ibkr_news` carries `["collect_ibkr_news.py", "--incremental"]` positionally (`data_scheduler.py:142`) but its `news_direct_source="ibkr"` branch runs FIRST; `iv_history` (`:161`) fails closed at the N9 retirement error before provider work. Task 1 removes: the two positional list args, the `SourceDef.collector` field, `_COLLECT_DIR` (`:69`), the `elif d.collector is not None:` subprocess branch (`:1204-1214`), and fixes the one live display consumer: `status_snapshot`'s `provider_fetch` (`:1468`) becomes `(d.adapter is not None) or (d.news_direct_source is not None) or d.prices_worker`-shaped truth (match the real fetch paths; pin with a test).
5. **Deleted tests are accounted, not hidden.** Retiring tombstones/wrappers deletes their pinned tests (migrate refusal tests, wrapper delegation test). These tests PASS on base, so the full A/B failure sets must stay IDENTICAL; only the passed count drops. The plan names every deleted test; any base-failure-set change blocks merge.
6. **av/eodhd backlog pointer:** the Task 6 map entry records "future Data Sources provider slice: alphavantage + eodhd (FieldDefs + connection test + health + ingestion); reference implementations recoverable at the pre-deletion commit recorded in the closeout." No dead code kept as "reference".
7. **Native host manifest step is approval-gated.** Repo changes (move + tests) are normal TDD; the machine-level Firefox native-messaging manifest re-point is a live operator step: dry-run (print current manifest path + content) → explicit user approval → update → user verifies the extension round-trip.
8. **Historical docs are not rewritten.** Design docs that cite `python -m scripts.smoke.pg_unreachable_e2e` as *what was run at the time* stay as-is; only standing/gate references (docs that tell you what to run NEXT time) are updated to the new module paths.

## Stop-Loss Triggers

Stop and report before continuing if any of these happen:

- A grep shows a LIVE (non-test, non-docstring) consumer of any file scheduled for deletion.
- Moving a collector requires changing its behavior (anything beyond module path / shim removal) to keep tests green.
- `provider_fetch` display semantics cannot be reproduced without the `collector` field (UI contract ambiguity → ask).
- The native host manifest points at something unexpected (a packaged launcher, multiple manifests, or a non-repo path).
- Any full A/B head-only deterministic failure, or any base-only entry beyond "test file deleted in this plan".

## Review Gates

1. `rg -n "from scripts\.|import scripts\." src/` returns ZERO hits (the rule's core, machine-checkable).
2. `rg -n "scripts\.collection|scripts/collection" src/ tests/` returns zero hits; `scripts/collection/` directory no longer exists.
3. `pytest tests/test_news_providers.py tests/test_collector_adapters.py tests/test_collector_load_env.py tests/test_news_direct.py tests/test_news_normalized_provider_adapters.py tests/test_data_scheduler.py tests/test_normalized_ibkr_worker.py tests/test_daily_update_wrapper.py -q` passes.
4. `pytest tests/test_pg_unreachable_e2e.py tests/test_ibkr_news_catchup_audit.py -q` passes with the new `src.smoke`/`src.audit` module paths; `python -m src.smoke.pg_unreachable_e2e` runs green (`ok:true`, `pg_attempts:[]`).
5. Native host: the offline `handle_message({"action": "ping"})` pin passes from `src.sa_native_host`; manifest re-point is user-verified with a real extension message round-trip (approval-gated).
6. Full A/B: failure sets identical; passed count may DROP by exactly the named deleted tests; zero head-only deterministic failures.
7. Scoping §5 contains the finalized rule; map §10 has the closeout entry with the pre-deletion sha.

---

## Task 1: Dead Retirement Batch

**Files:** deletions + `src/service/data_scheduler.py`, `src/universe_scope.py`, `src/tools/db_config.py`, `src/market_data_admin.py` (docstring mentions), affected tests.

**Deletion inventory (each with its reference disposition):**

| File | References found | Action |
|---|---|---|
| `scripts/collection/collect_ibkr_news.py` (48KB) | `data_scheduler.py:142` positional collector arg; negative test assertions | delete file + remove plumbing (Decision 4) |
| `scripts/collection/collect_ibkr_prices.py` (39KB) | one negative assertion (`test_data_scheduler.py:1958`) | delete; keep/simplify the negative assertion |
| `scripts/collection/collect_iv_history.py` | `data_scheduler.py:161` positional arg | delete + plumbing removal |
| `scripts/collection/collect_all_news.py` | none | delete |
| `scripts/collection/collect_ibkr_fundamentals.py` | `universe_scope.py:14` docstring mention | delete + docstring line update |
| `scripts/collection/collect_alphavantage_news.py` | `universe_scope.py:14` docstring | delete + docstring + backlog note (Decision 6) |
| `scripts/collection/collect_eodhd_news.py` | same | same |
| `scripts/collection/collect_ibkr_news_normalized.py` (S-A1 wrapper) | delegation test `test_normalized_ibkr_worker.py:265`; 3 negative assertions in `test_data_scheduler.py:1062/1122/1182` | delete file + delete the delegation test; keep the negative assertions (they now pin "never referenced at all") |
| `scripts/migrate_to_supabase.py` (tombstone) | EIGHT consumer files — full dispositions: `db_config.py:5` docstring (reword); `tests/test_news_identity.py:70-75` `test_direct_and_migration_share_the_same_hash_function` imports it to prove hash identity → rewrite to assert `src.news_providers.canonical_article_hash is src.news_identity.canonical_article_hash` only (migration compatibility is dead); `tests/test_news_direct.py:81` `from scripts.migrate_to_supabase import article_hash as canonical` → `from src.news_identity import canonical_article_hash`; `tests/test_news_scores.py` `TestMigrateDetectScoreColumns` (:156) = duplicate of the FileBackend `detect_score_columns` tests earlier in the same file → DELETE, and `TestMigrateScoresArchiveGate` (:178) = tombstone/refusal family → DELETE whole class (+ fix the file docstring `:3`); refusal pins in `test_db_backend.py`, `test_news_direct.py`, `test_daily_update_wrapper.py`, `test_n9_batch1_pg_drop.py` → DELETE (name each in the commit message); `tests/test_data_scheduler.py:100/:113/:1124` are NEGATIVE pins (assert the script is NOT referenced) → KEEP unchanged | delete file + the dispositions above |
| `scripts/migrate_sa_to_sqlite.py` (tombstone) | `test_sa_routing.py::test_migration_cli_permanently_refuses_pg_paths` | delete + delete that test |
| `scripts/migrate_market_to_sqlite.py` | `market_data_admin.py:22` docstring | delete + docstring |
| `scripts/sa_pg_freeze.py`, `scripts/monitor_service.py`, `scripts/token_usage_summary.py`, `scripts/patch_model_metadata.py`, `scripts/replay_run.py` | zero live refs (replay_run: docstring mention in `src/agents/shared/replay.py`) | delete + docstring fix |

- [ ] **Step 1: Per-file liveness proof.** For each file above run `rg -n "<basename-without-ext>" src/ tests/ scripts/ apps/` and record the FULL hit list — NEVER pipe inventory greps through `head`/`tail` (a truncated list read as complete is exactly how this plan's first draft missed three `migrate_to_supabase` consumers). A LIVE hit not in this table = stop-loss.
- [ ] **Step 2: RED — collector-plumbing removal pins.** Add to `tests/test_data_scheduler.py`: (a) `SOURCES` defines no `collector` anywhere (attribute gone); (b) `status_snapshot()` still reports `provider_fetch` True for `polygon_news`/`finnhub_news`/`ibkr_news`/`ibkr_prices` and False for a non-fetch source, using the new expression. Expected RED: `SourceDef` still has the field.
- [ ] **Step 3: Implement deletions + plumbing removal + docstring touch-ups.** Remove `_COLLECT_DIR`, the `:1204` branch, the `collector` field and both positional args; fix `provider_fetch` per Decision 4.
- [ ] **Step 4: Delete the named obsolete tests** (migrate refusal family + wrapper delegation) and run the affected files to green.
- [ ] **Step 5: Gates.** `pytest tests/test_data_scheduler.py tests/test_normalized_ibkr_worker.py tests/test_sa_routing.py tests/test_db_backend.py tests/test_news_direct.py tests/test_news_identity.py tests/test_news_scores.py tests/test_daily_update_wrapper.py tests/test_n9_batch1_pg_drop.py -q` → PASS. Commit: `refactor: retire dead collection and migration scripts`.

## Task 2: Polygon/Finnhub Collectors → `src/collectors/`

**Files:** Add `src/collectors/__init__.py`, `src/collectors/polygon_news.py`, `src/collectors/finnhub_news.py`; modify `src/news_providers.py`, `src/service/data_scheduler.py`; delete the two `scripts/collection/collect_*_news.py`; update the 8 test files importing `scripts.collection` (`test_news_providers.py`, `test_collector_adapters.py`, `test_collector_load_env.py`, `test_news_direct.py`, `test_news_normalized_provider_adapters.py`, `test_data_scheduler.py`, `test_normalized_ibkr_worker.py`, `test_n9_batch1_pg_drop.py`).

- [ ] **Step 1: RED — new module paths.** Write a small import-contract test: `src.collectors.polygon_news` exposes `CollectionConfig`, `PolygonNewsCollector`, `load_env`, `run_incremental`; same for finnhub (`FinnhubConfig`, `FinnhubNewsCollector`). Expected RED: modules don't exist.
- [ ] **Step 2: Move verbatim.** `git mv` the two files into `src/collectors/` (new names per Decision 3); remove ONLY the script-mode `sys.path` shims; do not reformat, do not rename symbols.
- [ ] **Step 3: Rewire runtime.** `news_providers.py:132/136` and `data_scheduler.py:325/337` import from `src.collectors.*`; adapter tuples `:125/:134` become `("src.collectors.polygon_news", "run_incremental")` / finnhub equivalent.
- [ ] **Step 4: Rewire tests.** Update the 8 named files' imports/monkeypatch strings (`"scripts.collection.collect_polygon_news"` → `"src.collectors.polygon_news"` etc.). Do not weaken any assertion.
- [ ] **Step 5: `scripts/collection/` residuals.** `DATA_DICTIONARY.md`: move to `docs/data/` if its content is still-true schema documentation, else delete. `README.md`: delete (superseded HOW). Directory itself removed in Task 3 after daily_update leaves.
- [ ] **Step 6: Gates.** Review Gate 1 grep must be zero for the news modules; run Gate 3's suite list → PASS. Commit: `refactor: move news collectors into src`.

## Task 3: `daily_update` → `python -m src.daily_update`

**Files:** move `scripts/collection/daily_update.py` → `src/daily_update.py`; update `tests/test_daily_update_wrapper.py` (it invokes the script subprocess-style by PATH — switch to `python -m src.daily_update`); delete old file; remove the now-empty `scripts/collection/` directory.

- [ ] **Step 1: RED.** Flip the wrapper test's invocation to the module path; expected RED: module missing.
- [ ] **Step 2: Move.** Keep CLI flags, `run_source` delegation, per-source flock behavior, and `daily_update.*` job-run aliases byte-identical; adjust only its internal repo-root/sys.path assumptions if any.
- [ ] **Step 3: Gates.** `pytest tests/test_daily_update_wrapper.py tests/test_job_runs.py -q` → PASS; `scripts/collection/` no longer exists (Gate 2). Commit: `refactor: move daily update cli into src`.

## Task 4: Smoke + Audit Harnesses → `src/smoke/`, `src/audit/`

**Files:** move `scripts/smoke/pg_unreachable_e2e.py` → `src/smoke/pg_unreachable_e2e.py`, `scripts/audit/ibkr_news_catchup_audit.py` → `src/audit/ibkr_news_catchup_audit.py` (+ `__init__.py`s); update `tests/test_pg_unreachable_e2e.py`, `tests/test_ibkr_news_catchup_audit.py`; delete `scripts/smoke/`, `scripts/audit/`.

- [ ] **Step 1: RED.** Flip both test files' imports to the `src.` paths; expected RED.
- [ ] **Step 2: Move.** `_bootstrap_repo_root` uses `parents[2]` — depth is identical under `src/smoke/`, verify by running the module once; the audit module has no path shim. The smoke's static no-Gateway/no-write tests in the audit suite must keep passing against the new source path.
- [ ] **Step 3: Standing references only.** Update live gate references (any doc/plan that instructs FUTURE runs, e.g. an active runbook line) to `python -m src.smoke.pg_unreachable_e2e`; historical PG-exit design docs stay untouched (Decision 8).
- [ ] **Step 4: Gates.** Gate 4 (tests + one live smoke run green from the new path). Commit: `refactor: move smoke and audit harnesses into src`.

## Task 5: SA Native Host → `python -m src.sa_native_host` (approval-gated live step)

**Files:** move `scripts/sa_native_host.py` → `src/sa_native_host.py`; update its `PROJECT_ROOT` bootstrap (`sys.path.insert` at `:28`) to the src-relative depth or drop it if module-run guarantees imports; tests if any reference the path.

- [ ] **Step 1: Repo move + RED/GREEN with a concrete offline pin.** Standard TDD on any existing native-host tests, PLUS a new offline test that imports `src.sa_native_host` and calls `handle_message({"action": "ping"})` directly (the handler exists — `handle_message` at the current `:60`, ping branch at `:118`), asserting the pong response shape; optionally also drive one length-prefixed stdin ping through the framing loop. This pins "the host works from the new location" WITHOUT the manifest; the real extension round-trip stays in the approval gate (Step 4). Keep the host protocol, logging path, and host id `com.mindfulrl.sa_alpha_picks` byte-identical.
- [ ] **Step 2: Manifest dry-run (read-only).** Locate the Firefox native-messaging manifest (expected under `~/.mozilla/native-messaging-hosts/com.mindfulrl.sa_alpha_picks.json`); print its current `path` and content. If it points at anything unexpected → stop-loss.
- [ ] **Step 3: APPROVAL CHECKPOINT.** Present the exact manifest edit (old path → new launcher invoking `python -m src.sa_native_host`) and wait for explicit user approval. Do not modify the manifest before approval.
- [ ] **Step 4: Re-point + live verify.** After approval, update the manifest; the user verifies one real extension capture round-trip (SA page → sidecar POST → local store row). Record the evidence in the closeout.
- [ ] **Step 5: Delete old script.** Commit: `refactor: move sa native host into src`.

## Task 6: Rule Finalization + Docs Closeout

**Files:** `docs/design/PG_EXIT_REMAINDER_SCOPING.md` (§5), `docs/design/PROJECT_PRIORITY_MAP.md`, this plan.

- [x] **Step 1: Finalize §5** to the ruled end-state: `scripts/` = app-unrelated/historical only (enumerate the survivors: `huggingface/`, `scoring/`, `migration/` gate evidence, `p1_2/`, `analysis/`, `visualization/`, `testing/`, `diagnostics/`, `live/` — each with one-line justification); `src/` never imports `scripts/`; all runnable app tooling is `python -m src.*`. `scripts/__init__.py` disposition is explicit, not implicit: DEFAULT = delete it and verify nothing still does `import scripts` (`rg -n "import scripts" src/ tests/` = zero after Tasks 1-5); if a retained historical script provably needs package-ness, keep it and LIST it as "retained package marker" in the survivor table. The final physical scan must be pycache-safe: `find scripts -type f -not -path "*__pycache__*"` (or clean generated caches first) so stale `.pyc` files cannot masquerade as residue.
- [x] **Step 2: Map closeout entry** (newest-first §10): what moved, what died (with the pre-deletion sha for av/eodhd recovery), the deleted-test accounting, gates + A/B result, native host manifest evidence.
- [x] **Step 3: Plan header → LIVE COMPLETE.** Commit: `docs: close scripts runtime consolidation`.

## Full A/B (after Task 4; rerun after Task 5 only if it touched runtime beyond the move)

- Base = this plan's merge base; head = branch tip.
- Acceptance: failure sets IDENTICAL. Passed count drops by exactly the deleted tests named in Task 1 (inventory them in the closeout). Any head-only deterministic failure, or any base-only entry that is not a deleted-test artifact, blocks merge.
- Note: deleted tests do not appear in failure sets at all (they passed on base); the set comparison is therefore expected to be strictly identical — treat ANY diff as a finding.

## Acceptance Criteria

- Review Gate 1 grep = zero: runtime never imports `scripts/`.
- `scripts/` contains only the enumerated app-unrelated/historical survivors.
- No wrappers, tombstones, or orphan stubs remain at any old location.
- Native host works from `src/` with the manifest re-pointed and user-verified.
- Map + scoping §5 record the finished rule; av/eodhd future-provider backlog note carries the recovery sha.

## Post-implementation review amendments (2026-07-06, reviewer)

Applied on the branch after Tasks 1–5, before full A/B. Two classes the plan's inventories
missed (import consumers were swept; shell-script and live-doc PATH references were not):

1. **Installer/launcher stale paths** — `extensions/sa_alpha_picks/install.sh` (`HOST_PATH`),
   `install_firefox.sh` (`HOST_SCRIPT`), `native_host_launcher.sh` (config fallback) all still
   pointed at `scripts/sa_native_host.py`; a fresh install would have registered a dead path.
   Fixed to `src/sa_native_host.py` with a new self-maintaining pin
   `tests/test_extension_install_paths.py` (parses the referenced path out of the shell
   sources, asserts it exists — RED before fix, GREEN after).
2. **Live-doc entrypoints** — `README.md` quickstart + layout, `PROJECT_STRUCTURE.md` table,
   `REFACTOR_PROTECTION_SMOKE_GATES.md` gate commands (4×) now say `python -m src.daily_update`
   / `src/collectors/`; path tokens updated in `LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md`
   (LOCK #9, 2 lines — path only; the psycopg2→PG "today" description there predates the SA
   local cutover and is a separate freshness item), `ARKSCOPE_PROVIDER_CATALOG.md` §3.9,
   `DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md` §5a. Historical docs untouched per plan rule.
3. **DATA_DICTIONARY disposition revised** (user ruling): Task 2 had deleted it; restored from
   `e4ecc2b` to `docs/data/NEWS_PROVIDER_DATA_DICTIONARY.md` with a status header separating
   durable provider-difference facts (2025-12 measurements) from superseded architecture
   (parquet layout, MD5 dedup, old script paths).
4. **Backlog filed** (user ruling): map §P2.5 provider capability display (absorbs av/eodhd
   future-provider note incl. recovery sha `f9d00c7^`) + §P2.6 SA extension health/setup
   surface with boundary note `SA_EXTENSION_HEALTH_SETUP_BOUNDARY.md`.
5. **Live cutover discipline** (recorded for the merge step): stop sidecar + close Firefox
   before merge (running sidecar lazy-imports adapter modules per tick; SA host spawns fresh
   per message); after merge, flip `~/.config/arkscope/sa_native_host.json` `host_script` to
   `src/sa_native_host.py` (single approval-gated live edit — covers Firefox AND Chrome, both
   manifests point at the stable launcher), restart, then extension round-trip.
