# Task 1 Removed Behavior Owners

Base 331, frozen 290: 147 unchanged node IDs, 184 removed IDs, 143 added IDs.

Each entry groups parameterized removed IDs. The JSON ledger lists every exact removed ID, its classification, and exact passing replacement IDs.

## tests/test_lifecycle_web_store.py::test_web_journal_installation_is_explicit_and_preserves_existing_schema

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_store.py::test_current_installation_preserves_unrelated_data_and_requires_no_case`
- `tests/test_lifecycle_investigation_store.py::test_journal_read_does_not_install_or_tolerate_unknown_schema`

Old journal installer is deleted; current installer is explicit and preserves unrelated persisted data.

## tests/test_lifecycle_web_store.py::test_web_journal_preserves_model_authorship_without_creating_human_acceptance

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_store.py::test_current_source_rows_are_immutable_and_no_human_acceptance_is_fabricated`

## tests/test_lifecycle_web_store.py::test_start_is_idempotent_and_does_not_reset_or_replay_existing_execution

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_store.py::test_current_start_replays_request_without_resetting_recorded_work`
- `tests/test_lifecycle_investigation_controller.py::test_replayed_current_start_is_durable_across_controllers_without_redispatch`

## tests/test_lifecycle_web_store.py::test_stale_or_wrong_worker_cannot_record_provider_work

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_store.py::test_current_wrong_or_expired_owner_cannot_record_provider_work`

## tests/test_lifecycle_web_store.py::test_recording_failure_stops_before_dispatch_and_never_fakes_completion

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_store.py::test_current_recording_failure_stops_control_before_remote_dispatch`

## tests/test_lifecycle_web_store.py::test_cancel_ack_does_not_write_a_cancelled_remote_terminal

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_controller.py::test_current_cancel_requires_remote_terminal_not_just_interrupt_ack`

## tests/test_lifecycle_web_store.py::test_expired_lease_recovers_honestly_without_provider_or_retry

Removed nodes: 2. Classification: transferred.

- `tests/test_lifecycle_investigation_store.py::test_expired_lease_recovers_other_target_without_replaying_a_request`

## tests/test_lifecycle_web_store.py::test_immutable_source_rows_cannot_be_rebound_after_investigation

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_store.py::test_current_source_rows_are_immutable_and_no_human_acceptance_is_fabricated`

## tests/test_lifecycle_web_store.py::test_completed_result_requires_all_owned_remote_terminals

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_store.py::test_success_requires_a_completed_owned_conclusion`
- `tests/test_lifecycle_investigation_store.py::test_unknown_remote_is_not_reported_cancelled_or_successful`

## tests/test_lifecycle_web_review.py::test_web_review_preparation_never_creates_a_human_assessment_or_tracking_change

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_adoption_safety.py::test_current_review_preparation_never_creates_a_human_assessment_or_tracking_change`

Same attended/generic writer contract, exercised from actual li_ agent output. Scheduled execution uses a completed finding with an attended future execution date, not authorization from a planned event.

## tests/test_lifecycle_web_review.py::test_web_confirmation_uses_existing_atomic_writer_without_requiring_provider_success

Removed nodes: 8. Classification: transferred.

- `tests/test_lifecycle_investigation_adoption_safety.py::test_current_confirmation_uses_existing_atomic_writer_without_requiring_provider_success`

Same attended/generic writer contract, exercised from actual li_ agent output. Scheduled execution uses a completed finding with an attended future execution date, not authorization from a planned event.

## tests/test_lifecycle_web_review.py::test_web_confirmation_rejects_changed_material_without_partial_human_adoption

Removed nodes: 5. Classification: transferred.

- `tests/test_lifecycle_investigation_adoption_safety.py::test_current_confirmation_rejects_changed_material_without_partial_human_adoption`
- `tests/test_lifecycle_investigation_adoption_safety.py::test_current_due_writer_rejects_evidence_added_after_attended_adoption`

Same attended/generic writer contract, exercised from actual li_ agent output. Scheduled execution uses a completed finding with an attended future execution date, not authorization from a planned event.
Current launch creates no case/evidence anchor. Once an attended confirmation creates that anchor, later evidence must block the real due writer.

## tests/test_lifecycle_web_review.py::test_current_active_otc_veto_is_not_lost_when_other_provider_requests_failed

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_adoption_safety.py::test_current_active_otc_veto_is_not_lost_when_other_provider_requests_failed`

