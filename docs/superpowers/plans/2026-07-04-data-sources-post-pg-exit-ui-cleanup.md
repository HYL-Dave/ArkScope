# Data Sources Post-PG-Exit UI Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Settings/Data Sources accurately reflect the post-PG-exit runtime: provider health, local stores, and scheduler entries should no longer look like PG/local routing choices.

**Architecture:** This is a UI/metadata cleanup slice. Backend changes are limited to presentation metadata that the UI cannot safely infer, such as scheduler source mode labels and provider disabled reasons; no data path, scheduler execution, migration, or destructive PG cleanup changes are allowed. Frontend changes should keep the existing Settings page structure but replace obsolete toggles/actions with read-only status where the route is now locked local-only.

**Tech Stack:** FastAPI route models, `src/service/provider_health.py`, `src/service/data_scheduler.py`, React/TypeScript Settings UI, Vitest, focused pytest.

---

## Scope And Non-Goals

- In scope:
  - Data Sources page text, labels, table structure, and badges.
  - Data Storage / News Ingestion / Macro Calendar / App Records Settings panels where they expose obsolete local-vs-PG controls.
  - Provider health display wording for FRED/macro disabled state.
  - Tests that pin post-PG-exit copy and prevent PG fallback wording from returning.
- Out of scope:
  - Batch-2 `job_runs` drop.
  - Batch-3 prices PG drop.
  - PG-unreachable E2E.
  - Model list and token monitoring UI.
  - Any new data collection or migration behavior.
  - Removing backend routes used by N9 cleanup; this slice may hide or relabel UI but must not delete migration/drop tooling.

## File Structure

- Modify `src/service/data_scheduler.py`
  - Add scheduler presentation metadata so the frontend does not infer "本地" from `provider_fetch=false`.
  - Keep execution behavior unchanged.
- Modify `src/service/provider_health.py`
  - Expose or encode the FRED disabled reason as "macro ingestion disabled/not enabled" rather than generic provider disabled.
- Modify `apps/arkscope-web/src/api.ts`
  - Extend `ScheduleSourceState` / provider health types with new presentation fields.
- Modify `apps/arkscope-web/src/marketDataDisplay.ts`
  - Update routing labels to post-PG-exit semantics.
  - Add small label helpers for provider status and schedule mode.
- Modify `apps/arkscope-web/src/Settings.tsx`
  - Update Data Sources header/copy.
  - Fix provider health label display.
  - Replace IBKR config table layout with a compact provider-field group.
  - Replace obsolete storage toggles/actions with read-only locked-local status where applicable.
- Modify tests:
  - `apps/arkscope-web/src/marketDataDisplay.test.ts`
  - `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
  - `apps/arkscope-web/src/SettingsNewsStorage.test.ts`
  - Add `apps/arkscope-web/src/SettingsPostPgExitStorage.test.tsx` for market/macro/App Records panel assertions.
  - Add/modify `tests/test_data_scheduler.py` and `tests/test_provider_health.py` only for backend metadata shape.

---

### Task 1: Backend Scheduler Presentation Metadata

**Files:**
- Modify: `src/service/data_scheduler.py`
- Test: `tests/test_data_scheduler.py`

- [ ] **Step 1: Write failing tests for post-PG-exit schedule metadata**

Add tests that assert the API no longer forces the frontend to infer source meaning from `provider_fetch`.

```python
def test_schedule_status_exposes_post_pg_exit_presentation_metadata(monkeypatch):
    from src.service.data_scheduler import status_snapshot

    snap = status_snapshot()

    prices = snap["ibkr_prices"]
    assert prices["source_mode"] == "direct_local"
    assert prices["write_target"] == "market_data.db"
    assert prices["source_badges"] == ["IBKR", "直寫本地"]
    assert prices["retired"] is False

    backfill = snap["price_backfill"]
    assert backfill["source_mode"] == "direct_local"
    assert backfill["source_badges"] == ["IBKR/Polygon", "直寫本地", "缺口補抓"]

    retired = snap["local_incremental"]
    assert retired["source_mode"] == "retired_pg_mirror"
    assert retired["retired"] is True
    assert "PG mirror retired" in retired["retired_reason"]
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
pytest tests/test_data_scheduler.py::test_schedule_status_exposes_post_pg_exit_presentation_metadata -q
```

Expected: fail because `source_mode`, `write_target`, `source_badges`, and `retired` are not present.

- [ ] **Step 3: Add presentation fields without changing execution**

Extend `SourceDef` with presentation-only fields:

```python
    # Presentation-only status metadata for Settings/Data Sources. These fields
    # do not affect execution.
    source_mode: str = "provider_fetch"
    write_target: str = "market_data.db"
    source_badges: tuple[str, ...] = ()
