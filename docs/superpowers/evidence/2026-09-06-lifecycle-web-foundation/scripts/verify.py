"""Verify the offline Web foundation in a private, source-only copy."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


PACKET = Path(__file__).resolve().parent.parent
PRIOR = PACKET.parent / "2026-09-06-lifecycle-current-review"
spec = importlib.util.spec_from_file_location(
    "web_foundation_test_runner",
    PACKET.parent / "2026-09-06-recent-price-repair/scripts/run_mutations.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
CONTRACT = "src/security_lifecycle_web_contract.py"
SOURCES = "src/lifecycle_public_sources.py"
ADDED = {
    "tests/test_security_lifecycle_web_contract.py", "tests/test_lifecycle_public_sources.py",
    "tests/test_auth_drivers.py", "tests/test_chatgpt_oauth_driver.py",
    "tests/test_claude_code_sdk_driver.py", "tests/test_subscription_structured_output.py",
    "tests/test_codex_app_server_runtime.py", "tests/test_codex_translation_adapter.py",
    "tests/test_model_capabilities.py", "tests/test_web_tools.py",
}


def mutation(name, owner, path, before, after):
    return {"name": name, "owner": owner, "path": path, "before": before, "after": after}


MUTATIONS = (
    mutation("oauth_becomes_api", "test_all_four_web_channels_have_explicit_transport_without_default", CONTRACT,
             'ChannelContract("openai", "chatgpt_oauth", "codex_app_server", None)',
             'ChannelContract("openai", "chatgpt_oauth", "openai_responses", None)'),
    mutation("unknown_auth_falls_back", "test_all_four_web_channels_have_explicit_transport_without_default", CONTRACT,
             '    if result is None:\n        raise WebContractError("web_auth_unsupported")',
             '    if result is None:\n        return _CHANNELS[("openai", "api_key")]'),
    mutation("private_input_accepted", "test_private_or_instruction_fields_cannot_enter_public_question", CONTRACT,
             'ConfigDict(extra="forbid", frozen=True, strict=True)',
             'ConfigDict(extra="allow", frozen=True, strict=True)'),
    mutation("model_admission_ignored", "test_web_admission_does_not_resurrect_or_expand_models", CONTRACT,
             '    if detail is not None:\n        raise WebContractError(detail["code"])',
             '    if False:\n        raise WebContractError(detail["code"])'),
    mutation("retired_route_admitted", "test_web_admission_owns_existing_research_capability_boundary", CONTRACT,
             'if capability.task_route_status != "current":', 'if False:'),
    mutation("missing_research_capability_admitted", "test_web_admission_owns_existing_research_capability_boundary", CONTRACT,
             'if not task_capability_ok("ai_research", capability):', 'if False:'),
    mutation("changed_billing_accepted", "test_terminal_cannot_change_selected_model_auth_or_billing", CONTRACT,
             'if selection != self.selection:', 'if False:'),
    mutation("interrupt_ack_is_terminal", "test_local_cleanup_and_interrupt_ack_do_not_prove_remote_cancelled", CONTRACT,
             'self._bound_call(call_id, remote_id).interrupt_ack = True',
             'self._bound_call(call_id, remote_id).terminal = "interrupted"'),
    mutation("cleanup_is_terminal", "test_unknown_dispatch_id_stays_unknown_and_is_not_retried", CONTRACT,
             'self._call(call_id).transport_lost = True', 'self._call(call_id).terminal = "cancelled"'),
    mutation("stop_allows_more_spending", "test_stop_before_dispatch_is_cancelled_without_model_call", CONTRACT,
             '            if self._stop_requested:\n                raise WebContractError("stop_requested")',
             '            if False:\n                raise WebContractError("stop_requested")'),
    mutation("failed_call_can_retry", "test_failed_model_request_cannot_be_followed_by_implicit_retry", CONTRACT,
             'if any(call.terminal != "completed" for call in self._calls.values()):', 'if False:'),
    mutation("mixed_private_dns_allowed", "test_dns_with_any_nonpublic_address_cannot_connect", SOURCES,
             'or proto != socket.IPPROTO_TCP or not _public_address(endpoint[0])',
             'or proto != socket.IPPROTO_TCP'),
    mutation("dns_wait_ignores_stop_and_deadline", "test_blocked_dns_releases_caller_without_late_http", SOURCES,
             'while not completed.wait(min(0.05, self._remaining())):', 'while not completed.wait():'),
    mutation("dns_saturation_ignored", "test_dns_saturation_refuses_new_resolution_without_waiting", SOURCES,
             'if not slots.acquire(blocking=False):', 'if False:'),
    mutation("connection_resolves_host_again", "test_pinned_https_transport_does_not_resolve_host_again", SOURCES,
             'raw.connect(endpoint)', 'raw.connect((self.host, 443))'),
    mutation("tls_verifies_ip_not_host", "test_pinned_https_transport_does_not_resolve_host_again", SOURCES,
             'server_hostname=self.host, do_handshake_on_connect=False',
             'server_hostname=endpoint[0], do_handshake_on_connect=False'),
    mutation("deadline_does_not_interrupt", "test_deadline_interrupts_an_inflight_read_not_only_its_return", SOURCES,
             '                timer.start()', '                pass'),
    mutation("cancel_leaves_reader_alive", "test_cancel_interrupts_an_inflight_read_and_refuses_next_hop", SOURCES,
             '                self._active_connection.abort()', '                pass'),
    mutation("oversize_source_accepted", "test_byte_limit_never_silently_truncates_even_without_content_length", SOURCES,
             'if len(body) > self.limits.max_response_bytes:', 'if False:'),
    mutation("invented_quote_accepted", "test_exact_passage_requires_real_source_and_byte_aligned_unicode", SOURCES,
             'if not excerpt.strip() or excerpt != expected_text:', 'if not excerpt.strip():'),
    mutation("source_metadata_not_bound", "test_citation_cannot_rebind_captured_source_metadata", SOURCES,
             'if not isinstance(page, PublicSourcePage) or page.capture_sha256 != _capture_digest(page):',
             'if not isinstance(page, PublicSourcePage):'),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--temp-root", type=Path, required=True)
    args = parser.parse_args()
    repo, staging, temporary = args.repo.resolve(), args.staging.resolve(), args.temp_root.resolve()
    if any(path.exists() or path == repo or repo in path.parents for path in (staging, temporary)):
        raise RuntimeError("verification_needs_new_external_directories")
    os.umask(0o077)
    source, output = staging / "source", staging / "results"
    source.mkdir(parents=True)
    output.mkdir()
    temporary.mkdir(parents=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=repo,
    ).decode().split("\0")
    copied = []
    for name in sorted(set(names) - {""}):
        path = Path(name)
        if (path.parts[0] == "data" or path.name in {".env", "CLAUDE.md", ".mcp.json"}
                or ".claude" in path.parts or not (repo / path).is_file()):
            continue
        target = source / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / path, target)
        copied.append(name)
    if (repo / "node_modules").exists():
        (source / "node_modules").symlink_to(repo / "node_modules", target_is_directory=True)
    focus = sorted(set(json.loads((PRIOR / "focus-files.json").read_text())["files"]) | ADDED)
    integration = sorted(set(json.loads((PRIOR / "integration-files.json").read_text())["files"]) | ADDED)
    if any(not (source / name).is_file() for name in focus + integration):
        raise RuntimeError("verification_test_file_missing")
    binding = {name for name in copied if not name.startswith("docs/")}
    hashes = {name: digest(source / name) for name in sorted(binding)}
    report = {"complete": False, "scope": "offline_common_contract_and_source_reader_not_runtime_admission",
              "head": head, "source_sha256": hashes, "focus": focus, "integration": integration, "mutations": []}

    def run(name, files):
        result = runner.test_run(sys.executable, source, output, temporary, name, files)
        print(json.dumps({"event": name, **result}), flush=True)
        return result

    report["baseline"] = run("baseline", focus)
    save(output / "report.json", report)
    if report["baseline"]["exit_code"]:
        raise RuntimeError("baseline_failed")
    for item in MUTATIONS:
        target = source / item["path"]
        original = target.read_bytes()
        try:
            content = original.decode()
            if content.count(item["before"]) != 1:
                raise RuntimeError("mutation_anchor_changed")
            target.write_text(content.replace(item["before"], item["after"], 1))
            result = run(item["name"], focus)
        finally:
            target.write_bytes(original)
        result.update(owner=item["owner"], edits=item, restored_sha256=digest(target))
        result["killed_by_owner"] = (
            result["exit_code"] == 1 and result["counts"]["errors"] == 0
            and result["counts"]["tests"] == report["baseline"]["counts"]["tests"]
            and any(item["owner"] in node for node in result["failed_nodes"])
        )
        report["mutations"].append(result)
        save(output / "report.json", report)
        if not result["killed_by_owner"] or digest(target) != hashes[item["path"]]:
            raise RuntimeError("mutation_not_owned_or_not_restored")
    report["restored"] = run("restored", focus)
    report["integration_result"] = run("integration", integration)
    save(output / "report.json", report)
    if report["restored"]["exit_code"] or report["integration_result"]["exit_code"]:
        raise RuntimeError("restored_or_integration_failed")
    if head != subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip():
        raise RuntimeError("source_head_changed")
    if any(digest(source / name) != value or digest(repo / name) != value for name, value in hashes.items()):
        raise RuntimeError("source_changed")
    report["complete"] = True
    save(output / "report.json", report)


if __name__ == "__main__":
    main()
