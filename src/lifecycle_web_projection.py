"""Closed, provider-free Web readbacks shared by the UI and Research tools."""

import sqlite3

from src.lifecycle_web_schema import RUNNING, verify_web_journal
from src.lifecycle_web_store import LifecycleWebStore
from src.lifecycle_source_context import parse_source_context
from src.security_lifecycle_provider_snapshot import instant


def project_web_run(row, *, at):
    """No local credential, worker, remote identifier or full page in the DTO."""
    status, failure = row["status"], row["failure_code"]
    if status in RUNNING and instant(row["lease_until"]) <= instant(at):
        status = "remote_outcome_unknown" if any(call["terminal"] is None for call in row["calls"].values()) else "failed"
        failure = "web_execution_interrupted"
    elif status in RUNNING and row["cancel_requested_at"] is not None:
        status = "cancelling"
    validated = row["finding"]
    reading = None
    if "source_context" in row:
        contexts = parse_source_context(row["source_context"], row["pages"])
        reading = {"sources": len(contexts),
                   "selected_sources": sum(value.ranges != ((0, value.source_bytes),) for value in contexts.values()),
                   "retained_text_bytes": sum(value.source_bytes for value in contexts.values()),
                   "model_text_bytes": sum(end - start for value in contexts.values() for start, end in value.ranges)}
    finding = None
    if validated is not None:
        value = validated.finding
        finding = {key: getattr(value, key) for key in (
            "source_ticker", "issuer_name", "security_class", "venue", "event_kind", "timing", "summary",
            "successor_ticker", "effective_date", "announcement_date", "contradictions", "unresolved_conditions")}
        finding.update(action=validated.action, block_reasons=list(validated.block_reasons),
                       unique_passage_count=validated.unique_passage_count,
                       independent_source_count=validated.independent_source_count,
                       citations=[{"url": passage.source_url, "quote": passage.excerpt, "retrieved_at": passage.retrieved_at}
                                  for passage in validated.passages])
    return {
        "version": 1, "run_id": row["run_id"], "case_id": row["case_id"], "ticker": row["request"].ticker,
        "status": status, "phase": row["status"] if row["status"] in RUNNING else None,
        "created_at": row["created_at"], "finished_at": row["finished_at"], "failure_code": failure,
        "cancel_requested_at": row["cancel_requested_at"],
        "execution": {key: getattr(row["selection"], key) for key in ("provider", "auth_mode", "model")},
        "model_submissions": len(row["calls"]), "source_requests": row.get("source_requests"),
        "usage": row.get("usage", {"input_tokens": None, "output_tokens": None}),
        "usage_report": row.get("usage_report"),
        "source_reading": reading,
        "source_reads": row["source_read_report"]["observations"] if "source_read_report" in row else None,
        "source_gaps": row["source_gaps"] if validated is not None else None,
        "finding": finding,
    }


def latest_web_runs(conn, case_ids, *, at):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name LIKE 'lifecycle_web_%'").fetchone():
        return []
    verify_web_journal(conn)
    if not case_ids:
        return []
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in case_ids)
    rows = conn.execute(f"""SELECT run_id FROM lifecycle_web_runs WHERE rowid IN
        (SELECT MAX(rowid) FROM lifecycle_web_runs WHERE case_id IN ({placeholders}) GROUP BY case_id)
        ORDER BY case_id""", list(case_ids)).fetchall()
    return [project_web_run(LifecycleWebStore.read_on_connection(conn, row[0], include_running_sources=False), at=at) for row in rows]
