"""Focused unit tests for the service-first API slice."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.config import get_agent_config
from src.analysis.contracts import AnalysisArtifact, AnalysisRequest, IntegrityResult, RenderedReport
from src.api.routes.jobs import JobRunRequest, jobs_status, run_named_job
from src.api.routes.reports import report_detail, reports_list
from src.api.routes.seeking_alpha import (
    _unwrap_sa_result,
    alpha_picks,
    alpha_pick_article_detail,
    market_news,
)
from src.monitor.notifiers import Alert
from src.service.jobs import JobNotRunnableError, list_jobs_status, run_job


class DummyDAL:
    """Small DAL stub for service-level tests."""

    def get_watchlist(self, include_sectors: bool = False):
        del include_sectors
        return SimpleNamespace(tickers=["NVDA", "AMD"])


class TestServiceJobs:
    def test_list_jobs_status_includes_external_and_flagged_jobs(self):
        cfg = get_agent_config()
        original_analysis = cfg.analysis_pipeline_enabled
        original_sa = cfg.sa_enabled
        cfg.analysis_pipeline_enabled = False
        cfg.sa_enabled = True
        try:
            jobs = list_jobs_status(DummyDAL(), config=cfg)
        finally:
            cfg.analysis_pipeline_enabled = original_analysis
            cfg.sa_enabled = original_sa

        names = {job["name"]: job for job in jobs}
        assert "analysis_watchlist_batch" in names
        assert names["analysis_watchlist_batch"]["enabled"] is False
        assert "analysis_pipeline.enabled" in names["analysis_watchlist_batch"]["availability_reason"]
        assert names["sa_alpha_picks_refresh"]["source"] == "chrome_extension"
        assert names["sa_alpha_picks_refresh"]["runnable_via_api"] is False

    def test_run_analysis_watchlist_batch(self, monkeypatch):
        artifact = AnalysisArtifact(
            request=AnalysisRequest(ticker="NVDA", depth="quick"),
            context_summary={},
            strategy_results={},
            final_decision={"action": "buy", "summary": "NVDA bias"},
            report_sections={"executive_summary": "NVDA bias"},
            degradation_summary=[],
        )

        def fake_run_analysis_request(request, *, dal=None, render_format="markdown"):
            del dal, render_format
            assert request.depth == "quick"
            return SimpleNamespace(
                artifact=artifact,
                integrity=IntegrityResult(artifact=artifact, status="clean"),
                report=RenderedReport(format="markdown", content="# Report"),
            )

        monkeypatch.setattr("src.service.jobs.run_analysis_request", fake_run_analysis_request)

        cfg = get_agent_config()
        original_analysis = cfg.analysis_pipeline_enabled
        cfg.analysis_pipeline_enabled = True
        try:
            result = run_job(
                "analysis_watchlist_batch",
                dal=DummyDAL(),
                params={"tickers": ["NVDA"], "depth": "quick"},
                config=cfg,
            )
        finally:
            cfg.analysis_pipeline_enabled = original_analysis

        assert result.status == "succeeded"
        assert result.result["success_count"] == 1
        assert result.result["items"][0]["ticker"] == "NVDA"
        assert result.result["items"][0]["action"] == "buy"

    def test_run_monitor_watchlist_scan(self, monkeypatch):
        class FakeMonitorEngine:
            def __init__(self, dal):
                del dal
                self.default_tickers = ["NVDA", "AMD"]
                self.last_scan_metrics = {
                    "tickers_scanned": 2,
                    "watchers": [
                        {
                            "watcher": "PriceWatcher",
                            "status": "ok",
                            "elapsed_seconds": 0.123,
                            "alert_count": 1,
                        }
                    ],
                    "alerts_before_dedup": 1,
                    "alerts_after_dedup": 1,
                    "notified": False,
                    "notifications_sent": 0,
                    "total_elapsed_seconds": 0.123,
                }

            async def scan_once(self, tickers=None, notify=False):
                del tickers, notify
                return [
                    Alert(
                        alert_type="price",
                        severity="warning",
                        title="NVDA moved",
                        message="Big move",
                        ticker="NVDA",
                    )
                ]

        monkeypatch.setattr("src.service.jobs.MonitorEngine", FakeMonitorEngine)

        result = run_job("monitor_watchlist_scan", dal=DummyDAL(), params={"notify": False})
        assert result.status == "succeeded"
        assert result.result["alert_count"] == 1
        assert result.result["by_type"]["price"] == 1
        assert result.result["scan_metrics"]["watchers"][0]["watcher"] == "PriceWatcher"


class TestJobsRoutes:
    def test_jobs_status_route_returns_count(self, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.jobs.list_jobs_status",
            lambda dal: [
                {
                    "name": "analysis_watchlist_batch",
                    "description": "desc",
                    "source": "api",
                    "runnable_via_api": True,
                    "enabled": True,
                    "availability_reason": None,
                    "default_params": {"depth": "standard"},
                    "watchlist_ticker_count": 2,
                    "last_status": "never_run",
                    "last_started_at": None,
                    "last_finished_at": None,
                    "last_message": None,
                    "last_result": None,
                }
            ],
        )

        response = jobs_status(dal=object())
        assert response.count == 1
        assert response.jobs[0].name == "analysis_watchlist_batch"

    def test_run_named_job_maps_external_job_to_409(self, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.jobs.run_job",
            lambda job_name, *, dal, params=None, trigger_source="api": (_ for _ in ()).throw(
                JobNotRunnableError("extension-managed")
            ),
        )

        with pytest.raises(HTTPException) as exc_info:
            run_named_job("sa_alpha_picks_refresh", JobRunRequest(), dal=object())
        assert exc_info.value.status_code == 409


class TestSeekingAlphaRoutes:
    def test_alpha_picks_route_passthrough(self, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.seeking_alpha.get_sa_alpha_picks",
            lambda dal, status="all", sector=None: {
                "current": [{"symbol": "NVDA"}],
                "freshness": {},
                "is_partial": False,
            },
        )
        result = alpha_picks(status="current", sector=None, dal=object())
        assert result["current"][0]["symbol"] == "NVDA"

    def test_market_news_disabled_maps_to_503(self, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.seeking_alpha.get_sa_market_news",
            lambda dal, ticker=None, keyword=None, limit=20: {
                "message": (
                    "Seeking Alpha Alpha Picks is not enabled. "
                    "To enable: set seeking_alpha.enabled: true in config/user_profile.yaml "
                    "and install the SA Alpha Picks Chrome extension (see extensions/sa_alpha_picks/)"
                )
            },
        )
        with pytest.raises(HTTPException) as exc_info:
            market_news(dal=object())
        assert exc_info.value.status_code == 503

    def test_article_detail_not_found_maps_to_404(self, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.seeking_alpha.get_sa_article_detail",
            lambda dal, article_id: {"error": f"Article {article_id} not found"},
        )
        with pytest.raises(HTTPException) as exc_info:
            alpha_pick_article_detail("123", dal=object())
        assert exc_info.value.status_code == 404

    def test_unwrap_sa_result_keeps_non_error_hint_payload(self):
        payload = {"error": None, "detail": None, "hint": "use picked_date"}
        assert _unwrap_sa_result(payload) == payload


class TestReportsRoutes:
    def test_reports_list_route(self, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.reports.list_reports",
            lambda dal, ticker=None, days=30, report_type=None, limit=20: [
                {
                    "id": 7,
                    "title": "NVDA Phase D Analysis",
                    "tickers": ["NVDA"],
                    "report_type": "phase_d_analysis",
                    "summary": "summary",
                    "conclusion": "BUY",
                    "confidence": 0.8,
                    "model": "structured-pipeline",
                    "file_path": "data/reports/nvda.md",
                    "tool_calls": 5,
                    "duration_seconds": 12.4,
                    "created_at": "2026-04-21T00:00:00",
                }
            ],
        )
        response = reports_list(dal=object())
        assert response.count == 1
        assert response.reports[0].id == 7
        assert response.reports[0].title == "NVDA Phase D Analysis"

    def test_reports_list_route_normalizes_nan_numeric_fields(self, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.reports.list_reports",
            lambda dal, ticker=None, days=30, report_type=None, limit=20: [
                {
                    "id": 8,
                    "title": "ZETA Analysis",
                    "tickers": ["ZETA"],
                    "report_type": "phase_d_analysis",
                    "summary": "summary",
                    "conclusion": "WATCH",
                    "confidence": float("nan"),
                    "model": "structured-pipeline",
                    "file_path": "data/reports/zeta.md",
                    "tool_calls": float("nan"),
                    "duration_seconds": float("nan"),
                    "created_at": "2026-04-21T00:00:00",
                }
            ],
        )
        response = reports_list(dal=object())
        assert response.count == 1
        assert response.reports[0].confidence is None
        assert response.reports[0].tool_calls is None
        assert response.reports[0].duration_seconds is None

    def test_report_detail_route(self, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.reports.get_report",
            lambda dal, report_id: {
                "id": report_id,
                "title": "NVDA Phase D Analysis",
                "tickers": ["NVDA"],
                "report_type": "phase_d_analysis",
                "summary": "summary",
                "conclusion": "BUY",
                "confidence": 0.8,
                "provider": "phase_d",
                "model": "structured-pipeline",
                "file_path": "data/reports/nvda.md",
                "tools_used": ["technical", "fundamental"],
                "tool_calls": 5,
                "duration_seconds": 12.4,
                "tokens_in": 1000,
                "tokens_out": 500,
                "created_at": "2026-04-21T00:00:00",
                "content": "# NVDA",
            },
        )
        response = report_detail(7, dal=object())
        assert response.id == 7
        assert response.content == "# NVDA"

    def test_report_detail_route_normalizes_nan_numeric_fields(self, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.reports.get_report",
            lambda dal, report_id: {
                "id": report_id,
                "title": "ZETA Analysis",
                "tickers": ["ZETA"],
                "report_type": "phase_d_analysis",
                "summary": "summary",
                "conclusion": "WATCH",
                "confidence": float("nan"),
                "provider": "phase_d",
                "model": "structured-pipeline",
                "file_path": "data/reports/zeta.md",
                "tools_used": ["technical"],
                "tool_calls": float("nan"),
                "duration_seconds": float("nan"),
                "tokens_in": float("nan"),
                "tokens_out": float("nan"),
                "created_at": "2026-04-21T00:00:00",
                "content": "# ZETA",
            },
        )
        response = report_detail(8, dal=object())
        assert response.id == 8
        assert response.confidence is None
        assert response.tool_calls is None
        assert response.duration_seconds is None
        assert response.tokens_in is None
        assert response.tokens_out is None

    def test_report_detail_maps_missing_to_404(self, monkeypatch):
        monkeypatch.setattr(
            "src.api.routes.reports.get_report",
            lambda dal, report_id: {"error": "Report file not found: data/reports/x.md"},
        )
        with pytest.raises(HTTPException) as exc_info:
            report_detail(7, dal=object())
        assert exc_info.value.status_code == 404
