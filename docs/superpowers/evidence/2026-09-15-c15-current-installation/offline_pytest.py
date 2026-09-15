"""C15 focused-test runner; synthetic state and no external services."""

import json
import os
from pathlib import Path
import sqlite3
import sys


def audit(event, args):
    if event in {"socket.connect", "socket.sendto", "socket.getaddrinfo",
                 "socket.gethostbyname", "socket.gethostbyaddr"}:
        raise PermissionError("C15 tests prohibit network access")
    if event == "subprocess.Popen":
        executable, argv = args[:2]
        if Path(os.fsdecode(executable)).name in {"codex", "claude"}:
            raise PermissionError("C15 tests prohibit provider CLI execution")


def main():
    sys.addaudithook(audit)
    root = Path(os.environ["C15_SOURCE_ROOT"])
    work = Path(os.environ["ARKSCOPE_OFFLINE_TEST_WORKSPACE"])
    os.chdir(root)
    sys.path.insert(0, str(root))
    for key, leaf in {
        "HOME": "home", "XDG_CONFIG_HOME": "home/config",
        "XDG_CACHE_HOME": "home/cache", "ARKSCOPE_LOCK_DIR": "state/locks",
    }.items():
        path = work / leaf
        path.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(path)
    for key, leaf in {
        "ARKSCOPE_PROFILE_DB": "profile.db", "ARKSCOPE_MARKET_DB": "market.db",
        "ARKSCOPE_SA_DB": "sa.db", "ARKSCOPE_MACRO_CALENDAR_DB": "macro.db",
        "ARKSCOPE_TOKEN_STORE_PATH": "tokens.json",
    }.items():
        os.environ[key] = str(work / "state" / leaf)
    with sqlite3.connect(":memory:") as conn:
        identity = {
            "python": sys.executable, "python_version": sys.version,
            "engine": conn.execute("SELECT sqlite_version(),sqlite_source_id()").fetchone(),
            "compile_options": sorted(row[0] for row in conn.execute("PRAGMA compile_options")),
            "ld_library_path": os.environ.get("LD_LIBRARY_PATH"),
            "ld_preload": os.environ.get("LD_PRELOAD"),
            "source_root": str(root), "argv": sys.argv[1:],
        }
    assert identity["engine"][0] == os.environ["PROBE_EXPECT_SQLITE"]
    assert identity["ld_library_path"] is identity["ld_preload"] is None
    (work / "runtime.json").write_text(json.dumps(identity, indent=2) + "\n")
    from src import env_keys
    env_keys._loaded = True
    import pytest
    return pytest.main([
        "-p", "no:cacheprovider", "-p", "anyio.pytest_plugin", "--tb=short",
        f"--basetemp={work / 'pytest'}", f"--junitxml={work / 'pytest.xml'}",
        *sys.argv[1:],
    ])


if __name__ == "__main__":
    raise SystemExit(main())
