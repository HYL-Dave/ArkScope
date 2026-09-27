"""Read-only financial identities and evidence, independent of acquisition owners."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Provider = Literal["seeking_alpha", "financial_datasets"]
StatementKind = Literal["income_statement", "balance_sheet", "cash_flow_statement"]
Period = Literal["annual", "quarterly"]
Freshness = Literal["stored", "auto", "refresh"]
ReadStatus = Literal["ok", "partial", "unavailable"]


class ReadContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class FinancialQuery(ReadContract):
    ticker: str = Field(min_length=1, max_length=32)
    period: Period = "annual"
    source: Literal["auto", "seeking_alpha", "financial_datasets"] = "auto"
    freshness: Freshness = "stored"
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    statement: StatementKind | None = None
    end_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    observation_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    read_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    period_offset: int = Field(default=0, ge=0)
    period_limit: int = Field(default=4, ge=1, le=8)
    max_age_seconds: int | None = Field(default=None, ge=0)

    @field_validator("ticker")
    @classmethod
    def normalized_ticker(cls, value: str) -> str:
        value = value.strip().upper()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("invalid ticker")
        return value

    @field_validator("end_month")
    @classmethod
    def real_month(cls, value: str | None) -> str | None:
        if value is not None:
            date.fromisoformat(value + "-01")
        return value


class FinancialGap(ReadContract):
    provider: str
    code: str
    dataset: str | None = None
    metric: str | None = None
    required_inputs: list[str] = Field(default_factory=list)


class FinancialValue(ReadContract):
    status: str
    raw: str | int | float | None = None
    normalized_value: str | None = None
    scale: str | None = None
    unit: str | None = None
    currency: str | None = None
    precision: str | None = None
    display_half_step: str | None = None
    label: str | None = None
    section: str | None = None

    @field_validator("normalized_value", "scale", "display_half_step")
    @classmethod
    def finite_decimal(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                if not Decimal(value).is_finite():
                    raise ValueError("nonfinite decimal")
            except InvalidOperation as exc:
                raise ValueError("invalid decimal") from exc
        return value


class FinancialObservation(ReadContract):
    provider: Provider
    dataset: str
    observation_id: str
    fetched_at: str
    evaluated_at: str
    age_seconds: float
    max_age_seconds: int | None = None
    within_max_age: bool | None = None
    freshness_mode: Freshness
    retrieval: Literal["stored", "refreshed", "coalesced"]
    persisted: bool
    source_url: str | None = None
    first_captured_at: str | None = None
    report_periods: list[str] = Field(default_factory=list)
    requested_periods: int | None = None
    configured_periods: int | None = None
    history: Literal["retained_observation", "current_retained_version_only", "not_retained"]


class FinancialCoverage(ReadContract):
    ticker: str
    status: ReadStatus
    selected_source: Provider | None = None
    period: Period
    requested_currency: str
    currency: str | None = None
    read_id: str | None = None
    statements: dict[StatementKind, list[dict]] = Field(default_factory=dict)
    missing_statements: list[StatementKind] = Field(default_factory=list)
    supported_metrics: list[str] = Field(default_factory=list)
    metric_gaps: dict[str, str] = Field(default_factory=dict)
    gaps: list[FinancialGap] = Field(default_factory=list)
