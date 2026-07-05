# Macro / FRED Product Semantics — Decision Document

- **Date:** 2026-07-05
- **Status:** **RULED 2026-07-05 (§8)** — semantics adopted: *readable local snapshot, refresh disabled* (§6). Implementation is a separate follow-up slice with its own plan; **this document itself implements nothing.**
- **Queue authority:** `PROJECT_PRIORITY_MAP.md` queued "FRED product semantics decision doc" after the PG-exit close (§10, 2026-07-05 entries).
- **Predecessors:** `P1_2_SPEC.md` (+ `P1_2_PROVIDER_DISCOVERY.md`) — the layer's design, written 2026-04-26, six days before the 2026-05-02 product pivot; `DESKTOP_APP_CARRYOVER_ANALYSIS.md` — post-pivot preservation ruling.

---

## 1. The question (reframed at ruling)

The draft framed this as "what is the product role of the macro layer — keep dormant or retire?". The user's ruling reframed it: **that was never the question.** The FRED key is configured, the provider is free, and 29k observations of useful data sit locally — the actual problem is that the app *displays and gates* all of that as if it were unusable. The Data Sources row collapses **three orthogonal states into one**:

1. **Provider/key state** — is the FRED key configured and working? (Yes.)
2. **Local data state** — is there usable data, and how fresh is it? (Yes — snapshot @ 2026-06-25.)
3. **Auto-refresh / ingestion enablement** — is scheduled fetching turned on? (No — and that is fine.)

Today 「未啟用抓取」 is literally a statement about axis 3, but the UI renders it where axes 1 and 2 should be visible, so a configured provider with real local data reads as "not usable". The question this document answers: **what are the correct product semantics for these three axes, and what should the app display and let the user/agent use?**

A code fact makes the answer cheap: `macro_calendar_enabled` today gates only the READ surfaces (two agent tools + `/macro/*` payload routes). The scheduler has no macro source at all — ingestion is manual-jobs-only — so opening reads creates **zero refresh obligation**. "Readable snapshot with refresh off" is the natural shape of the existing code, not a compromise.

## 2. Grounded inventory (verified 2026-07-05)

| Facet | State |
|---|---|
| Code | **Complete through P1.2**: `src/macro_calendar/` (FRED + Finnhub ingestion with append-only revision logs), `data_sources/fred_client.py`, storage layer, `src/service/macro_calendar_health.py`, `/macro/*` routes, 2 read-only agent tools (`get_economic_calendar`, `get_macro_value`) registered in the registry + both bridges |
| Storage | Local `data/macro_calendar.db` (PG `macro_*`/`cal_*` were **empty** and dropped in N9 batch-1; local store is the only store, `_local_macro_enabled()` collapsed to `True`) |
| Data — FRED series | **29,571 observations / 11 core series** (CPIAUCNS, CPILFESL, DGS10, DGS2, FEDFUNDS, GDP, GDPC1, PAYEMS, T10Y2Y, UNRATE, VIXCLS) + 4,659 release dates; last fetched **2026-06-25** |
| Data — Finnhub calendars | economic events **0**, earnings events **0** (never ran); IPO events 86 (last fetched 2026-06-24) |
| Ingestion trigger | **Manual jobs only** (`POST /jobs/run/…`, P1.2 commits 4+6). No scheduler source; the scheduler's seven sources contain no macro entry |
| Product gate | `macro_calendar.enabled` (AgentConfig default **False**; `config/user_profile.yaml` has **no** `macro_calendar` block) → both agent tools and `/macro/*` payload routes refuse with a disabled error |
| Provider key | `fred.api_key` is a managed FieldDef, configured (`effective_source=app`, S-J live check 8/8) |
| UI | No macro surface. Only the Data Sources provider row: FRED shows 「未啟用抓取」 (`disabled_reason=macro_ingestion_disabled`) |
| Encoded semantics already shipped | Provider health: `disabled` **outranks** `not_configured`/`missing_key` (a switched-off provider is not an error). PG-unreachable E2E: macro 503-with-disabled-detail is an explicitly allowed state |

**Net state:** a finished, tested, locally-cutover data layer whose FRED half was fed as recently as ten days ago, sitting behind a default-off product flag, with **zero consumers** — the two agent tools are the only would-be readers and they are gated off.

## 3. What changed since P1.2 was designed

P1.2's defining sophistication — append-only revision logs, ALFRED vintages, `as_of` semantics — exists to prevent **lookahead bias in backtests**. That consumer class died with the pivot: the RL line is paused (agent-facing RL tools removed 2026-06-03), signal validation and factor work are explicit non-goals of the workbench v1, and no backtest surface exists or is planned. What survives the pivot is the *mundane* half of the layer's value: **research context** — "CPI prints tomorrow", "FFR is 5.33", "the 10y-2y spread inverted" — as evidence for the AI research surface (C-2) and, later, ticker-detail context (C-3). That value needs the series/calendar data and the two read-only tools; it does not need vintage replay.

## 4. Constraints on the decision

1. **Carryover hard-lock #5** (`DESKTOP_APP_CARRYOVER_ANALYSIS.md`): macro is on the "what survives unchanged" list; `macro_calendar_tools.py` is ruled **preserve-adapt**, and FRED is named a locked layer-4 source of the workbench architecture. Any option that deletes capability requires an explicit lock amendment — it cannot happen as a side effect of a cleanup slice.
2. **Consumer-first rule** (user, standing): no implementation effort without a named consumer. FRED is free, so the research-subscription cost gate does not apply — but the attention/ops gate does: an enabled ingest is a freshness responsibility (staleness display, refresh cadence, failure surfacing).
3. **Honest-state discipline** (post-PG-exit convention): surfaces must not lie. If data is frozen, a consumer-facing surface must say so; "disabled" must keep meaning *product choice*, not *broken*.

