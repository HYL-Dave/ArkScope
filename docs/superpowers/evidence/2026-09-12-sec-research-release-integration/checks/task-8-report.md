# Task8 Test-Only Release Workflow Report

## Handoff

- Status: DONE. No unresolved product defect or blocker found.
- Workspace: `/tmp/arkscope-research-output-boundary`.
- Base: `883b0185b1b044ff6a94a7690cb85253fc7c82e5`.
- Commit: `a77a7c2e7cb1bb1b8d2b92cd4cfb129f299f6687`.
- Committed file: `tests/test_sec_research_release_workflow.py` only, 281 added lines.
- Test-file SHA-256, identical in the final tested worktree and committed blob:
  `794bdb064c169a541c27e4b2464680749e83c030cdd20fa589abbaa03b80e678`.
- Final focused verification: 9 passed, 0 failures, 0 errors, 0 skipped.
- No active runner at handoff. Every launched check process was awaited to exit.
- This report and the five receipt directories remain in ignored plan scratch for
  controller publication. No controller docs/evidence were staged or committed.

Read `task-8-brief.md` first, then `task8-preflight.md`. Did not read the whole
parent plan or sibling task scratch. Tasks1-7 were treated as accepted.

## Implemented Coverage

### Catalog, Facts, Document, Reload, Export And Restore

`test_research_catalog_fact_document_reload_export_restore` uses one generated
market Store/CaptureStore/ToolService graph and the actual Anthropic tool dispatch
helper for all three SEC tools. The fixture supplies generated ticker mapping,
submissions, Company Facts, directory JSON and HTML bytes. It reuses existing
response/connection/metadata transport helpers without modifying them. Document
acquisition uses the real PublicSourceReader and SecSourcePolicy/governor.

The adapter returns two catalog references, one fact reference and one passage
reference. Citation fields come only from production `citation_event_fields`
applied to whole adapter outputs, never constructed citation records. The harness
assembles local tool-start/end envelopes with four distinct call IDs, appends the
same eight events through ResearchRunStore, reopens them, and passes the actual
reloaded event list to `_persist_assistant_turn`. ResearchThreadStore and the
Research messages route then reopen the durable assistant message. The fixture
checks complete persisted calls, including IDs, inputs, previews and citations.

Assertions cover:

- Exact adapter and reopened decimal string `1234567890123456789.123`.
- Exact UTF-8 text `A\u4e2d\u6587 needle \U0001f642 retained observation`, its
  independently computed SHA-256 and byte-range length, and original HTML bytes.
- CIK resolution from the generated AAPL mapping.
- A later real refresh to `777.123` and a different document capture, with saved
  citations still reopening the original value/text/hash/capture ID.
- Actual `export_bundle`, including its SQLite backup path, and `restore_bundle`
  to a new root with database basename `relocated.db`.
- All saved catalog/fact/document references reopening identically at that root.
- Retention of an unrelated generated market table row and the issuer mapping.
- The separate generated Research profile is retained, not included in the
  market bundle. Its bytes and the source capture object bytes remain unchanged.

### Interrupted Refresh, Stored Reads And Cleanup

`test_interrupted_refresh_keeps_stored_references_out_of_cleanup` starts with the
same durable adapter-derived citations. It injects `OSError(ENOSPC)` only at the
real `os.link` publication boundary for a new Company Facts body containing
`999.456`. This is a filesystem-interrupted refresh, not a simulated app restart
or process-kill test.

Assertions cover:

- Refresh returns unavailable/empty rather than borrowing the old fact result.
- The real receipt retains completed submissions, pending companyfacts and
  `storage_space_insufficient`, with no prior companyfacts snapshot binding.
- Interrupted staged bytes remain charged; the new object was not published.
- Saved exact references reopen before recovery, while an unpinned stored fact
  request remains unavailable and makes no new metadata request.
- Actual CaptureStore recovery clears the reservation and charges the staged
  orphan without removing it.
- Actual maintenance preview uses an explicit read-only/query-only connection
  to the generated Research profile and verifies retained reference closure.
- Candidates are exactly the interrupted staged object plus a separate,
  registered but unreferenced positive cleanup control. No pinned source,
  original-document or text hash is a candidate.
- Preview leaves the candidate bytes intact. Explicit approval-digest apply
  removes only those candidates, writes a matching receipt, and frees exactly
  their combined byte count. All saved citations still reopen identically.

## Actual Test Commands And Results

