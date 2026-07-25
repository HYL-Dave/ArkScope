"""Seeking Alpha reads plus fixed, sidecar-owned Market News repair routes."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from src.agents.config import get_agent_config
from src.api.dependencies import get_dal
from src.service.sa_extension_health import collect_sa_extension_health
from src.service.sa_market_news_health import compute_market_news_health
from src.service.job_runs_store import get_job_runs_store
from src.sa.market_news_recovery import (
    MarketNewsRecoveryError,
    MarketNewsRecoveryService,
)
from src.tools.sa_tools import (
    _DISABLED_MSG,
    get_sa_alpha_picks,
    get_sa_article_detail,
    get_sa_articles,
    get_sa_feed,
    get_sa_market_news,
    get_sa_pick_detail,
)

router = APIRouter(prefix="/sa", tags=["seeking-alpha"])


class _RecoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MarketNewsRecoveryPreviewRequest(_RecoveryRequest):
    kind: Literal["recorded_failures", "incident_window"]
    source_run_ids: Optional[List[int]] = None


class MarketNewsRecoveryStartRequest(_RecoveryRequest):
    manifest: Dict[str, Any]
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class MarketNewsRecoveryStateRequest(_RecoveryRequest):
    run_id: Optional[int] = Field(default=None, ge=1)


class MarketNewsRecoveryCheckpointRequest(_RecoveryRequest):
    run_id: int = Field(ge=1)
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    news_id: str = Field(min_length=1, max_length=240)
    attempt_id: str = Field(min_length=1, max_length=160)
    state: Literal[
        "repaired", "already_present", "unavailable_at_source", "failed_retryable"
    ]
    reason_code: str = Field(min_length=1, max_length=64)
    attempt_count: int = Field(default=1, ge=0)
    evidence_code: Optional[str] = Field(default=None, max_length=64)


class MarketNewsRecoveryFinalizeRequest(_RecoveryRequest):
    run_id: int = Field(ge=1)
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    discovery: Optional[Dict[str, Any]] = None


class MarketNewsRecoveryCancelRequest(_RecoveryRequest):
    run_id: int = Field(ge=1)
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


def _recovery_service(dal: Any) -> MarketNewsRecoveryService:
    return MarketNewsRecoveryService(dal, get_job_runs_store(dal))


def _recovery_error(exc: MarketNewsRecoveryError) -> HTTPException:
    if exc.code == "repair_not_found":
        status = 404
    elif exc.code in {
        "repair_not_running",
        "checkpoint_conflict",
        "target_not_in_manifest",
    }:
        status = 409
    elif exc.code == "recovery_data_unavailable":
        status = 503
    else:
        status = 400
    return HTTPException(status_code=status, detail={"code": exc.code})


def _unwrap_sa_result(result: dict) -> dict:
    """Translate tool-style SA responses into explicit HTTP semantics."""
    message = result.get("message")
    if message == _DISABLED_MSG:
        raise HTTPException(status_code=503, detail=message)

    error = result.get("error")
    if error not in (None, ""):
        text = str(error)
        if "not found" in text.lower():
            raise HTTPException(status_code=404, detail=text)
        raise HTTPException(status_code=500, detail=text)
    return result


@router.get("/feed")
def sa_feed(
    q: Optional[str] = Query(None, description="search terms (FTS5; short/symbol → LIKE)"),
    ticker: Optional[str] = Query(None),
    item_type: Optional[str] = Query(None, pattern="^(article|market_news)$"),
    days: int = Query(30, ge=1, le=3650),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    dal=Depends(get_dal),
):
    """Unified Seeking Alpha evidence feed (articles + market news) for the 新聞·事件
    surface — newest first, paginated, with total + per-type/per-day facets over the
    same filters. Degraded states (e.g. SA not local-first) return available=False
    with an empty_reason, NOT an HTTP error — only the feature-disabled case is 503.
    """
    result = get_sa_feed(dal, q=q, ticker=ticker, item_type=item_type,
                         days=days, limit=limit, offset=offset)
    if result.get("message") == _DISABLED_MSG:
        raise HTTPException(status_code=503, detail=result["message"])
    return result


@router.get("/alpha-picks")
def alpha_picks(
    status: str = Query("all", pattern="^(all|current|closed)$"),
    sector: Optional[str] = Query(None),
    dal=Depends(get_dal),
):
    """Read cached Alpha Picks portfolio data from the backend."""
    return _unwrap_sa_result(get_sa_alpha_picks(dal, status=status, sector=sector))


@router.get("/picks/{symbol}")
def alpha_pick_detail(
    symbol: str,
    picked_date: Optional[str] = Query(None),
    dal=Depends(get_dal),
):
    """Read one cached Alpha Picks detail report."""
    return _unwrap_sa_result(get_sa_pick_detail(dal, symbol=symbol, picked_date=picked_date))


@router.get("/articles")
def alpha_pick_articles(
    ticker: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None, min_length=1),
    article_type: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    dal=Depends(get_dal),
):
    """Search cached Alpha Picks articles."""
    return _unwrap_sa_result(
        get_sa_articles(
            dal,
            ticker=ticker,
            keyword=keyword,
            article_type=article_type,
            limit=limit,
        )
    )


@router.get("/articles/{article_id}")
def alpha_pick_article_detail(
    article_id: str,
    dal=Depends(get_dal),
):
    """Read one cached Alpha Picks article body plus comments."""
    return _unwrap_sa_result(get_sa_article_detail(dal, article_id))


@router.get("/market-news")
def market_news(
    ticker: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None, min_length=1),
    limit: int = Query(20, ge=1, le=100),
    dal=Depends(get_dal),
):
    """Read cached Seeking Alpha market-news items."""
    return _unwrap_sa_result(
        get_sa_market_news(dal, ticker=ticker, keyword=keyword, limit=limit)
    )


@router.get("/market-news/health")
def market_news_health(
    response: Response,
    strict: bool = Query(False, description="Return 503 when severity != ok."),
    dal=Depends(get_dal),
):
    """Return SA market-news pipeline health (P0.4).

    Three layers reported separately so callers can tell pipeline staleness
    from feed-content lulls from detail-body gaps:

      - ``freshness``     last fetch / latest published age
      - ``feed_health``   rows in 24h / 7d
      - ``detail_health`` 7d body completeness

    Severity ladder: ``ok`` / ``warning`` / ``critical``. Default returns
    200 with the structured payload regardless. ``?strict=true`` upgrades
    any non-``ok`` severity to HTTP 503 for healthcheck-style probes.
    """
    if not get_agent_config().sa_enabled:
        raise HTTPException(status_code=503, detail=_DISABLED_MSG)

    report = compute_market_news_health(dal)
    if strict and report.get("severity") != "ok":
        response.status_code = 503
    return report


@router.get("/extension-health")
def sa_extension_health(dal=Depends(get_dal)):
    """Return the local SA extension/native-host setup checklist."""
    try:
        return collect_sa_extension_health(dal=dal)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "sa_extension_health_unavailable",
                "message": str(exc),
            },
        ) from exc


@router.post("/market-news-recovery/preview")
def market_news_recovery_preview(
    request: MarketNewsRecoveryPreviewRequest,
    dal=Depends(get_dal),
):
    """Build a read-only, immutable repair manifest preview."""

    try:
        service = _recovery_service(dal)
        if request.kind == "incident_window":
            if request.source_run_ids is not None:
                raise MarketNewsRecoveryError("manifest_invalid")
            return service.preview_incident()
        return service.preview_recorded_failures(source_run_ids=request.source_run_ids)
    except MarketNewsRecoveryError as exc:
        raise _recovery_error(exc) from exc


@router.post("/market-news-recovery/start")
def market_news_recovery_start(
    request: MarketNewsRecoveryStartRequest,
    dal=Depends(get_dal),
):
    """Atomically start one repair or return the actual running manifest."""

    try:
        return _recovery_service(dal).start(request.manifest, request.manifest_hash)
    except MarketNewsRecoveryError as exc:
        raise _recovery_error(exc) from exc


@router.post("/market-news-recovery/state")
def market_news_recovery_state(
    request: MarketNewsRecoveryStateRequest,
    dal=Depends(get_dal),
):
    """Return the full machine contract only on the fixed repair route."""

    try:
        return _recovery_service(dal).state(request.run_id)
    except MarketNewsRecoveryError as exc:
        raise _recovery_error(exc) from exc


@router.post("/market-news-recovery/checkpoint")
def market_news_recovery_checkpoint(
    request: MarketNewsRecoveryCheckpointRequest,
    dal=Depends(get_dal),
):
    """Merge one idempotent item attempt into durable repair progress."""

    try:
        return _recovery_service(dal).checkpoint(
            request.run_id,
            request.manifest_hash,
            news_id=request.news_id,
            attempt_id=request.attempt_id,
            state=request.state,
            reason_code=request.reason_code,
            attempt_count=request.attempt_count,
            evidence_code=request.evidence_code,
        )
    except MarketNewsRecoveryError as exc:
        raise _recovery_error(exc) from exc


@router.post("/market-news-recovery/finalize")
def market_news_recovery_finalize(
    request: MarketNewsRecoveryFinalizeRequest,
    dal=Depends(get_dal),
):
    """Reconcile body presence and derive the only terminal repair truth."""

    try:
        return _recovery_service(dal).finalize(
            request.run_id,
            request.manifest_hash,
            discovery=request.discovery,
        )
    except MarketNewsRecoveryError as exc:
        raise _recovery_error(exc) from exc


@router.post("/market-news-recovery/cancel")
def market_news_recovery_cancel(
    request: MarketNewsRecoveryCancelRequest,
    dal=Depends(get_dal),
):
    """Explicitly cancel one repair while retaining its immutable audit manifest."""

    try:
        return _recovery_service(dal).cancel(request.run_id, request.manifest_hash)
    except MarketNewsRecoveryError as exc:
        raise _recovery_error(exc) from exc
