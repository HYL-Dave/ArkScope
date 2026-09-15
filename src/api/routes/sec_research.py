"""Stored SEC research status and explicit, bounded structured refresh commands."""

import re
import sqlite3
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from data_sources.sec_transport import SecTransport, SecTransportFailure, validate_sec_identity
from src.api.dependencies import get_data_provider_store, get_profile_store
from src.api.permissions import require_db_write
from src.data_provider_config import PROVIDER_FIELDS, normalize_provider_config_value
from src.sec_research import schema
from src.sec_research.captures import CaptureStore
from src.sec_research.citations import CitationError, decode_citation_query, read_sec_citation
from src.sec_research.common import normalize_cik
from src.sec_research.config import MAX_CAPTURE_BUDGET_BYTES, get_capture_budget_bytes, set_capture_budget_bytes
from src.sec_research.paths import SecResearchPaths
from src.sec_research.queries import StoredQueries, query_date, validate_query
from src.sec_research.service import ResearchService
from src.sec_research.store import Store
from src.sec_research.schedule_store import ScheduleStore, FORMS


router = APIRouter(tags=["sec-research"])


def _cik(value):
    try:
        return normalize_cik(value)
    except ValueError:
        raise HTTPException(422, detail={"code": "sec_issuer_invalid"}) from None


def _unavailable(code):
    return {"status": "unavailable", "data": None, "gaps": [{"code": code}],
            "observed_at": None, "coverage": {}, "next_cursor": None}


def _installed(store):
    if not store.paths.market_db_path.exists():
        return False
    with store.connect(readonly=True) as conn:
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE lower(name) GLOB 'sec_research_*'"
        ).fetchone():
            return False
        schema.verify(conn)
    return True


class ConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capture_budget_bytes: int = Field(ge=1, le=MAX_CAPTURE_BUDGET_BYTES, strict=True)


@router.get("/sec-research/config")
def get_config():
    try:
        budget = get_capture_budget_bytes(get_profile_store())
    except ValueError:
        raise HTTPException(503, detail={"code": "sec_research_config_invalid"}) from None
    except (sqlite3.Error, OSError):
        raise HTTPException(503, detail={"code": "sec_research_config_unavailable"}) from None
    try:
        store = Store(SecResearchPaths.resolve())
        capacity = CaptureStore(store, budget=lambda: budget).status() if _installed(store) else None
        return {"capture_budget_bytes": budget, "capacity": capacity}
    except (ValueError, sqlite3.Error, OSError):
        raise HTTPException(503, detail={"code": "sec_research_store_unavailable"}) from None


@router.put("/sec-research/config")
def put_config(request: ConfigRequest):
    require_db_write("sec_research_config", {"capture_budget_bytes": request.capture_budget_bytes})
    try:
        saved = set_capture_budget_bytes(get_profile_store(), request.capture_budget_bytes)
        return {"capture_budget_bytes": saved}
    except (ValueError, sqlite3.Error, OSError):
        raise HTTPException(503, detail={"code": "sec_research_config_unavailable"}) from None


@router.get("/sec-research/citation")
def stored_citation(request: Request):
    try:
        if set(request.query_params) != {"ref"} or len(request.query_params.getlist("ref")) != 1:
            raise CitationError("sec_citation_query_invalid")
        citation = decode_citation_query(request.query_params["ref"])
    except CitationError:
        raise HTTPException(422, detail={"code": "sec_citation_query_invalid"}) from None
    try:
        store = Store(SecResearchPaths.resolve())
        if not _installed(store):
            return _unavailable("sec_research_not_installed")
        return read_sec_citation(store, CaptureStore(store, budget=None), citation=citation)
    except (ValueError, sqlite3.Error, OSError):
        return _unavailable("sec_citation_integrity_failed")


@router.get("/sec-research/schedule-status")
def schedule_status():
    try:
        result = ScheduleStore(Store(SecResearchPaths.resolve())).status()
        attempt = result["last_attempt"]
        status = {"succeeded": "ok", "partial": "partial", "failed": "unavailable",
                  "running": "partial"}.get(attempt["status"] if attempt else None, "unavailable")
        return {"status": status, "data": result,
                "gaps": attempt["gaps"] if attempt else [{"code": "sec_schedule_unobserved"}],
                "observed_at": attempt["finished_at"] or attempt["started_at"] if attempt else None,
                "coverage": {"scope": "recent", "forms": list(FORMS), "history_requested": False},
                "next_cursor": None}
    except (ValueError, sqlite3.Error, OSError):
        return _unavailable("sec_schedule_store_unavailable")


