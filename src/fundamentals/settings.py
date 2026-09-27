"""Profile-owned financial output and acquisition scope, separate from consent."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

from src.data_source_routing import DataSourcePolicyFailure, read_setting


FINANCIAL_READ_SETTINGS_KEY = "data_sources.financial_read.settings"
PeriodCount = Annotated[StrictInt, Field(gt=0, lt=2**31)]


class StatementPeriods(BaseModel):
    model_config = ConfigDict(extra="forbid")
    income_statement: PeriodCount
    balance_sheet: PeriodCount
    cash_flow_statement: PeriodCount


class FinancialPeriods(BaseModel):
    model_config = ConfigDict(extra="forbid")
    annual: StatementPeriods
    quarterly: StatementPeriods


class FinancialReadSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Zero disables this tool's cap, not the model's context limit.
    tool_output_chars: Annotated[StrictInt, Field(ge=0, lt=2**53)]
    fd_periods: FinancialPeriods


def default_settings() -> FinancialReadSettings:
    return FinancialReadSettings(
        tool_output_chars=48_000,
        fd_periods=FinancialPeriods(
            annual=StatementPeriods(income_statement=2, balance_sheet=1, cash_flow_statement=2),
            quarterly=StatementPeriods(income_statement=4, balance_sheet=1, cash_flow_statement=4),
        ),
    )


def parse_settings(raw: str | None) -> FinancialReadSettings:
    if raw is None:
        return default_settings()
    try:
        return FinancialReadSettings.model_validate_json(raw, strict=True)
    except (ValidationError, TypeError, ValueError) as exc:
        raise DataSourcePolicyFailure("financial_read_settings_invalid") from exc


def load_settings(dal=None) -> FinancialReadSettings:
    return parse_settings(read_setting(FINANCIAL_READ_SETTINGS_KEY, dal))


def settings_view(raw: str | None) -> dict:
    view = {
        "values": None,
        "defaults": default_settings().model_dump(),
        "setting_source": "profile" if raw is not None else "default",
        "error_code": None,
    }
    try:
        view["values"] = parse_settings(raw).model_dump()
    except DataSourcePolicyFailure as exc:
        view["error_code"] = exc.code
    return view
