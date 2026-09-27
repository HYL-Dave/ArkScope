"""A coherent local financial read; named, governed acquisition is a separate decision."""

from src.data_source_routing import (
    DataSourcePolicyFailure, FD_POLICY_KEY, fd_policy_from_settings, load_route, read_setting,
)
from src.fundamentals.adapters import (
    financial_profile, read_fd_statements, read_sa_statements,
)
from src.fundamentals.common_metrics import derive_common_metrics
from src.fundamentals.contracts import FinancialCoverage, FinancialGap, FinancialQuery
from src.fundamentals.reuse import ReuseFailure, configured_age, policy
from src.sa.company_data import CompanyDataFailure, digest, provider_symbol
from src.tools.schemas import FundamentalsResult


_FIELDS = {"income_statement": "income_statements", "balance_sheet": "balance_sheet",
           "cash_flow_statement": "cash_flow_statements"}


def _gap(code, provider="financials", **details):
    return FinancialGap(provider=provider, code=code, **details)


def _empty(query, gaps, route=None, choices=None):
    result = FundamentalsResult(ticker=query.ticker, income_statements=[], balance_sheet=[], cash_flow_statements=[],
        read_gaps=gaps, acquisition_gaps=_acquisition_gaps(gaps),
        source_routes=[route.describe(query.source)] if route else [], update_choices=choices or [])
    result.coverage = summarize_financials(result, query)
    return result


def _acquisition_gaps(gaps):
    return [{key: value for key, value in g.model_dump().items()
             if key in {"provider", "code", "dataset"} and value is not None} for g in gaps if not g.metric]


def _kinds(query):
    return [query.statement] if query.statement else list(_FIELDS)


def _has_rows(read):
    return any(read.statements.values())


def _fresh(read):
    return bool(read.observations) and all(o.within_max_age is True for o in read.observations)


def _complete(read, query):
    return all(read.statements.get(kind) for kind in _kinds(query))


def _choices(query, sources):
    choices = []
    for source in sources:
        if source == "financial_datasets":
            choices.append(dict(provider=source, action="explicit_refresh", requires_paid_admission=True))
        else:
            try:
                symbol = provider_symbol(query.ticker)
                urls = [f"https://seekingalpha.com/symbol/{symbol}/{kind.replace('_', '-')}"
                        for kind in _kinds(query)]
            except CompanyDataFailure:
                urls = []
            choices.append(dict(provider=source, action="browser_capture", capture_urls=urls,
                                status_url="/sa/acquisition-status", period=query.period,
                                currency=query.currency, requires_signed_in_browser=True))
    return choices


def _selected_rows(read, query):
    if query.end_month is None:
        return read.statements
    return {kind: [row for row in rows if row.end_month == query.end_month]
            for kind, rows in read.statements.items()}


def summarize_financials(result: FundamentalsResult, query: FinancialQuery) -> FinancialCoverage:
    """Summarize only the inspected selection, never a ticker inventory as coverage."""
    if result.coverage is not None:
        return result.coverage.model_copy(deep=True)
    rows = {kind: getattr(result, _FIELDS[kind]) or [] for kind in _kinds(query)}
    currencies = {row.currency for values in rows.values() for row in values}
    return FinancialCoverage(ticker=query.ticker, status=result.status,
        selected_source=result.data_source if result.data_source in {"seeking_alpha", "financial_datasets"} else None,
        period=query.period, requested_currency=query.currency,
        currency=next(iter(currencies)) if len(currencies) == 1 else None, read_id=result.read_id,
        statements={kind: [dict(end_month=row.end_month, report_period=row.report_period,
            period_precision=row.period_precision, currency=row.currency, observation_id=row.observation_id,
            column_index=row.column_index) for row in values] for kind, values in rows.items()},
        missing_statements=[kind for kind, values in rows.items() if not values],
        supported_metrics=list(result.metric_basis), metric_gaps=result.metric_gaps, gaps=result.read_gaps)


