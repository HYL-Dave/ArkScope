from __future__ import annotations

import inspect
import re
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (_ROOT / path).read_text(encoding="utf-8")


def test_current_authorities_make_no_legacy_capability_claim():
    current_authorities = (
        "README.md",
        "PROJECT_STRUCTURE.md",
        "docs/design/AGENT_EVOLUTION_TRACKER.md",
        "docs/design/ARKSCOPE_TOOL_CATALOG.md",
        "docs/design/ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md",
        "docs/design/DESKTOP_APP_CARRYOVER_ANALYSIS.md",
        "docs/design/PHASE_C_UNIFIED_RUNNER_SPEC.md",
        "docs/design/PHASE_D_ANALYSIS_PIPELINE_SKETCH.md",
        "docs/design/README.md",
        "docs/design/REFACTOR_PROTECTION_SMOKE_GATES.md",
        "docs/design/SCRIPTS_RETIREMENT_DECISION.md",
        "data_sources/API_SPECIFICATIONS.md",
    )
    runnable_legacy_claims = (
        "scripts/scoring/",
        "python -m scripts.scoring",
        "src/tools/signal_tools.py",
        "src/signals/",
        "src/analysis/pipeline.py",
        "/analysis/run",
        "analysis_watchlist_batch",
        "get_news_sentiment_summary",
        "synthesize_signal",
        "get_signal_factors",
    )

    offenders = {
        path: [claim for claim in runnable_legacy_claims if claim in _read(path)]
        for path in current_authorities
    }
    assert {path: claims for path, claims in offenders.items() if claims} == {}


def test_fresh_schemas_create_no_legacy_score_storage():
    from src.market_data_admin import _NEWS_SCHEMA
    from src.news_normalized.schema import ARTICLE_SCHEMA

    postgres_schema = _read("sql/001_init_schema.sql")
    combined = "\n".join((_NEWS_SCHEMA, ARTICLE_SCHEMA, postgres_schema)).lower()
    forbidden = (
        "news_article_scores",
        "sentiment_score",
        "sentiment_source",
        "sentiment_scale",
        "risk_score",
        "scored_model",
        "create table if not exists signals",
        "news_sentiment_summary",
    )
    assert [token for token in forbidden if token in combined] == []
    assert not (_ROOT / "sql/002_add_news_scores.sql").exists()


def test_model_visible_contracts_exclude_legacy_score_and_composite_capabilities():
    from src.tools.registry import create_default_registry

    registry = create_default_registry()
    names = set(registry.list_names())
    retired = {
        "get_news_sentiment_summary",
        "detect_anomalies",
        "synthesize_signal",
        "get_signal_factors",
    }
    assert names.isdisjoint(retired)
    assert {"detect_news_volume_anomaly", "detect_event_chains"} <= names

    model_copy = "\n".join(
        _read(path)
        for path in (
            "src/agents/shared/prompts.py",
            "src/agents/shared/subagent.py",
            "src/agents/anthropic_agent/tools.py",
            "src/agents/openai_agent/tools.py",
        )
    )
    forbidden_copy = (
        "sentiment scores (1-5 scale)",
        "get_news_sentiment_summary",
        "synthesize_signal",
        "get_signal_factors",
        "scored news",
    )
    assert [phrase for phrase in forbidden_copy if phrase in model_copy] == []


def test_ordinary_news_contract_has_no_legacy_score_fields():
    from src.tools.schemas import NewsArticle, NewsBrief

    article_fields = set(NewsArticle.model_fields)
    brief_fields = set(NewsBrief.model_fields)
    retired = {
        "sentiment_score",
        "risk_score",
        "scored_count",
        "avg_sentiment",
        "avg_risk",
        "bullish_count",
        "bearish_count",
    }
    assert article_fields == {
        "date", "ticker", "title", "source", "url", "publisher", "description"
    }
    assert brief_fields == {
        "ticker", "article_count", "earliest_date", "latest_date"
    }
    assert (article_fields | brief_fields).isdisjoint(retired)