@router.get("/sec-research/{cik}")
def stored_status(cik: str):
    cik = _cik(cik)
    try:
        store = Store(SecResearchPaths.resolve())
        if not _installed(store):
            return _unavailable("sec_research_not_installed")
        result = ResearchService(store, None, None).stored(cik)
        receipt = result["receipt"]
        if receipt is None:
            return _unavailable("sec_research_unobserved")
        return {"status": result["status"], "data": {"cik": cik, "snapshots": result["snapshot_counts"]},
                "gaps": receipt["gaps"], "observed_at": receipt["observed_at"],
                "coverage": {"scope": receipt["scope"], "completed": receipt["completed"], "pending": receipt["pending"]},
                "next_cursor": None}
    except (ValueError, sqlite3.Error, OSError):
        return _unavailable("sec_research_store_unavailable")


def _query_limit(value):
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,2}", value):
        value = int(value)
    if type(value) is not int or not 1 <= value <= 100:
        raise HTTPException(422, detail={"code": "sec_research_query_invalid"})
    return value


def _query_bool(value):
    if value in ("true", "false"):
        return value == "true"
    if type(value) is not bool:
        raise HTTPException(422, detail={"code": "sec_research_query_invalid"})
    return value


def _query_date(value):
    try:
        return query_date(value)
    except ValueError:
        raise HTTPException(422, detail={"code": "sec_research_query_invalid"}) from None


QueryLimit = Annotated[int, BeforeValidator(_query_limit), Query()]
QueryBool = Annotated[bool, BeforeValidator(_query_bool), Query()]
QueryDate = Annotated[str | None, BeforeValidator(_query_date), Query()]


def _stored_query(cik, kind, **params):
    cik = _cik(cik)
    try:
        if kind == "filing_forms":
            if params:
                raise ValueError("sec_research_query_invalid")
        else:
            validate_query(cik, kind, **params)
        store = Store(SecResearchPaths.resolve())
        if not _installed(store):
            return _unavailable("sec_research_not_installed")
        return getattr(StoredQueries(store), kind)(cik, **params)
    except ValueError as exc:
        if str(exc) in {"sec_research_query_invalid", "sec_research_cursor_invalid",
                        "sec_research_cursor_mismatch"}:
            raise HTTPException(422, detail={"code": str(exc)}) from None
        return _unavailable("sec_research_store_unavailable")
    except (sqlite3.Error, OSError):
        return _unavailable("sec_research_store_unavailable")


@router.get("/sec-research/{cik}/filing-forms")
def stored_filing_forms(cik: str, request: Request):
    if request.query_params:
        raise HTTPException(422, detail={"code": "sec_research_query_invalid"})
    return _stored_query(cik, "filing_forms")


@router.get("/sec-research/{cik}/filings")
def stored_filings(
    cik: str, forms: list[str] | None = Query(None),
    filed_from: QueryDate = None, filed_to: QueryDate = None,
    include_amendments: QueryBool = True, cursor: str | None = Query(None),
    limit: QueryLimit = 20,
):
    return _stored_query(cik, "filings", forms=forms, filed_from=filed_from, filed_to=filed_to,
                         include_amendments=include_amendments, cursor=cursor, limit=limit)


@router.get("/sec-research/{cik}/facts")
def stored_facts(
    cik: str, metrics: list[str] | None = Query(None), concepts: list[str] | None = Query(None),
    fact_ids: list[str] | None = Query(None), accession: str | None = Query(None),
    as_of: QueryDate = None, period: str = Query("all"),
    start: QueryDate = None, end: QueryDate = None,
    revisions: str = Query("latest"), cursor: str | None = Query(None), limit: QueryLimit = 40,
):
    return _stored_query(cik, "facts", metrics=metrics, concepts=concepts, fact_ids=fact_ids,
                         accession=accession, as_of=as_of, period=period, start=start, end=end,
                         revisions=revisions, cursor=cursor, limit=limit)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_sources: int = Field(default=4, ge=1, le=16, strict=True)
    resume: bool = Field(default=False, strict=True)


@router.post("/sec-research/{cik}/refresh")
def refresh(cik: str, request: RefreshRequest):
    cik = _cik(cik)
    require_db_write("sec_research_refresh", {"cik": cik})
    transport = None
    try:
        profile = get_profile_store()
        budget = lambda: get_capture_budget_bytes(profile)
        budget()
        config = get_data_provider_store().get_all()
        identity = config.get("sec_edgar", {}).get("user_agent", "")
        identity = normalize_provider_config_value(PROVIDER_FIELDS["sec_edgar"][0], identity)
        validate_sec_identity(identity)
        store = Store(SecResearchPaths.resolve())
        store.install()
        captures = CaptureStore(store, budget=budget)
        transport = SecTransport(user_agent=identity, max_rate_limit_retries=0)
        result = ResearchService(store, captures, transport).refresh(
            cik, max_sources=request.max_sources, resume=request.resume)
        return result
    except SecTransportFailure:
        raise HTTPException(503, detail={"code": "sec_identity_unconfigured"}) from None
    except (ValueError, sqlite3.Error, OSError, TimeoutError):
        raise HTTPException(503, detail={"code": "sec_research_refresh_unavailable"}) from None
    finally:
        if transport is not None:
            transport.close()
