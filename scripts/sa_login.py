#!/usr/bin/env python3
"""
Seeking Alpha session login script.

WARNING: This script saves browser session credentials (cookies + localStorage)
to a local file. Treat the output file as a sensitive credential — do NOT commit
it to version control or share it.

Usage:
    # Use existing Chrome profile (no re-login needed, close Chrome first):
    python scripts/sa_login.py --profile

    # Fresh browser (need to log in manually):
    python scripts/sa_login.py
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

_DEFAULT_CHROME_PROFILE = "~/.config/google-chrome"


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


def main():
    default_path = _get_default_session_path()
    parser = argparse.ArgumentParser(description="Save Seeking Alpha browser session")
    parser.add_argument(
        "--session-file",
        default=default_path,
        help=f"Path to save session state (default: {default_path})",
    )
    parser.add_argument(
        "--profile",
        nargs="?",
        const=_DEFAULT_CHROME_PROFILE,
        default=None,
        metavar="DIR",
        help=(
            "Use existing Chrome profile (loads your cookies, no re-login needed). "
            f"Default profile: {_DEFAULT_CHROME_PROFILE}. "
            "NOTE: Close Chrome before running this."
        ),
    )
    parser.add_argument(
        "--channel",
        default="chrome",
        help="Browser channel: chrome (system Chrome, default), chromium (Playwright bundled)",
    )
    args = parser.parse_args()

    session_path = _resolve_session_path(args.session_file)
    use_profile = args.profile is not None

    print("=" * 60)
    print("WARNING: This script saves your Seeking Alpha login session")
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
        if use_profile:
            # Persistent context: loads existing Chrome cookies/session
            profile_dir = os.path.expanduser(args.profile)
            if not os.path.isdir(profile_dir):
                print(f"ERROR: Chrome profile directory not found: {profile_dir}")
                sys.exit(1)

            print(f"Loading Chrome profile from: {profile_dir}")
            print("(Make sure Chrome is closed before running this)")
            print()

            context = p.chromium.launch_persistent_context(
                profile_dir,
                headless=False,
                channel=args.channel if args.channel != "chromium" else None,
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()
            page.goto(target_url, wait_until="networkidle")

            print(f"Browser opened to: {target_url}")
            print()

            # Check if already logged in
            current_url = page.url
            if "login" not in current_url and "sign_in" not in current_url:
                print("Already logged in via Chrome profile!")
            else:
                print("Not logged in yet. Please log in manually.")

            print("Press Enter to save the session.")
            print()
            input("Press Enter when ready...")

            context.storage_state(path=str(session_path))
            context.close()

        else:
            # Fresh context: user needs to log in manually
            launch_kwargs = {"headless": False}
            if args.channel != "chromium":
                launch_kwargs["channel"] = args.channel
            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()
            page.goto(target_url)

            print(f"Browser opened to: {target_url}")
            print()
            print("Please log in to your Seeking Alpha account.")
            print("Once you see the Alpha Picks portfolio page, press Enter here to save the session.")
            print()
            input("Press Enter when ready...")

            context.storage_state(path=str(session_path))
            browser.close()

        # Set file permissions to 0600 (owner read/write only)
        os.chmod(session_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600

        # Verify saved session
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
            print("WARNING: Session may not be saved correctly — verification redirected to login.")
            print(f"  URL: {verify_url}")
        else:
            print(f"Session saved successfully to: {session_path}")
            print(f"  File permissions: 0600 (owner read/write only)")
            print(f"  Directory permissions: 0700 (owner only)")

        ctx2.close()
        browser2.close()


if __name__ == "__main__":
    main()