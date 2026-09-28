"""Profile-owned circuit breaker for browser financial table validation."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

from src.data_source_routing import DataSourcePolicyFailure, read_setting


FINANCIAL_SETTINGS_KEY = "data_sources.sa_financial_acquisition.settings"


class FinancialAcquisitionSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    parser_failure_ticker_threshold: Annotated[StrictInt, Field(ge=0, lt=2**53)] = 3


def financial_settings_view(raw: str | None) -> dict:
    defaults = FinancialAcquisitionSettings().model_dump()
    result = {"values": None, "defaults": defaults,
              "setting_source": "profile" if raw is not None else "default", "error_code": None}
    try:
        result["values"] = defaults if raw is None else FinancialAcquisitionSettings.model_validate_json(raw, strict=True).model_dump()
    except (ValidationError, TypeError, ValueError):
        result["error_code"] = "sa_financial_settings_invalid"
    return result


def read_financial_settings() -> dict:
    return financial_settings_view(read_setting(FINANCIAL_SETTINGS_KEY))


def native_financial_settings() -> dict:
    try:
        return read_financial_settings()
    except DataSourcePolicyFailure as exc:
        return {"values": None, "error_code": exc.code}
