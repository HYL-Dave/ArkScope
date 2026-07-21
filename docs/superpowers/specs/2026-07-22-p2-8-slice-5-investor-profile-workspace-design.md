# P2.8 Slice 5 Investor Profile Workspace Design

> **Status: WRITTEN REVIEW APPROVED — IMPLEMENTATION PLAN NEXT**
>
> Written against merged `master` at `bca064d4` on 2026-07-22. This document
> is the bounded product and data-contract authority for P2.8 Slice 5. It does
> not authorize product implementation until a separate RED-first
> implementation plan receives independent written review GREEN. Independent
> full-document review approved this design on 2026-07-22; the sole required
> clarification, next-topic validation versus display ordering, is incorporated
> in Sections 4.1, 6.2, and 13.1. The implementation-plan review also aligned
> the per-run null snapshot case in Section 8.3 with queued runs that never
> reached prompt assembly; this is an honest extension of the same no-snapshot
> state, not a fabricated legacy backfill.

## 1. Purpose and Authority

The current Investor Profile surface is a long form followed by a calibration
conversation that starts with an empty text box. It exposes profile values, but
does not make the most common Settings task easy: confirm what personalization
is currently active, understand how it changes AI behavior, and deal with a
pending proposal without reading the entire form.

Slice 5 turns the existing `investor_profile` Settings anchor into a
summary-first workspace with three explicit secondary modes:

- Edit Profile;
- Calibration; and
- Proposal Review.

The slice also closes two backend integrity gaps:

1. calibration proposals currently expand partial model output against default
   values and can therefore overwrite fields that were never discussed; and
2. Research/Card runs persist a stance trace, but not the exact personalization
   context that was actually injected into the prompt.

Authority order:

1. [`ARKSCOPE_TERMINOLOGY.md`](../../design/ARKSCOPE_TERMINOLOGY.md) owns
   canonical English and Traditional Chinese terms.
2. The P2.8 canonical shell design owns Settings workflow tabs, the single
   Investor Profile anchor, focus behavior, and shared UI primitives.
3. The app-wide i18n decision owns locale mechanics and source-content
   boundaries.
4. [`INVESTMENT_SKILLS_PROFILE_DESIGN.md`](../../design/INVESTMENT_SKILLS_PROFILE_DESIGN.md)
   remains the authority for the meaning and downstream use of approved
   profile fields.
5. This document owns the Slice 5 information architecture, guided calibration
   protocol, proposal field policy, transparency surface, compatibility
   behavior, and verification contract.

### 1.1 Grounded baseline

At `bca064d4`:

- `InvestorProfileBody` has exactly 13 mutable fields;
- `payload()` preserves partial-update intent through `model_fields_set`;
- `concentration_limit_pct` is already present in both schema and Edit UI;
- `normalize_proposal_payload()` expands a model patch into a complete profile,
  including fields that were not discussed;
- calibration has sessions, messages, and proposals, but no closed topic
  catalog, prompt ID, turn ID, coverage proof, or proposal base values;
- starting calibration creates an empty session and no opening question;
- sending a calibration message stores the user turn before the Provider call,
  so an interrupted call can leave an unmatched user message;
- the profile response already returns `context_preview`;
- approved structured profile fields influence synthesis/chat emphasis only and
  do not enter evidence gathering;
- `freeform_notes` is not included in the personalization context;
- suggested/applied skill arrays remain empty and no skill engine is injected;
- the I18N-0 through I18N-2 line did not modify prompt or personalization
  construction paths; localized UI submits stable IDs, not translated labels;
  and
- the production profile DB contains one legacy active calibration session
  with 12 messages and one approved proposal, and no draft proposal. These are
  a migration observation, not an acceptance constant.

## 2. Goals and Non-Goals

### 2.1 Goals

Slice 5 must:

1. make the current effective personalization state readable before editing;
2. preserve one Settings anchor and one mounted Investor workspace;
3. provide a guided, resumable calibration interview with an immediate first
   question and honest topic coverage;
4. ensure a proposal can change only fields supported by topics actually
   covered in that session;