```

Set explicit values for the relevant sources:

```python
SourceDef(
    "ibkr_prices", "IBKR 股價",
    None, None,
    ibkr=True, universe_tickers=True, default_interval_min=60,
    prices_worker=True, writes_market_db=True,
    source_mode="direct_local",
    write_target="market_data.db",
    source_badges=("IBKR", "直寫本地"),
    description="IBKR/Polygon 15min bars for the active universe → market_data.db DIRECT (no PG sync/mirror)",
),
SourceDef(
    "price_backfill", "價格缺口補抓",
    None, None, ibkr=True, universe_tickers=True, default_interval_min=360,
    gap_planned=True,
    prices_worker=True, writes_market_db=True,
    source_mode="direct_local",
    write_target="market_data.db",
    source_badges=("IBKR/Polygon", "直寫本地", "缺口補抓"),
    description="IBKR/Polygon → market_data.db DIRECT (no PG); fills missing trading-day gaps for the active universe.",
),
SourceDef(
    "local_incremental", "本地鏡像增量",
    None, None, default_interval_min=15,
    source_mode="retired_pg_mirror",
    write_target="none",
    source_badges=("已退役",),
    description="Retired PG → market_data.db delta path; use direct-local sources",
),
```

In `status_snapshot()`, include:

```python
"source_mode": d.source_mode,
"write_target": d.write_target,
"source_badges": list(d.source_badges),
"retired": source in _N9_RETIRED_SOURCES,
"retired_reason": _N9_RETIRED_SOURCES.get(source),
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
pytest tests/test_data_scheduler.py::test_schedule_status_exposes_post_pg_exit_presentation_metadata -q
```

Expected: PASS.

Commit:

```bash
git add src/service/data_scheduler.py tests/test_data_scheduler.py
git commit -m "feat: expose scheduler post-pg-exit presentation metadata"
```

---

### Task 2: FRED Provider Health Wording

**Files:**
- Modify: `src/service/provider_health.py`
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/marketDataDisplay.ts`
- Test: `tests/test_provider_health.py`
- Test: `apps/arkscope-web/src/marketDataDisplay.test.ts`

- [ ] **Step 1: Write failing backend test for FRED disabled reason**

Add a test that pins the difference between "provider unavailable" and "macro ingestion not enabled".

```python
def test_fred_disabled_reason_is_macro_ingestion_not_provider_failure(monkeypatch):
    from src.service.provider_health import compute_provider_health

    class _Backend:
        def query_health_stats(self):
            return {}

    class _DAL:
        _backend = _Backend()

    class _Config:
        macro_calendar_enabled = False

    monkeypatch.setattr("src.agents.config.get_agent_config", lambda: _Config())

    out = compute_provider_health(_DAL())
    fred = next(p for p in out["providers"] if p["id"] == "fred")
    assert fred["status"] == "disabled"
    assert fred["disabled_reason"] == "macro_ingestion_disabled"
    assert "not enabled" in fred["detail"].lower()
```

- [ ] **Step 2: Run backend test and verify RED**

Run:

```bash
pytest tests/test_provider_health.py::test_fred_disabled_reason_is_macro_ingestion_not_provider_failure -q
```

Expected: fail because `disabled_reason` is missing.

- [ ] **Step 3: Add disabled reason metadata**

Update `_add()` in `provider_health.py` to accept:

```python
disabled_reason: str | None = None
```

and include it in the provider dict:

```python
"disabled_reason": disabled_reason,
```

For FRED, pass the reason and detail explicitly:

```python
fred_disabled = macro_enabled is False
_add(
    "fred", "FRED", "macro",
    _key_info(loaded_file_keys, app_keys, "FRED_API_KEY"),
    enabled=macro_enabled,
    last_success=fred["last_success"],
    last_attempt=fred["last_attempt"],
    last_error=fred["last_error"],
    detail=(
        "macro ingestion not enabled"
        if fred_disabled
        else f"latest fred job success {_iso(fred['last_success']) or '—'}"
    ),
    disabled_reason="macro_ingestion_disabled" if fred_disabled else None,
    signals={"jobs_prefix": "fetch_fred"},
)
```

This replaces the current FRED `_add(...)` call; keep all other providers unchanged.

- [ ] **Step 4: Add frontend label helper test**

In `marketDataDisplay.test.ts`, add:

```ts
import { providerHealthStatusLabel } from "./marketDataDisplay";

describe("providerHealthStatusLabel", () => {
  it("labels FRED macro disabled as not-enabled ingestion, not broken provider", () => {
    expect(providerHealthStatusLabel({
      id: "fred",
      kind: "macro",
      status: "disabled",
      disabled_reason: "macro_ingestion_disabled",
    })).toBe("未啟用抓取");
  });

  it("keeps generic disabled providers as disabled", () => {
    expect(providerHealthStatusLabel({
      id: "other",
      kind: "news",
      status: "disabled",
      disabled_reason: null,
    })).toBe("已停用");
  });
});
```

- [ ] **Step 5: Implement frontend helper and type**

In `api.ts`, extend provider health type:

```ts
disabled_reason?: string | null;
```

In `marketDataDisplay.ts`, add:

```ts
export function providerHealthStatusLabel(p: { status: string; disabled_reason?: string | null }): string {
  if (p.status === "disabled" && p.disabled_reason === "macro_ingestion_disabled") {
    return "未啟用抓取";
  }
  const labels: Record<string, string> = {
    connected: "正常",
    stale: "過期",
    maintenance: "維護中",
    no_signal: "無訊號",
    missing_key: "缺金鑰",
    disabled: "已停用",
  };
  return labels[p.status] ?? p.status;
}
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
pytest tests/test_provider_health.py::test_fred_disabled_reason_is_macro_ingestion_not_provider_failure -q
cd apps/arkscope-web && npm test -- marketDataDisplay.test.ts
```

Expected: both pass.

Commit:

```bash
git add src/service/provider_health.py tests/test_provider_health.py apps/arkscope-web/src/api.ts apps/arkscope-web/src/marketDataDisplay.ts apps/arkscope-web/src/marketDataDisplay.test.ts
git commit -m "fix: distinguish disabled macro ingestion from provider failure"
```

---

