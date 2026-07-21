# P2.8 Slice 5 Investor Profile Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Use
> superpowers:using-git-worktrees before Task 0,
> superpowers:test-driven-development for every behavior change,
> superpowers:requesting-code-review before integration, and
> superpowers:verification-before-completion before any passing or complete
> claim. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** WRITTEN — INDEPENDENT PLAN REVIEW PENDING
>
> The Slice 5 design received independent full-document GREEN at spec commit
> `62d59b93`. The required review pin is part of the approved authority:
> catalog order controls display only, the model may adaptively select only an
> uncovered catalog topic, and an invalid or already-covered `next_topic_id`
> leaves coverage/current unchanged while the turn remains retryable. Product
> implementation is blocked until this plan receives independent written GREEN.

**Goal:** Replace the form-first Investor Profile panel with a bilingual,
summary-first workspace; add a durable guided-calibration protocol whose
proposals can modify only covered fields; and persist the exact personalization
context actually used by each new Research and AI-card run.

**Architecture:** A backend-only policy catalog owns topic order and
topic-to-field eligibility, while a versioned SQLite calibration journal owns
durable turns, coverage, proposals, conflict metadata, and startup recovery.
Provider calls run outside SQLite transactions; pre-call intent and post-call
completion use two short transactions keyed by client `turn_id`. The frontend
keeps one Settings anchor and one controller, splits Summary/Edit/Calibration/
Proposal Review into focused components, and maps closed IDs to bilingual copy
without duplicating backend field policy.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, SQLite, React 18,
TypeScript 5.9, i18next 26.3.6 selector API, react-i18next 17.0.10, Vitest
4/jsdom, pytest, the existing TypeScript-AST visible-literal scanner,
Vite/Electron, and Playwright/CDP against isolated databases.

---

## Design Authority

1. Product/data contract:
   `docs/superpowers/specs/2026-07-22-p2-8-slice-5-investor-profile-workspace-design.md`.
2. Canonical vocabulary: `docs/design/ARKSCOPE_TERMINOLOGY.md`.
3. Settings IA:
   `docs/superpowers/specs/2026-07-19-p2-8-slice-4-1-settings-navigation-correction-design.md`.
4. i18n mechanics:
   `docs/superpowers/specs/2026-07-20-app-wide-i18n-decision.md`.
5. Personalization semantics and evidence boundary:
   `docs/design/INVESTMENT_SKILLS_PROFILE_DESIGN.md`.
6. Product-behavior A/B base: merged product `bca064d4`. The later spec and
   plan-clearance commits are documentation only and do not replace this base.

If this plan conflicts with an authority above, stop and amend the authority
before editing product code.

---

## Grounded Baseline

All values below were reproduced on clean `master` at `62d59b93`.

### Backend

- Full collection: `4569` tests.
- Focused collection: `167` tests across these ten files:

| File | Baseline |
|---|---:|
| `tests/test_investor_profile.py` | 12 |
| `tests/test_investor_profile_routes.py` | 6 |
| `tests/test_investor_profile_calibration.py` | 12 |
| `tests/test_investor_profile_calibration_routes.py` | 8 |
| `tests/test_provider_config_startup.py` | 5 |
| `tests/test_analysis_cards_api.py` | 18 |
| `tests/test_card_runs.py` | 10 |
| `tests/test_research_runs.py` | 23 |
| `tests/test_research_routes.py` | 46 |
| `tests/test_research_threads.py` | 27 |

Grounded defects and seams:

1. `normalize_proposal_payload()` expands a partial model patch into a full
   profile containing `enabled`, `freeform_notes`, and derived
   `risk_mismatch`.
2. `ApproveProposalBody.profile_patch` lets the client replace the stored
   proposal at approval time.
3. the message route commits the user message before waiting on the Provider,
   but owns no durable turn record or idempotency key;
4. `CalibrationStore.__init__()` silently creates/migrates schema;
5. Research calls `mark_running()` before resolving personalization;
6. Research messages persist a trace but `research_runs` do not persist an
   exact context snapshot;
7. card runs persist trace columns but no exact context snapshot; and
8. `resolve_personalization()` reads one profile, but computes context and trace
   as independent values with no persisted exact-context member.

### Frontend

- Full suite: `77 files / 778 tests`.
- Focused baseline used by this plan: `5 files / 59 tests`:
  `InvestorProfilePanel.test.tsx` 13,
  `SettingsWorkspace.test.tsx` 24,
  `i18n/resources.test.ts` 9,
  `ui/classCoverage.test.ts` 3, and
  `i18n/foundationBoundaries.test.ts` 10.
- Settings resources: exactly `623` non-empty leaves per locale.
- Literal scanner: exactly `1033 candidates / 973 signatures / 954 debt /
  20 allowlist`, with `28` migrated scopes.

Grounded defects and seams:

1. `InvestorProfilePanel` renders the full form before calibration and merges a
   pending proposal directly into form state;
2. approval sends the entire current form as `profile_patch`;
3. initial calibration failure is swallowed, so the UI can imply no pending
   proposal when the route merely failed;
4. calibration starts with a blank text area;
5. `SettingsView` infers Investor dirty state from any captured input/change
   and busy state from a DOM `aria-busy` query, so leaving Calibration is
   incorrectly treated like discarding an Edit draft;
6. `ResearchEvidenceDrawer` can read message personalization but not the new
   run-level exact snapshot; and
7. the current `ip-*` CSS family is suitable substrate but has no summary,
   proposal-diff, guided-journal, or mode-header layout.

### Production observation

Read-only production inspection found one active legacy calibration session,
12 messages, one approved proposal, and zero draft proposals. This is a
migration observation only. Tests must construct every legacy shape and must
not pin these counts as acceptance constants.

---

## Locked Decisions

1. Slice 5 keeps exactly one Settings registry anchor: `investor_profile`.
   Summary is the default/reload/exact-anchor destination. Edit, Calibration,
   and Proposal Review are ephemeral modes, not routes, anchors, or nested tabs.
2. Summary presents effective behavior: personalization enabled/disabled,
   effective stance, risk mismatch, calibration status, pending proposal, and
   current exact context. It does not present stored values as if they were
   effective values.
3. Edit preserves every existing profile field and draft/full-save behavior.
   Draft remains in Edit. Full save performs a fresh GET before returning to
   Summary. A failed fresh GET leaves Edit mounted with an honest error.
4. Dirty Edit exit uses the existing value-free `ConfirmDialog`. Calibration
   exit is free because its journal is durable. Save/approve in flight blocks
   mode and Settings-group navigation with `InlineAlert`.
5. Summary says `Start Calibration` only without an active guided session and
   `Continue Calibration` when a resumable session exists. Proposal Review is
   reachable only from a pending-proposal card.
6. The opening question is deterministic, zero-LLM, immediate, and versioned as
   `loss_response.opening.v1`. Store semantic `prompt_id` plus canonical
   fallback content. A known frontend renders its localized resource; an old
   frontend renders canonical fallback content for an unknown ID.
7. After the first user answer, the model asks one question at a time. The
   prompt requests one question but the frontend does not parse or reject
   multi-question prose.
8. Interview order is adaptive within the uncovered topic set. Backend catalog
   order is the sole display order and not a fixed interview script.
9. A returned `addressed_topic_id` must equal the server-selected current topic.
   A returned `next_topic_id` becomes current only when it is a catalog member
   and is not covered after this turn. Invalid/covered IDs end the turn with
   `calibration_catalog_validation_failed`; the answer remains, no assistant
   message/proposal/coverage/current advance occurs, and retry reuses the same
   `turn_id`.
10. Topic coverage is a closed enum and monotonic. The model reports whether
    the current topic was covered; the server validates and commits coverage.
11. Backend policy order is exact:
    `loss_response`, `financial_capacity`, `time_horizon`,
    `single_position_limit`, `risk_avoidances`, `behavioral_patterns`,
    `investment_approach`, `assistant_style`.
12. Backend is the only topic-to-field policy owner. Frontend owns only closed
    topic/prompt/field display mappings. It must not duplicate or infer field
    eligibility.
13. Proposable fields are exactly ten fields covered by the topic matrix.
    Denied fields are exactly `enabled`, `freeform_notes`, and `skill_mode`.
    The matrix union and deny list are disjoint and exactly partition all 13
    `InvestorProfileBody` fields.
14. A proposal is a partial patch. The server drops unknown, denied, derived,
    and uncovered fields. If no legal fields remain, no fake proposal is
    created.
15. Every proposal stores covered topics, normalized partial patch, source
    rationale, and base values for only proposed fields. `proposed_fields` is a
    DTO projection of legal patch keys in backend catalog order, not a second
    persisted authority; existing `changed_fields_json` remains the approval
    audit.
16. Approval accepts an empty body only and always applies the stored patch.
    Client `profile_patch`, extra keys, or replacement fields return `422`.
17. Scalar conflict comparison is exact. `preferred_edge`, `avoidances`, and
    `behavioral_flags` compare as sets so ordering alone cannot create a false
    conflict.
18. Conflict writes no profile field, keeps the proposal `draft`, persists
    conflict metadata, and returns typed `409 proposal_conflict`.
19. Profile merge and proposal approval are one `BEGIN IMMEDIATE` transaction.
    Any failure rolls both back. Reject changes no profile field.
20. `freeform_notes` stays user-authored and never enters prompt context. UI
    copy states that it currently does not affect AI analysis. A future causal
    field may not auto-copy historical notes.
21. Calibration has no tools, evidence retrieval, market/news/web/code access,
    or investment recommendations. It does not pass `ui_locale` to the model.
22. Opening-prompt canonical expansion in model context may use English while
    the frontend displays the current locale. This is intentional; response
    language anchors to the user's answer, not hidden locale injection.
23. Each answer/proposal request has a client `turn_id`. The first short
    transaction stores intent and answer; the Provider call occurs with no
    SQLite write lock; the second short transaction validates and completes.
24. One session may have at most one pending turn. A repeated completed or
    pending `turn_id` never duplicates a user message or Provider call.
