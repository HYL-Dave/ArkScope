"""Whole-focus concurrency and admission owners; UI contracts are unchanged."""

import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("attended_prior", HERE.parent / "2026-09-07-lifecycle-attended-source-gaps/verify.py")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
verifier = prior.verifier
mutation = verifier.mutation
STORE = "src/lifecycle_web_store.py"
REVIEW = "src/lifecycle_web_review.py"
retained = tuple(item for item in verifier.MUTATIONS["backend"] if item["name"] in {
    "resigned_acceptance_loses_gap_binding", "old_client_can_confirm_unseen_gaps",
    "truthy_acknowledgement_is_accepted", "changed_disclosure_digest_ignored",
    "positive_otc_veto_overridden", "essential_uncertainty_overridden",
})
verifier.MUTATIONS = {"frontend": (), "backend": retained + (
    mutation("verified_read_discarded_under_write_lock", "test_attended_web_source_validation_leaves_other_profile_writers_available[confirm-decode]", STORE,
             "        if validated is not None:\n", "        if False:\n"),
    mutation("changed_journal_binding_accepted", "test_validated_web_read_rechecks_its_binding_inside_the_transaction", STORE,
             "if LifecycleWebStore._review_binding(conn, run_id) != self.binding:", "if False:"),
    mutation("schema_generation_not_bound", "test_page_rewrite_with_unchanged_digest_cannot_reuse_a_verified_read", STORE,
             'cls._source_index(conn, run_id), conn.execute("PRAGMA schema_version").fetchone()[0])',
             'cls._source_index(conn, run_id), 0)'),
    mutation("verified_read_crosses_profile", "test_verified_web_material_cannot_cross_its_profile_run_or_transaction[profile]", STORE,
             "or Path(database).resolve() != self.path):", "or False):"),
    mutation("verified_read_without_atomic_transaction", "test_verified_web_material_cannot_cross_its_profile_run_or_transaction[transaction]", STORE,
             "not conn.in_transaction or self.run_id != run_id", "False or self.run_id != run_id"),
    mutation("source_index_not_rechecked", "test_validated_web_read_rechecks_its_binding_inside_the_transaction[source_added]", STORE,
             "if LifecycleWebStore._review_binding(conn, run_id) != self.binding:",
             "if LifecycleWebStore._review_binding(conn, run_id)[:4] + LifecycleWebStore._review_binding(conn, run_id)[5:] != self.binding[:4] + self.binding[5:]:"),
    mutation("validation_race_not_detected", "test_page_rewrite_with_unchanged_digest_cannot_reuse_a_verified_read[during_validation]", STORE,
             "            read.on_connection(conn, run_id)\n", "            pass\n"),
    mutation("central_approval_reloads_full_sources", "test_attended_web_source_validation_leaves_other_profile_writers_available[confirm-decode]", REVIEW,
             "_caller_transaction=True, web_read=web_read)\n                transition_id", "_caller_transaction=True, web_read=None)\n                transition_id"),
    mutation("validation_permission_recheck_moved_under_lock", "test_permission_is_rechecked_after_expensive_source_validation", REVIEW,
             "    web_read = LifecycleWebStore(service.profile_db_path).validated_read(run_id)\n    before_write()\n",
             "    web_read = LifecycleWebStore(service.profile_db_path).validated_read(run_id)\n"),
)}


if __name__ == "__main__":
    verifier.main()
