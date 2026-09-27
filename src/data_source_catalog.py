"""Capability metadata only; routing, schedules and entitlements keep their owners."""

from src.data_source_routing import DATASETS, SOURCE_ACCESS


def _source(provider, acquisition, access_requirement, *, controls=(), schedules=(), routes=None):
    return {
        "provider": provider,
        "integration": "candidate" if acquisition == "not_implemented" else "implemented",
        "acquisition": acquisition,
        "access_requirement": access_requirement,
        "controls": list(controls),
        "schedule_sources": list(schedules),
        "financial_routes": list(routes) if routes is not None else [
            name for name, route in DATASETS.items()
            if "financial_sources" in controls and provider in route.providers
        ],
    }


def _financial_sources():
    definition = DATASETS["fundamentals_analysis"]
    sources = [
        _source(provider, "browser_page_capture" if provider == "seeking_alpha" else "on_demand_api",
                SOURCE_ACCESS[provider], controls=("financial_sources", "sa_extension")
                if provider == "seeking_alpha" else ("financial_sources",),
                routes=("fundamentals_analysis", "sa_company_financials") if provider == "seeking_alpha" else None)
        for provider in definition.providers
    ]
    for provider in definition.unimplemented:
        requirement = "signed_in_browser_subscription" if provider == "seeking_alpha" else "endpoint_entitlement_unverified"
        sources.append(_source(provider, "not_implemented", requirement))
    return sources


def _sa_capture():
    return _source("seeking_alpha", "browser_extension", "signed_in_browser_subscription", controls=("sa_extension",))


def data_source_catalog():
    """Return fresh JSON metadata without opening stores or activating collectors."""
    return {
        "scope": "current_integrations_and_candidates",
        "categories": [
            {"id": "financial_statements", "sources": _financial_sources()},
            {"id": "valuation_ratings", "sources": [
                _source("seeking_alpha", "browser_page_capture", "signed_in_browser_subscription",
                        controls=("financial_sources", "sa_extension"), routes=("sa_company_valuation",)),
            ]},
            {"id": "earnings_estimates", "sources": [
                _source("seeking_alpha", "browser_page_capture", "signed_in_browser_subscription",
                        controls=("financial_sources", "sa_extension"), routes=("sa_company_estimates",)),
            ]},
            {"id": "current_quotes", "sources": [
                _source("ibkr", "gateway_snapshot", "gateway_market_access", controls=("connections",)),
            ]},
            {"id": "price_history", "sources": [
                _source("ibkr", "app_job", "gateway_market_access",
                        controls=("source_schedules", "price_coverage"), schedules=("ibkr_prices",)),
                _source("massive", "price_worker", "endpoint_entitlement_unverified", controls=("connections",)),
            ]},
            {"id": "news", "sources": [
                _source("massive", "app_job", "endpoint_entitlement_unverified",
                        controls=("source_schedules",), schedules=("polygon_news",)),
                _source("finnhub", "app_job", "endpoint_entitlement_unverified",
                        controls=("source_schedules",), schedules=("finnhub_news",)),
                _source("ibkr", "app_job", "gateway_news_access",
                        controls=("source_schedules",), schedules=("ibkr_news",)),
                _sa_capture(),
            ]},
            {"id": "company_events", "sources": [
                _source("finnhub", "app_job_and_on_demand", "endpoint_entitlement_unverified",
                        controls=("macro_schedules", "financial_sources"),
                        schedules=("finnhub_earnings_calendar", "finnhub_ipo_calendar")),
            ]},
            {"id": "macro", "sources": [
                _source("fred", "app_job", "api_key", controls=("macro_schedules",),
                        schedules=("fred_series", "fred_release_dates")),
                _source("finnhub", "app_job", "endpoint_entitlement_unverified",
                        controls=("macro_schedules",), schedules=("finnhub_economic_calendar",)),
            ]},
            {"id": "recommendations", "sources": [_sa_capture()]},
            {"id": "research_content", "sources": [_sa_capture()]},
            {"id": "holdings", "sources": [
                _source("ibkr", "account_capture", "gateway_account_access", controls=("connections",)),
            ]},
            {"id": "filings", "sources": [
                _source("sec_edgar", "local_and_opt_in_update", "public_identity",
                        controls=("sec_research", "source_schedules"), schedules=("sec_research_filings",)),
            ]},
        ],
    }