25. Startup reconciliation, not GET, converts stale pending turns to
    `interrupted`. Retry is explicit and keeps answer/question/topic identity.
26. Missing credentials use existing typed `provider_config_missing` product
    semantics and an action that reveals the Providers anchor. Raw Provider
    detail remains Developer diagnostics only.
27. Calibration schema migration is an explicit startup phase. Store
    construction and GET never create or migrate tables. Marker/schema
    mismatch fails closed and prevents scheduler startup.
28. Legacy active sessions and legacy draft proposals become `superseded` with
    explicit reasons. Approved/rejected proposals and messages remain
    byte-identical. No coverage/base values are inferred from prose.
29. `resolve_personalization()` computes context and trace from one profile
    object. `trace.context_snapshot` is captured at actual prompt assembly.
30. Research resolves personalization before `queued -> running` and stores
    the trace plus exact context in the same transition. A queued run that never
    starts has `personalization=null`.
31. New disabled/off Research and card runs store `context_snapshot=""`.
    Historical rows with no snapshot return `null`. No historical backfill is
    allowed.
32. Research terminal events/messages reuse the run's persisted trace; they do
    not re-resolve the current profile. Existing stance and exact snapshot
    therefore share one sampling instant.
33. AI cards resolve once immediately before synthesis and persist the same
    trace/context used by synthesis. `gather_evidence()` remains byte-identical
    and receives no personalization.
34. Current Summary context and historical run context are visually and
    textually distinct. Exact context is source content: display byte-for-byte,
    never translate, summarize, or reconstruct it.
35. Evidence Drawer additions use a new `research` i18n namespace. They do not
    enter `settings.*` and do not migrate the Drawer's existing I18N-4 debt.
36. Unknown topic IDs render localized `Other topic`, count toward progress,
    and reveal raw ID only in Developer diagnostics. Topic and prompt ID-set
    tripwires force a synchronized frontend update when backend catalogs grow.
37. All new chrome is bilingual from birth. Model/user answers, rationales,
    custom list values, identifiers, and exact context remain source content.
38. Locale switching preserves mode, dirty Edit draft, calibration journal,
    pending proposal, disclosure state, element identity, and focus. A known
    opening prompt relocalizes in place; source content does not change.
39. No new `aria-live`, Popover, Drawer, nested card, nested tablist, route,
    preference key, polling loop, or language selector is added.
40. Existing formatters, `personalizationDisplay.ts`, `modelRoutingUx.ts`,
    evidence gathering, tools, extensions, schedulers, and unrelated Settings
    sections stay byte-identical.

---

## Backend Contract

### Topic policy

Create `src/investor_profile_calibration_policy.py` as the single policy owner:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CalibrationTopic:
    id: str
    fields: tuple[str, ...]

CALIBRATION_TOPICS = (
    CalibrationTopic("loss_response", ("risk_appetite", "drawdown_tolerance_pct")),
    CalibrationTopic("financial_capacity", ("risk_capacity",)),
    CalibrationTopic("time_horizon", ("holding_horizon",)),
    CalibrationTopic("single_position_limit", ("concentration_limit_pct",)),
    CalibrationTopic("risk_avoidances", ("avoidances",)),
    CalibrationTopic("behavioral_patterns", ("behavioral_flags",)),
    CalibrationTopic("investment_approach", ("primary_preset", "preferred_edge")),
    CalibrationTopic("assistant_style", ("default_stance",)),
)

CALIBRATION_TOPIC_IDS = tuple(topic.id for topic in CALIBRATION_TOPICS)
NEVER_PROPOSABLE_FIELDS = frozenset({"enabled", "freeform_notes", "skill_mode"})
OPENING_PROMPTS = {
    "loss_response.opening.v1": (
        "Imagine a holding you still believe in falls 18% in one day without "
        "a clear change in the business. What would you most likely do next, "
        "and what information would you need before acting?"
    ),
}
OPENING_PROMPT_ID = "loss_response.opening.v1"
```

The module exposes pure `fields_for_topics()`, `clamp_proposal_patch()`,
`validate_addressed_topic()`, and `validate_next_topic()` helpers. Clamp calls
`normalize_profile_payload(raw_legal_patch, existing=current_profile)` and then
extracts only legal keys; normalization may never expand the returned patch.
Rejected field names are audit data, never values.

### Calibration schema v2

Create `src/investor_profile_calibration_schema.py`. It owns component marker
version `2`, exact schema fingerprinting, fresh creation, v1 migration, and
read-only assertion. It must not use global `PRAGMA user_version`.

```sql
CREATE TABLE investor_profile_calibration_schema (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    version     INTEGER NOT NULL,
    applied_at  TEXT NOT NULL
);

-- Additive session columns.
ALTER TABLE investor_profile_calibration_sessions ADD COLUMN interview_version INTEGER;
ALTER TABLE investor_profile_calibration_sessions ADD COLUMN covered_topics_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE investor_profile_calibration_sessions ADD COLUMN current_topic_id TEXT;
ALTER TABLE investor_profile_calibration_sessions ADD COLUMN current_question_message_id TEXT;
ALTER TABLE investor_profile_calibration_sessions ADD COLUMN superseded_reason TEXT;

-- Additive message columns.
ALTER TABLE investor_profile_calibration_messages ADD COLUMN turn_id TEXT;
ALTER TABLE investor_profile_calibration_messages ADD COLUMN topic_id TEXT;
ALTER TABLE investor_profile_calibration_messages ADD COLUMN prompt_id TEXT;
CREATE UNIQUE INDEX idx_calibration_message_turn_role
ON investor_profile_calibration_messages(session_id, turn_id, role)
WHERE turn_id IS NOT NULL;

CREATE TABLE investor_profile_calibration_turns (
    id                   TEXT PRIMARY KEY,
    session_id           TEXT NOT NULL REFERENCES investor_profile_calibration_sessions(id) ON DELETE CASCADE,
    kind                 TEXT NOT NULL CHECK (kind IN ('answer','proposal_request')),
    status               TEXT NOT NULL CHECK (status IN ('pending','completed','failed','interrupted')),
    question_message_id  TEXT,
    addressed_topic_id   TEXT,
    request_proposal     INTEGER NOT NULL DEFAULT 0,
    provider             TEXT,
    model                TEXT,
    user_message_id      TEXT,
    assistant_message_id TEXT,
    next_topic_id        TEXT,
    error_code           TEXT,
    diagnostic           TEXT,
    attempt_count        INTEGER NOT NULL DEFAULT 1,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    completed_at         TEXT
);
CREATE UNIQUE INDEX idx_calibration_one_pending_turn
ON investor_profile_calibration_turns(session_id)
WHERE status = 'pending';

-- Additive proposal columns.
ALTER TABLE investor_profile_calibration_proposals ADD COLUMN covered_topics_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE investor_profile_calibration_proposals ADD COLUMN base_values_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE investor_profile_calibration_proposals ADD COLUMN rejected_fields_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE investor_profile_calibration_proposals ADD COLUMN conflicted_at TEXT;
ALTER TABLE investor_profile_calibration_proposals ADD COLUMN conflict_fields_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE investor_profile_calibration_proposals ADD COLUMN superseded_at TEXT;
ALTER TABLE investor_profile_calibration_proposals ADD COLUMN superseded_reason TEXT;
```

Migration runs under one `BEGIN IMMEDIATE` statement list, rechecks after lock,
and inserts the marker last. Accepted starting states are exactly: no component
tables, exact unmarked v1, or exact marked v2. Any partial v2 artifact, unknown
column/index, wrong marker, or marker/schema disagreement raises
`CalibrationSchemaMismatch` without writing.

Legacy conversion in that transaction is exact:

```sql
UPDATE investor_profile_calibration_sessions
SET status='superseded', updated_at=:now, closed_at=COALESCE(closed_at,:now),
    superseded_reason='legacy_guided_protocol_unavailable'
WHERE status='active';

UPDATE investor_profile_calibration_proposals
SET status='superseded', superseded_at=:now,
    superseded_reason='legacy_proposal_missing_coverage_proof'
WHERE status='draft';
```

The migration does not modify message content, terminal proposal JSON/status,
or synthesize coverage/base values. `CalibrationStore.__init__()` calls only
`assert_calibration_schema_v2(path)` through a read-only SQLite URI and never
creates a directory or DB.

### Durable turn state machine

`CalibrationStore.start_session()` creates an active v2 session plus one
assistant opening message in the same transaction:

```python
CalibrationMessage(
    role="assistant",
    topic_id="loss_response",
    prompt_id=OPENING_PROMPT_ID,
    content=OPENING_PROMPTS[OPENING_PROMPT_ID],
)
```

`begin_answer_turn()` and `begin_proposal_turn()` are caller-idempotent. The
answer path stores one user message and one pending turn in the first short
transaction. A repeated pending ID returns `call_provider=False`; a completed
ID returns the prior state; a failed/interrupted ID is retried only through
`retry_turn()` and never inserts a second answer.

Provider completion input is structured:

```python
@dataclass(frozen=True)
class CalibrationAgentResult:
    assistant_message: str
    addressed_topic_id: str
    topic_covered: bool
    next_topic_id: str | None
    profile_patch: dict | None
    rationales: dict[str, str]
```

`complete_turn()` validates the frozen addressed topic, derives
`covered_after`, validates `next_topic_id` against that set, clamps proposal
fields, and then atomically appends the assistant message, advances coverage /
current question, creates at most one draft proposal, and marks the turn
completed. Catalog validation failure marks only the turn failed with the typed
code and diagnostic; session coverage/current and proposal/message rows do not
advance.

### Approval transaction

Refactor `src/investor_profile.py` to provide caller-owned connection helpers
with exact signatures
`_read_profile_on_connection(conn: sqlite3.Connection) -> InvestorProfile` and
`_write_profile_on_connection(conn: sqlite3.Connection, profile:
InvestorProfile) -> None`.

`InvestorProfileStore.get()` and `save()` use the same helpers. Add a store
write lock so ordinary PUT and proposal approval serialize. Calibration approval
verifies both stores point at the same SQLite file, acquires locks in one fixed
order, opens one connection, runs `BEGIN IMMEDIATE`, reads proposal/current
profile, compares stored base values, writes either conflict metadata or the
partial normalized merge, and commits proposal status with the same connection.

### Personalization snapshot

Add pure single-sample helper:

```python
def personalization_bundle(
    profile: InvestorProfile,
    override: str | None = None,
) -> tuple[str, dict]:
    context = build_personalization_context(profile, override)
    trace = personalization_trace(profile, override)
    return context, {**trace, "context_snapshot": context}
