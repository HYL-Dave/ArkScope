from src.analysis.contracts import AnalysisArtifact, AnalysisContext, AnalysisRequest, StrategyResult
from src.analysis.context_builder import build_dal_context_builder
from src.analysis.factory import build_default_pipeline
from src.analysis.integrity import validate_and_repair_artifact
from src.analysis.pipeline import AnalysisPipeline
from src.analysis.renderer import render_report
from src.analysis.scheduler_hooks import render_scheduled_batch
from src.analysis.service import run_analysis_request, save_analysis_run
from src.analysis.strategies import (
    DecisionStrategy,
    FundamentalStrategy,
    RiskStrategy,
    SentimentStrategy,
    TechnicalStrategy,
    build_default_strategies,
)


class _FakeStrategy:
    def __init__(self, name: str, payload: dict, status: str = "ok"):
        self.name = name
        self._payload = payload
        self._status = status

    def run(self, context, upstream):
        return StrategyResult(
            name=self.name,
            status=self._status,
            payload=dict(self._payload),
        )


def test_pipeline_runs_strategies_in_order_and_builds_artifact():
    pipeline = AnalysisPipeline(
        [
            _FakeStrategy("technical", {"signal": "trend_up"}),
            _FakeStrategy("decision", {"summary": "Buy setup", "action": "buy"}),
        ]
    )

    artifact = pipeline.run(AnalysisRequest(ticker="NVDA"))

    assert artifact.request.ticker == "NVDA"
    assert list(artifact.strategy_results.keys()) == ["technical", "decision"]
    assert artifact.final_decision["summary"] == "Buy setup"
    assert artifact.report_sections["executive_summary"] == "Buy setup"


def test_integrity_placeholder_fill_repairs_missing_required_fields():
    artifact = AnalysisArtifact(
        request=AnalysisRequest(ticker="AMD"),
        context_summary={},
        strategy_results={},
        final_decision={},
        report_sections={},
        degradation_summary=[],
    )

    result = validate_and_repair_artifact(artifact)

    assert result.status == "placeholder_filled"
    assert "final_decision.summary" in result.missing_fields
    assert artifact.final_decision["summary"] == "TBD"
    assert artifact.report_sections["executive_summary"] == "TBD"


def test_real_technical_and_decision_strategies_produce_buy_bias():
    def build_context(request: AnalysisRequest) -> AnalysisContext:
        return AnalysisContext(
            request=request,
            quote={"price": 105.0},
            market_data={"price": 105.0, "ma5": 102.0, "ma10": 100.0, "ma20": 97.0},
        )

    pipeline = AnalysisPipeline(
        [TechnicalStrategy(), DecisionStrategy()],
        context_builder=build_context,
    )

    artifact = pipeline.run(AnalysisRequest(ticker="NVDA"))

    technical = artifact.strategy_results["technical"]
    decision = artifact.strategy_results["decision"]

    assert technical.status == "ok"
    assert technical.payload["bullish_alignment"] is True
    assert decision.payload["action"] == "buy"
    assert artifact.final_decision["action"] == "buy"
    assert artifact.report_sections["executive_summary"].startswith("NVDA:")


def test_technical_strategy_partial_data_degrades_without_crashing_pipeline():
    def build_context(request: AnalysisRequest) -> AnalysisContext:
        return AnalysisContext(
            request=request,
            quote={"price": 101.0},
            market_data={"price": 101.0, "ma5": 100.0},
        )

    pipeline = AnalysisPipeline(
        [TechnicalStrategy(), DecisionStrategy()],
        context_builder=build_context,
    )

    artifact = pipeline.run(AnalysisRequest(ticker="AMD"))

    technical = artifact.strategy_results["technical"]
    decision = artifact.strategy_results["decision"]

    assert technical.status == "partial"
    assert decision.status == "ok"
    assert decision.payload["action"] == "hold"
    assert "technical:partial" in artifact.degradation_summary


