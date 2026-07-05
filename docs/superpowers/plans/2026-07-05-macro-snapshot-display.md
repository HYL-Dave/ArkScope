# Macro/FRED Snapshot Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** DRAFT PLAN 2026-07-05. Docs-only; no runtime changes authorized until review.

**Goal:** Make FRED visible and useful as a local readable snapshot without enabling automatic macro ingestion. The Data Sources page should stop presenting FRED as "not enabled" when the API key is configured and local FRED observations exist; the app should expose a small curated macro snapshot and let agent tools read `get_macro_value()` from `macro_calendar.db`, with every displayed value carrying both `observation_date` and `fetched_at`.

**Architecture:** Re-scope `macro_calendar.enabled` from "macro reads are allowed" to "macro refresh/manual ingestion jobs are allowed." FRED series reads and the new curated snapshot route are local read surfaces and must work while refresh is disabled. Finnhub economic/earnings calendar surfaces remain gated/excluded because their local tables are empty and the product decision did not adopt them.

**Tech Stack:** Python/FastAPI, SQLite `macro_calendar.db`, existing `MacroCalendarLocalStore`, `provider_health`, React Settings/Data Sources UI, Vitest, pytest.

---

## Map Check / Authority

- `docs/design/MACRO_FRED_PRODUCT_SEMANTICS.md` §6 is the governing product decision: adopted semantics are "readable local snapshot, refresh disabled." It explicitly rejects the stale framing where FRED is treated as disabled merely because auto-refresh is off.
- `docs/design/PROJECT_PRIORITY_MAP.md` §10 queues this slice as **macro snapshot display**: Data Sources relabeling, a Macro Snapshot panel, `get_macro_value` enablement, and an in-slice decision on release dates.
- Current local facts that shape the slice:
  - `data/macro_calendar.db` has `macro_observations = 29,571`, `macro_series = 11`, `macro_release_dates = 4,659`, `cal_ipo_events = 86`.
  - FRED series present: `CPIAUCNS`, `CPILFESL`, `DGS10`, `DGS2`, `FEDFUNDS`, `GDP`, `GDPC1`, `PAYEMS`, `T10Y2Y`, `UNRATE`, `VIXCLS`.
  - Max FRED `fetched_at` is `2026-06-25T01:09:52Z`.
  - `cal_economic_events = 0` and `cal_earnings_events = 0`; do not present Finnhub calendars as available in this slice.
  - `src/service/data_scheduler.py` has no macro/FRED source. Opening reads creates no refresh obligation.
- Carryover hard-lock #5 keeps the macro layer in the product unless explicitly amended; this slice is a display/readability correction, not a retirement or ingestion expansion.

**Out of scope:**

- No scheduler source for FRED.
- No live FRED API calls.
- No `macro_calendar.enabled=true` default flip.
- No Finnhub economic/earnings backfill.
- No C-2/C-3 workflow integration beyond making `get_macro_value()` usable and snapshot data available.
- No removal of P1.2 vintage/as-of machinery.
- No dead-code sweep beyond stale copy directly touched by this slice.

## Decisions Locked

1. **Three-axis FRED status.** Provider/key state, local snapshot state, and auto-refresh state are separate. FRED may be "configured + local snapshot available + auto-refresh off"; that is not a provider-disabled state.
2. **`macro_calendar.enabled` becomes refresh-only for FRED.** It continues to gate manual ingestion/jobs and Finnhub calendar routes. It no longer gates FRED series reads, the curated snapshot route, or `get_macro_value()`.
3. **Curated snapshot is a new read route.** Add `GET /macro/snapshot` instead of making the frontend fan out to eleven `/macro/series/{id}` requests. The route reads only local SQLite and returns honest-empty when the DB is missing.
4. **Every displayed value carries freshness.** Snapshot items include `observation_date` and `fetched_at`. Series observations should include `fetched_at`; `get_macro_value()` output must mention fetched freshness for found values.
5. **Calendar surfaces stay out.** `/macro/economic-calendar`, `/macro/earnings-calendar`, `/macro/ipo-calendar`, and `get_economic_calendar()` remain feature-gated because their adopted product semantics were not changed and two local Finnhub tables are empty.
6. **Release dates are included only as metadata.** `macro_release_dates` may inform provider health/Data Sources snapshot coverage, but there is no release-calendar UI in this slice unless it can be shown as simple coverage text. Do not create a scheduling/alert feature.
7. **Missing DB does not create a file.** Status/snapshot reads must not materialize `macro_calendar.db`. Return `available=false` / empty items when absent, mirroring `read_macro_table_stats()`.
8. **PG-unreachable invariant remains.** New macro snapshot reads must work under the existing PG poison smoke with `pg_attempts=[]`.

