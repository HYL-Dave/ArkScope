# Task8 Cross-Task Verification Ownership

Status: final complete backend NOT RUN. Scoped review at911d69a2 leaves blocking
N1 (Anthropic child model I/O on the OpenAI parent loop). This mapping is retained
for the corrected-source gate; there is no task8-final-validation.json result
and no complete-suite claim in this checkpoint.

The workflow review approved its two tests and explicitly declined to infer
broader guarantees from those examples. The final complete backend gate must
execute the contract owners below; their actual counts will appear in
task8-final-validation.json. That file, not this pre-gate mapping, is the result.

| Requirement | Existing owners retained in the gate |
| --- | --- |
| Default-off, real scheduler/state/audit and fair fresh membership | test_sec_research_schedule, test_sec_research_schedule_runtime, test_data_scheduler, test_active_universe, test_macro_scheduler_outcomes |
| Four real tool adapters and common output admission | test_sec_research_tool_adapters, test_sec_research_tool_results, test_tool_output_channels, test_sec_research_output_integration, test_sec_research_native_dispatch |
| Delegated invocation, retained references and SDK-owned cancellation | test_sec_research_delegated_dispatch, test_sec_research_delegated_trace, test_subagent, test_fable_5_1_runtime |
| Zero acquisition for stored/pinned requests | test_sec_research_tool_service, test_sec_research_release_workflow; M1 now asserts both acquisition-entry and transport counts |
| Snapshot/filter cursors, malformed inputs and multipage UTF-8 boundaries | test_sec_research_queries, test_sec_research_fact_queries, test_sec_research_document_queries |
| Exact Decimal TEXT, independent periods and current schema | test_sec_research_facts, test_sec_research_store, test_sec_research_catalog |
| Complete retained citations and historical Research publication | test_sec_research_citations, test_sec_research_references, test_sec_research_trace, test_research_runs, test_research_threads |
| Original capture/file safety and interrupted publication | test_sec_research_captures, test_sec_research_capture_lock, test_sec_research_document_store, test_sec_research_maintenance |
| Document section/TOC semantics | test_sec_research_document_toc, test_sec_research_document_queries |
| Operation exclusion, portable backup, reset and unrelated data protection | test_sec_research_operations, test_sec_research_operation_admission, test_sec_research_schema_admin, test_sec_research_cli |
| Existing data, decisions and captured auth/default selection | test_market_data_direct, test_sa_capture_store, test_news_identity, test_lifecycle_investigation_review, test_task_runtime_binding, test_card_execution_authority |

Frontend has a separate fresh full1833P gate and typecheck/build/i18n receipts.
Task7's final actual-service browser proof checks four locale/viewport cases,
stored pinned content, dirty budget and shared schedule controls. It does not
claim live SEC/model behavior or an all-Settings health census. The earlier
Research citation UI owners are also included in the full frontend run.

Source/test/runner readback and prior review boundaries remain explicit in
task8-final-proof-readback.json:13 current-source schedule inverses, exact
publication repair proof, unchanged maintenance implementation and39 unchanged
existing maintenance definitions. Only the schedule batch verification was
added to the operation verifier; its current negative/inverse owners cover that
new boundary. Older checkpoints are not mislabelled fresh mutation runs.

The complete gate compares exact collected/executed node identities and the
same12 explicitly live-only skipped test identities from maintenance acceptance.
Focused runs and reviewed examples are never added to the final passed count.
No test proves absence of damage in a production DB that was not opened here.
