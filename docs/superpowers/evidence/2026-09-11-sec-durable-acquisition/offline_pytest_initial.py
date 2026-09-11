"""Disposable offline test runner, copied from the preceding reviewed batch."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(os.environ.get("ARKSCOPE_OFFLINE_TEST_WORKSPACE", str(Path(__file__).resolve().parent)))
MAIN = Path("/mnt/md0/PycharmProjects/ArkScope")
FIXTURES = WORK / "pytest"


def _audit(event, args):
    if event in {"open", "sqlite3.connect"} and args:
        raw = args[0]
        if isinstance(raw, (str, bytes, os.PathLike)):
            value = os.fsdecode(raw)
            if value.startswith("file:"):
                value = value[5:].split("?", 1)[0]
            path = Path(value).resolve()
            if path.is_relative_to(MAIN / "data") or path == MAIN / "config/.env":
                raise PermissionError("offline test rejected production data access")
    if event in {"socket.connect", "socket.sendto", "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"}:
        address = args[1] if event in {"socket.connect", "socket.sendto"} else args[0]
        host = address[0] if isinstance(address, tuple) else address
        if host not in {"127.0.0.1", "::1", "localhost", None}:
            raise PermissionError("offline test rejected provider network")
    if event == "subprocess.Popen":
        executable, argv = args[:2]
        path = Path(os.fsdecode(executable))
        fixture = path.is_absolute() and path.resolve().is_relative_to(FIXTURES)
        if path.name in {"codex", "claude"} and not fixture and "--version" not in argv:
            raise PermissionError("offline test rejected real provider CLI session")


sys.addaudithook(_audit)

if __name__ == "__main__":
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    for name, leaf in {
        "HOME": "home", "XDG_CONFIG_HOME": "home/config", "XDG_CACHE_HOME": "home/cache",
        "ARKSCOPE_LOCK_DIR": "state/locks",
    }.items():
        path = WORK / leaf
        path.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(path)
    for name, leaf in {
        "ARKSCOPE_PROFILE_DB": "profile.db", "ARKSCOPE_MARKET_DB": "market.db",
        "ARKSCOPE_SA_DB": "sa.db", "ARKSCOPE_MACRO_CALENDAR_DB": "macro.db",
        "ARKSCOPE_TOKEN_STORE_PATH": "tokens.json",
    }.items():
        os.environ[name] = str(WORK / "state" / leaf)
    from src import env_keys
    env_keys._loaded = True
    import pytest
    raise SystemExit(pytest.main(["-p", "no:cacheprovider", "-p", "anyio.pytest_plugin",
        "--tb=short", f"--basetemp={FIXTURES}", *sys.argv[1:]]))