```

`resolve_personalization()` reads one profile and delegates to this helper.
Research adds nullable `personalization_json` to `research_runs` and replaces
`mark_running()` at execution with
`mark_running_with_personalization(run_id, trace)`. This transaction moves only
`queued -> running`, writes `started_at`, and persists the exact trace before
the Provider stream starts. Every terminal event/message uses that same trace.

Card runs add nullable `personalization_context_snapshot TEXT`. New route calls
always pass a trace containing the key; disabled/off stores `""`. Rows created
before Slice 5 or direct legacy fixtures without the key return `null`.

---

## Frontend Contract

### Component ownership

`InvestorProfilePanel.tsx` remains the controller and single request/generation
owner. It accepts:

```ts
export interface InvestorProfilePanelProps {
  developerMode?: boolean;
  onNavigationGuardChange?: SettingsNavigationGuardReporter;
  onNavigateToProviders?: () => void;
  turnIdFactory?: () => string;
}
```

`turnIdFactory` defaults to `crypto.randomUUID`; tests inject a deterministic
factory. Four focused renderers live under `src/settings/investor/`:

- `InvestorProfileSummary.tsx`: effective state, mismatch, calibration/proposal
  status, commands, current-context disclosure;
- `InvestorProfileEdit.tsx`: the complete existing form, draft/full save, risk
  concept disclosure, and non-causal notes help;
- `InvestorProfileCalibration.tsx`: current question, source answer input,
  backend-ordered coverage, journal, retry, and Propose Now;
- `InvestorProfileProposalReview.tsx`: covered-topic chips, ordered current to
  proposed field comparisons, source rationales, conflict, approve/reject.

`investorProfileDisplay.ts` owns closed topic/prompt/field/value display only.
It contains exact literal ID sets and localized fallback logic, but no
topic-to-field mapping. Unknown topic displays `Other topic`, contributes to
counts, and returns raw ID only through a Developer diagnostic value.

### Loading and mode behavior

Initial profile and calibration reads use one generation and independent
`Promise.allSettled` legs. Profile failure is blocking. Calibration failure
keeps Summary usable but renders a partial alert plus retry; it never substitutes
`active_session=null` or `latest_proposal=null`.

Mode is local state initialized to `summary`. Exact-anchor reveal and reload do
not preserve a secondary mode. Entering a mode focuses its heading. Returning
focus targets the command that opened it. Edit stores a baseline profile for
dirty comparison. Calibration never marks Settings dirty. `onNavigationGuardChange`
reports precise Edit dirty/busy state and clears on unmount.

### API shapes

Evolve `api.ts` with stable semantic types:

```ts
export type CalibrationTopicId =
  | "loss_response" | "financial_capacity" | "time_horizon"
  | "single_position_limit" | "risk_avoidances"
  | "behavioral_patterns" | "investment_approach" | "assistant_style";

export interface CalibrationMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  turn_id: string | null;
  topic_id: string | null;
  prompt_id: string | null;
  created_at: string;
}

