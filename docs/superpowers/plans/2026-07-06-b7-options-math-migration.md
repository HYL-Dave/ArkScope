# B7 — `analysis/` → `src/options_math/` Migration Implementation Plan

> **Status: IMPLEMENTED FOR REVIEW — reviewer full A/B pending before merge.**
> 2026-07-06 review folded in: MF1 the consumer inventory missed two real sites in
> `tests/test_rate_curve.py` (`:251` patch-target string, `:290` second import) — root
> cause was a `head -2` on the per-file site grep, the session's third capped-inventory
> incident; MF2 residue gate widened to catch patch-target strings + docstring mentions;
> SF focused suite re-centered on option/rate/tools. Approved as a slice by the
> 2026-07-06 B6 ruling 1 — a TARGETED exception to the packaging-deferred domain-reorg
> lock: exactly one root-level package moves; nothing else in `src/` re-organizes.
> Implementation branch evidence: T1 RED matched the predicted `ModuleNotFoundError`;
> T2 `tests/test_option_pricing.py tests/test_rate_curve.py` = 94 passed; T3 focused
> gate = same 9 pre-existing `tests/test_tools.py` data/network failures and 113 passed,
> plus the two targeted options-tool tests passed, scripts compiled, and optional
> evidence/compressor suites passed; T4 real residue gate zero. Full A/B did not finish
> in this Codex environment, so reviewer full A/B remains the merge gate.

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
| `tests/test_rate_curve.py:5` | top-level import |
| `tests/test_rate_curve.py:241` | in-function import |
| `tests/test_rate_curve.py:251` | **`patch("analysis.rate_curve._fetch_treasury_curve", …)` — STRING patch target, invisible to import-greps** |
| `tests/test_rate_curve.py:290` | in-function `from analysis.option_pricing import get_risk_free_rate` |

**13 functional sites total.** Docstring mentions to update in the same pass (zero-residue
semantics must be unambiguous): `tests/test_rate_curve.py:1` ("Tests for
analysis.rate_curve …") and `analysis/rate_curve.py:9` (usage example) — plus anything
else the T4 gate surfaces.

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

- [x] **T1 (RED):** rewire the two test files to `src.options_math` — ALL five
  `tests/test_rate_curve.py` sites (`:1` docstring, `:5`, `:241`, **`:251` patch target
  string**, `:290`) + `tests/test_option_pricing.py:22` → run
  `pytest tests/test_option_pricing.py tests/test_rate_curve.py -q` → predicted failure:
  `ModuleNotFoundError: No module named 'src.options_math'` (anything else = STOP).
- [x] **T2 (GREEN):** `git mv` the three files to `src/options_math/`; update the
  `__init__` docstring path mention + `rate_curve.py:9` usage-example docstring; rerun
  the two files → green.
- [x] **T3:** rewire the remaining 8 sites (6 in `options_tools.py`, 2 in
  `scripts/analysis/`). Core gate (SF):
  `pytest tests/test_option_pricing.py tests/test_rate_curve.py tests/test_tools.py -q`
  + `python -m py_compile scripts/analysis/*.py` (no tests cover those two).
  Additive (optional, indirect surfaces): `tests/test_evidence_packet.py`,
  `tests/test_compressor_reducers.py`.
- [x] **T4 (residue gate, single hard sweep — MF2):**
  `rg -n "from analysis|import analysis|analysis\.(option_pricing|rate_curve)|patch\([\"']analysis" src tests scripts --glob "*.py"`
  = **zero** (catches patch-target strings and docstrings, not just imports; the
  `src.analysis`/`analysis_cards` false-positive class is excluded by inspection if it
  appears); `test ! -e analysis` (root dir gone, pycache included).
  Do NOT run `tests/test_agents.py` on the main checkout (live-key hazard) — the A/B
  covers it in virgin env.
- [ ] **T5 (full A/B):** virgin `git archive` both sides, sequential, failure SETS.
  **Acceptance is the crispest form yet: NO tests added or deleted → failure sets
  strictly identical AND passed counts EQUAL.** Any delta = finding. Codex evidence so
  far: scoped virgin A/B over `tests/test_option_pricing.py tests/test_rate_curve.py
  tests/test_tools.py` is identical (`9 failed, 113 passed` on both sides; same 9
  pre-existing `tests/test_tools.py` data/network failures). The full suite hung in this
  environment and is intentionally left for reviewer execution per the review protocol.
- [x] **T6 (branch closeout docs):** B6 doc §1 status flip; map §10 entry; PROJECT docs mention?
  (root README/PROJECT_STRUCTURE do not list `analysis/` — verified, no edits needed);
  memory sync deferred until reviewer full A/B + merge.

## Stop-Loss

- T1's RED differs from the predicted ModuleNotFoundError → STOP.
- Any consumer discovered beyond the 13 inventoried sites → STOP, re-inventory (the
  grep above is the contract).
- Any behavior/test-count change → STOP (this slice is a pure move).