All commands ran sequentially from `/tmp/arkscope-research-output-boundary` using
the existing unchanged `run_checks.py` in `backend` mode and its unchanged
`offline_pytest.py` launcher. No alternate runtime, package install, collection
gate or full backend invocation was used. Each receipt directory below contains
the exact expanded command/environment in `command.json`, `output.log` and
`results.xml`; all failing attempts remain intact.

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py task8-workflow-baseline-01 backend -q 'tests/test_sec_research_tool_adapters.py::test_each_research_transport_dispatches_three_real_sec_tools[anthropic]' tests/test_sec_research_trace.py::test_sec_citations_roundtrip_event_message_and_legacy_rows tests/test_sec_research_operations.py::test_export_restore_preserves_wal_and_historical_citations tests/test_sec_research_maintenance.py::test_cleanup_preserves_every_retained_reference_class

/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py task8-workflow-integration-01 backend -q tests/test_sec_research_release_workflow.py

/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py task8-workflow-integration-02 backend -q tests/test_sec_research_release_workflow.py

/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py task8-workflow-integration-03 backend -q tests/test_sec_research_release_workflow.py

/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py task8-workflow-focused-final-01 backend -q tests/test_sec_research_release_workflow.py 'tests/test_sec_research_tool_adapters.py::test_each_research_transport_dispatches_three_real_sec_tools[anthropic]' tests/test_sec_research_trace.py::test_sec_citations_roundtrip_event_message_and_legacy_rows tests/test_sec_research_operations.py::test_export_restore_preserves_wal_and_historical_citations tests/test_sec_research_maintenance.py::test_cleanup_preserves_every_retained_reference_class tests/test_sec_research_tool_service.py::test_stored_and_pinned_calls_never_open_acquisition tests/test_sec_research_tool_service.py::test_document_refresh_failure_blocks_old_capture_but_pin_reopens tests/test_sec_research_document_queries.py::test_unknown_form_keeps_whole_text_and_section_gap
```

| Receipt ID | Exit | JUnit Cases | Passed | Failures | Errors | Skips | Runner Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| task8-workflow-baseline-01 | 0 | 4 | 4 | 0 | 0 | 0 | 4.784 |
| task8-workflow-integration-01 | 1 | 2 | 0 | 0 | 2 | 0 | 4.327 |
| task8-workflow-integration-02 | 1 | 2 | 0 | 0 | 2 | 0 | 4.367 |
| task8-workflow-integration-03 | 0 | 2 | 2 | 0 | 0 | 0 | 5.370 |
| task8-workflow-focused-final-01 | 0 | 9 | 9 | 0 | 0 | 0 | 7.796 |

The final runner printed `9 passed in 6.98s`. Local accounting parsed only these
five receipt XMLs with Python's ElementTree and their command JSON with the JSON
parser. There were 19 testcase attempts across 9 unique nodes: 15 passed and 4
fixture setup errors, with no testcase-body failures or skips. This is focused
worker accounting, not the controller's whole-suite reconciliation.

Two new test nodes were added. No existing test was changed, removed, disabled or
parametrically reduced. The final nine nodes are the two new names above plus:

- `tests/test_sec_research_tool_adapters.py::test_each_research_transport_dispatches_three_real_sec_tools[anthropic]`
- `tests/test_sec_research_trace.py::test_sec_citations_roundtrip_event_message_and_legacy_rows`
- `tests/test_sec_research_operations.py::test_export_restore_preserves_wal_and_historical_citations`
- `tests/test_sec_research_maintenance.py::test_cleanup_preserves_every_retained_reference_class`
- `tests/test_sec_research_tool_service.py::test_stored_and_pinned_calls_never_open_acquisition`
- `tests/test_sec_research_tool_service.py::test_document_refresh_failure_blocks_old_capture_but_pin_reopens`
- `tests/test_sec_research_document_queries.py::test_unknown_form_keeps_whole_text_and_section_gap`

## Failed Attempts And RED Classification

`task8-workflow-integration-01` failed in fixture setup at the index call:

```python
assert page["status"] == "ok", page
# Actual: partial; gaps = [{"code": "section_index_unavailable", "section_id": None}]
```

The paragraph-only HTML intentionally has no recognizable section heading. The
index result correctly reports the section gap and still exposes a text cursor.
This was a fixture expectation mistake, not a product defect or behavioral RED.

`task8-workflow-integration-02` failed later in fixture setup at the text cursor:

```python
assert page["status"] == ("partial" if name == "read_sec_filing" else "ok"), page
# Actual text cursor page: ok; gaps = []; complete original UTF-8 passage present.
```

The first correction incorrectly generalized the index gap to text pages.
Inspection of `DocumentQueries._page` confirmed that section gaps belong only to
index mode. The final fixture asserts exact `partial`/section-gap for the index
call and exact `ok`/no-gap for the text call; it does not accept arbitrary statuses
or suppress errors. Both failed receipt directories are retained. No runner or
production code was changed to address these fixture mistakes.

`task8-workflow-integration-03` then passed both workflows. Self-review added
strict equality between the raw adapter value/text and independently reopened
value/text; `task8-workflow-focused-final-01` verified that final version.

Classification: positive integration checks of accepted existing behavior. No
fabricated RED, no product fix, no source mutation inverse and no claimed killed
behavioral inverse. Any shared-source inverse remains subject to coordination.

## Self-Review And Scoped Commit

Reviewed the complete owned test file against the brief/preflight and the actual
interfaces. Expected failure boundaries include lost/misbound persisted calls,
adapter value/text corruption, retargeting old citations to latest observations,
missing restored evidence, stale-success borrowing after interruption, and
cleanup selecting or damaging referenced bytes. Literal exact decimal/text and
raw-body/hash checks prevent an empty or merely self-consistent round trip from
passing. Citation counts and exact candidate sets prevent vacuous checks.

No source, authorization, lifecycle, model-routing or schedule behavior changed.
No new framework, producer-loop clone, maintenance HTTP/UI or four-channel copy
was added. No independent reviewer was launched because subagents and final
whole-change review belong to the controller.

Verification/commit commands and observed results:

```text
git diff --cached --name-only
  Empty before staging.
