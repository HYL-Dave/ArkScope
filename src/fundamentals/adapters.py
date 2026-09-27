"""Source observations only; selection, acquisition authority and ratios live elsewhere."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
import math
import re

from data_sources.financial_datasets_client import FinancialDatasetsClient
from data_sources.financial_datasets_governance import FinancialDatasetsFailure
from src.fundamentals.contracts import (
    FinancialGap, FinancialObservation, FinancialQuery, FinancialValue, Freshness, Provider, StatementKind,
)
from src.fundamentals.reuse import Observation, instant, policy
from src.fundamentals.source_comparison import METRICS, decimal, number, sa_records, source_value
from src.sa.company_data import CompanyDataFailure, digest
from src.sa.company_store import read_capture
from src.tools.schemas import FinancialStatement


STATEMENT_DATASETS = {"income_statement": "income_statements", "balance_sheet": "balance_sheets",
                      "cash_flow_statement": "cash_flow_statements"}
_IDENTITY_FIELDS = {"ticker", "report_period", "fiscal_period", "period", "currency", "input_basis_version"}


def to_financial_statement(obj) -> FinancialStatement:
    """Compatibility conversion for callers not yet using observation adapters."""
    return FinancialStatement(report_period=obj.report_period, fiscal_period=getattr(obj, "fiscal_period", None),
        period_type=getattr(obj, "period", "quarterly"), currency=getattr(obj, "currency", None),
        input_basis_version=getattr(obj, "input_basis_version", None),
        data={key: value for key, value in asdict(obj).items() if key not in _IDENTITY_FIELDS and value is not None})


def financial_profile(dal):
    try:
        profile = dal.get_user_profile()
        return profile if isinstance(profile, dict) else {}
    except Exception:
        return {}


def fd_cache_days(dal):
    try:
        config = financial_profile(dal).get("data_preferences", {}).get("paid_sources", {}).get("financial_datasets", {})
        return {period: config["cache_days_" + period] for period in ("annual", "quarterly")
                if "cache_days_" + period in config}
    except (TypeError, AttributeError):
        return {}


@dataclass
class ProviderRead:
    provider: Provider
    statements: dict[StatementKind, list[FinancialStatement]] = field(default_factory=dict)
    observations: list[FinancialObservation] = field(default_factory=list)
    gaps: list[FinancialGap] = field(default_factory=list)


def _gap(result, code, statement, metric=None, required_inputs=()):
    result.gaps.append(FinancialGap(provider=result.provider, code=code, dataset=statement,
                                    metric=metric, required_inputs=list(required_inputs)))


def _kinds(query):
    return [query.statement] if query.statement else list(STATEMENT_DATASETS)


def _metadata(value):
    allowed = FinancialValue.model_fields
    return FinancialValue(**{key: item for key, item in value.items() if key in allowed})


def _valid_records(records):
    # Refuse the dataset instead of promoting an older column after a bad newest one.
    for record in records:
        month = record["end_month"]
        if not re.fullmatch(r"\d{4}-\d{2}", month) or date.fromisoformat(month + "-01").strftime("%Y-%m") != month:
            return "financial_period_missing"
    if any(count > 1 for count in Counter(r["end_month"] for r in records).values()):
        return "financial_period_ambiguous"
    return None


def read_sa_statements(dal, query: FinancialQuery) -> ProviderRead:
    result = ProviderRead("seeking_alpha")
    path = getattr(getattr(dal, "_backend", None), "_sa_db", None)
    for kind in _kinds(query):
        result.statements[kind] = []
        try:
            body = read_capture(query.ticker, kind, query.period, query.currency,
                                observation_id=query.observation_id, db_path=path)
            if body is None:
                _gap(result, "financial_observation_missing" if query.observation_id else "sa_company_capture_missing", kind)
                continue
            records = sa_records(body, query.period)
            error = _valid_records(records)
            if error:
                _gap(result, error, kind)
                continue
            acquired = instant(body["last_captured_at"])
            if acquired is None:
                raise CompanyDataFailure("sa_company_observation_invalid")
            desc = Observation(None, acquired, datetime.now(timezone.utc)).describe(
                "seeking_alpha", kind, policy("stored", query.max_age_seconds))
            result.observations.append(FinancialObservation(**desc, observation_id=body["observation_id"],
                source_url=body["source_url"], first_captured_at=body["first_captured_at"],
                report_periods=[r["end_month"] for r in records], history="retained_observation"))
            source = dict(provider="seeking_alpha", status="ok", records=records)
            for record in sorted(records, key=lambda row: row["end_month"], reverse=True):
                values = {metric: _metadata(source_value(source, metric, label, unit, record["end_month"]))
                          for metric, label, unit in METRICS[kind]}
                for metric, value in values.items():
                    if value.status != "value":
                        _gap(result, value.status, kind, metric)
                result.statements[kind].append(FinancialStatement(
                    period_type=query.period, currency=body["currency"], end_month=record["end_month"],
                    period_precision="month", provider="seeking_alpha", observation_id=body["observation_id"],
                    column_index=record["column_index"], unit_note=body["unit_note"], value_metadata=values,
                    data={key: value.normalized_value if value.status == "value" else None for key, value in values.items()},
                    raw_reference=dict(tool="get_sa_company_data", ticker=body["ticker"], statement=kind,
                                       period=query.period, currency=body["currency"], observation_id=body["observation_id"]),
                ))
        except CompanyDataFailure as exc:
            _gap(result, exc.code, kind)
        except (ValueError, TypeError, KeyError, AttributeError):
            result.statements[kind] = []
            result.observations = [o for o in result.observations if o.dataset != kind]
            _gap(result, "sa_company_observation_invalid", kind)
    return result


def _fd_statement(obj, kind, result, query):
    raw = asdict(obj)
    declared = raw.get("currency")
    currency = declared if isinstance(declared, str) and re.fullmatch(r"[A-Z]{3}", declared) else None
    if currency is None or currency != query.currency:
        _gap(result, "currency_unknown" if currency is None else "currency_mismatch", kind)
    values, data = {}, {}
    per_share = {m for m, _, unit in METRICS.get(kind, ()) if unit == "per_share"}
    for metric, value in raw.items():
        if metric in _IDENTITY_FIELDS:
            continue
        numeric = decimal(value) if type(value) in (int, float) else None
        finite = numeric is not None and math.isfinite(float(numeric))
        status = "value" if finite else "metric_missing" if value is None else "invalid_value"
        values[metric] = FinancialValue(status=status, raw=value if finite or type(value) is str else None,
            normalized_value=number(numeric) if finite else None, scale="1" if finite else None,
            currency=currency, unit=(currency or "currency_unknown") + ("/share" if metric in per_share else ""),
            label=metric, precision="provider_numeric_float")
        data[metric] = float(numeric) if finite else None
        if status == "invalid_value":
            _gap(result, status, kind, metric)
    return FinancialStatement(report_period=obj.report_period, end_month=obj.report_period[:7],
        fiscal_period=obj.fiscal_period, period_type=obj.period, currency=currency,
        input_basis_version=obj.input_basis_version, period_precision="day", provider="financial_datasets",
        value_metadata=values, data=data)


def read_fd_statements(dal, query: FinancialQuery, *, mode: Freshness = "stored",
                       max_age_seconds: int | None = None, request_policy: dict | None = None,
                       retained: ProviderRead | None = None) -> ProviderRead:
    result = ProviderRead("financial_datasets")
    client = FinancialDatasetsClient(cache_backend=getattr(dal, "_backend", None), request_policy=request_policy,
                                    cache_days=fd_cache_days(dal) if mode != "stored" else None)
    readers = {"income_statement": client.get_income_statements, "balance_sheet": client.get_balance_sheets,
               "cash_flow_statement": client.get_cash_flow_statements}
    pending = list(_kinds(query))
    refusal = None
    for kind in pending:
        result.statements[kind] = []
        cached = next((o for o in retained.observations if o.dataset == kind), None) if retained else None
        if mode == "auto" and cached and cached.within_max_age is True and retained.statements.get(kind):
            result.statements[kind] = retained.statements[kind]
            result.observations.append(cached)
            result.gaps.extend(g for g in retained.gaps if g.dataset == kind)
            continue
        if refusal:
            _gap(result, "financial_datasets_not_attempted_after_refusal", kind)
            continue
        limit = 1 if kind == "balance_sheet" else 4 if query.period == "quarterly" else 2
        try:
            objects = readers[kind](query.ticker, period=query.period, limit=limit,
                                   freshness=mode, max_age_seconds=max_age_seconds if mode != "stored" else None)
            rows = [_fd_statement(obj, kind, result, query) for obj in objects]
            error = _valid_records([dict(end_month=row.end_month) for row in rows])
            if error:
                _gap(result, error, kind)
                continue
            desc = dict(client.observations[-1], dataset=kind)
            if mode == "stored":
                maximum = max_age_seconds if max_age_seconds is not None else query.max_age_seconds
                desc.update(max_age_seconds=maximum,
                            within_max_age=None if maximum is None else 0 <= desc["age_seconds"] <= maximum)
            identity = digest(dict(statements=[r.model_dump() for r in rows], fetched_at=desc["fetched_at"]))
            result.observations.append(FinancialObservation(**desc, observation_id=identity,
                history="current_retained_version_only" if desc["persisted"] else "not_retained"))
            for row in rows:
                row.observation_id = identity
            result.statements[kind] = sorted(rows, key=lambda row: row.report_period, reverse=True)
            if not desc["persisted"]:
                _gap(result, "financial_retention_failed", kind)
        except FinancialDatasetsFailure as exc:
            _gap(result, exc.code, kind)
            if mode != "stored":
                refusal = exc.code
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            _gap(result, "financial_read_result_invalid", kind)
            if mode != "stored":
                refusal = "financial_read_result_invalid"
    return result