### Task 3: Data Sources Schedule Labels And Header Copy

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Test: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`

- [ ] **Step 1: Extend schedule response type**

In `api.ts`, extend `ScheduleSourceState`:

```ts
source_mode: string;
write_target: string;
source_badges: string[];
retired: boolean;
retired_reason: string | null;
```

- [ ] **Step 2: Write failing UI test for schedule labels**

In `SettingsProviderConfig.test.ts`, modify the mock schedule source to include `price_backfill`:

```ts
price_backfill: {
  label: "價格缺口補抓",
  description: "IBKR/Polygon → market_data.db DIRECT (no PG)",
  ibkr: true,
  provider_fetch: false,
  enabled: false,
  interval_minutes: 360,
  default_interval_minutes: 360,
  running: false,
  progress: null,
  last_attempt_at: null,
  last_result: null,
  gap_planned: true,
  durable_state: null,
  job_name: "collect.price_backfill",
  source_mode: "direct_local",
  write_target: "market_data.db",
  source_badges: ["IBKR/Polygon", "直寫本地", "缺口補抓"],
  retired: false,
  retired_reason: null,
},
```

Add test:

```ts
it("renders scheduler source badges from backend metadata instead of provider_fetch heuristics", async () => {
  await renderDataSources();
  const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
    node.textContent?.includes("價格缺口補抓"));
  if (!row) throw new Error("missing price_backfill row");
  expect(row.textContent).toContain("IBKR/Polygon");
  expect(row.textContent).toContain("直寫本地");
  expect(row.textContent).toContain("缺口補抓");
  expect(row.textContent).not.toContain(" · 本地");
});
```

- [ ] **Step 3: Implement schedule row badge rendering**

Replace the current schedule source suffix:

```tsx
{s.ibkr && <span className="muted tiny"> · IBKR</span>}
{!s.provider_fetch && <span className="muted tiny"> · 本地</span>}
```

with:

```tsx
{(s.source_badges ?? []).map((badge) => (
  <span className="muted tiny" key={badge}> · {badge}</span>
))}
{s.retired && <span className="ds-chip ds-disabled">已退役</span>}
```

Update the Data Sources header copy to say:

```tsx
App 直接發起資料抓取（免 cron）。每個來源獨立排程；IBKR 來源共用 Gateway 鎖序列化，
且同一輪最多啟動一個本地市場 DB 寫入者。股價與新聞抓取皆直寫本地 SQLite；PG mirror 路徑已退役。
```

- [ ] **Step 4: Run UI tests and commit**

Run:

```bash
cd apps/arkscope-web && npm test -- SettingsProviderConfig.test.ts
```

Expected: PASS.

Commit:

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/Settings.tsx apps/arkscope-web/src/SettingsProviderConfig.test.ts
git commit -m "fix: show direct-local scheduler source labels"
```

---

### Task 4: IBKR Provider Config Layout