Same attended/generic writer contract, exercised from actual li_ agent output. Scheduled execution uses a completed finding with an attended future execution date, not authorization from a planned event.

## tests/test_lifecycle_web_review.py::test_future_web_action_is_scheduled_and_rechecked_before_applying

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_adoption_safety.py::test_future_current_action_is_scheduled_and_rechecked_before_applying`

Same attended/generic writer contract, exercised from actual li_ agent output. Scheduled execution uses a completed finding with an attended future execution date, not authorization from a planned event.

## tests/test_lifecycle_web_review.py::test_web_adoption_cannot_survive_an_approval_failure_in_a_partial_transaction

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_adoption_safety.py::test_current_adoption_cannot_survive_an_approval_failure_in_a_partial_transaction`

Same attended/generic writer contract, exercised from actual li_ agent output. Scheduled execution uses a completed finding with an attended future execution date, not authorization from a planned event.

## tests/test_lifecycle_web_review.py::test_unrelated_sa_refresh_and_other_ticker_edits_do_not_block_web_review

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_adoption_safety.py::test_unrelated_sa_refresh_and_other_ticker_edits_do_not_block_current_review`

Same attended/generic writer contract, exercised from actual li_ agent output. Scheduled execution uses a completed finding with an attended future execution date, not authorization from a planned event.

## tests/test_lifecycle_web_review.py::test_unretained_sec_case_cannot_start_new_adoption_but_keeps_audit_material

Removed nodes: 2. Classification: legacy_only_removed.

No replacement runtime branch: exclusively legacy behavior removed.

Launch/adoption based on an obsolete unretained SEC case no longer exists. Current target runs require no legacy case; no hypothetical legacy run retained.

## tests/test_lifecycle_web_review.py::test_central_writer_rejects_forged_web_authority_even_with_recomputed_preview_digest

Removed nodes: 3. Classification: transferred.

- `tests/test_lifecycle_investigation_adoption_safety.py::test_central_writer_rejects_forged_current_authority_even_with_recomputed_preview_digest`

Same attended/generic writer contract, exercised from actual li_ agent output. Scheduled execution uses a completed finding with an attended future execution date, not authorization from a planned event.

## tests/test_lifecycle_web_review.py::test_stale_provider_state_after_web_approval_blocks_the_real_due_writer

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_adoption_safety.py::test_stale_provider_state_after_current_approval_blocks_the_real_due_writer`

Same attended/generic writer contract, exercised from actual li_ agent output. Scheduled execution uses a completed finding with an attended future execution date, not authorization from a planned event.

## tests/test_lifecycle_web_review.py::test_web_applied_receipt_can_reverse_without_erasing_investigation_or_reenrolling_on_sa_refresh

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_adoption_safety.py::test_current_applied_receipt_can_reverse_without_erasing_investigation_or_reenrolling_on_sa_refresh`

Same attended/generic writer contract, exercised from actual li_ agent output. Scheduled execution uses a completed finding with an attended future execution date, not authorization from a planned event.

## tests/test_lifecycle_web_read.py::test_research_and_current_detail_share_readonly_web_findings_for_every_auth

Removed nodes: 8. Classification: transferred.

- `tests/test_lifecycle_investigation_routes.py::test_target_routes_read_and_adopt_without_dispatch_or_legacy_queue`
- `tests/test_lifecycle_investigation_controller.py::test_current_worker_preserves_four_channel_identity_and_provider_free_readback`

Per-case model-tool web_runs projection is intentionally removed. Current run/latest API readback owns preserved findings, auth, no-dispatch, and private-data exclusion.

## tests/test_lifecycle_web_read.py::test_population_retains_web_sources_and_human_adoption_without_exporting_pages_or_credentials

Removed nodes: 1. Classification: legacy_only_removed.

No replacement runtime branch: exclusively legacy behavior removed.

Exclusively legacy web_journal population inventory/retention shape; current journal is not exported under this obsolete prefix.

## tests/test_lifecycle_web_read.py::test_missing_journal_is_empty_but_malformed_installed_journal_is_not_silently_dropped

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_store.py::test_journal_read_does_not_install_or_tolerate_unknown_schema`

