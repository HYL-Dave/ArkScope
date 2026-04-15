"""Phase D analysis pipeline routes."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.agents.config import get_agent_config
from src.analysis import AnalysisRequest, run_analysis_request, save_analysis_run
from src.api.dependencies import get_dal

router = APIRouter(tags=["analysis"])


class AnalysisRunRequest(BaseModel):
    """Request body for Phase D pipeline execution."""

    ticker: str
    depth: Literal["quick", "standard", "full"] = "standard"
    format: Literal["markdown", "html"] = "markdown"
    user_query: Optional[str] = None
    persist: bool = False
    title: Optional[str] = None


class AnalysisRunResponse(BaseModel):
    """Response body for Phase D pipeline execution."""

    ticker: str
    integrity_status: str
    action: Optional[str] = None
    degradation_summary: List[str]
    report: Optional[str] = None
    strategy_status: Dict[str, str]
    saved_report_id: Optional[int] = None
    saved_report_path: Optional[str] = None


@router.post("/analysis/run", response_model=AnalysisRunResponse)
def run_analysis(
    request: AnalysisRunRequest,
    dal=Depends(get_dal),
):
    """Run the feature-flagged Phase D analysis pipeline."""
    if not get_agent_config().analysis_pipeline_enabled:
        raise HTTPException(
            status_code=503,
            detail="Phase D analysis pipeline is disabled. Set analysis_pipeline.enabled=true.",
        )

    output = run_analysis_request(
        AnalysisRequest(
            ticker=request.ticker.upper(),
            depth=request.depth,
            source="api",
            mode="interactive",
            user_query=request.user_query,
        ),
        dal=dal,
        render_format=request.format,
    )
    saved_report = None
    if request.persist:
        saved_report = save_analysis_run(
            dal,
            output,
            title=request.title,
        )
    return AnalysisRunResponse(
        ticker=output.artifact.request.ticker,
        integrity_status=output.integrity.status,
        action=output.artifact.final_decision.get("action"),
        degradation_summary=list(output.artifact.degradation_summary),
        report=output.report.content if output.report is not None else None,
        strategy_status={
            name: result.status
            for name, result in output.artifact.strategy_results.items()
        },
        saved_report_id=saved_report.id if saved_report is not None else None,
        saved_report_path=saved_report.file_path if saved_report is not None else None,
    )
