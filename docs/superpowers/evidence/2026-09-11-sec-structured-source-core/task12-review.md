# Independent Review: Tasks 1 And 2

Reviewed 2026-09-11 in `/tmp/arkscope-listing-sec-macro-convergence`.
Baseline: `95ad149ea4bda2569030f1dfc95f93bf3c279738`.

## Findings And Verdict

No actionable implementation defects, lost live test properties, or blocking
spec-compliance findings identified. Task 1 and Task 2 are approved on both
spec compliance and code quality, within the scope and limitations below.

Evidence reconciliation, informational rather than an implementation finding:
`docs/superpowers/evidence/2026-09-11-sec-structured-source-core/review-followups.md:106`
and `.superpowers/sdd/2026-09-11-sec-structured-source-core/task-1-report.md:63`
explicitly preserve an earlier parent-supplied snapshot. Their
`scratch/task2-green.xml` locator is not the actual artifact path supplied for
this review, and restoration is no longer pending. The verified artifacts are
`.superpowers/sdd/2026-09-11-sec-structured-source-core/task2-{red,green,inverse,restored}.xml`.
The completed record is **2 RED failures / 280 passes; 447 GREEN passes;
2 inverse failures / 1 pass; 3 restored passes**. This review records that later
evidence without rewriting the implementer's historical snapshot or sealed files.

## Task 1: Spec Compliance

- Read the Task 1 brief/report and all three new evidence files. Compared the
  executable to the sealed `current-journal-cleanup/sqlite-research.md:198`
  five-case matrix and its upstream reproducer.
- Independently parsed the archived case literals with standard-library AST:
  all five tuples match exactly. All five emitted SQL strings match the
  archived DDL/DML modulo whitespace and a final statement terminator. The
  upstream `REPLACE`, schema-policy `INSERT`, and `INSERT OR REPLACE` cases
  retain both conflict clauses. The latter still omits schema-level REPLACE.
  Both single-clause controls retain their original spelling and schema policy.
- `sqlite_upsert_repro.py:86` opens a fresh `:memory:` connection for each
  case, closes it with `closing`, and sets temporary storage to memory. There
  is no database-path interface, repair, application import, or installation.
- Measurements retain engine version/source ID, memory journal mode, both
  archived count queries, actual table rows, full integrity-check output, and
  quick-check output. `NOT INDEXED` adds a direct row check without changing SQL.
- A fresh clean-interpreter execution returned **exit 1 / defect_reproduced**.
  All three duplicate-clause cases reported table/index counts **2/3**, full
  integrity error `wrong # of entries in index sqlite_autoindex_v0_1`, and quick
  check `ok`. Both controls reported **2/2**, with both checks `ok`. Every
  journal was `memory`. Fresh stdout byte-matched `sqlite-upsert-result.json`,
  with empty stderr. Exit 1 is the intended defect observation, not a test failure.
- Observed engine: SQLite 3.37.2; source ID
  `2022-01-06 13:25:41 872ba256cbf61d9290b571c0e6d82a20c224ca3ad82971edc46b29818d5dalt1`.
- `git ls-tree` independently confirmed the four old `src/audit` files remain
  tracked both at `30bb31c7` and current `refs/heads/master`. This worktree's
  `src/audit` is absent, as desired. Main was not treated as disposable.
- The September 8 completion plan already records limitations versus blocking
  unresolved conditions and an explicit attended execution date. The named
  findings/review/routes owners passed in the independent offline run below;
  their expectations and the transition/security-review files are unchanged
  against baseline.
- Sealed research SHA-256 remains
  `170fd68b2dfe84b8fde89dd76fb763c2810c0ee465b218f50e25b058a03f109c`;
  its baseline diff is empty.

## Task 1: Code Quality

`sqlite_upsert_repro.py:26` and `:45` classify observed behavior rather than
version numbers. Missing measurements, unexpected signatures, probe errors,
wrong case accounting, or failed controls produce exit 2 before any defect
claim. Healthy cases produce exit 0; valid controls plus an exact defect
signature produce exit 1. Import/SQL failures remain structured evidence.
Argument and isolation-flag rejection happen before probe execution.

The code is small, standard-library-only, and preserves full returned check
messages. No unnecessary abstraction or application coupling was introduced.
The report's six diagnostic regression tests were inspected and independently
rerun: **6 passed**, including audited memory-only connection targets, invalid
SQL, version-independent classification, missing observations, failed-control
precedence, and CLI status/argument handling.

## Task 2: Spec Compliance And Code Quality

- Read only Task 2 of the implementation plan, the supplied review diff,
  new absence tests, and Task 2 result artifacts. The current four-file tracked
  diff byte-matches `task2-review.diff` against the specified baseline.
- Independently recomputed `task2-ast.json`: **16 retained functions/classes
  identical; removed only `run_query_sync`; changed none; added none**.
  A stronger whole-module AST comparison also passes after removing only that
  baseline function and substituting the updated module docstring. Imports,
  module statements, async/streaming functions, helpers, and classes otherwise
  remain identical.
- `src/agents/openai_agent/__init__.py:12` removes only the sync import/export;
  it adds no alias or compatibility wrapper. Anthropic's agent package has no
  baseline diff. No Task 2 transport or API-route change is present.
