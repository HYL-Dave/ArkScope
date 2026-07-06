# Repo Hygiene B6 — Module/Root-Dir Disposition (analysis · config · scripts · resources)

> **Status: ✅ EXECUTED — B7 merged 2026-07-06 (`cf4ec92`; A/B 37=37 + passed 3730=3730);
> rulings 2 (survivor table stands) + 3 (config/skills → skills design line) confirmed.** Third table of the hygiene line (after
> `REPO_HYGIENE_AUDIT_2026_07.md` + `DOCS_SWEEP_DISPOSITION_2026_07.md`).
> Boundary defaults come from the 2026-07-06 review ruling: analysis→src is a TDD slice;
> resources/skills = packaged data, never into src/; config = future db-ification, no
> deletions now; scripts survivor-table changes = standing-ruling changes.
> Nothing here executes anything.

## 1. `analysis/` — ✅ MIGRATED (B7 merged; `src/options_math/` live)

Root-level package (`option_pricing.py`, `rate_curve.py`, `__init__.py`) predating `src/`
conventions. **Name collision is real**: `src/analysis/` already exists (the AI-card
analysis pipeline: context_builder/contracts/factory), so B7 moves the options pricing
math package to **`src/options_math/`**.

Complete consumer inventory (rewired by the B7 implementation branch):

| Consumer | Sites |
|---|---|
| `src/tools/options_tools.py` | lazy imports at `:40` `:151` `:152` `:187` `:264` `:267` |
| `scripts/analysis/compare_bs_vs_american.py` | `:27` (retained survivor — must keep working) |
| `scripts/analysis/scan_option_mispricing.py` | `:51` (same) |
| `tests/test_option_pricing.py`, `tests/test_rate_curve.py` | direct imports, in-function imports, and `patch("analysis.rate_curve...")` string target |

(`tests/test_analysis_cards_api.py` is a false match — it imports the routes module.)

**Disposition**: B7 implementation branch `codex/b7-options-math` performs the verbatim
move + consumer rewiring with zero residue (no shim at `analysis/`). Branch evidence:
T1 RED matched `ModuleNotFoundError`, option/rate suites passed after the move, scripts
compiled, residue gates are clean, and scoped virgin A/B over the affected tests is
identical. Merge remains gated on reviewer full A/B.

## 2. `config/` — all live; nothing to clean

| File | Code/test consumers | Disposition |
|---|---|---|
| `user_profile.yaml` | 24 | keep (core config) |
| `tickers_core.json` | ~10 (collectors, native host, scheduler, profile route, UI) | keep; retire only inside the future config-db-ification slice (readers first) |
| `sectors.yaml` | 7 | keep |
| `macro_calendar_series.yaml` | 2 | keep |
| `event_types.yaml` | 1 | keep |
| `.env.template` | template (B4a already made it local-first) | keep |
| `skills/` (.gitkeep, EMPTY) | **read by code**: `skills.py:31` `_CUSTOM_DIR` (Tier 3a/3b custom skills) | **defer to the Investment-Skills design line** — retiring it = code change + deciding the custom-skills home (profile DB vs dir); not a hygiene call |

## 3. `scripts/` — survivor table re-audit: **TABLE STANDS, no changes recommended**

Any change here = changing the standing ruling (`REFACTOR_PROTECTION_SMOKE_GATES.md` §6);
per-subfolder evidence:

| Subfolder | Consumers | Verdict |
|---|---|---|
| `migration/` (10 files) | **10 test files** import `scripts.migration` (refusal/gate pins) | keep-historical (gate evidence; tests depend) |
| `scoring/` (7+README) | **4 test files** + S-G active import CLI | keep (user-ruled) |
| `diagnostics/` (1) | `tests/test_news_normalized_ibkr_adapter.py:16` imports the probe's helpers | keep (has a live test consumer — stronger than "ad hoc") |
| `analysis/` (3) | imports root `analysis/` package (see §1 — B7 must rewire) | keep-historical; B7 dependency noted |
| `huggingface/` (3) | none (docs/provenance) | keep (user-ruled) |
| `live/` (3) | none (operator smokes, deliberately outside CI) | keep |
| `p1_2/` (1) | none | keep-historical |
| `testing/` (2) | none | keep-historical (zero cost) |
| `visualization/` (3) | none | keep-historical (defer ruled 2026-06-01: reads live data, revisit at desktop UI) |
| `__init__.py` | test namespaces | keep (package marker) |

## 4. `resources/` — packaged skill library; keep, and it is BIGGER than earlier notes said

**Correction**: the hygiene audit said "5 skills" from a capped listing — the full listing
is **10 SKILL.md across 3 category dirs**:

- `builtin/`: earnings-prep · full-analysis · portfolio-scan · sector-rotation (Tier 1,
  hard-fail scan, canonical names pinned in `_BUILTIN_SKILL_NAMES`)
- `equity-research/`: catalyst-calendar · **earnings-analysis** · **idea-generation**
- `financial-analysis/`: **competitive-analysis** · **comps-analysis** · **dcf-model**

Loader (`src/agents/shared/skills.py`, Phase G): tiered registry — Tier 1 builtin
(cannot be overridden) → Tier 2 packaged categories (`resources/skills/{category}/**`) →
Tier 3 custom (`config/skills/`, dir currently empty); alias map + **trigger index**
already exist. The DCF/comps/earnings skills the owner described as the product vision
**already have packaged content and are loaded** — what does not exist yet is selection
policy, explainability ("which skills, why"), profile/persona, and auto-trigger rules.

**Disposition**: keep in place as read-only packaged data (review ruling); the boundary
(src = registry/selector/profile engine · resources/skills = content · profile DB = user
prefs + custom skills) goes to the **Investment Skills + Investor Profile design spec**,
which starts from this Phase G inventory instead of re-designing the loader.

## 5. Owner decisions for B6

1. Review and merge **B7 = `analysis/` → `src/options_math/`** migration branch after
   reviewer full A/B (TDD, zero-residue; rewires the retained scripts and test string
   patch target as well as import sites).
2. Confirm **scripts survivor table stands** (no re-ruling this round)?
3. Confirm **`config/skills/` question moves to the skills design line** (not hygiene)?
