# Investment Profile Track A Implementation Plan

> **Status: REVIEW DRAFT (2026-07-06).** Built from
> `docs/design/INVESTMENT_SKILLS_PROFILE_DESIGN.md` after review commit `cc0c71e`.
> Track A implements only v1 Investor Profile + Assistant Stance. It does **not**
> implement holdings, alerts, research-notes product expansion, skill suggestions, or
> auto-trigger.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in Investor Profile + Assistant Stance to workbench research surfaces,
with explicit run trace and no hidden evidence filtering.

**Architecture:** Store the durable profile in the existing local `profile_state.db`
using a new focused store (`src/investor_profile.py`), not by expanding the already-large
`ProfileStateStore`. API routes expose default-disabled reads, deterministic draft
normalization, and gated writes. Workbench AI Research and AI Card synthesis resolve a
compact personalization context only when enabled; EvidencePacket gathering remains
unchanged and profile/stance metadata is persisted with generated runs/messages.

**Tech Stack:** Python 3, stdlib SQLite, FastAPI handler-direct tests (no TestClient),
Pydantic, pytest, React/Vite/Vitest/TypeScript.

---

## Deferred Product Dependencies

These are real product surfaces, but they are **not** prerequisites for Track A:

- **Holdings:** ProductSpec locks Holdings as IBKR-first/broker-authoritative, not a
  manual portfolio mock. Track A asks about concentration, horizon, and drawdown tolerance
  without syncing real positions. Real position/cash/options context is a later IBKR
  holdings slice.
- **Alerts:** alerts should consume profile/stance and later holdings/signals. Track A does
  not create alert rules.
- **Research notes:** ticker notes and memory/report tools already exist. Track A adds run
  trace metadata only; a fuller research-notes browser/lifecycle remains separate.

## Open Questions Resolved for Track A

The design doc §13 leaves five planning questions. Track A locks them as follows:

1. **Store owner:** create `src/investor_profile.py` with its own
   `InvestorProfileStore`, sharing the same `profile_state.db` path via a new API
   dependency. Do not extend `src/profile_state.py`.
2. **Preset set:** support the full enum (`growth`, `value`, `momentum`, `income`,
   `event_driven`, `balanced`, `custom`) in schema/API, but ship the setup UI with
   **Growth Investor** as the first-class default path. Other presets are stored labels,
   not separate inference engines.
3. **Freeform calibration:** no LLM in Track A setup. Save raw notes and run deterministic
   normalization/mismatch derivation. LLM-assisted calibration is a future opt-in follow-up.
4. **Stance surface:** Settings owns the durable default; AI Research and AI Card own
   per-run override controls. If personalization is disabled, effective stance is `off`.
5. **Export/import:** defer to the profile-portability track. The new tables live in
   `profile_state.db`, so future export can include them without a format migration.

## Grounding

- `src/profile_state.py` owns watchlists/tags/notes/settings and already creates
  `profile_state.db`. Do not make it larger.
- `src/api/permissions.py` exposes `require_profile_state_write`; profile creation/update
  must call it before saving.
- `src/api/routes/query.py` is the workbench AI Research route. Existing tests call handler
  functions directly with temp stores; keep that shape.
- `src/api/routes/analysis_cards.py` calls `gather_evidence(...)` before `synthesize_card(...)`.
  Track A may pass profile context to synthesis only, never to `gather_evidence`.
- `src/card_runs.py` stores generated AI card runs in `ai_card_runs`.
- `src/research_threads.py` stores research messages; `src/research_runs.py` stores
  server-owned run metadata/events.
- `apps/arkscope-web/src/AICard.tsx` is the AI Card run surface.
- `apps/arkscope-web/src/Research.tsx` is the AI Research composer.
- `apps/arkscope-web/src/Settings.tsx` is already large; create a focused
  `InvestorProfilePanel.tsx` and import it rather than adding another large inline block.

## Non-Goals

- No embedded advisor/suitability engine.
- No auto-trading.
- No skill suggestion or auto-application in Track A.
- No deletion or migration of `config/skills/`.
- No holdings sync, alert rules, or research-notes browser expansion.
- No EvidencePacket filtering, re-weighting, or gather-stage profile influence.
- No default-on personalization.
- No changes to legacy CLI/Discord auto-apply behavior beyond evidence capture and Track B
  handoff notes.

