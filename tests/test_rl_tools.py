"""Tests for RL Pipeline tools and model registry."""

import json
import re

import pytest


def _unwrap(result: str) -> str:
    """Strip <tool_output> wrapping to get raw JSON/text."""
    m = re.search(r"<tool_output[^>]*>\n(.*)\n</tool_output>", result, re.DOTALL)
    return m.group(1) if m else result


# ============================================================
# ModelMetadata Tests
# ============================================================

class TestModelMetadata:
    def test_create_default(self):
        from training.model_registry import ModelMetadata
        m = ModelMetadata(model_id="test_model", algorithm="PPO", score_source="gpt5")
        assert m.model_id == "test_model"
        assert m.algorithm == "PPO"
        assert m.score_type == "sentiment"
        assert m.feature_set == []
        assert m.backtest_results == {}

    def test_to_dict(self):
        from training.model_registry import ModelMetadata
        m = ModelMetadata(
            model_id="ppo_test",
            algorithm="PPO",
            score_source="claude",
            stock_dim=5,
            backtest_results={"sharpe_ratio": 1.5},
        )
        d = m.to_dict()
        assert d["model_id"] == "ppo_test"
        assert d["stock_dim"] == 5
        assert d["backtest_results"]["sharpe_ratio"] == 1.5

    def test_from_dict(self):
        from training.model_registry import ModelMetadata
        d = {
            "model_id": "cppo_v1",
            "algorithm": "CPPO",
            "score_source": "polygon",
            "epochs": 100,
            "hyperparams": {"gamma": 0.99},
        }
        m = ModelMetadata.from_dict(d)
        assert m.model_id == "cppo_v1"
        assert m.algorithm == "CPPO"
        assert m.epochs == 100
        assert m.hyperparams["gamma"] == 0.99

    def test_from_dict_ignores_unknown_keys(self):
        from training.model_registry import ModelMetadata
        d = {
            "model_id": "test",
            "algorithm": "PPO",
            "score_source": "x",
            "future_field": "ignored",
        }
        m = ModelMetadata.from_dict(d)
        assert m.model_id == "test"
        assert not hasattr(m, "future_field")

    def test_roundtrip(self):
        from training.model_registry import ModelMetadata
        m = ModelMetadata(
            model_id="roundtrip",
            algorithm="PPO",
            score_source="claude",
            feature_set=["sentiment_7d_ma", "news_count"],
            backtest_results={"sharpe_ratio": 2.1, "max_drawdown": -0.15},
        )
        d = m.to_dict()
        m2 = ModelMetadata.from_dict(d)
        assert m2.model_id == m.model_id
        assert m2.feature_set == m.feature_set
        assert m2.backtest_results == m.backtest_results

    def test_backtest_runs_default_empty(self):
        from training.model_registry import ModelMetadata
        m = ModelMetadata(model_id="test", algorithm="PPO", score_source="x")
        assert m.backtest_runs == []

    def test_backtest_runs_append(self):
        from training.model_registry import ModelMetadata
        m = ModelMetadata(model_id="test", algorithm="PPO", score_source="x")
        run = {"timestamp": "2026-03-01", "metrics": {"sharpe_ratio": 1.5}}
        m.backtest_runs.append(run)
        assert len(m.backtest_runs) == 1
        d = m.to_dict()
        assert d["backtest_runs"][0]["metrics"]["sharpe_ratio"] == 1.5

    def test_from_dict_without_backtest_runs(self):
        """Old JSON without backtest_runs should still load (backward compat)."""
        from training.model_registry import ModelMetadata
        d = {
            "model_id": "old_model",
            "algorithm": "PPO",
            "score_source": "claude",
            "training_date": "2026-01-01",
        }
        m = ModelMetadata.from_dict(d)
        assert m.backtest_runs == []

    def test_utc_z_suffix_date_parsing(self):
        """training_date with Z suffix should parse correctly."""
        from training.model_registry import ModelRegistry
        dt = ModelRegistry._parse_date("2026-03-01T12:30:45Z")
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.hour == 12


# ============================================================
# ModelRegistry Tests
# ============================================================

