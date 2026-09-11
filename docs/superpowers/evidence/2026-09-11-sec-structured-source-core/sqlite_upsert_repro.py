#!/usr/bin/python3
"""Archived UPSERT matrix, in memory only; stdout JSON, exit 0/1/2.

Run with an explicit interpreter under env -i and -I -S -B. No arguments,
application imports, filesystem-backed SQLite, repairs, or runtime changes.
"""

from contextlib import closing
import json
import os
import shlex
import sys


# Verbatim case matrix from the sealed current-journal-cleanup/sqlite-research.md.
CASES = (
    ("upstream_replace_duplicate", "REPLACE", " ON CONFLICT REPLACE", True),
    ("insert_schema_replace_duplicate", "INSERT", " ON CONFLICT REPLACE", True),
    ("insert_or_replace_duplicate", "INSERT OR REPLACE", "", True),
    ("replace_single_clause", "REPLACE", " ON CONFLICT REPLACE", False),
    ("insert_single_clause", "INSERT", " ON CONFLICT REPLACE", False),
)
INDEX_DAMAGE = ["wrong # of entries in index sqlite_autoindex_v0_1"]


def classify_case(result):
    """Recognize only a healthy result or the exact archived defect signature."""
    if (
        result.get("error") is not None
        or not result.get("sqlite_version")
        or not result.get("sqlite_source_id")
        or result.get("journal_mode") != "memory"
        or result.get("table_count") != 2
        or result.get("table_rows") != [[0, 11], [11, 22]]
        or result.get("quick_check") != ["ok"]
    ):
        return "inconclusive"
    if result.get("indexed_count") == 2 and result.get("integrity_check") == ["ok"]:
        return "pass"
    if result.get("indexed_count") == 3 and result.get("integrity_check") == INDEX_DAMAGE:
        return "defect_signature"
    return "inconclusive"


def classify_results(results):
    """Inconclusive cases or failed controls override any reproduced signature."""
    if [result.get("name") for result in results] != [case[0] for case in CASES]:
        return "inconclusive", 2
    statuses = [classify_case(result) for result in results]
    if "inconclusive" in statuses or statuses[3:] != ["pass", "pass"]:
        return "inconclusive", 2
    if "defect_signature" in statuses[:3]:
        return "defect_reproduced", 1
    return "all_pass", 0


def run_probe(case):
    name, verb, schema_policy, duplicate = case
    setup = (
        "CREATE TABLE v0(c1 INTEGER PRIMARY KEY" + schema_policy + ",c2 UNIQUE);\n"
        "INSERT INTO v0 VALUES(0,33),(11,22);"
    )
    statement = (
        verb + " INTO v0 VALUES(0,11) ON CONFLICT(c2) DO UPDATE SET c1=c2,c2=c2"
        + (" ON CONFLICT(c2) DO UPDATE SET c1=c1,c2=c1" if duplicate else "")
        + ";"
    )
    result = {
        "name": name,
        "role": "reproducer" if duplicate else "control",
        "sql": setup + "\n" + statement,
        "sqlite_version": None,
        "sqlite_source_id": None,
        "journal_mode": None,
        "table_count": None,
        "indexed_count": None,
        "table_rows": None,
        "integrity_check": None,
        "quick_check": None,
        "error": None,
    }
    try:
        # Import failures are probe failures too; keep them in the JSON report.
        import sqlite3

        with closing(sqlite3.connect(":memory:")) as connection:
            connection.execute("PRAGMA temp_store=MEMORY")
            result["sqlite_version"], result["sqlite_source_id"] = connection.execute(
                "SELECT sqlite_version(), sqlite_source_id()"
            ).fetchone()
            result["journal_mode"] = connection.execute("PRAGMA journal_mode").fetchone()[0]
            connection.executescript(setup)
            connection.execute(statement)
            # Preserve the archived counts; additionally inspect the table
            # without an index so a damaged covering index cannot hide row loss.
            result["table_count"] = connection.execute("SELECT count(*) FROM v0").fetchone()[0]
            result["indexed_count"] = connection.execute(
                "SELECT count(*) FROM v0 WHERE c2>8"
            ).fetchone()[0]
            result["table_rows"] = [list(row) for row in connection.execute(
                "SELECT c1,c2 FROM v0 NOT INDEXED ORDER BY c1"
            ).fetchall()]
            result["integrity_check"] = [row[0] for row in connection.execute(
                "PRAGMA integrity_check"
            ).fetchall()]
            result["quick_check"] = [row[0] for row in connection.execute(
                "PRAGMA quick_check"
            ).fetchall()]
    except Exception as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    result["classification"] = classify_case(result)
    return result


def main():
    report = {
        "scope": "synthetic :memory: SQLite only; no App runtime or user-data assessment",
        "reproduction_command": shlex.join([
            "env", "-i", "PATH=/usr/bin:/bin", sys.executable, "-I", "-S", "-B",
            os.path.abspath(__file__),
        ]),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "python_flags": {
            "isolated": sys.flags.isolated,
            "no_site": sys.flags.no_site,
            "dont_write_bytecode": sys.flags.dont_write_bytecode,
        },
        "cases": [],
        "error": None,
    }
    if len(sys.argv) != 1:
        report["error"] = "No arguments accepted; the only database target is :memory:."
        classification, exit_code = "inconclusive", 2
    elif not all(report["python_flags"].values()):
        report["error"] = "Run with env -i and explicit interpreter flags -I -S -B."
        classification, exit_code = "inconclusive", 2
    else:
        report["cases"] = [run_probe(case) for case in CASES]
        classification, exit_code = classify_results(report["cases"])
    report.update(classification=classification, exit_code=exit_code)
    print(json.dumps(report, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
