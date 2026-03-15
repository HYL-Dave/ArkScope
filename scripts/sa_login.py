#!/usr/bin/env python3
"""
DEPRECATED: Use Chrome extension instead (extensions/sa_alpha_picks/).

Seeking Alpha session export script (cookie extraction approach).
Kept for reference — the Chrome extension approach is preferred because
Playwright headless/headed browsers are detected by SA's PerimeterX anti-bot.

Extracts SA cookies from your Chrome browser's cookie database and saves them
in Playwright storage_state format. No need to close Chrome or launch a browser.

WARNING: The output file contains your login credentials — do NOT commit it
to version control or share it.

Usage:
    python scripts/sa_login.py                        # Auto-detect Chrome profile
    python scripts/sa_login.py --profile "Profile 1"  # Specify Chrome profile name
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import stat
import sys
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

_CHROME_USER_DATA = os.path.expanduser("~/.config/google-chrome")
_SA_DOMAIN = "seekingalpha.com"


def _resolve_session_path(path_str: str) -> Path:
    """Expand ~ and resolve the session file path."""
    return Path(os.path.expanduser(path_str)).resolve()


def _get_default_session_path() -> str:
    """Read default session path from AgentConfig, fallback to hardcoded."""
    try:
        from src.agents.config import get_agent_config
        return get_agent_config().sa_session_file
    except Exception:
        return "~/.config/mindfulrl/seeking_alpha/storage_state.json"


def _find_sa_profile() -> str | None:
    """Find which Chrome profile has SA cookies."""
    for name in os.listdir(_CHROME_USER_DATA):
        cookie_path = os.path.join(_CHROME_USER_DATA, name, "Cookies")
        if not os.path.isfile(cookie_path):
            continue
        try:
            tmp = tempfile.mktemp(suffix=".db")
            shutil.copy2(cookie_path, tmp)
            conn = sqlite3.connect(tmp)
            count = conn.execute(
                f"SELECT count(*) FROM cookies WHERE host_key LIKE '%{_SA_DOMAIN}%'"
            ).fetchone()[0]
            conn.close()
            os.unlink(tmp)
            if count > 0:
                return name
        except Exception:
            continue
    return None


def _extract_cookies(profile_name: str) -> list[dict]:
    """Extract and decrypt SA cookies from a Chrome profile.

    Uses pycookiecheat for GNOME keyring decryption, plus raw SQLite
    for cookie metadata (domain, path, flags).
    """
    from pycookiecheat import chrome_cookies

    cookie_file = os.path.join(_CHROME_USER_DATA, profile_name, "Cookies")
    if not os.path.isfile(cookie_file):
        raise FileNotFoundError(f"Cookies file not found: {cookie_file}")

    # Decrypt cookie values
    decrypted = chrome_cookies(
        f"https://{_SA_DOMAIN}",
        cookie_file=cookie_file,
    )

    # Read metadata from raw DB (domain, path, flags)
    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(cookie_file, tmp)
    conn = sqlite3.connect(tmp)
    rows = conn.execute(
        "SELECT host_key, name, path, expires_utc, is_secure, is_httponly, samesite "
        f"FROM cookies WHERE host_key LIKE '%{_SA_DOMAIN}%'"
    ).fetchall()
    conn.close()
    os.unlink(tmp)

    meta = {}
    for r in rows:
        meta[r[1]] = {
            "domain": r[0],
            "path": r[2],
            "expires": r[3] / 1000000 - 11644473600 if r[3] > 0 else -1,
            "secure": bool(r[4]),
            "httpOnly": bool(r[5]),
            "sameSite": ["None", "Lax", "Strict"][r[6]] if r[6] in (0, 1, 2) else "None",
        }

    # Build Playwright cookie format
    cookies = []
    for name, value in decrypted.items():
        m = meta.get(name, {})
        cookies.append({
            "name": name,
            "value": value,
            "domain": m.get("domain", f".{_SA_DOMAIN}"),
            "path": m.get("path", "/"),
            "expires": m.get("expires", -1),
            "httpOnly": m.get("httpOnly", False),
            "secure": m.get("secure", False),
            "sameSite": m.get("sameSite", "None"),
        })

    return cookies


def main():
    default_path = _get_default_session_path()
    parser = argparse.ArgumentParser(
        description="Export Seeking Alpha session from Chrome cookies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/sa_login.py                        # Auto-detect profile\n"
            "  python scripts/sa_login.py --profile 'Profile 1'  # Specify profile\n"
        ),
    )
    parser.add_argument(
        "--session-file",
        default=default_path,
        help=f"Output path (default: {default_path})",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Chrome profile name (e.g. 'Default', 'Profile 1'). Auto-detected if omitted.",
    )
    args = parser.parse_args()

    session_path = _resolve_session_path(args.session_file)

    print("=" * 60)
    print("Seeking Alpha session export")
    print(f"  Output: {session_path}")
    print("=" * 60)
    print()

    try:
        from pycookiecheat import chrome_cookies  # noqa: F401
    except ImportError:
        print("ERROR: pycookiecheat is not installed.")
        print("  pip install pycookiecheat")
        sys.exit(1)

    # Find or verify profile
    profile = args.profile
    if not profile:
        print("Searching Chrome profiles for SA cookies...")
        profile = _find_sa_profile()
        if not profile:
            print("ERROR: No Chrome profile found with Seeking Alpha cookies.")
            print("Make sure you're logged in to seekingalpha.com in Chrome.")
            sys.exit(1)
        print(f"Found SA cookies in: {profile}")
    else:
        cookie_path = os.path.join(_CHROME_USER_DATA, profile, "Cookies")
        if not os.path.isfile(cookie_path):
            print(f"ERROR: Profile not found: {cookie_path}")
            sys.exit(1)

    # Extract cookies
    print(f"Extracting cookies from {profile}...")
    cookies = _extract_cookies(profile)

    if not cookies:
        print("ERROR: No SA cookies found. Make sure you're logged in to seekingalpha.com.")
        sys.exit(1)

    # Build storage_state
    storage_state = {
        "cookies": cookies,
        "origins": [{
            "origin": f"https://{_SA_DOMAIN}",
            "localStorage": [],
        }],
    }

    # Write with secure permissions
    session_path.parent.mkdir(parents=True, exist_ok=True)
    with open(session_path, "w") as f:
        json.dump(storage_state, f, indent=2)
    os.chmod(session_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    os.chmod(session_path.parent, stat.S_IRWXU)  # 0700

    print()
    print(f"Exported {len(cookies)} cookies to: {session_path}")
    print(f"  File permissions: 0600 (owner read/write only)")
    print()

    # Verify with headless browser
    print("Verifying session with headless browser...")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                storage_state=str(session_path),
                viewport={"width": 1280, "height": 800},
            )
            page = ctx.new_page()
            page.goto(f"https://{_SA_DOMAIN}/alpha-picks/portfolio", wait_until="networkidle")

            url = page.url
            if "login" in url or "sign_in" in url:
                print("WARNING: Verification failed — redirected to login.")
                print(f"  URL: {url}")
                print("  The cookies may have expired or SA blocked headless access.")
            else:
                print("Session verified — SA Alpha Picks page loaded successfully!")

            ctx.close()
            browser.close()
    except Exception as e:
        print(f"Verification skipped: {e}")
        print("(Cookies were exported; verification requires: pip install playwright && playwright install chromium)")


if __name__ == "__main__":
    main()