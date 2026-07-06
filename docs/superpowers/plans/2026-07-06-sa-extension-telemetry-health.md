# SA Extension Telemetry Plumbing + Health Surface Implementation Plan

> **Status: REVIEWED — cleared for implementation (Tasks 1→6).** 3 must-fixes + 2
> should-fixes from the 2026-07-06 user review are folded in below (marked MF1-3/SF1-2).
> User priority ruling: this slice runs **ahead of the other P1 items** — it builds the
> desktop/extension observability foundation.
> Authority for the boundary: `docs/design/SA_EXTENSION_HEALTH_SETUP_BOUNDARY.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the structural telemetry gap (dev:desktop's ephemeral-port+token sidecar is
unreachable by the browser-spawned native host, so `record_extension_job` silently never
lands) and give the app a per-segment SA extension health view so "data landed but
telemetry didn't" is visible instead of invisible.

**Architecture:** Three small pieces. (1) The Electron shell already knows the per-run
`apiBase`+`token` (`apps/arkscope-desktop/main.js:144-148`) — after the sidecar passes
health it writes them into `~/.config/arkscope/sa_native_host.json` and clears them on
clean shutdown. (2) `src/sa_native_host.py` resolves its telemetry target as **env >
config > default-8420** (real env wins — `0495757` precedent) with a one-shot fallback to
the default target when a config-sourced target refuses (covers crash-stale config +
standalone-8420 workflow). (3) A read-only sidecar health service + `GET
/sa/extension-health` + a Settings 資料來源 SA panel showing the segment checklist
(config / manifests / launcher / simulated host ping / telemetry binding / last telemetry
row / capture read-back).

**Explicit non-goals (user ruling 2026-07-06):** NO embedded SA browser/session — that is a
separate Desktop App Vision decision (new ingestion client: login/2FA/DOM drift/security
boundary; recorded in map §P2.6). No extension JS changes. No repair-writes from the panel
in v1 (display + re-check only; the shell/installer remain the writers). No keyring.

**Tech Stack:** Python 3 + pytest (handler-direct route tests, no TestClient), Node
`node:test` for the desktop pure module (`navigation.test.js` pattern), React+vitest for
the panel, existing PG-unreachable smoke.

---

## Map Check / Authority

- Map §P2.6 filed 2026-07-06; this plan promotes its named sub-fix ("not gated on Desktop
  App Vision", boundary doc `a468646`) to an active slice, plus health display.
- Incident + port map + design constraint: boundary doc "Incident grounding" section.
- Live facts (verified 2026-07-06): shell spawns `python -m src.api` on ephemeral port
  (observed 34145) with per-run token (`main.js:98-117` spawn, `:144-148` port/token,
  `:119-134` stop); host POSTs to `ARKSCOPE_API_*` env else `127.0.0.1:8420`
  (`sa_native_host.py:721-738`); token enforced when set (`src/api/app.py:151-153`);
  launcher reads config at `ARKSCOPE_SA_NATIVE_HOST_CONFIG` else
  `~/.config/arkscope/sa_native_host.json`; installers rewrite the config **wholesale**
  (`install.sh:71-89`) — a later install drops api fields until the next app start
  (self-heals; the panel's telemetry-binding row shows the gap meanwhile).
- Last successful extension telemetry row: `sa_market_news_refresh/extension` at
  `2026-07-05T16:05Z` (rode a standalone 8420 sidecar) — the baseline this slice fixes.

## Decisions Locked

1. **Precedence env > config > default.** Any of `ARKSCOPE_API_BASE_URL/HOST/PORT/TOKEN`
   set in the host's (browser) env wins unchanged; else config `api_base`/`api_token`;
   else `http://127.0.0.1:8420` tokenless. Real env beats app-written state (client-id
   hint precedent `0495757`).
2. **Write after health, clear on clean quit.** The shell writes `api_base`/`api_token`
   only after `waitForHealth` succeeds (never advertise a dead sidecar) and removes both
   keys in `stopSidecar` (other keys untouched; absent file on write → create with just
   api fields; installer later overwrites wholesale — accepted, self-heals next launch).
3. **One-shot refused fallback.** If the POST target came from **config** and the
   connection is refused, retry once at the env/default target. Covers: crash-stale config
   while a standalone 8420 sidecar is running. No other retries; total worst case 2 ×
   2s timeout in a per-message process.
4. **Telemetry stays best-effort.** Malformed/absent config must never raise out of
   `record_extension_job`; failure log line gains `target=... source=...` for
   diagnosability. The per-run token is never logged and never included in the ping
   response; config file written `0600` via tmp-file+rename.
