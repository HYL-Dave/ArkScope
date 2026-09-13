# Task8 Offline Workflow Preflight

Companion to task-8-brief.md, prepared without running another test session
during the Task6 publication repair. Do not begin product edits until Task7 is
accepted and the controller dispatches the integration-test portion explicitly.

## Reuse Actual Owners

- `tests/test_sec_research_tool_adapters.py::dispatch/wire` exercise the actual
  four bridge entrypoints and inject ToolService construction only. Use one
  service/capture graph for all three tools in the release workflow, not the
  existing per-tool separate graph fixtures. Remote bytes are generated; no
  credential, provider, CLI or default production path is needed.
- `tests/test_sec_research_trace.py::trace_stores` demonstrates real Research
  event/message persistence and reopening. Derive citation fields from actual
  whole adapter results with the production extraction function, never invent
  hashes or citation records in the workflow. Preserve call IDs and pass the
  actual accumulated events into durable assistant-turn publication.
- `tests/test_sec_research_citations.py` has exact Decimal, UTF-8 passage and
  independent source fixtures. Retained citations pin observations, not current
  latest values. A changed capture or recent schedule must leave these pins
  readable with their original hashes/value/text.
- `tests/test_sec_research_operations.py` already exercises real backup, export,
  restore, closure and reader leases. Reuse those APIs instead of another copy
  mechanism. Bundles include the entire market DB and SEC objects, not a separate
  profile DB; explicitly keep the generated Research profile and carry its saved
  refs to the restored market root. Do not claim all-installation portability.
- `tests/test_sec_research_maintenance.py` supplies query-only reference access,
  actual preview/digest/apply and generated profiles. Referenced evidence must
  never appear as a removal candidate. Keep an unrelated unreferenced object as
  a positive cleanup control; after explicit apply, exact citations still read.

## Verification Ownership

Worker owns only the new release workflow test and any explicitly ruled minimal
product fix with RED/GREEN. A behavior that already works is a positive
integration check, not manufactured RED. Do not rewrite existing test fixtures,
duplicate a broad producer suite or grow the workflow into a second framework.

Controller owns census/adjudication, documentation, full frontend checks, final
frozen single backend run, exact collection/JUnit/skip reconciliation, source
and runner readback, independent full-change review, and evidence packaging.
No task reviewer re-runs a full suite. Freeze includes current Task6 repair,
Task7 schema/source/resources and this workflow; tests must not overlap another
runner, browser fixture or source edit on this worktree.

Task7 already owns schedule controls/browser fixtures. Extend or re-use that
same generated local API/service to include stored citation/config controls,
not the user's live App. Offline browser fixtures are stopped after evidence.
Source-only wider cleanup status is disclosed; unrelated C12/C15/C20 and scanner
queues are not bundled into a release-test patch or claimed complete.

No live stores, provider/model calls, package or runtime install, actual schema
administration, App restart, master merge or push is authorized by this task.

## Current-Surface Ruling

Task6 deliberately exposes operator maintenance through the CLI, not a browser
route or a model tool. Task8's combined browser/workflow sentence must not create
an unplanned HTTP maintenance interface just to exercise a preview. Verify actual
preview/approval/apply functions on the generated workflow stores; browser gates
cover the actual Research/Settings/config/schedule surfaces. Earlier accepted
Research citation screenshots remain provenance evidence, not a substitute for
fresh tests of any changed interface. No new operator UI is requested.

The concrete test work is bounded to the new release workflow owner and minimal
shared fixture use. One adapter is sufficient for the combined round trip; the
existing separate four-channel equivalence owners remain in the full gate. Do
not clone this entire workflow four times or fabricate an initial RED when
already-implemented behavior passes. Any genuine product defect found here must
be reported with its intended failing assertion before expanding source scope.