## File Map

- Modify `src/api/routes/macro_calendar.py`
  - Add `GET /macro/snapshot`.
  - Remove `_require_enabled()` from `/macro/series/{series_id}` only.
  - Keep `_require_enabled()` on health/calendar routes.
  - Update module docstring and disabled message so "enabled" means refresh/calendar feature gate, not all macro reads.
- Modify `src/macro_calendar/local_store.py`
  - Include `fetched_at` in `get_macro_observations()` rows.
  - Add a read-only snapshot helper or support route-level read-only queries without creating the DB.
- Modify `src/tools/macro_calendar_tools.py`
  - Remove `macro_calendar_enabled` gate from `get_macro_value()`.
  - Keep `get_economic_calendar()` gated.
  - Update stale `_BACKEND_MSG` / docstring text ("PostgreSQL DAL backend" is false after PG-exit).
  - Include `fetched_at` in found-value output.
- Modify `src/service/provider_health.py`
  - Make FRED health snapshot-aware.
  - Stop setting `disabled_reason="macro_ingestion_disabled"` when the key/local snapshot is available but refresh is off.
- Modify `apps/arkscope-web/src/api.ts`
  - Add `MacroSnapshotResponse` / `MacroSnapshotItem` types and `getMacroSnapshot()`.
  - Add narrow signal typing helpers only if needed; do not widen unrelated DTOs.
- Modify `apps/arkscope-web/src/Settings.tsx`
  - Render FRED provider health as configured/snapshot-available/refresh-off.
  - Add a compact Macro Snapshot panel in Data Sources, near Provider health or Macro / Calendar storage, using the new route.
  - Make the FRED snapshot text visible, not only a `title=` hover.
- Modify `apps/arkscope-web/src/marketDataDisplay.ts`
  - Remove or retire the special `macro_ingestion_disabled -> 未啟用抓取` headline path if provider health no longer emits it for FRED.
- Tests:
  - `tests/test_macro_calendar_read.py`
  - `tests/test_provider_health.py`
  - `tests/test_pg_unreachable_e2e.py`
  - `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
  - `apps/arkscope-web/src/marketDataDisplay.test.ts`
  - Add a focused frontend snapshot test file only if keeping it inside `SettingsProviderConfig.test.ts` becomes noisy.

## Snapshot Contract

Curated series list for v1:

```python
MACRO_SNAPSHOT_SERIES = (
    ("FEDFUNDS", "Fed Funds"),
    ("DGS10", "10Y Treasury"),
    ("DGS2", "2Y Treasury"),
    ("T10Y2Y", "10Y-2Y Spread"),
    ("CPIAUCNS", "CPI"),
    ("CPILFESL", "Core CPI"),
    ("UNRATE", "Unemployment"),
    ("PAYEMS", "Payrolls"),
    ("GDP", "GDP"),
    ("GDPC1", "Real GDP"),
    ("VIXCLS", "VIX"),
)
```

Response shape:

```json
{
  "available": true,
  "macro_db": "/path/to/data/macro_calendar.db",
  "series_count": 11,
  "observation_count": 29571,
  "release_dates_count": 4659,
  "latest_fetched_at": "2026-06-25T01:09:52Z",
  "auto_refresh_enabled": false,
  "items": [
    {
      "series_id": "FEDFUNDS",
      "label": "Fed Funds",
      "title": "Federal Funds Effective Rate",
      "units": "Percent",
      "value": 4.33,
      "observation_date": "2026-06-01",
      "fetched_at": "2026-06-25T01:09:52Z",
      "realtime_start": "2026-07-01",
      "realtime_end": "9999-12-31"
    }
  ],
  "missing_series": []
}
```

Rules:

- `available=false` when `macro_calendar.db` is absent or has no `macro_observations`.
- `items` are latest current-vintage observations for each curated series (`realtime_end='9999-12-31'`), ordered by `MACRO_SNAPSHOT_SERIES`.
- Missing curated series are listed in `missing_series` and do not make the request fail.
- No value formatting is done in the backend beyond raw value/units; frontend formats display.

## Task 1: Backend Snapshot + Series Freshness

**Files:**
- Modify `src/macro_calendar/local_store.py`
- Modify `src/api/routes/macro_calendar.py`
- Test `tests/test_macro_calendar_read.py`

- [ ] **Step 1: RED - snapshot route works while refresh is disabled**

Add route tests that seed a temp macro DB and call route functions directly with `macro_calendar_enabled=False`.

Expected RED now: no `macro_snapshot` route exists; `macro_series()` raises 503.

Test intent:

```python
def test_macro_snapshot_readable_when_refresh_disabled(seed_macro_db):
    undo = _disable_macro()
    try:
        result = macro_snapshot(dal=object())
    finally:
        undo()
    assert result["available"] is True
    assert result["auto_refresh_enabled"] is False
    assert result["series_count"] == 11
    assert result["observation_count"] >= 1
    fedfunds = next(item for item in result["items"] if item["series_id"] == "FEDFUNDS")
    assert fedfunds["observation_date"]
    assert fedfunds["fetched_at"]
