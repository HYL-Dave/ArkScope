# SDD ledger - plan: docs/superpowers/plans/2026-09-11-sec-structured-source-core.md

Base: 95ad149ea4bda2569030f1dfc95f93bf3c279738.
Isolated worktree verified, clean at start; main unchanged at 30bb31c7.
Existing user approval covers continuation of the architectural SEC spec and
cleanup. No new product-policy decision or external side effect is inferred.

## Preflight

| Tasks | Shared contract / consistency | Ruling |
| --- | --- | --- |
| 1 | Exact repro already archived; standalone absent | Add executable and output, preserve original archive |
| 2 | Test sync branches reference removed entrypoint | Remove only sync-specific nodes, preserve other parametrized owners |
| 3 | Catalog consumes common exact JSON and CIK | Same task owns both; no provider mapping or history completeness inference |
| 4 | Common SourceError/SourceRef/CIK and bytes decoding from 3 | Use exact declared interface, no second JSON decoder |
| 3 / 4 | Both need accession/date checks | Common owns pure validation helpers; additions reviewed with both scopes |
| 5 / all | Full node accounting starts at base | Snapshot before source changes; earlier counts are not this batch's verification |
| 1 / 5 | New evidence directory, distinct files | Task1 owns repro/result/followup only; parent owns final README/accounting |

Ruling: main src/audit is still tracked old code, not disposable cache; only the
implementation branch is clean. Do not delete main tracked files without merge.
Ruling: no model-date change needed. September 8 completion plan lines 91-97
records unknown dates as limitations plus explicit user execution date. Current
_execution_date and adoption remain authoritative and will be exercised unchanged.
Ruling: deliver pure structured-source core this batch rather than bypass capture
quota with an ad-hoc source BLOB store or register incomplete tools. Cost is that
complete SEC service still requires storage/acquisition/integration steps.

## Progress

- Task 1: complete, commit755cba8d; independent task12 reviewer passed both
  spec/quality. Exact memory-only repro repeated by worker, parent and reviewer.
  Six diagnostic tests pass; worker and reviewer closed.
- Task 2: complete, commit41ab878e; RED2F/280P,
  GREEN447P, inverse2F/1P, restored3P.16 retained functions/classes AST-identical.
  Independent reviewer459P, exact5sync-only nodes removed/3added, no lost assertion.
- Task 3: implementation complete, independent spec/quality review PASS.
  124P;2initialRED;3originalmutations killed; presenceflag RED4; four isolated
  follow-up mutants killed (the flag mutant gives1F/3P). Source stable.
  Implementer Nash closed after completed review; committed82512b8b.
- Task 4: behavioral tests written; initial collection attempted before module
  exists yielded53setup errors and is not accepted RED evidence. Explicit
  runtime-owner assertion then failed as expected before implementation.
  Implementation now GREEN54P; float inverse4F, overwrite inverse2F, restored54P.
  Report task-4-report.md; independent spec/quality review PASS; committeddd93bcf8.
  Parent precommit parser run178P0.75s; no source changes during full execution.
- Task 5: in progress
  Combined existing/new SEC scope332P6.02s. Collection8304nodes5.30s. Census
  completed1100read4311candidates3352uncertainties; rawcompareexit2, only new
  catalog/facts test-only modules; newuncertainty/reduction/dependency/untracked0.
  Final task3/task4/integration reviewer Leibniz passed all scopes; independently
  executed181focused+54synthetic tests. Report parsers-final-review.md; reviewer
  closed. Frozen783source/test paths and patch5b17c541... match review exactly.
  Parent fullbackend finished8292P/12S1108.57s, exit0; session7822 closed.
  Reconciliation PASS:8304unique collected/executed; removed5added181; all783
  source/test hashes and exact review patch stable,12skip identities unchanged.
  Six standalone SQLite diagnostics freshly passed. Final staged-doc census
  repeats identical read-source manifest and comparison, exit2/review_required.
  Data artifacts remain fixture-only. Final archival/docs commit next.

Baseline collected8128nodes, no collection errors,4.95s. No actual DB access.
Harness note: first Task2 GREEN invocation named nonexistent test_streaming.py;
exit4, no acceptance. Corrected selection uses test_agent_history.py and actual
replay/subagent files;447P result above is the corrected real run.
Skill helpers were not executable: invoked sdd-workspace with bash; task-brief
internally executes that helper and also failed. Used read-only awk extraction
from the committed plan instead; did not change installed plugin permissions.
Ruling: tool's model override restriction outranks skill tier preference;
delegated agents inherit the parent model with explicit high reasoning.
Ruling: add CatalogSnapshot.historical_files_observed. The original tuple-only
interface collapsed absent files into explicitly observed zero historical files;
a future traversal could silently infer completion. Preserve this presence bit
now without adding traversal, a tool envelope or speculative provider calls.
Task3 worker owns the named RED and implementation. Facts uses common.source_ref
once per snapshot, so the shared helper has an actual source consumer.
Task1/2 independent report: task12-review.md. Review correctly treats worker
followup's earlier parent-supplied result as a dated snapshot; final README will
point to actual archived XML and completed restored results.
