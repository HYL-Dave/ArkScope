"""Bound ID sets without a SQL variable per item or a separate item-count cap."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence


def integer_ids_json(values: Sequence[int]) -> str:
    for value in values:
        if not -(2**63) <= value <= 2**63 - 1:
            raise OverflowError("Python int too large to convert to SQLite INTEGER")
    return json.dumps(values, separators=(",", ":"))


def text_ids_query(
    conn: sqlite3.Connection, values: Sequence[str],
) -> tuple[str, tuple[str]]:
    for value in values:
        value.encode("utf-8")
    if any("\0" in value for value in values):
        # SQLite 3.37 JSON text decoding truncates at NUL. Pass JSON string
        # literals through json_each, then decode them with Python's parser.
        conn.create_function("arkscope_json_text", 1, json.loads, deterministic=True)
        payload = json.dumps([json.dumps(value) for value in values])
        return "SELECT arkscope_json_text(value) FROM json_each(?)", (payload,)
    return "SELECT value FROM json_each(?)", (
        json.dumps(values, ensure_ascii=False, separators=(",", ":")),
    )