5. keep all user-owned notes and uncovered profile fields unchanged;
6. make current and per-run personalization context inspectable;
7. ship every new product-owned string in `zh-Hant` and `en` from birth;
8. preserve existing generation guards, Developer diagnostics, draft behavior,
   and evidence-gathering boundaries; and
9. remain usable without horizontal overflow at every canonical viewport.

### 2.2 Non-goals

This slice does not:

- add a Settings anchor, nested tablist, Popover, Drawer, or glossary surface;
- add investment advice, market/news/web/code tools, or evidence retrieval to
  calibration;
- pass `ui_locale` into a model prompt or translate model/user source content;
- create or modify a skill engine;
- inject `freeform_notes` into AI context;
- create an AI-guidance free-text field;
- expose the public locale selector;
- redesign the whole Evidence Drawer or migrate its existing I18N-4 debt;
- change EvidencePacket gathering or let personalization select evidence;
- fabricate context snapshots for historical runs;
- infer new topic coverage or base values from legacy calibration prose; or
- turn calibration into a required gate before using ArkScope.

## 3. Workspace Information Architecture

### 3.1 One anchor, four ephemeral modes

The existing `investor_profile` anchor remains the only registry destination.
Its default and reload state is Summary. Edit Profile, Calibration, and
Proposal Review are ephemeral component modes:

- they are not routes, anchors, tabs, or persisted preferences;
- Settings search and `NavigationTarget` always land on Summary;
- reload always returns to Summary; and
- only the active mode is mounted.

The command-driven structure is intentional. Edit and Calibration are actions,
not peer destinations that deserve a nested tablist. Calibration is a primary
workflow and therefore does not belong in a constrained Drawer.

### 3.2 Summary

Summary answers “what is active now?” and displays effective behavior rather
than merely echoing stored fields. It contains:

1. personalization enabled/disabled;
2. effective Assistant Stance;
3. primary investment style and holding horizon;
4. Risk appetite, Risk capacity, and the four-state mismatch result;
5. current calibration session state;
6. a pending proposal card when one exists; and
7. a concise personalization-effects disclosure defined in Section 8.

`Not assessed / 未評估` is an honest mismatch state, not an error. A disabled
profile remains visible as stored data while Summary clearly states that it is
not currently shaping AI behavior.

Commands are state-aware:

- `Edit Profile / 編輯 Profile` is always available when the profile leg is
  ready;
- `Start Calibration / 開始校準` appears when no current guided session exists;
- `Continue Calibration / 繼續校準` appears when a guided session can resume;
  and
- `Review Proposal / 檢視提案` exists only inside a pending proposal card.

The pending proposal card gives coverage its own line and the review command a
separate action row. Text and controls must never overlap.

### 3.3 Edit Profile

Edit continues to expose all 13 mutable profile fields, including the existing
single-position limit. It preserves the current full-save and draft-save
distinction:

- saving a draft posts the partial draft and stays in Edit;
- saving the profile performs the current full validation, then returns to
  Summary only after a fresh profile GET succeeds; and
- leaving Edit with dirty values opens the existing value-free ConfirmDialog.

The dialog never includes field values, notes, prompt content, or Provider
details. Cancel keeps the draft and focus in Edit. Confirm discards the draft,
returns to Summary, and restores focus to the `Edit Profile` command.

`freeform_notes` is labeled as a personal record that currently does not affect
AI analysis. It remains user-authored only.

### 3.4 Calibration

Calibration is a guided interview, not a blank chatbot. It displays:

- one current question;
- the conversation journal;
- covered and remaining topic progress;
- a concise explanation for unfamiliar topic groups; and
- an explicit “propose now” action that may end the interview early.

Leaving Calibration is always allowed without a discard confirmation because
the server journal is durable and resumable. A pending save/approve operation
may hard-block mode switching with an InlineAlert; it must not create a second
guard mechanism.

The current question receives focus on entry. Returning to Summary restores
focus to the Start/Continue Calibration command.

### 3.5 Proposal Review

Proposal Review is reachable only from a pending proposal card. It shows:

- covered-topic chips in backend catalog order;
- each proposed field with a localized field label and `current -> proposed`
  comparison; closed semantic IDs use the existing localized presenter while
  numeric/list values preserve their normalized meaning;
