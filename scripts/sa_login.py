#!/usr/bin/env python3
"""
Seeking Alpha session login script.

WARNING: This script saves browser session credentials (cookies + localStorage)
to a local file. Treat the output file as a sensitive credential — do NOT commit
it to version control or share it.

Usage:
    # Recommended: reuse your Chrome login (closes Chrome briefly, then reopens)
    python scripts/sa_login.py --launch

    # Fresh browser (need to log in manually)
    python scripts/sa_login.py
"""

from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


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


def _chrome_profile_dir() -> str:
    """Get the Chrome user data directory."""
    return os.path.expanduser("~/.config/google-chrome")


def _is_chrome_running() -> bool:
    """Check if a real Chrome browser process is running (not just helpers)."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", r"/chrome/chrome\b"], capture_output=True, text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _remove_singleton_locks():
    """Remove Chrome's singleton lock files so a new instance can start fresh."""
    profile = _chrome_profile_dir()
    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        path = os.path.join(profile, name)
        try:
            os.unlink(path)
        except (FileNotFoundError, OSError):
            pass


def _close_chrome() -> bool:
    """Close all Chrome instances and clean up locks. Returns True if successful."""
    if not _is_chrome_running():
        _remove_singleton_locks()
        return True

    print("Chrome is currently running. It needs to close briefly to export your session.")
    print("(All windows and tabs will be restored automatically)")
    print()
    answer = input("Close Chrome? [Y/n] ").strip().lower()
    if answer and answer != "y":
        print("Aborted.")
        return False

    print("Closing Chrome...")

    # Graceful close
    subprocess.run(["pkill", "-TERM", "-f", r"/chrome/chrome"], capture_output=True)
    for _ in range(20):
        time.sleep(0.5)
        if not _is_chrome_running():
            _remove_singleton_locks()
            print("Chrome closed.")
            return True

    # Force kill
    subprocess.run(["pkill", "-KILL", "-f", r"/chrome/chrome"], capture_output=True)
    subprocess.run(["pkill", "-KILL", "-f", "chrome_crashpad"], capture_output=True)
    time.sleep(1)
    _remove_singleton_locks()

    if _is_chrome_running():
        print("ERROR: Could not close Chrome. Please close it manually and try again.")
        return False

    print("Chrome closed.")
    return True


def main():
    default_path = _get_default_session_path()
    parser = argparse.ArgumentParser(
        description="Save Seeking Alpha browser session",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Reuse your Chrome login (recommended):\n"
            "  python scripts/sa_login.py --launch\n\n"
            "  # Fresh browser (manual login):\n"
            "  python scripts/sa_login.py\n"
        ),
    )
    parser.add_argument(
        "--session-file",
        default=default_path,
        help=f"Path to save session state (default: {default_path})",
    )
    parser.add_argument(
        "--launch",
        action="store_true",
        help=(
            "Use your existing Chrome profile (reuses SA login). "
            "Closes Chrome briefly, opens with Playwright to export session, "
            "then you can reopen Chrome normally."
        ),
    )
    args = parser.parse_args()

    session_path = _resolve_session_path(args.session_file)

    print("=" * 60)
    print("This script saves your Seeking Alpha login session")
    print("(cookies + localStorage) to a local file.")
    print(f"  Output: {session_path}")
    print("Treat this file as a sensitive credential.")
    print("=" * 60)
    print()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright is not installed.")
        print("  pip install playwright && playwright install chromium")
        sys.exit(1)

    # Create directory with 0700 permissions
    session_path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(session_path.parent, stat.S_IRWXU)  # 0700

    target_url = "https://seekingalpha.com/alpha-picks/portfolio"

    with sync_playwright() as p:
        if args.launch:
            # --- Profile mode: use system Chrome profile via Playwright ---
            profile_dir = _chrome_profile_dir()

            if not os.path.isdir(profile_dir):
                print(f"ERROR: Chrome profile not found: {profile_dir}")
                sys.exit(1)

            # Must close Chrome — can't share profile with running instance
            if not _close_chrome():
                sys.exit(1)

            print()
            print(f"Opening system Chrome with your profile...")
            print(f"(Profile: {profile_dir})")

            context = p.chromium.launch_persistent_context(
                profile_dir,
                headless=False,
                channel="chrome",
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()
            page.goto(target_url, wait_until="networkidle")

            print(f"Navigated to: {target_url}")
            print()

            current_url = page.url
            if "login" not in current_url and "sign_in" not in current_url:
                print("Already logged in! Your SA session will be exported.")
            else:
                print("Not logged in. Please log in in the browser window.")

            print()
            input("Press Enter to save session...")

            context.storage_state(path=str(session_path))
            context.close()

            print()
            print("Browser closed. You can reopen Chrome normally now.")

        else:
            # --- Fresh mode: new browser, manual login ---
            browser = p.chromium.launch(headless=False, channel="chrome")
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()
            page.goto(target_url)

            print(f"Browser opened to: {target_url}")
            print()
            print("Please log in to your Seeking Alpha account.")
            print("Once you see the Alpha Picks portfolio page, press Enter here.")
            print()
            input("Press Enter when ready...")

            context.storage_state(path=str(session_path))
            browser.close()

        # Set file permissions to 0600 (owner read/write only)
        os.chmod(session_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600

        # Verify saved session with headless browser
        print()
        print("Verifying saved session...")
        browser2 = p.chromium.launch(headless=True)
        ctx2 = browser2.new_context(
            storage_state=str(session_path),
            viewport={"width": 1280, "height": 800},
        )
        page2 = ctx2.new_page()
        page2.goto(target_url, wait_until="networkidle")

        verify_url = page2.url
        if "login" in verify_url or "sign_in" in verify_url:
            print("WARNING: Session may not be valid — verification redirected to login.")
            print(f"  URL: {verify_url}")
        else:
            print(f"Session saved and verified: {session_path}")
            print(f"  File permissions: 0600 (owner read/write only)")

        ctx2.close()
        browser2.close()


if __name__ == "__main__":
    main()