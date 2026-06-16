"""Slice 0 — env value unquoting must strip QUOTES first, THEN whitespace.

Regression for the EODHD 401: config/.env stored EODHD_API_KEY as
``"  <key>"`` — a leading space INSIDE the quotes. The old
``value.strip().strip('"')`` order trimmed the OUTER whitespace, removed the
quotes, then left the now-leading inner space, so the key reached EODHD as
`` <key>`` (server rejected it). ``unquote_env_value`` strips the matched quote
pair first, then the whitespace, so the inner space is removed. FAKE keys only.
"""

from __future__ import annotations

import pytest

from src.env_keys import unquote_env_value


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('"  eodhd-fake-123"', "eodhd-fake-123"),  # the actual config/.env shape — FAILS pre-fix
        ('  "  abc  "  ', "abc"),                   # outer ws + quotes + inner ws — FAILS pre-fix
        ("'  abc'", "abc"),                          # single-quoted, inner leading space
        ('"abc"', "abc"),                            # clean double-quoted (regression)
        ("'abc'", "abc"),                            # clean single-quoted (regression)
        ("abc", "abc"),                              # unquoted (regression)
        ("  abc  ", "abc"),                          # unquoted, outer ws (regression)
        ('""', ""),                                  # empty quoted -> empty
        ("eodhd-fake-123", "eodhd-fake-123"),        # plain key unchanged
        ('"abc', '"abc'),                            # unmatched leading quote left intact
        ('a"b', 'a"b'),                              # interior quote untouched
    ],
)
def test_unquote_env_value(raw, expected):
    assert unquote_env_value(raw) == expected
