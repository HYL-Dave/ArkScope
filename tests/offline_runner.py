"""Frozen regression entrypoint with private state and no external networking."""

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
WORK = Path(os.environ["ARKSCOPE_VERIFICATION_WORK"]).resolve()
FIXTURES = WORK / "pytest-temp"
FORBIDDEN = Path(os.environ["ARKSCOPE_FORMAL_DATA"]).resolve()


def audit(event, args):
    if event in {"socket.connect", "socket.sendto", "socket.getaddrinfo",
                 "socket.gethostbyname", "socket.gethostbyaddr"}:
        address = args[1] if event in {"socket.connect", "socket.sendto"} else args[0]
        host = address[0] if isinstance(address, tuple) else address
        if host not in {"127.0.0.1", "::1", "localhost", None}:
            raise PermissionError("offline verification rejected external network")
    if event == "subprocess.Popen":
        executable, argv = args[:2]
        path = Path(os.fsdecode(executable))
        fixture = path.is_absolute() and path.resolve().is_relative_to(FIXTURES)
        if path.name in {"codex", "claude"} and not fixture and "--version" not in argv:
            raise PermissionError("offline verification rejected provider CLI")
    if event == "sqlite3.connect":
        from urllib.parse import unquote
        raw = os.fsdecode(args[0])
        if raw.startswith("file:"):
            raw = unquote(raw[5:].split("?", 1)[0])
        if raw != ":memory:" and Path(raw).resolve().is_relative_to(FORBIDDEN):
            raise PermissionError("offline verification rejected formal database")


def main():
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    for key in list(os.environ):
        if key.startswith(("OPENAI_", "ANTHROPIC_", "FINNHUB_", "MASSIVE_", "POLYGON_",
                           "FRED_", "FINANCIAL_DATASETS_", "SEC_", "IBKR_")):
            del os.environ[key]
    # conftest gives each test its own locks/governor. A session-wide override
    # would leak request reservations from one disposable test to the next.
    os.environ.pop("ARKSCOPE_LOCK_DIR", None)
    # Installed Snap Firefox gates create disposable profiles under the real
    # ~/snap/firefox/common confinement root. Keep HOME for that prerequisite;
    # test fixtures and the explicit token/DB paths isolate application state.
    for key, leaf in {"XDG_CONFIG_HOME": "home/config", "XDG_CACHE_HOME": "home/cache"}.items():
        path = WORK / leaf
        path.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(path)
    for key, leaf in {"ARKSCOPE_PROFILE_DB": "profile.db", "ARKSCOPE_MARKET_DB": "market.db",
                      "ARKSCOPE_SA_DB": "sa.db", "ARKSCOPE_MACRO_CALENDAR_DB": "macro.db",
                      "ARKSCOPE_TOKEN_STORE_PATH": "tokens.json"}.items():
        os.environ[key] = str(WORK / leaf)
    os.environ.update(ARKSCOPE_DISABLE_SCHEDULER="1", ARKSCOPE_PROVIDER_ENV_FALLBACK="0",
                      ARKSCOPE_BROWSER_ACCEPTANCE="1")
    sys.addaudithook(audit)
    from src import env_keys
    env_keys._loaded = True
    import pytest
    return pytest.main(["--basetemp=" + str(FIXTURES), *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
