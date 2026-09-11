"""Reported token scopes, separate from billing and investigation success."""

from src.auth_drivers.lifecycle_web_models import WebModelError, require_response_model


TOKEN_FIELDS = ("input_tokens", "output_tokens")
COUNTER_FIELDS = (*TOKEN_FIELDS, "cache_creation_input_tokens", "cache_read_input_tokens", "web_search_requests")
_MODEL_FIELDS = ("inputTokens", "outputTokens", "cacheCreationInputTokens", "cacheReadInputTokens", "webSearchRequests")
USAGE_BASES = frozenset({"claude_model_usage", "adapter_report", "unreported"})
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
