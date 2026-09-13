# Final Census Classification

Baseline ca49b454; final source5235705c. Same scanner, baseline read from Git.
Only main-worktree untracked names were enumerated; contents were not read.

Initial final scan found one new actual dead CSS rule: `.research-evidence-tool-head
.ui-status`. StatusBadge renders `.ui-status-badge`, not `.ui-status`.5235705c
deletes only that ineffective rule. Fresh full frontend1824P, typecheck/build/i18n
and four realAPI/store browser workflows pass after removal. Source inspection
and final screenshots preserve the existing component/style, not a renamed badge.

Final:4330candidates,3469uncertainties,1158readfiles (baseline4330/3463/1148).
Zero new candidates, coverage reductions, dependency metadata changes or untracked
name drift. No scanner weakening. Raw exit2/review_required is retained.

151 new uncertainty IDs:
- 145 position-only matches:93HTTP,30i18n,3CSS,19SQL. Identical non-position
  metadata; SQL also maps unchanged source lines and identical source AST
  fragments. `census-reconciliation.json` retains every pair and algorithm.
- One new HTTP template: api.ts getSecResearchCitation. Scanner's actual route
  table matches GET /sec-research/citation to this helper; drawer, unit tests and
  four actualAPI/store browser flows call it. Not an orphan or deletion candidate.
- Five new SQL statements in references.py: query_only PRAGMA, bounded dynamic
  facts/filings query, object metadata read, receipt source_snapshots read and
  receipt JSON expansion. Three sql_prepare_failed entries arise in the scanner's
  incomplete union schema; actual installed Store/read/closure owners execute all
  these queries. The dynamic table/WHERE fragments are closed local choices;
  operands remain bound parameters. Query-only enforcement has a behavioral owner.
  Retain under CENSUS-SQL-001, not a new DROP list or a claim of scanner completion.

Existing CENSUS-I18N-001, broader CSS and CENSUS-SQL-001 queues remain open.
C12/C15/C20 and actual stored-data/schema disposal remain separate. C21 is
deliberately deferred. This citation batch does not reclassify those obligations.

Controller setup note: the last preview launch first named a nonexistent nested
apps/arkscope-web/node_modules/vite path (module-not-found, no listener). Correct
hoisted node_modules/vite launcher then served numeric loopback8457. PID3800600
was checked against exact own config and terminated after browser exit0; its PTY
session41572 closed. No product/server config changed, no actual App restarted.
