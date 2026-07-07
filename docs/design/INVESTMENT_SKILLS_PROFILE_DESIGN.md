# Investment Skills + Investor Profile Design

> **Status: ACTIVE DESIGN - no implementation plan yet.** Drafted 2026-07-06 after the
> B6 repo-hygiene ruling moved `config/skills/` and the packaged skill boundary out of
> cleanup and into product design. This document is the authority for how ArkScope should
> personalize investment analysis with user profile, assistant stance, and skills. It
> does not authorize runtime changes by itself.

## 1. Problem

ArkScope already has a useful financial skills substrate, but it is not yet a product
experience:

- `resources/skills/` contains 10 packaged `SKILL.md` workflows, including DCF, comps,
  earnings analysis, catalyst calendar, portfolio scan, and full analysis.
- `src/agents/shared/skills.py` already loads a tiered registry, aliases, trigger phrases,
  and custom skills from `config/skills/`.
- `config/user_profile.yaml` already contains early investment preferences such as risk
  tolerance, style, holding period, watchlists, and strategy weights.

The missing layer is not "more prompt text". The missing layer is a controlled product
model for:

1. who the user is as an investor,
2. what role the assistant should play for this run,
3. which skills are useful for the task,
4. when skills may be suggested or automatically applied,
5. how the UI explains the above without hiding analysis machinery.

The user requirement is explicit: this feature must be optional, and the assistant should
not merely change tone. It should embody a useful investment posture, such as being more
conservative, more willing to consider risk, more strictly rational, or deliberately
complementary to the user's own tendencies.

## 2. Current Grounding

### 2.1 Existing skills substrate

`src/agents/shared/skills.py` currently defines:

- `SkillDefinition`: name, description, prompt template, aliases, trigger, category,
  required params, data sources, output, `auto_apply`, and source path.
- Tiered loading:
  - Tier 1 builtin: `resources/skills/builtin/**/SKILL.md`, hard-fail and protected.
  - Tier 2 packaged categories: `resources/skills/{category}/**/SKILL.md`.
  - Tier 3 custom: `config/skills/custom/**/SKILL.md` or legacy `config/skills/*.yaml`.
- Alias map and trigger index.
- `match_skill_trigger(question)`, `expand_skill(name, params)`, and
  `build_auto_apply_context(skill, question)`.

Important current-state split:

- **Workbench / web research paths** do not currently use trigger matching or auto-apply.
  For those surfaces, `off` can be tested as byte-identical current behavior.
- **Legacy CLI and Discord paths already auto-apply some skills by default.**
  `SkillDefinition.auto_apply` defaults true, `can_auto_apply()` allows paramless skills,
  `src/agents/cli.py` injects `build_auto_apply_context()` for a unique auto-applicable
  match, and `src/monitor/discord_bot.py` has the same pattern.

So v2 auto-trigger is not merely "technically reachable"; a legacy version exists today
outside the workbench control model. This design does not bless that behavior as the
future contract. Track B must bring CLI under `skill_mode` semantics. The Discord surface
must be proven live and then either brought under the same contract or retired as a
pre-pivot surface in its own implementation plan.

### 2.2 Existing packaged skills

Current packaged skills:

- builtin: `earnings_prep`, `full_analysis`, `portfolio_scan`, `sector_rotation`
- equity research: `catalyst_calendar`, `earnings_analysis`, `idea_generation`
- financial analysis: `competitive_analysis`, `comps_analysis`, `dcf_model`

Notably, the user's desired DCF, comps, and earnings-analysis workflows already exist as
content. The design should reuse them instead of creating a parallel skill concept.

### 2.3 Existing profile and permission boundaries

`ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md` already locks the relevant controls:

- Reads from local/app data and enabled providers are not gated.
- `db_write` and `profile_state_write` are separate gated action classes.
- Memory recall is free read; memory writes go through `db_write`.
- User profile/universe-setting changes go through `profile_state_write`.