```

Use real `MacroCalendarLocalStore` against `ARKSCOPE_MACRO_CALENDAR_DB` temp path; do not mock the store shape. Seed at least two series with explicit `fetched_at` if existing upsert helpers cannot set it, use direct SQLite insert into the temp DB after schema creation.

- [ ] **Step 2: RED - `/macro/series/{series_id}` includes `fetched_at` and ignores refresh flag**

Flip/add tests:

```python
def test_macro_series_readable_when_refresh_disabled(monkeypatch, seeded_macro_store):
    undo = _disable_macro()
    try:
        result = macro_series(
            "FEDFUNDS",
            from_date=None,
            to_date=None,
            as_of=None,
            limit=5,
            dal=object(),
        )
    finally:
        undo()
    assert result["series_id"] == "FEDFUNDS"
    assert result["observations"][0]["fetched_at"] == "2026-06-25T01:09:52Z"
```

Surgical flip only: calendar disabled tests stay disabled.

- [ ] **Step 3: Implement local store observation freshness**

In `get_macro_observations()`, change:

```python
"SELECT observation_date,value,realtime_start,realtime_end FROM macro_observations "
```

to include `fetched_at`:

```python
"SELECT observation_date,value,realtime_start,realtime_end,fetched_at FROM macro_observations "
```

- [ ] **Step 4: Implement read-only snapshot helper**

Prefer a helper in `local_store.py` that does not construct `MacroCalendarLocalStore` when the file is absent:

```python
def read_macro_snapshot(db_path: str | Path, series: Sequence[tuple[str, str]]) -> dict:
    stats = read_macro_table_stats(db_path)
    obs = stats.get("macro_observations", {})
    base = {
        "macro_db": str(db_path),
        "series_count": stats.get("macro_series", {}).get("row_count", 0),
        "observation_count": obs.get("row_count", 0),
        "release_dates_count": stats.get("macro_release_dates", {}).get("row_count", 0),
        "latest_fetched_at": obs.get("last_fetched_at"),
    }
    if not Path(db_path).exists() or not obs.get("row_count"):
        return {
            **base,
            "available": False,
            "items": [],
            "missing_series": [sid for sid, _ in series],
        }
    # Open sqlite URI f"file:{db_path}?mode=ro", query the latest current-vintage observation for each
    # requested series, and return {**base, "available": True, "items": items,
    # "missing_series": missing}. Do not instantiate MacroCalendarLocalStore here;
    # the constructor can create the DB.
```

The query for each item should select the latest current-vintage row:

```sql
SELECT s.series_id, s.title, s.units,
       o.value, o.observation_date, o.realtime_start, o.realtime_end, o.fetched_at
FROM macro_series s
JOIN macro_observations o ON o.series_id = s.series_id
WHERE s.series_id = ? AND o.realtime_end = '9999-12-31'
ORDER BY o.observation_date DESC
LIMIT 1
```

- [ ] **Step 5: Implement `GET /macro/snapshot`**

In `macro_calendar.py`:

```python
@router.get("/snapshot")
def macro_snapshot():
    payload = read_macro_snapshot(resolve_macro_calendar_db_path(), MACRO_SNAPSHOT_SERIES)
    payload["auto_refresh_enabled"] = bool(get_agent_config().macro_calendar_enabled)
    return payload