Legacy detail web_runs absence is removed; current journal missing/unknown schema must fail closed without installing.

## tests/test_lifecycle_web_read.py::test_population_rejects_orphaned_web_adoption_dependency

Removed nodes: 1. Classification: legacy_only_removed.

No replacement runtime branch: exclusively legacy behavior removed.

Obsolete web_journal_inventory acceptance-reference format removed. Task 2 owns current population reference closure.

## tests/test_lifecycle_web_read.py::test_population_does_not_treat_a_malformed_web_inventory_as_absent

Removed nodes: 4. Classification: legacy_only_removed.

No replacement runtime branch: exclusively legacy behavior removed.

Obsolete web_journal_inventory format removed; Task 2 rejects unexpected manifest material, not hypothetical old installations.

## tests/test_lifecycle_web_gaps.py::test_gap_disclosure_follows_finding_review_and_explicit_human_receipt

Removed nodes: 8. Classification: transferred.

- `tests/test_lifecycle_investigation_gaps.py::test_current_gap_disclosure_follows_finding_review_and_explicit_receipt`

Old source-ID failure/URL side dictionaries are removed. Current gaps are actual agent observations; closed shape, canonical public URL, explicit acknowledgement, and fail-closed re-read are retained.

## tests/test_lifecycle_web_gaps.py::test_confirmation_rejects_a_different_gap_disclosure_without_any_write

Removed nodes: 4. Classification: transferred.

- `tests/test_lifecycle_investigation_gaps.py::test_current_confirmation_rejects_different_gap_disclosure_without_write`

Old source-ID failure/URL side dictionaries are removed. Current gaps are actual agent observations; closed shape, canonical public URL, explicit acknowledgement, and fail-closed re-read are retained.

## tests/test_lifecycle_web_gaps.py::test_old_or_malformed_confirmation_cannot_apply_unshown_gaps

Removed nodes: 5. Classification: transferred.

- `tests/test_lifecycle_investigation_gaps.py::test_current_confirmation_api_cannot_apply_unacknowledged_gaps`

Old source-ID failure/URL side dictionaries are removed. Current gaps are actual agent observations; closed shape, canonical public URL, explicit acknowledgement, and fail-closed re-read are retained.

## tests/test_lifecycle_web_gaps.py::test_direct_adoption_requires_literal_gap_acknowledgement

Removed nodes: 4. Classification: transferred.

- `tests/test_lifecycle_investigation_gaps.py::test_current_direct_adoption_requires_literal_gap_acknowledgement`

Old source-ID failure/URL side dictionaries are removed. Current gaps are actual agent observations; closed shape, canonical public URL, explicit acknowledgement, and fail-closed re-read are retained.

## tests/test_lifecycle_web_gaps.py::test_gap_acknowledgement_never_substitutes_for_a_completed_investigation

Removed nodes: 2. Classification: transferred.

- `tests/test_lifecycle_investigation_gaps.py::test_current_gap_acknowledgement_never_substitutes_for_completed_finding`

Old source-ID failure/URL side dictionaries are removed. Current gaps are actual agent observations; closed shape, canonical public URL, explicit acknowledgement, and fail-closed re-read are retained.

## tests/test_lifecycle_web_gaps.py::test_disclosed_read_gap_does_not_override_missing_essential_proof

Removed nodes: 5. Classification: transferred, changed_current_policy.

- `tests/test_lifecycle_investigation_gaps.py::test_current_disclosed_gap_does_not_override_missing_essential_proof`
- `tests/test_lifecycle_investigation_review.py::test_unknown_event_date_is_explicit_and_requires_an_attended_execution_date`

Old source-ID failure/URL side dictionaries are removed. Current gaps are actual agent observations; closed shape, canonical public URL, explicit acknowledgement, and fail-closed re-read are retained.
The exact event date may remain unknown in a current finding; the attended user must supply an execution date. The old unconditional missing-model-date veto is deliberately not reinstated.