def _assemble(read, query, route, choices, extra=()):
    selected = _selected_rows(read, query)
    gaps = [*read.gaps, *extra]
    if not any(selected.values()):
        if query.end_month:
            gaps.append(_gap("financial_period_unavailable", read.provider))
        return _empty(query, gaps, route, choices)
    missing = [kind for kind in _kinds(query) if not selected.get(kind)]
    for kind in missing:
        if not any(g.dataset == kind for g in gaps):
            gaps.append(_gap("financial_statement_unavailable", read.provider, dataset=kind))
    # The identity covers the whole retained selection and metric inputs, not page slices or evaluation time.
    identity = digest(dict(version="common-financial-read-v1", ticker=query.ticker, period=query.period,
        provider=read.provider, currency=query.currency, statement=query.statement, end_month=query.end_month,
        observation_id=query.observation_id,
        statements={kind: [row.model_dump() for row in rows] for kind, rows in read.statements.items()}))
    if query.read_id is not None and identity != query.read_id:
        return _empty(query, [_gap("financial_read_changed", read.provider)], route, choices)

    # Historical metrics need an anchor at the requested month AND its retained earlier periods.
    metric_rows, currency_blocks = {}, set()
    for kind in _kinds(query):
        rows = read.statements.get(kind, []) if selected.get(kind) else []
        if query.end_month:
            rows = [row for row in rows if row.end_month <= query.end_month]
        if rows and rows[0].currency != query.currency:
            currency_blocks.add(kind)
            rows = []
        metric_rows[kind] = rows
    metrics = derive_common_metrics(*(metric_rows.get(kind, []) for kind in _FIELDS), source=read.provider)
    for key, basis in list(metrics["metric_basis"].items()):
        if any(ref.get("currency") != query.currency for ref in basis.get("input_observations", [])):
            metrics[key] = None
            metrics["metric_gaps"][key] = "currency_mismatch"
            del metrics["metric_basis"][key]
    for gap in metrics.pop("input_gaps"):
        kind = "balance_sheet" if gap.metric in {"total_debt", "cash_and_equivalents", "debt_to_equity", "current_ratio"} else (
            "cash_flow_statement" if gap.metric == "free_cash_flow" else "income_statement")
        if kind in currency_blocks:
            gap = gap.model_copy(update={"code": "currency_mismatch"})
            metrics["metric_gaps"][gap.metric] = gap.code
        gaps.append(gap)
    result = FundamentalsResult(ticker=query.ticker, status="partial" if missing else "ok",
        data_source=read.provider, read_id=identity,
        period_selection="retained_observation" if query.observation_id else "explicit_month" if query.end_month else "latest_stored",
        snapshot_date=next((rows[0].report_period for rows in selected.values() if rows), None),
        source_observations=[o.model_dump() for o in read.observations], source_routes=[route.describe(query.source, read.provider)],
        read_gaps=gaps, acquisition_gaps=_acquisition_gaps([*read.gaps, *extra]),
        update_choices=choices, **{_FIELDS[kind]: selected.get(kind, []) for kind in _FIELDS},
        **{key: value for key, value in metrics.items() if key in FundamentalsResult.model_fields})
    result.coverage = summarize_financials(result, query)
    count = max((len(rows) for rows in selected.values()), default=0)
    result.pagination = dict(offset=query.period_offset, limit=query.period_limit, total_periods=count,
                             has_more=query.period_offset + query.period_limit < count)
    for kind, field in _FIELDS.items():
        setattr(result, field, selected.get(kind, [])[query.period_offset:query.period_offset + query.period_limit])
    return result


def read_financials(dal, query: FinancialQuery) -> FundamentalsResult:
    if dal is None:
        from src.tools.data_access import DataAccessLayer
        dal = DataAccessLayer()
    pinned = query.end_month or query.observation_id or query.read_id
    if pinned and query.freshness != "stored":
        return _empty(query, [_gap("financial_historical_requires_stored")])
    if query.observation_id and (query.source != "seeking_alpha" or query.statement is None):
        return _empty(query, [_gap("financial_observation_scope_required")])
    if query.period_offset and not query.read_id:
        return _empty(query, [_gap("financial_read_id_required")])
    if query.freshness == "refresh" and query.source == "auto":
        return _empty(query, [_gap("financial_refresh_source_required")])
    try:
        age = configured_age(financial_profile(dal)) if query.freshness == "auto" and query.max_age_seconds is None else 0
        reuse = policy(query.freshness, query.max_age_seconds, default_age=age)
        route = load_route("fundamentals_analysis", dal)
        sources = route.candidates(query.source)
    except (DataSourcePolicyFailure, ReuseFailure) as exc:
        return _empty(query, [_gap(exc.code)])
    choices = _choices(query, sources)
    observed_query = query.model_copy(update={"max_age_seconds": reuse.max_age_seconds})
    target = sources[0]
    if query.freshness == "refresh" and target == "seeking_alpha":
        return _empty(query, [_gap("sa_browser_update_required", target)], route, choices)

    retained, chosen = {}, None
    if query.freshness != "refresh":
        for source in sources:
            value = read_sa_statements(dal, observed_query) if source == "seeking_alpha" else read_fd_statements(dal, observed_query)
            retained[source] = value
            if _has_rows(value) and (query.freshness == "stored" or _fresh(value)):
                chosen = value
                break
        if chosen is None:
            chosen = next((value for value in retained.values() if _has_rows(value)), None)
        if query.freshness == "stored":
            return _assemble(chosen, query, route, choices) if chosen else _empty(
                query, [g for value in retained.values() for g in value.gaps], route, choices)
        if chosen and _fresh(chosen) and _complete(chosen, query):
            return _assemble(chosen, query, route, choices)
        if target == "seeking_alpha" or (chosen and chosen.provider != target):
            extra = [_gap("sa_browser_update_required", "seeking_alpha")]
            return _assemble(chosen, query, route, choices, extra) if chosen else _empty(
                query, [g for value in retained.values() for g in value.gaps] + extra, route, choices)

    # Only the selected primary/explicit FD route reaches paid admission. SA failure is not authority.
    try:
        config = fd_policy_from_settings(read_setting(FD_POLICY_KEY, dal), financial_profile(dal))
    except DataSourcePolicyFailure as exc:
        extra = [_gap(exc.code, "financial_datasets")]
        return _assemble(chosen, query, route, choices, extra) if chosen else _empty(query, extra, route, choices)
    acquired = read_fd_statements(dal, observed_query, mode=query.freshness, max_age_seconds=reuse.max_age_seconds,
                                 request_policy=config, retained=retained.get("financial_datasets"))
    return _assemble(acquired, query, route, choices)
