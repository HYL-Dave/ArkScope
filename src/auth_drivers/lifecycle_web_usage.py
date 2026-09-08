"""Reported token scopes, separate from billing and investigation success."""

from src.auth_drivers.lifecycle_web_models import WebModelError, require_response_model


TOKEN_FIELDS = ("input_tokens", "output_tokens")
COUNTER_FIELDS = (*TOKEN_FIELDS, "cache_creation_input_tokens", "cache_read_input_tokens", "web_search_requests")
_MODEL_FIELDS = ("inputTokens", "outputTokens", "cacheCreationInputTokens", "cacheReadInputTokens", "webSearchRequests")
USAGE_BASES = frozenset({"claude_model_usage", "adapter_report", "unreported"})
USAGE_COVERAGE = frozenset({"complete", "partial", "unknown"})
# JSON integers must survive the Python -> browser boundary exactly. This is
# not a provider context limit or an application input/output budget.
_MAX_COUNTER = 2**53 - 1


def _counter(value):
    if value is not None and (type(value) is not int or not 0 <= value <= _MAX_COUNTER):
        raise WebModelError("model_usage_invalid")
    return value


def _counters(value, fields=COUNTER_FIELDS):
    if value is None:
        return dict.fromkeys(COUNTER_FIELDS)
    if type(value) is not dict:
        raise WebModelError("model_usage_invalid")
    return {key: _counter(value.get(source)) for key, source in zip(COUNTER_FIELDS, fields)}


def _sum(values, *, require_all):
    known = [value for value in values if value is not None]
    if not known or (require_all and len(known) != len(values)):
        return None
    return _counter(sum(known))


def token_totals(value):
    if type(value) is not dict or set(value) != set(TOKEN_FIELDS):
        raise WebModelError("model_usage_invalid")
    return {key: _counter(value[key]) for key in TOKEN_FIELDS}


def claude_usage_observation(message, selected):
    aggregate = message.model_usage
    if aggregate is not None and type(aggregate) is not dict:
        raise WebModelError("model_usage_invalid")
    rows = []
    for model, value in (aggregate or {}).items():
        require_response_model({"model": model}, selected)
        if type(value) is not dict:
            raise WebModelError("model_usage_invalid")
        rows.append(_counters(value, _MODEL_FIELDS))
    return {
        "basis": "claude_model_usage" if rows else "unreported",
        "values": {key: _sum([row[key] for row in rows], require_all=True) for key in COUNTER_FIELDS},
        "main_loop": None if message.usage is None else _counters(message.usage),
    }


def validate_usage_observation(value):
    if (type(value) is not dict or set(value) != {"basis", "values", "main_loop"}
            or not isinstance(value["basis"], str) or value["basis"] not in USAGE_BASES):
        raise WebModelError("model_usage_invalid")
    for counters in (value["values"], value["main_loop"]):
        if counters is not None and (type(counters) is not dict or set(counters) != set(COUNTER_FIELDS)):
            raise WebModelError("model_usage_invalid")
    if value["values"] is None:
        raise WebModelError("model_usage_invalid")
    result = {"basis": value["basis"], "values": _counters(value["values"]),
              "main_loop": None if value["main_loop"] is None else _counters(value["main_loop"])}
    if result["basis"] == "unreported" and any(count is not None for count in result["values"].values()):
        raise WebModelError("model_usage_invalid")
    if result["basis"] == "adapter_report" and result["main_loop"] is not None:
        raise WebModelError("model_usage_invalid")
    return result


def phase_usage(call, reply):
    if call.call_id != {"search": "search-1", "analysis": "analysis-1"}.get(call.phase):
        raise WebModelError("model_usage_invalid")
    observation = reply.usage_observation
    if observation is None:
        observation = {"basis": "adapter_report", "values": _counters(reply.usage), "main_loop": None}
    observation = validate_usage_observation(observation)
    if {key: observation["values"][key] for key in TOKEN_FIELDS} != token_totals(reply.usage):
        raise WebModelError("model_usage_invalid")
    return {"call_id": call.call_id, "remote_id": reply.remote_id, "observation": observation}


def validate_usage_report(value, calls):
    if (type(value) is not dict or set(value) != {"version", "phases"}
            or type(value["version"]) is not int or value["version"] != 1
            or type(value["phases"]) is not list or len(value["phases"]) > 2):
        raise WebModelError("model_usage_invalid")
    phases = []
    seen = set()
    for phase in value["phases"]:
        if type(phase) is not dict or set(phase) != {"call_id", "remote_id", "observation"}:
            raise WebModelError("model_usage_invalid")
        call_id = phase["call_id"]
        if (not isinstance(call_id, str) or call_id not in {"search-1", "analysis-1"}
                or call_id in seen or call_id not in calls or calls[call_id]["terminal"] != "completed"
                or not isinstance(phase["remote_id"], str) or not phase["remote_id"]
                or phase["remote_id"] != calls[call_id]["remote_id"]):
            raise WebModelError("model_usage_invalid")
        seen.add(call_id)
        phases.append({"call_id": call_id, "remote_id": phase["remote_id"],
                       "observation": validate_usage_observation(phase["observation"])})
    phases.sort(key=lambda phase: phase["call_id"] != "search-1")
    return {"version": 1, "phases": phases}


def project_usage_report(value, calls):
    report = validate_usage_report(value, calls)
    by_call = {phase["call_id"]: phase["observation"] for phase in report["phases"]}
    counters = [by_call[call_id]["values"] if call_id in by_call else dict.fromkeys(COUNTER_FIELDS) for call_id in calls]
    totals = {key: _sum([row[key] for row in counters], require_all=True) for key in TOKEN_FIELDS}
    subtotal = {key: _sum([row[key] for row in counters], require_all=False) for key in TOKEN_FIELDS}
    coverage = ("complete" if all(value is not None for value in totals.values()) else
                "partial" if any(value is not None for value in subtotal.values()) else "unknown")
    return {"version": 1, "recorded_submissions": len(by_call), "coverage": coverage,
            "totals": totals, "known_subtotal": subtotal,
            "phases": [{"phase": "search" if phase["call_id"] == "search-1" else "analysis",
                        "basis": phase["observation"]["basis"], **phase["observation"]["values"]}
                       for phase in report["phases"]]}
