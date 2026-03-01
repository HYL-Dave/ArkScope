"""Tests for training/train_utils.py — shared utilities for PPO/CPPO scripts."""

import json
import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from training.config import INDICATORS
from training.data_prep.feature_engineering import AVAILABLE_FEATURES, FeatureScaler
from training.train_utils import (
    detect_and_load_features,
    file_hash,
    generate_model_id,
    save_training_artifacts,
)


# ── file_hash ────────────────────────────────────────────────


class TestFileHash:
    def test_deterministic(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b,c\n1,2,3\n")
        h1 = file_hash(str(f))
        h2 = file_hash(str(f))
        assert h1 == h2
        assert len(h1) == 6

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.csv"
        f2 = tmp_path / "b.csv"
        f1.write_text("hello")
        f2.write_text("world")
        assert file_hash(str(f1)) != file_hash(str(f2))


# ── generate_model_id ────────────────────────────────────────


class TestGenerateModelId:
    def test_format_without_data(self):
        mid = generate_model_id("ppo", "test", 100, 42)
        assert mid.startswith("ppo_test_100ep_s42_")
        assert mid.endswith("_hf")

    def test_format_with_data(self, tmp_path):
        f = tmp_path / "train.csv"
        f.write_text("data")
        mid = generate_model_id("cppo", "claude", 50, 0, data_path=str(f))
        assert mid.startswith("cppo_claude_50ep_s0_")
        assert not mid.endswith("_hf")
        # Should end with 6-char hash
        parts = mid.split("_")
        assert len(parts[-1]) == 6

    def test_algorithm_lowercased(self):
        mid = generate_model_id("CPPO", "test", 10, 0)
        assert mid.startswith("cppo_")


# ── detect_and_load_features ─────────────────────────────────


def _make_df(n_tickers=2, n_days=5, extra_cols=None):
    """Minimal df for feature detection tests."""
    tickers = [f"T{i}" for i in range(n_tickers)]
    dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
    rows = []
    for d in dates:
        for tic in tickers:
            row = {
                "date": d.strftime("%Y-%m-%d"),
                "tic": tic,
                "close": 100.0,
                "llm_sentiment": 3,
                "llm_risk": 2,
            }
            for ind in INDICATORS:
                row[ind] = 0.5
            for col in (extra_cols or []):
                row[col] = 1.5
            rows.append(row)
    return pd.DataFrame(rows)


class TestFindScalerPath:
    def test_tagged_scaler_preferred(self, tmp_path):
        """feature_scaler_{tag}.json is preferred over feature_scaler.json."""
        from training.train_utils import _find_scaler_path

        csv_path = str(tmp_path / "train_claude_opus.csv")
        tagged = tmp_path / "feature_scaler_claude_opus.json"
        legacy = tmp_path / "feature_scaler.json"
        tagged.write_text("{}")
        legacy.write_text("{}")
        assert _find_scaler_path(csv_path) == str(tagged)

    def test_legacy_fallback(self, tmp_path):
        """Falls back to feature_scaler.json if tagged doesn't exist."""
        from training.train_utils import _find_scaler_path

        csv_path = str(tmp_path / "train_claude_opus.csv")
        legacy = tmp_path / "feature_scaler.json"
        legacy.write_text("{}")
        assert _find_scaler_path(csv_path) == str(legacy)

    def test_neither_exists_returns_tagged(self, tmp_path):
        """If neither exists, return the tagged path (for error messages)."""
        from training.train_utils import _find_scaler_path

        csv_path = str(tmp_path / "train_test_data.csv")
        result = _find_scaler_path(csv_path)
        assert "feature_scaler_test_data.json" in result

    def test_trade_prefix_stripped(self, tmp_path):
        """trade_xxx.csv should find feature_scaler_xxx.json (not trade_xxx)."""
        from training.train_utils import _find_scaler_path

        csv_path = str(tmp_path / "trade_gpt5_high.csv")
        tagged = tmp_path / "feature_scaler_gpt5_high.json"
        tagged.write_text("{}")
        assert _find_scaler_path(csv_path) == str(tagged)

    def test_write_path_always_tagged(self, tmp_path):
        """Write path must always be tagged, even when legacy exists."""
        from training.train_utils import _build_scaler_write_path

        csv_path = str(tmp_path / "train_claude_opus.csv")
        legacy = tmp_path / "feature_scaler.json"
        legacy.write_text("{}")
        result = _build_scaler_write_path(csv_path)
        assert "feature_scaler_claude_opus.json" in result
        assert result != str(legacy)


class TestDetectAndLoadFeatures:
    def test_no_features_returns_empty(self):
        """args.features=None → no features, no scaler."""
        df = _make_df()
        result_df, cols, scaler = detect_and_load_features(df, None)
        assert cols == []
        assert scaler is None

    def test_path_b_computes_features(self, tmp_path):
        """args.features=[] → compute defaults on-the-fly."""
        df = _make_df(n_days=10)
        csv_path = str(tmp_path / "train_test.csv")
        df.to_csv(csv_path, index=False)

        result_df, cols, scaler = detect_and_load_features(
            df.copy(), [], data_path=csv_path,
        )
        assert len(cols) > 0
        assert scaler is not None
        assert scaler._fitted
        # Scaler should be saved next to CSV with tag-based name
        assert os.path.exists(tmp_path / "feature_scaler_test.json")

    def test_path_b_specific_features(self, tmp_path):
        """args.features=['sentiment_7d_ma'] → compute only that one."""
        df = _make_df(n_days=10)
        csv_path = str(tmp_path / "train.csv")
        df.to_csv(csv_path, index=False)

        result_df, cols, scaler = detect_and_load_features(
            df.copy(), ["sentiment_7d_ma"], data_path=csv_path,
        )
        assert cols == ["sentiment_7d_ma"]

    def test_path_a_loads_existing_scaler(self, tmp_path):
        """Pre-standardized CSV + scaler → Path A, no recomputation."""
        from training.data_prep.feature_engineering import engineer_features

        df = _make_df(n_days=10)
        df, extra_cols, meta = engineer_features(df)

        # Fit and save scaler
        scaler = FeatureScaler()
        scaler.fit(df, extra_cols)
        scaler.transform(df, extra_cols)
        csv_path = str(tmp_path / "train.csv")
        df.to_csv(csv_path, index=False)
        scaler.save(str(tmp_path / "feature_scaler.json"))

        # Reload CSV (simulating train script)
        loaded = pd.read_csv(csv_path)
        result_df, cols, loaded_scaler = detect_and_load_features(
            loaded, None, data_path=csv_path,
        )
        assert cols == extra_cols
        assert loaded_scaler is not None
        assert loaded_scaler.feature_set == extra_cols

    def test_features_no_scaler_raises(self, tmp_path):
        """CSV has feature columns but no scaler.json → FileNotFoundError."""
        df = _make_df()
        # Add a feature column manually
        df["sentiment_7d_ma"] = 0.5
        csv_path = str(tmp_path / "train.csv")
        df.to_csv(csv_path, index=False)

        with pytest.raises(FileNotFoundError, match="feature_scaler"):
            detect_and_load_features(pd.read_csv(csv_path), None, data_path=csv_path)

    def test_features_scaler_mismatch_raises(self, tmp_path):
        """CSV has features but scaler contract doesn't match → ValueError."""
        df = _make_df()
        df["sentiment_7d_ma"] = 0.5
        csv_path = str(tmp_path / "train.csv")
        df.to_csv(csv_path, index=False)

        # Create a scaler fitted on a different feature set
        df_for_scaler = df.copy()
        df_for_scaler["risk_7d_ma"] = 0.3
        scaler = FeatureScaler()
        scaler.fit(df_for_scaler, ["risk_7d_ma"])
        scaler.save(str(tmp_path / "feature_scaler.json"))

        with pytest.raises(ValueError, match="contract mismatch"):
            detect_and_load_features(pd.read_csv(csv_path), None, data_path=csv_path)


# ── save_training_artifacts ──────────────────────────────────


class TestSaveTrainingArtifacts:
    def test_saves_model_and_metadata(self, tmp_path, monkeypatch):
        """Full artifact save: model.pth + metadata.json + registry.json."""
        monkeypatch.setattr("training.train_utils.TRAINED_MODEL_DIR", str(tmp_path))

        import torch.nn as nn
        model = nn.Linear(4, 2)

        path = save_training_artifacts(
            model_id="ppo_test_10ep_s42_20260301T000000Z_abc123",
            algorithm="PPO",
            model_state_dict=model.state_dict(),
            score_source="test",
            extra_cols=[],
            stock_dim=5,
            state_dim=50,
            train_period="2020-01-01 ~ 2023-12-31",
            epochs=10,
            seed=42,
            hyperparams={"hid": 512},
        )

        model_dir = tmp_path / "ppo_test_10ep_s42_20260301T000000Z_abc123"
        assert (model_dir / "model.pth").exists()
        assert (model_dir / "metadata.json").exists()
        assert (tmp_path / "registry.json").exists()

        # Verify metadata content
        meta = json.loads((model_dir / "metadata.json").read_text())
        assert meta["algorithm"] == "PPO"
        assert meta["stock_dim"] == 5
        assert meta["training_date"].endswith("Z")
        assert meta["score_type"] == "sentiment"  # PPO default

    def test_cppo_score_type_both(self, tmp_path, monkeypatch):
        """CPPO should save score_type='both'."""
        monkeypatch.setattr("training.train_utils.TRAINED_MODEL_DIR", str(tmp_path))

        import torch.nn as nn
        model = nn.Linear(4, 2)

        save_training_artifacts(
            model_id="cppo_score_type_test",
            algorithm="CPPO",
            model_state_dict=model.state_dict(),
            score_source="test",
            extra_cols=[],
            stock_dim=2,
            state_dim=30,
            train_period="",
            epochs=1,
            seed=0,
            score_type="both",
            hyperparams={},
        )

        meta = json.loads((tmp_path / "cppo_score_type_test" / "metadata.json").read_text())
        assert meta["score_type"] == "both"
        assert meta["algorithm"] == "CPPO"

    def test_saves_scaler_when_provided(self, tmp_path, monkeypatch):
        """Scaler should be saved alongside model if provided."""
        monkeypatch.setattr("training.train_utils.TRAINED_MODEL_DIR", str(tmp_path))

        import torch.nn as nn
        model = nn.Linear(4, 2)

        df = _make_df()
        scaler = FeatureScaler()
        scaler.fit(df, ["llm_sentiment"])

        save_training_artifacts(
            model_id="ppo_scaler_test",
            algorithm="PPO",
            model_state_dict=model.state_dict(),
            score_source="test",
            extra_cols=["llm_sentiment"],
            stock_dim=2,
            state_dim=30,
            train_period="",
            epochs=1,
            seed=0,
            hyperparams={},
            scaler=scaler,
        )

        model_dir = tmp_path / "ppo_scaler_test"
        assert (model_dir / "feature_scaler.json").exists()
        loaded = FeatureScaler.load(str(model_dir / "feature_scaler.json"))
        assert loaded.feature_set == ["llm_sentiment"]