class TestModelRegistry:
    @pytest.fixture
    def registry(self, tmp_path):
        from training.model_registry import ModelRegistry
        return ModelRegistry(models_dir=str(tmp_path))

    @pytest.fixture
    def sample_meta(self):
        from training.model_registry import ModelMetadata
        return ModelMetadata(
            model_id="ppo_test_20260301",
            algorithm="PPO",
            score_source="claude_opus",
            stock_dim=5,
            state_dim=56,
            train_period="2013-01-01 ~ 2018-12-31",
            test_period="2019-01-01 ~ 2023-12-31",
            epochs=10,
            training_date="2026-03-01",
            backtest_results={"sharpe_ratio": 1.8, "max_drawdown": -0.12},
        )

    def test_empty_registry(self, registry):
        assert registry.list_models() == []
        assert registry.get_model("nonexistent") is None
        assert registry.get_latest_model() is None

    def test_save_and_list(self, registry, sample_meta):
        registry.save_metadata(sample_meta)
        models = registry.list_models()
        assert len(models) == 1
        assert models[0].model_id == "ppo_test_20260301"
        assert models[0].backtest_results["sharpe_ratio"] == 1.8

    def test_get_model(self, registry, sample_meta):
        registry.save_metadata(sample_meta)
        m = registry.get_model("ppo_test_20260301")
        assert m is not None
        assert m.algorithm == "PPO"
        assert m.stock_dim == 5

    def test_get_latest_model(self, registry):
        from training.model_registry import ModelMetadata
        m1 = ModelMetadata(
            model_id="old", algorithm="PPO", score_source="x",
            training_date="2026-01-01",
        )
        m2 = ModelMetadata(
            model_id="new", algorithm="CPPO", score_source="x",
            training_date="2026-03-01",
        )
        registry.save_metadata(m1)
        registry.save_metadata(m2)

        latest = registry.get_latest_model()
        assert latest.model_id == "new"

    def test_sort_handles_inconsistent_date_formats(self, registry):
        """training_date with mixed formats should still sort correctly."""
        from training.model_registry import ModelMetadata
        m1 = ModelMetadata(
            model_id="oldest", algorithm="PPO", score_source="x",
            training_date="2025-12-15",
        )
        m2 = ModelMetadata(
            model_id="middle", algorithm="PPO", score_source="x",
            training_date="2026-01-05T14:30:00",
        )
        m3 = ModelMetadata(
            model_id="newest", algorithm="PPO", score_source="x",
            training_date="2026-03-01",
        )
        m4 = ModelMetadata(
            model_id="bad_date", algorithm="PPO", score_source="x",
            training_date="not-a-date",
        )
        m5 = ModelMetadata(
            model_id="empty_date", algorithm="PPO", score_source="x",
            training_date="",
        )
        for m in (m3, m1, m5, m2, m4):  # insert out of order
            registry.save_metadata(m)

        models = registry.list_models()
        ids = [m.model_id for m in models]
        # newest first; unparseable dates sort to the end (mutual order undefined)
        assert ids[:3] == ["newest", "middle", "oldest"]
        assert set(ids[3:]) == {"bad_date", "empty_date"}

    def test_get_latest_model_by_algorithm(self, registry):
        from training.model_registry import ModelMetadata
        m1 = ModelMetadata(
            model_id="ppo1", algorithm="PPO", score_source="x",
            training_date="2026-01-01",
        )
        m2 = ModelMetadata(
            model_id="cppo1", algorithm="CPPO", score_source="x",
            training_date="2026-03-01",
        )
        registry.save_metadata(m1)
        registry.save_metadata(m2)

        ppo = registry.get_latest_model(algorithm="PPO")
        assert ppo.model_id == "ppo1"
        cppo = registry.get_latest_model(algorithm="CPPO")
        assert cppo.model_id == "cppo1"

    def test_save_overwrites_existing(self, registry, sample_meta):
        registry.save_metadata(sample_meta)
        sample_meta.epochs = 50
        registry.save_metadata(sample_meta)

        models = registry.list_models()
        assert len(models) == 1
        assert models[0].epochs == 50

    def test_metadata_json_file_created(self, registry, sample_meta, tmp_path):
        registry.save_metadata(sample_meta)
        meta_file = tmp_path / "ppo_test_20260301" / "metadata.json"
        assert meta_file.exists()
        with open(meta_file) as f:
            data = json.load(f)
        assert data["model_id"] == "ppo_test_20260301"

    def test_registry_json_created(self, registry, sample_meta, tmp_path):
        registry.save_metadata(sample_meta)
        reg_file = tmp_path / "registry.json"
        assert reg_file.exists()
        with open(reg_file) as f:
            data = json.load(f)
        assert len(data) == 1


