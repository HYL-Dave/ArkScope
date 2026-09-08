"""Public target binding, independent of case/SEC/SA existence."""

from contextlib import closing
from dataclasses import asdict
from datetime import date
from pathlib import Path
import sqlite3
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.auth_drivers.lifecycle_web_models import ModelCall, credential_generation
from src.lifecycle_investigation.runtime import RuntimeStore
from src.lifecycle_investigation.schema import verify_journal
from src.lifecycle_web_store import _sha
from src.model_capabilities import capability_for
from src.security_lifecycle_listing_evidence import _FACT_SECURITY_CLASSES, _FACT_VENUES
from src.security_lifecycle_provider_store import ProviderCheckStore
from src.security_lifecycle_review import now
from src.security_lifecycle_web_contract import validate_selection


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    ticker: str = Field(pattern=r"^[A-Z0-9]{1,8}(?:[ .-][A-Z0-9]{1,8})?$", max_length=20)
    issuer_name: str | None = Field(default=None, min_length=1, max_length=240)
    security_class: str | None = Field(default=None, min_length=1, max_length=120)
    venue: str | None = Field(default=None, min_length=1, max_length=120)
    issuer_cik: str | None = Field(default=None, pattern=r"^[0-9]{10}$")
    composite_figi: str | None = Field(default=None, pattern=r"^[A-Z0-9]{12}$")
    identity_status: Literal["observed", "needs_lookup", "conflicting"] = "needs_lookup"
    as_of: str

    @field_validator("as_of")
    @classmethod
    def canonical_date(cls, value):
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("target_date")
        return value


def target_snapshot(service, ticker, *, market_path=None, sa_path=None, conn=None):
    Target(ticker=ticker, as_of=now(service)[:10])
    sources = service._read_service.sources_by_ticker()
    if sources is None:
        raise ValueError("tracking_state_unavailable")
    if ticker not in sources or not sources[ticker]:
        raise ValueError("target_not_tracked")
    if conn is None:
        with service._profile_connection(write=False) as owned:
            check = ProviderCheckStore.latest_for_connection(owned, ticker)
    else:
        check = ProviderCheckStore.latest_for_connection(conn, ticker)
    locators = [row["source_locator"] for row in (check["evidence"] if check else [])
        if row["kind"] == "listing_directory_snapshot" and row["source_locator"].get("candidate_ticker") == ticker]
    names = set()
    if sa_path is not None and Path(sa_path).is_file():
        try:
            with closing(sqlite3.connect(Path(sa_path).resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as sa:
                names = {row[0].strip() for row in sa.execute("SELECT DISTINCT company FROM sa_alpha_picks WHERE symbol=? AND company<>''", (ticker,)) if row[0].strip()}
        except sqlite3.Error:
            pass  # Optional public name hint; identity stays explicitly unresolved.
    values = {"issuer_name": names,
        "issuer_cik": {row["issuer_cik"] for row in locators if row.get("issuer_cik")},
        "composite_figi": {row["composite_figi"] for row in locators if row.get("composite_figi")},
        "security_class": {_FACT_SECURITY_CLASSES[row["security_type"]].replace("_", " ") for row in locators if row.get("security_type") in _FACT_SECURITY_CLASSES},
        "venue": {_FACT_VENUES[row["primary_exchange"]] for row in locators if row.get("primary_exchange") in _FACT_VENUES}}
    # Historical display names are hints, not competing security identifiers.
    conflict = any(len(values[key]) > 1 for key in ("issuer_cik", "composite_figi", "security_class", "venue"))
    return Target(ticker=ticker, as_of=now(service)[:10],
        identity_status="conflicting" if conflict else "observed" if all(len(values[key]) == 1 for key in ("issuer_name", "security_class", "venue")) else "needs_lookup",
        **{key: next(iter(items)) if len(items) == 1 else None for key, items in values.items()})


def provider_observations(conn, ticker):
    check = ProviderCheckStore.latest_for_connection(conn, ticker)
    if check is None:
        return {"observed_at": None, "listings": [], "gaps": ["structured_check_missing"]}, None
    fields = ("candidate_ticker", "listing_status", "primary_exchange", "security_type", "market", "snapshot_complete", "delisted_utc", "provider_last_updated_utc", "directory")
    providers = {"massive_reference": "massive", "eodhd_symbol_directory": "eodhd", "nasdaq_symbol_directory": "nasdaq"}
    listings = [{key: row["source_locator"].get(key) for key in fields} | {"observed_at": row["retrieved_at"], "provider": providers[row["adapter"]]}
        for row in check["evidence"] if row["kind"] == "listing_directory_snapshot"]
    return {"observed_at": check["at"], "listings": listings,
            "gaps": list(check.get("blockers", ()))}, check["digest"]


class TargetPreflight:
    def __init__(self, service, *, credential_store, route_loader, market_path=None, sa_path=None):
        self.service, self.credential_store, self.route_loader = service, credential_store, route_loader
        self.market_path, self.sa_path = market_path, sa_path

    def _material(self, ticker, *, language="zh-Hant"):
        if language not in {"en", "zh-Hant"}:
            raise ValueError("investigation_language")
        target = target_snapshot(self.service, ticker, market_path=self.market_path, sa_path=self.sa_path)
        with self.service._profile_connection(write=False) as conn:
            verify_journal(conn)
            observations, provider_digest = provider_observations(conn, ticker)
        route = self.route_loader()
        active = [row for row in self.credential_store.list(route.provider) if row.active]
        if len(active) != 1:
            raise ValueError("selected_credential_unavailable")
        row = active[0]
        selection = validate_selection(route.provider, row.auth_type, route.model, f"local:{row.id}")
        runtime = RuntimeStore(self.service.profile_db_path).read()
        output = None if selection.auth_mode != "api_key" else runtime.api_output_tokens
        # This validates the exact capability without guessing a family limit or silently clamping a setting.
        ModelCall(selection, "step-1", "analysis", "Validate selection", {"type": "object"}, route.effort, output, runtime.web_actions, runtime.model_timeout_seconds)
        binding = {"version": 2, "language": language, "target": target.model_dump(), "selection": asdict(selection),
            "runtime": runtime.model_dump(), "effort": route.effort, "credential_generation": credential_generation(row),
            "provider_observations": observations, "provider_sha256": provider_digest}
        return binding, row.alias

    def prepare(self, ticker, *, language="zh-Hant"):
        from src.lifecycle_investigation.store import safe_code
        try:
            binding, label = self._material(ticker, language=language)
        except (KeyError, ValueError, RuntimeError, sqlite3.Error) as exc:
            return {"version": 2, "ticker": ticker, "available": False, "reason": safe_code(exc),
                    "preflight_sha256": None, "target": None, "execution": None, "credential_label": None, "limits": None}
        selection = binding["selection"]
        return {"version": 2, "ticker": ticker, "available": True, "reason": None,
            "preflight_sha256": _sha(binding), "target": binding["target"],
            "execution": {key: selection[key] for key in ("provider", "auth_mode", "model")} | {"effort": binding["effort"]},
            "credential_label": label, "limits": binding["runtime"] | {
                "output_control": "configured" if selection["auth_mode"] == "api_key" else "provider",
                "search_enforcement": "observed" if selection["auth_mode"] == "chatgpt_oauth" else "enforced"}}

    def validate_start(self, ticker, *, preflight_sha256, language="zh-Hant"):
        binding, _ = self._material(ticker, language=language)
        if _sha(binding) != preflight_sha256:
            raise ValueError("investigation_preflight_changed")
        return {"binding": binding}
