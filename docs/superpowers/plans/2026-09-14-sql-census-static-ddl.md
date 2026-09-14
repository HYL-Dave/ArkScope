# SQL Census Static DDL Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task-by-task.

**Goal:** Close CENSUS-SQL-001's missing JOIN-reader observation without
executing application modules, guessing SQL holes, or authorizing data deletion.

**Architecture:** Resolve a bounded Python AST subset for SQL strings: immutable
string constants and the existing pure quoted-enum join idiom. Verify the helper
body and bindings, not its name. Feed the exact resulting SQL to the existing
disposable SQLite parser and union schema. Unresolved expressions remain gaps.

**Tech Stack:** Python ast, in-memory SQLite, pytest.

**Spec:** Cleanup audit CENSUS-SQL-001. Production schemas/stores are unchanged.

## Task 1: Exact Static SQL Expressions

Modify `tests/repository_inventory.py` and `tests/test_repository_inventory.py`.

- [x] Add a failing fixture with a quoted-enum f-string table and a literal
  `SELECT t.* ... JOIN ...` reader. Expect the reader to observe every translation
  column. Add the actual source pair as a regression owner (read source only).
- [x] Recognize only undecorated, single-return `", ".join(f"'{value}'" for value
  in sorted(values))` helpers, literal immutable string enums, unshadowed names,
  and f-strings without conversion/format specs. Do not call/eval/import source.
  Resolve only eagerly evaluated module assignments using the immutable values
  available at that assignment, not later schema-version rebindings. Unknown
  calls, mutable values, local/class/lazy scopes, prior unknown rebindings,
  conditional function redefinitions, and decorated/side-effecting helpers
  remain dynamic SQL. This is bounded static syntax analysis, not a claim of
  complete Python execution/data-flow modeling.
- [x] Invalidate match-pattern and exception-handler bindings, not just
  `ast.Name` stores. Reject assignments containing `NamedExpr` rather than
  assuming their entry snapshot is still valid after an earlier sibling.
  Reviewer-provided negative controls must fail before the fix, then pass.
- [x] Test these negative controls with the positive JOIN case. Verify the
  quoted helper reproduces exact SQL, not a NULL/placeholder approximation.
- [x] Run all scanner tests; re-run census with explicit scanner-version drift
  attribution. Confirm the retained translation reader is observed, its columns
  leave the false-positive queue, and every row still has
  `deletion_authorized=False`. Other unresolved SQL remains visible.
- [x] Record test evidence, limits and candidate delta; commit separately from
  product-schema disposal and SQLite runtime deployment.

Completed at `eed65fb8`; both review findings have RED/green owners. Exact
scanner-vs-source attribution and remaining uncertainties:
`docs/superpowers/evidence/2026-09-14-runtime-cleanup-closeout/README.md`.
