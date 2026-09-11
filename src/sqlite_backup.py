"""WAL-safe SQLite backups to a new, private destination."""

from contextlib import closing
import os
from pathlib import Path
import sqlite3


def backup_connection(conn: sqlite3.Connection, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    with closing(sqlite3.connect(path)) as destination:
        conn.backup(destination)
