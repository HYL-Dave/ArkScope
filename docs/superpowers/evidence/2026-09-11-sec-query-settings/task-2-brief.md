# Task 2: Financial Facts Stored Query

Worktree: /tmp/arkscope-listing-sec-macro-convergence
Plan: docs/superpowers/plans/2026-09-11-sec-query-settings.md, global constraints
and Task 2. Read the linked approved spec sections 6/8 and task-1-report.md for
helper signatures. Implement Task 2 only, no subagents; RED-first, explicit scoped
commit and write task-2-report.md here. Use apply_patch; no real data/config/token
reads, provider network, installation, merge, push or unrelated cleanup.

Task1 review found a malformed stored receipt JSON-type error; its implementer
is fixing only store.py/read validation + Task1 tests. Current query helpers and
their public contracts remain your authoritative starting point. Your write set
is disjoint. Report ready-to-commit BEFORE index changes; parent coordinates all
commits. Task1 gate and Task2 real integration must both pass before completion.

Write scope: src/sec_research/fact_queries.py, src/sec_research/queries.py thin
entry/helper adjustment, tests/test_sec_research_fact_queries.py. A separate small
fact projection helper is allowed only for a coherent responsibility. Do not
change schema/service/captures or existing financial-cache semantics. Need extra
shared helper change? State why, keep narrow and test catalog regression.

Use original exact TEXT numbers and source references. Reuse reviewed mapping
constants INCOME_STATEMENT_MAPPING/BALANCE_SHEET_MAPPING/CASH_FLOW_MAPPING from
data_sources/sec_edgar_financials.py, not float selection functions. UI-independent
query interfaces in the plan are binding. Treat unit/namespace/start/end as part
of identity; no ratio, Q4 subtraction, TTM or USD default. Alternative concepts
need explicit conflict/missing gaps, not arbitrary first-alternative dominance.

as_of constrains filed_date (daily availability, not report end); same latest date
and period with different values remain conflicting rows, no arbitrary winner.
Quarter/YTD/annual classification cannot assume fp identifies the actual row's
period: Company Facts includes comparative periods and YTD rows in a quarterly
filing. Require supporting original duration/frame context, label unknown when
not defensible, do not hide raw start/end. Document any concrete classification
ruling and tests, including quarterly vs YTD in same filing and year-end frames.
Primary technical documentation checked (not a data API acquisition):
https://www.sec.gov/search-filings/edgar-application-programming-interfaces .
Its frames API describes calendar-aligned CYyyyy / CYyyyyQn / CYyyyyQnI, with
annual duration365+/-30 days and quarter91+/-30. It explicitly warns fiscal
start/end calendars differ. This is a calendar-frame hint, not proof a fact's
`fp` or `fy` identifies the actual comparative period. Any use of that format in
Company Facts classification must remain corroborated by original start/end.

Ordinary queries use the exact bound Company Facts snapshot from Task 1, never
all retained snapshots to repair a failed current source. Other incomplete catalog
sources should not erase a usable facts response, but their relationship must be
clear in coverage. No observations vs observed empty are distinct.

Explicit fact_ids open retained original rows independently of current/latest
receipt success. They reject incompatible selection filters and bind cursors to
ids + actual immutable snapshot identities (a distinct query kind through shared
codec is okay). Future newly retained rows cannot reshuffle a continued page.
Missing ids are typed gaps, not silent omissions. No byte truncation of rows.

Evidence: use this plan's run_checks.py (TZ=Asia/Taipei, isolated env/paths and
offline_pytest.py). Run focused RED before production changes, GREEN all SEC
query suites, inverse float/as_of-end-date/fact-id-latest filtering in own scratch
copies/in-memory loaded functions; verify restored hashes. Log raw outputs and
JUnit in own task-2 subdirectory. Report concrete commands, counts, filenames,
RED cause, inverse named owner failures, scope limitations and commit.
