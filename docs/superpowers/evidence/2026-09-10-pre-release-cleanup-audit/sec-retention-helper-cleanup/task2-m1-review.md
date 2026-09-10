# Task 2 M1 Re-Review

**M1: FIXED / ADDRESSED. Spec compliance: PASS. Quality: APPROVED.**

- Scope: `5d41f570330e63a5942835f2ae39ca3cf5d9dcc7..58e1929b61905b905fc0e12bdc5daf1ad116b84b`, using the supplied `task2-m1-review.diff`. Only `tests/test_lifecycle_journal_codec.py` changes: 27 additions, no deletions (`task2-m1-review.diff:7`). The worker report was available and read; no report-arrival gap remains.

## M1 Closure

- `tests/test_lifecycle_journal_codec.py:58` adds two parametrized runtime checks rejecting legacy `_json`/`_sha` attributes and `__all__` exports at the retained owner. Reintroduced assignments or forwarding functions can no longer satisfy the ownership checks.
- The original direct-neutral-import assertion remains at `tests/test_lifecycle_journal_codec.py:119`. The added AST assertions reject legacy imported names/import aliases (`:124`, `:126`), synchronous/asynchronous definitions (`:130`, `:132`), and bare-name bindings/calls or attribute references (`:136`, `:139`) across the same nine consumers. An unused neutral import no longer conceals the legacy imports/references identified in M1.
- The fix adds focused negative checks without changing literal codec fixtures, removing tests, introducing a general-purpose linter, or modifying product behavior. The supplied test-only diff and parent's current-product verification preserve the earlier byte/hash/schema/error-ownership conclusions without reopening Task 2.

## New Breakage

**Critical: none. Important: none. Minor: none.** No new correctness or maintainability issue was found in the fix diff. Open findings: none.

## Evidence Checked

Actual artifact directory: `.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/task2-state/m1/artifacts/`, not `task2-state/m1-artifacts/`.

| Saved XML | Independently Observed Outcome |
| --- | --- |
| `baseline-copy.xml` | 41 passed |
| `aliases-before-m1.xml`, `legacy-import-use-before-m1.xml` | 41 passed each; original assertions missed both regressions |
| `aliases-red.xml`, `definitions-red.xml` | 3 failed, 40 passed each; both export checks and retained-owner AST check detect the mutants |
| `legacy-import-use-red.xml`, `legacy-attribute-use-red.xml` | 4 failed, 39 passed each; current-store AST check additionally detects legacy imports or attribute calls |
| `restored-copy.xml`, `final.xml` | 43 passed each |

- Standard-library XML inspection confirmed all nine reports have zero errors/skips and no duplicate names. After accounting for each single-module fixture's classname prefix, all 41 baseline node names remain; the only two additions are the `_json`/`_sha` export cases. Exact named mutation-failure sets match `task2-m1-report.md:41`, `:48`, `:52`, and `:56`.
- Parsed `commands-and-results.json`: all nine actual pytest commands use the specified clean environment, offline runner, interpreter, isolated state/TMPDIR, one codec test module, and distinct pytest roots. Saved console summaries agree with the XML and contain no warning/deprecation lines. The separately recorded initial `undefined` command exited 127 before pytest and correctly has no XML (`task2-m1-report.md:62`).
- **Named evidence risk: a mutant might exercise the wrong source or fail for an unrelated reason.** Compared only retained baseline/mutant copies for old-owner aliases, forwarding definitions, current-store legacy import/calls, and module-attribute calls. Also inspected `task2-state/m1/aliases/tests/conftest.py:6`; it prepends that fixture's source path. XML export-failure traces identify the corresponding mutant owner, and AST failures identify the intended imports/definitions/references, including current-store failures despite retained neutral imports.
- No standalone `.patch` files were found under the M1 fixture tree. Complete retained source copies supply the mutations instead (`task2-m1-report.md:160`); direct read-only comparisons corroborated them. This is an artifact-format difference, not missing mutation evidence.

## Limits

- Historical evidence was inspected, not replayed or authenticated against historical filesystem state. The exact-name AST checks are intentionally scoped to the nine listed modules, not arbitrary dynamic dataflow. This does not leave the reported M1 defect unresolved.
- No broad Task 2 re-review, pytest execution, production/provider/network access, credential or `.env` access, App startup, subagents, or git operations occurred. No current product file was opened for a new review. The only write is this requested report; product, test, index, branch, parent inventory, and existing evidence files were left untouched.
- Out-of-scope observations: none. This approves M1 closure and the fix diff only, not a new whole-branch or production-data sign-off.
