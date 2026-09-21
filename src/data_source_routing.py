"""Operator-selected sources for the implemented financial tool paths."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3

from src.app_records_store import resolve_profile_state_db_path


ROUTE_PREFIX = "data_sources.route."
FD_POLICY_KEY = "data_sources.financial_datasets.request_policy"


class DataSourcePolicyFailure(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SourceDataset:
    providers: tuple[str, ...]
    consumers: tuple[str, ...]
    unimplemented: tuple[str, ...] = ()


DATASETS = {
    "fundamentals_analysis": SourceDataset(
        ("sec_edgar", "financial_datasets"), ("get_fundamentals_analysis",),
        ("massive", "seeking_alpha"),
    ),
    "detailed_financials": SourceDataset(("sec_edgar",), ("get_detailed_financials",)),
    "earnings_supplements": SourceDataset(("finnhub",), ("get_detailed_financials",)),
    "sa_company_financials": SourceDataset(("seeking_alpha",), ("get_sa_company_data",)),
}
SOURCE_ACCESS = {
    "sec_edgar": "public_identity",
    "financial_datasets": "metered_requests",
    "finnhub": "endpoint_entitlement_unverified",
    "seeking_alpha": "signed_in_browser_subscription",
}


@dataclass(frozen=True)
class SourceRoute:
    dataset: str
    providers: tuple[str, ...]
    setting_source: str

    def candidates(self, requested="auto"):
        if type(requested) is not str or requested not in ("auto", *DATASETS[self.dataset].providers):
            raise DataSourcePolicyFailure("data_source_unsupported")
        if requested != "auto" and requested not in self.providers:
            raise DataSourcePolicyFailure("data_source_not_selected")
        if not self.providers:
            raise DataSourcePolicyFailure("data_source_route_disabled")
        return self.providers if requested == "auto" else (requested,)

    def describe(self, requested="auto", selected=None):
        return {
            "dataset": self.dataset, "requested": requested,
            "configured_sources": list(self.providers), "selected_source": selected,
            "setting_source": self.setting_source, "selection_policy": "local_first_ordered",
        }


def validate_sources(dataset, providers):
    if dataset not in DATASETS:
        raise DataSourcePolicyFailure("data_source_dataset_unknown")
    if (type(providers) is not list
            or any(type(item) is not str or item not in DATASETS[dataset].providers for item in providers)
            or len(set(providers)) != len(providers)):
        raise DataSourcePolicyFailure("data_source_policy_invalid")
    return tuple(providers)


def parse_route(dataset, raw):
    if dataset not in DATASETS:
        raise DataSourcePolicyFailure("data_source_dataset_unknown")
    if raw is None:
        return SourceRoute(dataset, DATASETS[dataset].providers, "default")
    try:
        providers = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise DataSourcePolicyFailure("data_source_policy_invalid") from exc
    return SourceRoute(dataset, validate_sources(dataset, providers), "profile")


def read_setting(key, dal=None):
    """No store constructor: even a first stored-only read must not create a DB."""
    path = Path(resolve_profile_state_db_path(dal)).expanduser().resolve()
    conn = None
    try:
        try:
            path.stat()
        except FileNotFoundError:
            return None
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
        conn.execute("PRAGMA query_only=ON")
        row = conn.execute("SELECT value FROM profile_settings WHERE key=?", (key,)).fetchone()
        return row[0] if row is not None else None
    except (OSError, sqlite3.Error) as exc:
        raise DataSourcePolicyFailure("data_source_settings_unavailable") from exc
    finally:
        if conn is not None:
            conn.close()


def load_route(dataset, dal=None):
    return parse_route(dataset, read_setting(ROUTE_PREFIX + dataset, dal))


def route_view(dataset, raw):
    definition = DATASETS[dataset]
    view = {
        "dataset": dataset, "consumers": list(definition.consumers),
        "options": [{"provider": provider, "access": SOURCE_ACCESS[provider]}
                    for provider in definition.providers],
        "unimplemented": list(definition.unimplemented),
        "providers": None, "setting_source": "profile" if raw is not None else "default",
        "error_code": None,
    }
    try:
        view["providers"] = list(parse_route(dataset, raw).providers)
    except DataSourcePolicyFailure as exc:
        view["error_code"] = exc.code
    return view


def validate_fd_policy(value):
    keys = {"enabled", "daily_request_limit", "requests_per_minute"}
    if not isinstance(value, dict) or set(value) != keys or type(value["enabled"]) is not bool:
        raise DataSourcePolicyFailure("financial_datasets_policy_invalid")
    for key in keys - {"enabled"}:
        limit = value[key]
        if limit is None and not value["enabled"]:
            continue
        if type(limit) is not int or not 0 < limit < 2**63:
            raise DataSourcePolicyFailure("financial_datasets_policy_invalid")
    return dict(value)


def fd_policy_from_settings(raw, profile):
    if raw is not None:
        try:
            return validate_fd_policy(json.loads(raw))
        except (TypeError, ValueError) as exc:
            raise DataSourcePolicyFailure("financial_datasets_policy_invalid") from exc
    preferences = profile.get("data_preferences") if isinstance(profile, dict) else None
    paid = preferences.get("paid_sources") if isinstance(preferences, dict) else preferences
    return paid.get("financial_datasets") if isinstance(paid, dict) else paid


def fd_policy_view(raw, profile):
    from data_sources.financial_datasets_governance import FinancialDatasetsFailure, FinancialDatasetsPolicy

    view = {
        "enabled": None, "daily_request_limit": None, "requests_per_minute": None,
        "setting_source": "profile" if raw is not None else "default",
        "state": "invalid", "error_code": None,
    }
    try:
        policy = fd_policy_from_settings(raw, profile)
        if isinstance(policy, dict):
            for key in ("enabled", "daily_request_limit", "requests_per_minute"):
                value = policy.get(key)
                if ((key == "enabled" and type(value) is bool)
                        or (key != "enabled" and type(value) is int and 0 < value < 2**63)):
                    view[key] = value if key == "enabled" else str(value)
        FinancialDatasetsPolicy.from_config(policy)
        view["state"] = "enabled"
    except (DataSourcePolicyFailure, FinancialDatasetsFailure) as exc:
        view["error_code"] = exc.code
        view["state"] = {
            "financial_datasets_paid_requests_disabled": "disabled",
            "financial_datasets_policy_unconfigured": "unconfigured",
        }.get(exc.code, "invalid")
    return view
