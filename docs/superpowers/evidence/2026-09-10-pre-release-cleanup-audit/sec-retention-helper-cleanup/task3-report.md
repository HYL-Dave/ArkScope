# Task3 Report

Status: implemented and committed; parent owns final whole-branch tests/review/census.
Base: `58e1929b61905b905fc0e12bdc5daf1ad116b84b`
Head: `0c5896a561fb8397daa79e60d4f1c80cb299463b` (announced immediately after commit; subsequent edits are scratch artifacts only).

## Scope
Exactly five registrations removed, App **221 -> 216**, no added or other changed endpoint identities. Measured before updating either exact-count owner: [route delta](task3-route-delta.json).
Translation orchestrator, adapter/DTO and three exclusive store methods deleted, with no placeholders. Schema and `list_evidence` historical SQL reader unchanged.

Committed files (M modified, D deleted):
```text
M src/api/routes/security_lifecycle.py
M src/api/routes/ticker_identity.py
M src/security_lifecycle_investigation.py
D src/security_lifecycle_translation.py
M tests/test_api.py
M tests/test_card_execution_authority.py
M tests/test_security_lifecycle_current_routes.py
M tests/test_security_lifecycle_review_routes.py
M tests/test_security_lifecycle_routes.py
M tests/test_security_lifecycle_tools.py
D tests/test_security_lifecycle_translation.py
```

## Verification
Same command environment/runner as [brief](task3-brief.md); complete commands, suites, exit codes, mutation and preservation checks: [evidence JSON](task3-evidence.json).
Every run retains full `task3-<run>.log` and `.xml`; both collection logs and suite manifests are also retained.

| Run | Passed / Failed | Meaning |
| --- | --- | --- |
| baseline | 975 / 0 | 27 exact affected suites, whole API included |
| inventory-before | 1 / 0 | Actual App inventory, no lifespan |
| red | 1 / 5 | All five named absence owners fail; positive surface passes |
| intermediate | 6 / 2 | Five absences + inventory pass; old surface/count owners fail |
| green | 962 / 0 | Updated scoped collateral and integrity controls |
| mutation | 0 / 1 | Original confirmation registration restored; named owner kills it |
| restored | 962 / 0 | Mutation byte-restored; complete scoped rerun before commit |

Collection: **975 -> 962**; **24 removed / 11 added identities**, including six preserved-behavior renames (18 obsolete-only removals + five absence owners). Exact IDs below; mappings and per-file counts: [accounting JSON](task3-accounting.json).

## Preservation And Concerns
Historical `test_case_detail_projects_original_evidence_with_derived_translations` keeps every original assertion; only setup became a synthetic SQL INSERT. Local audit projections, current list/no-write controls and four retry-state/receipt/no-write cases remain live. Shared card/translation/model/auth owners are unchanged except the single deleted adapter-only test.
No scoped regression observed. Production inventory/disposition is separate and was not rerun; no schema/data disposal, codec edits, provider execution, or broader parent work performed. Independent parent review remains outstanding.

<details>
<summary>Exact Removed Test IDs (24)</summary>

```text
tests/test_card_execution_authority.py::test_direct_evidence_translation_caller_keeps_captured_effort_and_auth
tests/test_security_lifecycle_current_routes.py::test_unknown_current_review_is_not_found
tests/test_security_lifecycle_review_routes.py::test_existing_case_readers_do_not_export_private_confirmation[audit_api]
tests/test_security_lifecycle_routes.py::test_active_case_routes_share_closed_projection_and_compact_listing_dto
tests/test_security_lifecycle_routes.py::test_case_automation_run_dispatches_exact_attended_authority
tests/test_security_lifecycle_routes.py::test_case_automation_run_materializes_a_source_only_case_in_the_worker
tests/test_security_lifecycle_routes.py::test_case_automation_run_reconciles_a_stale_running_row_after_lock_acquisition
tests/test_security_lifecycle_routes.py::test_case_automation_run_returns_409_on_real_flock_collision
tests/test_security_lifecycle_routes.py::test_evidence_translation_route_caches_and_returns_typed_provenance
tests/test_security_lifecycle_routes.py::test_evidence_translation_route_reports_selected_route_without_fallback
tests/test_security_lifecycle_routes.py::test_evidence_translation_route_reports_unresolvable_route_without_provider_call
tests/test_security_lifecycle_routes.py::test_evidence_translation_route_validates_before_permission_and_masks_failures
tests/test_security_lifecycle_routes.py::test_http_and_ai_share_one_exact_closed_automation_run_projection
tests/test_security_lifecycle_routes.py::test_manual_run_reports_profile_config_store_failure_as_typed_503[/security-lifecycle/cases/{case_id}/automation/run]
tests/test_security_lifecycle_routes.py::test_operator_detail_reaches_http_ai_tool_and_ui_identically
tests/test_security_lifecycle_routes.py::test_routes_omit_one_malformed_listing_without_losing_the_case_or_other_evidence
tests/test_security_lifecycle_translation.py::test_lifecycle_persistence_keeps_its_16000_character_boundary
tests/test_security_lifecycle_translation.py::test_listing_snapshot_translation_rejects_before_every_downstream_boundary
tests/test_security_lifecycle_translation.py::test_translation_cache_is_bound_to_evidence_hash_and_locale
tests/test_security_lifecycle_translation.py::test_translation_failure_detail_is_closed_bounded_and_message_free
tests/test_security_lifecycle_translation.py::test_translation_failure_leaves_authoritative_evidence_and_case_unchanged
tests/test_security_lifecycle_translation.py::test_translation_preserves_safe_typed_provider_failure
tests/test_security_lifecycle_translation.py::test_translation_rejects_unsupported_locale_and_malformed_output
tests/test_security_lifecycle_translation.py::test_translation_runs_without_write_transaction_and_rechecks_evidence
```
</details>

<details>
<summary>Exact Added Test IDs (11)</summary>

```text
tests/test_security_lifecycle_review_routes.py::test_existing_case_readers_do_not_export_private_confirmation[audit_local]
tests/test_security_lifecycle_routes.py::test_active_case_readers_share_closed_projection_and_compact_listing_dto
tests/test_security_lifecycle_routes.py::test_actual_app_excludes_unused_lifecycle_http_entry[case-audit]
tests/test_security_lifecycle_routes.py::test_actual_app_excludes_unused_lifecycle_http_entry[case-automation]
tests/test_security_lifecycle_routes.py::test_actual_app_excludes_unused_lifecycle_http_entry[current-review-detail]
tests/test_security_lifecycle_routes.py::test_actual_app_excludes_unused_lifecycle_http_entry[evidence-translation]
tests/test_security_lifecycle_routes.py::test_actual_app_excludes_unused_lifecycle_http_entry[review-confirmation]
tests/test_security_lifecycle_routes.py::test_case_readers_omit_one_malformed_listing_without_losing_the_case_or_other_evidence
tests/test_security_lifecycle_routes.py::test_global_automation_run_reconciles_a_stale_running_row_after_lock_acquisition
tests/test_security_lifecycle_routes.py::test_local_audit_and_ai_share_one_exact_closed_automation_run_projection
tests/test_security_lifecycle_routes.py::test_operator_detail_reaches_local_audit_and_ai_tool_identically
```
</details>
