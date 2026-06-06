"""
§2 AI result-card routes: generate · list · detail · save-as-report · archive.

The product's core surface. ``POST /analysis/card/{ticker}`` runs the §2.4
pipeline — deterministic objective EvidencePacket → forced-structured synthesis →
validated ResultCard — and auto-caches the run locally (CardRunStore). Generated
runs are short-term/traceable; "Save as report" promotes one to a durable report.

Card-run writes funnel through the ``db_write`` choke-point — a generated card is
an *additive analysis record*, not a research-universe/profile-state mutation. A
single card's LLM inference is NOT metered_spend-gated (that gate is reserved for
batch / fan-out spend), matching the locked permission taxonomy.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.agents.config import get_agent_config
from src.api.dependencies import get_card_store, get_dal
from src.api.permissions import require_db_write
from src.card_runs import CardRun, CardRunStore
from src.card_synthesis import confidence_to_score, render_card_markdown, synthesize_card
from src.evidence_packet import gather_evidence
from src.result_card import ResultCard
from src.tools.data_access import DataAccessLayer
from src.tools.report_tools import save_report

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis-cards"])

_VALID_PROVIDERS = {"anthropic", "openai"}


class GenerateBody(BaseModel):
    question: Optional[str] = None
    horizon: Optional[str] = None
    provider: str = "anthropic"
    include_sa: Optional[bool] = None  # override config.sa_enabled for this run


class ArchiveBody(BaseModel):
    archived: bool


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _summary(run: CardRun) -> dict:
    """Light list-row view — no full card / packet."""
    card = run.result_card or {}
    return {
        "run_id": run.id,
        "ticker": run.ticker,
        "question": run.question,
        "horizon": run.horizon,
        "card_type": run.card_type,
        "status": run.status,
        "provider": run.provider,
        "model": run.model,
        "generated_at": run.generated_at,
        "saved_report_id": run.saved_report_id,
        "conclusion": card.get("conclusion"),
        "confidence_level": card.get("confidence_level"),
    }


@router.post("/analysis/card/{ticker}")
def generate_card(
    ticker: str,
    body: GenerateBody,
    dal: DataAccessLayer = Depends(get_dal),
    store: CardRunStore = Depends(get_card_store),
):
    """Generate a §2 card: gather objective evidence → synthesize → cache the run."""
    provider = (body.provider or "anthropic").lower()
    if provider not in _VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"unknown provider: {provider}")

    now = _utcnow()
    sa_enabled = body.include_sa if body.include_sa is not None else get_agent_config().sa_enabled

    packet = gather_evidence(
        dal,
        ticker,
        now_iso=now,
        question=body.question,
        horizon=body.horizon,
        sa_enabled=sa_enabled,
    )

    try:
        card, meta = synthesize_card(
            packet,
            now_iso=now,
            provider=provider,  # type: ignore[arg-type]
            question=body.question,
            horizon=body.horizon,
        )
    except Exception as exc:
        logger.warning("Card synthesis failed for %s: %s", ticker, exc)
        raise HTTPException(status_code=502, detail=f"synthesis failed: {exc}")

    require_db_write(
        "card_generate", {"ticker": packet.ticker, "provider": provider}
    )
    run = store.record(
        ticker=packet.ticker,
        result_card=card.model_dump(),
        evidence_packet=packet.model_dump(),
        question=body.question,
        horizon=body.horizon,
        provider=meta["provider"],
        model=meta["model"],
        as_of=now,
        generated_at=now,
    )
    return {
        "run_id": run.id,
        "status": run.status,
        "provider": run.provider,
        "model": run.model,
        "generated_at": run.generated_at,
        "card": card.model_dump(),
        "evidence_packet": packet.model_dump(),
    }


@router.get("/analysis/cards")
def list_cards(
    ticker: Optional[str] = None,
    limit: int = 20,
    include_archived: bool = False,
    store: CardRunStore = Depends(get_card_store),
):
    """Recent card runs (default: generated + saved; archived hidden)."""
    statuses = ("generated", "saved", "archived") if include_archived else ("generated", "saved")
    runs = store.recent(ticker=ticker, limit=limit, statuses=statuses)
    return {"cards": [_summary(r) for r in runs]}


@router.get("/analysis/cards/{run_id}")
def get_card(
    run_id: int,
    store: CardRunStore = Depends(get_card_store),
):
    """Full run: the validated card + the evidence packet it was built from."""
    run = store.get(run_id)
    if not run or run.status == "deleted":
        raise HTTPException(status_code=404, detail="card run not found")
    return {
        "run_id": run.id,
        "ticker": run.ticker,
        "question": run.question,
        "horizon": run.horizon,
        "card_type": run.card_type,
        "status": run.status,
        "provider": run.provider,
        "model": run.model,
        "generated_at": run.generated_at,
        "as_of": run.as_of,
        "saved_report_id": run.saved_report_id,
        "card": run.result_card,
        "evidence_packet": run.evidence_packet,
    }


@router.post("/analysis/cards/{run_id}/save")
def save_card(
    run_id: int,
    dal: DataAccessLayer = Depends(get_dal),
    store: CardRunStore = Depends(get_card_store),
):
    """Promote a generated run to a durable report; flip status to 'saved'."""
    run = store.get(run_id)
    if not run or run.status == "deleted":
        raise HTTPException(status_code=404, detail="card run not found")
    if run.status == "saved" and run.saved_report_id is not None:
        return {
            "run_id": run_id,
            "status": run.status,
            "saved_report_id": run.saved_report_id,
            "report": None,
            "already_saved": True,
        }
    try:
        card = ResultCard(**run.result_card)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"stored card is malformed: {exc}")

    require_db_write("card_save", {"run_id": run_id, "ticker": run.ticker})
    rep = save_report(
        dal,
        title=f"{run.ticker} — research card",
        tickers=[run.ticker],
        report_type="thesis",
        summary=card.conclusion[:280],
        content=render_card_markdown(card),
        confidence=confidence_to_score(card.confidence_level),
        provider=run.provider,
        model=run.model,
    )
    report_id = rep.get("id")
    updated = store.mark_saved(run_id, saved_report_id=report_id)
    return {
        "run_id": run_id,
        "status": updated.status if updated else run.status,
        "saved_report_id": report_id,
        "report": rep,
    }


@router.post("/analysis/cards/{run_id}/archive")
def archive_card(
    run_id: int,
    body: ArchiveBody,
    store: CardRunStore = Depends(get_card_store),
):
    """Archive (hide from default list) or restore a run."""
    run = store.get(run_id)
    if not run or run.status == "deleted":
        raise HTTPException(status_code=404, detail="card run not found")
    action = "card_archive" if body.archived else "card_restore"
    require_db_write(action, {"run_id": run_id})
    if body.archived:
        target = "archived"
    else:
        # Restore to the real prior status: a promoted card returns to 'saved'
        # (not 'generated'), so it stays out of the auto-archive sweep and keeps
        # its report link consistent.
        target = "saved" if run.saved_report_id is not None else "generated"
    updated = store.set_status(run_id, target)
    return {"run_id": run_id, "status": updated.status if updated else run.status}


@router.delete("/analysis/cards/{run_id}")
def delete_card(
    run_id: int,
    store: CardRunStore = Depends(get_card_store),
):
    """Soft-delete a run (status='deleted')."""
    run = store.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="card run not found")
    require_db_write("card_delete", {"run_id": run_id})
    store.set_status(run_id, "deleted")
    return {"deleted": True, "id": run_id}
