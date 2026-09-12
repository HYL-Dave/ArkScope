"""Verify the private probe engine before running disposable application tests."""

import json
from pathlib import Path
import runpy
import sqlite3
import sys

WORK = Path(__file__).resolve().parent
EXPECTED = "2026-07-24 19:02:57 bf7c7f30031888f4e796e429ab3978879485813aaca6f641c7b33e4e09459bcc"
assert sqlite3.sqlite_version == "3.53.4", "private SQLite candidate was not loaded"
library = WORK / "sqlite-candidate/prefix/lib/libsqlite3.so.3.53.4"
mapped = {line.split()[-1] for line in Path("/proc/self/maps").read_text().splitlines()
          if "/libsqlite3.so" in line}
assert mapped == {str(library.resolve())}, "unexpected SQLite mapped library"
connection = sqlite3.connect(":memory:")
try:
    source_id = connection.execute("SELECT sqlite_source_id()").fetchone()[0]
finally:
    connection.close()
assert source_id == EXPECTED, "SQLite candidate source ID mismatch"
print(json.dumps({"probe_only": True, "sqlite": sqlite3.sqlite_version,
                  "source_id": source_id, "mapped_libraries": sorted(mapped)}), flush=True)
launcher = WORK / "offline_pytest.py"
sys.argv[0] = str(launcher)
runpy.run_path(str(launcher), run_name="__main__")
