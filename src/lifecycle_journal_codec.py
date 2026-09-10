"""Canonical JSON bytes and digests for current and retained lifecycle journals."""

import hashlib
import json


def canonical_json(value, *, ensure_ascii=True):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=ensure_ascii, allow_nan=False)


def digest_json(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()