## tests/test_lifecycle_web_gaps.py::test_present_malformed_gap_metadata_is_not_treated_as_legacy_absence

Removed nodes: 7. Classification: transferred.

- `tests/test_lifecycle_investigation_gaps.py::test_current_adoption_rejects_malformed_saved_gaps_even_with_valid_payload_hash`

Old source-ID failure/URL side dictionaries are removed. Current gaps are actual agent observations; closed shape, canonical public URL, explicit acknowledgement, and fail-closed re-read are retained.

## tests/test_lifecycle_web_gaps.py::test_reopened_journal_rejects_malformed_gap_urls_even_with_a_valid_payload_hash

Removed nodes: 4. Classification: transferred.

- `tests/test_lifecycle_investigation_gaps.py::test_current_adoption_rejects_malformed_saved_gaps_even_with_valid_payload_hash`

Old source-ID failure/URL side dictionaries are removed. Current gaps are actual agent observations; closed shape, canonical public URL, explicit acknowledgement, and fail-closed re-read are retained.

## tests/test_lifecycle_web_gaps.py::test_gap_metadata_cannot_relabel_read_pages_exceed_source_count_or_export_raw_errors

Removed nodes: 5. Classification: transferred.

- `tests/test_lifecycle_investigation_gaps.py::test_current_adoption_rejects_malformed_saved_gaps_even_with_valid_payload_hash`

Old source-ID failure/URL side dictionaries are removed. Current gaps are actual agent observations; closed shape, canonical public URL, explicit acknowledgement, and fail-closed re-read are retained.

## tests/test_lifecycle_web_gaps.py::test_central_writer_rechecks_gap_disclosure_even_if_an_acceptance_is_resigned

Removed nodes: 2. Classification: transferred.

- `tests/test_lifecycle_investigation_gaps.py::test_current_writer_rechecks_gap_disclosure_even_when_acceptance_is_resigned`

Old source-ID failure/URL side dictionaries are removed. Current gaps are actual agent observations; closed shape, canonical public URL, explicit acknowledgement, and fail-closed re-read are retained.

## tests/test_lifecycle_web_gaps.py::test_current_active_otc_evidence_still_vetoes_attended_adoption_with_read_gaps

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_gaps.py::test_current_gap_acknowledgement_never_waives_active_provider_evidence`

Old source-ID failure/URL side dictionaries are removed. Current gaps are actual agent observations; closed shape, canonical public URL, explicit acknowledgement, and fail-closed re-read are retained.

## tests/test_lifecycle_web_gaps.py::test_legacy_read_gap_is_visible_without_inventing_a_source_url

Removed nodes: 1. Classification: legacy_only_removed.

No replacement runtime branch: exclusively legacy behavior removed.

Legacy absent source_failure_urls fallback is retired. Current agents record explicit URL/corpus on each gap; no old-payload absence branch remains.

## tests/test_lifecycle_web_gaps.py::test_no_gaps_is_an_empty_list_not_unknown_and_no_extra_internal_fields_escape

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_gaps.py::test_current_review_has_empty_gaps_without_internal_source_fields`

Old source-ID failure/URL side dictionaries are removed. Current gaps are actual agent observations; closed shape, canonical public URL, explicit acknowledgement, and fail-closed re-read are retained.

## tests/test_lifecycle_web_attended_concurrency.py::test_attended_web_source_validation_leaves_other_profile_writers_available

Removed nodes: 6. Classification: transferred.

- `tests/test_lifecycle_investigation_attended_concurrency.py::test_current_source_validation_leaves_profile_writers_available`

Current li_ captures and actual SQLite connections; both WAL and rollback-journal control, no copied old writer.

## tests/test_lifecycle_web_attended_concurrency.py::test_validated_web_read_rechecks_its_binding_inside_the_transaction

Removed nodes: 4. Classification: transferred.

- `tests/test_lifecycle_investigation_attended_concurrency.py::test_current_validated_read_rechecks_its_binding_inside_the_transaction`

Current li_ captures and actual SQLite connections; both WAL and rollback-journal control, no copied old writer.

