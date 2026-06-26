"""PG → local app-records migration (PG-exit 1c) — reports / memories / agent_queries.

These are the irreplaceable, PG-only records. The migration is ID-PRESERVING (gate #2:
``ai_card_runs.saved_report_id`` references report ids — changing ids would break card→report
links) and split into a **dry-run preview** and an explicit **apply** (gate #5). Apply backs up
``profile_state.db`` first (gate #4) and refuses to clobber (gate #3: a same-id-different-content
row fails the whole run; a same-id-same-content row is an idempotent skip; new ids insert).

This module reads the PG side through a ``source`` abstraction so 1c-core is fully testable with a
fake (no live PG). The live PG source (raw ``SELECT *``) lands in 1c-live. NOT included: the
legacy ``signals`` table (dead-path cleanup, separate).

A ``source`` exposes, per table, a list of full row dicts with the SAME column names as the local
schema (id + all columns; ``created_at`` already rendered 'YYYY-MM-DDTHH:MM:SS', tickers/tags as
JSON text so they hash identically to the migrated local rows):
    source.fetch_reports() / fetch_memories() / fetch_agent_queries()
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.app_records_store import AppRecordsLocalStore

logger = logging.getLogger(__name__)

# (table, source fetch method, local insert method, file_path column or None)
_PLAN = [
    ("research_reports", "fetch_reports", "insert_report", "file_path"),
    ("agent_memories", "fetch_memories", "insert_memory", "file_path"),
    ("agent_queries", "fetch_agent_queries", "insert_agent_query", None),
]

# Stable identity-vs-content fields per table: enough to tell "same row re-migrated"
# (idempotent skip) from "a DIFFERENT row already sits at this id" (hard fail).
_HASH_FIELDS = {
    "research_reports": ["title", "created_at", "summary", "conclusion", "file_path"],
    "agent_memories": ["title", "created_at", "content", "category"],
    "agent_queries": ["question", "created_at", "answer"],
}


def _content_hash(table: str, row: Dict[str, Any]) -> str:
    raw = "|".join("" if row.get(f) is None else str(row.get(f)) for f in _HASH_FIELDS[table])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _insert_kwargs(table: str, row: Dict[str, Any]) -> Dict[str, Any]:
    """Map a raw source row → the local insert method's kwargs (id-preserving). tickers/tags
    arrive as JSON text or list; the local insert re-serializes, so pass through as lists."""
    from src.app_records_store import _list  # JSON-text/list tolerant
    common = {"id": row["id"], "created_at": row.get("created_at")}
    if table == "research_reports":
        return {**common, "title": row.get("title"), "tickers": _list(row.get("tickers")),
                "report_type": row.get("report_type"), "summary": row.get("summary"),
                "conclusion": row.get("conclusion"), "confidence": row.get("confidence"),
                "provider": row.get("provider"), "model": row.get("model"),
                "file_path": row.get("file_path"), "tools_used": _list(row.get("tools_used")),
                "tool_calls": row.get("tool_calls"), "duration_seconds": row.get("duration_seconds"),
                "tokens_in": row.get("tokens_in"), "tokens_out": row.get("tokens_out")}
    if table == "agent_memories":
        return {**common, "title": row.get("title"), "content": row.get("content"),
                "category": row.get("category") or "note", "tickers": _list(row.get("tickers")),
                "tags": _list(row.get("tags")), "importance": row.get("importance") or 5,
                "source": row.get("source"), "provider": row.get("provider"),
                "model": row.get("model"), "file_path": row.get("file_path"),
                "expires_at": row.get("expires_at")}
    return {**common, "question": row.get("question"), "answer": row.get("answer"),
            "provider": row.get("provider"), "model": row.get("model"),
            "tools_used": _list(row.get("tools_used")), "duration_ms": row.get("duration_ms"),
            "tokens_in": row.get("tokens_in"), "tokens_out": row.get("tokens_out")}


def _classify(table: str, source_rows: List[Dict], local_rows: List[Dict]) -> Dict[str, Any]:
    """Per-table dry-run classification (no writes)."""
    local_by_id = {int(r["id"]): _content_hash(table, r) for r in local_rows}
    to_insert, idempotent_skip, conflicts = [], [], []
    for row in source_rows:
        rid = int(row["id"])
        if rid not in local_by_id:
            to_insert.append(rid)
        elif local_by_id[rid] == _content_hash(table, row):
            idempotent_skip.append(rid)        # same id + same content → safe re-run
        else:
            conflicts.append(rid)              # same id, DIFFERENT content → would clobber
    src_ids = [int(r["id"]) for r in source_rows]
    return {
        "pg_count": len(source_rows),
        "local_count": len(local_rows),
        "max_pg_id": max(src_ids) if src_ids else None,
        "max_local_id": max(local_by_id) if local_by_id else None,
        "to_insert": to_insert,
        "idempotent_skip": idempotent_skip,
        "conflicts": conflicts,                # ids that block apply
    }


def _missing_files(table: str, file_col: Optional[str], source_rows: List[Dict],
                   base: Optional[str]) -> List[str]:
    if not file_col:
        return []
    out = []
    for r in source_rows:
        fp = r.get(file_col)
        if not fp:
            continue
        p = Path(fp) if Path(fp).is_absolute() else Path(base or ".") / fp
        if not p.exists():
            out.append(fp)
    return out


def preview_migration(source: Any, local: AppRecordsLocalStore,
                      *, base: Optional[str] = None) -> Dict[str, Any]:
    """DRY-RUN (gate #5): classify every PG row against the local store, surface counts, max ids,
    conflicts, and missing markdown files. NO writes. ``would_apply`` is False iff any table has a
    same-id-different-content conflict (apply would refuse)."""
    tables: Dict[str, Any] = {}
    any_conflict = False
    for table, fetch, _insert, file_col in _PLAN:
        source_rows = list(getattr(source, fetch)())
        local_rows = local.raw_rows(table)
        cls = _classify(table, source_rows, local_rows)
        cls["missing_files"] = _missing_files(table, file_col, source_rows, base)
        any_conflict = any_conflict or bool(cls["conflicts"])
        tables[table] = cls
    return {"tables": tables, "would_apply": not any_conflict}


def backup_profile_state_db(db_path: str, dest: str) -> Optional[str]:
    """WAL-safe SQLite backup of profile_state.db before a migration write (gate #4)."""
    if not Path(db_path).exists():
        return None
    src = sqlite3.connect(db_path)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return dest


def apply_migration(source: Any, local: AppRecordsLocalStore, *, base: Optional[str] = None,
                    backup: bool = True, backup_path: Optional[str] = None,
                    now_stamp: Optional[str] = None) -> Dict[str, Any]:
    """APPLY (gate #5, explicit) — backup (gate #4) → conflict guard (gate #3) → id-preserving
    inserts (gate #2). Refuses (raises) before ANY write if the preview finds a conflict, so a
    partial clobber is impossible. Idempotent: re-running skips same-id-same-content rows.

    ``now_stamp`` names the backup file deterministically (the runtime can't call now() inside a
    workflow); defaults to a fixed suffix when omitted."""
    preview = preview_migration(source, local, base=base)
    if not preview["would_apply"]:
        blocked = {t: c["conflicts"] for t, c in preview["tables"].items() if c["conflicts"]}
        raise RuntimeError(f"migration refused — same-id-different-content conflicts: {blocked}")

    backup_made = None
    if backup:
        suffix = now_stamp or "pre-migrate"
        backup_made = backup_path or f"{local.db_path}.{suffix}.bak"
        backup_profile_state_db(local.db_path, backup_made)

    result: Dict[str, Any] = {"backup": backup_made, "tables": {}}
    for table, fetch, insert_name, _fc in _PLAN:
        source_rows = list(getattr(source, fetch)())
        cls = _classify(table, source_rows, local.raw_rows(table))
        to_insert = set(cls["to_insert"])
        insert: Callable = getattr(local, insert_name)
        inserted = 0
        for row in source_rows:
            if int(row["id"]) in to_insert:
                insert(**_insert_kwargs(table, row))
                inserted += 1
        result["tables"][table] = {"inserted": inserted, "skipped": len(cls["idempotent_skip"])}
    return result
