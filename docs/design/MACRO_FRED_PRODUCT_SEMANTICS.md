# Macro / FRED Product Semantics — Decision Document

- **Date:** 2026-07-05
- **Status:** DRAFT — awaiting user ruling on §6. **This document implements nothing.**
- **Queue authority:** `PROJECT_PRIORITY_MAP.md` queued "FRED product semantics decision doc" after the PG-exit close (§10, 2026-07-05 entries). The standing rule for this item: decision document ONLY; no implementation until a real consumer exists.
- **Predecessors:** `P1_2_SPEC.md` (+ `P1_2_PROVIDER_DISCOVERY.md`) — the layer's design, written 2026-04-26, six days before the 2026-05-02 product pivot; `DESKTOP_APP_CARRYOVER_ANALYSIS.md` — post-pivot preservation ruling.

---

## 1. The question

Post-pivot (local-first research workbench), what is the **product role** of the macro/calendar layer (FRED series + Finnhub economic/earnings/IPO calendars)? Today it is fully built, locally stored, recently fed on one side — and switched off at every product surface. That combination is stable but semantically undefined: every adjacent slice (S-J provider health, PG-unreachable E2E, Data Sources UI) has had to hand-craft a special case for "FRED: built, keyed, disabled, not broken". This document defines the semantics once so future slices stop paying that tax.

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

**D. Dormant-capability semantics with named wake triggers (recommended).** Keep the layer exactly as it is — built, keyed, off — but *define* that state and its exit conditions in writing, so it is a decision rather than an ambiguity.

## 6. Recommendation (awaiting ruling)

Adopt **D** with the following semantics:

1. **Product role (post-pivot):** macro/FRED is a **research-context layer** — dormant capability of the locked layer-4 architecture. It is NOT a signal/backtest layer; P1.2's vintage/revision machinery stays dormant with it (kept because removal buys nothing and the carryover lock protects it, not because a backtest consumer is expected).
2. **Dormant-state contract:** flag stays default-off; tools keep refusing with the disabled error; Data Sources keeps 「未啟用抓取」; provider-health keeps `disabled` outranking config errors; the frozen data (FRED @ 2026-06-25, IPO @ 2026-06-24, economic/earnings empty) stays in place with **no refresh obligation**. Manual `POST /jobs/run/…` remains available for ad-hoc refresh without any semantics change.
3. **Wake triggers (any one suffices to open an enablement slice):**
   - a C-2 research workflow demonstrably degraded by missing macro context (a real transcript where the agent needed CPI/FFR/calendar data and had to refuse), or
   - C-3 ticker-detail design names macro context as a section, or
   - the user states a direct research need for the series/calendars.
4. **Enablement contract (when woken):** the first slice is **freshness/ops semantics, not architecture** — staleness display, refresh cadence (manual-job cadence may suffice; a scheduler source is optional), and scoping WHICH sub-domains wake (FRED series alone is the cheap core; the never-run Finnhub economic/earnings calendars are a separate decision with their own backfill cost). Consumer named first, per the standing rule.
5. **Dormancy expiry:** if no wake trigger fires by **end of 2026-Q4**, revisit retirement (option B) as a deliberate agenda item WITH the carryover-lock amendment — dormancy is a parking state with an expiry, not a forever-limbo.
6. **Dead-code sweep guardrail:** the sweep must treat `src/macro_calendar/`, the two agent tools, `/macro/*` routes, and `scripts/p1_2/` as **protected dormant capability** (hard-lock #5), not dead code — sweep scope explicitly excludes them.

## 7. Non-goals now

- No `macro_calendar.enabled=true` flip, no scheduler source, no UI surface, no new providers, no Finnhub calendar backfill, no vintage/as_of consumer work.
- No change to provider-health/E2E semantics (already correct for the dormant state).

## 8. Decision log

- *(awaiting user ruling on §6)*