git add -- tests/test_sec_research_release_workflow.py
git diff --cached --check -- tests/test_sec_research_release_workflow.py
  Exit 0, no whitespace errors.
git diff --cached --stat
  One file, 281 insertions.
git commit --only -m 'test(sec-research): verify offline release workflows' -- tests/test_sec_research_release_workflow.py
  Exit 0, a77a7c2e7cb1bb1b8d2b92cd4cfb129f299f6687.
git diff-tree --no-commit-id --name-only -r HEAD
  tests/test_sec_research_release_workflow.py
git cat-file blob HEAD:tests/test_sec_research_release_workflow.py | sha256sum
  794bdb064c169a541c27e4b2464680749e83c030cdd20fa589abbaa03b80e678
```

`sha256sum` before and after focused checks confirmed unchanged runner bytes:

- `run_checks.py`: `2c1cc48b15f817b02cc70a99cad757a0962e875e37381fa122fca8b89796247f`
- `offline_pytest.py`: `4c74153e1ef86c35f7bbc923586de624c0ffe3f577c2853e6e4c0a78426c95ff`

The final `git status --short` retained only the controller's pre-existing three
modified docs and two untracked evidence directories. The report is ignored by
`.superpowers/sdd/.gitignore:1:*` and was not force-added. Read-only exploration
also found no AGENTS files at the probed ancestors, and one attempted search
named nonexistent `tests/test_sec_research_sections.py`; neither was a test run
or a product RED.

The final active-runner probe was:

```bash
pgrep -af '[/](run_checks|offline_pytest|sqlite_pytest|browser_check|browser_fixture)[.]py|[p]ytest tests/'
```

It returned no matches (exit 1). No background runner, server, browser fixture or
worker process is handed off.

## Rulings, Scope And Limitations

- Ruling: one actual Anthropic adapter is sufficient for the combined workflow.
  Existing four-channel equivalence owners remain for the controller gate.
- Ruling: maintenance uses the actual preview/approval/apply functions on
  generated stores. No HTTP endpoint, browser operator UI or provider CLI was
  introduced or invoked.
- Ruling: the bundle contains the market DB and SEC capture objects, not the
  Research profile. Keeping that generated profile and applying its saved refs
  to the restored market root is verified; all-installation portability is not.
- Ruling: Task7 owns default-disabled scheduling. No duplicate schedule test or
  behavior change was added here.
- Ruling: accepted working behavior is positive integration evidence. The two
  setup mistakes above are disclosed separately, not marketed as product RED.
- The test harness supplies remote bytes/DNS/connection responses, fixture time,
  disposable paths/capture budget and the one filesystem failure. Service
  construction is wired to the single local graph. Local event envelopes replace
  live model transport; production extraction and persistence remain real.
- No production DB, default production store, config/.env, token or credential
  was read. No real provider/model call, external network, package/runtime
  install, actual-store operation, app restart, master merge or push occurred.
- This work does not claim live SEC/model correctness, full producer streaming,
  browser correctness, all-channel equivalence, actual-store rollout or
  old-schema disposition. A live canary remains unauthorized.
- Controller retains docs, census/adjudication, browser/frontend gates, exact
  final collection and skip reconciliation, the single frozen full backend run,
  source/runner final readback, whole-change review and evidence packaging.
  None of those controller gates was executed here.
- Wider C09/C11/C12, C12/C15/C20 and scanner queues remain independently owned;
  no wider cleanup or repository-clean claim is made.

The worktree and all five task8-workflow receipt directories are retained for
the controller's independent review and final gate. No active runner handoff.