## tests/test_lifecycle_web_attended_concurrency.py::test_page_rewrite_with_unchanged_digest_cannot_reuse_a_verified_read

Removed nodes: 2. Classification: transferred.

- `tests/test_lifecycle_investigation_attended_concurrency.py::test_current_source_rewrite_with_unchanged_digest_invalidates_verified_read`

Current li_ captures and actual SQLite connections; both WAL and rollback-journal control, no copied old writer.

## tests/test_lifecycle_web_attended_concurrency.py::test_verified_web_material_cannot_cross_its_profile_run_or_transaction

Removed nodes: 4. Classification: transferred.

- `tests/test_lifecycle_investigation_attended_concurrency.py::test_current_verified_material_cannot_cross_profile_run_or_transaction`

Current li_ captures and actual SQLite connections; both WAL and rollback-journal control, no copied old writer.

## tests/test_lifecycle_web_attended_concurrency.py::test_prevalidated_sources_do_not_cache_mutable_adoption_authority

Removed nodes: 5. Classification: transferred.

- `tests/test_lifecycle_investigation_attended_concurrency.py::test_current_prevalidated_sources_do_not_cache_mutable_adoption_authority`

Current li_ captures and actual SQLite connections; both WAL and rollback-journal control, no copied old writer.

## tests/test_lifecycle_web_attended_concurrency.py::test_permission_is_rechecked_after_expensive_source_validation

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_attended_concurrency.py::test_current_permission_is_rechecked_after_expensive_validation_before_opening_writer`

Current li_ captures and actual SQLite connections; both WAL and rollback-journal control, no copied old writer.

## tests/test_lifecycle_web_attended_concurrency.py::test_source_validation_is_not_cached_between_user_commands

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_attended_concurrency.py::test_current_source_validation_is_not_cached_between_user_commands`

Current li_ captures and actual SQLite connections; both WAL and rollback-journal control, no copied old writer.

## tests/test_lifecycle_web_attended_concurrency.py::test_generic_review_of_a_web_adoption_uses_the_same_verified_read

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_attended_concurrency.py::test_current_source_validation_leaves_profile_writers_available`

Current li_ captures and actual SQLite connections; both WAL and rollback-journal control, no copied old writer.

## tests/test_lifecycle_web_attended_concurrency.py::test_adoption_prevalidation_never_releases_a_callers_transaction

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_attended_concurrency.py::test_current_adoption_prevalidation_never_releases_callers_transaction`

Current li_ captures and actual SQLite connections; both WAL and rollback-journal control, no copied old writer.

## tests/test_lifecycle_web_attended_concurrency.py::test_attended_confirmation_cannot_starve_a_real_current_worker

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_attended_concurrency.py::test_current_confirmation_does_not_starve_a_real_investigation_worker`

Current li_ captures and actual SQLite connections; both WAL and rollback-journal control, no copied old writer.

## tests/test_lifecycle_web_usage_journal.py::test_legacy_usage_has_no_fabricated_scope_or_zero_counters

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_usage_journal.py::test_current_usage_retains_known_or_unknown_totals_and_truthful_remote_outcome`

Legacy usage_report absence branch removed. Current unreported per-call observation stays None; incomplete totals stay unknown.

## tests/test_lifecycle_web_usage_journal.py::test_usage_receipt_rejects_cross_call_duplicate_and_malformed_observations_before_write

Removed nodes: 7. Classification: transferred.

- `tests/test_lifecycle_investigation_usage_journal.py::test_current_reopened_usage_rechecks_call_binding_and_integrity`
- `tests/test_lifecycle_web_usage.py::test_malformed_reported_model_counter_is_not_silently_unknown`

Old two-phase fail()/usage_report write API is physically removed; current adapters reject malformed provider counters, and current journal rechecks every completed call, observation, uniqueness and aggregate before projection/adoption.