## Preflight (No Commit)

- [ ] Run the legacy auto-apply inventory:

```bash
rg -n "build_auto_apply_context|match_skill_trigger|can_auto_apply" src/agents src/monitor scripts apps tests --glob "*.py" --glob "*.tsx" --glob "*.ts"
```

Expected current-state shape:

- `src/agents/cli.py` has legacy implicit auto-apply.
- `src/monitor/discord_bot.py` has legacy implicit auto-apply.
- workbench routes (`src/api/routes/query.py`, `src/api/routes/analysis_cards.py`) have no
  trigger matching.

- [ ] Run the Discord live-surface check:

```bash
rg -n "discord_bot|DISCORD|Discord|monitor_service|discord" README.md docs src scripts tests --glob "*.py" --glob "*.md" --glob "*.sh"
```

Expected: record whether any current launcher/config still starts `src/monitor/discord_bot.py`.
If a live launcher exists, Track A implementation may continue, but Track B must bring it
under `skill_mode`. If no launcher exists, closeout docs should mark Discord as likely
pre-pivot/unreachable pending Track B retirement.

Stop if workbench route paths already use skill triggers; that invalidates the design's
`off = current workbench behavior` premise.

## Task 1 — Investor Profile Store

**Files:**

- Create: `src/investor_profile.py`
- Create: `tests/test_investor_profile.py`

**Schema:**

Create one singleton row:

```sql
CREATE TABLE IF NOT EXISTS investor_profile (
    id                       TEXT PRIMARY KEY CHECK (id = 'default'),
    enabled                  INTEGER NOT NULL DEFAULT 0,
    primary_preset            TEXT NOT NULL DEFAULT 'growth',
    risk_appetite             INTEGER,
    risk_capacity             INTEGER,
    risk_mismatch             TEXT NOT NULL DEFAULT 'unclear',
    holding_horizon           TEXT NOT NULL DEFAULT 'mixed',
    drawdown_tolerance_pct    REAL,
    concentration_limit_pct   REAL,
    preferred_edge_json       TEXT NOT NULL DEFAULT '[]',
    avoidances_json           TEXT NOT NULL DEFAULT '[]',
    behavioral_flags_json     TEXT NOT NULL DEFAULT '[]',
    freeform_notes            TEXT NOT NULL DEFAULT '',
    default_stance            TEXT NOT NULL DEFAULT 'complementary',
    skill_mode                TEXT NOT NULL DEFAULT 'off',
    last_reviewed_at          TEXT,
    updated_at                TEXT NOT NULL
);
```

**Constants:**

```python
PRESETS = ("growth", "value", "momentum", "income", "event_driven", "balanced", "custom")
STANCES = (
    "off",
    "neutral",
    "aligned",
    "complementary",
    "strict_risk_control",
    "valuation_rationalist",
    "growth_opportunity",
)
SKILL_MODES = ("off", "suggest_only")  # auto_with_trace is Track C, not Track A.
RISK_MISMATCHES = ("none", "appetite_above_capacity", "capacity_above_appetite", "unclear")
```

**Required public API in `src/investor_profile.py`:**