# ============================================================
# RL Tools — Disabled State Tests
# ============================================================

class TestRLToolsDisabled:
    """Test RL tools when pipeline is disabled (default)."""

    @pytest.fixture(autouse=True)
    def _disable_rl(self, monkeypatch):
        """Ensure RL pipeline is disabled."""
        monkeypatch.setattr(
            "src.tools.rl_tools._is_enabled", lambda: False
        )

    def test_model_status_disabled(self):
        from src.tools.rl_tools import get_rl_model_status
        result = get_rl_model_status(None)
        assert any(s in result.lower() for s in ["not enabled", "not yet enabled", "disabled", "experimental"])
        assert "train" in result.lower()

    def test_prediction_disabled(self):
        from src.tools.rl_tools import get_rl_prediction
        result = get_rl_prediction(None, ticker="NVDA")
        assert any(s in result.lower() for s in ["not enabled", "not yet enabled", "disabled", "experimental"])

    def test_backtest_report_disabled(self):
        from src.tools.rl_tools import get_rl_backtest_report
        result = get_rl_backtest_report(None, model_id="latest")
        assert any(s in result.lower() for s in ["not enabled", "not yet enabled", "disabled", "experimental"])


# ============================================================
# RL Tools — Enabled State Tests
# ============================================================

class TestRLToolsEnabled:
    """Test RL tools when pipeline is enabled with mock registry."""

    @pytest.fixture(autouse=True)
    def _enable_rl(self, monkeypatch, tmp_path):
        """Enable RL pipeline with tmp models dir."""
        monkeypatch.setattr(
            "src.tools.rl_tools._is_enabled", lambda: True
        )
        monkeypatch.setattr(
            "src.tools.rl_tools._get_models_dir", lambda: str(tmp_path)
        )
        self._tmp = tmp_path

    def _save_model(self):
        from training.model_registry import ModelRegistry, ModelMetadata
        registry = ModelRegistry(models_dir=str(self._tmp))
        meta = ModelMetadata(
            model_id="ppo_test_20260301",
            algorithm="PPO",
            score_source="claude_opus",
            stock_dim=5,
            state_dim=56,
            training_date="2026-03-01",
            feature_set=["llm_sentiment"],
            train_period="2013 ~ 2018",
            backtest_results={
                "sharpe_ratio": 1.8,
                "information_ratio": 0.6,
                "max_drawdown": -0.12,
                "cvar_95": -0.04,
            },
        )
        registry.save_metadata(meta)
        return meta

    def test_model_status_no_models(self):
        from src.tools.rl_tools import get_rl_model_status
        result = json.loads(get_rl_model_status(None))
        assert result["status"] == "enabled_no_models"

    def test_model_status_with_models(self):
        self._save_model()
        from src.tools.rl_tools import get_rl_model_status
        result = json.loads(get_rl_model_status(None))
        assert result["status"] == "active"
        assert result["model_count"] == 1
        assert result["models"][0]["model_id"] == "ppo_test_20260301"
        assert result["models"][0]["sharpe_ratio"] == 1.8

    def test_prediction_model_found(self):
        self._save_model()
        from src.tools.rl_tools import get_rl_prediction
        result = json.loads(get_rl_prediction(None, ticker="NVDA"))
        assert result["status"] == "experimental_metadata_only"
        assert result["ticker"] == "NVDA"
        assert result["model_id"] == "ppo_test_20260301"
        assert result.get("experimental") is True
        assert "experimental" in result["note"].lower()

    def test_prediction_model_not_found(self):
        from src.tools.rl_tools import get_rl_prediction
        result = json.loads(get_rl_prediction(None, ticker="NVDA", model_id="nonexistent"))
        assert "error" in result

    def test_backtest_report(self):
        self._save_model()
        from src.tools.rl_tools import get_rl_backtest_report
        result = json.loads(get_rl_backtest_report(None, model_id="latest"))
        assert result["model_id"] == "ppo_test_20260301"
        assert result["algorithm"] == "PPO"
        assert result["backtest_results"]["sharpe_ratio"] == 1.8

    def test_backtest_report_by_id(self):
        self._save_model()
        from src.tools.rl_tools import get_rl_backtest_report
        result = json.loads(get_rl_backtest_report(None, model_id="ppo_test_20260301"))
        assert result["model_id"] == "ppo_test_20260301"

    def test_backtest_report_not_found(self):
        from src.tools.rl_tools import get_rl_backtest_report
        result = json.loads(get_rl_backtest_report(None, model_id="nonexistent"))
        assert "error" in result


