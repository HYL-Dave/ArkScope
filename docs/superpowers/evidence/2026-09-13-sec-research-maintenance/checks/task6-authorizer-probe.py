"""Observe authorizer reset behavior using only an in-memory SQLite database."""

import json
import sqlite3
import sys

connection = sqlite3.connect(":memory:")
result = {"python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
          "database": ":memory:"}
try:
    connection.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
    result["baseline"] = connection.execute("SELECT 1").fetchone()[0]
    connection.set_authorizer(None)
    try:
        result["none_reset"] = connection.execute("SELECT 2").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        result["none_reset"] = {"type": type(exc).__name__, "message": str(exc)}
    connection.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
    result["callback_reset"] = connection.execute("SELECT 3").fetchone()[0]
finally:
    connection.close()
print(json.dumps(result))
