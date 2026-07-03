"""Deterministic, key-scoped price patch model (P0-C HAPN adopt-PG ruling).

A patch is a reviewed JSON document: exact insert keys with PG values, exact
update keys with PG values plus the local preimage they are allowed to replace.
Apply is insert/update only within the enumerated scope — never a bulk copy.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

Key = tuple[str, str, str]           # (ticker, interval, datetime)
Values = tuple[Any, Any, Any, Any, Any]  # (open, high, low, close, volume)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _insert_key(row: Sequence[Any]) -> Key:
    return (str(row[0]), str(row[1]), str(row[2]))


def _update_key(entry: Mapping[str, Any]) -> Key:
    k = entry["key"]
    return (str(k[0]), str(k[1]), str(k[2]))


def patch_fingerprints(patch: Mapping[str, Any]) -> dict[str, str]:
    insert_keys = sorted(_insert_key(r) for r in patch["insert_rows"])
    update_keys = sorted(_update_key(e) for e in patch["update_rows"])
    return {
        "key_scope_fingerprint": _sha256({"insert": insert_keys, "update": update_keys}),
        "pg_values_fingerprint": _sha256({
            "insert": sorted([list(r) for r in patch["insert_rows"]]),
            "update": sorted([[list(_update_key(e)), list(e["pg"])] for e in patch["update_rows"]]),
        }),
        "local_preimage_fingerprint": _sha256(
            sorted([[list(_update_key(e)), list(e["local_preimage"])] for e in patch["update_rows"]])
        ),
    }


def build_patch_dict(
    *,
    insert_rows: Iterable[Sequence[Any]],
    update_rows: Iterable[Mapping[str, Any]],
    ticker: str = "HAPN",
    interval: str = "15min",
) -> dict[str, Any]:
    patch: dict[str, Any] = {
        "schema_version": 1,
        "scope": "p0c_hapn_adopt_pg_patch",
        "ticker": ticker,
        "interval": interval,
        "insert_rows": sorted([list(r) for r in insert_rows]),
        "update_rows": sorted([dict(e) for e in update_rows], key=_update_key),
    }
    patch["counts"] = {"insert": len(patch["insert_rows"]), "update": len(patch["update_rows"])}
    patch.update(patch_fingerprints(patch))
    body = {k: v for k, v in patch.items()}
    patch["fingerprint"] = _sha256(body)
    return patch


def validate_patch(patch: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    ticker = patch.get("ticker")
    insert_keys = [_insert_key(r) for r in patch.get("insert_rows", [])]
    update_keys = [_update_key(e) for e in patch.get("update_rows", [])]
    for key in (*insert_keys, *update_keys):
        if key[0] != ticker or key[1] != patch.get("interval"):
            errors.append(f"key outside patch ticker/interval scope: {key}")
    overlap = set(insert_keys) & set(update_keys)
    if overlap:
        errors.append(f"insert/update key overlap: {sorted(overlap)[:3]}")
    if len(set(insert_keys)) != len(insert_keys) or len(set(update_keys)) != len(update_keys):
        errors.append("duplicate keys inside patch")
    counts = patch.get("counts", {})
    if counts.get("insert") != len(insert_keys) or counts.get("update") != len(update_keys):
        errors.append("counts do not match row lists")
    fps = patch_fingerprints(patch)
    for name, value in fps.items():
        if patch.get(name) != value:
            errors.append(f"{name} fingerprint mismatch")
    body = {k: v for k, v in patch.items() if k != "fingerprint"}
    if patch.get("fingerprint") != _sha256(body):
        errors.append("overall fingerprint mismatch")
    return errors


@dataclass(frozen=True)
class PatchPlan:
    insert_needed: tuple[Key, ...]
    update_needed: tuple[Key, ...]
    already_applied_keys: tuple[Key, ...]
    blocked: tuple[dict[str, Any], ...]

    @property
    def would_apply(self) -> bool:
        return not self.blocked and bool(self.insert_needed or self.update_needed)

    @property
    def already_applied(self) -> bool:
        return not self.blocked and not self.insert_needed and not self.update_needed


def _values_equal(a: Sequence[Any], b: Sequence[Any]) -> bool:
    return [None if x is None else x for x in a] == [None if x is None else x for x in b]


def plan_apply(patch: Mapping[str, Any], current_rows: Mapping[Key, Values]) -> PatchPlan:
    inserts: list[Key] = []
    updates: list[Key] = []
    applied: list[Key] = []
    blocked: list[dict[str, Any]] = []

    for row in patch["insert_rows"]:
        key, pg_values = _insert_key(row), tuple(row[3:8])
        current = current_rows.get(key)
        if current is None:
            inserts.append(key)
        elif _values_equal(current, pg_values):
            applied.append(key)
        else:
            blocked.append({"key": key, "reason": "insert_key_present_with_unexpected_values"})

    for entry in patch["update_rows"]:
        key = _update_key(entry)
        pg_values, preimage = tuple(entry["pg"]), tuple(entry["local_preimage"])
        current = current_rows.get(key)
        if current is None:
            blocked.append({"key": key, "reason": "update_key_missing_locally"})
        elif _values_equal(current, pg_values):
            applied.append(key)
        elif _values_equal(current, preimage):
            updates.append(key)
        else:
            blocked.append({"key": key, "reason": "update_key_matches_neither_preimage_nor_pg"})

    return PatchPlan(
        insert_needed=tuple(sorted(inserts)),
        update_needed=tuple(sorted(updates)),
        already_applied_keys=tuple(sorted(applied)),
        blocked=tuple(sorted(blocked, key=lambda b: b["key"])),
    )