# ============================================================
# Config Tests
# ============================================================

class TestRLConfig:
    def test_default_disabled(self):
        from src.agents.config import AgentConfig
        config = AgentConfig()
        assert config.rl_pipeline_enabled is False
        assert config.rl_models_dir == "trained_models"


# ============================================================
# Registry Integration Tests
# ============================================================

class TestRegistryRLTools:
    def test_registry_includes_rl_tools(self):
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        names = registry.list_names()
        assert "get_rl_model_status" in names
        assert "get_rl_prediction" in names
        assert "get_rl_backtest_report" in names

    def test_registry_tool_count(self):
        """Registry has base + rl tools."""
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        assert len(registry.list_all()) == 50  # 47 base + 3 rl


# ============================================================
# Anthropic Tool Schema Tests
# ============================================================

class TestAnthropicRLSchemas:
    def test_tool_names_include_rl(self):
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        names = {t["name"] for t in tools}
        assert "get_rl_model_status" in names
        assert "get_rl_prediction" in names
        assert "get_rl_backtest_report" in names

    def test_tool_count(self):
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        assert len(tools) == 51  # 50 registry tools + delegate_to_subagent


# ============================================================
# Anthropic Tool Execution Tests
# ============================================================

class TestAnthropicRLExecution:
    def test_execute_rl_model_status(self, monkeypatch):
        """execute_tool dispatches to get_rl_model_status."""
        monkeypatch.setattr(
            "src.tools.rl_tools._is_enabled", lambda: False
        )
        from src.agents.anthropic_agent.tools import execute_tool
        from src.tools.data_access import DataAccessLayer
        dal = DataAccessLayer()
        result = execute_tool("get_rl_model_status", {}, dal)
        text = _unwrap(result)
        assert any(s in text.lower() for s in ["not enabled", "not yet enabled", "disabled", "experimental"])


# ============================================================
# OpenAI Tool Creation Tests
# ============================================================

class TestOpenAIRLTools:
    def test_creates_rl_tools(self):
        from src.agents.openai_agent.tools import create_openai_tools
        from src.tools.data_access import DataAccessLayer
        dal = DataAccessLayer()
        tools = create_openai_tools(dal)
        names = {t.name for t in tools}
        assert "tool_get_rl_model_status" in names
        assert "tool_get_rl_prediction" in names
        assert "tool_get_rl_backtest_report" in names

    def test_tool_count(self):
        from src.agents.openai_agent.tools import create_openai_tools
        from src.tools.data_access import DataAccessLayer
        dal = DataAccessLayer()
        tools = create_openai_tools(dal)
        assert len(tools) == 51  # 50 registry tools + delegate_to_subagent


# ============================================================
# System Prompt Tests
# ============================================================

class TestSystemPromptRL:
    def test_system_prompt_mentions_rl(self):
        from src.agents.shared.prompts import SYSTEM_PROMPT
        assert "rl model" in SYSTEM_PROMPT.lower() or "rl_model" in SYSTEM_PROMPT.lower()

    def test_build_system_prompt_includes_rl_section(self):
        """build_system_prompt includes RL status section."""
        from src.agents.shared.prompts import build_system_prompt
        # Default config has rl_pipeline_enabled=False, so RL section shows
        # disabled + experimental warning about the collapse investigation.
        prompt = build_system_prompt()
        assert "RL MODELS" in prompt
        assert any(
            s in prompt.lower()
            for s in ("not yet enabled", "not enabled", "disabled", "experimental")
        )