```python
@dataclass
class InvestorProfile:
    enabled: bool
    primary_preset: str
    risk_appetite: int | None
    risk_capacity: int | None
    risk_mismatch: str
    holding_horizon: str
    drawdown_tolerance_pct: float | None
    concentration_limit_pct: float | None
    preferred_edge: list[str]
    avoidances: list[str]
    behavioral_flags: list[str]
    freeform_notes: str
    default_stance: str
    skill_mode: str
    last_reviewed_at: str | None
    updated_at: str | None

def default_profile() -> InvestorProfile:
    """Return the disabled Growth-Investor default profile."""

def derive_risk_mismatch(risk_appetite: int | None, risk_capacity: int | None) -> str:
    """Return one of RISK_MISMATCHES from appetite/capacity values."""

def normalize_profile_payload(payload: dict, *, existing: InvestorProfile | None = None) -> InvestorProfile:
    """Validate, clamp/normalize lists, and derive risk_mismatch."""

def effective_stance(profile: InvestorProfile, override: str | None = None) -> str:
    """Return 'off' when disabled, else a validated override/default stance."""

def personalization_trace(profile: InvestorProfile, override: str | None = None) -> dict:
    """Return the persisted run-trace dict used by card/research records."""

def build_personalization_context(profile: InvestorProfile, override: str | None = None) -> str:
    """Return the compact prompt block, or '' when disabled/effective stance off."""

class InvestorProfileStore:
    def __init__(self, db_path: str | Path):
        """Create/upgrade the investor_profile table in profile_state.db."""

    def get(self) -> InvestorProfile:
        """Read the singleton profile or return default_profile()."""

    def draft(self, payload: dict) -> InvestorProfile:
        """Normalize payload without writing it."""

    def save(self, payload: dict) -> InvestorProfile:
        """Normalize and upsert the singleton profile."""
```

**Behavior locks:**

- `get()` returns `default_profile()` if no row exists.
- `default_profile().enabled is False`.
- If `enabled=False`, `effective_stance(...) == "off"` even if `default_stance` is saved as
  another value.
- If profile is disabled, `build_personalization_context(...) == ""`.
- `personalization_trace(...)` always returns:

```python
{
    "profile_active": bool,
    "assistant_stance": str,
    "skill_mode": str,
    "suggested_skills": [],
    "applied_skills": [],
}
```

- `suggested_skills` and `applied_skills` remain empty in Track A.
- `derive_risk_mismatch(8, 4) == "appetite_above_capacity"`.
- `derive_risk_mismatch(3, 7) == "capacity_above_appetite"`.
- Missing appetite/capacity yields `"unclear"`.
- Small differences yield `"none"`.
- Clamp risk scores to 1-10 or raise `ValueError`; do not silently store 99.

**Tests:**

- `test_default_profile_is_disabled_and_context_empty`
- `test_round_trip_profile_and_json_fields`
- `test_risk_mismatch_derivation`
- `test_disabled_profile_forces_effective_stance_off`
- `test_enabled_profile_context_contains_stance_and_no_evidence_language`
- `test_rejects_invalid_stance_or_skill_mode`

Run:

```bash
pytest tests/test_investor_profile.py -q
```

Commit:

```bash
git add src/investor_profile.py tests/test_investor_profile.py
git commit -m "feat: add investor profile store"
```

## Task 2 — Investor Profile API Routes

**Files:**

- Modify: `src/api/dependencies.py`
- Create: `src/api/routes/investor_profile.py`
- Modify: `src/api/app.py`
- Create: `tests/test_investor_profile_routes.py`

**Dependency:**

Add:

```python
@lru_cache(maxsize=1)
def get_investor_profile_store():
    from src.investor_profile import InvestorProfileStore
    return InvestorProfileStore(_local_state_db_path())
```

**Routes:**

Create router with:

- `GET /profile/investor`
- `POST /profile/investor/draft`
- `PUT /profile/investor`

Response shape:

```json
{
  "profile": {
    "enabled": false,
    "primary_preset": "growth",
    "risk_appetite": null,
    "risk_capacity": null,
    "risk_mismatch": "unclear",
    "holding_horizon": "mixed",
    "drawdown_tolerance_pct": null,
    "concentration_limit_pct": null,
    "preferred_edge": [],
    "avoidances": [],
    "behavioral_flags": [],
    "freeform_notes": "",
    "default_stance": "complementary",
    "skill_mode": "off",
    "last_reviewed_at": null,
    "updated_at": null
  },
  "effective_stance": "off",
  "trace": {
    "profile_active": false,
    "assistant_stance": "off",
    "skill_mode": "off",
    "suggested_skills": [],
    "applied_skills": []
  },
  "context_preview": ""
}
```

Rules:

- `GET` is read-only and does not call `require_profile_state_write`.
- `POST /draft` is read-only deterministic normalization and does not save.
- `PUT` calls `require_profile_state_write("investor_profile_update", {...})` before
  writing.
- Route tests call handlers directly with a temp `InvestorProfileStore`; do not use
  `TestClient`.
- Add router to `src/api/app.py`.

