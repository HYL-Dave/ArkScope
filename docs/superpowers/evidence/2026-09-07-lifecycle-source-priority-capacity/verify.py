"""Whole-focus owners for source priorities, bounded memory and short commits."""

import importlib.util
from pathlib import Path


PACKET = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("capacity_prior_verifier", PACKET.parent / "2026-09-07-lifecycle-source-context/verify.py")
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
verifier = prior.verifier
verifier.foundation.ADDED.update({"tests/test_lifecycle_source_capacity.py", "tests/test_lifecycle_source_progress.py"})
mutation = verifier.mutation
SOURCE = "src/lifecycle_public_sources.py"
STORE = "src/lifecycle_web_store.py"
CONTEXT = "src/lifecycle_source_context.py"
PIPELINE = "src/security_lifecycle_web_pipeline.py"

retained = tuple(item for item in verifier.MUTATIONS["backend"] if item["name"] in {
    "incomplete_body_is_admitted", "decoded_size_not_enforced", "unfinished_compression_accepted",
    "full_pages_sent_to_model", "unseen_quotes_accepted", "failed_read_receipt_not_saved",
})
verifier.MUTATIONS["backend"] = retained + (
    mutation("sec_required_for_search", "test_search_priority_follows_the_tracking_question_not_a_mandatory_sec_hop",
             "src/security_lifecycle_web_contract.py", "SEC is supplementary, not a required source.", "SEC is a required source."),
    mutation("sec_required_for_analysis", "test_all_four_channels_share_source_reading_and_finding_validation",
             PIPELINE, "SEC is supplementary, not a required source;", "SEC is a required source;"),
    mutation("old_wire_capacity", "test_source_capacity_is_separate_from_model_tokens_and_bound_to_confirmation",
             "src/lifecycle_web_preflight.py", "max_source_bytes=32 * 1024 * 1024", "max_source_bytes=16 * 1024 * 1024"),
    mutation("old_decoded_capacity", "test_source_capacity_is_separate_from_model_tokens_and_bound_to_confirmation",
             "src/lifecycle_web_preflight.py", "max_decoded_source_bytes=128 * 1024 * 1024", "max_decoded_source_bytes=32 * 1024 * 1024"),
    mutation("old_shared_read_deadline", "test_source_capacity_is_separate_from_model_tokens_and_bound_to_confirmation",
             "src/lifecycle_web_preflight.py", "source_timeout_seconds=180", "source_timeout_seconds=45"),
    mutation("monolithic_capture_hash", "test_large_page_hash_never_serializes_the_whole_source_at_once", SOURCE,
             "    return _page_material_digest(material)",
             '    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()'),
    mutation("hash_chunk_dropped", "test_streamed_page_fingerprints_are_byte_identical_to_legacy_json", SOURCE,
             "range(0, len(value), 65536)", "range(0, max(0, len(value) - 65536), 65536)"),
    mutation("source_json_escape_expansion", "test_unicode_source_journal_avoids_escape_expansion_without_changing_old_digests", STORE,
             "_json(material, ensure_ascii=False)", "_json(material, ensure_ascii=True)"),
    mutation("page_hash_not_checked", "test_source_journal_still_rejects_changed_page_and_capture_fingerprints[page_sha256]", STORE,
             'if _page_material_digest(material) != row["page_sha256"]:', 'if False:'),
    mutation("capture_hash_not_checked", "test_source_journal_still_rejects_changed_page_and_capture_fingerprints[capture_sha256]", STORE,
             "if _capture_digest(page) != page.capture_sha256:", "if False:"),
    mutation("validation_holds_write_lock", "test_final_source_validation_does_not_block_heartbeat_or_cancellation", STORE,
             '        finding = validate_finding(PublicInvestigationInput.model_validate(header["request"]), payload, pages,\n'
             '                                   unread_source_count=len(source_failures), source_context=source_context)',
             '        with self.connection(write=True):\n'
             '            finding = validate_finding(PublicInvestigationInput.model_validate(header["request"]), payload, pages,\n'
             '                                       unread_source_count=len(source_failures), source_context=source_context)'),
    mutation("decode_holds_read_lock", "test_final_source_decoding_does_not_keep_a_read_transaction_open", STORE,
             '            if saved is None or saved["page_sha256"] != digest:\n'
             '                raise WebJournalError("web_journal_integrity")\n'
             '            pages[source_id] = self._decode_page(saved)',
             '                if saved is None or saved["page_sha256"] != digest:\n'
             '                    raise WebJournalError("web_journal_integrity")\n'
             '                pages[source_id] = self._decode_page(saved)'),
    mutation("changed_source_index_accepted", "test_changed_source_snapshot_cannot_commit_a_previously_validated_finding", STORE,
             'if current_index != source_index or current["header_sha256"] != before["header_sha256"]:',
             'if current["header_sha256"] != before["header_sha256"]:'),
    mutation("cancel_at_commit_ignored", "test_final_source_validation_does_not_block_heartbeat_or_cancellation[True]", STORE,
             "current, _, current_index = self._completion_state(conn, run_id, owner)",
             "current, current_index = before, source_index"),
    mutation("full_context_copied", "test_full_context_reuses_the_retained_text_without_a_second_source_copy", CONTEXT,
             '"text": page.text if full_text else encoded[start:end].decode("utf-8")',
             '"text": page.text.encode("utf-8").decode("utf-8") if full_text else encoded[start:end].decode("utf-8")'),
    mutation("model_json_escape_expansion", "test_unicode_analysis_keeps_exact_text_without_ascii_escape_expansion", PIPELINE,
             'json.dumps(material, ensure_ascii=False, separators=(",", ":"))',
             'json.dumps(material, ensure_ascii=True, separators=(",", ":"))'),
    mutation("progress_loads_full_sources", "test_progress_poll_does_not_decode_running_source_bodies[controller]",
             "src/lifecycle_web_controller.py", "self.store.read(identity, include_running_sources=False)", "self.store.read(identity)"),
    mutation("current_view_loads_full_sources", "test_progress_poll_does_not_decode_running_source_bodies[current_review]",
             "src/lifecycle_web_projection.py", "row[0], include_running_sources=False", "row[0], include_running_sources=True"),
    mutation("result_read_validation_holds_lock", "test_source_read_validation_releases_its_owned_read_transaction", STORE,
             "        return self._read_material(row, header, calls, saved, pages)",
             '        with self.connection() as conn:\n'
             '            conn.execute("SELECT run_id FROM lifecycle_web_runs").fetchall()\n'
             '            return self._read_material(row, header, calls, saved, pages)'),
    mutation("source_cursor_holds_lock", "test_connection_reader_does_not_hold_page_cursor_during_decoding", STORE,
             '        pages = {}\n'
             '        for source_id, digest in cls._source_index(conn, run_id):\n'
             '            saved = conn.execute("SELECT * FROM lifecycle_web_pages WHERE run_id=? AND source_id=?", (run_id, source_id)).fetchone()\n'
             '            if saved is None or saved["page_sha256"] != digest:\n'
             '                raise WebJournalError("web_journal_integrity")\n'
             '            pages[source_id] = cls._decode_page(saved)\n'
             '            del saved\n'
             '        return pages',
             '        return {row["source_id"]: cls._decode_page(row)\n'
             '                for row in conn.execute("SELECT * FROM lifecycle_web_pages WHERE run_id=? ORDER BY source_id", (run_id,))}'),
    mutation("terminal_progress_skips_source_integrity", "test_terminal_progress_read_still_validates_source_integrity", STORE,
             '        pages = (self._read_pages(run_id, source_index)\n'
             '                 if include_running_sources or row["status"] not in RUNNING else {})',
             '        pages = self._read_pages(run_id, source_index) if include_running_sources else {}'),
    mutation("journal_wait_too_short", "test_web_journal_wait_preserves_owner_cancellation_and_failure[commit]", STORE,
             "JOURNAL_BUSY_SECONDS = 45", "JOURNAL_BUSY_SECONDS = 5"),
    mutation("journal_wait_exceeds_lease", "test_web_journal_wait_is_bounded_below_the_unchanged_lease", STORE,
             "JOURNAL_BUSY_SECONDS = 45", "JOURNAL_BUSY_SECONDS = 600"),
)
verifier.MUTATIONS["frontend"] = verifier.MUTATIONS["frontend"] + (
    mutation("receipt_timeout_too_short", "accepts a slow verified local result without retrying or starting another investigation",
             "apps/arkscope-web/src/api.ts", "const LIFECYCLE_RECEIPT_TIMEOUT_MS = 180_000;", "const LIFECYCLE_RECEIPT_TIMEOUT_MS = 60_000;"),
    mutation("receipt_timeout_unbounded", "still bounds a stalled receipt read and never retries it",
             "apps/arkscope-web/src/api.ts", "const LIFECYCLE_RECEIPT_TIMEOUT_MS = 180_000;", "const LIFECYCLE_RECEIPT_TIMEOUT_MS = 600_000;"),
    mutation("receipt_budget_leaks_to_general_requests", "does not increase the unrelated dispatch/default request budget",
             "apps/arkscope-web/src/api.ts", "const DEFAULT_TIMEOUT_MS = 15_000;", "const DEFAULT_TIMEOUT_MS = 60_000;"),
)


if __name__ == "__main__":
    verifier.main()
