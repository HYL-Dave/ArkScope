"""In-memory negative controls after pytest's production-store isolation."""
import errno
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))


class Mutation:
    def __init__(self, mode):
        self.mode = mode

    def pytest_collection_finish(self):
        if self.mode == "ambient_auth":
            from src.auth_drivers import runtime_binding
            runtime_binding.pinned_auth_headers = lambda provider, secret: {}
        elif self.mode == "lost_reauth_code":
            from src.api.routes import analysis_cards
            analysis_cards.SubscriptionStructuredOutputError = type("UnmatchedError", (RuntimeError,), {})
        elif self.mode != "baseline":
            raise ValueError("unknown mutation")


def main():
    if sys.argv[1] != "--worker":
        env = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "LANG", "LC_ALL"}}
        return subprocess.run([shutil.which("unshare"), "--user", "--map-root-user", "--net",
                               sys.executable, str(Path(__file__).resolve()), "--worker", sys.argv[1]],
                              cwd=ROOT, env=env).returncode
    subprocess.run([shutil.which("ip"), "link", "set", "lo", "up"], check=True)
    with socket.socket() as probe:
        assert probe.connect_ex(("192.0.2.1", 443)) == errno.ENETUNREACH
    mode = sys.argv[2]
    files = ["tests/test_chatgpt_oauth_wire_auth.py", "tests/test_card_execution_authority.py"]
    selected = "wire_uses_only_selected or auth_failure_survives"
    result = pytest.main(["-q", *files, "-k", selected, "--tb=line"], plugins=[Mutation(mode)])
    expected = pytest.ExitCode.OK if mode == "baseline" else pytest.ExitCode.TESTS_FAILED
    print(f"mutation={mode} pytest_exit={result} expected={expected}", flush=True)
    return 0 if result == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