```

No `_require_enabled()` call.

- [ ] **Step 6: Preserve calendar gates**

Keep `_require_enabled()` on:

- `/macro/health`
- `/macro/economic-calendar`
- `/macro/earnings-calendar`
- `/macro/ipo-calendar`

Run:

```bash
pytest tests/test_macro_calendar_read.py -q
```

Expected: green after flipping only the FRED series/snapshot expectations.

## Task 2: `get_macro_value()` Readability

**Files:**
- Modify `src/tools/macro_calendar_tools.py`
- Test `tests/test_macro_calendar_read.py`

- [ ] **Step 1: RED - disabled refresh does not disable `get_macro_value()`**

Flip the old test:

```python
def test_get_macro_value_readable_when_refresh_disabled(monkeypatch):
    undo = _disable_macro()
    try:
        monkeypatch.setattr(
            "src.tools.macro_calendar_tools.get_macro_calendar_store",
            lambda dal: MagicMock(
                is_available=MagicMock(return_value=True),
                get_macro_observations=MagicMock(return_value={
                    "series_id": "FEDFUNDS",
                    "title": "Federal Funds Effective Rate",
                    "units": "Percent",
                    "observations": [{
                        "observation_date": date(2026, 6, 1),
                        "value": 4.33,
                        "realtime_start": date(2026, 7, 1),
                        "realtime_end": date(9999, 12, 31),
                        "fetched_at": "2026-06-25T01:09:52Z",
                    }],
                }),
            ),
        )
        out = get_macro_value(object(), "FEDFUNDS", "2026-06-01")
    finally:
        undo()
    assert "FEDFUNDS" in out
    assert "4.33" in out
    assert "fetched 2026-06-25T01:09:52Z" in out
```

- [ ] **Step 2: Keep `get_economic_calendar()` gated**

The existing `TestGetEconomicCalendarTool.test_disabled_returns_helpful_string` remains valid. Update its message only if copy changes.

- [ ] **Step 3: Implement**

Remove only this block from `get_macro_value()`:

```python
if not get_agent_config().macro_calendar_enabled:
    return _DISABLED_MSG
```

Keep the store availability guard, but fix stale copy:

```python
_BACKEND_MSG = (
    "macro_calendar local store is unavailable for this DAL/profile; "
    "no PostgreSQL fallback exists after PG-exit."
)
```

Append freshness to found values:

```python
fetched = row.get("fetched_at")
freshness = f"; fetched {fetched}" if fetched else ""
return (
    f"{sid} ({title}) on {obs.isoformat()}: {value_str} "
    f"(vintage {rt_start} -> {rt_end}{freshness})"
)
```

Use ASCII arrow `->` in changed source unless the file already keeps the existing Unicode arrow and tests expect it.

Run:

```bash
pytest tests/test_macro_calendar_read.py -q
```

## Task 3: Provider Health Three-Axis FRED Status

**Files:**
- Modify `src/service/provider_health.py`
- Test `tests/test_provider_health.py`

- [ ] **Step 1: RED - FRED snapshot available is not disabled**

Replace `test_fred_disabled_when_macro_calendar_feature_is_off` with a snapshot-aware contract:

```python
def test_fred_snapshot_available_when_refresh_is_off(monkeypatch, tmp_path):
    monkeypatch.setenv("FRED_API_KEY", "k")
    monkeypatch.setattr("src.agents.config.get_agent_config",
                        lambda: type("Cfg", (), {"macro_calendar_enabled": False})())
    monkeypatch.setattr(
        "src.service.provider_health.resolve_macro_calendar_db_path",
        lambda: str(tmp_path / "macro_calendar.db"),
    )
    monkeypatch.setattr(
        "src.service.provider_health.read_macro_table_stats",
        lambda path: {
            "macro_series": {"row_count": 11, "last_fetched_at": "2026-06-25T01:09:52Z"},
            "macro_observations": {"row_count": 29571, "last_fetched_at": "2026-06-25T01:09:52Z"},
            "macro_release_dates": {"row_count": 4659, "last_fetched_at": "2026-06-25T01:09:52Z"},
        },
    )
    p = _by_id(compute_provider_health(_FakeDAL(_FakeBackend()), now=_WEDNESDAY), "fred")
    assert p["status"] in {"connected", "no_signal"}
    assert p["disabled_reason"] is None
    assert p["enabled"] is False
    assert p["signals"]["auto_refresh_enabled"] is False
    assert p["signals"]["local_snapshot"]["observation_count"] == 29571
    assert "local snapshot" in p["detail"].lower()
