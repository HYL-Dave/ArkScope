"""Run acceptance in a Linux network namespace with no external interfaces.

This is a verification harness, not the product's Python-execution sandbox.
Only loopback is enabled for local HTTP fixtures; provider credentials are not
inherited. Requires the host's unshare and ip utilities.
"""

import errno
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[4]


def main():
    args = sys.argv[1:]
    if not args or args[0] != "--worker":
        environment = {key: value for key, value in os.environ.items()
                       if key in {"PATH", "HOME", "LANG", "LC_ALL", "PYTHONPATH", "TMPDIR"}}
        command = [shutil.which("unshare"), "--user", "--map-root-user", "--net",
                   sys.executable, str(Path(__file__).resolve()), "--worker", *args]
        return subprocess.run(command, cwd=ROOT, env=environment, check=False).returncode

    subprocess.run([shutil.which("ip"), "link", "set", "lo", "up"], check=True)
    interfaces = [name for _, name in socket.if_nameindex()]
    if interfaces != ["lo"]:
        raise RuntimeError("unexpected_network_interface")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1)
        result = probe.connect_ex(("192.0.2.1", 443))
    if result != errno.ENETUNREACH:
        raise RuntimeError("external_route_not_blocked")
    print(json.dumps({"interfaces": interfaces, "external_probe": "ENETUNREACH",
                      "inherited_credentials": False}), flush=True)
    mode, *rest = args[1:]
    if mode == "pytest":
        command = [sys.executable, "-m", "pytest", *rest]
    elif mode == "mutation":
        command = [sys.executable, str(Path(__file__).with_name("mutation_check.py")), *rest]
    else:
        raise ValueError("offline_check_mode")
    os.execv(sys.executable, command)


if __name__ == "__main__":
    raise SystemExit(main())