This design inherits those boundaries. Creating or editing Investor Profile is a
profile-state write. Suggesting skills is a read-only planning action. Automatically
applying skills may increase tool usage and must be explainable and controlled.

### 2.4 Evidence boundary

`ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md` §2 and Tool Catalog rule 9 make the EvidencePacket a
hard boundary: evidence is objective, source-labeled, and gathered before synthesis.
Investor Profile, Assistant Stance, and skill-selection policy must not change what counts
as evidence, silently filter evidence, or weaken required counter-thesis. They may shape
the synthesis/chat layer: what the assistant emphasizes, how it challenges the user, and
which explicit analysis frameworks it suggests or applies with trace.

## 3. Product Decisions

### 3.1 Split the user from the assistant

The model has two independent layers:

1. **Investor Profile**: durable description of the user as an investor.
2. **Assistant Stance**: per-run or default role the assistant adopts when the feature is
   enabled.

This split is load-bearing. A user can be a growth investor while asking the assistant to
act as a complementary risk-control reviewer. The assistant should not blindly mirror the
user's own bias.

### 3.2 Feature is opt-in

Personalized profile/stance behavior is off by default. When disabled, the agent behaves
like the current workbench: no profile-derived judgment posture, no personalized skill
suggestion, and no automatic skill application. This statement is scoped to the workbench
surface. The legacy CLI/Discord auto-apply call sites described in §2.1 are existing
out-of-contract behavior and must be handled by Track B before the product can claim a
global skill-mode policy.

The UI should make the active state visible:

- Profile personalization: off/on.
- Assistant stance for this run.
- Skill mode: off/suggest-only/auto-with-trace, where only the first two are v1/v1.5.

`profile.enabled=false` is the master switch. It forces effective stance to `off` and
disables profile-derived skill suggestions or auto-trigger, regardless of any saved
default stance.

### 3.3 v1 prioritizes profile and stance

v1 is not a skill automation project. It builds the durable profile and makes the
assistant's judgment stance explicit.

v1 must answer:

- What kind of investor is this user?
- What risks can the user actually tolerate, not just claim to tolerate?
- What behavioral biases should the assistant compensate for?
- Should the assistant align with the user, challenge the user, or impose strict risk
  discipline for this run?

### 3.4 v1.5 adds skill suggestion

Skill suggestion is useful but secondary. It helps expert users and teaches less expert
users which frameworks might apply.

The assistant may suggest skills with reasons, but not apply them automatically:

> Suggested skills: `dcf_model`, `comps_analysis`. Reason: the user asked whether the
> current price is justified, and both intrinsic value and relative valuation are relevant.

The UI or trace must clearly show that these were suggestions only.

### 3.5 v2 commits to opt-in auto-trigger

Auto-trigger is not rejected. It is a committed v2 track and must not be lost. It can be
pulled forward if implementation proves small, but only after v1/v1.5 have the necessary
controls.

v2 requires:

- explicit skill mode toggle: `off`, `suggest_only`, `auto_with_trace`;
- visible trace: which skills were applied and why;
- stance-aware selection policy;
- no hidden metered spend, external web access, code execution, DB write, or profile write
  without the existing permission gates;
- a way to undo or rerun without the auto-applied skills.

## 4. Investor Profile Model

The profile should capture both preferences and guardrails. It must not treat self-reported
risk appetite as truth.

### 4.1 Core fields

Recommended v1 fields:

| Field | Type | Meaning |
|---|---|---|
| `enabled` | bool | Whether personalized profile behavior is active. |
| `primary_preset` | enum | Growth, value, momentum, income, event-driven, balanced, custom. |
| `risk_appetite` | 1-10 | How much risk the user says they want. |
| `risk_capacity` | 1-10 | How much risk the user can plausibly absorb. |
| `risk_mismatch` | enum | none / appetite_above_capacity / capacity_above_appetite / unclear. |
| `holding_horizon` | enum | intraday / days-weeks / months / multi-year / mixed. |
| `drawdown_tolerance_pct` | number or bucket | Maximum portfolio drawdown the user can accept without likely forced selling. |
| `concentration_limit_pct` | number or bucket | Max intended single-position exposure. |
| `preferred_edge` | list | Growth, valuation, catalyst, quality, momentum, macro, options, sentiment. |
| `avoidances` | list | Things the user wants to avoid: leverage, unprofitable companies, binary events, high IV, etc. |
| `behavioral_flags` | list | FOMO, greed, overconfidence, panic selling, loss aversion, anchoring, narrative susceptibility, revenge trading, under-diversification. |
| `freeform_notes` | text | User's own description of goals, observations, and hopes. |
| `last_reviewed_at` | timestamp | Profile recency. |

### 4.2 Risk capacity vs appetite

The assistant must distinguish:

- **Risk appetite**: what the user wants or feels willing to take.
- **Risk capacity**: what the user can plausibly withstand.

The setup flow should deliberately surface mismatches. Examples:

- A user says they want high-growth aggressive investing but would panic at a 10% drawdown.
- A user wants concentrated positions but has short liquidity needs.
- A user chases large upside but cannot explain downside scenarios.

This is not paternalism; it is the core safety function of the profile. The assistant can
still analyze aggressive ideas, but it should label the mismatch and adjust warnings.

### 4.3 Freeform calibration

The setup should allow the user to write observations or hopes in their own words:

- "I like high-growth companies but sell too early."
- "I get greedy after big wins."
- "I want someone to challenge my AI-stock enthusiasm."
- "I care more about asymmetric upside than quarterly volatility."

The agent may ask follow-up questions to infer bias and capacity. The output should be a
structured profile proposal that the user confirms before saving.

## 5. Assistant Stance Model

Assistant Stance is separate from Investor Profile and can be changed per run.

Recommended v1 stances:

| Stance | Purpose |
|---|---|
| `off` | Do not use profile or stance. Current neutral behavior. |
| `neutral` | Use objective analysis; do not personalize materially. |
| `aligned` | Analyze in the user's preferred style while still showing risks. |
| `complementary` | Intentionally counterbalance the user's likely blind spots. |
| `strict_risk_control` | Prioritize downside, concentration, liquidity, and invalidation. |
| `valuation_rationalist` | Emphasize intrinsic value, peer valuation, margin of safety, and assumptions. |
| `growth_opportunity` | Emphasize catalysts, growth durability, TAM, execution, and optionality. |

The UI should not bury this in advanced settings. The user should be able to choose it
near the query/run surface, because it is a run-level behavior control.

When `profile.enabled=false`, the effective stance is `off`. Saved stance preferences may
remain in storage, but they are inert until profile personalization is enabled again.

## 6. Skill Selection Policy

### 6.1 v1: no skill selection

For the workbench surface, v1 may include the current explicit `/skill` command and
existing manual skills UI, but profile/stance does not automatically choose skills.

This does not describe the whole repository today: CLI and Discord currently have legacy
trigger-based auto-injection. Track B must explicitly settle those call sites instead of
letting them remain a parallel policy.

### 6.2 v1.5: suggest-only

The selector may rank candidate skills and show them with reasons.

Inputs:

- user query;
- ticker/task context if present;
- Investor Profile;
- Assistant Stance;
- skill metadata: name, description, trigger, category, required params, data sources,
  `auto_apply`.

Output:

```json
{
  "mode": "suggest_only",
  "suggestions": [
    {
      "skill": "dcf_model",
      "reason": "The query asks whether valuation is justified; DCF makes assumptions explicit.",
      "requires_confirmation": true
    }
  ]
}
```

No prompt expansion occurs in v1.5 unless the user accepts the suggestion.

Track B must include the legacy call sites:

- CLI: move from implicit unique-match auto-injection to the shared `skill_mode` contract.
  Default should be `suggest_only`, so existing users still see useful skill guidance
  without hidden context injection.