```

If the desired status is `connected`, pass `last_success` as the snapshot `latest_fetched_at` rather than job success. This is the recommended choice because the row has a usable local snapshot even though refresh is off.

- [ ] **Step 2: Add missing-snapshot contract**

Add a separate test for refresh off + no local snapshot:

```python
def test_fred_refresh_off_without_snapshot_is_no_signal(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "k")
    monkeypatch.setattr("src.agents.config.get_agent_config",
                        lambda: type("Cfg", (), {"macro_calendar_enabled": False})())
    monkeypatch.setattr("src.service.provider_health.read_macro_table_stats", lambda path: {})
    p = _by_id(compute_provider_health(_FakeDAL(_FakeBackend()), now=_WEDNESDAY), "fred")
    assert p["status"] == "no_signal"
    assert p["disabled_reason"] is None
    assert p["signals"]["auto_refresh_enabled"] is False
    assert p["signals"]["local_snapshot"]["observation_count"] == 0
```

- [ ] **Step 3: Implement snapshot signals**

Import at function scope to preserve best-effort behavior:

```python
macro_stats: dict[str, Any] = {}
try:
    from src.macro_calendar.local_store import read_macro_table_stats, resolve_macro_calendar_db_path
    macro_stats = read_macro_table_stats(resolve_macro_calendar_db_path())
except Exception as e:
    notes.append(f"macro local stats failed: {e}")
```

Build:

```python
macro_obs = macro_stats.get("macro_observations") or {}
macro_series = macro_stats.get("macro_series") or {}
macro_releases = macro_stats.get("macro_release_dates") or {}
snapshot_latest = _to_dt(macro_obs.get("last_fetched_at"))
snapshot_count = int(macro_obs.get("row_count") or 0)
snapshot = {
    "available": snapshot_count > 0,
    "series_count": int(macro_series.get("row_count") or 0),
    "observation_count": snapshot_count,
    "release_dates_count": int(macro_releases.get("row_count") or 0),
    "latest_fetched_at": _iso(snapshot_latest),
}
```

FRED `_add()` call:

```python
_add(
    "fred", "FRED", "macro",
    _key_info(loaded_file_keys, app_keys, "FRED_API_KEY"),
    config_error=_config_error("fred"),
    enabled=macro_enabled,
    last_success=snapshot_latest or fred["last_success"],
    last_attempt=fred["last_attempt"],
    last_error=fred["last_error"],
    detail=(
        f"local snapshot {snapshot['observation_count']} observations"
        f" · {snapshot['series_count']} series"
        f" · latest fetched {_iso(snapshot_latest) or '—'}"
        f" · auto-refresh {'on' if macro_enabled else 'off'}"
    ),
    signals={
        "jobs_prefix": "fetch_fred",
        "auto_refresh_enabled": bool(macro_enabled),
        "local_snapshot": snapshot,
    },
    disabled_reason=None,
)
```

Do not set `disabled_reason="macro_ingestion_disabled"` for this provider after the decision. Refresh-off is represented by `signals.auto_refresh_enabled=false` and visible detail.

Run:

```bash
pytest tests/test_provider_health.py -q
```

## Task 4: PG-Unreachable E2E Surface Update

**Files:**
- Modify `scripts/smoke/pg_unreachable_e2e.py`
- Test `tests/test_pg_unreachable_e2e.py`

- [ ] **Step 1: RED - macro snapshot route is required and not disabled**

Add `macro_snapshot` to `REQUIRED_CHECKS`:

```python
CheckSpec("macro_snapshot", "GET", "/macro/snapshot", 200, _assert_key("items")),
```

Add an assertion helper:

```python
def _assert_macro_snapshot(body: Any) -> None:
    assert isinstance(body, dict)
    assert "items" in body
    assert "auto_refresh_enabled" in body
    assert "available" in body