## 5. Options

**A. Status quo, undocumented (do nothing).** Zero cost today. But the semantics stay undefined — the exact tax this document exists to end — and the 29k rows age silently with no stated policy. Rejected as the *deliberate* choice; it is only acceptable as the accidental one.

**B. Retire the layer (remove tools/routes, archive the DB).** Buys almost nothing — the code is small, tested, and stable; the data is 3 MB-scale — and it violates carryover hard-lock #5 without a compelling reason to amend it. If a future quarter concludes macro will never serve the workbench, this becomes the right move *via* a lock amendment. Not now.

**C. Enable now (flip `macro_calendar.enabled=true`, define cadence, wire the research surface).** This is implementation without a consumer: nothing in C-2 today asks macro questions that fail, no user workflow has surfaced the need, and enabling creates an ops obligation (freshness, cadence, calendar backfill for the two never-run Finnhub domains). Premature under the consumer-first rule.

**D. Dormant-capability semantics with named wake triggers (the draft's recommendation).** Keep the layer built-keyed-off but define the state and its exit conditions in writing.

> §5's option space (A–D) is preserved as the draft's reasoning record. The ruling **superseded D** with the reframed semantics below: D still treated "off" as the resting state and made reads wait for a wake trigger; the ruling observed that the user IS the consumer, the data is real, and only the *refresh* axis should rest.

## 6. ADOPTED semantics — readable local snapshot, refresh disabled (ruled 2026-07-05)

1. **Three-axis model (the core fix).** Provider/key state, local-data state, and refresh enablement are three independent axes and must never again be collapsed into one displayed status. For FRED today: provider **已設定/可用** · local snapshot **available** (11 core series, 29,571 observations, last fetched 2026-06-25) · auto-refresh **off** (an ops state, NOT a provider-disabled state).
2. **Reads open, honestly labeled.** The app may read and display the local snapshot even with refresh off. Every displayed value carries `observation_date` + `fetched_at` so snapshot data never masquerades as live data. Staleness is information, not an error.
3. **Display contract (Data Sources row).** Target copy shape:
   > FRED · 已設定 · 本地快照可用
   > 11 個核心序列，最後更新 2026-06-25；自動刷新未啟用
   「未啟用抓取」 as the *headline* status is retired — it described axis 3 while occupying the slot users read as axes 1+2.
4. **What surfaces first (the named follow-up slice, "macro snapshot display"):**
   - **Macro Snapshot** display: Fed Funds, 10Y / 2Y, 10Y−2Y spread, CPI / Core CPI, Unemployment, Payrolls, GDP, VIX — each with observation date + fetched-at.
   - **Agent value lookup** (`get_macro_value`) usable, so research answers can cite "FFR / CPI / yield spread per the local snapshot (as of …)".
   - **FRED release dates** = a *candidate* "release schedule" surface — decided within the slice, not committed here.
   - **Finnhub economic/earnings calendars stay OUT** — both tables are empty (never ran); surfacing them would be dishonest until a deliberate backfill decision.
5. **Refresh stays off; manual jobs remain.** No scheduler source, no cadence obligation. `POST /jobs/run/…` remains the ad-hoc refresh path. *Refresh enablement* (cadence, staleness thresholds, which sub-domains auto-update) is a separate, consumer-gated future decision — the P1.2 vintage/revision machinery stays dormant with it.
6. **Gate mechanics belong to the implementation plan.** The current single flag (`macro_calendar_enabled`) conflates the axes; the slice decides whether to re-scope it to mean "auto-refresh enabled" (reads always-on) or flip-plus-label. Constraint either way: provider-health/E2E must keep "refresh off" ≠ "provider broken" (the existing `disabled`-outranks discipline generalizes to the new wording).
7. **Dead-code sweep guardrail (unchanged from draft):** `src/macro_calendar/`, the two agent tools, `/macro/*` routes, and `scripts/p1_2/` are **protected capability** (carryover hard-lock #5) — not dead code. The sweep MAY fix stale copy inside them (e.g. `macro_calendar_tools.py` still says "requires PostgreSQL DAL backend") but must not remove capability.

## 7. Non-goals now

- No scheduler source, no refresh cadence, no new providers, no Finnhub economic/earnings calendar backfill, no vintage/`as_of` consumer work.
- No further provider-health/E2E semantic change beyond the display re-labeling in §6.3 (mechanics per §6.6).

## 8. Decision log

- **2026-07-05 (user ruling):** Facts of §2 independently verified GREEN (DB counts, flag default, scheduler absence, gating, carryover lock all reproduced). Draft recommendation D **superseded**: the question was reframed from "keep dormant vs retire" to "why does a configured, free, data-rich provider display as unusable — and what should the app show and let be used?". Adopted: **readable local snapshot, refresh disabled** (§6) — three-axis display decomposition, reads open with staleness honesty, refresh stays off, Finnhub calendars excluded, follow-up implementation slice named ("macro snapshot display"). Non-blocking note routed to the dead-code/copy sweep under §6.7's protection boundary: stale "requires PostgreSQL DAL backend" wording in `macro_calendar_tools.py`.