def test_provider_native_sentiment_and_investor_risk_contracts_are_preserved():
    from src.collectors.polygon_news import NewsArticle as PolygonNewsArticle
    from src.investor_profile import InvestorProfile
    from src.tools.schemas import NewsArticle

    assert {"source_sentiment", "source_sentiment_label"} <= {
        field.name for field in __import__("dataclasses").fields(PolygonNewsArticle)
    }
    assert {"risk_appetite", "risk_capacity"} <= {
        field.name for field in __import__("dataclasses").fields(InvestorProfile)
    }
    assert {"sentiment_score", "risk_score"}.isdisjoint(NewsArticle.model_fields)


def test_raw_news_backend_contract_has_no_score_parameters():
    from src.tools.backends import DataBackend
    from src.tools.data_access import DataAccessLayer

    expected_query = {"self", "ticker", "days", "source"}
    expected_search = {"self", "query", "ticker", "days", "limit"}
    assert set(inspect.signature(DataBackend.query_news).parameters) == expected_query
    assert set(inspect.signature(DataAccessLayer.get_news).parameters) == expected_query
    assert set(inspect.signature(DataAccessLayer.search_news).parameters) == expected_search

    class Backend:
        def __init__(self):
            self.calls = []

        def query_news(self, ticker=None, days=30, source="auto"):
            import pandas as pd

            self.calls.append((ticker, days, source))
            return pd.DataFrame(
                [{
                    "date": "2026-08-08T10:00:00+0000",
                    "ticker": "NVDA",
                    "title": "Raw headline",
                    "source": "polygon",
                    "url": "https://example.test/raw",
                    "publisher": "Wire",
                    "description": "Raw excerpt",
                }]
            )

        def get_available_tickers(self, data_type):
            return []

    backend = Backend()
    result = DataAccessLayer(base_path=_ROOT, backend=backend).get_news(
        ticker="NVDA", days=2, source="polygon"
    )
    assert backend.calls == [("NVDA", 2, "polygon")]
    assert result.model_dump() == {
        "ticker": "NVDA",
        "count": 1,
        "articles": [{
            "date": "2026-08-08T10:00:00+0000",
            "ticker": "NVDA",
            "title": "Raw headline",
            "source": "polygon",
            "url": "https://example.test/raw",
            "publisher": "Wire",
            "description": "Raw excerpt",
        }],
        "source_breakdown": {"polygon": 1},
        "query_days": 2,
    }


def test_runtime_legacy_score_consumer_writer_census_is_closed_and_empty():
    runtime_roots = ("src", "apps/arkscope-web/src", "scripts", "config")
    patterns = {
        "news_article_scores": re.compile(r"\bnews_article_scores\b"),
        "score_import": re.compile(r"\bscore_(?:import|migration)\b"),
        "score_api": re.compile(
            r"\b(?:scored_only|get_news_sentiment_summary|sentiment_score|"
            r"sentiment_source|sentiment_scale)\b"
        ),
        "signal_runtime": re.compile(
            r"\b(?:synthesize_signal|get_signal_factors|SignalWatcher|"
            r"SentimentWatcher|analysis_watchlist_batch|analysis_pipeline_enabled)\b|"
            r"src\.signals|src\.tools\.signal_tools|/analysis/run|/signals"
        ),
    }
    allowed = {
        "src/evidence_packet.py": {"score_api", "signal_runtime"},
        "src/collectors/polygon_news.py": {"score_api"},
    }
    rows: list[tuple[str, str]] = []
    for root_name in runtime_roots:
        root = _ROOT / root_name
        if not root.exists():
            continue
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            if path.suffix not in {".py", ".ts", ".tsx", ".yaml", ".md"}:
                continue
            relative = path.relative_to(_ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            for label, pattern in patterns.items():
                if pattern.search(text) and label not in allowed.get(relative, set()):
                    rows.append((relative, label))
    assert rows == []


def test_scoring_scripts_and_root_package_are_absent():
    assert not (_ROOT / "scripts").exists()
    assert not (_ROOT / "training").exists()
    assert not (_ROOT / "tests/live/smoke_yfinance.py").exists()

    requirements = _read("requirements.txt").lower()
    ownerless = (
        "gymnasium", "torch", "datasets", "mpi4py", "spinup",
        "matplotlib", "stable-baselines3", "yfinance",
    )
    assert [package for package in ownerless if re.search(
        rf"(?m)^\s*{re.escape(package)}(?:\b|[<>=])", requirements
    )] == []