```

Use it for the route.

- [ ] **Step 2: Keep calendar-disabled allowance narrow**

`macro_health` and `macro_ipo` may keep the `(200, 503)` allowance if their 503 detail is still the config-disabled state. Do not allow `macro_snapshot` to return 503. This is the smoke-level proof that FRED read surfaces are open while calendar/refresh remains off.

- [ ] **Step 3: Update disabled helper wording if needed**

If `_DISABLED_MSG` in macro routes changes, update `_is_macro_disabled_body()` to recognize the new calendar/refresh wording. It should not match snapshot responses.

Run:

```bash
pytest tests/test_pg_unreachable_e2e.py -q
python -m scripts.smoke.pg_unreachable_e2e
```

The live smoke may read the real local macro DB. It must still report `pg_attempts: []`.

## Task 5: Frontend API + Data Sources Display

**Files:**
- Modify `apps/arkscope-web/src/api.ts`
- Modify `apps/arkscope-web/src/Settings.tsx`
- Modify `apps/arkscope-web/src/marketDataDisplay.ts`
- Test `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
- Test `apps/arkscope-web/src/marketDataDisplay.test.ts`

- [ ] **Step 1: RED - FRED no longer renders as "未啟用抓取"**

Update the mocked `fred` provider in `SettingsProviderConfig.test.ts`:

```ts
{
  id: "fred",
  label: "FRED",
  kind: "macro",
  status: "connected",
  enabled: false,
  key_present: true,
  key_source: "app",
  key_vars: ["FRED_API_KEY"],
  last_success_at: "2026-06-25T01:09:52Z",
  last_attempt_at: null,
  last_error: null,
  detail: "local snapshot 29571 observations · 11 series · latest fetched 2026-06-25T01:09:52Z · auto-refresh off",
  signals: {
    auto_refresh_enabled: false,
    local_snapshot: {
      available: true,
      series_count: 11,
      observation_count: 29571,
      release_dates_count: 4659,
      latest_fetched_at: "2026-06-25T01:09:52Z",
    },
  },
  key_import_suggested: false,
}
```

Flip the existing FRED test:

```ts
it("renders FRED as configured local snapshot with refresh off", async () => {
  await renderDataSources();
  const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
    node.textContent?.includes("FRED"));
  if (!row) throw new Error("missing FRED provider row");
  expect(row.textContent).toContain("正常");
  expect(row.textContent).toContain("app");
  expect(row.textContent).not.toContain("未啟用抓取");
  expect(row.textContent).not.toContain("已停用");
});
```

- [ ] **Step 2: Add macro snapshot API type**

In `api.ts`:

```ts
export interface MacroSnapshotItem {
  series_id: string;
  label: string;
  title: string | null;
  units: string | null;
  value: number | null;
  observation_date: string | null;
  fetched_at: string | null;
  realtime_start: string | null;
  realtime_end: string | null;
}

export interface MacroSnapshot {
  available: boolean;
  macro_db: string;
  series_count: number;
  observation_count: number;
  release_dates_count: number;
  latest_fetched_at: string | null;
  auto_refresh_enabled: boolean;
  items: MacroSnapshotItem[];
  missing_series: string[];
}

export function getMacroSnapshot(): Promise<MacroSnapshot> {
  return getJSON<MacroSnapshot>("/macro/snapshot");
}
```

- [ ] **Step 3: Render a compact snapshot panel**

Add state/load in `DataSourcesSection` alongside health/schedule/config. Keep layout dense and table-like; no marketing card.

Recommended rendering:

- Title: `FRED 本地快照`
- Summary line:
  - available: `11 序列 · 29,571 觀測值 · 最後抓取 2026-06-25 · 自動刷新關閉`
  - unavailable: `尚無本地快照 · 自動刷新關閉`
- Table columns: `指標`, `值`, `觀測日`, `抓取時間`.
- Display only first 8-11 items; no horizontal overflow. Cells must wrap long titles.

Do not show Finnhub calendars in this panel.

- [ ] **Step 4: Make Provider health detail visible**

The existing Provider table only exposes `p.detail` via `title`. Add a small detail line for FRED in the provider cell or detail column:

```tsx
{p.id === "fred" && (
  <div className="muted tiny">
    本地快照可用 · 自動刷新未啟用
  </div>
)}
```

Prefer deriving counts from `p.signals.local_snapshot` when present:

```tsx
const snap = fredSnapshotFromSignals(p.signals);
```

Keep the helper defensive (`unknown` input), not a cast-heavy component.

- [ ] **Step 5: Retire old special label**

`providerHealthStatusLabel()` may keep generic disabled mapping, but the FRED-specific `macro_ingestion_disabled` path should no longer be used by the main FRED state. Either remove it or leave a backward-compatible test that proves legacy disabled maps to a less prominent label. The key UI test is that the live FRED mock no longer contains "未啟用抓取".

Run:

```bash
cd apps/arkscope-web
npm test -- SettingsProviderConfig.test.ts marketDataDisplay.test.ts --runInBand
npm run build
```

