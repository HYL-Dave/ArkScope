"""Tests for enhanced backtest metrics, artifacts, and registry integration."""

import json
import os

import numpy as np
import pytest

from training.backtest import compute_metrics, save_artifacts, _get_git_sha


# ── compute_metrics ──────────────────────────────────────────


class TestComputeMetrics:
    def test_basic_positive_returns(self):
        """Growing equity should produce positive metrics."""
        equity = [100, 101, 102, 103, 104, 105]
        m = compute_metrics(equity)
        assert m["final_equity"] == 105.0
        assert m["total_return"] > 0
        assert m["sharpe_ratio"] is not None
        assert m["sharpe_ratio"] > 0
        assert m["max_drawdown"] <= 0  # drawdown is always <= 0
        assert m["win_rate"] == 1.0  # all days positive
        assert m["n_trading_days"] == 5

    def test_basic_negative_returns(self):
        """Declining equity should produce negative metrics."""
        equity = [100, 99, 98, 97, 96]
        m = compute_metrics(equity)
        assert m["total_return"] < 0
        assert m["sharpe_ratio"] < 0
        assert m["max_drawdown"] < 0
        assert m["win_rate"] == 0.0

    def test_ir_always_none(self):
        """IR requires benchmark — should always be None with ir_note."""
        equity = [100, 110, 120]
        m = compute_metrics(equity)
        assert m["information_ratio"] is None
        assert "benchmark" in m["ir_note"].lower()

    def test_insufficient_data_single_point(self):
        """Single equity point → all ratios None."""
        m = compute_metrics([100])
        assert m["final_equity"] == 100.0
        assert m["total_return"] is None
        assert m["sharpe_ratio"] is None
        assert m["max_drawdown"] is None

    def test_insufficient_data_empty(self):
        """Empty equity → final_equity 0."""
        m = compute_metrics([])
        assert m["final_equity"] == 0.0

    def test_zero_volatility(self):
        """Constant equity → sharpe = 0 (not inf/nan)."""
        equity = [100, 100, 100, 100, 100]
        m = compute_metrics(equity)
        assert m["sharpe_ratio"] == 0.0
        assert "zero volatility" in m.get("sharpe_ratio_note", "").lower()

    def test_no_drawdown(self):
        """Monotonically increasing equity → calmar = None."""
        equity = [100, 101, 102, 103, 104]
        m = compute_metrics(equity)
        assert m["max_drawdown"] == 0.0
        assert m["calmar_ratio"] is None
        assert "drawdown" in m.get("calmar_ratio_note", "").lower()

    def test_zero_downside_std(self):
        """No downside variance → sortino = 0."""
        # All returns are positive (after subtracting tiny risk-free)
        # Use large returns to overwhelm the daily risk-free
        equity = [100, 150, 200, 300]
        m = compute_metrics(equity, risk_free_rate=0.0)
        # All excess returns positive → no downside
        assert m["sortino_ratio"] is None or m["sortino_ratio"] == 0.0

    def test_cvar_computed(self):
        """CVaR should be a real number."""
        rng = np.random.default_rng(42)
        equity = list(np.cumsum(rng.normal(0.001, 0.01, 100)) + 100)
        m = compute_metrics(equity)
        assert m["cvar_95"] is not None
        assert isinstance(m["cvar_95"], float)

    def test_no_nan_or_inf(self):
        """No metric should ever be NaN or Inf."""
        test_cases = [
            [100, 101, 102],
            [100, 99, 98],
            [100, 100, 100],
            [100, 50, 100],  # V-shaped
            [100],
        ]
        for eq in test_cases:
            m = compute_metrics(eq)
            for k, v in m.items():
                if isinstance(v, float):
                    assert not np.isnan(v), f"NaN in {k} for equity={eq}"
                    assert not np.isinf(v), f"Inf in {k} for equity={eq}"

    def test_drawdown_values(self):
        """Check drawdown is computed correctly."""
        equity = [100, 110, 90, 95]
        m = compute_metrics(equity)
        # Peak was 110, trough was 90 → drawdown = (90-110)/110 ≈ -0.1818
        assert m["max_drawdown"] == pytest.approx(-20 / 110, abs=1e-4)

    def test_calmar_ratio(self):
        """Calmar = annualized_return / |max_drawdown|."""
        equity = [100, 110, 90, 120]
        m = compute_metrics(equity)
        if m["calmar_ratio"] is not None:
            assert m["calmar_ratio"] == pytest.approx(
                m["annualized_return"] / abs(m["max_drawdown"]), rel=1e-4
            )


# ── save_artifacts ───────────────────────────────────────────


class TestPrintSummaryEdgeCases:
    def test_single_point_no_crash(self, capsys):
        """Printing metrics with None total_return should not crash."""
        metrics = compute_metrics([100])
        # Simulate the print logic from main()
        tr = metrics.get("total_return")
        line = f"{tr * 100:.2f}%" if tr is not None else "N/A"
        assert line == "N/A"


