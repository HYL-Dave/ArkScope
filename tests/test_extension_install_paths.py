"""Pin: SA extension installers must reference a host script that exists.

The Firefox/Chrome native-messaging manifests point at a stable launcher
outside the repo; the launcher resolves the actual host script from
~/.config/arkscope/sa_native_host.json, which the install scripts write.
If the host script moves without updating the installers, a fresh install
registers a dead path and every extension message fails at spawn time.
These tests parse the paths out of the shell sources so they stay valid
no matter where the host script lives.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXT_DIR = REPO_ROOT / "extensions" / "sa_alpha_picks"


def _extract(pattern: str, path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(pattern, text)
    assert match, f"expected pattern {pattern!r} in {path.name}; installer layout changed"
    return match.group(1)


@pytest.mark.parametrize(
    "script_name, pattern",
    [
        ("install.sh", r'HOST_PATH="\$PROJECT_ROOT/([^"]+)"'),
        ("install_firefox.sh", r'HOST_SCRIPT="\$PROJECT_ROOT/([^"]+)"'),
        (
            "native_host_launcher.sh",
            r'cfg\.get\("project_root", ""\) \+ "/([^"]+)"',
        ),
    ],
)
def test_installer_host_script_path_exists(script_name, pattern):
    rel = _extract(pattern, EXT_DIR / script_name)
    target = REPO_ROOT / rel
    assert target.is_file(), (
        f"{script_name} references {rel}, which does not exist in the repo; "
        "update the installer to the host script's current location"
    )
