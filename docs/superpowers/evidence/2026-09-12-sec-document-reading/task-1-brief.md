# Task1: Bounded Document Core

Read Task1 and Global Constraints in
docs/superpowers/plans/2026-09-12-sec-document-reading.md, and approved spec section7.
Ledger preflight is progress.md beside this brief. Work only in
/tmp/arkscope-listing-sec-macro-convergence, base98499d65. No subagents.

Implement the exact Task1 write scope and interfaces. Read relevant existing
common/catalog/PublicSourceReader/parser code first. Defaults of live lifecycle
reader must be unchanged: narrow optional extractor callback only. No I/O in new
pure modules. Use apply_patch. No private data/env/token or provider calls, no
dependency changes. Do not touch other tasks/docs. If an interface is ambiguous,
send a concise specific question; ordinary implementation choices are yours.

Tests only via:
/home/hyl/.virtualenvs/llm_app/bin/python -B
.superpowers/sdd/2026-09-12-sec-document-reading/run_checks.py UNIQUE-NAME backend
-q <test paths>. Names create-only. All own scratch under task-1/ or task1-* runs
inside this plan workspace. Runner audit-hook/isolated paths; not OS containment.
First baseline typo named absent schema test (exit4/no tests) is retained, corrected
all sec_research + public_sources baseline884P. Do not alter unrelated expectations.

RED requires failing behavior assertions, not only missing imports. Empty new
interfaces are permitted to reach assertions. Preserve original RED logs. Run
focused tests while iterating and the full relevant sec_research plus public_source
and wire suites once. Execute the three named inverse mutations and restore exact
source hashes; keep raw logs. Capture a bounded synthetic parser memory/cancel
probe, not a whole-App memory claim. Existing helper reuse rather than copied
entire unbounded parser. New document parser constraints can subclass/refine old
owner without altering lifecycle defaults. Avoid XML DTD/entity work, duplicate
TOC guessed sections and quadratic byte-offset work.

Self-review; record report task-1-report.md including exact public result types,
named RED/GREEN, inverse owners/counts and test paths, limitations. Do not stage
or commit until parent grants sole index window. Then commit scoped product/tests
and report concise status/SHA/test summary. Parent supplies independent review.
