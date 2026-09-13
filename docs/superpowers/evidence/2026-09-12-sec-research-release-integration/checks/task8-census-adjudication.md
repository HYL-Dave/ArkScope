# Task8 Census Preflight Adjudication

Checkpoint source:883b0185. Final workflow source will be scanned again; this is
not that final receipt. Same scanner code is used for document sourcec997a6c9
and current source. Historical/private evidence and all SDD workspaces are
excluded from source reads. Main-worktree untracked names only are enumerated.

Baseline4346 candidates/3460 uncertainties/1126 read files; current4400/3579/1171.
Comparison:70 new candidates,671 new uncertainty IDs,5 coverage reductions,
zero dependency metadata or untracked-name drift. Raw exit2/review_required is
preserved. No scanner candidate or uncertainty is automatic deletion authority.

## Candidate Ownership

-68 locale leaves:24 Research protection/error title/detail leaves and44 SEC
  schedule leaves. Actual consumers are researchErrors.ts:145-176,
  SecResearchPanel.tsx:123-154 and settingsBackendCopy.ts:329-330. Their translator
  parameters obscure static namespace binding; Research/Settings tests and
  browser rendering exercise those bindings. Keep both locale definitions.
-`python:src.sec_research.__main__`: intentional operator CLI; tested through
  actual cleanup/export/schema commands. Task6 owns it; no forwarding alias.
-`python:src.sec_research.scheduled`: actual SourceDef adapter at
  src/service/data_scheduler.py:134, imported through the existing generic
  scheduler adapter. Task7's actual adapter tests own it. String reference does
  not mean disconnected code.

## Uncertainty Ownership

The source-aware reconciliation maps541 unchanged positional records:
CSS48/i18n264/HTTP97/Python2/settings7/SQL123. SQL relocation additionally requires
unchanged source lines and identical AST fragments, not merely a matching label.
The remaining130 records are retained as follows:

-40 i18n: typed translator passage into the Research error mapper and SEC status
  helper, plus the exact resource inventory test. Keep runtime tests; do not
  suppress escaped-namespace uncertainty or delete consumed leaves.
-1 HTTP: api.ts:1339 builds the citation query URL. The matching actual route is
  sec_research.py:91. Citation API/trace/drawer tests own its schema and usage.
-9 Python: dynamic imports in five test modules (output lifetimes/channels,
  issuer/schedule/maintenance fixtures). They deliberately bind real modules
  after disposable configuration setup; the fixtures own them.
-80 SQL:18 dynamic,39 prepare-failed,23 unmodeled. Owners are the current SEC
  operations/maintenance/reference/schema/schedule/store tests and the common
  query/compressor boundary. Static union-schema/statement modeling remains
  CENSUS-SQL-001; these are not80 proven query failures, nor a claim of complete
  scanner coverage. Exact records/locations remain in the reconciliation JSON.

## Reductions And Remaining Work

The five coverage reductions are the already-reviewed C09/C10 physical removals:
alpha_vantage_source.py, eodhd_source.py, finnhub_source.py, source_factory.py and
tools/backends/file_backend.py. Current provider fetch/config, price DAL and SEC
tool owners remain in the release gate. No new removed source is introduced by
this checkpoint. Net candidates+54 reflects70 additions and16 prior removals;
these are occurrence counts, not test totals or a cleanliness score.

C12 collector CLI/writer convergence, C15 obsolete migration tooling, C20
agent_queries disposition, CENSUS-I18N-001 and CENSUS-SQL-001 remain open under
their existing audit/priority-map owners. C21 remains deliberately deferred.
Actual stored rows/schema/settings were neither inventoried nor removed here.

## Final Workflow Source Checkpoint

Re-run at a77a7c2e reads1172 source files, including the new two-test workflow
owner. Counts remain4400 candidates/3579 uncertainties, compared with4346/3460
at the sealed document source. The same70 candidates/671 uncertainty IDs and
five reductions are retained;541 positional records and130 substantive/unresolved
records retain the ownership above. Dependency metadata and main-worktree
untracked-name drift remain zero. Exit2/review_required is intentionally kept.
Raw final receipts and exact reconciliation are task8-final-census and
task8-final-census-reconciliation.json. This is current-source adjudication,
not a claim that the broader cleanup queues or SQL scanner modeling are finished.

## Reviewed Fix Source Checkpoint

Re-run at911d69a2 reads1174 source files, adding the two delegated regression
owners. The entire comparison object is identical to the a77a7c2e checkpoint:
70 new candidates,671 uncertainty IDs,five reviewed reductions,no dependency
metadata or main-worktree untracked-name drift. Both541 positional mappings and
130 substantive/unresolved records retain their existing owners. Current counts
remain4400/3579 and exit2/review_required. Exact current receipts are
task8-reviewed-census and task8-reviewed-census-reconciliation.json.

This equality was checked structurally with jq over both reconciliation JSON
objects, not inferred from equal totals alone. No source deletion or scanner
suppression followed from this comparison.
