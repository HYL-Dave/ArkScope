"""Diagnostic SQL timing for fake-source capacity work; never record parameters."""

import argparse
import json
from pathlib import Path
import sqlite3
import sys
from threading import Lock, current_thread
import time
from unittest.mock import patch

import measure_polling


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hold-commit-seconds", type=float, default=0)
    args, remaining = parser.parse_known_args()
    if not 0 <= args.hold_commit_seconds <= 30:
        raise ValueError("bounded_synthetic_commit_hold")
    connect = sqlite3.connect
    observations = []
    hold_lock, holds, source_inserts = Lock(), [], []
    started = time.monotonic()

    def measured(operation, callback):
        before, error = time.monotonic(), None
        try:
            return callback()
        except sqlite3.Error as exc:
            error = str(exc)
            raise
        finally:
            elapsed = time.monotonic() - before
            if elapsed > 0.02 or error is not None:
                observations.append({"thread": current_thread().name, "operation": operation,
                    "at_seconds": round(before - started, 3), "elapsed_seconds": round(elapsed, 3), "error": error})

    class TimedCursor(sqlite3.Cursor):
        def execute(self, sql, parameters=()):
            return measured(" ".join(sql.split())[:100], lambda: super(TimedCursor, self).execute(sql, parameters))

        def fetchone(self):
            return measured("fetchone", lambda: super(TimedCursor, self).fetchone())

        def fetchall(self):
            return measured("fetchall", lambda: super(TimedCursor, self).fetchall())

    class TimedConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            result = self.cursor(factory=TimedCursor).execute(sql, parameters)
            if sql.startswith("INSERT INTO lifecycle_web_pages"):
                self.source_inserted = True
                with hold_lock:
                    source_inserts.append(True)
            return result

        def commit(self):
            with hold_lock:
                hold = bool(args.hold_commit_seconds and getattr(self, "source_inserted", False)
                            and len(source_inserts) == 8 and not holds)
                if hold:
                    holds.append(args.hold_commit_seconds)
            if hold:
                measured("synthetic_large_commit_hold", lambda: time.sleep(args.hold_commit_seconds))
            return measured("commit", lambda: super(TimedConnection, self).commit())

        def close(self):
            return measured("close", lambda: super(TimedConnection, self).close())

    def open_connection(*values, **options):
        options.setdefault("factory", TimedConnection)
        return connect(*values, **options)

    original_arguments = sys.argv
    sys.argv = [sys.argv[0], *remaining, "--output", str(args.output)]
    try:
        with patch.object(sqlite3, "connect", open_connection):
            measure_polling.main()
    finally:
        sys.argv = original_arguments
        with args.output.with_name("sql-timing.json").open("x") as stream:
            json.dump({"provider_calls": 0, "production_data_access": False, "parameters_recorded": False,
                       "synthetic_commit_holds_seconds": holds,
                       "source_inserts_observed": len(source_inserts),
                       "observations": observations}, stream, sort_keys=True, indent=2)
            stream.write("\n")


if __name__ == "__main__":
    main()