5. **No synthetic capture writes.** The health surface proves the write leg with real
   freshness (`sa_refresh_meta`/`sa_articles`/`sa_market_news` max timestamps) and
   `job_runs` telemetry rows — it never inserts test rows into capture tables.
6. **Panel is read-only + 重新檢查.** Placement: Settings 資料來源 SA area, macro 本地快照
   panel precedent. Segment labels in plain zh (terminology discipline), each row = 名稱 +
   ✓/✗/— + one-line detail; on failure the row says WHICH segment broke.

## Stop-Loss Triggers

- A RED differs from the plan's predicted failure (shape/AttributeError instead of the
  named assert) → STOP, report, don't improvise fixtures.
- Two consecutive unexplained gate failures → STOP.
- Task 2 wiring turns out to need Electron-runtime APIs beyond `fs`/`path`/`process`
  in the pure module → STOP and re-scope (the module must stay node:test-able).
- Any test writes to the real `~/.config/arkscope/` or real profile DBs → STOP, fix
  isolation first (hermeticity family).

## Review Gates

- Gate 1 (after Task 1): `python -m pytest tests/test_sa_native_host_telemetry.py tests/test_job_runs.py -q` green; RED evidence recorded for each new test.
- Gate 2 (after Task 2): `node --test apps/arkscope-desktop/` green (navigation tests still pass).
- Gate 3 (after Task 4): `python -m pytest tests/test_sa_extension_health.py tests/test_sa_routing.py tests/test_sa_tools.py -q` green.
- Gate 4 (after Task 5): `npm run test --workspace apps/arkscope-web` + `npm run build` green.
- Gate 5: PG-unreachable smoke unchanged (`python src/smoke/pg_unreachable_e2e.py` 24 checks, `pg_attempts:[]`).
- Full A/B (virgin `git archive`, sequential, failure SETS): strictly identical; passed
  delta = exactly the new tests.

---

## Task 1: Host telemetry target resolution (`src/sa_native_host.py`)

**Files:** `src/sa_native_host.py`; NEW `tests/test_sa_native_host_telemetry.py`.

- [ ] **Step 1 (RED):** New test file; import `src.sa_native_host` directly (module import
  is side-effect-safe for helpers; mirror how `tests/test_job_runs.py` exercises
  `_post_extension_job_to_sidecar` seams). Cases, each with env cleared via
  `monkeypatch.delenv(..., raising=False)` and a tmp config via
  `monkeypatch.setenv("ARKSCOPE_SA_NATIVE_HOST_CONFIG", str(tmp_path/"cfg.json"))`:
  1. no env, no config file → target `http://127.0.0.1:8420`, token None, source `default`
  2. config `{"api_base":"http://127.0.0.1:45001","api_token":"t1"}` → that base+token, source `config`
  3. config present AND `ARKSCOPE_API_PORT=9999` env → env wins (source `env`)
  4. malformed JSON config → source `default`, no exception
  5. POST via fake `urllib.request.urlopen` raising `URLError(ConnectionRefusedError)` on
     the config target → second call hits the default target (assert both URLs seen, in order)
  6. source `env`/`default` refused → NO second call (fallback only from config)
  7. `handle_message({"action":"ping"})` response includes `telemetry_target` +
     `telemetry_source` and does NOT include any token value
  8. **(MF2) ping is DAL-free**: monkeypatch `src.tools.data_access.DataAccessLayer` to
     raise on construction → `handle_message({"action":"ping"})` STILL returns
     `status:"ok"` with `telemetry_target`/`telemetry_source`. Today this fails because
     `handle_message` constructs `DataAccessLayer(db_dsn="auto")` at
     `sa_native_host.py:75` before the ping branch at `:118` — a broken profile/DAL
     poisons even the health probe.
- [ ] **Step 2 (GREEN):** Implement `_resolve_sidecar_target() -> (base, token, source)`
  and rewire `_post_extension_job_to_sidecar` (keep `/jobs/extension-record`, headers,
  2.0s timeout); **(MF2) move the ping branch ABOVE the `DataAccessLayer` construction**
  (`:75`) so ping never touches DAL/profile state; failure log line gains target+source.
- [ ] **Step 3:** Run Gate 1; record RED→GREEN evidence.

## Task 2: Electron shell writes/clears the api fields

**Files:** NEW `apps/arkscope-desktop/sidecarConfig.js` + `sidecarConfig.test.js`;
`apps/arkscope-desktop/main.js`.

