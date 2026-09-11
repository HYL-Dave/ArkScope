# Task3 Execution Notes

Requirements are the official extracted task-3-requirements.md and Global
Constraints in the approved document-reading plan. Use reviewed Task2 types in
task-2-report.md; preserve six current endpoints. Base will be set on dispatch.
Work only linked worktree, no subagents, no index until permission, offline tests
only via run_checks.py unique task3-* names. Apply_patch for code/test edits.

Scope: src/api/routes/sec_research.py, new document-route tests, actual API inventory
collateral in test_api.py/test_security_lifecycle_routes.py. Validate filing ID,
document choice, capture/section/query/cursor/max_chars before touching absent or
malformed stores; closed422 codes for invalid operands, unavailable for valid
unobserved/missing/corrupt data. Budget setting corruption must not stop stored
reads of already captured text: no request/write path on GET, and CaptureStore.read
does not need quota authority. POST identity/config validation before installation
or network, permission before mutation, root lease/limit behavior inherited service.

Use explicit profile SecSourcePolicy, never implicit env/sec identity fallback.
Real-service route tests must exercise generated actual source bodies through new
document parser/store/query, not only assert mocks called. Preserve API error
redaction and all installed model/tool inventories. No dependency or auth changes.

Return only actual durable completion status. A disconnected client may still have
completed POST; keep GET reread path available. If introducing async bridge, own
cancel+await; existing synchronous route is acceptable with finite service timeouts.

Report exact request/response types and examples for Task4, named RED/GREEN and
inverse/gate logs in task-3-report.md. Parent controls independent review and commit.

Task2 examples (actual generated service/query outputs, not hand-built JSON) are in
task2-final-inverse-restored-01/interface-examples.json and its final report.
Index data has document/documents/sections/passages/text_start_cursor. Metadata
document_id is resolved file:<name>; query operands/cursors keep the caller's exact
choice including primary. Service attempt contains acquisition_id, nullable
attempt_id/capture_id, primary_document, resolved_document_id, status/gaps/outcome,
and measured request reports. clock() is an aware ISO string, not datetime object.
Pending independent Task2 review may revise implementation; use its final commit.

Task2 review found and is fixing invalid-report dispatch accounting. Its fix may
separate report validity from independently observed count/dispatch. Use the fixed
report delta; do not reconstruct no_dispatch from an empty validated-report list.

Fix1 at1f964efe defines requests as {operation,url,request_count,dispatch_state,
report,gaps}; count/report nullable, state dispatched/not_dispatched/unknown.
Attempt adds nullable invalidation_primary_document, which is NOT fresh admission
authority. GET envelope/citation/index shapes and service call signatures unchanged.
Use observed request_count, not report.requests, when rendering/reporting counts.
