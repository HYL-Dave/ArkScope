"""SQLite byte contracts shared by current investigation installation and disposal."""

from __future__ import annotations

import hashlib
from pathlib import Path


class ListingMigrationRejected(RuntimeError):
    """Original encoding error type, retained independently of the retired converter."""


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _encode_cell(value: object) -> bytes:
    if value is None:
        return b"n"
    if isinstance(value, bytes):
        return b"b" + str(len(value)).encode("ascii") + b":" + value
    if isinstance(value, str):
        encoded = value.encode("utf-8", errors="surrogatepass")
        return b"s" + str(len(encoded)).encode("ascii") + b":" + encoded
    if isinstance(value, int):
        return b"i" + str(value).encode("ascii") + b";"
    if isinstance(value, float):
        return b"f" + value.hex().encode("ascii") + b";"
    raise ListingMigrationRejected("unsupported_sqlite_value")