- model rationale verbatim as source content;
- Approve and Reject commands; and
- a persistent conflict state when current values no longer match proposal
  base values.

Raw snake_case fields, raw topic IDs, and raw model output envelopes never
appear in normal mode. Reject returns to a freshly loaded Summary. Approve
returns only after the atomic update succeeds and a fresh GET confirms the
effective profile. A conflict performs no profile write and leaves the proposal
pending for explicit rejection or recalibration.

### 3.6 Concept explanations

The existing Settings disclosure pattern owns explanations. There is no new
Popover or glossary primitive.

- Values, coverage, and mismatch warnings remain visible while disclosures are
  closed.
- Each explanation covers a coherent concept group, such as Risk appetite
  versus Risk capacity, rather than attaching isolated definitions to every
  field.
- Topic labels must be understandable without opening a disclosure; the
  disclosure adds context rather than rescuing an opaque label.
- Disclosure state is ephemeral and not persisted.
- Changing locale preserves disclosure state and focus while translating its
  chrome in place.

## 4. Calibration Topic and Field Policy

### 4.1 Ordered topic catalog

The backend owns this ordered catalog and its field policy:

| Topic ID | User-facing concept | Question style | Proposable fields |
| --- | --- | --- | --- |
| `loss_response` | How you respond to losses / 遇到虧損時怎麼做 | Situational | `risk_appetite`, `drawdown_tolerance_pct` |
| `financial_capacity` | What your finances allow / 資金能承受多少 | Direct or situational | `risk_capacity` |
| `time_horizon` | How long you invest / 預計持有多久 | Direct or situational | `holding_horizon` |
| `single_position_limit` | Single-position limit / 單一持股上限 | Direct or situational | `concentration_limit_pct` |
| `risk_avoidances` | Risks you avoid / 不碰哪些風險 | Direct | `avoidances` |
| `behavioral_patterns` | Behavioral patterns to watch / 容易受哪些行為影響 | Situational | `behavioral_flags` |
| `investment_approach` | Research approaches you prefer / 偏好的研究方法 | Direct | `primary_preset`, `preferred_edge` |
| `assistant_style` | How you want AI to work with you / 希望 AI 如何配合 | Direct | `default_stance` |

The order above is the only presentation order. The frontend does not sort or
reorder topics. Interview order is adaptive: the model may select the next
topic only from the still-uncovered catalog set. Catalog order does not turn
the interview into a fixed script.

### 4.2 Complete field partition

The explicit never-proposable deny-list is:

- `enabled`;
- `freeform_notes`; and
- `skill_mode`.

The matrix field union and deny-list must be disjoint and together equal the
complete 13-field `InvestorProfileBody` set. Derived fields such as
`risk_mismatch` and timestamps are not Body fields and are never proposable.

This is a structural invariant, not a snapshot assertion. Adding a future Body
field must fail the catalog test until the field is explicitly assigned to a
topic or to the deny-list.

The backend catalog is the single policy authority. The frontend duplicates no
topic-to-field matrix. It owns only exhaustive topic-ID-to-resource display
mapping. Backend and frontend each pin the same literal topic ID set as a
display-completeness tripwire, so adding a topic forces both policy and copy
work.

An unknown topic from a newer backend remains visible as localized
`Other topic / 其他主題`, counts toward total progress, and exposes its raw ID
only in a fail-closed Developer diagnostic. Hiding it would make coverage
misleading.

### 4.3 Coverage authority

Coverage is structured state, never inferred from prose:

- the backend reports the current question topic and the topic addressed by
  each completed turn;
- only the server-selected current topic can become newly covered on that turn;
- covered topics are monotonic within a session;
- the model cannot mark an unasked topic covered;
- the frontend renders only backend coverage IDs; and
- all topics covered triggers a proposal, while the user may request an early
  proposal at any time.

An early proposal may include only fields belonging to covered topics. It must
list the topics covered in that proposal so partial scope is obvious.

## 5. Deterministic Opening Question

Starting a session performs no LLM call and requires no AI credential. The
backend persists a versioned semantic prompt ID and canonical fallback text.

