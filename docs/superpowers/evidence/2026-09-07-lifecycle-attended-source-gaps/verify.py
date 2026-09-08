"""Attended-gap amendment: independent mutations against the whole prior focus."""

import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gap_prior", HERE.parent / "2026-09-07-lifecycle-source-priority-capacity/verify.py")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
verifier = prior.verifier
mutation = verifier.mutation
STORE = "src/lifecycle_web_store.py"
REVIEW = "src/lifecycle_web_review.py"
PIPELINE = "src/security_lifecycle_web_pipeline.py"
FINDING = "src/security_lifecycle_web_finding.py"
VIEW = "apps/arkscope-web/src/lifecycle/LifecycleWebPanel.tsx"
CONTRACT = "apps/arkscope-web/src/lifecycle/webContract.ts"

verifier.MUTATIONS = {
    "backend": (
        mutation("unread_supplement_blocks_every_action", "test_unread_supplement_does_not_block_an_otherwise_supported_attended_finding", FINDING,
                 "    # Unread supplements are disclosed by the journal/review packet, not proof\n"
                 "    # of a missing action field. Essential gaps and contradictions still block.",
                 '    if unread_source_count:\n        blockers.add("source_read_incomplete")'),
        mutation("gap_urls_dropped_at_controller", "test_real_controller_persists_gap_urls_or_reports_a_typed_invalid_gap_record",
                 "src/lifecycle_web_controller.py", "source_failure_urls=result.source_failure_urls)", "source_failure_urls={})"),
        mutation("malformed_url_map_treated_as_legacy", "test_reopened_journal_rejects_malformed_gap_urls_even_with_a_valid_payload_hash", STORE,
                 'urls=value.get("source_failure_urls", _MISSING_SOURCE_URLS))',
                 'urls=value.get("source_failure_urls") or _MISSING_SOURCE_URLS)'),
        mutation("unsafe_gap_url_accepted", "test_present_malformed_gap_metadata_is_not_treated_as_legacy_absence", STORE,
                 "if any(canonical_source_url(url) != url for url in urls.values()):", "if False:"),
        mutation("gap_disclosure_dropped_from_readback", "test_research_and_current_detail_share_readonly_web_findings_for_every_auth",
                 "src/lifecycle_web_projection.py", '"source_gaps": row["source_gaps"] if validated is not None else None,',
                 '"source_gaps": [] if validated is not None else None,'),
        mutation("gap_disclosure_dropped_from_public_review", "test_gap_disclosure_follows_finding_review_and_explicit_human_receipt",
                 "src/security_lifecycle_review.py", 'if "source_gaps" in packet else {}),', 'if False else {}),'),
        mutation("resigned_acceptance_loses_gap_binding", "test_central_writer_rechecks_gap_disclosure_even_if_an_acceptance_is_resigned", REVIEW,
                 '            or packet.get("source_gaps", []) != run["source_gaps"]\n', ''),
        mutation("old_client_can_confirm_unseen_gaps", "test_old_or_malformed_confirmation_cannot_apply_unshown_gaps", REVIEW,
                 'if run.get("source_gaps") and acknowledge_source_gaps is not True:', 'if False:'),
        mutation("truthy_acknowledgement_is_accepted", "test_direct_adoption_requires_literal_gap_acknowledgement", REVIEW,
                 'if run.get("source_gaps") and acknowledge_source_gaps is not True:',
                 'if run.get("source_gaps") and not acknowledge_source_gaps:'),
        mutation("changed_disclosure_digest_ignored", "test_confirmation_rejects_a_different_gap_disclosure_without_any_write", REVIEW,
                 'if packet["packet_sha256"] != packet_sha256 or packet["action"] != action:', 'if packet["action"] != action:'),
        mutation("essential_uncertainty_overridden", "test_disclosed_read_gap_does_not_override_missing_essential_proof", FINDING,
                 'if finding.unresolved_conditions:', 'if False:'),
        mutation("positive_otc_veto_overridden", "test_current_active_otc_evidence_still_vetoes_attended_adoption_with_read_gaps", REVIEW,
                 'row.get("listing_status") == "active" and instant(at)', 'False and instant(at)'),
        mutation("no_complete_source_still_runs_analysis", "test_all_source_failures_keep_measured_diagnostics_after_journal_reopen", PIPELINE,
                 '        if not pages:\n            raise WebModelError("source_read_incomplete")', '        if False:\n            raise WebModelError("source_read_incomplete")'),
        mutation("prompt_confuses_read_gap_with_material_uncertainty", "test_source_read_failure_remains_visible_and_never_retries", PIPELINE,
                 'Do not treat an unread supplement alone as a material unresolved condition.',
                 'Treat every unread supplement as a material unresolved condition.'),
    ),
    "frontend": (
        mutation("result_hides_gap_disclosure", "shows unread references and the reviewed conclusion at the last confirmation", VIEW,
                 '<SourceGaps gaps={run.source_gaps} locale={locale} />', '<SourceGaps gaps={null} locale={locale} />'),
        mutation("confirmation_hides_gap_disclosure", "shows unread references and the reviewed conclusion at the last confirmation", VIEW,
                 '<SourceGaps gaps={packet?.source_gaps ?? null} locale={locale} />', '<SourceGaps gaps={null} locale={locale} />'),
        mutation("confirmation_hides_reviewed_conclusion", "shows unread references and the reviewed conclusion at the last confirmation", VIEW,
                 '<p>{packet?.finding.impact_summary}</p>', '<p />'),
        mutation("gap_runtime_shape_unchecked", "rejects malformed gap metadata rather than hiding it", CONTRACT,
                 'export function parseWebSourceGaps(value: unknown) {\n',
                 'export function parseWebSourceGaps(value: unknown): any {\n  return value;\n'),
        mutation("review_parser_discards_gap_disclosure", "preserves the same closed source gap disclosure in result and confirmation",
                 "apps/arkscope-web/src/lifecycle/currentReviewContract.ts",
                 'source_gaps: row.source_gaps === undefined ? null : nullable(row.source_gaps, parseWebSourceGaps),',
                 'source_gaps: null,'),
        mutation("confirmation_omits_gap_acknowledgement", "acknowledges only the validated source gaps shown with the confirmed packet",
                 "apps/arkscope-web/src/api.ts", '...(packet.source_gaps?.length ? { acknowledge_source_gaps: true } : {})',
                 '...(false ? { acknowledge_source_gaps: true } : {})'),
        mutation("unknown_source_reason_claims_investigation_failed", "an unrecognized source reason does not turn a complete finding into a failed investigation", VIEW,
                 'copy.errors[gap.reason as keyof typeof copy.errors] ?? copy.sourceGapReasonUnknown', 'webReason(gap.reason, locale)'),
        mutation("gap_extra_internal_fields_accepted", "rejects malformed gap metadata rather than hiding it", CONTRACT,
                 'if (Object.keys(row).length !== 2 || !("url" in row) || !("reason" in row)) return invalid();', 'if (false) return invalid();'),
        mutation("gap_raw_error_reason_accepted", "rejects malformed gap metadata rather than hiding it", CONTRACT,
                 'if (!/^[a-z_]{1,100}$/.test(result.reason)) return invalid();', 'if (false) return invalid();'),
        mutation("gap_unsafe_url_accepted", "rejects malformed gap metadata rather than hiding it", CONTRACT,
                 'const result = { url: nullable(row.url, sourceUrl), reason: text(row.reason) };',
                 'const result = { url: nullable(row.url, text), reason: text(row.reason) };'),
    ),
}


if __name__ == "__main__":
    verifier.main()