- New owners at `tests/test_openai_sync_surface_cleanup.py:11`, `:22`, and
  `:29` check absence of the implementation/export and retained async,
  streaming, and Anthropic synchronous entrypoint shapes. Archived RED and
  inverse XML both fail exactly the two absence owners, with no collection
  errors. The positive owner passes; all three pass after restoration.
- Runtime-binding changes at `tests/test_task_runtime_binding.py:775`,
  `:1015`, and `:1126` remove only OpenAI sync parameters and their unreachable
  branches/patch. Retained branches continue to exercise real async/stream
  calls, Anthropic sync, child calls, and cross-provider child calls.
- Independent AST accounting found all **136 runtime-binding assertions** and
  all **86 legacy-surface assertions** unchanged. Manual branch inspection
  confirms the same retained assertion reachability: exact request count and
  authorization, captured credentials, redaction/length bounds, exception
  context suppression, two-attempt retry policy, parent-context restoration,
  sensitive trace exclusion, trace metadata, success output, and token usage.
  The legacy signature guard removes only the obsolete OpenAI sync name.
- Baseline node accounting within the GREEN selection is **449 - 5 + 3 = 447**.
  No other pre-existing selected node disappears. No test is skipped or marked
  expected-failure to obtain GREEN.

### Exact Removed Nodes

```text
tests/test_task_runtime_binding.py::test_enabled_sdk_tracing_excludes_sensitive_data_preserves_metadata[key_echo-sync]
tests/test_task_runtime_binding.py::test_enabled_sdk_tracing_excludes_sensitive_data_preserves_metadata[success-sync]
tests/test_task_runtime_binding.py::test_native_key_echo_is_redacted_before_logs_scratchpad_and_public_errors[False-openai_sync]
tests/test_task_runtime_binding.py::test_native_key_echo_is_redacted_before_logs_scratchpad_and_public_errors[True-openai_sync]
tests/test_task_runtime_binding.py::test_openai_retry_key_echo_is_private_without_changing_retry_policy[sync]
```

### Exact Added Nodes

```text
tests/test_openai_sync_surface_cleanup.py::test_openai_sync_implementation_is_removed
tests/test_openai_sync_surface_cleanup.py::test_openai_sync_entrypoint_is_not_exported
tests/test_openai_sync_surface_cleanup.py::test_retained_research_entrypoints_are_available
```

## Independent Executions

All commands ran from the reviewed worktree with `login=false`.

SQLite diagnostic (captured and compared in memory with the archived JSON):

```bash
env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B /tmp/arkscope-listing-sec-macro-convergence/docs/superpowers/evidence/2026-09-11-sec-structured-source-core/sqlite_upsert_repro.py
```

Inspected diagnostic regression block:

```bash
env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B -c 'from pathlib import Path; p=Path(".superpowers/sdd/2026-09-11-sec-structured-source-core/task-1-report.md"); source=p.read_text().split("```python\n",1)[1].split("\n```",1)[0]; exec(compile(source,str(p),"exec"))'
```

Focused application tests through the existing offline runner, with a unique
WORK directory and clean environment:

```bash
env -i PATH=/usr/bin:/bin PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-sec-structured-source-core/task12-review-20260911-independent /home/hyl/.virtualenvs/llm_app/bin/python -I -B .superpowers/sdd/2026-09-11-sec-structured-source-core/offline_pytest.py -q tests/test_openai_sync_surface_cleanup.py tests/test_task_runtime_binding.py tests/test_legacy_agent_surface_retirement.py tests/test_ticker_identity_transition.py tests/test_lifecycle_investigation_review.py tests/test_security_lifecycle_review.py tests/test_agents.py tests/test_agent_history.py tests/test_replay.py tests/test_replay_openai.py tests/test_subagent.py tests/test_lifecycle_investigation_findings.py::test_unknown_exact_date_is_a_visible_limitation_not_a_material_conflict tests/test_lifecycle_investigation_routes.py::test_current_confirmation_rejects_unknown_fields_dates_and_coerced_acknowledgements --junitxml=.superpowers/sdd/2026-09-11-sec-structured-source-core/task12-review-20260911-independent/focused.xml
```

Result: **459 passed in 37.32 seconds, exit 0; zero errors/failures/skips**.
Parsed fresh XML confirms all original 447 GREEN node IDs are present. The
12 additional nodes are the unknown-exact-date findings owner and 11 invalid
confirmation/date variants. The attended-date review owner was already in the
447 selection. Scoped `git diff --check` also passed.

## Boundaries

No subagents, commits, provider/network calls, production store/config/token
reads, or application imports outside the existing isolated runner. Only this
review was manually written; the authorized runner generated disposable test
fixtures and XML under its unique WORK directory. No source/test mutation was
performed for an inverse rerun: inverse evidence was independently inspected,
while current GREEN and diagnostic behavior were freshly executed.

No whole-suite run or review of concurrent SEC pure-parser work was performed.
This approval does not assess the running App's SQLite interpreter, user-data
integrity, WAL behavior, future SEC ingestion, or merge readiness of other tasks.
