"""In-memory controls in a credential-free network namespace."""

import ast
import errno
import inspect
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest


class Mutation:
    def __init__(self, mode):
        self.mode = mode
        self.failures = []

    def pytest_runtest_logreport(self, report):
        if report.failed:
            self.failures.append(report.nodeid)

    def pytest_collection_finish(self):
        from src import security_lifecycle_provider_authority as authority
        if self.mode == "baseline":
            return
        if self.mode == "review_only":
            authority._automatic_continuation_issues = lambda decision: ("provider_continuation_review",)
        elif self.mode == "ignore_readiness":
            authority._automatic_continuation_issues = lambda decision: ()
        elif self.mode == "ignore_successor_conflict":
            original = authority._continuation
            tree = ast.parse(inspect.getsource(original))
            body = tree.body[0].body
            removed = [node for node in body if isinstance(node, ast.If)
                       and '"inactive"' in ast.unparse(node.test).replace("'", '"')]
            assert len(removed) == 1
            tree.body[0].body = [node for node in body if node not in removed]
            namespace = {}
            exec(compile(ast.fix_missing_locations(tree), original.__code__.co_filename, "exec"),
                 original.__globals__, namespace)
            authority._continuation = namespace[original.__name__]
        elif self.mode == "skip_transaction_gate":
            original = authority.provider_transition_guard
            tree = ast.parse(inspect.getsource(original))
            replacements = [node for node in ast.walk(tree) if isinstance(node, ast.Return)
                            and isinstance(node.value, ast.Call)
                            and isinstance(node.value.func, ast.Name)
                            and node.value.func.id == "_automatic_continuation_issues"]
            assert len(replacements) == 1
            replacements[0].value = ast.Tuple(elts=[], ctx=ast.Load())
            namespace = {}
            exec(compile(ast.fix_missing_locations(tree), original.__code__.co_filename, "exec"),
                 original.__globals__, namespace)
            authority.provider_transition_guard.__code__ = namespace[original.__name__].__code__
        elif self.mode == "skip_successor_material":
            from src.security_lifecycle_provider_store import ProviderCheckStore
            ProviderCheckStore.current_material = classmethod(lambda cls, conn, row, at:
                (tuple(authority.evidence_dict(item) for item in row["evidence"]), tuple(row["blockers"])))
        elif self.mode == "drop_provider_codes":
            from dataclasses import replace
            from src.security_lifecycle_provider_store import ProviderCheckStore
            original = ProviderCheckStore.bundle

            def without_codes(self, *args, **kwargs):
                return replace(original(self, *args, **kwargs), provider_codes=())

            ProviderCheckStore.bundle = without_codes
        elif self.mode == "reactivate_membership":
            from src import ticker_identity_transition as transitions
            transitions._automatic_membership_guard = lambda *args, **kwargs: ()
        elif self.mode == "prefer_obsolete_pending":
            from src import security_lifecycle_current as current
            current._current_action_transitions = lambda transitions, material: transitions
        elif self.mode == "keep_recovered_error":
            from src.security_lifecycle_provider_store import ProviderCheckStore
            original = ProviderCheckStore.current_material

            def keep_error(cls, conn, row, *, at):
                material, codes = original(conn, row, at=at)
                if "successor_listing_provider_error" in row["blockers"]:
                    codes = (*codes, "successor_listing_provider_error")
                return material, codes

            ProviderCheckStore.current_material = classmethod(keep_error)
        else:
            raise ValueError("unknown mutation")


if __name__ == "__main__":
    if sys.argv[1] != "--worker":
        env = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL"}}
        command = [shutil.which("unshare"), "--user", "--map-root-user", "--net", sys.executable,
                   str(Path(__file__).resolve()), "--worker", sys.argv[1]]
        raise SystemExit(subprocess.run(command, cwd=Path(__file__).resolve().parents[4], env=env).returncode)
    subprocess.run([shutil.which("ip"), "link", "set", "lo", "up"], check=True)
    with socket.socket() as probe:
        assert probe.connect_ex(("192.0.2.1", 443)) == errno.ENETUNREACH
    mode = sys.argv[2]
    owner_names = {
        "baseline": (),
        "review_only": ("test_exact_current_rename_requests_the_existing_transition_with_event_date",),
        "ignore_readiness": ("test_historical_rename_stays_available_for_attended_review_only",),
        "ignore_successor_conflict": ("test_successor_active_inactive_conflict_cannot_establish_continuity",),
        "skip_transaction_gate": ("test_transaction_guard_independently_rejects_incomplete_automatic_rename",),
        "skip_successor_material": ("test_real_scan_carries_the_successor_directory_observation_without_extra_requests",
                                    "test_successor_observation_is_rechecked_inside_the_apply_transaction"),
        "drop_provider_codes": ("test_independently_stored_successor_conflict_blocks_automatic_rename[provider_error]",),
        "reactivate_membership": ("test_automation_preflight_blocks_archived_successor_membership",
                                  "test_preexisting_automatic_approval_cannot_reactivate_successor"),
        "prefer_obsolete_pending": ("test_applied_rollover_replaces_obsolete_pending_projection_without_losing_receipts",),
        "keep_recovered_error": ("test_successor_recovery_clears_derived_error_without_rewriting_old_receipt",),
    }
    mutation = Mutation(mode)
    code = pytest.main(["-q", "tests/test_security_lifecycle_automatic_rename.py",
                       "tests/test_security_lifecycle_successor_evidence.py",
                       "tests/test_security_lifecycle_automatic_rename_suppression.py",
                       "tests/test_security_lifecycle_policy_rollover.py", "--tb=line"],
                       plugins=[mutation])
    expected = pytest.ExitCode.OK if mode == "baseline" else pytest.ExitCode.TESTS_FAILED
    owned = all(any(owner in node for node in mutation.failures) for owner in owner_names[mode])
    print(json.dumps(dict(mutation=mode, observed=int(code), expected=int(expected),
                          named_owners_failed=owned, failed=mutation.failures)))
    raise SystemExit(0 if code == expected and owned else 1)
