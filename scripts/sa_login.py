#!/usr/bin/env python3
"""
Seeking Alpha session login script.

WARNING: This script saves browser session credentials (cookies + localStorage)
to a local file. Treat the output file as a sensitive credential — do NOT commit
it to version control or share it.

Usage:
    python scripts/sa_login.py [--session-file PATH]

The script opens a visible browser window to seekingalpha.com/alpha-picks/portfolio.
Log in with your SA Premium account, then press Enter in the terminal to save the session.
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


def _resolve_session_path(path_str: str) -> Path:
    """Expand ~ and resolve the session file path."""
    return Path(os.path.expanduser(path_str)).resolve()


def main():
    parser = argparse.ArgumentParser(description="Save Seeking Alpha browser session")
    parser.add_argument(
        "--session-file",
        default="~/.config/mindfulrl/seeking_alpha/storage_state.json",
        help="Path to save session state (default: ~/.config/mindfulrl/seeking_alpha/storage_state.json)",
    )
    args = parser.parse_args()

    session_path = _resolve_session_path(args.session_file)

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
        browser = p.chromium.launch(headless=False)
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

        # Save session state
        context.storage_state(path=str(session_path))

        # Set file permissions to 0600 (owner read/write only)
        os.chmod(session_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600

        # Verify: reload and check if portfolio table is visible
        print("Verifying session... reloading page...")
        page.reload()
        page.wait_for_load_state("networkidle")

        # Check if we can see the portfolio content (not redirected to login)
        current_url = page.url
        if "login" in current_url or "sign_in" in current_url:
            print("WARNING: Session may not be saved correctly — page redirected to login.")
            print(f"  Current URL: {current_url}")
        else:
            print(f"Session saved successfully to: {session_path}")
            print(f"  File permissions: 0600 (owner read/write only)")
            print(f"  Directory permissions: 0700 (owner only)")

        browser.close()


if __name__ == "__main__":
    main()
