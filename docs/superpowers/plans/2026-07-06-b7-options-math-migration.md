# B7 — `analysis/` → `src/options_math/` Migration Implementation Plan

> **Status: DRAFT — pending user review.** Approved as a slice by the 2026-07-06 B6
> ruling 1. This is a TARGETED exception to the packaging-deferred domain-reorg lock:
> exactly one root-level package moves; nothing else in `src/` re-organizes.

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (or
> subagent-driven-development). TDD shape for a migration: rewire imports first (RED:
> ModuleNotFoundError), move the package (GREEN), then gates.

**Goal:** the live options-math runtime (`option_pricing.py`, `rate_curve.py`) moves from
the root-level `analysis/` package to `src/options_math/`, zero residue (no shim, root
package gone), all consumers rewired, behavior byte-identical.

**Why `options_math`:** `src/analysis/` already exists (AI-card analysis pipeline —
context_builder/contracts/factory); reusing the name would collide.

**Non-goals:** no logic changes; no scripts survivor-table changes (`scripts/analysis/*`
files STAY where they are — only their import lines change, which is file-internal, not a
table change); no other `src/` reorganization.

## Grounded consumer inventory (uncapped grep, 2026-07-06 — ALL must rewire)

| Site | Form |
|---|---|
| `src/tools/options_tools.py:40` | `from analysis import (…)` (lazy, in-function) |
| `src/tools/options_tools.py:151` | `from analysis import scan_options_for_mispricing` |
| `src/tools/options_tools.py:152` | `from analysis.rate_curve import get_yield_curve, get_rate_for_dte` |
| `src/tools/options_tools.py:187` | `from analysis.option_pricing import calculate_days_to_expiry` |
| `src/tools/options_tools.py:264` | `from analysis import american_greeks` |
| `src/tools/options_tools.py:267` | `from analysis import black_scholes_greeks` |
| `scripts/analysis/compare_bs_vs_american.py:27` | `from analysis import (…)` |
| `scripts/analysis/scan_option_mispricing.py:51` | `from analysis import (…)` |
| `tests/test_option_pricing.py:22` | `from analysis.option_pricing import (…)` |
| `tests/test_rate_curve.py:5` **and `:241`** | top-level AND in-function imports (two sites) |

`analysis/__init__.py` re-exports 30+ names (`__all__` incl. dataclasses + version) — it
moves VERBATIM (only the docstring's module path mention updates); the public surface
`from src.options_math import X` must equal today's `from analysis import X`.

False-positive class (do NOT touch): `src.analysis`/`analysis_cards` route imports.

## Decisions Locked

1. Move via `git mv` (history preserved): `analysis/{__init__,option_pricing,rate_curve}.py`
   → `src/options_math/`. Remove root `analysis/__pycache__`; root dir gone.
2. Zero residue: no `analysis/` shim package; any lingering `from analysis import` is a
   gate failure.
3. `scripts/analysis/*` keep their filenames/location (survivor table untouched); they
   run by path with repo-root `sys.path` — verify their header does `sys.path` setup or
   runs from repo root; rewire imports only.

## Tasks

- [ ] **T1 (RED):** rewire the two test files to `src.options_math` → run
  `pytest tests/test_option_pricing.py tests/test_rate_curve.py -q` → predicted failure:
  `ModuleNotFoundError: No module named 'src.options_math'` (anything else = STOP).
- [ ] **T2 (GREEN):** `git mv` the three files to `src/options_math/`; update the
  `__init__` docstring path mention; rerun the two files → green.
- [ ] **T3:** rewire the remaining 8 sites (6 in `options_tools.py`, 2 in
  `scripts/analysis/`). Gate: `python -m py_compile scripts/analysis/*.py` (they have no
  tests) + `pytest tests/test_tools.py tests/test_evidence_packet.py tests/test_compressor_reducers.py -q`.
- [ ] **T4 (residue gates, all uncapped):**
  `git grep -n "from analysis import\|from analysis\." -- ':!docs'` = zero;
  `test ! -e analysis` (root dir gone); `git grep -rn "import analysis\b" -- src/ tests/ scripts/` = zero.
  Do NOT run `tests/test_agents.py` on the main checkout (live-key hazard) — the A/B
  covers it in virgin env.
- [ ] **T5 (full A/B):** virgin `git archive` both sides, sequential, failure SETS.
  **Acceptance is the crispest form yet: NO tests added or deleted → failure sets
  strictly identical AND passed counts EQUAL.** Any delta = finding.
- [ ] **T6 (closeout):** B6 doc §1 status flip; map §10 entry; PROJECT docs mention?
  (root README/PROJECT_STRUCTURE do not list `analysis/` — verified, no edits needed);
  memory sync.

## Stop-Loss

- T1's RED differs from the predicted ModuleNotFoundError → STOP.
- Any consumer discovered beyond the 10 inventoried sites → STOP, re-inventory (the
  grep above is the contract).
- Any behavior/test-count change → STOP (this slice is a pure move).
