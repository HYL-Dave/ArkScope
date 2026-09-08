"""Provider-free preparation using the selected profile route and public identity."""

from dataclasses import asdict
from pathlib import Path
import sqlite3

from pydantic import ValidationError

from src.auth_drivers.lifecycle_web_models import ModelCall, WebModelError, credential_generation
from src.lifecycle_web_controller import _failure_code
from src.lifecycle_web_schema import verify_web_journal
from src.lifecycle_web_store import _sha
from src.security_lifecycle_listing_evidence import _FACT_SECURITY_CLASSES, _FACT_VENUES
from src.security_lifecycle_provider_snapshot import instant
from src.security_lifecycle_provider_store import ProviderCheckStore
from src.security_lifecycle_review import now
from src.security_lifecycle_web_contract import PublicInvestigationInput, validate_selection
from src.security_lifecycle_web_pipeline import default_investigation_options


class LifecycleWebPreflight:
    def __init__(self, service, *, credential_store, route_loader, sa_db_path, output_limit_loader):
        self.service = service
        self.credential_store = credential_store
        self.route_loader = route_loader
        self.sa_db_path = Path(sa_db_path)
        self.output_limit_loader = output_limit_loader

    def _public_input(self, case, *, question, check):
        names, ciks = set(), set()
        for row in self.service._read_service._cases():
            observation = row.get("observation")
            if row["ticker"] != case["ticker"] or row["source"] != "sec_edgar" or not isinstance(observation, dict):
                continue
            if observation.get("issuer_name"):
                names.add(observation["issuer_name"])
            if observation.get("cik"):
                ciks.add(observation["cik"])
        if not names and self.sa_db_path.is_file():
            with sqlite3.connect(self.sa_db_path.resolve().as_uri() + "?mode=ro", uri=True) as conn:
                names = {row[0] for row in conn.execute("SELECT DISTINCT company FROM sa_alpha_picks WHERE symbol=? AND company<>''", (case["ticker"],))}
        if len(names) != 1 or len(ciks) > 1:
            raise WebModelError("web_public_identity_missing")
        locators = [row["source_locator"] for row in (check["evidence"] if check else [])
                    if row["kind"] == "listing_directory_snapshot" and row["source_locator"].get("candidate_ticker") == case["ticker"]
                    and row["source_locator"].get("listing_status") in {"active", "inactive"}]
        figis = {row["composite_figi"] for row in locators if row.get("composite_figi")}
        ciks |= {row["issuer_cik"] for row in locators if row.get("issuer_cik")}
        if len(figis) > 1 or len(ciks) > 1:
            raise WebModelError("web_security_identity_conflict")
        venues = {_FACT_VENUES[row["primary_exchange"]] for row in locators if row.get("primary_exchange") in _FACT_VENUES}
        classes = {_FACT_SECURITY_CLASSES[row["security_type"]].replace("_", " ") for row in locators if row.get("security_type") in _FACT_SECURITY_CLASSES}
        try:
            return PublicInvestigationInput(ticker=case["ticker"], issuer_name=next(iter(names)),
                security_class=next(iter(classes)) if len(classes) == 1 else None,
                venue=next(iter(venues)) if len(venues) == 1 else None,
                issuer_cik=next(iter(ciks)) if ciks else None, composite_figi=next(iter(figis)) if figis else None,
                question=question, as_of=instant(now(self.service)).date().isoformat())
        except ValidationError:
            raise WebModelError("web_public_identity_missing") from None

    def _material(self, case_id, *, question):
        if question not in {"listing_status", "symbol_continuation"}:
            raise WebModelError("web_question_invalid")
        case = self.service._read_service.get_case(case_id)
        if not case.get("observation_fingerprint_sha256"):
            raise WebModelError("web_public_identity_missing")
        with self.service._profile_connection(write=False) as conn:
            verify_web_journal(conn)
            check = ProviderCheckStore.latest_for_connection(conn, case["ticker"])
        route = self.route_loader()
        active = [row for row in self.credential_store.list(route.provider) if row.active]
        if len(active) != 1:
            raise WebModelError("selected_credential_unavailable")
        row = active[0]
        selected = validate_selection(route.provider, row.auth_type, route.model, f"local:{row.id}")
        request = self._public_input(case, question=question, check=check)
        options = default_investigation_options(selected.auth_mode, effort=route.effort,
            output_token_limit=self.output_limit_loader() if selected.auth_mode == "api_key" else None)
        ModelCall(selected, "search-1", "search", request.search_prompt(), {"type": "object", "properties": {}, "additionalProperties": False},
                  options.effort, options.output_token_limit, options.max_search_uses, options.model_timeout_seconds)
        binding = {"case_id": case_id, "observation_sha256": case["observation_fingerprint_sha256"],
                   "request": request.model_dump(), "selection": asdict(selected), "options": asdict(options),
                   "credential_generation": credential_generation(row)}
        return binding, request, selected, options, row.alias

    def prepare(self, case_id, *, question):
        try:
            binding, request, selected, options, label = self._material(case_id, question=question)
        except (KeyError, ValueError, RuntimeError, sqlite3.Error) as exc:
            return {"version": 1, "case_id": case_id, "available": False, "reason": _failure_code(exc),
                    "preflight_sha256": None, "public_identity": None, "execution": None, "credential_label": None, "limits": None}
        return {"version": 1, "case_id": case_id, "available": True, "reason": None, "preflight_sha256": _sha(binding),
                "public_identity": {key: getattr(request, key) for key in ("ticker", "issuer_name", "security_class", "venue", "question", "as_of")},
                "execution": {key: getattr(selected, key) for key in ("provider", "auth_mode", "model")}, "credential_label": label,
                "limits": {"model_submissions": 2, "search_uses": options.max_search_uses,
                           "search_enforcement": "observed" if selected.auth_mode == "chatgpt_oauth" else "enforced",
                           "source_requests": options.max_source_requests, "sources": options.max_sources,
                           "max_source_bytes": options.max_source_bytes, "max_decoded_source_bytes": options.max_decoded_source_bytes,
                           "model_timeout_seconds": options.model_timeout_seconds, "source_timeout_seconds": options.source_timeout_seconds,
                           "output_token_limit": options.output_token_limit,
                           "background_retention": selected.provider == "openai" and selected.auth_mode == "api_key"}}

    def validate_start(self, case_id, *, question, preflight_sha256):
        binding, request, selection, options, _ = self._material(case_id, question=question)
        if _sha(binding) != preflight_sha256:
            raise ValueError("web_preflight_changed")
        return {"case_id": case_id, "observation_sha256": binding["observation_sha256"],
                "request": request, "selection": selection, "options": options,
                "credential_generation": binding["credential_generation"]}
