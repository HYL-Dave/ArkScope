# Maintenance Census Adjudication

Source checkpoint78157e62, base7401e656. The unchanged scanner's raw
`task6-final-census` run exits2/review_required:4355 candidates,3543 uncertainties,
1167 source files read. Coverage reductions, dependency metadata changes and main
worktree untracked-name drift are all empty. No actual data was read.

## New Candidates

Exactly25:24 locale leaves and the `src.sec_research.__main__` module.

- Each of six maintenance/admission error families has Title/Detail in both
  locales. `researchErrors.ts:108` receives `ResearchT`; that alias is explicitly
  `TFunction<"research">` in `i18n/researchPresentation.ts:12`. The twelve selectors
  at researchErrors.ts:145-176 are real consumers. Research.tsx:36 and
  ResearchRunProgress.tsx:6 import the presenter. Full frontend1830P and focused
  resource inventory14P keep both locales and error behavior covered. These are
  dynamic-namespace scanner candidates, not unused messages to delete.
- `__main__.py` is the intentional `python -m src.sec_research` operator entry.
  Its parser/command behavior has explicit tests in test_sec_research_cli.py.
  It is not expected to have an ordinary runtime importer. The two maintenance
  modules are consumed by this entry and are not new orphan candidates.

## Uncertainty Accounting

The raw comparison has177 new uncertainty IDs. The reconciliation requires
identical non-position metadata; SQL additionally requires unchanged mapped
source lines and equal AST fragments. It classifies103 as positional churn
(23 i18n,80 SQL), leaving74 new or changed obligations:

| Class | Count | Owner / Treatment |
| --- | --- | --- |
| Dynamic translation namespace | 12 | Exact presenter consumers and bilingual behavior above; no blanket whitelist. |
| Test dynamic import | 1 | test_sec_research_maintenance.py:23-26 explicitly checks/imports the maintenance module for the RED owner; not product dynamic discovery. |
| Dynamic SQL | 15 | Reviewed maintenance/schema/export ownership, quoting, exact-name/DROP and fresh-reference tests; retain CENSUS-SQL-001 scanner obligation. |
| SQL prepare failure | 25 | Static prepare failures are uncertainty, not established product failures. CENSUS-SQL-001 owns incomplete union-schema diagnostics; disposable-store tests execute the real schema. Keep each raw uncertainty visible. |
| Unmodeled SQL statement | 21 | Transaction/PRAGMA/administration statements in the current operation modules; tested behavior, not proof the scanner models them. |

The61 SQL entries are retained individually with file/line in
task6-final-census-reconciliation.json. Task5/Task6 reviews and covering1064P
validate the executed operation paths, not the completeness of SQL scanning.
No uncertainty authorizes deleting a table or column. No scanner policy,
existing candidate, dependency or private untracked file was removed to make
this result pass. This is a scoped accounting result, not a claim that the
remaining C12/C15/C20, i18n/CSS or SQL cleanup queues are closed.
