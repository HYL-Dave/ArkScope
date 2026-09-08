"""Source-bound whole-focus mutations and complete offline regression suites."""

import importlib.util
import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET


PACKET = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("source_context_verifier", PACKET.parent / "2026-09-07-lifecycle-web-runtime/scripts/verify.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
verifier.foundation.ADDED |= {
    "tests/test_lifecycle_public_sources_wire.py", "tests/test_lifecycle_source_compatibility.py",
    "tests/test_lifecycle_source_context.py", "tests/test_lifecycle_source_read_report.py",
}
mutation = verifier.mutation
SOURCE = "src/lifecycle_public_sources.py"
CONTEXT = "src/lifecycle_source_context.py"
STORE = "src/lifecycle_web_store.py"
FINDING = "src/security_lifecycle_web_finding.py"
CONTRACT = "apps/arkscope-web/src/lifecycle/webContract.ts"
VIEW = "apps/arkscope-web/src/lifecycle/LifecycleWebPanel.tsx"

verifier.MUTATIONS = {
    "backend": (
        mutation("normal_close_aborts_response", "test_response_owned_body_survives_connection_close", SOURCE,
                 "                stream.close()\n\n\nclass _SourceTextParser",
                 "                stream.close()\n\n    def close(self):\n        self.abort()\n        super().close()\n\n\nclass _SourceTextParser"),
        mutation("incomplete_body_is_admitted", "test_real_truncated_response_remains_rejected", SOURCE,
                 '        if length is not None and observed["received_body_bytes"] != length:', '        if False:'),
        mutation("conflicting_framing_accepted", "test_ambiguous_framing_is_not_reported_as_a_short_document", SOURCE,
                 'if transfer is not None and (transfer.strip().lower() != "chunked" or length_header is not None):',
                 'if transfer is not None and transfer.strip().lower() != "chunked":'),
        mutation("decoded_size_not_enforced", "test_decoded_size_budget_is_separate_and_never_returns_a_prefix", SOURCE,
                 'if observed["decoded_body_bytes"] > decoded_limit:', 'if False:'),
        mutation("unfinished_compression_accepted", "test_complete_wire_body_does_not_hide_damaged_gzip", SOURCE,
                 'if decoder is not None and not decoder.eof:', 'if False:'),
        mutation("xml_entities_not_rejected", "test_xml_dtd_entities_and_malformed_documents_are_rejected", SOURCE,
                 'forbid_dtd=True, forbid_entities=True, forbid_external=True', 'forbid_dtd=False, forbid_entities=False, forbid_external=False'),
        mutation("xml_mixed_content_collapsed", "test_xml_normalization_preserves_record_boundaries_without_repeating_long_names", SOURCE,
                 'target=C14NWriterTarget(write)', 'target=C14NWriterTarget(write, strip_text=True)'),
        mutation("full_pages_sent_to_model", "test_large_source_is_saved_whole_but_analysis_receives_traceable_passages", CONTEXT,
                 '    if not matched:', '    if True:'),
        mutation("unseen_quotes_accepted", "test_citation_must_have_been_in_model_context_not_merely_stored_page", FINDING,
                 'if contexts is not None and not contexts[citation.source_id].contains(start_byte, end_byte):', 'if False:'),
        mutation("metadata_claims_delisting", "test_json_metadata_cannot_stand_in_for_a_listing_notice", FINDING,
                 'if page.mime_type == "application/json" and any(value != "security_identity" for value in citation.supports):', 'if False:'),
        mutation("null_context_treated_as_legacy", "test_present_but_malformed_journal_context_is_not_treated_as_legacy_full_text", STORE,
                 '            if "source_context" in value:', '            if value.get("source_context"):'),
        mutation("failed_read_receipt_not_saved", "test_all_source_failures_keep_measured_diagnostics_after_journal_reopen", STORE,
                 '            if source_read_report is not None:\n                material = {"failure_source_read_report":',
                 '            if False:\n                material = {"failure_source_read_report":'),
        mutation("failed_receipt_satisfies_adoption", "test_population_retains_failure_receipts_without_accepting_them_as_findings",
                 "src/security_lifecycle_population.py", '                   or runs[row["run_id"]]["status"] != "succeeded"\n', ''),
        mutation("old_source_cap_restored", "test_source_capacity_is_separate_from_model_tokens_and_bound_to_confirmation",
                 "src/lifecycle_web_preflight.py", 'max_source_bytes=16 * 1024 * 1024', 'max_source_bytes=2 * 1024 * 1024'),
    ),
    "frontend": (
        mutation("source_coverage_shape_ignored", "keeps legacy source coverage unknown but validates every new coverage field", CONTRACT,
                 'source_reading: row.source_reading === undefined ? null : nullable(row.source_reading, sourceReading),',
                 'source_reading: row.source_reading as any,'),
        mutation("source_read_shape_ignored", "reads bounded source diagnostics without accepting header blobs or fake counts", CONTRACT,
                 'source_reads: row.source_reads === undefined ? null : nullable(row.source_reads, (x) => list(x, sourceRead)),',
                 'source_reads: row.source_reads as any,'),
        mutation("selected_source_disclosure_hidden", "shows selected context honestly without claiming the model read the complete source", VIEW,
                 'run.source_reading.selected_sources > 0', 'run.source_reading.selected_sources > 999'),
    ),
}


def test_run(python, source, output, temp_root, name, files):
    # The full suite previously needed >600 s under concurrent verification.
    # This is a harness deadline, not an application/provider timeout change.
    xml = output / f"{name}.xml"
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}}
    env.update(PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE="1", ARKSCOPE_DISABLE_SCHEDULER="1")
    started = time.monotonic()
    result = subprocess.run([python, "-m", "pytest", "-q", *files, f"--junitxml={xml}", f"--basetemp={temp_root / name}"],
                            cwd=source, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            timeout=1200 if files == ["tests"] else 600)
    (output / f"{name}.log").write_text(result.stdout)
    suites = ET.parse(xml).getroot().findall("testsuite")
    failures = [f'{case.attrib["classname"]}::{case.attrib["name"]}' for suite in suites for case in suite.findall("testcase")
                if case.find("failure") is not None or case.find("error") is not None]
    return {"name": name, "exit_code": result.returncode,
            "counts": {key: sum(int(s.attrib.get(key, 0)) for s in suites) for key in ("tests", "failures", "errors", "skipped")},
            "failed_nodes": failures, "duration_seconds": round(time.monotonic() - started, 3)}


verifier.backend.test_run = test_run


if __name__ == "__main__":
    verifier.main()