def test_default_strategy_chain_runs_end_to_end_with_mixed_context():
    def build_context(request: AnalysisRequest) -> AnalysisContext:
        return AnalysisContext(
            request=request,
            quote={"price": 105.0},
            market_data={
                "price": 105.0,
                "ma5": 102.0,
                "ma10": 100.0,
                "ma20": 97.0,
                "volatility": 0.22,
                "beta_60d": 1.05,
                "max_drawdown": -0.12,
            },
            fundamentals={
                "revenue_growth": 0.18,
                "gross_margin": 0.52,
                "free_cash_flow": 1200000,
                "debt_to_equity": 0.6,
                "current_ratio": 1.4,
                "pe_ratio": 22.0,
            },
            news=[
                {"sentiment_score": 4.4},
                {"sentiment_score": 4.1},
            ],
            social=[{"llm_sentiment": 4.0}],
        )

    pipeline = AnalysisPipeline(build_default_strategies(), context_builder=build_context)
    artifact = pipeline.run(AnalysisRequest(ticker="NVDA"))

    assert list(artifact.strategy_results.keys()) == [
        "technical",
        "fundamental",
        "sentiment",
        "risk",
        "decision",
    ]
    assert artifact.strategy_results["fundamental"].status == "ok"
    assert artifact.strategy_results["sentiment"].status == "ok"
    assert artifact.strategy_results["risk"].status == "ok"
    assert artifact.strategy_results["decision"].payload["action"] == "buy"


def test_default_strategy_chain_degrades_when_nontechnical_context_is_missing():
    def build_context(request: AnalysisRequest) -> AnalysisContext:
        return AnalysisContext(
            request=request,
            quote={"price": 99.0},
            market_data={
                "price": 99.0,
                "ma5": 100.0,
                "ma10": 101.0,
                "ma20": 102.0,
            },
        )

    pipeline = AnalysisPipeline(build_default_strategies(), context_builder=build_context)
    artifact = pipeline.run(AnalysisRequest(ticker="AMD"))

    assert artifact.strategy_results["technical"].status == "ok"
    assert artifact.strategy_results["fundamental"].status == "skipped"
    assert artifact.strategy_results["sentiment"].status == "skipped"
    assert artifact.strategy_results["risk"].status == "skipped"
    assert "fundamental:skipped" in artifact.degradation_summary
    assert "sentiment:skipped" in artifact.degradation_summary
    assert "risk:skipped" in artifact.degradation_summary
    assert artifact.strategy_results["decision"].status == "ok"


def test_render_report_includes_strategy_sections_and_degradation_summary():
    def build_context(request: AnalysisRequest) -> AnalysisContext:
        return AnalysisContext(
            request=request,
            quote={"price": 99.0},
            market_data={"price": 99.0, "ma5": 100.0, "ma10": 101.0, "ma20": 102.0},
        )

    pipeline = AnalysisPipeline(build_default_strategies(), context_builder=build_context)
    artifact = pipeline.run(AnalysisRequest(ticker="AMD"))
    integrity = validate_and_repair_artifact(artifact)
    report = render_report(integrity, fmt="markdown")

    assert report is not None
    assert "# AMD" in report.content
    assert "## Technical" in report.content
    assert "## Decision" in report.content
    assert "## Context" in report.content
    assert "## Degradation" in report.content
    assert "fundamental:skipped" in report.content


def test_render_scheduled_batch_returns_reports_for_default_pipeline():
    def build_context(request: AnalysisRequest) -> AnalysisContext:
        return AnalysisContext(
            request=request,
            quote={"price": 105.0},
            market_data={
                "price": 105.0,
                "ma5": 102.0,
                "ma10": 100.0,
                "ma20": 97.0,
                "volatility": 0.22,
                "beta_60d": 1.05,
                "max_drawdown": -0.12,
            },
            fundamentals={
                "revenue_growth": 0.18,
                "gross_margin": 0.52,
                "free_cash_flow": 1200000,
                "debt_to_equity": 0.6,
            },
            news=[{"sentiment_score": 4.2}, {"sentiment_score": 4.0}, {"sentiment_score": 4.1}],
        )

    pipeline = AnalysisPipeline(build_default_strategies(), context_builder=build_context)
    rendered = render_scheduled_batch(pipeline, ["NVDA", "AMD"])

    assert len(rendered) == 2
    assert rendered[0].startswith("# NVDA")
    assert "Action: buy" in rendered[0]


class _StubBar:
    def __init__(self, datetime: str, close: float):
        self.datetime = datetime
        self.close = close


class _StubPriceResult:
    def __init__(self, bars):
        self.bars = bars