- Discord: first prove whether the bot surface is still live. If live, bring it under the
  same `skill_mode` contract. If not live, mark it as pre-pivot and retire or defer it in
  the implementation plan.

### 6.3 v2: auto-with-trace

The committed v2 auto-trigger policy:

- `off`: never suggest or apply skills.
- `suggest_only`: propose skills, user chooses.
- `auto_with_trace`: apply allowed skills automatically when confidence is high, but show
  the skill trace before or with the answer.

The trace must include:

- matched skill names;
- stance/profile factors used;
- trigger evidence;
- whether any required params were inferred;
- whether any gated actions were requested because of the skill.

Auto-application must be disabled for ambiguous multiple matches unless the selector can
explain a unique best match.

## 7. UX Flow

### 7.1 Profile setup

Recommended flow:

1. Choose a preset, starting with Growth Investor as a first-class preset.
2. Answer a short risk-capacity questionnaire.
3. Add optional freeform description.
4. App produces a structured profile draft.
5. User confirms, edits, or rejects.

The questionnaire should ask about actual behavior and constraints, not only preference:

- How large a drawdown would cause you to sell or lose sleep?
- How long can you hold through a thesis not working?
- What percent of your portfolio can one idea occupy?
- Have you held through a 30% drawdown before?
- Are you investing money you may need within 12 months?
- Do you prefer missing upside or avoiding large losses?

### 7.2 Run-time controls

Each research run should show:

- profile personalization: on/off;
- stance;
- skill mode;
- applied/suggested skills trace when relevant.

Persisted outputs must also record the personalization context. A card run or research run
generated under `strict_risk_control` is not directly comparable to one generated under
`growth_opportunity` unless the stored metadata says so. Store at least:
`profile_active`, `assistant_stance`, `skill_mode`, `suggested_skills`, and
`applied_skills`.

For v1, the trace may simply say:

> Profile personalization active. Stance: complementary. This run will emphasize
> valuation risk, thesis invalidation, and position-sizing warnings because the profile is
> growth-oriented with high risk appetite.

### 7.3 Review and correction

The user must be able to correct the profile. Corrections are profile-state writes and
use the existing `profile_state_write` permission class.

Examples:

- "Don't treat me as panic-prone."
- "I can tolerate 30% drawdowns in individual positions."
- "For crypto-related equities, be stricter than usual."

## 8. Storage Boundary

### 8.1 Recommended storage

The implementation should store Investor Profile and Assistant Stance in local
`profile_state.db`, not in `config/user_profile.yaml`.

Reasoning:

- Settings authority has been moving to local profile DB.
- Profile edits are app state, not repo config.
- Sync/export can later include the profile DB.
- `config/user_profile.yaml` remains import material and historical seed.

### 8.2 `config/skills/` decision

`config/skills/` currently exists as Tier 3 custom-skill directory. This design does not
delete it immediately, but it changes the desired end state:

- packaged built-in skills stay under `resources/skills/`;
- user-created custom skills should eventually live in profile DB or profile-owned
  exportable content, not repo config;
- `config/skills/` becomes an import/legacy bridge during the migration.

This requires its own implementation plan because it changes skill loading and export
semantics.

## 9. Agent Prompt Contract

When profile personalization is active, the agent context should contain a compact,
structured block. It should not dump raw questionnaire text unless useful.

This block belongs in synthesis/chat context only. It must not be passed into
`gather_evidence()` or any deterministic evidence collector, and it must not change the
EvidencePacket rules from ProductSpec §2. In card generation, stance can change emphasis
inside the synthesis prompt, not evidence eligibility.

Example:

```text
[Investor Profile]
Primary preset: growth
Risk appetite: high
Risk capacity: medium
Risk mismatch: appetite_above_capacity
Holding horizon: months
Behavioral flags: FOMO, narrative susceptibility, under-diversification

[Assistant Stance]
Mode: complementary
Instruction: Counterbalance growth bias. Preserve upside analysis, but explicitly test
valuation, downside, concentration, and invalidation.

[Skill Mode]
suggest_only
```

