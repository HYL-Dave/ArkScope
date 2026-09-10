"""Prepare source SQL in disposable in-memory SQLite; never open product stores."""

from collections import defaultdict
import re
import sqlite3


def statements(text):
    pending = ""
    for part in text.split(";"):
        pending += part + ";"
        if sqlite3.complete_statement(pending):
            if pending.strip("; \n\t"):
                yield pending
            pending = ""
    if pending.strip("; \n\t"):
        yield pending


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def sql_inventory(sites):
    tables = defaultdict(lambda: {"columns": set(), "declarations": [], "reads": [],
                                  "writes": [], "read_columns": set(), "kinds": set()})
    unresolved, triggers, foreign_keys, queries = [], [], [], []
    for site in sites:
        where = {key: site[key] for key in ("path", "line")}
        if site.get("dynamic"):
            unresolved.append({**where, "kind": "dynamic_sql"})
            continue
        for statement in statements(site["text"]):
            statement = re.sub(r"\A\s*(?:(?:--[^\n]*\n|/\*.*?\*/)\s*)+", "", statement, flags=re.S)
            if re.match(r"\s*CREATE\s+(?:(?:TEMP|TEMPORARY|VIRTUAL)\s+)?TABLE\b", statement, re.I):
                conn = sqlite3.connect(":memory:")
                try:
                    conn.enable_load_extension(False)
                    conn.set_authorizer(lambda action, *_: sqlite3.SQLITE_DENY
                        if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH) else sqlite3.SQLITE_OK)
                    conn.execute(statement)
                    kinds = {row[1]: row[2] for row in conn.execute("PRAGMA table_list")}
                    for name, in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
                        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({quote(name)})")}
                        tables[name]["columns"].update(columns)
                        tables[name]["declarations"].append(where)
                        tables[name]["kinds"].add(kinds.get(name, "unknown"))
                        for edge in conn.execute(f"PRAGMA foreign_key_list({quote(name)})"):
                            foreign_keys.append({**where, "child": name, "parent": edge[2],
                                                 "child_column": edge[3], "parent_column": edge[4]})
                except sqlite3.Error as exc:
                    unresolved.append({**where, "kind": "ddl_parse_failed", "error_type": type(exc).__name__})
                finally:
                    conn.close()
            elif re.match(r"\s*CREATE\s+(?:TEMP(?:ORARY)?\s+)?TRIGGER\b", statement, re.I):
                triggers.append({**where, "statement": statement})
            elif re.match(r"\s*(?:SELECT|WITH|INSERT|REPLACE|UPDATE|DELETE|CREATE\s+VIEW)\b", statement, re.I):
                queries.append((where, statement))
            else:
                unresolved.append({**where, "kind": "unmodeled_sql_statement"})

    # The union schema makes literal queries preparable, not DB ownership provable.
    conn = sqlite3.connect(":memory:", cached_statements=0)
    for name, row in sorted(tables.items()):
        if row["columns"]:
            conn.execute(f"CREATE TABLE {quote(name)} ({','.join(quote(c) for c in sorted(row['columns']))})")
    active = {}
    trigger_sites = {}

    def authorize(action, first, second, _db, source):
        if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
            return sqlite3.SQLITE_DENY
        where = trigger_sites.get(source, active)
        if first in tables:
            event = {**where, "via_trigger": source} if source else dict(where)
            if action == sqlite3.SQLITE_READ:
                tables[first]["reads"].append(event)
                if second:
                    tables[first]["read_columns"].add(second)
            elif action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE):
                tables[first]["writes"].append(event)
        if action == sqlite3.SQLITE_CREATE_TRIGGER:
            trigger_sites[first] = dict(active)
        return sqlite3.SQLITE_OK

    conn.set_authorizer(authorize)
    for trigger in triggers:
        active = {key: trigger[key] for key in ("path", "line")}
        try:
            conn.execute(trigger["statement"])
        except sqlite3.Error as exc:
            unresolved.append({**active, "kind": "trigger_prepare_failed", "error_type": type(exc).__name__})
    compiled = 0
    for where, statement in queries:
        active = where
        # Refresh authorizer context so prepared-statement reuse cannot hide a site.
        conn.set_authorizer(authorize)
        try:
            conn.execute("EXPLAIN " + statement)
            compiled += 1
        except sqlite3.ProgrammingError as exc:
            # SQLite's authorizer ran during prepare, before parameter binding.
            if "Incorrect number of bindings supplied" in str(exc) or "You did not supply a value" in str(exc):
                compiled += 1
            else:
                unresolved.append({**where, "kind": "sql_prepare_failed", "error_type": type(exc).__name__})
        except sqlite3.Error as exc:
            unresolved.append({**where, "kind": "sql_prepare_failed", "error_type": type(exc).__name__})
    for name, row in sorted(tables.items()):
        active = {"path": "<trigger-probe>", "line": 0}
        column = next(iter(sorted(row["columns"])), None)
        if column is None:
            continue
        for statement in (f"INSERT INTO {quote(name)} DEFAULT VALUES",
                          f"UPDATE {quote(name)} SET {','.join(quote(c) + '=NULL' for c in sorted(row['columns']))}",
                          f"DELETE FROM {quote(name)}"):
            try:
                conn.execute("EXPLAIN " + statement)
            except sqlite3.Error:
                # Deferred trigger bodies may require UDFs or unmodeled tables.
                if trigger_sites:
                    unresolved.append({"path": "<trigger-probe>", "line": 0,
                                       "kind": "trigger_body_unresolved", "table": name})
    conn.close()
    rows = []
    for name, row in sorted(tables.items()):
        def unique(events):
            return [dict(items) for items in sorted({tuple(sorted(event.items())) for event in events
                    if event.get("path") != "<trigger-probe>"})]
        reads, writes = unique(row["reads"]), unique(row["writes"])
        rows.append({"table": name, "columns": sorted(row["columns"]),
                     "sqlite_table_kind": next(iter(row["kinds"])) if len(row["kinds"]) == 1 else "mixed",
                     "declarations": unique(row["declarations"]), "reads": reads, "writes": writes,
                     "read_columns": sorted(row["read_columns"]),
                     "columns_without_observed_read": sorted(row["columns"] - row["read_columns"]),
                     "state": "reader_observed" if reads else "no_static_reader_observed",
                     "database_scope": "not_resolved", "deletion_authorized": False})
    return {"tables": rows, "foreign_keys": foreign_keys,
            "triggers": [{k: v for k, v in item.items() if k != "statement"} for item in triggers],
            "coverage": {"sql_sites": len(sites), "literal_queries": len(queries),
                         "prepared_queries": compiled, "schema_tables": len(rows)},
            "unresolved": unresolved,
            "limitations": ["union schema is not database-scoped", "dynamic SQL is unresolved",
                            "absence of an observed read does not authorize dropping a table/column"]}
