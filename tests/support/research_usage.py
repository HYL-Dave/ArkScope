"""Summarize a private research snapshot without publishing its contents.

This offline audit is not a product tool, a provider probe or a retirement rule.
Optional live verification reads only four research tables with query_only and
a table/column allowlist. No application stores, credentials or DAL are loaded.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sqlite3


COLUMNS = {
    "research_threads": ("id", "created_at"),
    "research_messages": ("id", "thread_id", "role", "content", "created_at", "tool_calls_json", "run_id", "provider", "model"),
    "research_runs": ("id", "thread_id", "status", "provider", "auth_mode", "created_at", "question"),
    "research_run_events": ("run_id", "seq", "type", "data_json", "created_at"),
}


def decode(value):
    return json.loads(value) if isinstance(value, str) else value


def project(tables):
    result = {}
    for table, columns in COLUMNS.items():
        rows = []
        for row in tables[table]:
            rows.append({key: decode(row[key]) if key.endswith("_json") and row[key] is not None else row[key]
                         for key in columns})
        result[table] = sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=True))
    return result


def fingerprint(tables):
    return hashlib.sha256(json.dumps(project(tables), sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def readonly_tables(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=ON")
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1

        def authorize(action, table, column, database, trigger):
            if action == sqlite3.SQLITE_READ:
                return sqlite3.SQLITE_OK if database == "main" and column in COLUMNS.get(table, ()) else sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_TRANSACTION) else sqlite3.SQLITE_DENY

        conn.set_authorizer(authorize)
        conn.execute("BEGIN")
        return {table: [dict(row) for row in conn.execute("SELECT " + ",".join(columns) + " FROM " + table)]
                for table, columns in COLUMNS.items()}
    finally:
        conn.rollback()
        conn.close()


def tool_name(value):
    if not isinstance(value, str):
        raise ValueError("tool name missing")
    for prefix in ("mcp__ark__", "tool_"):
        value = value.removeprefix(prefix)
    if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
        raise ValueError("unrecognized tool name shape")
    return value


def channel(run):
    provider, mode = run.get("provider"), run.get("auth_mode")
    return {("openai", "api_key"): "openai_api_key",
            ("anthropic", "api_key"): "anthropic_api_key",
            ("openai", "chatgpt_oauth"): "chatgpt_oauth",
            ("anthropic", "claude_code_oauth"): "claude_oauth"}.get((provider, mode), "unobserved")


def outcome(data):
    if data.get("is_error") is True:
        return "reported_error"
    try:
        body = decode(data.get("summary"))
    except (TypeError, ValueError):
        body = None
    if isinstance(body, dict) and body.get("status") in ("unavailable", "partial"):
        return "reported_" + body["status"]
    if data.get("is_error") is False:
        return "reported_success"
    return "unknown"


def summarize(tables, annotations, registered_names):
    tables = project(tables)
    messages = tables["research_messages"]
    users = [row for row in messages if row["role"] == "user"]
    labels = {int(key): value for key, value in annotations["by_message_id"].items()}
    if set(labels) != {row["id"] for row in users}:
        raise ValueError("topic labels must cover exactly the captured user messages")
    topics = []
    for name in sorted(set(labels.values())):
        selected = [row for row in users if labels[row["id"]] == name]
        topics.append({"topic": name, "messages": len(selected),
                       "distinct_thread_prompts": len({(row["thread_id"], row["content"].strip()) for row in selected}),
                       "threads": len({row["thread_id"] for row in selected})})
    topics.sort(key=lambda row: (-row["messages"], row["topic"]))

    runs = {row["id"]: row for row in tables["research_runs"]}
    if len(runs) != len(tables["research_runs"]):
        raise ValueError("duplicate run identity")
    events = defaultdict(list)
    identities = set()
    for event in tables["research_run_events"]:
        identity = (event["run_id"], event["seq"])
        if identity in identities or event["run_id"] not in runs:
            raise ValueError("duplicate event identity or unobserved run")
        identities.add(identity)
        events[event["run_id"]].append(event)

    stats = defaultdict(Counter)
    channels = defaultdict(Counter)
    header_channels = defaultdict(Counter)
    message_channels = defaultdict(Counter)
    calls = []
    for run_id, stream in events.items():
        pending = {}
        for event in sorted(stream, key=lambda event: event["seq"]):
            if event["type"] not in ("tool_start", "tool_end"):
                continue
            data = event["data_json"]
            name = tool_name(data["tool"])
            if event["type"] == "tool_start":
                call = {"name": name, "channel": channel(runs[run_id]), "outcome": "unknown"}
                calls.append(call)
                stats[name]["starts"] += 1
                channels[name][call["channel"]] += 1
                group = pending.setdefault(name, {"calls": [], "ends": [], "ambiguous": False})
                group["ambiguous"] |= bool(group["calls"])
                group["calls"].append(call)
            elif set(data) == {"tool"}:
                # Old native traces also emit result-less headers. They are not
                # a second invocation or evidence of successful completion.
                stats[name]["header_only_ends"] += 1
                header_channels[name][channel(runs[run_id])] += 1
            elif name not in pending:
                stats[name]["unpaired_ends"] += 1
            else:
                group = pending[name]
                group["ends"].append(data)
                if len(group["ends"]) == len(group["calls"]):
                    if group["ambiguous"]:
                        stats[name]["ambiguous_starts"] += len(group["calls"])
                    else:
                        group["calls"][0]["outcome"] = outcome(data)
                    del pending[name]
        for name, group in pending.items():
            stats[name]["incomplete_starts"] += len(group["calls"])
    for call in calls:
        stats[call["name"]][call["outcome"]] += 1

    unbound_messages = 0
    for message in messages:
        records = message["tool_calls_json"] or []
        if not isinstance(records, list):
            raise ValueError("invalid message tool records")
        for record in records:
            name = tool_name(record["name"])
            stats[name]["message_records"] += 1
            if message["run_id"] is None:
                unbound_messages += 1
            message_channels[name][channel(runs.get(message["run_id"], {}))] += 1
    rows = []
    for name in sorted(set(registered_names) | set(stats)):
        counts = stats[name]
        good, bad = counts["reported_success"], counts["reported_error"]
        row = {"tool": name, "registered": name in registered_names, **{key: counts[key] for key in (
            "starts", "reported_success", "reported_error", "reported_unavailable", "reported_partial", "unknown",
            "header_only_ends", "unpaired_ends", "ambiguous_starts", "incomplete_starts", "message_records",
        )}, "channels": dict(sorted(channels[name].items())),
               "header_channels": dict(sorted(header_channels[name].items())),
               "message_channels": dict(sorted(message_channels[name].items())),
               "flagged_completion_success_percent": round(100 * good / (good + bad), 2) if good + bad else None}
        rows.append(row)
    rows.sort(key=lambda row: (-row["starts"], -row["message_records"], row["tool"]))
    return {
        "schema_version": 1, "corpus_fingerprint": fingerprint(tables),
        "counts": {"threads": len(tables["research_threads"]), "messages": len(messages),
                   "user_messages": len(users), "runs": len(runs), "events": len(identities),
                   "message_tool_records": sum(row["message_records"] for row in rows),
                   "message_tool_records_without_run_link": unbound_messages},
        "run_channels": dict(sorted(Counter(channel(run) for run in runs.values()).items())),
        "run_statuses": dict(sorted(Counter(run["status"] for run in runs.values()).items())),
        "event_types": dict(sorted(Counter(event["type"] for event in tables["research_run_events"]).items())),
        "last_research_run_at": max(run["created_at"] for run in runs.values()),
        "topics": topics, "tools": rows,
        "unobserved_registered_tools": sorted(name for name in registered_names
            if not stats[name]["starts"] and not stats[name]["message_records"] and not stats[name]["header_only_ends"]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--verify-db", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    raw = args.snapshot.read_bytes()
    snapshot = json.loads(raw)
    result = summarize(snapshot["tables"], json.loads(args.annotations.read_text()), json.loads(args.registry.read_text()))
    result["snapshot_sha256"] = hashlib.sha256(raw).hexdigest()
    result["snapshot_utc"] = snapshot["captured_at"]
    if args.verify_db:
        current = fingerprint(readonly_tables(args.verify_db))
        if current != result["corpus_fingerprint"]:
            raise ValueError("current research differs from the annotated snapshot; do not claim current coverage")
        result["live_corpus_verified_equal"] = True
    args.output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n")
    print(json.dumps({"counts": result["counts"], "topics": result["topics"], "run_channels": result["run_channels"]}))


if __name__ == "__main__":
    main()