**Tests:**

- `test_get_default_profile_disabled`
- `test_draft_derives_mismatch_without_write_gate`
- `test_put_profile_calls_profile_state_write_and_round_trips`
- `test_put_rejects_invalid_values`
- `test_disabled_profile_response_context_preview_empty`

Run:

```bash
pytest tests/test_investor_profile.py tests/test_investor_profile_routes.py -q
```

Commit:

```bash
git add src/api/dependencies.py src/api/routes/investor_profile.py src/api/app.py tests/test_investor_profile_routes.py
git commit -m "feat: expose investor profile routes"
```

## Task 3 — Shared Prompt Context and AI Research Injection

**Files:**

- Modify: `src/agents/shared/prompts.py`
- Modify: `src/agents/openai_agent/agent.py`
- Modify: `src/agents/anthropic_agent/agent.py`
- Modify: `src/api/routes/query.py`
- Modify: `src/research_threads.py`
- Modify: `tests/test_research_routes.py`
- Create: `tests/test_personalization_prompt.py`

**Prompt helper behavior:**

Modify `build_system_prompt` signature:

```python
def build_system_prompt(freshness_summary: str = "", personalization_context: str = "") -> str:
```

Append a section only when `personalization_context.strip()` is non-empty:

```text
─── INVESTOR PROFILE / ASSISTANT STANCE ───

[Investor Profile]
Primary preset: growth
Risk appetite: high
Risk capacity: medium
Risk mismatch: appetite_above_capacity

[Assistant Stance]
Mode: complementary
Instruction: Counterbalance growth bias. Preserve upside analysis, but explicitly test
valuation, downside, concentration, and invalidation.
```

Off-state acceptance:

```python
assert build_system_prompt() == build_system_prompt(personalization_context="")
```

**Agent function signatures:**

Add optional `personalization_context: str = ""` to:

- `src/agents/openai_agent/agent.py::run_query`
- `src/agents/openai_agent/agent.py::run_query_stream`
- `src/agents/anthropic_agent/agent.py::run_query`
- `src/agents/anthropic_agent/agent.py::run_query_stream`

Only pass the context into `build_system_prompt(...)` / `_build_effective_prompt(...)`.
Do not alter tool lists or history selection.

**Query route request:**

Add to `QueryRequest`:

```python
assistant_stance: Optional[str] = None
```

Resolve profile context inside `query_agent` and `query_agent_stream` using
`get_investor_profile_store`. If the context is empty, do **not** pass a
`personalization_context` kwarg to legacy fake streams; this preserves existing tests and
off behavior. If non-empty, pass `personalization_context=context`.

When a `done` event is observed, attach trace metadata:

```python
event.data["personalization"] = trace
```

Persist the same trace on the assistant message.

**Research message schema:**

Add nullable JSON column:

```sql
personalization_json TEXT
```

Add `personalization: Optional[dict] = None` to `ResearchMessage` and
`ResearchThreadStore.append_message(...)`.

Migration rule: add the column idempotently in `_ensure_schema`; old rows read with
`personalization=None`.

**Tests:**

- `tests/test_personalization_prompt.py::test_empty_context_keeps_system_prompt_byte_identical`
- `tests/test_personalization_prompt.py::test_context_appends_after_base_prompt`
- `tests/test_research_routes.py::test_query_stream_profile_off_does_not_pass_personalization_kwarg`
- `tests/test_research_routes.py::test_query_stream_enabled_profile_passes_context_and_persists_trace`
- `tests/test_research_threads.py::test_message_personalization_round_trip`

Important assertion for the off case:

```python
def fake_stream(*, question, model, dal, history, max_tool_calls, **kwargs):
    assert "personalization_context" not in kwargs
```

Run:

```bash
pytest tests/test_personalization_prompt.py tests/test_research_threads.py tests/test_research_routes.py -q
```

Commit:

```bash
git add src/agents/shared/prompts.py src/agents/openai_agent/agent.py src/agents/anthropic_agent/agent.py src/api/routes/query.py src/research_threads.py tests/test_personalization_prompt.py tests/test_research_threads.py tests/test_research_routes.py
git commit -m "feat: inject investor stance into research prompts"
```

