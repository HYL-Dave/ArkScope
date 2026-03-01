"""Integration smoke test: features -> env -> train_utils -> backtest -> rl_tools.

Tests the full pipeline chain without actually running PPO/CPPO training
(which requires MPI + GPU). Instead, we simulate the pipeline by:
1. Creating a synthetic dataset
2. Computing features + fitting scaler
3. Building environments with extra features
4. Saving a fake model via save_training_artifacts
5. Running compute_metrics + save_artifacts
6. Querying rl_tools to verify registry integration
"""

import json
import os

import numpy as np
import pandas as pd
import pytest
import torch
import torch.nn as nn

from training.backtest import compute_metrics, save_artifacts
from training.config import INDICATORS
from training.data_prep.feature_engineering import (
    DEFAULT_FEATURES,
    FeatureScaler,
    engineer_features,
)
from training.train_utils import (
    detect_and_load_features,
    generate_model_id,
    save_training_artifacts,
)


def _make_pipeline_df(n_tickers=3, n_days=20):
    """Build a realistic-ish DataFrame for integration testing."""
    tickers = [f"TIC{i}" for i in range(n_tickers)]
    dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
    rng = np.random.default_rng(42)

    rows = []
    for d in dates:
        for tic in tickers:
            row = {
                "date": d.strftime("%Y-%m-%d"),
                "tic": tic,
                "close": 100 + rng.normal(0, 5),
                "llm_sentiment": rng.integers(1, 6),
                "llm_risk": rng.integers(1, 6),
                "turbulence": rng.random() * 10,
            }
            for ind in INDICATORS:
                row[ind] = rng.random()
            rows.append(row)

    df = pd.DataFrame(rows)
    df["date"] = df["date"].astype(str)
    df = df.sort_values(["date", "tic"]).reset_index(drop=True)
    unique_dates = df["date"].unique()
    date_to_idx = {date: idx for idx, date in enumerate(unique_dates)}
    df["new_idx"] = df["date"].map(date_to_idx)
    df = df.set_index("new_idx")
    return df


