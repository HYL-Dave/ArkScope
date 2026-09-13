"""Pure tool-event projection shared by live Research and durable recovery."""

from collections.abc import Iterable
from copy import deepcopy


def _name(value):
    return value.removeprefix("mcp__ark__").removeprefix("tool_") if isinstance(value, str) else value


def accumulate_tool_calls(
    events: Iterable[tuple[str, dict]], *, tool_calls: list[dict] | None = None,
) -> list[dict]:
    """Project admitted events, optionally supplementing with a partial trace.

    IDs match exactly and the first completion wins on replay. Anonymous calls
    retain legacy last-open pairing, isolated from identified calls. Durable
    events take precedence over caller fields during recovery reconciliation.
    """
    rows: list[dict] = []
    identified: dict[str, int] = {}
    anonymous_open: list[int] = []
    completed: set[int] = set()
    for etype, data in events:
        if etype not in ("tool_start", "tool_end"):
            continue
        call_id = data.get("call_id")
        target = identified.get(call_id) if call_id is not None else None
        if call_id is None and etype == "tool_end" and anonymous_open:
            target = anonymous_open.pop()
        if target is None:
            target = len(rows)
            rows.append({"name": _name(data.get("tool")), "input": data.get("input"), "result_preview": None})
            if call_id is not None:
                identified[call_id] = target
                rows[target]["call_id"] = call_id
            elif etype == "tool_start":
                anonymous_open.append(target)
        row = rows[target]
        if target in completed:
            continue
        if row["input"] is None and "input" in data:
            row["input"] = data["input"]
        if etype == "tool_end":
            row["result_preview"] = data.get("summary")
            for field in ("sec_citations", "sec_citation_gaps"):
                if field in data:
                    row[field] = data[field]
            completed.add(target)

    if tool_calls:
        _reconcile_tool_calls(rows, identified, tool_calls)
    return deepcopy(rows)


def _reconcile_tool_calls(rows, identified, supplied):
    # Anonymous rows have no stable identity: pair equal name/input occurrences
    # once each, never by a position that could consume an identified call.
    anonymous = [index for index, row in enumerate(rows) if row.get("call_id") is None]
    for incoming in supplied:
        call_id = incoming.get("call_id")
        target = identified.get(call_id) if call_id is not None else next((
            index for index in anonymous
            if rows[index].get("name") == incoming.get("name")
            and rows[index].get("input") == incoming.get("input")
        ), None)
        if target is None:
            if call_id is not None:
                identified[call_id] = len(rows)
            rows.append(dict(incoming))
            continue
        if call_id is None:
            anonymous.remove(target)
        row = rows[target]
        for field, value in incoming.items():
            if field not in row or (row[field] is None and field in ("name", "input", "result_preview")):
                row[field] = value