class TestSaveArtifacts:
    def test_creates_daily_returns_csv(self, tmp_path):
        """daily_returns.csv should have date, equity, daily_return, drawdown."""
        import pandas as pd

        class MockEnv:
            pass

        equity = [100, 101, 102]
        dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
        metrics = compute_metrics(equity)
        paths = save_artifacts(MockEnv(), equity, metrics, dates, str(tmp_path))

        assert "daily_returns" in paths
        df = pd.read_csv(paths["daily_returns"])
        assert "date" in df.columns
        assert "equity" in df.columns
        assert "daily_return" in df.columns
        assert "drawdown" in df.columns

    def test_creates_equity_curve_png(self, tmp_path):
        class MockEnv:
            pass

        equity = [100, 101, 102]
        metrics = compute_metrics(equity)
        paths = save_artifacts(MockEnv(), equity, metrics, ["d1", "d2", "d3"], str(tmp_path))

        assert "equity_curve" in paths
        assert os.path.exists(paths["equity_curve"])
        assert paths["equity_curve"].endswith(".png")

    def test_non_date_strings_no_warning(self, tmp_path):
        """Non-date strings as dates should not produce pandas warnings."""
        import warnings as w

        class MockEnv:
            pass

        equity = [100, 101, 102]
        metrics = compute_metrics(equity)
        with w.catch_warnings():
            w.simplefilter("error")  # turn warnings into errors
            # "d1", "d2" are not dates — should fall back to step-based x-axis
            paths = save_artifacts(MockEnv(), equity, metrics, ["d1", "d2", "d3"], str(tmp_path))
        assert "equity_curve" in paths

    def test_handles_action_memory(self, tmp_path):
        """If env has save_action_memory(), it should create actions_log.csv."""
        import pandas as pd

        class MockEnvWithActions:
            def save_action_memory(self):
                return pd.DataFrame({"action": [0, 1, 0]})

        equity = [100, 101, 102]
        metrics = compute_metrics(equity)
        paths = save_artifacts(
            MockEnvWithActions(), equity, metrics,
            ["d1", "d2", "d3"], str(tmp_path),
        )
        assert "actions_log" in paths


# ── _get_git_sha ─────────────────────────────────────────────


class TestGitSha:
    def test_returns_string(self):
        sha = _get_git_sha()
        assert isinstance(sha, str)
        # In this repo, should be non-empty
        if sha:
            assert len(sha) >= 7


# ── IR=None contract in rl_tools ─────────────────────────────


class TestIRNoteContract:
    def test_backtest_report_includes_ir_note(self, monkeypatch, tmp_path):
        """When backtest_results has IR=None + ir_note, report should include ir_note."""
        monkeypatch.setattr("src.tools.rl_tools._is_enabled", lambda: True)
        monkeypatch.setattr("src.tools.rl_tools._get_models_dir", lambda: str(tmp_path))

        from training.model_registry import ModelMetadata, ModelRegistry
        registry = ModelRegistry(models_dir=str(tmp_path))
        meta = ModelMetadata(
            model_id="test_ir",
            algorithm="PPO",
            score_source="test",
            training_date="2026-03-01",
            backtest_results={
                "sharpe_ratio": 1.5,
                "information_ratio": None,
                "ir_note": "Requires --benchmark flag (e.g. SPY).",
                "max_drawdown": -0.10,
            },
        )
        registry.save_metadata(meta)

        from src.tools.rl_tools import get_rl_backtest_report
        result = json.loads(get_rl_backtest_report(None, model_id="test_ir"))
        assert result["backtest_results"]["information_ratio"] is None
        assert "ir_note" in result
        assert "benchmark" in result["ir_note"].lower()

    def test_model_status_includes_ir_note(self, monkeypatch, tmp_path):
        """Model status should include ir_note when IR is None."""
        monkeypatch.setattr("src.tools.rl_tools._is_enabled", lambda: True)
        monkeypatch.setattr("src.tools.rl_tools._get_models_dir", lambda: str(tmp_path))

        from training.model_registry import ModelMetadata, ModelRegistry
        registry = ModelRegistry(models_dir=str(tmp_path))
        meta = ModelMetadata(
            model_id="test_ir_status",
            algorithm="PPO",
            score_source="test",
            training_date="2026-03-01",
            backtest_results={
                "information_ratio": None,
                "ir_note": "Requires --benchmark.",
            },
        )
        registry.save_metadata(meta)

        from src.tools.rl_tools import get_rl_model_status
        result = json.loads(get_rl_model_status(None))
        model_entry = result["models"][0]
        assert model_entry["information_ratio"] is None
        assert "ir_note" in model_entry