## tests/test_lifecycle_web_usage_journal.py::test_usage_only_failure_receipt_is_readable_and_does_not_create_a_finding

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_usage_journal.py::test_current_usage_retains_known_or_unknown_totals_and_truthful_remote_outcome`

## tests/test_lifecycle_web_usage_journal.py::test_present_malformed_saved_usage_is_not_treated_as_legacy_absence

Removed nodes: 5. Classification: transferred.

- `tests/test_lifecycle_investigation_usage_journal.py::test_current_reopened_usage_rechecks_call_binding_and_integrity`

Current model_result steps replace legacy fixed search/analysis phase receipts.

## tests/test_lifecycle_web_usage_journal.py::test_reopened_usage_receipt_rechecks_remote_binding_even_with_valid_hash

Removed nodes: 3. Classification: transferred.

- `tests/test_lifecycle_investigation_usage_journal.py::test_current_reopened_usage_rechecks_call_binding_and_integrity`

Current model_result steps replace legacy fixed search/analysis phase receipts.

## tests/test_lifecycle_web_usage_journal.py::test_completed_result_rechecks_aggregate_agreement_on_read

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_usage_journal.py::test_current_reopened_usage_rechecks_call_binding_and_integrity`

Current model_result steps replace legacy fixed search/analysis phase receipts.

## tests/test_lifecycle_web_usage_journal.py::test_legacy_usage_pair_rejects_malformed_shape_instead_of_exporting_it

Removed nodes: 5. Classification: transferred.

- `tests/test_lifecycle_investigation_usage_journal.py::test_current_reopened_usage_rechecks_call_binding_and_integrity`

Current model_result steps replace legacy fixed search/analysis phase receipts.

## tests/test_lifecycle_source_capacity.py::test_unicode_source_journal_avoids_escape_expansion_without_changing_old_digests

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_source_journal.py::test_current_journal_preserves_full_unicode_source_and_supplied_passages_after_reopen`

Full current Unicode capture and canonical payload digest retained. Legacy page_json-specific storage expansion ratio and dual old encodings are obsolete; neutral codec UTF-8/canonical digest owners remain unchanged.

## tests/test_lifecycle_source_capacity.py::test_source_journal_still_rejects_changed_page_and_capture_fingerprints

Removed nodes: 2. Classification: transferred.

- `tests/test_lifecycle_investigation_source_journal.py::test_current_adoption_rejects_changed_source_or_capture_digest`

Current source text and canonical payload digests replace obsolete SourcePage capture_sha256 storage.

## tests/test_lifecycle_source_capacity.py::test_final_source_validation_does_not_block_heartbeat_or_cancellation

Removed nodes: 2. Classification: transferred.

- `tests/test_lifecycle_investigation_source_journal.py::test_current_agent_final_source_validation_allows_heartbeat_and_running_cancellation`

## tests/test_lifecycle_source_capacity.py::test_final_source_decoding_does_not_keep_a_read_transaction_open

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_source_progress.py::test_current_source_read_decoding_releases_its_owned_read_transaction`

## tests/test_lifecycle_source_capacity.py::test_changed_source_snapshot_cannot_commit_a_previously_validated_finding

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_attended_concurrency.py::test_current_confirmation_rejects_source_added_after_validation`

## tests/test_lifecycle_source_context.py::test_web_journal_retains_context_ranges_and_full_source_after_reopen

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_source_journal.py::test_current_journal_preserves_full_unicode_source_and_supplied_passages_after_reopen`

Actual source captures and supplied passage IDs replace old per-page source_context range envelopes. Pure range/byte context tests stay unchanged.

## tests/test_lifecycle_source_context.py::test_present_but_malformed_journal_context_is_not_treated_as_legacy_full_text

Removed nodes: 4. Classification: transferred.

- `tests/test_lifecycle_investigation_source_journal.py::test_current_adoption_requires_citations_from_the_recorded_model_context`

## tests/test_lifecycle_source_progress.py::test_web_journal_wait_is_bounded_below_the_unchanged_lease

Removed nodes: 2. Classification: transferred.

- `tests/test_lifecycle_source_progress.py::test_current_journal_wait_is_bounded_below_the_lease`

## tests/test_lifecycle_source_progress.py::test_web_journal_wait_preserves_owner_cancellation_and_failure

Removed nodes: 3. Classification: transferred.

- `tests/test_lifecycle_source_progress.py::test_current_journal_wait_preserves_cancellation_and_failure`