## Task 4 — AI Card Personalization Metadata

**Files:**

- Modify: `src/card_synthesis.py`
- Modify: `src/card_runs.py`
- Modify: `src/api/routes/analysis_cards.py`
- Modify: `tests/test_card_runs.py`
- Modify: `tests/test_analysis_cards_api.py`

**Synthesis boundary:**

Change `synthesize_card(...)` to accept:

```python
personalization_context: str = ""
```

Pass context only to the LLM synthesis prompt/user message. Do **not** change
`gather_evidence(...)` signature or arguments. Add a test that monkeypatches
`gather_evidence` and proves no profile/stance value reaches it.

Recommended implementation: append the following block after the current
`EvidencePacket` JSON in `_build_user_message(...)`:

```python
if personalization_context.strip():
    parts.append("Synthesis personalization context (emphasis only; does not alter evidence):")
    parts.append(personalization_context.strip())
```

**Card run schema:**

Add columns to `ai_card_runs`:

```sql
profile_active INTEGER NOT NULL DEFAULT 0,
assistant_stance TEXT NOT NULL DEFAULT 'off',
skill_mode TEXT NOT NULL DEFAULT 'off',
suggested_skills_json TEXT NOT NULL DEFAULT '[]',
applied_skills_json TEXT NOT NULL DEFAULT '[]'
```

Add `personalization: dict` to `CardRun`.

Update `CardRunStore.record(..., personalization: Optional[dict] = None)`.

**Route request/response:**

Add to `GenerateBody`:

```python
assistant_stance: Optional[str] = None
```

Resolve context/trace from `InvestorProfileStore`.

Return and persist:

```json
"personalization": {
  "profile_active": true,
  "assistant_stance": "complementary",
  "skill_mode": "off",
  "suggested_skills": [],
  "applied_skills": []
}
```

Also include personalization metadata in `list_cards` and `get_card`.

**Tests:**

- `tests/test_card_runs.py::test_card_run_personalization_defaults_off`
- `tests/test_card_runs.py::test_card_run_personalization_round_trip`
- `tests/test_analysis_cards_api.py::test_generate_card_profile_off_does_not_change_gather_or_synthesis_context`
- `tests/test_analysis_cards_api.py::test_generate_card_enabled_profile_passes_synthesis_context_only`
- `tests/test_analysis_cards_api.py::test_get_card_returns_personalization_metadata`

Run:

```bash
pytest tests/test_card_runs.py tests/test_analysis_cards_api.py tests/test_investor_profile.py -q
```

Commit:

```bash
git add src/card_synthesis.py src/card_runs.py src/api/routes/analysis_cards.py tests/test_card_runs.py tests/test_analysis_cards_api.py
git commit -m "feat: persist investor stance on card runs"
```

## Task 5 — Frontend API and Settings Profile Panel

**Files:**

- Modify: `apps/arkscope-web/src/api.ts`
- Create: `apps/arkscope-web/src/InvestorProfilePanel.tsx`
- Create: `apps/arkscope-web/src/InvestorProfilePanel.test.tsx`
- Modify: `apps/arkscope-web/src/Settings.tsx`

**API types:**

Add:

```ts
export type InvestorPreset = "growth" | "value" | "momentum" | "income" | "event_driven" | "balanced" | "custom";
export type AssistantStance = "off" | "neutral" | "aligned" | "complementary" | "strict_risk_control" | "valuation_rationalist" | "growth_opportunity";
export type SkillMode = "off" | "suggest_only";

export interface PersonalizationTrace {
  profile_active: boolean;
  assistant_stance: AssistantStance;
  skill_mode: SkillMode;
  suggested_skills: string[];
  applied_skills: string[];
}

export interface InvestorProfile {
  enabled: boolean;
  primary_preset: InvestorPreset;
  risk_appetite: number | null;
  risk_capacity: number | null;
  risk_mismatch: "none" | "appetite_above_capacity" | "capacity_above_appetite" | "unclear";
  holding_horizon: string;
  drawdown_tolerance_pct: number | null;
  concentration_limit_pct: number | null;
  preferred_edge: string[];
  avoidances: string[];
  behavioral_flags: string[];
  freeform_notes: string;
  default_stance: AssistantStance;
  skill_mode: SkillMode;
  last_reviewed_at: string | null;
  updated_at: string | null;
}
```