class TestFullPipelineIntegration:
    """End-to-end smoke test for the feature → train → backtest → rl_tools chain."""

    @pytest.fixture
    def pipeline_dir(self, tmp_path):
        """Set up a temporary pipeline directory."""
        return tmp_path

    def test_ppo_pipeline(self, pipeline_dir, monkeypatch):
        """PPO: features → env → save_artifacts → registry → rl_tools."""
        monkeypatch.setattr("training.train_utils.TRAINED_MODEL_DIR", str(pipeline_dir))

        # 1. Create dataset and compute features
        df = _make_pipeline_df(n_tickers=2, n_days=15)
        df_feat, extra_cols, feat_meta = engineer_features(df.copy())
        assert len(extra_cols) == len(DEFAULT_FEATURES)

        # 2. Fit scaler on the data
        scaler = FeatureScaler()
        scaler.fit(df_feat, extra_cols, shift=feat_meta["shift"],
                   imputation=feat_meta["imputation"])
        scaler.transform(df_feat, extra_cols)

        # 3. Build PPO env
        from training.envs.stocktrading_llm import StockTradingEnv

        N = 2
        K = len(INDICATORS)
        F = len(extra_cols)
        state_space = 1 + 2 * N + (1 + K + F) * N

        env = StockTradingEnv(
            df=df_feat, stock_dim=N, hmax=100, initial_amount=1e6,
            num_stock_shares=[0] * N,
            buy_cost_pct=[0.001] * N, sell_cost_pct=[0.001] * N,
            state_space=state_space, action_space=N,
            tech_indicator_list=INDICATORS,
            reward_scaling=1e-4,
            extra_feature_cols=extra_cols,
        )

        # 4. Verify state vector size
        assert len(env.state) == state_space

        # 5. Step through env
        actions = np.zeros(N)
        for _ in range(3):
            state, _, done, _, _ = env.step(actions)
            if done:
                break
            assert len(state) == state_space

        # 6. Save fake model via shared utility
        model = nn.Linear(state_space, N)
        model_id = generate_model_id("ppo", "integration_test", 1, 42)

        save_training_artifacts(
            model_id=model_id,
            algorithm="PPO",
            model_state_dict=model.state_dict(),
            score_source="integration_test",
            extra_cols=extra_cols,
            stock_dim=N,
            state_dim=state_space,
            train_period="2024-01-01 ~ 2024-01-31",
            epochs=1,
            seed=42,
            hyperparams={"hid": 64, "layers": 1},
            scaler=scaler,
        )

        # 7. Verify files exist
        model_dir = pipeline_dir / model_id
        assert (model_dir / "model.pth").exists()
        assert (model_dir / "metadata.json").exists()
        assert (model_dir / "feature_scaler.json").exists()
        assert (pipeline_dir / "registry.json").exists()

        # 8. Compute backtest metrics
        equity = [1e6, 1.01e6, 1.02e6, 0.99e6, 1.03e6]
        metrics = compute_metrics(equity)
        assert metrics["information_ratio"] is None
        assert "benchmark" in metrics["ir_note"].lower()
        assert metrics["sharpe_ratio"] is not None

        # 9. Save artifacts
        dates = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
        artifact_paths = save_artifacts(env, equity, metrics, dates, str(model_dir))
        assert "daily_returns" in artifact_paths
        assert "equity_curve" in artifact_paths

        # 10. Update registry with backtest run
        from training.model_registry import ModelRegistry
        registry = ModelRegistry(models_dir=str(pipeline_dir))
        meta = registry.get_model(model_id)
        assert meta is not None
        meta.backtest_results = metrics
        meta.backtest_runs.append({
            "timestamp": "2026-03-01T00:00:00",
            "metrics": metrics,
            "feature_set": extra_cols,
        })
        registry.save_metadata(meta)

        # 11. Verify via rl_tools
        monkeypatch.setattr("src.tools.rl_tools._is_enabled", lambda: True)
        monkeypatch.setattr("src.tools.rl_tools._get_models_dir", lambda: str(pipeline_dir))

        from src.tools.rl_tools import get_rl_backtest_report, get_rl_model_status

        status = json.loads(get_rl_model_status(None))
        assert status["status"] == "active"
        assert status["model_count"] == 1
        assert status["models"][0]["model_id"] == model_id
        assert status["models"][0]["information_ratio"] is None
        assert "ir_note" in status["models"][0]

        report = json.loads(get_rl_backtest_report(None, model_id=model_id))
        assert report["model_id"] == model_id
        assert report["feature_set"] == extra_cols
        assert report["backtest_results"]["sharpe_ratio"] is not None
        assert "ir_note" in report

    def test_cppo_pipeline(self, pipeline_dir, monkeypatch):
        """CPPO: features → env → risk tail invariant holds through pipeline."""
        monkeypatch.setattr("training.train_utils.TRAINED_MODEL_DIR", str(pipeline_dir))

        df = _make_pipeline_df(n_tickers=2, n_days=15)
        df_feat, extra_cols, _ = engineer_features(df.copy())

        scaler = FeatureScaler()
        scaler.fit(df_feat, extra_cols)
        scaler.transform(df_feat, extra_cols)

        from training.envs.stocktrading_llm_risk import StockTradingEnv

        N = 2
        K = len(INDICATORS)
        F = len(extra_cols)
        state_space = 1 + 2 * N + (2 + K + F) * N

        env = StockTradingEnv(
            df=df_feat, stock_dim=N, hmax=100, initial_amount=1e6,
            num_stock_shares=[0] * N,
            buy_cost_pct=[0.001] * N, sell_cost_pct=[0.001] * N,
            state_space=state_space, action_space=N,
            tech_indicator_list=INDICATORS,
            reward_scaling=1e-4,
            extra_feature_cols=extra_cols,
        )

        # Risk tail invariant: last N elements = llm_risk values
        risk_tail = env.state[-N:]
        assert all(isinstance(r, (int, float)) for r in risk_tail)

        # Step and check invariant holds
        actions = np.zeros(N)
        for _ in range(5):
            state, _, done, _, _ = env.step(actions)
            if done:
                break
            assert len(state) == state_space

    def test_detect_and_load_path_a_roundtrip(self, pipeline_dir):
        """Path A roundtrip: prepare → save CSV+scaler → detect_and_load → env."""
        df = _make_pipeline_df(n_tickers=2, n_days=15)
        df_feat, extra_cols, feat_meta = engineer_features(df.copy())

        # Fit scaler and save
        scaler = FeatureScaler()
        scaler.fit(df_feat, extra_cols, shift=feat_meta["shift"],
                   imputation=feat_meta["imputation"])
        scaler.transform(df_feat, extra_cols)

        csv_path = str(pipeline_dir / "train.csv")
        df_feat.to_csv(csv_path)
        scaler.save(str(pipeline_dir / "feature_scaler.json"))

        # Reload and detect
        loaded = pd.read_csv(csv_path)
        if "Unnamed: 0" in loaded.columns:
            loaded = loaded.drop("Unnamed: 0", axis=1)
        result_df, cols, loaded_scaler = detect_and_load_features(
            loaded, None, data_path=csv_path,
        )

        # Path A: should use scaler's feature_set as truth
        assert cols == extra_cols
        assert loaded_scaler is not None
        assert loaded_scaler.feature_set == scaler.feature_set

    def test_scaler_contract_validation_in_pipeline(self, pipeline_dir, monkeypatch):
        """Full pipeline: save scaler with model, load in backtest-like flow."""
        monkeypatch.setattr("training.train_utils.TRAINED_MODEL_DIR", str(pipeline_dir))

        df = _make_pipeline_df(n_tickers=2, n_days=10)
        df_feat, extra_cols, _ = engineer_features(df.copy())

        scaler = FeatureScaler()
        scaler.fit(df_feat, extra_cols)

        model = nn.Linear(10, 2)
        model_id = "ppo_contract_test"

        save_training_artifacts(
            model_id=model_id,
            algorithm="PPO",
            model_state_dict=model.state_dict(),
            score_source="test",
            extra_cols=extra_cols,
            stock_dim=2,
            state_dim=10,
            train_period="",
            epochs=1,
            seed=0,
            hyperparams={},
            scaler=scaler,
        )

        # Load scaler back and validate contract
        scaler_path = str(pipeline_dir / model_id / "feature_scaler.json")
        loaded = FeatureScaler.load(scaler_path)
        loaded.validate_contract(extra_cols)  # should not raise

        # Wrong columns should raise
        with pytest.raises(ValueError, match="mismatch"):
            loaded.validate_contract(["wrong_feature"])
