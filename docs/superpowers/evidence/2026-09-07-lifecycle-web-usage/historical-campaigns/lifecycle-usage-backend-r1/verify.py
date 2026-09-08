"""Usage calibration owners, always run against the entire existing focus."""

import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("usage_previous", HERE.parent / "2026-09-07-lifecycle-attended-write-concurrency/verify.py")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
verifier = prior.verifier
mutation = verifier.mutation
USAGE = "src/auth_drivers/lifecycle_web_usage.py"
STORE = "src/lifecycle_web_store.py"
CONTROLLER = "src/lifecycle_web_controller.py"
VIEW = "apps/arkscope-web/src/lifecycle/LifecycleWebPanel.tsx"
CONTRACT = "apps/arkscope-web/src/lifecycle/webContract.ts"
retained = tuple(item for item in verifier.MUTATIONS["backend"] if item["name"] in {
    "verified_read_discarded_under_write_lock", "changed_journal_binding_accepted",
})
verifier.MUTATIONS = {
    "backend": retained + (
        mutation("main_loop_substituted_for_model_aggregate", "test_claude_web_uses_reported_model_totals_not_main_loop_or_sum_of_scopes",
                 "src/auth_drivers/lifecycle_web_claude.py",
                 'return ModelReply(session_id, output, {key: usage["values"][key] for key in TOKEN_FIELDS}, usage)',
                 'return ModelReply(session_id, output, {key: usage["main_loop"][key] for key in TOKEN_FIELDS}, usage)'),
        mutation("missing_counters_become_zero", "test_missing_model_aggregate_does_not_fall_back_to_main_loop_usage", USAGE,
                 '    if not known or (require_all and len(known) != len(values)):\n        return None',
                 '    if not known or (require_all and len(known) != len(values)):\n        return 0'),
        mutation("boolean_counter_is_a_token", "test_malformed_reported_model_counter_is_not_silently_unknown[True]", USAGE,
                 'type(value) is not int or not 0 <= value <= _MAX_COUNTER',
                 'not isinstance(value, int) or not 0 <= value <= _MAX_COUNTER'),
        mutation("counter_loses_json_integer_precision", "test_malformed_reported_model_counter_is_not_silently_unknown[9007199254740992]", USAGE,
                 'type(value) is not int or not 0 <= value <= _MAX_COUNTER', 'type(value) is not int or value < 0'),
        mutation("partial_rows_claim_complete_total", "test_model_rows_sum_only_equal_scopes_and_missing_row_is_not_zero", USAGE,
                 'not known or (require_all and len(known) != len(values))', 'not known'),
        mutation("failure_discards_accepted_search_usage", "test_real_pipeline_usage_survives_source_failure_and_reopen_for_each_channel", CONTROLLER,
                 'usage_report={"version": 1, "phases": usage_phases})', 'usage_report={"version": 1, "phases": []})'),
        mutation("controller_never_observes_accepted_usage", "test_completed_pipeline_sums_each_accepted_phase_once_without_changing_action", CONTROLLER,
                 '                on_reply=reply,', '                on_reply=None,'),
        mutation("another_remote_call_supplies_usage", "test_reopened_usage_receipt_rechecks_remote_binding_even_with_valid_hash", USAGE,
                 'or phase["remote_id"] != calls[call_id]["remote_id"]', 'or False'),
        mutation("duplicate_phase_usage_is_accepted", "test_usage_receipt_rejects_cross_call_duplicate_and_malformed_observations_before_write", USAGE,
                 'or call_id in seen or call_id not in calls', 'or call_id not in calls'),
        mutation("saved_usage_report_ignored", "test_reopened_usage_receipt_rechecks_remote_binding_even_with_valid_hash", STORE,
                 '            if "usage_report" in value:\n', '            if False:\n'),
        mutation("legacy_usage_shape_unchecked", "test_legacy_usage_pair_rejects_malformed_shape_instead_of_exporting_it", STORE,
                 'value["usage"] = token_totals(value.get("usage"))', 'value["usage"] = value.get("usage")'),
        mutation("pipeline_total_not_bound_before_write", "test_inconsistent_pipeline_total_is_rejected_before_success_but_phase_usage_is_retained", STORE,
                 'if public_usage["totals"] != normalized_usage(usage):', 'if False:'),
        mutation("saved_total_disagrees_with_phase_report", "test_completed_result_rechecks_aggregate_agreement_on_read", STORE,
                 'if "usage_report" in value and result["usage"] != value["usage"]:', 'if False:'),
        mutation("extra_usage_fields_silently_discarded", "test_usage_receipt_rejects_cross_call_duplicate_and_malformed_observations_before_write", USAGE,
                 'or set(value) != {"basis", "values", "main_loop"}', 'or False'),
    ),
    "frontend": (
        mutation("runtime_discards_phase_provenance", "roundtrips phase counters without losing provenance or cache counts", CONTRACT,
                 'usage_report: row.usage_report === undefined ? null : nullable(row.usage_report, (value) => usageReport(value, count(row.model_submissions))),',
                 'usage_report: null,'),
        mutation("frontend_accepts_false_coverage", "instead of hiding present malformed usage", CONTRACT,
                 'if (result.coverage !== coverage) return invalid();', 'if (false) return invalid();'),
        mutation("frontend_accepts_total_disagreement", "rejects disagreement with the parent usage pair", CONTRACT,
                 'if (result.usage_report && (result.usage_report.totals.input_tokens !== result.usage.input_tokens',
                 'if (false && result.usage_report && (result.usage_report.totals.input_tokens !== result.usage.input_tokens'),
        mutation("usage_not_collapsed", "keeps usage in a collapsed record and never dispatches on expansion", VIEW,
                 '<details className="lifecycle-web-usage">', '<details className="lifecycle-web-usage" open>'),
        mutation("legacy_usage_claims_complete", "shows unrecorded scope for old history instead of declaring zero or complete usage", VIEW,
                 '<p>{copy.usageLegacy}</p>', '<p>{copy.usageCoverage.complete}</p>'),
        mutation("partial_usage_claims_total", "does not present a partial accounting subtotal as the complete amount or investigation success", VIEW,
                 '<h4>{report.coverage === "complete" ? copy.usageTotal : copy.usageSubtotal}</h4>', '<h4>{copy.usageTotal}</h4>'),
        mutation("unreported_displayed_as_zero", "distinguishes unknown from actual zero in displayed counters", VIEW,
                 'value === null ? copy.usageUnknown : value.toLocaleString(locale)', 'value === null ? "0" : value.toLocaleString(locale)'),
        mutation("cache_token_scope_hidden", "keeps usage in a collapsed record and never dispatches on expansion", VIEW,
                 '...(phase.basis === "claude_model_usage" ? [', '...(false ? ['),
    ),
}


if __name__ == "__main__":
    verifier.main()