Add functions:

```ts
export function getInvestorProfile(): Promise<InvestorProfileResponse>
export function draftInvestorProfile(profile: Partial<InvestorProfile>): Promise<InvestorProfileResponse>
export function saveInvestorProfile(profile: Partial<InvestorProfile>): Promise<InvestorProfileResponse>
```

Add optional `personalization?: PersonalizationTrace` to `GenerateResult`,
`CardSummary`, and `CardDetail`.

Add optional `assistant_stance?: AssistantStance` to `streamQuery(...)` body and
`generateCard(...)` body.

**Settings panel:**

Create `InvestorProfilePanel` rather than adding a large inline block to `Settings.tsx`.

Panel controls:

- enable personalization checkbox;
- preset select (default Growth Investor);
- risk appetite select 1-10;
- risk capacity select 1-10;
- holding horizon select;
- drawdown tolerance input;
- concentration limit input;
- preferred edge checkbox group;
- avoidances text input (comma-separated);
- behavioral flags checkbox group;
- freeform notes textarea;
- default stance select;
- buttons: `產生設定草稿` and `儲存設定`.

UI copy rule:

- Do not imply financial advice or suitability.
- Show mismatch as a guardrail, e.g. `風險胃納高於承受能力`.
- Skill mode should render as read-only `off` in Track A with a small note that skill
  suggestions are a later track. Do not expose auto-trigger.

**Tests:**

- `InvestorProfilePanel.test.tsx::loads_default_disabled_profile`
- `InvestorProfilePanel.test.tsx::draft_button_posts_profile_without_saving`
- `InvestorProfilePanel.test.tsx::save_button_puts_profile`
- `InvestorProfilePanel.test.tsx::disabled_profile_shows_effective_off`

Run:

```bash
npm run test --workspace apps/arkscope-web -- InvestorProfilePanel.test.tsx
npm run build
```

Commit:

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/InvestorProfilePanel.tsx apps/arkscope-web/src/InvestorProfilePanel.test.tsx apps/arkscope-web/src/Settings.tsx
git commit -m "feat: add investor profile settings panel"
```

## Task 6 — Run-Level Stance Controls and Trace Display

**Files:**

- Modify: `apps/arkscope-web/src/Research.tsx`
- Modify: `apps/arkscope-web/src/AICard.tsx`
- Modify: `apps/arkscope-web/src/api.ts`
- Create: `apps/arkscope-web/src/personalizationDisplay.ts`
- Create: `apps/arkscope-web/src/personalizationDisplay.test.ts`
- Modify: `apps/arkscope-web/src/streamQuery.test.ts`

**Display helper:**

Create:

```ts
export function stanceLabel(stance: AssistantStance): string
export function mismatchLabel(mismatch: InvestorProfile["risk_mismatch"]): string
export function traceSummary(trace: PersonalizationTrace | null | undefined): string | null
```

Labels should be short; avoid explanatory paragraphs in the app UI.

**Research UI:**

- Load `getInvestorProfile()` on mount.
- If profile `enabled=false`, render no stance selector and send no `assistant_stance`.
- If enabled, render a compact stance select near model/effort controls.
- Default selected stance = profile `default_stance`.
- Send `assistant_stance` in `streamQuery(...)`.
- Display assistant message personalization trace when present in persisted message/done data.

**AI Card UI:**

- Load `getInvestorProfile()` on mount of `AICardTab`.
- If enabled, show compact stance select near the question/advanced controls.
- Pass `assistant_stance` to `generateCard(...)`.
- Display trace metadata in `CardView` when present.

**Transport tests:**

Update `streamQuery.test.ts` to assert `assistant_stance` is included when supplied and
absent when not supplied.

**Tests:**

- `personalizationDisplay.test.ts`
- `streamQuery.test.ts`
- If Research/AICard component tests become too mock-heavy, add focused helper tests and
  keep the UI changes small; do not introduce brittle full-page DOM assertions.

Run:

```bash
npm run test --workspace apps/arkscope-web -- personalizationDisplay.test.ts streamQuery.test.ts
npm run build
```

Commit:

```bash
git add apps/arkscope-web/src/Research.tsx apps/arkscope-web/src/AICard.tsx apps/arkscope-web/src/api.ts apps/arkscope-web/src/personalizationDisplay.ts apps/arkscope-web/src/personalizationDisplay.test.ts apps/arkscope-web/src/streamQuery.test.ts
git commit -m "feat: show investor stance on research runs"
```

## Task 7 — Verification Gates and Closeout Docs

**Files:**

- Modify: `docs/design/INVESTMENT_SKILLS_PROFILE_DESIGN.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Optional: memory topic/index if this repo uses the current memory workflow in this
  session.