export interface CalibrationSession {
  id: string;
  status: "active" | "closed" | "superseded";
  interview_version: number | null;
  covered_topics: string[];
  current_topic_id: string | null;
  current_question_message_id: string | null;
  superseded_reason: string | null;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export interface CalibrationTurn {
  id: string;
  session_id: string;
  kind: "answer" | "proposal_request";
  status: "pending" | "completed" | "failed" | "interrupted";
  question_message_id: string | null;
  addressed_topic_id: string | null;
  next_topic_id: string | null;
  error_code: string | null;
  diagnostic: string | null;
  attempt_count: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface CalibrationProposal {
  id: string;
  session_id: string;
  status: "draft" | "approved" | "rejected" | "superseded";
  profile_patch: Partial<InvestorProfile>;
  proposed_fields: string[];
  covered_topics: string[];
  rationales: Record<string, string>;
  conflict_fields: string[];
  created_at: string;
  approved_at: string | null;
  rejected_at: string | null;
  conflicted_at: string | null;
  superseded_at: string | null;
  superseded_reason: string | null;
}

export interface CalibrationState {
  active_session: CalibrationSession | null;
  sessions: CalibrationSession[];
  messages: CalibrationMessage[];
  pending_turn: CalibrationTurn | null;
  latest_proposal: CalibrationProposal | null;
  topic_catalog: string[];
}
```

Approval sends `{}`. Sending an answer includes client `turn_id`; retry sends
only provider/model metadata to the explicit turn endpoint; Propose Now uses a
dedicated endpoint and sends no synthetic user text.

### Settings navigation guard

Delete `investorPotentialDirty`, the investor input/change capture wrapper, and
the investor DOM `aria-busy` query from `Settings.tsx`. Store the reporter value
exactly like the other Settings sections. Pass
`onNavigateToProviders={() => revealSection("providers")}` (using the existing
exact-anchor reveal path) so typed missing-credential recovery changes group,
mounts, focuses, and restores Drawer behavior through one navigation owner.

### Research transparency

Create `ResearchPersonalizationContext.tsx`. `ResearchEvidenceDrawer` chooses
`message?.personalization ?? details?.personalization ?? null` and delegates
only this new block. The component renders:

- `null`: legacy run has no snapshot;
- `context_snapshot === ""`: personalization was disabled for this run;
- non-empty string: exact source text in `<pre>` plus closed stance effect copy.

It never rebuilds context from current profile or translates the source block.

---

## Exact Resource Contract

Settings starts at `623` leaves. Add exactly `94` leaves under
`investor.workspace.*` and remove exactly these five obsolete leaves:

```text
investor.panel.description
investor.fields.enabledWithStance
investor.calibration.description
investor.calibration.messageLabel
investor.calibration.send
```

Final Settings count is `623 + 94 - 5 = 712` leaves per locale.

The 94 additions are fixed by subtree:

| Subtree | Count | Keys / semantics |
|---|---:|---|
| `summary` | 13 | `title`, `description`, `personalizationEnabled`, `personalizationDisabled`, `effectiveStance`, `riskComparison`, `calibrationActive`, `calibrationIdle`, `proposalPending`, `contextTitle`, `contextCurrentNotice`, `contextDisabled`, `contextUnavailable` |
| `mode` | 3 | `edit`, `calibration`, `proposalReview` |
| `actions` | 11 | `edit`, `startCalibration`, `continueCalibration`, `reviewProposal`, `backSummary`, `saveDraft`, `saveProfile`, `saving`, `requestProposal`, `approve`, `reject` |
| `guard` | 5 | `dirtyTitle`, `dirtyDescription`, `stay`, `discard`, `busy` |
| `calibration` | 13 | `title`, `description`, `progress`, `covered`, `current`, `answerLabel`, `answerPlaceholder`, `send`, `sending`, `retry`, `interrupted`, `requestNow`, `noCredential` |
| `proposal` | 10 | `title`, `coverageTitle`, `changesTitle`, `currentValue`, `proposedValue`, `rationaleTitle`, `conflictTitle`, `conflictDescription`, `approved`, `rejected` |
| `context` | 4 | `disclosureTitle`, `explanation`, `exactTitle`, `notesNonCausal` |
| `notes` | 1 | `nonCausalHelp` |
| `disclosures` | 4 | `riskTitle`, `riskBody`, `topicsTitle`, `topicsBody` |
| `effects` | 7 | one exact leaf for every Assistant Stance including `off` |
| `topics` | 16 | `label` and `description` for each of the eight topic IDs |
| `prompts` | 1 | `lossResponseOpeningV1` |
| `errors` | 6 | `profileLoad`, `calibrationLoad`, `save`, `refresh`, `turn`, `proposal` |

Topic labels use the terminology authority exactly:

| ID | en | zh-Hant |
|---|---|---|
| `loss_response` | How you respond to losses | 遇到虧損時怎麼做 |
| `financial_capacity` | What your finances allow | 資金能承受多少 |
| `time_horizon` | How long you invest | 預計持有多久 |
| `single_position_limit` | Single-position limit | 單一持股上限 |
| `risk_avoidances` | Risks you avoid | 不碰哪些風險 |
| `behavioral_patterns` | Behavioral patterns to watch | 容易受哪些行為影響 |
| `investment_approach` | Research approaches you prefer | 偏好的研究方法 |
| `assistant_style` | How you want AI to work with you | 希望 AI 如何配合 |

The localized opening prompt preserves the same scenario meaning, while the
canonical fallback remains the exact English string in the backend policy.
Source answers/rationales are never resource values.

Add a new `research` namespace with exactly five leaves per locale:

```text
personalization.title
personalization.runNotice
personalization.active
personalization.disabled
personalization.unavailable
```

Settings net leaf growth is `+89`; Research growth is `+5`; total bundled net
growth is exactly `+94` per locale. Locale namespace/key sets remain equal and
all leaves remain non-empty.

---

## Exact File Map

### Create: backend

- `src/investor_profile_calibration_policy.py`
- `src/investor_profile_calibration_schema.py`
- `tests/test_investor_profile_calibration_policy.py`
- `tests/test_investor_profile_calibration_migration.py`

### Modify: backend

- `src/investor_profile.py`
- `src/investor_profile_calibration.py`
- `src/investor_profile_calibration_agent.py`
- `src/api/personalization.py`
- `src/api/dependencies.py`
- `src/api/app.py`
- `src/api/routes/investor_profile_calibration.py`
- `src/research_runs.py`
- `src/research_run_manager.py`
- `src/api/routes/research.py`
- `src/research_threads.py`
- `src/card_runs.py`
- `src/api/routes/analysis_cards.py`
- the ten focused backend tests listed in the baseline table

### Create: frontend

- `apps/arkscope-web/src/settings/investor/InvestorProfileSummary.tsx`
- `apps/arkscope-web/src/settings/investor/InvestorProfileEdit.tsx`
- `apps/arkscope-web/src/settings/investor/InvestorProfileCalibration.tsx`
- `apps/arkscope-web/src/settings/investor/InvestorProfileProposalReview.tsx`
- `apps/arkscope-web/src/settings/investor/investorProfileDisplay.ts`
- `apps/arkscope-web/src/settings/investor/investorProfileDisplay.test.ts`
- `apps/arkscope-web/src/InvestorProfileApi.test.ts`
- `apps/arkscope-web/src/ResearchPersonalizationContext.tsx`
- `apps/arkscope-web/src/ResearchPersonalizationContext.test.tsx`
- `apps/arkscope-web/src/InvestorProfileCss.test.ts`
- `apps/arkscope-web/src/i18n/resources/en/research.ts`
- `apps/arkscope-web/src/i18n/resources/zh-Hant/research.ts`

### Modify: frontend

- `apps/arkscope-web/src/InvestorProfilePanel.tsx`
- `apps/arkscope-web/src/InvestorProfilePanel.test.tsx`
- `apps/arkscope-web/src/Settings.tsx`
- `apps/arkscope-web/src/SettingsWorkspace.test.tsx`
- `apps/arkscope-web/src/api.ts`
- `apps/arkscope-web/src/ResearchEvidenceDrawer.tsx`
- `apps/arkscope-web/src/i18n/resources.ts`
- `apps/arkscope-web/src/i18n/resources/en/settings.ts`
- `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`
- `apps/arkscope-web/src/i18n/resources.test.ts`
- `apps/arkscope-web/src/i18n/foundationBoundaries.test.ts`
- `apps/arkscope-web/scripts/i18n/migrated-scopes.json`
- `apps/arkscope-web/src/ui/primitives.css`
- `apps/arkscope-web/src/ui/classCoverage.test.ts`

### Evidence/docs only

- `docs/superpowers/plans/2026-07-22-p2-8-slice-5-investor-profile-workspace.md`
- `docs/superpowers/specs/2026-07-22-p2-8-slice-5-investor-profile-workspace-design.md`
- `docs/design/PROJECT_PRIORITY_MAP.md`
- `docs/design/ARKSCOPE_TERMINOLOGY.md` remains byte-identical during product
  implementation because the approved spec already added all canonical terms.

### Immutable boundaries

The following must be byte-identical to `bca064d4`:

```text
src/evidence_packet.py
src/tools/**
src/agents/** except no files are owned here
src/api/routes/query.py
apps/arkscope-web/src/personalizationDisplay.ts
apps/arkscope-web/src/modelRoutingUx.ts
apps/arkscope-web/src/settings/settingsCopy.ts
apps/arkscope-web/src/settings/settingsBackendCopy.ts
apps/arkscope-web/src/settings/legacy/**
apps/arkscope-web/src/shell/**
apps/arkscope-web/src/settings/settings.css
apps/arkscope-web/src/shell/shell.css
apps/arkscope-desktop/**
extensions/**
package.json
package-lock.json
apps/arkscope-web/package.json
```

---

## Exact Test Ledger

### Backend: `+53/-1`, net `+52`

Full collection moves `4569 -> 4621`. Focused collection moves
`10 files / 167 -> 12 files / 219`.

#### `tests/test_investor_profile_calibration_policy.py` — add 10

1. `test_catalog_order_and_topic_ids_are_exact`
2. `test_catalog_fields_and_deny_list_exactly_partition_profile_body`
3. `test_covered_topics_derive_only_the_reviewed_field_union`
4. `test_clamp_preserves_partial_patch_and_normalizes_only_legal_fields`
5. `test_clamp_drops_unknown_uncovered_denied_and_derived_fields_without_values`
6. `test_clamp_with_no_legal_fields_returns_no_proposal`
7. `test_next_topic_accepts_any_uncovered_catalog_topic`
8. `test_next_topic_rejects_unknown_and_already_covered_topics`
9. `test_opening_prompt_catalog_is_versioned_and_exact`
10. `test_catalog_serialization_preserves_backend_display_order`

#### `tests/test_investor_profile_calibration_migration.py` — add 8

1. `test_fresh_migration_creates_exact_v2_schema_and_marker`
2. `test_v1_migration_preserves_message_and_terminal_proposal_bytes`
3. `test_v1_migration_supersedes_active_session_and_draft_only`
4. `test_v2_migration_is_idempotent`
5. `test_marker_schema_mismatch_fails_closed_without_writes`
6. `test_unmarked_v2_artifacts_fail_closed_without_rebuild`
7. `test_statement_failure_rolls_back_to_exact_v1`
8. `test_store_construction_and_status_read_never_create_or_migrate`

#### `tests/test_investor_profile_calibration.py` — add 17, remove 1

Remove exactly:

- `test_create_proposal_is_inert_and_server_derives_mismatch`

Add exactly:

1. `test_start_guided_session_persists_opening_prompt_without_provider_call`
2. `test_begin_turn_is_idempotent_and_allows_only_one_pending_turn`
3. `test_begin_turn_records_pre_provider_answer_and_frozen_topic`
4. `test_complete_turn_advances_adaptive_uncovered_topic`
5. `test_complete_turn_rejects_wrong_addressed_topic_without_advancing`
6. `test_complete_turn_rejects_unknown_or_covered_next_topic_without_advancing`
7. `test_failed_turn_retains_answer_and_is_retryable_with_same_turn_id`
8. `test_startup_reconciliation_marks_pending_turn_interrupted`
9. `test_request_proposal_uses_covered_topics_without_synthetic_user_message`
10. `test_create_guided_proposal_clamps_to_covered_fields_and_records_base_values`
11. `test_all_illegal_proposal_fields_create_no_proposal`
12. `test_pending_proposal_blocks_second_draft_for_session`
13. `test_approve_partial_patch_preserves_uncovered_and_denied_profile_fields`
14. `test_approve_compares_list_base_values_as_sets`
15. `test_approve_conflict_keeps_proposal_pending_and_writes_nothing`
16. `test_approve_profile_and_proposal_roll_back_together_on_fault`
17. `test_reject_guided_proposal_keeps_profile_and_audit_unchanged`

The remaining 11 baseline nodes retain their IDs and evolve in place where the
prompt/parser/status model changed.

#### `tests/test_investor_profile_calibration_routes.py` — add 10

1. `test_start_guided_session_returns_opening_prompt_without_responder_call`
2. `test_turn_requires_client_turn_id_and_returns_retryable_state`
3. `test_completed_turn_retry_returns_same_state_without_second_provider_call`
4. `test_invalid_next_topic_returns_typed_catalog_validation_failure_and_retryable_turn`
5. `test_retry_interrupted_turn_reuses_answer_and_turn_id`
6. `test_request_proposal_uses_dedicated_route_without_fake_user_message`
7. `test_approve_schema_rejects_client_profile_patch`
8. `test_approve_conflict_returns_409_and_keeps_pending_proposal`
9. `test_missing_provider_configuration_uses_existing_typed_error_family`
10. `test_calibration_failure_hides_provider_detail_outside_diagnostic_field`

#### Other backend additions — add 8

- `tests/test_provider_config_startup.py` +2:
  `test_lifespan_migrates_calibration_before_scheduler_start`,
  `test_lifespan_reconciles_pending_calibration_turns_before_scheduler_start`.
- `tests/test_investor_profile.py` +1:
  `test_personalization_context_golden_fixture_excludes_notes_and_localized_labels`.
- `tests/test_card_runs.py` +2:
  `test_card_run_context_snapshot_distinguishes_legacy_null_from_new_disabled_empty`,
  `test_card_run_context_snapshot_round_trips_exact_active_prompt_block`.
- `tests/test_research_runs.py` +2:
  `test_research_run_persists_prompt_assembly_trace_and_exact_context_before_stream`,
  `test_research_run_context_snapshot_distinguishes_legacy_null_from_disabled_empty`.
- `tests/test_research_threads.py` +1:
  `test_message_personalization_snapshot_round_trip_and_legacy_null`.

Existing analysis-card and Research route nodes evolve in place to assert the
additive snapshot DTO and no evidence/tool drift. No other backend node may be
removed or renamed.

### Frontend: `+47/-1`, net `+46`

Full suite moves `77 files / 778 -> 81 files / 824`. The nine-file focused
suite moves `5 existing files / 59 -> 9 files / 105`.

#### New `investorProfileDisplay.test.ts` — add 8

1. `pins exact known topic and prompt ID sets`
2. `maps all topic labels and descriptions in both locales`
3. `uses generic topic copy while keeping an unknown raw ID diagnostic-only`
4. `relocalizes a known opening prompt and falls back to canonical unknown copy`
5. `maps all proposable field labels without owning topic field policy`
6. `preserves source list and numeric values while localizing semantic IDs`
7. `maps all seven stance effects in both locales`
8. `preserves backend topic and proposed-field order without sorting`

#### `InvestorProfilePanel.test.tsx` — add 20

1. `renders summary first with effective stance mismatch and current context`
2. `loads profile and calibration independently without inventing empty state`
3. `defaults and reloads to summary while keeping one registry anchor`
4. `enters edit with focus and preserves every profile field`
5. `dirty edit exit uses value-free confirm and cancel restores focus`
6. `confirmed edit discard returns to a fresh summary`
7. `draft save stays in edit without writing or clearing fields`
8. `full save refetches effective profile before summary`
9. `failed post-save refresh stays in edit with an honest error`
10. `busy save or approve blocks mode change`
11. `calibration exit is free and restores command focus`
12. `starts with a localizable fixed question without a provider call`
13. `submits source answer with stable turn ID and preserves journal`
14. `retries interrupted turn with the same ID without duplicate answer`
15. `requests early proposal without synthetic user content`
16. `renders backend-ordered coverage and unknown topic without raw ID`
17. `preserves edit calibration disclosure proposal and focus across locale switch`
18. `proposal mode requires a pending proposal and separates coverage from actions`
19. `renders localized field diffs and source rationales then approves without patch`
20. `keeps conflicted proposal pending and routes missing provider to Providers`

The existing 13 nodes retain their IDs and evolve to the new summary/mode
structure. Source-content, Developer diagnostics, generation guard, loading,
and full field coverage assertions must not weaken.

#### `SettingsWorkspace.test.tsx` — add 3, remove 1

Remove exactly:

- `investor_profile_guard_blocks_busy_and_confirms_potential_draft_without_modifying_panel`

Add exactly:

1. `investor profile guard uses the panel reporter for dirty edit and busy mutation`
2. `calibration mode leaves Personalization without discard confirmation`
3. `investor provider action reveals the Providers anchor and restores focus`

#### New frontend files — add 14

- `InvestorProfileApi.test.ts` +5:
  `serializes guided start and turn contracts with stable IDs`,
  `retries a turn without mutating answer payload`,
  `requests an early proposal on the dedicated route`,
  `approves with an empty body and never sends profile_patch`,
  `exposes run personalization snapshot without credential identity`.
- `ResearchPersonalizationContext.test.tsx` +6:
  `renders legacy null as no snapshot`,
  `renders empty snapshot as disabled`,
  `renders active exact source text byte for byte`,
  `distinguishes run context from current Settings context`,
  `switches locale without changing source context or disclosure state`,
  `maps closed stance effect copy without deriving it from context text`.
- `InvestorProfileCss.test.ts` +3:
  `defines every Slice 5 Investor class`,
  `uses responsive intrinsic grids and wrap-safe command rows`,
  `adds no media query breakpoint or nested-card selector`.

#### Existing i18n tests — add 2

- `resolves the Slice 5 Investor workspace copy in both locales`
- `contains exactly 712 Settings leaves and 5 Research leaves per locale`

`classCoverage.test.ts` and `foundationBoundaries.test.ts` evolve in place;
they add no node.

---

## Exact Literal-Ratchet Contract

All new visible copy uses static selector calls. Add exactly two migrated
scopes:

```text
src/settings/investor/**
src/ResearchPersonalizationContext.tsx
```

Keep the existing `src/InvestorProfilePanel.tsx` scope. Do not add
`ResearchEvidenceDrawer.tsx`; this slice adds no visible literal there and does
not claim migration of its existing debt. `visible-literal-debt.json` and
`visible-literal-allowlist.json` remain byte-identical.

Final scanner result remains exactly:

```text
1033 candidates / 973 signatures / 954 debt / 20 allowlist
30 migrated scopes
```

No dynamic key, locale branch, raw field/topic ID, or new stable-value
allowlist entry is authorized.

---

## Implementation Ledger

| Task | Backend node delta | Frontend node delta | Commit intent |
|---|---:|---:|---|
| 0. clearance/re-ground | 0 | 0 | docs only |
| 1. policy + schema migration | +18 | 0 | policy/schema authority |
| 2. turn/proposal store | +17/-1 | 0 | durable state machine |
| 3. agent + routes | +10 | 0 | Provider seam and typed API |
| 4. startup + reconciliation | +2 | 0 | migration/startup ownership |
| 5. prompt snapshots | +6 | 0 | current/run transparency data |
| 6. resources + display/API seams | 0 | +15 | bilingual closed mappings |
| 7. workspace UI + Settings guard | 0 | +23/-1 | summary/modes/navigation |
| 8. Research context + CSS/ratchet | 0 | +9 | historical transparency/layout |
| **Total** | **+53/-1** | **+47/-1** | **net backend +52, frontend +46** |

Every task ends with focused GREEN, `git diff --check`, a bounded diff review,
and a commit. If exact collection changes, stop and amend this plan before
continuing. Every named addition is exactly one collected node; exercise
multi-case contracts with loops inside that node. Parametrization that expands
collection requires a reviewed ledger amendment.

---

## Task 0: Plan Clearance, Worktree, and Re-grounding

**Files:**
- Modify: this plan status and implementation ledger only
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [ ] **Step 1: Record independent plan review**

  After written GREEN, change status to `CLEARED FOR IMPLEMENTATION`, record
  every finding/resolution without deleting history, and commit docs only.
  Record that hash as `PLAN_REVIEW_CLEARANCE_COMMIT`.

- [ ] **Step 2: Create an isolated implementation worktree**

  From the clearance commit, use `superpowers:using-git-worktrees` to create
  branch `codex/p2-8-slice-5-investor-profile-workspace`. Do not implement in
  `master`.

- [ ] **Step 3: Record exact baselines before RED**

  Run:

  ```bash
  pytest --collect-only -q
  pytest --collect-only -q \
    tests/test_investor_profile.py \
    tests/test_investor_profile_routes.py \
    tests/test_investor_profile_calibration.py \
    tests/test_investor_profile_calibration_routes.py \
    tests/test_provider_config_startup.py \
    tests/test_analysis_cards_api.py \
    tests/test_card_runs.py \
    tests/test_research_runs.py \
    tests/test_research_routes.py \
    tests/test_research_threads.py
  cd apps/arkscope-web && npx vitest list
  npm run check:i18n-literals
  ```

  Expected: backend `4569` and focused `167`; frontend `77/778`; scanner
  `1033/973/954/20` and 28 scopes. If any differs, stop and reconcile the plan.

- [ ] **Step 4: Verify immutable baselines and production observation**

  Record SHA-256 for immutable files/trees. Use SQLite URI read-only mode to
  record calibration aggregate counts and schema columns; do not open a write
  connection and do not pin observed row counts as tests.

- [ ] **Step 5: Commit clearance ledger**

  ```bash
  git add docs/superpowers/plans/2026-07-22-p2-8-slice-5-investor-profile-workspace.md \
    docs/design/PROJECT_PRIORITY_MAP.md
  git commit -m "docs: clear investor profile workspace implementation"
  ```

---

## Task 1: Establish Calibration Policy and Explicit Schema v2

**Files:**
- Create: `src/investor_profile_calibration_policy.py`
- Create: `src/investor_profile_calibration_schema.py`
- Create: `tests/test_investor_profile_calibration_policy.py`
- Create: `tests/test_investor_profile_calibration_migration.py`
- Modify: `src/investor_profile_calibration.py`
- Modify: `tests/test_investor_profile_calibration.py`
- Modify: `tests/test_investor_profile_calibration_routes.py`

- [ ] **Step 1: Write the 18 exact RED nodes**

  Implement fixtures that create exact fresh, v1, partial-v2, and marked-v2
  DBs with real schema SQL. Hash ordered message/proposal rows before migration.
  Policy tests import `InvestorProfileBody.model_fields` only in tests to prove
  the exact 10+3 partition without introducing a runtime FastAPI dependency.

- [ ] **Step 2: Prove RED identity**

  ```bash
  pytest tests/test_investor_profile_calibration_policy.py \
    tests/test_investor_profile_calibration_migration.py -q
  ```

  Expected: exactly 18 collected and failures caused by missing policy/schema
  modules, not fixture errors.

- [ ] **Step 3: Implement the pure policy catalog**

  Add the exact dataclasses/constants/helpers in Backend Contract. Every helper
  accepts/returns IDs and fields only; no user/model text, FastAPI, store, or
  SQLite import is allowed.

- [ ] **Step 4: Implement schema migration and assertion**

  Use one statement list inside `BEGIN IMMEDIATE`; never `executescript()`
  inside the transaction. Recheck fingerprint after lock, run exact legacy
  updates, create indexes/table, insert marker last, commit, then assert final
  fingerprint. On `BaseException`, rollback and re-raise.

- [ ] **Step 5: Make store construction assertion-only**

  Remove `_ensure_schema()` from `CalibrationStore.__init__()`. Test fixtures
  call `migrate_calibration_schema(path)` explicitly before construction.

- [ ] **Step 6: Run focused GREEN and migration probes**

  Expected: `18 passed`. Run `PRAGMA integrity_check`, `foreign_key_check`,
  exact marker/column/index assertions, second migration no-op, and byte digest
  equality for preserved legacy rows.

- [ ] **Step 7: Commit**

  ```bash
  git add src/investor_profile_calibration_policy.py \
    src/investor_profile_calibration_schema.py \
    src/investor_profile_calibration.py \
    tests/test_investor_profile_calibration_policy.py \
    tests/test_investor_profile_calibration_migration.py \
    tests/test_investor_profile_calibration.py \
    tests/test_investor_profile_calibration_routes.py
  git commit -m "feat: version investor calibration policy and schema"
  ```

---

## Task 2: Implement the Durable Turn and Partial-Proposal Store

**Files:**
- Modify: `src/investor_profile_calibration.py`
- Modify: `src/investor_profile_calibration_policy.py`
- Modify: `src/investor_profile.py`
- Modify: `tests/test_investor_profile_calibration.py`

- [ ] **Step 1: Replace the one obsolete node and add 17 RED nodes**

  Preserve the exact ledger. Use real stores on one temp DB. Add a fake fault by
  monkeypatching the proposal-status connection helper after the profile write,
  so the rollback test proves one transaction rather than two compensating
  writes.

- [ ] **Step 2: Run RED and verify reasons**

  ```bash
  pytest tests/test_investor_profile_calibration.py -q
  ```

  Expected collection: `28` (`12 - 1 + 17`). New failures must identify absent
  opening prompt, turns, clamp/base metadata, conflict, or atomic approval.

- [ ] **Step 3: Add exact v2 dataclasses and serializers**

  Extend session/message/proposal dataclasses and add `CalibrationTurn`.
  Serialization exposes IDs, status, counts, ordered field names, and bounded
  diagnostics, never hidden field values or raw Provider payloads.

- [ ] **Step 4: Implement guided start and first transaction**

  `start_session()` inserts session and opening assistant message atomically.
  `begin_answer_turn()` validates active v2 session/current question, inserts
  one source user message and one pending turn, and returns a `ProviderWork`
  envelope. `begin_proposal_turn()` inserts no user message.

- [ ] **Step 5: Implement retry and completion transactions**

  Retry increments attempt count and returns the frozen context. Completion
  validates addressed/next topics before any session/message/proposal mutation.
  On valid completion, append assistant content, advance coverage/current, and
  create at most one legal draft. On invalid completion, fail only the turn.

- [ ] **Step 6: Implement partial proposal/base/conflict ownership**

  Store JSON with deterministic key order from the backend catalog. Base values
  include only proposed fields. Rejected field audit stores field names only.
  Derive DTO `proposed_fields` from legal patch keys in catalog order; do not
  persist a duplicate proposed-field list. Keep existing `changed_fields_json`
  as the actual approval audit.
  `raw_profile_patch_json` is legacy-preservation only; new guided proposals
  write `{}` and approval never reads it.

- [ ] **Step 7: Implement caller-owned profile helpers and atomic approval**

  Refactor the existing store through `_read_profile_on_connection` and
  `_write_profile_on_connection`. Keep ordinary GET/PUT output unchanged.
  Implement fixed lock order, shared-file check, exact/list conflict checks,
  partial merge, atomic status write, conflict metadata, and reject.

- [ ] **Step 8: Run GREEN**

  ```bash
  pytest tests/test_investor_profile_calibration.py \
    tests/test_investor_profile_calibration_policy.py \
    tests/test_investor_profile.py -q
  ```

  Expected: `28 + 10 + 13 = 51 passed` after Task 5 adds the one profile node;
  at this checkpoint before Task 5, `50 passed` is correct.

- [ ] **Step 9: Commit**

  ```bash
  git add src/investor_profile.py src/investor_profile_calibration.py \
    src/investor_profile_calibration_policy.py \
    tests/test_investor_profile.py tests/test_investor_profile_calibration.py
  git commit -m "feat: make investor calibration durable and partial"
  ```

---

## Task 3: Wire the Structured Agent and Typed Calibration Routes

**Files:**
- Modify: `src/investor_profile_calibration_agent.py`
- Modify: `src/api/routes/investor_profile_calibration.py`
- Modify: `tests/test_investor_profile_calibration.py`
- Modify: `tests/test_investor_profile_calibration_routes.py`

- [ ] **Step 1: Add the 10 route RED nodes and evolve parser nodes in place**

  Route fakes return structured addressed/covered/next data. Include hostile
  model results with denied fields, unknown next topic, already-covered next
  topic, raw exception/credential-like diagnostic, and all-illegal proposal.

- [ ] **Step 2: Prove exact RED collection**

  ```bash
  pytest tests/test_investor_profile_calibration.py \
    tests/test_investor_profile_calibration_routes.py -q
  ```

  Expected collection after Task 2: `28 + 18 = 46`; only the ten new route
  nodes and evolved structured-parser assertions fail.

- [ ] **Step 3: Replace the free-form agent output contract**

  Prompt includes exact catalog order, topic fields, covered/current IDs,
  request-proposal bit, and no-tool boundaries. It forbids schema names in user
  prose. Parser validates JSON types but does not normalize/expand proposal
  fields; the policy/store owns clamp and next-topic validation.

- [ ] **Step 4: Build canonical model context**

  Expand known `prompt_id` to canonical text for historical messages. Preserve
  user answers verbatim. Model-generated assistant questions remain canonical
  source content with `prompt_id=null`. No `ui_locale`, resources, DAL, tools,
  evidence, or profile notes enter the request.

- [ ] **Step 5: Evolve routes without a dual-writer window**

  Start calls only `start_session()`. Message POST requires `turn_id`, commits
  `begin_answer_turn()`, waits on responder outside locks, then completes.
  Add explicit retry and proposal-request routes. Remove direct
  `append_message()+create_proposal()` orchestration.

- [ ] **Step 6: Preserve typed failures and privacy**

  Store a bounded sanitized diagnostic on failed turns. Return product code
  `provider_config_missing` for missing auth and
  `calibration_responder_failed` for other Provider failures. Response detail
  contains generic product message plus diagnostic only through the existing
  typed `ApiError` field; no credential ID/token/raw model body enters state.

- [ ] **Step 7: Make approval schema empty and strict**

  Use a Pydantic body with `extra="forbid"` and no fields. Route permission gate
  occurs before atomic store approval; client replacement patch is impossible.

- [ ] **Step 8: Run GREEN and seam gates**

  Expected: `46 passed`. Static scans require zero DAL/tool/evidence imports in
  calibration agent/policy, zero `profile_patch` in approve request bodies, and
  zero `ui_locale` in calibration prompt code.

- [ ] **Step 9: Commit**

  ```bash
  git add src/investor_profile_calibration_agent.py \
    src/api/routes/investor_profile_calibration.py \
    tests/test_investor_profile_calibration.py \
    tests/test_investor_profile_calibration_routes.py
  git commit -m "feat: guide investor calibration turns"
  ```

---

## Task 4: Make Migration and Interrupted-Turn Recovery Startup-Owned

**Files:**
- Modify: `src/api/app.py`
- Modify: `src/api/dependencies.py`
- Modify: `tests/test_provider_config_startup.py`

- [ ] **Step 1: Add two startup-order RED nodes**

  Instrument calls and require strict subsequence:

  ```text
  apply provider env
  migrate calibration schema
  construct calibration store
  reconcile pending calibration turns
  reconcile scheduler/provider telemetry
  start data/portfolio schedulers
  ```

  Migration mismatch must escape lifespan startup; it may not be caught as
  setup-only provider failure or debug-only reconciliation noise. In the first
  node, run both successful and failed Provider-environment setup as an
  in-node table so migration/reconciliation are proven unconditional without
  expanding the exact node ledger.

- [ ] **Step 2: Run RED**

  ```bash
  pytest tests/test_provider_config_startup.py -q
  ```

  Expected: `7` collected, exactly two new failures.

- [ ] **Step 3: Add explicit startup phase**

  In lifespan, resolve `_local_state_db_path()`, call migration, construct the
  assertion-only store, then call `reconcile_interrupted_turns()`. Keep the
  operation synchronous/short before scheduler task creation. This phase runs
  even when Provider environment setup failed and `provider_config_ready` is
  false; only Provider-dependent schedulers remain disabled in that state.

- [ ] **Step 4: Preserve dependency laziness without migration**

  `get_investor_calibration_store()` returns the already-v2 assertion-only
  store. Cache clearing in tests remains deterministic. GET and constructor do
  not call migration or reconciliation.

- [ ] **Step 5: Run GREEN and no-scheduler ordering probe**

  Expected: `7 passed`, including `ARKSCOPE_DISABLE_SCHEDULER=1` while migration
  and turn reconciliation still run.

- [ ] **Step 6: Commit**

  ```bash
  git add src/api/app.py src/api/dependencies.py \
    tests/test_provider_config_startup.py
  git commit -m "feat: reconcile investor calibration at startup"
  ```

---

## Task 5: Persist Exact Personalization Context for Research and Cards

**Files:**
- Modify: `src/investor_profile.py`
- Modify: `src/api/personalization.py`
- Modify: `src/research_runs.py`
- Modify: `src/research_run_manager.py`
- Modify: `src/api/routes/research.py`
- Modify: `src/research_threads.py`
- Modify: `src/card_runs.py`
- Modify: `src/api/routes/analysis_cards.py`
- Modify: `tests/test_investor_profile.py`
- Modify: `tests/test_analysis_cards_api.py`
- Modify: `tests/test_card_runs.py`
- Modify: `tests/test_research_runs.py`
- Modify: `tests/test_research_routes.py`
- Modify: `tests/test_research_threads.py`

- [ ] **Step 1: Add six RED nodes and strengthen existing route nodes**

  Use planted profile values and exact expected context bytes. Insert legacy
  rows before additive column migration. Assert three states independently:
  null legacy, empty new disabled, exact non-empty new active.

- [ ] **Step 2: Prove RED**

  Run the six affected focused files. Expected six new failures only; existing
  evidence-gathering and personalization tests remain green.

- [ ] **Step 3: Add `personalization_bundle()` and golden pin**

  Resolve trace and context from one in-memory profile. Golden assertion pins
  exact English context, evidence guard, empty skills, absence of notes, and
  absence of localized UI labels.

- [ ] **Step 4: Persist Research run trace at prompt assembly**

  Add tolerant nullable `personalization_json` migration. In executor, resolve
  before running, call `mark_running_with_personalization()`, reload/use the
  persisted trace, and pass `context_snapshot` to the Provider. On resolution
  failure, persist honest off trace with empty snapshot. Do not re-resolve for
  success/error/cancel/interruption.

- [ ] **Step 5: Expose run snapshot safely**

  `_run_dict()` adds `personalization`; it continues to remove credential
  identity only at agent payload boundaries already owned elsewhere. Message
  DTO remains additive. No raw profile fields beyond exact context/closed trace
  enter the DTO.

- [ ] **Step 6: Persist card snapshot**

  Add nullable column, round-trip it inside existing `personalization`, and
  ensure `generate_card()` passes the same bundle used by synthesis. Keep
  `gather_evidence()` invocation and arguments byte-identical.

- [ ] **Step 7: Run focused GREEN**

  Run all 12 backend focused files. Expected exact `219 passed` in a data-ready
  environment, with `+53/-1` node accounting and no removed node beyond the one
  named obsolete calibration test.

- [ ] **Step 8: Commit**

  ```bash
  git add src/investor_profile.py src/api/personalization.py \
    src/research_runs.py src/research_run_manager.py \
    src/api/routes/research.py src/research_threads.py src/card_runs.py \
    src/api/routes/analysis_cards.py \
    tests/test_investor_profile.py tests/test_analysis_cards_api.py \
    tests/test_card_runs.py tests/test_research_runs.py \
    tests/test_research_routes.py tests/test_research_threads.py
  git commit -m "feat: snapshot run personalization context"
  ```

---

## Task 6: Add Bilingual Resources, API Types, and Display Seams

**Files:**
- Create: `apps/arkscope-web/src/InvestorProfileApi.test.ts`
- Create: `apps/arkscope-web/src/settings/investor/investorProfileDisplay.ts`
- Create: `apps/arkscope-web/src/settings/investor/investorProfileDisplay.test.ts`
- Create: `apps/arkscope-web/src/i18n/resources/en/research.ts`
- Create: `apps/arkscope-web/src/i18n/resources/zh-Hant/research.ts`
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/i18n/resources.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources.test.ts`

- [ ] **Step 1: Write 15 RED nodes**

  Add eight display, five API, and two resource nodes exactly as ledgered.
  API fetch spies assert JSON bodies and explicitly reject any approval
  `profile_patch`. Display tests loop exact known topic/prompt sets and both
  locale resources.

- [ ] **Step 2: Prove RED identity**

  ```bash
  npm test -- --run src/settings/investor/investorProfileDisplay.test.ts \
    src/InvestorProfileApi.test.ts src/i18n/resources.test.ts
  ```

  Expected: `3 files / 24 tests` after additions, with 15 new failures.

- [ ] **Step 3: Add exact resources**

  Implement the 94-add/5-remove Settings contract and new five-leaf Research
  namespace in both locales. Register bundled static namespace in
  `resources.ts`; no loader/Suspense/dynamic import.

- [ ] **Step 4: Evolve DTOs and request helpers**

  Add turn/topic/prompt/proposal/run personalization types. Answer sends a
  supplied `turn_id`; retry has no answer; proposal request has no fake text;
  approval serializes `{}`. Existing API error compatibility remains unchanged.

- [ ] **Step 5: Implement closed display mappings**

  Use exhaustive switches for known IDs and static selector calls. Expose
  ordered rendering helpers, source value presenters, unknown compatibility,
  and stance effects. Do not import backend policy or duplicate its field map.

- [ ] **Step 6: Run GREEN and resource counts**

  Expected: `24 passed`, Settings `712`, Research `5`, recursive locale keys
  equal, no empty leaf, no dynamic key.

- [ ] **Step 7: Commit**

  ```bash
  git add apps/arkscope-web/src/api.ts \
    apps/arkscope-web/src/InvestorProfileApi.test.ts \
    apps/arkscope-web/src/settings/investor/investorProfileDisplay.ts \
    apps/arkscope-web/src/settings/investor/investorProfileDisplay.test.ts \
    apps/arkscope-web/src/i18n
  git commit -m "feat: define bilingual investor workspace copy"
  ```

---

## Task 7: Build the Summary-First Workspace and Precise Settings Guard

**Files:**
- Create: `apps/arkscope-web/src/settings/investor/InvestorProfileSummary.tsx`
- Create: `apps/arkscope-web/src/settings/investor/InvestorProfileEdit.tsx`
- Create: `apps/arkscope-web/src/settings/investor/InvestorProfileCalibration.tsx`
- Create: `apps/arkscope-web/src/settings/investor/InvestorProfileProposalReview.tsx`
- Modify: `apps/arkscope-web/src/InvestorProfilePanel.tsx`
- Modify: `apps/arkscope-web/src/InvestorProfilePanel.test.tsx`
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Modify: `apps/arkscope-web/src/SettingsWorkspace.test.tsx`

- [ ] **Step 1: Add 20 panel nodes and replace the one Settings guard node**

  Add three Settings nodes. Preserve all existing node IDs. Use deferred
  promises for profile/calibration/turn/save/approve legs, live DOM identity
  after locale changes, connected focus targets, and planted secret-like source
  values that must not enter guard/dialog copy.

- [ ] **Step 2: Prove exact RED collection**

  ```bash
  npm test -- --run src/InvestorProfilePanel.test.tsx \
    src/SettingsWorkspace.test.tsx
  ```

  Expected collection: Panel `33`; Settings `26`; total `59`, with raw ledger
  `+23/-1`.

- [ ] **Step 3: Split renderers without splitting state ownership**

  Keep all requests, generation refs, mode, dirty baseline, focus refs, and
  error state in `InvestorProfilePanel`. Child components receive values and
  semantic callbacks. They do not fetch, own navigation, or call i18next
  dynamically.

- [ ] **Step 4: Implement independent load and Summary**

  Use `Promise.allSettled`, one mounted controller, honest leg states, effective
  summary, status-aware commands, proposal card spacing, and current-context
  disclosure. Pending proposal action is on its own row and cannot overlap
  covered-topic text.

- [ ] **Step 5: Implement Edit mode and internal guard**

  Move the full existing form without dropping fields. Draft stays in mode.
  Full save refetches. Dirty mode exit uses value-free ConfirmDialog; cancel and
  confirm restore the correct command focus. Notes help states non-causality.

- [ ] **Step 6: Implement Calibration and Proposal Review**

  Render fixed/localized opening question, source journal, current topic,
  progress, unknown fallback, interrupted retry, and Propose Now. Proposal
  Review renders covered topics separately, then ordered field diffs and source
  rationales, then conflict/approve/reject actions.

- [ ] **Step 7: Preserve generation guards and locale state**

  Every explicit calibration action increments the generation. Initial stale
  reads cannot overwrite active edits/turns/proposals. Locale changes do not
  refetch/remount or clear source content/disclosures/focus.

- [ ] **Step 8: Replace the Settings heuristic guard**

  Store reported guard state, remove capture/DOM inference, and route Provider
  recovery through existing exact-anchor navigation. Calibration remains clean;
  Edit dirty and mutations busy are precise.

- [ ] **Step 9: Run GREEN**

  Expected: exact `59 passed`. Run resource/display/API tests too; expected
  Task 6-7 owned cumulative is `5 files / 83 passed`. Including the unchanged
  class-coverage and foundation-boundary baselines, the final-suite checkpoint
  before Task 8 is `7 files / 96 passed`; Task 8 then adds nine nodes.

- [ ] **Step 10: Commit**

  ```bash
  git add apps/arkscope-web/src/InvestorProfilePanel.tsx \
    apps/arkscope-web/src/InvestorProfilePanel.test.tsx \
    apps/arkscope-web/src/Settings.tsx \
    apps/arkscope-web/src/SettingsWorkspace.test.tsx \
    apps/arkscope-web/src/settings/investor
  git commit -m "feat: rebuild investor profile workspace"
  ```

---

## Task 8: Add Historical Context Transparency, Layout, and Ratchets

**Files:**
- Create: `apps/arkscope-web/src/ResearchPersonalizationContext.tsx`
- Create: `apps/arkscope-web/src/ResearchPersonalizationContext.test.tsx`
- Create: `apps/arkscope-web/src/InvestorProfileCss.test.ts`
- Modify: `apps/arkscope-web/src/ResearchEvidenceDrawer.tsx`
- Modify: `apps/arkscope-web/src/ui/primitives.css`
- Modify: `apps/arkscope-web/src/ui/classCoverage.test.ts`
- Modify: `apps/arkscope-web/src/i18n/foundationBoundaries.test.ts`
- Modify: `apps/arkscope-web/scripts/i18n/migrated-scopes.json`

- [ ] **Step 1: Write six Research and three CSS RED nodes**

  Use null/empty/non-empty traces, source text containing non-English content,
  locale changes, and closed stance IDs. CSS tests inspect rules structurally,
  not screenshots or arbitrary pixel values.

- [ ] **Step 2: Prove RED**

  Expected: `9` new failures, existing class coverage green.

- [ ] **Step 3: Implement the Research component and Drawer wire**

  Keep new copy in `research` namespace. Prefer selected-message trace, then
  exact fetched run trace. Render source context byte-exact. Do not modify
  existing Drawer strings or migrate its debt.

- [ ] **Step 4: Add restrained workspace CSS**

  Extend `ui/primitives.css` with intrinsic grids (`auto-fit`/`minmax`), stable
  mode header dimensions, wrap-safe actions/chips, bounded journal overflow,
  proposal diff rows, and source context pre-wrap. No card inside card, no
  `@media`, viewport-width font sizing, 959/960/961 literals, negative letter
  spacing, or new palette.

- [ ] **Step 5: Update class and literal coverage**

  Evolve the existing Investor class node to recursively scan the controller
  and `settings/investor` components. Add exactly two migrated scopes, leave
  debt/allowlist bytes unchanged, and strengthen the foundation node to require
  30 exact scopes.

- [ ] **Step 6: Run the exact final frontend focused suite**

  ```bash
  npm test -- --run \
    src/InvestorProfilePanel.test.tsx \
    src/SettingsWorkspace.test.tsx \
    src/i18n/resources.test.ts \
    src/ui/classCoverage.test.ts \
    src/i18n/foundationBoundaries.test.ts \
    src/settings/investor/investorProfileDisplay.test.ts \
    src/InvestorProfileApi.test.ts \
    src/ResearchPersonalizationContext.test.tsx \
    src/InvestorProfileCss.test.ts
  ```

  Expected: `9 files / 105 passed`.

- [ ] **Step 7: Run scanner GREEN**

  ```bash
  npm run check:i18n-literals
  ```

  Expected exact `1033/973/954/20`, 30 scopes, debt/allowlist SHA unchanged.

- [ ] **Step 8: Commit**

  ```bash
  git add apps/arkscope-web/src/ResearchPersonalizationContext.tsx \
    apps/arkscope-web/src/ResearchPersonalizationContext.test.tsx \
    apps/arkscope-web/src/ResearchEvidenceDrawer.tsx \
    apps/arkscope-web/src/InvestorProfileCss.test.ts \
    apps/arkscope-web/src/ui apps/arkscope-web/src/i18n/foundationBoundaries.test.ts \
    apps/arkscope-web/scripts/i18n/migrated-scopes.json
  git commit -m "feat: expose run personalization context"
  ```

---

## Task 9: Canonical Verification and Isolated Live Gate

**Files:**
- Modify only evidence sections in this plan after commands complete

- [ ] **Step 1: Run backend focused and full collection**

  ```bash
  pytest tests/test_investor_profile_calibration_policy.py \
    tests/test_investor_profile_calibration_migration.py \
    tests/test_investor_profile.py \
    tests/test_investor_profile_routes.py \
    tests/test_investor_profile_calibration.py \
    tests/test_investor_profile_calibration_routes.py \
    tests/test_provider_config_startup.py \
    tests/test_analysis_cards_api.py \
    tests/test_card_runs.py \
    tests/test_research_runs.py \
    tests/test_research_routes.py \
    tests/test_research_threads.py -q
  pytest --collect-only -q
  ```

  Expected: `12 files / 219 passed`; full collect `4621`.

- [ ] **Step 2: Run frontend canonical gates**

  ```bash
  npm test --workspace apps/arkscope-web -- --run
  npm run typecheck --workspace apps/arkscope-web
  npm run build --workspace apps/arkscope-web
  npm run check:i18n-literals --workspace apps/arkscope-web
  ```

  Expected: `81 files / 824 passed`; clean typecheck; build succeeds with only
  the existing chunk-size warning; scanner exact.

- [ ] **Step 3: Prove exact node accounting with virgin archives**

  Use archives of `bca064d4` and product tip with the same root `node_modules`.
  Backend node comm must be `+53/-1`; frontend comm `+47/-1`. Removed IDs must
  be exactly the two named obsolete nodes. Existing failure/error/skip/warning
  families must be bidirectionally identical.

- [ ] **Step 4: Run copied-production migration proof**

  Use SQLite online backup to a `0600` temp file. On the copy only:

  1. record aggregate counts plus ordered SHA-256 digests of messages and
     terminal proposals;
  2. run v1->v2 migration;
  3. verify marker 2, integrity, FK check, exact columns/indexes;
  4. verify active legacy session becomes superseded with reason;
  5. verify zero inferred coverage/base values and preserved row digests;
  6. run migration again and require byte/aggregate idempotence; and
  7. separately synthesize a v1 draft proposal and prove only that draft is
     superseded.

  Production DB remains read-only and unchanged.

- [ ] **Step 5: Run atomicity and no-lock Provider probe**

  Instrument SQLite transactions and a blocking fake responder. Require first
  transaction committed before Provider starts, no write lock during await,
  second transaction after response, and rollback of both profile/proposal on
  injected approval failure.

- [ ] **Step 6: Run static boundaries**

  Require zero hits for:

  ```text
  calibration agent/policy importing DAL, tools, evidence, ui_locale, resources
  approve request accepting or sending profile_patch
  freeform_notes in personalization context construction
  gather_evidence receiving personalization
  dynamic i18n keys or locale branches in new UI
  raw topic/field IDs in normal-mode render paths
  new aria-live, window.confirm, nested tablist, @media, 959/960/961 literals
  new literal allowlist/debt entries
  ```

- [ ] **Step 7: Run no-PG smoke**

  Use the repository's existing isolated no-PG harness and require
  `ok:true` plus `pg_attempts:[]`. Calibration migration/state, current Summary,
  and run snapshot reads must be local SQLite only.

- [ ] **Step 8: Run bilingual six-viewport browser matrix**

  Use scheduler-off sidecar, temp DB, isolated Vite/CDP ports, and both bundled
  locales at `1440x900`, `1024x768`, `961x768`, `960x768`, `959x768`, and
  `390x844`. Verify Summary/Edit/Calibration/Proposal, exact one Settings
  anchor, no nested tabs, complete fields, no overlap/overflow, command focus,
  dirty/busy guards, independent load failure, unknown topic, conflict,
  disclosure state, and in-place locale preservation.

- [ ] **Step 9: Run one bounded Provider live turn on an isolated DB copy**

  Start branch sidecar against an online backup on a separate port with
  scheduler disabled and ephemeral API token. Start guided calibration (zero
  Provider), submit one answer once, and verify a persisted answer/turn plus a
  valid adaptive next topic or legal partial proposal. Do not approve it. Do
  not retry a paid/failed call repeatedly. If credentials/provider service are
  unavailable, record typed `provider_config_missing` or responder failure and
  keep unit/fake-backed Provider completion as the implementation proof.

- [ ] **Step 10: Verify Research/Card transparency in the isolated profile**

  Create one new disabled trace and one enabled fake-backed run/card. Verify
  null legacy, empty disabled, and exact active snapshot in API and Drawer;
  current Summary context may differ and is labelled separately. Verify
  EvidencePacket and tool inputs are byte-identical to base fixtures.

- [ ] **Step 11: Clean all temporary processes/artifacts**

  Stop isolated sidecar/Vite/browser, remove temp DBs/profiles/screenshots only
  after evidence is summarized, confirm ports closed, and verify production DB,
  normal browser profile, and main checkout digests unchanged.

---

## Task 10: Record Review-Ready Evidence and Stop

**Files:**
- Modify: this plan
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [ ] **Step 1: Fill the evidence ledger**

  Record product tip, exact tests/collections, node comms, scanner hashes,
  copied-DB migration proof, atomicity/lock evidence, no-PG result, bilingual
  viewport matrix, bounded live result, immutable hashes, and cleanup PIDs/ports.

- [ ] **Step 2: Mark review-ready, not LIVE**

  Set status to `IMPLEMENTED — INDEPENDENT IMPLEMENTATION REVIEW PENDING` and
  update the priority map. Do not merge, migrate production, restart normal
  desktop, or mark Slice 5 LIVE.

- [ ] **Step 3: Run final docs/diff checks and commit evidence**

  ```bash
  git diff --check
  git status --short
  git add docs/superpowers/plans/2026-07-22-p2-8-slice-5-investor-profile-workspace.md \
    docs/design/PROJECT_PRIORITY_MAP.md
  git commit -m "docs: record investor workspace verification"
  ```

- [ ] **Step 4: Request independent implementation review**

  Reviewer reruns canonical A/B, copied-DB migration, exact ledgers, static
  boundaries, and the bilingual interaction matrix. Stop here.

---

## Independent Reviewer Focus

1. exact backend `+53/-1`, frontend `+47/-1`, and only the two named removals;
2. policy matrix and deny list exactly partition `InvestorProfileBody`;
3. model-selected next topic is catalog-valid and uncovered before commit;
4. catalog order is display only and adaptive interview order is preserved;
5. pre-call intent / no-lock Provider / post-call completion transaction order;
6. repeated `turn_id` does not duplicate message or Provider call;
7. migration marker/fingerprint fail closed and legacy rows preserve bytes;
8. no GET/constructor schema writes and startup ordering precedes schedulers;
9. proposal clamp/base/conflict/approval atomicity and all-illegal no-proposal;
10. client approval body cannot replace stored patch;
11. current trace and exact context share one prompt-assembly sample;
12. Research null/empty/non-empty snapshot semantics and no terminal re-resolve;
13. Card snapshot uses synthesis context while evidence gathering is unchanged;
14. Summary shows effective state, not merely stored values;
15. precise Settings guard: dirty Edit only, clean Calibration exit, busy block;
16. opening prompt zero-call, semantic ID, canonical fallback, locale relocalize;
17. unknown topic counts honestly without normal-mode raw ID;
18. source answer/rationale/context byte preservation and notes non-causality;
19. Proposal Review content, conflict retention, focus, and command spacing;
20. exact resources `settings 712 / research 5`, scanner unchanged at
    `1033/973/954/20`, 30 scopes, no allowlist/debt change;
21. Evidence Drawer new copy belongs only to `research` namespace;
22. six-viewports x two locales, no overlap/overflow, state/focus preservation;
23. immutable evidence/tools/shared-presenters/other Settings/desktop/extensions;
24. copied production DB only before merge and no production write during review.

---

## Stop Conditions

Stop and return to review if:

1. topic IDs, order, matrix fields, deny list, or opening prompt ID differ;
2. next-topic validation cannot remain server-owned and pre-commit;
3. Provider work requires a SQLite write lock to remain held;
4. idempotency requires deduping by text/time instead of client `turn_id`;
5. migration needs global `user_version`, lazy GET/constructor writes, or
   inferred legacy coverage/base values;
6. proposal approval cannot be one SQLite transaction with profile write;
7. any client-supplied approval patch must be accepted;
8. all-illegal proposal output would create an empty/pending proposal;
9. trace and context cannot be sampled at the same prompt-assembly point;
10. Research/Card history would require fabricated snapshot backfill;
11. personalization would enter evidence gathering or calibration would gain tools;
12. `freeform_notes` or a localized UI label would enter prompt context;
13. UI needs a second anchor, nested tabs, Drawer/Popover, polling, route, or
    persistence key;
14. Calibration exit must be treated as dirty or Edit guard remains heuristic;
15. frontend must duplicate topic-to-field policy;
16. source content must be translated or reconstructed;
17. resource counts differ from `Settings 712 / Research 5`, keys differ, or
    leaves are empty;
18. scanner differs from `1033/973/954/20`, requires a new allowlist/debt entry,
    or migrated scopes differ from 30;
19. backend/frontend collection differs from exact ledgers without a reviewed
    plan amendment;
20. new CSS needs a breakpoint, media query, nested card, viewport font scaling,
    or causes canonical viewport overflow;
21. an immutable file/tree changes;
22. no-PG smoke records an attempt;
23. normal mode exposes Provider diagnostic, raw unknown topic ID, credential
    identity, secret, or private path;
24. verification requires writing production DB/browser profile; or
25. a live Provider failure would be retried repeatedly to force a successful gate.

---

## Post-Review Merge and Production Migration

Only after independent implementation GREEN and explicit user approval:

1. close normal app, sidecar, browser extension writers, and test servers;
2. create retained timestamped `0600` SQLite online backup of production
   `profile_state.db` and record its SHA-256;
3. restore the main checkout to clean tracked state and fast-forward merge the
   reviewed branch;
4. run merged code only for calibration v1->v2 migration; never let pre-Slice-5
   code reopen a production v2 calibration schema;
5. verify marker 2, `integrity_check`, `foreign_key_check`, preserved message /
   terminal proposal digests, legacy active/draft supersession, and no inferred
   coverage/base values;
6. rerun merged focused `219`, full backend collect `4621`, frontend `81/824`,
   typecheck, build, scanner, no-PG, resources, immutable gates, and one normal
   desktop Summary smoke;
7. mark spec/plan/map LIVE with merge/evidence hashes;
8. keep the retained backup until the user confirms normal operation;
9. remove implementation worktree/branch and temporary artifacts; and
10. choose the next priority-map unit only after merged-master closeout.