V1 opening prompt:

- prompt ID: `loss_response.opening.v1`;
- topic: `loss_response`;
- English canonical fallback: `Suppose an important holding falls 18% over a short period while its long-term thesis is not clearly broken. What would you usually do?`; and
- Traditional Chinese resource: `假設一個重要持股在短期內下跌 18%，但長期 thesis 尚未明確失效，你通常會怎麼處理？`

For a known prompt ID, the frontend renders the current-locale resource. For an
unknown prompt ID, it renders the DTO's canonical text rather than hiding the
question. Prompt IDs are append-only and versioned: changing wording creates a
new ID, while old resource keys and canonical expansions remain available for
old journals.

The backend and frontend each pin the same literal supported opening-prompt ID
set as a display-completeness tripwire. Canonical prompt text and expansion
remain backend-owned; the frontend owns only localized rendering for known IDs.

Before the first answer, reload reconstructs the fixed question from persisted
prompt metadata. After the first answer, reload reconstructs the model-driven
journal and current structured question state.

The journal stores the user's answer with the prompt ID. When building model
context, the backend expands the prompt ID to canonical question text. The
frontend may display that question in a different locale. This is an accepted
design: model language mirroring is anchored to the user's answer, not to
`ui_locale`, and no locale preference is injected into the prompt.

## 6. Turn State Machine and Provider Boundary

### 6.1 Durable turns

Each submitted answer carries a client-generated `turn_id`.

1. A short SQLite transaction validates the session/current question, stores
   the answer, and records one pending turn.
2. The transaction closes before any Provider call.
3. The Provider receives the canonical journal, closed topic catalog, current
   topic, and structured-output contract. It receives no tools.
4. A second short transaction stores the assistant question, validated coverage
   transition, optional proposal, and completed turn state.

Retrying the same `turn_id` must not duplicate a user or assistant message.
There may be at most one pending turn per session.

Provider, parsing, or catalog-validation failure preserves the user's answer
and marks the turn failed/retryable. Sidecar startup reconciliation, not a
status read, marks stale pending turns interrupted/retryable. If no credential
is configured, calibration uses the existing `provider_config_missing` typed
error family and Provider navigation guidance; it does not invent a new
credential error vocabulary.

### 6.2 Structured model response

The model response contains:

- assistant question or transition text;
- the addressed topic ID, which must equal the server-selected current topic;
- whether that addressed topic is now covered;
- next topic ID when another question is needed; the server accepts it only
  when it belongs to the catalog and is still uncovered, and only then makes it
  the new server-selected current topic;
- optional partial profile patch;
- proposal rationale; and
- no free-form authority to add topic IDs or profile fields.

“One question at a time” is a prompt contract, not a brittle frontend parser.
The UI renders model source text even if a model occasionally asks a compound
question; prompt QA owns that drift. After the first answer, the prompt asks the
model to mirror the language of the user's answer for questions and rationale.
It does not use `ui_locale` as a language signal.

An invalid or already-covered next topic is a catalog-validation failure. The
turn retains its answer, becomes failed/retryable, and advances neither current
topic nor coverage.

### 6.3 Load and race behavior

Summary loads Profile and Calibration independently under one monotonic request
generation:

- Profile failure is load-blocking and offers the existing localized retry;
- Calibration failure is a partial/degraded state and must not be rendered as
  “no active session” or “no pending proposal”;
- a valid default profile is an honest empty state;
- an initial read never overwrites an Edit object after the user has started
  editing;
- an explicit save/reject/approve/retry wins over any stale earlier response;
  and
- approve installs the returned profile first; an advisory refresh may follow
  without rolling it back.

These preserve the generation guard established by I18N-2 Decisions 62-64.

The domain-to-common-state mapping is:

