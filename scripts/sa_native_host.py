#!/home/hyl/.virtualenvs/llm_app/bin/python3
"""
Native Messaging host for SA Alpha Picks Chrome extension.

Chrome launches this script via stdin/stdout pipe when the extension calls
chrome.runtime.sendNativeMessage(). Each invocation is a fresh process.

Message format: 4-byte little-endian length prefix + UTF-8 JSON body.
"""

from __future__ import annotations

import json
import logging
import os
import struct
import sys
from datetime import datetime, timezone

# Fix cwd — Chrome starts native hosts with unpredictable cwd.
# DAL and config use relative paths (data/cache/seeking_alpha/, config/user_profile.yaml).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

# Ensure log directory exists BEFORE configuring logging
_log_dir = os.path.join(PROJECT_ROOT, "data", "logs")
os.makedirs(_log_dir, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(_log_dir, "sa_native_host.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def read_message():
    """Read a Native Messaging message from stdin."""
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) < 4:
        return None
    length = struct.unpack("=I", raw_length)[0]
    data = sys.stdin.buffer.read(length)
    return json.loads(data)


def write_message(msg):
    """Write a Native Messaging message to stdout."""
    encoded = json.dumps(msg).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("=I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def handle_message(msg):
    """Process a message from the extension."""
    from src.tools.data_access import DataAccessLayer

    action = msg.get("action")
    scope = msg.get("scope")

    # batch_ts from extension (shared across scopes), fallback to now()
    batch_ts_str = msg.get("batch_ts")
    if batch_ts_str:
        # JS Date.toISOString() outputs trailing Z; Python 3.10 fromisoformat can't parse Z
        attempt_ts = datetime.fromisoformat(batch_ts_str.replace("Z", "+00:00"))
    else:
        attempt_ts = datetime.now(tz=timezone.utc)

    dal = DataAccessLayer()

    if action == "refresh":
        return _handle_refresh(dal, scope, msg.get("picks", []), attempt_ts)

    elif action == "refresh_failure":
        return _handle_failure(dal, scope, attempt_ts, msg.get("error", "unknown"))

    elif action == "ping":
        return {"status": "ok", "project_root": PROJECT_ROOT}

    return {"status": "error", "error": f"unknown action: {action}"}


def _handle_refresh(dal, scope, picks, attempt_ts):
    """Persist scraped picks via DAL."""
    # Add portfolio_status and is_stale (extension doesn't set these)
    for pick in picks:
        pick["portfolio_status"] = scope
        pick["is_stale"] = False

    snapshot_ts = datetime.now(tz=timezone.utc)
    try:
        count = dal.apply_sa_refresh(
            scope=scope,
            picks=picks,
            attempt_ts=attempt_ts,
            snapshot_ts=snapshot_ts,
        )
        logger.info("Refresh %s: %d picks saved", scope, count)

        # Ticker sync: only on current scope success
        if scope == "current" and picks:
            _try_ticker_sync(dal, picks)

        return {"status": "ok", "scope": scope, "count": count}

    except Exception as e:
        logger.error("Refresh %s failed: %s", scope, e)
        try:
            dal.record_sa_refresh_failure(scope, attempt_ts, str(e))
        except Exception:
            pass
        return {"status": "error", "scope": scope, "error": str(e)}


def _handle_failure(dal, scope, attempt_ts, error):
    """Record a refresh failure (session expired, paywall, etc.)."""
    try:
        dal.record_sa_refresh_failure(scope, attempt_ts, error)
        logger.warning("Recorded failure for %s: %s", scope, error)
    except Exception as e:
        logger.error("Failed to record failure for %s: %s", scope, e)
    return {"status": "ok", "scope": scope, "recorded_failure": True}


def _try_ticker_sync(dal, picks):
    """Best-effort ticker sync to tickers_core.json."""
    try:
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient
        client = SAAlphaPicksClient(dal=dal)
        client.sync_tickers_to_collection(picks)
        logger.info("Ticker sync completed")
    except Exception as e:
        logger.warning("Ticker sync failed (best-effort): %s", e)


def main():
    try:
        msg = read_message()
        if msg is None:
            return

        logger.info("Received: action=%s scope=%s", msg.get("action"), msg.get("scope"))
        result = handle_message(msg)
        write_message(result)
        logger.info("Sent: %s", json.dumps(result)[:200])

    except Exception as e:
        logger.exception("Native host error")
        try:
            write_message({"status": "error", "error": str(e)})
        except Exception:
            pass


if __name__ == "__main__":
    main()