The agent must not claim the profile is an objective diagnosis. It is a user-confirmed
working model.

## 10. Safety and Permission Rules

1. Profile creation or update is `profile_state_write`.
2. Skill suggestion is read-only.
3. Skill application may lead to tool calls, but existing tool permission classes still
   apply.
4. No automatic `db_write`, `profile_state_write`, `external_web_access`,
   `external_browser_automation`, `code_execution`, or `metered_spend` bypass.
5. Auto-trigger v2 must expose trace and allow rerun without skills.
6. The assistant should challenge clearly harmful mismatches between stated appetite and
   plausible capacity.
7. Investor Profile and Assistant Stance must not alter deterministic evidence gathering,
   filter EvidencePacket items, or weaken required counter-thesis. Aligned stance still
   includes the strongest good-faith opposing view. Complementary stance amplifies
   counter-thesis and invalidation emphasis in synthesis; it does not change evidence
   rules.
8. The feature must not be marketed as financial advice or suitability determination. It
   is a research-personalization aid.

## 11. Implementation Tracks

### Track A - v1 profile and stance — ✅ IMPLEMENTED + MERGED 2026-07-07 (`b770826`)

Shipped exactly this scope plus two reviewed amendments: stance rides the server-owned
research runs (the current workbench execution path), and persisted traces cover
success/error/cancelled terminals. Off = byte-identical is pinned at the prompt, route,
and card-synthesis seams.

Build:

- profile schema and store;
- setup questionnaire;
- freeform profile draft flow;
- stance selector;
- prompt-context injection;
- profile/stance visible in run trace;
- persisted card/research run metadata for `profile_active`, `assistant_stance`,
  `skill_mode`, `suggested_skills`, and `applied_skills`.

Acceptance:

- workbench feature off means byte-identical agent prompt behavior;
- enabled profile creates explicit stance context;
- risk appetite/capacity mismatch is represented;
- profile edits require profile-state permission;
- when `profile.enabled=false`, workbench prompt behavior is byte-identical and effective
  stance is `off`.

### Track B - v1.5 skill suggestion

Build:

- skill-suggestion selector;
- reason strings;
- UI/trace display;
- accept suggestion action that expands selected skills.
- CLI legacy auto-apply call site brought under `skill_mode` with default
  `suggest_only`;
- Discord legacy auto-apply call site either brought under `skill_mode` if live or
  explicitly retired/deferred if proven pre-pivot.

Acceptance:

- suggestions do not auto-apply;
- multiple matches are shown as choices;
- trace records why a skill was suggested;
- no hidden tool execution occurs.
- legacy CLI/Discord behavior no longer bypasses the product skill-mode policy.

### Track C - v2 auto-trigger

Build only after Track A and Track B provide the controls:

- `auto_with_trace` skill mode;
- stance-aware skill auto-selection;
- high-confidence threshold and ambiguous-match refusal;
- applied-skill trace;
- rerun-without-skills path.

Acceptance:

- auto-trigger can be turned off globally and per run;
- every auto-applied skill is visible and explained;
- gated tool actions still prompt through the existing permission model;
- user can inspect and override the selection.

## 12. Non-Goals

- Do not build an embedded broker/advisor or suitability engine.
- Do not auto-trade.
- Do not delete `config/skills/` in the design slice.
- Do not rewrite existing packaged skills.
- Do not make auto-trigger default-on.
- Do not use profile to hide bear cases or contrary evidence.

## 13. Open Questions for Implementation Planning

These are planning questions, not blockers for this design:

1. Which profile-store API should own the new tables: a new `investor_profile_store.py` or
   an extension of an existing profile-state store?
2. Should v1 start with only Growth Investor preset, or ship a small preset set?
3. Should freeform calibration call an LLM in the setup flow, or first save raw notes and
   add structured inference later?
4. What exact UI surface owns the stance selector: query composer, Settings, or both?
5. Should profile export/import be part of the first implementation plan or deferred to
   the larger profile-portability track?
