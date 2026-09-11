"""Stored SEC research status and explicit, bounded structured refresh commands."""

import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from data_sources.sec_transport import SecTransport, SecTransportFailure, validate_sec_identity
from src.api.dependencies import get_data_provider_store, get_profile_store
from src.api.permissions import require_db_write
from src.data_provider_config import PROVIDER_FIELDS, normalize_provider_config_value
from src.sec_research import schema
from src.sec_research.captures import CaptureStore
from src.sec_research.common import normalize_cik
from src.sec_research.config import get_capture_budget_bytes
from src.sec_research.paths import SecResearchPaths
from src.sec_research.service import ResearchService
from src.sec_research.store import Store


router = APIRouter(tags=["sec-research"])


def _cik(value):
    try:
        return normalize_cik(value)
    except ValueError:
        raise HTTPException(422, detail={"code": "sec_issuer_invalid"}) from None


def _unavailable(code):
    return {"status": "unavailable", "data": None, "gaps": [{"code": code}],
            "observed_at": None, "coverage": {}, "next_cursor": None}


@router.get("/sec-research/{cik}")
def stored_status(cik: str):
    cik = _cik(cik)
    store = Store(SecResearchPaths.resolve())
    if not store.paths.market_db_path.exists():
        return _unavailable("sec_research_not_installed")
    try:
        with store.connect(readonly=True) as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='sec_research_snapshots'").fetchone():
                return _unavailable("sec_research_not_installed")
            schema.verify(conn)
        result = ResearchService(store, None, None).stored(cik)
        receipt = result["receipt"]
        if receipt is None:
            return _unavailable("sec_research_unobserved")
        return {"status": result["status"], "data": {"cik": cik, "snapshots": result["snapshot_counts"]},
                "gaps": receipt["gaps"], "observed_at": receipt["observed_at"],
                "coverage": {"completed": receipt["completed"], "pending": receipt["pending"]},
                "next_cursor": None}
    except (ValueError, sqlite3.Error, OSError):
        return _unavailable("sec_research_store_unavailable")


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
        transport = SecTransport(user_agent=identity)
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
