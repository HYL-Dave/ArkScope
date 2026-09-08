import importlib.util
from pathlib import Path
import sqlite3

import pytest


SPEC = importlib.util.spec_from_file_location("instrument_corrected_recorder", Path(__file__).with_name("record_live_r2.py"))
recorder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recorder)


def test_receipt_connection_corrects_row_shape_without_writing_journal(tmp_path):
    from src.lifecycle_web_schema import WebJournalError
    from src.lifecycle_web_store import LifecycleWebStore
    from tests.test_lifecycle_web_review import context

    c = context(tmp_path)
    before = c["profile"].read_bytes()
    uri = c["profile"].as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        with pytest.raises(WebJournalError, match="^web_journal_integrity$"):
            LifecycleWebStore.read_on_connection(conn, c["run_id"])
    with recorder.connection_factory(sqlite3.connect)(uri, uri=True) as conn:
        conn.execute("PRAGMA query_only=ON")
        row = LifecycleWebStore.read_on_connection(conn, c["run_id"])
        assert row["finding"].action == "terminal_delisting"
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
    assert c["profile"].read_bytes() == before
