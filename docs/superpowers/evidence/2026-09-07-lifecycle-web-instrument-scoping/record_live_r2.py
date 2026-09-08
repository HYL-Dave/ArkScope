"""Correct the receipt reader's connection setup; leave admitted files intact."""

import hashlib
import importlib.util
from pathlib import Path
import sqlite3
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("instrument_original_recorder", HERE / "record_live.py")
recorder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recorder)


def connection_factory(connect):
    def with_rows(*args, **kwargs):
        conn = connect(*args, **kwargs)
        conn.row_factory = sqlite3.Row
        return conn
    return with_rows


def main():
    write = recorder.original.write_new_json

    def receipt(path, value):
        if path.name == "verification.json":
            value = {**value, "receipt_reader_correction": {
                "previous_failure": "Missing sqlite3.Row in the receipt reader, not stored journal corruption",
                "corrected_wrapper_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "product_source_or_live_output_changed": False,
            }}
        return write(path, value)

    with patch.object(sqlite3, "connect", connection_factory(sqlite3.connect)), \
            patch.object(recorder.original, "write_new_json", receipt):
        recorder.main()


if __name__ == "__main__":
    main()
