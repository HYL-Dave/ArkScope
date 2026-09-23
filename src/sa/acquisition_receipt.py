"""Bounded public acquisition identity; secrets stay in the native authority."""

import math
import re

from src.sa.extension_run_protocol import ProtocolError


_KEYS = {"schema_version", "ledger_id", "browser", "client_id", "build", "protocol_version", "generation",
         "task_id", "batch_id", "priority", "trigger", "navigation_attempt_count", "queue_wait_ms",
         "acquisition_duration_ms", "identity_basis"}


def project_acquisition(value):
    def require(condition):
        if not condition:
            raise ProtocolError("acquisition_unverified")

    require(type(value) is dict and set(value) == _KEYS)
    require(type(value["schema_version"]) is int and value["schema_version"] == 1
            and type(value["protocol_version"]) is int and value["protocol_version"] == 2)
    for key in ("ledger_id", "task_id"):
        require(type(value[key]) is str and re.fullmatch(r"[a-f0-9]{32}", value[key]))
    require(type(value["client_id"]) is str and re.fullmatch(r"[a-f0-9-]{32,36}", value["client_id"]))
    require(type(value["batch_id"]) is str and re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value["batch_id"]))
    require(type(value["build"]) is str and 0 < len(value["build"]) <= 128)
    require(value["browser"] in {"chrome", "firefox"} and value["priority"] in {"routine", "background"}
            and value["trigger"] in {"manual", "alarm", "startup", "continuation"}
            and value["identity_basis"] == "native_task_admission")
    for key in ("generation", "navigation_attempt_count"):
        require(type(value[key]) is int and value[key] >= (1 if key == "generation" else 0))
    for key in ("queue_wait_ms", "acquisition_duration_ms"):
        require(type(value[key]) in (int, float) and math.isfinite(value[key]) and value[key] >= 0)
    return dict(value)


def validate_event_acquisition(result, value, *, present):
    if not present:
        if result["schema_version"] == 1:
            return None
        if not result["item_outcomes"] and all(p["state"] in {"skipped", "deferred"} for p in result["phases"].values()):
            return None
        raise ProtocolError("acquisition_unverified")
    if result["schema_version"] != 2:
        raise ProtocolError("acquisition_unverified")
    projection = project_acquisition(value)
    from src.sa.company_collector import CompanyCollector

    if not CompanyCollector().verify_receipt(projection, result):
        raise ProtocolError("acquisition_unverified")
    return projection