**Files:**
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Test: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`

- [ ] **Step 1: Write failing UI structure test for grouped IBKR fields**

Extend the mocked IBKR provider fields to include `host` and `port` before `client_id`:

```ts
{
  field: "host",
  label: "Gateway host",
  secret: false,
  env_var: "IBKR_HOST",
  app_value_set: true,
  app_value_masked: "<ibkr-gateway-host>",
  effective_source: "app",
  needs_import: false,
  import_source: null,
  importable_env_vars: ["IBKR_HOST"],
  defaulted: false,
  guarded: false,
  guard_reason: null,
},
{
  field: "port",
  label: "Gateway port",
  secret: false,
  env_var: "IBKR_PORT",
  app_value_set: true,
  app_value_masked: "4001",
  effective_source: "app",
  needs_import: false,
  import_source: null,
  importable_env_vars: ["IBKR_PORT"],
  defaulted: false,
  guarded: false,
  guard_reason: null,
},
```

Add test:

```ts
it("renders IBKR connection settings as one grouped block with derived ids below the client id", async () => {
  await renderDataSources();
  const group = host!.querySelector("[data-testid='ibkr-config-group']");
  expect(group?.textContent).toContain("Gateway host");
  expect(group?.textContent).toContain("Gateway port");
  expect(group?.textContent).toContain("Client ID");
  expect(group?.textContent).toContain("各域用戶端 ID：");
  expect(group?.textContent).toContain("股價=21");
});
```

- [ ] **Step 2: Implement grouped IBKR rendering**

Add a small helper in `Settings.tsx`:

```tsx
function isIbkrProvider(pid: string): boolean {
  return pid === "ibkr";
}
```

In the provider config table body, special-case `pid === "ibkr"` and render one row:

```tsx
if (isIbkrProvider(pid) && c.fields.length > 0) {
  return (
    <tr key="ibkr.group">
      <td>{label}</td>
      <td colSpan={4}>
        <div data-testid="ibkr-config-group" className="provider-config-group">
          {c.fields.map((f) => renderProviderFieldControl(pid, f))}
        </div>
      </td>
    </tr>
  );
}
```

Extract the repeated field control into:

```tsx
function ProviderConfigFieldControl({
  pid,
  f,
  busy,
  keyDrafts,
  setKeyDrafts,
  saveField,
}: {
  pid: string;
  f: ProviderConfigField;
  busy: string;
  keyDrafts: Record<string, string>;
  setKeyDrafts: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  saveField: (provider: string, field: string, value: string | null, fieldMeta?: ProviderConfigField) => Promise<void>;
}) {
  const draftKey = `${pid}.${f.field}`;
  const draft = keyDrafts[draftKey] ?? "";
  const envControlled = f.env_var === "IBKR_CLIENT_ID" && f.effective_source === "env";
  const chips = f.env_var === "IBKR_CLIENT_ID" && (f.client_id_domains?.length ?? 0) > 0
    ? ibkrClientIdChips(f.client_id_domains!, envControlled ? "" : draft)
    : null;
  const caption = envControlled
    ? "各域用戶端 ID（環境變數控制中）："
    : chips?.preview
      ? "存檔後 ID："
      : "各域用戶端 ID：";
  return (
    <div className="provider-config-field" key={draftKey}>
      <div className="provider-config-field-label">{f.label}</div>
      <div className="provider-config-field-current">
        {f.effective_source === "missing"
          ? <span className="ds-chip ds-missing_key">未設定</span>
          : <>
              <span className="mono">{f.app_value_set ? f.app_value_masked : "（外部）"}</span>
              {f.defaulted && <span className="muted tiny"> · 預設</span>}
              <span className="muted tiny">（{providerConfigSourceLabel(f.effective_source)}）</span>
            </>}
      </div>
      <div className="provider-config-field-edit">
        <input
          className="ds-interval ds-keyinput"
          type={f.secret ? "password" : "text"}
          placeholder={f.secret ? "貼上金鑰…" : f.label}
          value={draft}
          disabled={busy === draftKey}
          onChange={(e) => setKeyDrafts((d) => ({ ...d, [draftKey]: e.target.value }))}
          onKeyDown={(e) => {
            if (e.key === "Enter" && draft) void saveField(pid, f.field, draft, f);
          }}
        />
        {draft && (
          <button className="btn-ghost tiny" onClick={() => void saveField(pid, f.field, draft, f)}>
            儲存
          </button>
        )}
        {f.app_value_set && (
          <button className="btn-ghost tiny" onClick={() => void saveField(pid, f.field, null, f)}>
            清除
          </button>
        )}
      </div>
      {chips && (
        <div className="provider-config-field-hint muted tiny">
          {caption}{chips.text}
        </div>
      )}
    </div>
  );
}
```

Do not change save/clear behavior. Keep the already-fixed env-controlled Client ID preview: when `f.effective_source === "env"`, the derived-id row must not show `存檔後 ID`.

- [ ] **Step 3: Add minimal CSS**

Add CSS in `apps/arkscope-web/src/styles.css` near the existing `.ds-config` rule:

```css
.provider-config-group {
  display: grid;
  gap: 10px;
  max-width: 760px;
}
.provider-config-field {
  display: grid;
  grid-template-columns: minmax(110px, 160px) minmax(160px, 1fr) auto;
  gap: 8px;
  align-items: center;
}
.provider-config-field-edit {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}
.provider-config-field-hint {
  grid-column: 2 / -1;
}
@media (max-width: 760px) {
  .provider-config-field {
    grid-template-columns: 1fr;
  }
  .provider-config-field-hint {
    grid-column: 1;
  }
}
```

- [ ] **Step 4: Run tests and build, then commit**

Run:

```bash
cd apps/arkscope-web && npm test -- SettingsProviderConfig.test.ts && npm run build
```

Expected: PASS.

Commit:

```bash
git add apps/arkscope-web/src/Settings.tsx apps/arkscope-web/src/SettingsProviderConfig.test.ts apps/arkscope-web/src/*.css
git commit -m "fix: group ibkr gateway settings layout"
```

---

### Task 5: Post-PG-Exit Storage Panel Labels

**Files:**
- Modify: `apps/arkscope-web/src/marketDataDisplay.ts`
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Test: `apps/arkscope-web/src/marketDataDisplay.test.ts`
- Test: `apps/arkscope-web/src/SettingsNewsStorage.test.ts`
- Test: add `apps/arkscope-web/src/SettingsPostPgExitStorage.test.tsx`

- [ ] **Step 1: Update routing label tests**

Change `marketDataDisplay.test.ts` expectations:

```ts
describe("marketRoutingLabel", () => {
  it("renders prices as local authority after P0-C", () => {
    expect(marketRoutingLabel(status({ routing_enabled: true, pg_fallback_active: false })))
      .toBe("本地權威（PG fallback 已退役）");
    expect(marketRoutingLabel(status({ use_local_market_setting: false, routing_enabled: false })))
      .toBe("本地權威（設定尚未翻成預設；PG fallback 已退役）");
  });
});

describe("macroRoutingLabel", () => {
  it("never suggests PG fallback for macro/calendar", () => {
    expect(macroRoutingLabel(macroStatus({ local_first_active: false })))
      .toBe("本地功能未啟用（不會 fallback PG）");
  });
});
```

- [ ] **Step 2: Implement label changes**

Update `marketRoutingLabel()`:

```ts
export function marketRoutingLabel(status: MarketDataStatus): string {
  if (status.routing_enabled) return "本地權威（PG fallback 已退役）";
  if (status.use_local_market_setting) return "設定已開，待建立資料庫";
  return "本地權威（設定尚未翻成預設；PG fallback 已退役）";
}
```

Update `macroRoutingLabel()`:

```ts
export function macroRoutingLabel(status: MacroStatus): string {
  if (!status.local_first_active) return "本地功能未啟用（不會 fallback PG）";
  const envNote = status.env_override ? " · env 強制" : "";
  return status.exists
    ? `啟用中（本地${envNote}）`
    : `啟用中（本地${envNote}）· 待 ingestion 建立`;
}
```

- [ ] **Step 3: Hide obsolete Data Storage actions**

In `Settings.tsx`, replace the Data Storage actions for `bootstrap`, `update`, and `validate` with read-only explanatory text because the backend now rejects these retired PG mirror routes:

```tsx
<p className="muted tiny" style={{ marginTop: 12 }}>
  PG mirror bootstrap / update / validation routes are retired. Price and news ingestion now run from the per-source scheduler below.
</p>
```

Keep `TradingDayCoveragePanel`.

For the `使用本地 market data` checkbox, replace it with read-only status:

```tsx
<span className="ds-chip ds-connected">local authority</span>
```

Do not remove backend toggle endpoints in this task.

- [ ] **Step 4: Remove Macro local toggle from visible UI**

In `MacroStorageSection`, replace the checkbox with:

```tsx
<p className="muted tiny" style={{ marginTop: 12 }}>
  Macro / Calendar is local-only in the app. FRED/Finnhub jobs populate macro_calendar.db; when disabled or empty, reads return honest empty results rather than PG fallback.
</p>
```

- [ ] **Step 5: Simplify News Ingestion panel copy**

For `status.news_hard_local`, keep only read-only rows:

```tsx
<dt>新聞寫入</dt>
<dd>{newsWriteRouteLabel(status)}</dd>
<dt>新聞讀取</dt>
<dd>{newsReadSurfaceLabel(status)}</dd>
<dt>PostgreSQL</dt>
<dd>{newsPostgresRouteLabel(status)}</dd>
```

Ensure no local/normalized toggle labels render in hard-local mode:

```ts
expect(host.textContent).not.toContain("Polygon／Finnhub 新聞直寫本地");
expect(host.textContent).not.toContain("Normalized news writes");
```

- [ ] **Step 6: Add App Records nav/status test**

Add a test asserting App Records is not active in normal navigation:

```ts
it("does not show the completed App Records migration panel in normal settings navigation", async () => {
  await renderDataSources();
  expect(host!.textContent).not.toContain("App Records 遷移");
});
```

Keep backend routes untouched; they are N9 maintenance tools until final cleanup.

- [ ] **Step 7: Run tests and commit**

Run:

```bash
cd apps/arkscope-web && npm test -- marketDataDisplay.test.ts SettingsNewsStorage.test.ts SettingsProviderConfig.test.ts SettingsPostPgExitStorage.test.tsx && npm run build
```

Expected: PASS.

Commit:

```bash
git add apps/arkscope-web/src/marketDataDisplay.ts apps/arkscope-web/src/marketDataDisplay.test.ts apps/arkscope-web/src/Settings.tsx apps/arkscope-web/src/SettingsNewsStorage.test.ts apps/arkscope-web/src/SettingsProviderConfig.test.ts apps/arkscope-web/src/SettingsPostPgExitStorage.test.tsx
git commit -m "fix: align storage settings with post-pg-exit routing"
```

---

### Task 6: Final Verification And Review Packet

**Files:**
- No production files unless tests expose a defect.

- [ ] **Step 1: Run backend focused tests**

Run:

```bash
pytest tests/test_data_scheduler.py tests/test_provider_health.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend focused tests and build**

Run:

```bash
cd apps/arkscope-web && npm test -- marketDataDisplay.test.ts SettingsProviderConfig.test.ts SettingsNewsStorage.test.ts SettingsPostPgExitStorage.test.tsx && npm run build
```

Expected: PASS.

- [ ] **Step 3: Grep for forbidden PG-fallback UI wording in Settings**

Run:

```bash
rg -n "關閉（使用 PG）|PG fallback|PG 為 fallback|PG 同步|本地鏡像|使用本地 market data|使用本地 macro" apps/arkscope-web/src/Settings.tsx apps/arkscope-web/src/marketDataDisplay.ts
```

Expected:
- No hits for active UI labels.
- Any hit must be in an explicit retired-route explanation, such as "PG mirror routes are retired".

- [ ] **Step 4: Commit any final test-only correction**

If Task 6 caused a tiny test expectation correction, commit:

```bash
git add apps/arkscope-web/src tests
git commit -m "test: pin post-pg-exit settings labels"
```

- [ ] **Step 5: Prepare review summary**

Include:
- The list of changed files.
- Screenshots are optional; if not using browser, provide the exact labels now shown for:
  - FRED provider status.
  - IBKR host/port/client-id group.
  - `price_backfill`.
  - Market/Macro/News panels.
  - App Records navigation.
- Test commands and pass counts.

---

## Self-Review Notes

- Spec coverage:
  - FRED "已停用" confusion: Task 2.
  - IBKR host/port/client-id alignment: Task 4.
  - `本地價格直連補抓 · IBKR · 本地` wording: Task 1 and Task 3.
  - Market/Macro local toggles after PG-exit: Task 5.
  - News Ingestion post-exit role: Task 5.
  - App Records migration visibility: Task 5.
- Placeholder scan:
  - No "TBD" or unspecified test commands.
- Type consistency:
  - New schedule fields are introduced in backend Task 1 and TypeScript Task 3 before UI use.
  - Provider `disabled_reason` is introduced in backend Task 2 and TypeScript Task 2 before UI use.
- Scope check:
  - This plan intentionally does not remove backend migration/drop routes. Backend removal belongs to N9 batch-2/batch-3 cleanup, not UI cleanup.