| Domain condition | Common state | Required presentation |
| --- | --- | --- |
| Profile request unresolved | `loading` | Loading state for the whole Summary; no invented defaults yet. |
| Profile ready, no explicit saved customization | `empty/ready` | Valid default profile with setup actions, not an error. |
| Calibration request unresolved while Profile is ready | `loading` | Calibration subregion remains pending; profile facts stay visible. |
| Calibration request failed while Profile is ready | `partial` | Keep profile facts and show localized retry; do not claim no session/proposal. |
| Turn awaiting Provider | `running` | Bounded progress and mode-switch veto where applicable. |
| Provider/configuration unavailable | `blocked` | Typed guidance to Provider settings. |
| Turn interrupted or retryable | `interrupted` | Preserve answer and offer retry of the same `turn_id`. |
| Pending proposal | `ready` + action | Proposal card and Review command. |
| Base-value conflict | `blocked` | No write; keep proposal pending for user disposition. |

## 7. Proposal Integrity and Approval

### 7.1 Generation clamp

The backend derives the allowed proposal field set from covered topics and
clamps model output to it. Out-of-scope, unknown, deny-listed, and derived fields
are discarded from generation output and recorded only as sanitized Developer
diagnostics. If no legal fields remain, no proposal is created.

The stored proposal contains only:

- the partial legal patch;
- covered topics;
- normalized base values for exactly the proposed fields;
- changed fields;
- source rationale; and
- lifecycle/conflict metadata.

The current behavior that expands a partial proposal into a complete default
profile is retired. Partial remains partial through storage, DTOs, review, and
approval.

### 7.2 Approval validation

Approval is fail-closed. The client identifies the stored proposal; it does not
send a replacement patch. The backend applies only the reviewed partial patch
already stored with that proposal. Any unknown, deny-listed, uncovered, or
otherwise invalid stored field rejects the entire approval with zero profile
write. A client request that attempts to inject patch fields is rejected at the
request schema boundary.

Before applying, the backend compares current values with proposal base values:

- scalar values use exact normalized equality; and
- `avoidances`, `preferred_edge`, and `behavioral_flags` use set equality and
  ignore order.

A mismatch marks the proposal conflicted while leaving it pending. It does not
silently supersede or partially apply. The user may reject it or recalibrate.

On success, merging only the proposal patch into the current profile and
marking the proposal approved occur in one SQLite transaction. Any error rolls
back both. Reject updates only proposal state.

## 8. Personalization Effect and Transparency

### 8.1 What the profile changes

Investor Profile remains functional and intentionally influences AI output.
Its approved structured fields build a bounded personalization context used for
synthesis and chat emphasis. They may affect framing, risk emphasis,
time-horizon interpretation, concentration warnings, preferred research style,
and Assistant Stance.

They do not alter evidence collection, source selection, factual retrieval, or
EvidencePacket construction. The shared evidence guard remains part of the
prompt contract. Slice 5 does not inject an actual skill, and suggested/applied
skill traces remain truthful.

Summary shows a localized plain-language effect description for each of the
seven closed Assistant Stance values. This description is static product copy;
it is not parsed from prompt text.

### 8.2 Current context disclosure

Summary includes a disclosure labeled as the context that would be applied
now. It renders the backend's exact `context_preview` byte-for-byte as source
content:

- it is not translated, reformatted, or reconstructed in the frontend;
- disabled personalization renders an exact empty context with localized
  explanatory chrome; and
- the disclosure visibly distinguishes current settings from historical run
  context.

The `freeform_notes` help text is auditable: users can inspect the exact current
context and verify that notes are absent.

### 8.3 Per-run context snapshot

Every new Research and AI Card run captures the exact personalization context
at actual prompt assembly/execution time, not at queue creation. The persisted
trace and DTO distinguish:

- non-empty string: exact context used for that run;
- empty string: a new run executed with personalization disabled; and
- null/missing value: no snapshot exists for a pre-Slice 5 run, or for a new
  queued run that never reached prompt assembly/execution.

Historical runs are never backfilled from current profile state.

The per-run Evidence Drawer displays this exact source context under an
explicit “used for this run” label, separate from Summary's “would be used now”
disclosure. New Drawer chrome ships bilingual from birth. Existing Drawer copy
outside this bounded addition remains owned by I18N-4.

A golden byte-exact fixture pins context construction and snapshot storage. It
must fail if localized UI labels enter the prompt, if the context changes
without review, or if null and empty collapse into one state.

### 8.4 Freeform notes consent boundary

