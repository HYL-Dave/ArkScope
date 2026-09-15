"""Byte-level contracts retained from the listing converter's live helpers."""

import hashlib
import sqlite3

import pytest

from src.lifecycle_investigation import sqlite_helpers as helpers


@pytest.mark.parametrize("value,encoded", (
    (None, b"n"),
    (b"", b"b0:"),
    (b"\x00\xff", b"b2:\x00\xff"),
    ("", b"s0:"),
    ("a:\n", b"s3:a:\n"),
    ("\u4e2d", b"s3:\xe4\xb8\xad"),
    ("\ud800", b"s3:\xed\xa0\x80"),
    (0, b"i0;"),
    (-7, b"i-7;"),
    (9223372036854775807, b"i9223372036854775807;"),
    (True, b"iTrue;"),
    (False, b"iFalse;"),
    (0.0, b"f0x0.0p+0;"),
    (-0.0, b"f-0x0.0p+0;"),
    (1.5, b"f0x1.8000000000000p+0;"),
    (float("inf"), b"finf;"),
    (float("-inf"), b"f-inf;"),
    (float("nan"), b"fnan;"),
))
def test_cell_encoding_is_byte_identical(value, encoded):
    assert helpers._encode_cell(value) == encoded


@pytest.mark.parametrize("value", (bytearray(b"a"), memoryview(b"a"), [], {}, object()))
def test_unsupported_cells_keep_the_original_error_type_and_code(value):
    with pytest.raises(RuntimeError) as error:
        helpers._encode_cell(value)
    assert type(error.value) is helpers.ListingMigrationRejected
    assert error.value.args == ("unsupported_sqlite_value",)


@pytest.mark.parametrize("value,quoted", (
    ("plain", '"plain"'),
    ("", '""'),
    ('a"b', '"a""b"'),
    ('"; DROP TABLE retained; --', '"""; DROP TABLE retained; --"'),
))
def test_identifier_encoding_is_exact_and_does_not_execute_embedded_sql(value, quoted):
    assert helpers._quote_identifier(value) == quoted
    with sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE TABLE retained(value TEXT)")
        conn.execute(f"CREATE TABLE {helpers._quote_identifier(value)}(value BLOB)")
        conn.execute(f"INSERT INTO {helpers._quote_identifier(value)} VALUES (?)", (b"kept",))
        assert conn.execute(f"SELECT * FROM {helpers._quote_identifier(value)}").fetchall() == [(b"kept",)]
        assert conn.execute("SELECT * FROM retained").fetchall() == []


@pytest.mark.parametrize("size", (0, 3, 1048575, 1048576, 1048577, 2097169))
def test_file_digest_keeps_all_bytes_across_chunk_boundaries(tmp_path, size):
    path = tmp_path / "binary"
    raw = (bytes(range(256)) * (size // 256 + 1))[:size]
    path.write_bytes(raw)
    assert helpers._sha_file(path) == hashlib.sha256(raw).hexdigest()
    assert path.read_bytes() == raw


@pytest.mark.parametrize("directory", (False, True))
def test_file_digest_propagates_file_open_errors(tmp_path, directory):
    path = tmp_path / "unreadable"
    if directory:
        path.mkdir()
    with pytest.raises(IsADirectoryError if directory else FileNotFoundError):
        helpers._sha_file(path)
