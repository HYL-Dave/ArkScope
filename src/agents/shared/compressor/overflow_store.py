"""Disk persistence for Layer 0 overflow records (P1.4 commit 1).

Implements docs/design/P1_4_SPEC.md §3.1 + §3.1.1:

  - ``record_id = sha256(tool_name + b"\\0" + canonical_args_hash + b"\\0" +
    payload_bytes).hexdigest()[:16]``
  - Records persisted at ``<base_dir>/<session_id>/<record_id>.json``.
  - Session-isolated reads — a record written by session A is not
    visible to session B.
  - Path-traversal hardened: ``record_id`` must match
    ``^[0-9a-f]{16}$``; ``session_id`` must not contain ``/`` or ``..``.
  - Reads return ``None`` on missing / malformed / corrupt records,
    NEVER raise (per §3.1 fail-open principle: Layer 0 must not block
    agent progress, even when persistence misbehaves).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .types import CompressionRecord

logger = logging.getLogger(__name__)


_RECORD_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")
_RECORD_ID_LENGTH = 16  # 16 hex chars == 64 bits

# Session-id rejects: path-traversal vectors and an empty string. We do
# not enforce a strict allowlist beyond that — callers pass the running
# session's id (typically ``session_YYYYMMDD_HHMMSS`` style) and we trust
# that, but we still defend against the obvious escape characters.
_SESSION_ID_REJECT = re.compile(r"[/\\]|\.\.")


def canonical_args_hash(args: Optional[Dict[str, Any]]) -> str:
    """Stable sha256 hex of args dict — sort_keys=True, ensure_ascii=False.

    A dict with the same key/value contents but different insertion
    order produces the same hash. This is the contract relied on by
    `test_canonical_args_hash_dict_order_independent`.
    """
    canonical = json.dumps(args or {}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_record_id(
    tool_name: str,
    args: Optional[Dict[str, Any]],
    payload_bytes: bytes,
) -> str:
    """Derive ``record_id`` per spec §3.1.1.

    Provenance-unambiguous: ``tool_name`` is part of the hash input, so
    two tools that happen to produce the same payload bytes still land
    in different records. This is intentional — see the open-question
    resolution at spec §9 #2.
    """
    if not isinstance(tool_name, str) or not tool_name:
        raise ValueError("tool_name must be a non-empty str")
    if not isinstance(payload_bytes, (bytes, bytearray)):
        raise TypeError("payload_bytes must be bytes")

    args_hash = canonical_args_hash(args)
    h = hashlib.sha256()
    h.update(tool_name.encode("utf-8"))
    h.update(b"\0")
    h.update(args_hash.encode("utf-8"))
    h.update(b"\0")
    h.update(bytes(payload_bytes))
    return h.hexdigest()[:_RECORD_ID_LENGTH]


def is_valid_record_id(record_id: Any) -> bool:
    """Path-traversal guard: only canonical 16-lowercase-hex IDs accepted."""
    if not isinstance(record_id, str):
        return False
    return bool(_RECORD_ID_PATTERN.match(record_id))


def _validate_session_id(session_id: str) -> None:
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("session_id must be a non-empty str")
    if _SESSION_ID_REJECT.search(session_id):
        raise ValueError(
            f"session_id contains forbidden characters (/, \\, ..): "
            f"{session_id!r}"
        )


class OverflowStore:
    """Session-scoped disk store for Layer 0 overflow records.

    Layout: ``<base_dir>/<session_id>/<record_id>.json``.

    The ``base_dir`` is created on demand; the per-session directory
    is created in ``__init__``. ``record_id`` is validated on every
    read and write to prevent path traversal — even if a caller
    accidentally passes user-supplied input.
    """

    def __init__(self, base_dir: Path, session_id: str) -> None:
        _validate_session_id(session_id)
        self._base_dir = Path(base_dir)
        self._session_id = session_id
        self._session_dir = self._base_dir / session_id
        self._session_dir.mkdir(parents=True, exist_ok=True)

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def session_dir(self) -> Path:
        return self._session_dir

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def write(
        self,
        tool_name: str,
        args: Optional[Dict[str, Any]],
        payload: str,
    ) -> CompressionRecord:
        """Compute ``record_id``, persist, return the ``CompressionRecord``.

        Args:
            tool_name: name of the tool that produced ``payload``.
            args: original args dict (or None / empty dict).
            payload: original payload as str. utf-8 encoded for hashing.
        """
        if not isinstance(payload, str):
            raise TypeError("payload must be str (utf-8)")
        if not isinstance(tool_name, str) or not tool_name:
            raise ValueError("tool_name must be a non-empty str")

        payload_bytes = payload.encode("utf-8")
        args_dict = dict(args or {})
        args_hash = canonical_args_hash(args_dict)
        record_id = compute_record_id(tool_name, args_dict, payload_bytes)

        record = CompressionRecord(
            record_id=record_id,
            tool_name=tool_name,
            args=args_dict,
            args_hash=args_hash,
            original_size=len(payload_bytes),
            original_payload=payload,
            written_at=datetime.now(timezone.utc).isoformat(),
        )

        self._record_path(record_id).write_text(
            json.dumps(record.to_dict(), ensure_ascii=False),
            encoding="utf-8",
        )
        return record

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def read(self, record_id: str) -> Optional[CompressionRecord]:
        """Read a record by id. Returns ``None`` on missing / invalid / corrupt
        / **tampered**.

        Never raises for normal not-found or malformed-id scenarios —
        callers (Layer 5 transcript renderer, CLI debug, etc.) treat
        ``None`` as "no overflow available".

        Integrity validation (mismatch → return None, no raise):

          1. ``record_id`` argument must match canonical-id pattern.
          2. JSON ``record_id`` field must equal the filename-derived id.
          3. ``args_hash`` field must equal ``canonical_args_hash(args)``.
          4. ``original_size`` field must equal
             ``len(original_payload.encode("utf-8"))``.
          5. ``compute_record_id(tool_name, args, payload_bytes)`` must
             equal the JSON ``record_id``.

          Any of (2)-(5) failing means the record was tampered with on
          disk; we refuse to surface tampered data to the agent.
        """
        if not is_valid_record_id(record_id):
            logger.debug("Rejected invalid record_id: %r", record_id)
            return None

        path = self._record_path(record_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            record = CompressionRecord.from_dict(data)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "Failed to read overflow record %s in session %s: %s",
                record_id, self._session_id, exc,
            )
            return None

        if not self._verify_record_integrity(record, expected_filename_id=record_id):
            return None
        return record

    def _verify_record_integrity(
        self,
        record: CompressionRecord,
        *,
        expected_filename_id: str,
    ) -> bool:
        """Return True iff every cross-field invariant holds. False = tampered."""
        # (2) JSON record_id must match the filename
        if record.record_id != expected_filename_id:
            logger.warning(
                "Overflow record id mismatch: filename=%s, json=%s — refusing",
                expected_filename_id, record.record_id,
            )
            return False

        # (3) args_hash must match canonical_args_hash(args)
        expected_args_hash = canonical_args_hash(record.args)
        if record.args_hash != expected_args_hash:
            logger.warning(
                "Overflow record args_hash mismatch for id=%s — refusing",
                record.record_id,
            )
            return False

        # (4) original_size must match the utf-8 byte length of original_payload
        try:
            payload_bytes = record.original_payload.encode("utf-8")
        except (AttributeError, UnicodeError):
            logger.warning(
                "Overflow record original_payload not utf-8 encodable for id=%s",
                record.record_id,
            )
            return False
        if record.original_size != len(payload_bytes):
            logger.warning(
                "Overflow record original_size mismatch for id=%s "
                "(claimed=%d, actual=%d) — refusing",
                record.record_id, record.original_size, len(payload_bytes),
            )
            return False

        # (5) recomputed id from (tool_name, args, payload) must match
        try:
            recomputed = compute_record_id(
                record.tool_name, record.args, payload_bytes,
            )
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Overflow record recompute failed for id=%s: %s",
                record.record_id, exc,
            )
            return False
        if recomputed != record.record_id:
            logger.warning(
                "Overflow record recomputed id mismatch for id=%s "
                "(recomputed=%s) — refusing",
                record.record_id, recomputed,
            )
            return False

        return True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _record_path(self, record_id: str) -> Path:
        if not is_valid_record_id(record_id):
            raise ValueError(f"Invalid record_id: {record_id!r}")
        return self._session_dir / f"{record_id}.json"
