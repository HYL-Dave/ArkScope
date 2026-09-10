"""Retained action-case reads and the remaining legacy web-router cutover gate."""

from pathlib import Path
import sqlite3

from src.lifecycle_investigation.schema import installed, verify_journal


def cutover_active(profile_path):
    path = Path(profile_path)
    if not path.is_file():
        return False
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2) as conn:
        if not installed(conn):
            return False
        verify_journal(conn)
        return True


def retained_action_cases(conn):
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "ticker_identity_transitions" not in tables:
        return set()
    return {row[0] for row in conn.execute("SELECT DISTINCT case_id FROM ticker_identity_transitions")}