- [ ] **Step 1 (RED):** `sidecarConfig.test.js` (node:test, `navigation.test.js` pattern,
  tmp dirs via `fs.mkdtempSync`): write-into-absent-file creates parents + only api keys;
  write-into-existing preserves `project_root`/`python_path`/`host_script`; mode is 0600;
  clear removes only the two api keys (file + other keys survive); clear on absent file =
  no-op; write is tmp+rename (no partial JSON on interrupt — assert no `*.tmp` leftover).
  **(MF1) stop-cleanup cases on `stopSidecarCleanup(child, configPath, {kill})`:**
  `child = null` → config api keys STILL cleared, no throw, kill not called;
  `child = {exitCode: 0}` (already crashed/exited) → config STILL cleared, kill not
  called; `child = {exitCode: null, pid: 123}` (running) → config cleared AND kill
  attempted. Rationale: `main.js:120` early-returns on `!sidecar || sidecar.exitCode !==
  null` — a clear placed after that guard leaves stale `api_base`/`api_token` exactly when
  the sidecar crashed, defeating this slice.
- [ ] **Step 2 (GREEN):** Implement `writeSidecarApiConfig(configPath, {apiBase, apiToken})`,
  `clearSidecarApiConfig(configPath)`, and `stopSidecarCleanup(child, configPath, {kill})`
  (clears config FIRST unconditionally, then applies the existing kill/guard dance to
  `child`; injectable `kill` for tests) — pure `fs`/`path`, no Electron imports.
- [ ] **Step 3:** Wire `main.js`: default config path
  `process.env.ARKSCOPE_SA_NATIVE_HOST_CONFIG || ~/.config/arkscope/sa_native_host.json`;
  call write **after** `waitForHealth(port, token)` returns true (`createWindow`);
  `stopSidecar()` delegates to `stopSidecarCleanup` so the config clear is its FIRST
  effect, **before any early return**; one `pushTail`/console line each; failures logged,
  never fatal to the app. Run Gate 2.

## Task 3: Health service (`src/service/sa_extension_health.py`)

**Files:** NEW `src/service/sa_extension_health.py`; NEW `tests/test_sa_extension_health.py`.

- [ ] **Step 1 (RED):** Tests build a fake HOME layout under `tmp_path` (config json,
  Firefox/Chrome manifest jsons, executable launcher stub) and inject paths via the
  service's explicit `SAExtensionHealthPaths` dataclass (no real-HOME reads in tests).
  Segments asserted: `config` (exists/parses/host_script exists + under project root/
  python executable), `manifests` (per-browser found + path==launcher), `launcher`
  (exists+exec), `host_ping` (spawn seam injected: fake returns ping payload with
  `telemetry_target`), `telemetry_binding` (config api_base+api_token vs this process's
  `ARKSCOPE_API_HOST/PORT/TOKEN` → match/mismatch/absent with which-side detail),
  `telemetry_last` **(MF3 — query by trigger_source, never by fixed job names)**: the
  extension sends `job_name` shapes the host passes through VERBATIM
  (`sa_native_host.py:672` `msg.get("job_name")`) — canonical (`sa_market_news_refresh`)
  AND `sa_extension:<slug>` both exist in real `job_runs` data
  (`sa_extension:manual_fetch` observed live). A fixed-name
  `run_summary_by_name([...])` lookup misses the slug shape, and a bare
  `list_runs(limit=200)` scan drowns old extension rows under scheduler rows (13k+
  `collect.*` rows). Therefore: extend `JobRunsLocalStore.list_runs`
  (`src/service/job_runs_store.py:555`, currently `job_name`/`limit`/`offset` only) with
  an optional `trigger_source: Optional[str] = None` filter (its own RED in
  `tests/test_job_runs.py`), and `telemetry_last` = newest terminal
  (`succeeded`/`failed`) row with `trigger_source='extension'` regardless of job_name.
  Fixture MUST include both a `sa_market_news_refresh` row and a NEWER
  `sa_extension:alpha_picks_quick` row and assert the slug row is the one found.
  `capture_readback` (tmp `sa_capture.db` via
  `sa_capture_store.connect(read_only=True)` honest-empty → "no capture yet", populated
  fixture → freshness timestamps). Failure of one segment never hides the others (each
  row independent).
- [ ] **Step 2 (GREEN):** Implement. **(SF1) Segments are tri-state
  `{key, state: ok|warn|fail, detail}`**: `telemetry_last` and `capture_readback` with NO
  history (fresh install / just-reset profile, before the first capture) are **`warn`
  (「尚未有第一次擷取」), never `fail`** — a fresh install must not show hard-red before
  it has ever captured. Overall `ok` = no `fail` among required segments (`warn` allowed);
  manifests require ≥1 browser found.