class _StubNewsArticle:
    def __init__(self, sentiment_score: float):
        self.date = "2026-04-15"
        self.title = "Stub news"
        self.source = "test"
        self.publisher = "test"
        self.sentiment_score = sentiment_score
        self.risk_score = 2.0
        self.description = "stub"
        self.url = "https://example.com"


class _StubNewsResult:
    def __init__(self, articles):
        self.articles = articles


class _StubDetailedFinancials:
    def model_dump(self, exclude_none: bool = True):
        assert exclude_none is True
        return {
            "revenue_growth": 0.15,
            "gross_margin": 0.48,
            "free_cash_flow": 500000.0,
            "debt_to_equity": 0.7,
            "current_ratio": 1.3,
            "pe_ratio": 24.0,
        }


class _StubDal:
    backend_type = "StubBackend"

    def get_prices(self, ticker: str, interval: str = "1d", days: int = 90):
        del ticker, interval, days
        bars = []
        for idx, close in enumerate(range(100, 130)):
            bars.append(_StubBar(f"2026-03-{idx + 1:02d}", float(close)))
        return _StubPriceResult(bars)

    def get_news(self, ticker: str, days: int = 14, scored_only: bool = True):
        del ticker, days, scored_only
        return _StubNewsResult(
            [
                _StubNewsArticle(4.2),
                _StubNewsArticle(4.0),
                _StubNewsArticle(4.4),
            ]
        )


def test_build_dal_context_builder_uses_existing_data_access_contracts(monkeypatch):
    stub_dal = _StubDal()

    monkeypatch.setattr(
        "src.tools.analysis_tools.get_detailed_financials",
        lambda dal, ticker: _StubDetailedFinancials(),
    )

    builder = build_dal_context_builder(stub_dal)
    context = builder(AnalysisRequest(ticker="NVDA"))

    assert context.quote["price"] == 129.0
    assert context.market_data["ma5"] is not None
    assert context.market_data["ma20"] is not None
    assert context.market_data["max_drawdown"] <= 0
    assert context.fundamentals["revenue_growth"] == 0.15
    assert len(context.news) == 3
    assert context.provider_status["backend_type"] == "StubBackend"


def test_build_default_pipeline_accepts_optional_dal(monkeypatch):
    stub_dal = _StubDal()

    monkeypatch.setattr(
        "src.tools.analysis_tools.get_detailed_financials",
        lambda dal, ticker: _StubDetailedFinancials(),
    )

    pipeline = build_default_pipeline(dal=stub_dal)
    artifact = pipeline.run(AnalysisRequest(ticker="NVDA"))

    assert artifact.strategy_results["technical"].status == "ok"
    assert artifact.strategy_results["fundamental"].status == "ok"
    assert artifact.strategy_results["sentiment"].status == "ok"
    assert artifact.strategy_results["decision"].payload["action"] == "buy"


def test_run_analysis_request_returns_artifact_integrity_and_report(monkeypatch):
    stub_dal = _StubDal()

    monkeypatch.setattr(
        "src.tools.analysis_tools.get_detailed_financials",
        lambda dal, ticker: _StubDetailedFinancials(),
    )

    output = run_analysis_request(
        AnalysisRequest(ticker="NVDA"),
        dal=stub_dal,
    )

    assert output.artifact.request.ticker == "NVDA"
    assert output.integrity.status == "clean"
    assert output.report is not None
    assert output.report.content.startswith("# NVDA")


def test_save_analysis_run_uses_shared_report_tools(monkeypatch):
    output = run_analysis_request(
        AnalysisRequest(ticker="NVDA"),
        dal=None,
    )

    captured = {}

    def _fake_save_report(dal, **kwargs):
        del dal
        captured.update(kwargs)
        return {
            "id": 42,
            "file_path": "data/reports/fake.md",
            "title": kwargs["title"],
            "created_at": "2026-04-15T00:00:00",
        }

    monkeypatch.setattr("src.tools.report_tools.save_report", _fake_save_report)

    saved = save_analysis_run(object(), output, title="NVDA Phase D Analysis")

    assert saved.id == 42
    assert saved.file_path == "data/reports/fake.md"
    assert captured["report_type"] == "phase_d_analysis"
    assert captured["provider"] == "phase_d"
    assert captured["model"] == "structured-pipeline"
    assert captured["tickers"] == ["NVDA"]