If this repo's Vitest command differs, use the established local command from recent frontend slices.

## Task 6: Focused Integration + Full Regression Gate

Run focused backend suites:

```bash
pytest tests/test_macro_calendar_read.py tests/test_provider_health.py tests/test_pg_unreachable_e2e.py -q
pytest tests/test_fred_ingestion.py tests/test_macro_calendar_settings_route.py -q
```

Expected:

- `tests/test_fred_ingestion.py` remains green; jobs are still feature-gated.
- `tests/test_macro_calendar_settings_route.py` remains green; status/settings are still ungated.
- `tests/test_pg_unreachable_e2e.py` includes `macro_snapshot` and remains PG-clean.

Run focused frontend suites:

```bash
cd apps/arkscope-web
npm test -- SettingsProviderConfig.test.ts SettingsPostPgExitStorage.test.ts marketDataDisplay.test.ts --runInBand
npm run build
```

Run full A/B:

- Base = plan merge base.
- Head = implementation branch.
- Failure set must be identical, except for deliberate flips in tests named in this plan. Any new deterministic failure blocks merge.

## Task 7: Live Smoke / Manual Verification

After merge to master, with the sidecar/app running:

1. `GET /providers/health`
   - FRED key source is `app` or `env`.
   - FRED does not report `disabled_reason="macro_ingestion_disabled"`.
   - `signals.local_snapshot.observation_count` matches the local DB (currently expected around `29,571`).
   - `signals.auto_refresh_enabled=false` is visible.
2. `GET /macro/snapshot`
   - `available=true` on the primary machine.
   - `items` contains `FEDFUNDS`, `DGS10`, `DGS2`, `CPIAUCNS`, `UNRATE`, `VIXCLS`.
   - Every item has `observation_date` and `fetched_at`.
3. `GET /macro/series/FEDFUNDS?limit=1`
   - 200 even when `macro_calendar.enabled=false`.
   - Observation row includes `fetched_at`.
4. `python -m scripts.smoke.pg_unreachable_e2e`
   - `ok:true`, `pg_attempts:[]`.
   - `macro_snapshot` check is 200.
5. Data Sources UI:
   - FRED row reads as configured/local snapshot, not disabled.
   - Snapshot panel visible and does not overflow at the current app width.
   - Calendar/Finnhub empty tables are not presented as active data.

## Task 8: Docs Closeout

**Files:**
- Modify `docs/design/MACRO_FRED_PRODUCT_SEMANTICS.md`
- Modify `docs/design/PROJECT_PRIORITY_MAP.md`

Closeout content:

- Mark macro snapshot display as shipped.
- Record live evidence:
  - provider health FRED state
  - snapshot counts
  - `macro_snapshot` PG-unreachable smoke result
- Record that `macro_calendar.enabled` is now refresh/manual-job gating for FRED, not a read gate.
- Queue future decisions:
  - FRED refresh cadence / staleness policy
  - Finnhub economic/earnings calendar enablement
  - C-2/C-3 macro context integration

## Review Gates

1. FRED Provider health no longer displays "未啟用抓取" when a key and local snapshot exist.
2. `GET /macro/snapshot` works with `macro_calendar.enabled=false` and does not create the DB when absent.
3. `GET /macro/series/{series_id}` works with refresh disabled and includes `fetched_at`.
4. `get_macro_value()` works with refresh disabled and includes freshness in found-value output.
5. Calendar/Finnhub routes and `get_economic_calendar()` remain gated or honest-empty; no empty Finnhub tables are presented as live capability.
6. No scheduler source, interval, or auto-refresh behavior is introduced.
7. PG-unreachable E2E remains `pg_attempts=[]` and includes `macro_snapshot`.
8. Frontend Data Sources layout shows snapshot detail visibly, not only in hover text, and does not overflow on the current settings width.
9. Full A/B failure set is identical.

## Stop-Loss Triggers

Stop and ask for review before continuing if any of these happens:

- Opening FRED reads requires changing job scheduling or real provider calls.
- `macro_calendar.enabled=false` cannot be separated from calendar routes without large route rewrites.
- `get_macro_value()` needs a DAL shape that would revive PostgreSQL assumptions.
- PG-unreachable smoke records any `psycopg2.connect` attempt.
- Frontend needs a broader Settings layout redesign beyond the FRED snapshot panel and provider row copy.