**Backend focused gates:**

```bash
pytest tests/test_investor_profile.py tests/test_investor_profile_routes.py tests/test_personalization_prompt.py -q
pytest tests/test_research_threads.py tests/test_research_routes.py -q
pytest tests/test_card_runs.py tests/test_analysis_cards_api.py -q
```

**Frontend focused gates:**

```bash
npm run test --workspace apps/arkscope-web -- InvestorProfilePanel.test.tsx personalizationDisplay.test.ts streamQuery.test.ts
npm run build
```

**Standing smoke:**

```bash
python -m scripts.smoke.pg_unreachable_e2e
```

Expected: `ok:true`, `pg_attempts:[]`. If import path has moved to `src.smoke` in the
current checkout, use the standing gate command recorded in
`docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md`.

**Off-byte-identical gate (workbench surface):**

Run a targeted backend test that compares:

- `build_system_prompt()` vs `build_system_prompt(personalization_context="")`;
- query route fake-stream kwargs with profile disabled;
- AI card route fake `synthesize_card` context with profile disabled.

All must be byte-identical/empty. This gate is stricter than full A/B for the core
product promise.

**Full A/B:**

Run the existing virgin archive A/B protocol. Acceptance:

- failure set identical;
- no head-only deterministic failures;
- passed count increases exactly by the net-new test count.

**Docs closeout:**

- Mark Track A as implemented in `INVESTMENT_SKILLS_PROFILE_DESIGN.md` §11.
- Add a newest-first `PROJECT_PRIORITY_MAP.md` §10 decision-log entry:
  - Track A shipped;
  - open questions resolved as above;
  - holdings/alerts/research-notes deferred dependencies recorded;
  - Track B next if skill suggestions are prioritized;
  - Discord legacy auto-apply live/unreachable evidence from Preflight.

Commit:

```bash
git add docs/design/INVESTMENT_SKILLS_PROFILE_DESIGN.md docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: close investor profile track a"
```

## Review Gates

1. `profile.enabled=false` produces no prompt/context changes on workbench AI Research and
   AI Card paths.
2. Profile writes call `require_profile_state_write`; `GET` and `/draft` do not.
3. `gather_evidence(...)` receives no profile/stance parameters and its call shape stays
   unchanged.
4. Persisted run/message metadata contains `profile_active`, `assistant_stance`,
   `skill_mode`, `suggested_skills`, and `applied_skills`.
5. `suggested_skills` and `applied_skills` are always `[]` in Track A.
6. `auto_with_trace` is not user-selectable and is not accepted by the Track A store/API.
7. Frontend does not expose holdings-aware sizing or alert behavior.
8. No TestClient is introduced for these route tests.
9. Discord/CLI legacy auto-apply behavior is documented for Track B; Track A does not
   silently bless it.
10. Full A/B has no new deterministic failures.

## Stop-Loss

- Any code path tries to use Investor Profile inside `gather_evidence` or evidence
  collectors: STOP.
- Any disabled-profile workbench prompt differs from current prompt/request shape: STOP.
- Any route write mutates profile without `require_profile_state_write`: STOP.
- Any implementation starts LLM-based freeform calibration: STOP; Track A explicitly chose
  deterministic draft only.
- Any UI attempts to implement holdings, alerts, research-notes browser, or skill
  suggestions: STOP and split a new plan.
- Any legacy CLI/Discord auto-apply change is needed to keep tests green: STOP and open
  Track B instead of sneaking it into Track A.