## tests/test_lifecycle_source_progress.py::test_historical_projection_does_not_decode_running_source_bodies

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_controller.py::test_current_progress_reads_skip_source_bodies_and_do_not_redispatch`

## tests/test_lifecycle_source_progress.py::test_source_read_decoding_releases_its_owned_read_transaction

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_source_progress.py::test_current_source_read_decoding_releases_its_owned_read_transaction`

## tests/test_lifecycle_source_progress.py::test_source_read_validation_releases_its_owned_read_transaction

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_attended_concurrency.py::test_current_source_validation_leaves_profile_writers_available`

## tests/test_lifecycle_source_progress.py::test_transaction_bound_adoption_read_retains_caller_atomicity

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_source_progress.py::test_current_transaction_bound_adoption_read_retains_caller_atomicity`

## tests/test_lifecycle_source_progress.py::test_connection_reader_does_not_hold_page_cursor_during_decoding

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_source_progress.py::test_current_connection_reader_releases_source_cursor_before_decoding`

## tests/test_lifecycle_source_progress.py::test_source_read_keeps_snapshot_when_worker_adds_a_later_source

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_source_progress.py::test_current_source_read_keeps_snapshot_when_worker_adds_a_later_source`

## tests/test_lifecycle_source_progress.py::test_terminal_historical_projection_still_validates_source_integrity

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_source_journal.py::test_current_adoption_rejects_changed_source_or_capture_digest`
- `tests/test_ticker_identity_history.py::test_current_history_requires_approved_passage_digest_even_when_result_is_resigned`

Current approval validates full source; history verifies the approved result/passages digest without rereading large source bodies.

## tests/test_lifecycle_source_read_report.py::test_population_retains_failure_receipts_without_accepting_them_as_findings

Removed nodes: 1. Classification: legacy_only_removed.

No replacement runtime branch: exclusively legacy behavior removed.

Exclusively old web_journal population inventory reference closure. Real current failure diagnostics/readback remain in the retained same-named all_source_failures owner.

## tests/test_ticker_identity_history.py::test_legacy_web_investigation_history_preserves_auth_model_and_source_link

Removed nodes: 1. Classification: transferred.

- `tests/test_ticker_identity_history.py::test_target_investigation_history_names_the_recorded_model_and_cited_news_only`

Current li_ history uses captured model/auth and original cited news; current-admission and full-source parsing forbidden.

## tests/test_ticker_identity_history.py::test_legacy_web_source_metadata_must_match_the_approved_passage_digest

Removed nodes: 4. Classification: transferred.

- `tests/test_ticker_identity_history.py::test_current_history_requires_approved_passage_digest_even_when_result_is_resigned`
- `tests/test_lifecycle_investigation_source_journal.py::test_current_adoption_rejects_changed_source_or_capture_digest`

Current history's owner is the approved result/passages snapshot, not legacy pages metadata. Digest guard is inverse-mutation proven.

## tests/test_lifecycle_investigation_store.py::test_v2_installation_preserves_v1_and_requires_no_case

Removed nodes: 1. Classification: transferred.

- `tests/test_lifecycle_investigation_store.py::test_current_installation_preserves_unrelated_data_and_requires_no_case`

Preserve unrelated data and no fabricated case. Installing/preserving hypothetical abandoned schema is intentionally removed.

## tests/test_lifecycle_journal_codec.py::test_retained_journal_does_not_export_legacy_codec_helpers

Removed nodes: 2. Classification: legacy_only_removed.

No replacement runtime branch: exclusively legacy behavior removed.

Old module export assertions are obsolete because old module is physically absent, proven by parent's absence owners. Neutral codec's literal byte/digest tests remain.

## tests/test_lifecycle_journal_codec.py::test_journal_consumers_import_the_neutral_codec_directly

Removed nodes: 3. Classification: legacy_only_removed, transferred.

- `tests/test_lifecycle_journal_codec.py::test_journal_consumers_import_the_neutral_codec_directly`

This AST ownership check exclusively targeted a physically deleted old module. Parent's absence tests now prohibit restoring it.
Old consumers removed, new current review consumes canonical_json directly. Remaining history parameter ID shifts because list is shorter.