- [ ] **Step 3 (seam-mock discipline):** ONE real-shape integration test that spawns the
  REAL host (`[sys.executable, "src/sa_native_host.py"]`, length-prefixed ping, 15s
  timeout, repo cwd) and asserts the service parses its actual reply — the sibling for the
  mocked spawn seam. Mark `@pytest.mark.integration` if collection cost demands. Gate 3
  partial run.

## Task 4: Route `GET /sa/extension-health`

**Files:** `src/api/routes/seeking_alpha.py`; tests appended to
`tests/test_sa_extension_health.py` (or `tests/test_sa_routing.py` — follow that file's
handler-direct style: call the handler with a fake service, NO TestClient).

- [ ] **Step 1 (RED):** handler returns the service payload verbatim + 200; service raising
  → **(SF2)** `HTTPException(status_code=503, detail={"code":
  "sa_extension_health_unavailable"})` — the test asserts the raised exception's
  `.detail["code"]`, and any HTTP-level check asserts the FastAPI wire shape
  `{"detail": {"code": ...}}`, NOT a top-level `code` key (the `detail.code`-vs-`code`
  false-red from earlier slices).
- [ ] **Step 2 (GREEN):** implement thin route (service injected the same way the file's
  existing routes take dependencies). Run Gate 3.

## Task 5: Frontend panel

**Files:** `apps/arkscope-web/src/api.ts`; `apps/arkscope-web/src/Settings.tsx`;
NEW `apps/arkscope-web/src/saExtensionHealthDisplay.ts` + `.test.ts` (pure display helper,
`marketDataDisplay.ts` pattern).

- [ ] **Step 1 (RED):** vitest on the display helper: segment → {label(zh), state ✓/✗/—,
  detail}; ordering fixed (鏈路順序: 設定檔 → 瀏覽器註冊 → 啟動器 → 主機測試 → 遙測綁定 →
  最近遙測 → 資料回讀); unknown segment key → safe fallback row.
- [ ] **Step 2 (GREEN):** `getSAExtensionHealth()` in api.ts; Settings 資料來源 SA area
  gains the 「SA Extension 健康」 disclosure (macro 本地快照 panel precedent): checklist
  rows + 重新檢查 button (re-fetch), loading/error states. Run Gate 4.

## Task 6: Live verification + closeout

- [ ] **Step 1 (live, the structural proof):** with ONLY `npm run dev:desktop` running:
  panel all-green (telemetry binding = 綁定本次 sidecar), then Firefox Quick Refresh →
  `job_runs` gains a NEW `*/extension` row — the outcome that was structurally impossible
  before this slice. Evidence: row timestamp + host log line with `source=config`.
- [ ] **Step 2 (live, regression):** clean-quit dev:desktop (config api fields cleared) →
  standalone `python -m src.api` (8420, no token) → Quick Refresh → telemetry lands via
  `default` source. Also run Gate 5 smoke.
- [ ] **Step 3 (docs):** map §10 closeout entry + §P2.6 status update (part 1 shipped;
  embedded-browser decision explicitly still open); boundary doc status flip; memory sync.
  Commit: `docs: close sa extension telemetry health slice`.

## Full A/B (after Task 5)

- Base = this plan's merge base; head = branch tip. Virgin `git archive` both sides from
  the main repo, sequential full suite, compare failure SETS.
- Acceptance: sets strictly identical; passed count grows by exactly the new tests (no
  deletions planned in this slice — ANY base-only entry is a finding).

## Acceptance Criteria

- Under dev:desktop alone, extension telemetry lands in local `job_runs` (live-proven).
- Standalone-8420 workflow still lands telemetry (fallback + cleared config proven).
- Host never crashes on absent/malformed config; token never appears in logs, ping
  replies, or API responses (only match/mismatch verdicts).
- Panel shows per-segment 鏈路 status and names the broken segment on failure; a fresh
  install (no capture history) shows warn (—), never hard-red (SF1).
- A crashed sidecar still gets its stale `api_base`/`api_token` cleared on shutdown (MF1);
  host ping succeeds even when DAL construction raises (MF2); `sa_extension:<slug>`
  telemetry rows are found by the health view (MF3).
- Installer-overwrite and crash-stale-config behaviors documented in the boundary doc.
- PG-unreachable smoke unchanged (24 checks); full A/B strictly identical.