`freeform_notes` remains a private personal record and never enters a prompt.
Automatically giving existing notes causal AI effect would retroactively change
the contract under which they were written and could turn informal or
instruction-like text into prompt content without renewed consent.

If a future product need justifies free-text AI guidance, it must use a new,
explicitly opt-in field whose UI states that it affects AI. Existing notes must
never be copied or migrated into that field automatically.

## 9. Persistence and Compatibility

### 9.1 Semantic storage additions

Implementation may choose normalized columns or a focused companion table, but
the durable model must represent these facts without deriving them from prose:

- session interview version and lifecycle;
- ordered covered topic IDs and current topic;
- opening/current prompt ID plus canonical fallback;
- idempotent turn ID and pending/completed/failed/interrupted state;
- proposal covered topics, partial patch, base values, conflict state, and
  lifecycle;
- exact per-run personalization context snapshot; and
- null versus empty snapshot semantics.

The implementation plan must choose one physical owner for each fact and must
not create JSON/column dual authorities.

### 9.2 Legacy calibration migration

Legacy dialogue remains historical source data. Migration must not infer topic
coverage, prompt IDs, or proposal base values from message text.

- completed approved/rejected legacy proposals and all messages remain
  byte-preserved;
- a legacy active session without the guided-interview version is marked
  `superseded` with a machine-readable migration reason, then retained;
- a legacy draft proposal without coverage/base provenance is retained but
  marked `superseded`, not `rejected`, and can never be approved;
- legacy closed/superseded sessions remain unchanged; and
- the next calibration command starts a new guided session.

This policy matches the production observation of one active legacy session
with an approved proposal while remaining safe for copied/test DBs that may
contain legacy drafts. No historical content is deleted and no user action is
falsely recorded.

Migration is idempotent, transaction-bounded, and fail-closed on a marker/schema
mismatch. It runs in an explicit sidecar startup migration phase before routes
are served. Read/status paths do not create or migrate schema.

## 10. Error, Privacy, and Permission Boundaries

- Permission/configuration gates run before any paid Provider call.
- SQLite write locks are never held while waiting for a Provider.
- Normal mode presents localized typed errors and actions.
- Raw Provider errors, unknown topic IDs, rejected model fields, internal field
  names, and parser diagnostics are Developer Mode only and fail-closed.
- User answers, model questions, proposal rationale, and exact context are
  source content; they are not inserted into translation resources.
- Guard/ConfirmDialog payloads contain no profile values, notes, dialogue,
  rationale, context text, credentials, or raw errors.
- Calibration has no research tools and cannot fetch market facts or make an
  investment recommendation.
- Model output is parsed into the reviewed schema before storage or rendering;
  raw envelopes never reach normal UI.

## 11. Localization and Terminology

All new chrome uses the existing typed resource system, primarily under
`settings.investor.*`. The bounded Evidence Drawer addition uses its owning
namespace. Both locales ship in the same change with exact key parity and
non-empty values.

Stable IDs remain payload values. Topic IDs, prompt IDs, field names, and error
codes are never translated and never used as normal-mode labels.

Locale switching must preserve state and focus in each of these cases:

1. Edit contains a dirty draft;
2. Calibration contains a live conversation/current question;
3. a concept disclosure is expanded; and
4. a pending proposal is visible or being reviewed.

Only product chrome changes language. Draft values, user/model source content,
request identity, and mode stay intact. The known semantic opening prompt is
the deliberate exception: it re-renders from `prompt_id` in the new locale
without changing journal identity.

The terminology authority records all new topic labels and mode/action names.
No visible label duplicates `translation · original`. English aliases may
remain searchable without being printed in zh-Hant.

## 12. Responsive and Accessibility Contract

The complete Summary, Edit, Calibration, and Proposal Review states are tested
in both locales at:

- `1440x900`;
- `1024x768`;
- `961x768`;
- `960x768`;
- `959x768`; and
- `390x844`.

Required behavior:

