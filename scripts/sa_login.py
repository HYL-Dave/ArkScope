#!/usr/bin/env python3
"""
Seeking Alpha session login script.

WARNING: This script saves browser session credentials (cookies + localStorage)
to a local file. Treat the output file as a sensitive credential — do NOT commit
it to version control or share it.

Usage:
    # Recommended: connect to your running Chrome via CDP (no re-login needed)
    #   Step 1: Restart Chrome with remote debugging:
    #     google-chrome --remote-debugging-port=9222
    #   Step 2: Run this script:
    python scripts/sa_login.py --cdp

    # Alternative: fresh browser (need to log in manually)
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

_DEFAULT_CDP_PORT = 9222


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


def _is_cdp_available(port: int) -> bool:
    """Check if a Chrome instance is listening on the CDP port."""
    import urllib.request
    try:
        urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
        return True
    except Exception:
        return False


def _find_chrome() -> str | None:
    """Find a Chrome executable."""
    chrome_paths = [
        "google-chrome", "google-chrome-stable",
        "/opt/google/chrome/chrome",
        "/usr/bin/google-chrome",
    ]
    for chrome in chrome_paths:
        try:
            subprocess.run([chrome, "--version"], capture_output=True, timeout=5)
            return chrome
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


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


def _graceful_close_chrome() -> bool:
    """Gracefully close all Chrome instances. Returns True if Chrome exited."""
    try:
        subprocess.run(["pkill", "-TERM", "-f", r"/chrome/chrome"], capture_output=True)
        for _ in range(20):
            time.sleep(0.5)
            if not _is_chrome_running():
                _remove_singleton_locks()
                return True
        # Force kill remaining
        subprocess.run(["pkill", "-KILL", "-f", r"/chrome/chrome"], capture_output=True)
        subprocess.run(["pkill", "-KILL", "-f", "chrome_crashpad"], capture_output=True)
        time.sleep(1)
        _remove_singleton_locks()
        return not _is_chrome_running()
    except FileNotFoundError:
        return False


def _launch_chrome_with_cdp(port: int) -> subprocess.Popen | None:
    """Launch Chrome with remote debugging enabled. Returns the process."""
    chrome = _find_chrome()
    if not chrome:
        return None

    # If Chrome is running, close it first (can't add CDP to existing process)
    if _is_chrome_running():
        print("Chrome is currently running. It will be restarted with CDP enabled.")
        print("(Your tabs and session will be restored automatically)")
        print()
        answer = input("Close Chrome and restart with CDP? [Y/n] ").strip().lower()
        if answer and answer != "y":
            print("Aborted.")
            return None

        print("Closing Chrome...")
        if not _graceful_close_chrome():
            print("ERROR: Could not close Chrome. Please close it manually and try again.")
            return None
        print("Chrome closed.")

    print(f"Launching: {chrome} --remote-debugging-port={port}")
    proc = subprocess.Popen(
        [chrome, f"--remote-debugging-port={port}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    # Wait for CDP to become available (up to 30s — restoring many windows takes time)
    print("Waiting for Chrome to start...", end="", flush=True)
    for i in range(120):
        time.sleep(0.5)
        if _is_cdp_available(port):
            print(" ready!")
            return proc
        if i % 10 == 9:
            print(".", end="", flush=True)

    # Don't kill Chrome — user may still want it running
    print()
    print(f"WARNING: Chrome started but CDP not available on port {port} after 30s.")
    print("Chrome is still running. You can connect manually:")
    print(f"  python scripts/sa_login.py --cdp --cdp-port {port}")
    return None


def main():
    default_path = _get_default_session_path()
    parser = argparse.ArgumentParser(
        description="Save Seeking Alpha browser session",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Connect to running Chrome (recommended):\n"
            "  #   1. Restart Chrome: google-chrome --remote-debugging-port=9222\n"
            "  #   2. Run: python scripts/sa_login.py --cdp\n\n"
            "  # Auto-launch Chrome with CDP:\n"
            "  python scripts/sa_login.py --cdp --launch\n\n"
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
        "--cdp",
        action="store_true",
        help=(
            "Connect to running Chrome via CDP (Chrome DevTools Protocol). "
            "Reuses your existing login session. "
            f"Requires Chrome started with --remote-debugging-port={_DEFAULT_CDP_PORT}"
        ),
    )
    parser.add_argument(
        "--cdp-port",
        type=int,
        default=_DEFAULT_CDP_PORT,
        help=f"CDP port (default: {_DEFAULT_CDP_PORT})",
    )
    parser.add_argument(
        "--launch",
        action="store_true",
        help="With --cdp: auto-launch Chrome with CDP if not already running",
    )
    parser.add_argument(
        "--channel",
        default="chrome",
        help="Browser channel for fresh mode: chrome (default), chromium (Playwright bundled)",
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
    chrome_proc = None

    with sync_playwright() as p:
        if args.cdp:
            # --- CDP mode: connect to running Chrome ---
            port = args.cdp_port

            if not _is_cdp_available(port):
                if args.launch:
                    print(f"No Chrome on port {port}. Launching Chrome with CDP...")
                    chrome_proc = _launch_chrome_with_cdp(port)
                    if not chrome_proc:
                        print("ERROR: Could not launch Chrome. Install google-chrome or start it manually:")
                        print(f"  google-chrome --remote-debugging-port={port}")
                        sys.exit(1)
                    print(f"Chrome launched (pid={chrome_proc.pid})")
                else:
                    print(f"ERROR: No Chrome listening on port {port}.")
                    print()
                    print("Option A — restart Chrome with CDP enabled:")
                    print(f"  google-chrome --remote-debugging-port={port}")
                    print("  Then re-run: python scripts/sa_login.py --cdp")
                    print()
                    print("Option B — let this script launch Chrome:")
                    print(f"  python scripts/sa_login.py --cdp --launch")
                    sys.exit(1)

            print(f"Connecting to Chrome on port {port}...")
            browser = p.chromium.connect_over_cdp(f"http://localhost:{port}")
            context = browser.contexts[0]  # Use the default (existing) context
            page = context.new_page()
            page.goto(target_url, wait_until="networkidle")

            print(f"Navigated to: {target_url}")
            print()

            current_url = page.url
            if "login" not in current_url and "sign_in" not in current_url:
                print("Already logged in! Your existing session will be saved.")
            else:
                print("Not logged in. Please log in in the browser window.")
                print("(You can also log in via any other tab in this Chrome)")

            print()
            input("Press Enter to save session...")

            context.storage_state(path=str(session_path))
            page.close()
            browser.close()  # Disconnects CDP, does NOT close Chrome

        else:
            # --- Fresh mode: new browser, manual login ---
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