- no horizontal overflow, clipping, incoherent overlap, or hidden commands;
- topic chips wrap without changing adjacent control geometry;
- proposal coverage and action rows remain separate;
- long English labels and source rationale wrap naturally;
- only one Investor mode is mounted;
- mode entry focuses its heading/current question;
- return restores focus to the initiating Summary command;
- ConfirmDialog and busy-veto focus behavior remains intact;
- disclosures retain native/shared keyboard semantics; and
- no new `aria-live` region is introduced.

The slice uses existing PageHeader, section bands, InlineAlert,
SettingsDisclosure, ConfirmDialog, StatusBadge, and button/icon conventions. It
does not introduce a new UI primitive.

## 13. Verification Contract

### 13.1 Backend and persistence

Tests must prove:

1. the topic catalog order and exact topic ID set;
2. every matrix field belongs to `InvestorProfileBody`;
3. matrix union plus deny-list is an exact disjoint partition of all 13 Body
   fields;
4. coverage is monotonic and only the asked topic can advance;
5. next-topic selection is adaptive only within the uncovered catalog set, and
   invalid/already-covered choices leave current topic and coverage unchanged;
6. partial proposals remain partial through generation, storage, DTO, and
   approval;
7. malicious deny-listed, uncovered, unknown, and extra approval fields cause
   zero profile writes;
8. an all-illegal model patch creates no proposal;
9. scalar and set-valued base comparisons follow Section 7.2;
10. conflicts remain pending/conflicted and write nothing;
11. profile merge plus approved state is one rollback-safe transaction;
12. `turn_id` retries do not duplicate messages;
13. startup reconciliation marks stale pending turns interrupted/retryable;
14. no credential uses the existing typed configuration family;
15. the opening prompt starts with zero Provider calls and survives reload;
16. post-answer reload reconstructs the model-driven journal;
17. legacy migration preserves messages/proposals, supersedes only unsupported
    active/draft state, and is idempotent;
18. exact context snapshots distinguish non-empty, empty, and legacy null;
19. evidence gathering receives no personalization context;
20. `freeform_notes` never appears in context; and
21. suggested/applied skills remain truthful and are not fabricated.

### 13.2 Frontend and localization

Tests must prove:

1. exact-anchor reveal, search, and reload land on Summary;
2. Proposal Review is absent without a pending proposal;
3. draft save stays in Edit while full save/approve fresh-load Summary;
4. dirty Edit discard and clean/calibration exits follow distinct rules;
5. pending busy operations block mode switching with value-free copy;
6. known and unknown topic/prompt IDs follow the reviewed display fallbacks;
7. covered topics and proposal fields render in backend order with localized
   labels and unchanged source values;
8. locale switching during dirty Edit, active Calibration, open disclosure, and
   pending Proposal Review preserves state and focus while translating chrome;
9. the semantic opening question re-translates in place without changing its
   prompt/session identity;
10. current and per-run context disclosures are clearly different and preserve
    source bytes;
11. normal mode exposes no raw field/topic IDs, model envelope, or Provider
    detail; and
12. `zh-Hant`/`en` resources have exact non-empty key parity and all touched
    scopes pass the CJK literal ratchet.

### 13.3 Canonical gates

The implementation plan must publish an exact RED-first node ledger. It must
run focused backend/frontend suites, complete backend canonical A/B, full
Vitest, typecheck, production build, i18n scanner checks, no-PG smoke, static
privacy/ownership ratchets, and the complete two-locale six-viewport matrix.

After fake-backed paths and all static gates pass, one bounded live Provider
calibration smoke may verify a single turn and partial proposal. It must not
perform repeated paid calls merely to prove retry behavior.

## 14. Delivery and Review Sequence

1. Independent written review must return GREEN on this document.
2. A separate RED-first implementation plan must ground current baselines,
   physical schema ownership, file map, exact node accounting, migrations, and
   live-gate procedure.
3. Plan review must return GREEN before a feature worktree or product edit.
4. Implementation stops at independent implementation review.
5. Merge requires explicit user approval.
6. Post-merge closeout updates this status, the canonical shell, terminology,
   priority map, Design Kit, and memory as separate evidence.

Independent written review completed Step 1 on 2026-07-22. Slice 5 remains
design-only until the separate implementation plan completes Steps 2 and 3.
