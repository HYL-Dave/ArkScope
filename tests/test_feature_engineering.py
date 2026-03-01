"""Tests for feature engineering module and FeatureScaler."""

import json
import math

import numpy as np
import pandas as pd
import pytest

from training.data_prep.feature_engineering import (
    AVAILABLE_FEATURES,
    DEFAULT_FEATURES,
    FeatureScaler,
    _IMPUTATION,
    engineer_features,
)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def sample_df():
    """Multi-ticker panel: 2 tickers × 10 days."""
    dates = pd.date_range("2024-01-01", periods=10, freq="B")
    rows = []
    for d in dates:
        for tic in ["AAPL", "NVDA"]:
            rows.append({
                "date": d.strftime("%Y-%m-%d"),
                "tic": tic,
                "close": 100.0 + np.random.randn(),
                "llm_sentiment": np.random.randint(1, 6),
            })
    df = pd.DataFrame(rows)
    return df


@pytest.fixture
def sample_df_with_risk(sample_df):
    """Same as sample_df but with llm_risk column."""
    sample_df["llm_risk"] = np.random.randint(1, 6, size=len(sample_df))
    return sample_df


@pytest.fixture
def deterministic_df():
    """Small deterministic df for exact value checks."""
    return pd.DataFrame({
        "date": ["2024-01-01"] * 2 + ["2024-01-02"] * 2 + ["2024-01-03"] * 2,
        "tic": ["A", "B"] * 3,
        "llm_sentiment": [3, 4, 5, 2, 1, 4],
        "llm_risk": [2, 3, 4, 1, 5, 2],
    })


# ── engineer_features basic tests ────────────────────────────


class TestEngineerFeatures:
    def test_default_features(self, sample_df):
        df, extra_cols, meta = engineer_features(sample_df)
        # risk_7d_ma skipped (no llm_risk column)
        expected = ["sentiment_7d_ma", "sentiment_momentum", "sentiment_volatility"]
        assert extra_cols == expected
        for col in expected:
            assert col in df.columns

    def test_all_defaults_with_risk(self, sample_df_with_risk):
        df, extra_cols, meta = engineer_features(sample_df_with_risk)
        assert "risk_7d_ma" in extra_cols
        assert len(extra_cols) == 4  # all 4 defaults

    def test_specific_features(self, sample_df):
        df, extra_cols, meta = engineer_features(
            sample_df, features=["sentiment_7d_ma"]
        )
        assert extra_cols == ["sentiment_7d_ma"]
        assert "sentiment_momentum" not in df.columns

    def test_unknown_feature_raises(self, sample_df):
        with pytest.raises(ValueError, match="Unknown features"):
            engineer_features(sample_df, features=["nonexistent_feature"])

    def test_missing_sentiment_col_raises(self):
        df = pd.DataFrame({"date": ["2024-01-01"], "tic": ["A"], "close": [100]})
        with pytest.raises(ValueError, match="llm_sentiment"):
            engineer_features(df)

    def test_no_nan_in_output(self, sample_df_with_risk):
        df, extra_cols, _ = engineer_features(sample_df_with_risk)
        for col in extra_cols:
            assert df[col].isna().sum() == 0, f"NaN found in {col}"

    def test_output_sorted_by_date_tic(self, sample_df):
        df, _, _ = engineer_features(sample_df)
        dates = df["date"].tolist()
        assert dates == sorted(dates)

    def test_metadata_records_shift_and_imputation(self, sample_df):
        _, extra_cols, meta = engineer_features(sample_df, shift=1)
        assert meta["shift"] == 1
        assert "imputation" in meta
        for col in extra_cols:
            assert col in meta["imputation"]


class TestSignalLag:
    """Verify shift(1) correctly delays features by 1 day."""

    def test_shift1_first_day_is_fillna(self, deterministic_df):
        """With shift=1, the first day's features should be fillna values."""
        df, extra_cols, _ = engineer_features(
            deterministic_df,
            features=["sentiment_7d_ma"],
            shift=1,
        )
        # First day for ticker A: shift(1) → NaN → fillna(3.0)
        first_a = df[(df["tic"] == "A") & (df["date"] == "2024-01-01")]
        assert first_a["sentiment_7d_ma"].values[0] == pytest.approx(3.0)

    def test_shift0_first_day_has_value(self, deterministic_df):
        """With shift=0, first day should have the actual computed value."""
        df, _, _ = engineer_features(
            deterministic_df,
            features=["sentiment_7d_ma"],
            shift=0,
        )
        first_a = df[(df["tic"] == "A") & (df["date"] == "2024-01-01")]
        # min_periods=1 → first value = itself = 3.0
        assert first_a["sentiment_7d_ma"].values[0] == pytest.approx(3.0)

    def test_shift1_second_day_uses_first_day(self, deterministic_df):
        """With shift=1, second day's MA should equal first day's value."""
        df, _, _ = engineer_features(
            deterministic_df,
            features=["sentiment_7d_ma"],
            shift=1,
        )
        # Ticker A: day1 sentiment=3, day2 sentiment=5
        # Without shift: day1 MA=3, day2 MA=mean(3,5)=4
        # With shift(1): day2 sees day1's MA = 3.0
        second_a = df[(df["tic"] == "A") & (df["date"] == "2024-01-02")]
        assert second_a["sentiment_7d_ma"].values[0] == pytest.approx(3.0)


class TestPerTickerRolling:
    """Verify rolling operations are per-ticker (no cross-ticker leakage)."""

    def test_rolling_no_cross_ticker_leakage(self):
        """Ticker A's rolling should not use Ticker B's values."""
        df = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02"],
            "tic": ["A", "B", "A", "B"],
            "llm_sentiment": [1, 5, 1, 5],
        })
        result, _, _ = engineer_features(df, features=["sentiment_7d_ma"], shift=0)
        # Ticker A: all 1s → MA = 1.0
        a_vals = result[result["tic"] == "A"]["sentiment_7d_ma"].tolist()
        assert all(v == pytest.approx(1.0) for v in a_vals)
        # Ticker B: all 5s → MA = 5.0
        b_vals = result[result["tic"] == "B"]["sentiment_7d_ma"].tolist()
        assert all(v == pytest.approx(5.0) for v in b_vals)


class TestSemanticFillna:
    """Verify fillna values match the imputation policy."""

    def test_fillna_values_match_imputation_dict(self, sample_df_with_risk):
        df, extra_cols, meta = engineer_features(
            sample_df_with_risk, shift=1
        )
        for col in extra_cols:
            expected_fill = _IMPUTATION[col]
            assert col in meta["imputation"]
            assert meta["imputation"][col] == expected_fill

    def test_sentiment_ma_fills_neutral(self):
        """Single row → shift(1) → fillna(3.0)."""
        df = pd.DataFrame({
            "date": ["2024-01-01"],
            "tic": ["A"],
            "llm_sentiment": [5],
        })
        result, _, _ = engineer_features(df, features=["sentiment_7d_ma"], shift=1)
        assert result["sentiment_7d_ma"].values[0] == pytest.approx(3.0)

    def test_momentum_fills_zero(self):
        """Single row → shift(1) → fillna(0)."""
        df = pd.DataFrame({
            "date": ["2024-01-01"],
            "tic": ["A"],
            "llm_sentiment": [5],
        })
        result, _, _ = engineer_features(df, features=["sentiment_momentum"], shift=1)
        assert result["sentiment_momentum"].values[0] == pytest.approx(0.0)

    def test_volatility_fills_zero(self):
        """Single row → shift(1) → fillna(0)."""
        df = pd.DataFrame({
            "date": ["2024-01-01"],
            "tic": ["A"],
            "llm_sentiment": [5],
        })
        result, _, _ = engineer_features(
            df, features=["sentiment_volatility"], shift=1
        )
        assert result["sentiment_volatility"].values[0] == pytest.approx(0.0)


class TestModelDisagreement:
    def test_single_sentiment_col_returns_zero(self, sample_df):
        """With only llm_sentiment, model_disagreement should be 0."""
        df, extra_cols, _ = engineer_features(
            sample_df, features=["model_disagreement"], shift=0
        )
        assert "model_disagreement" in extra_cols
        assert (df["model_disagreement"] == 0).all()

    def test_multiple_sentiment_cols(self):
        """With 2+ sentiment_* columns, should compute std across them."""
        df = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-01"],
            "tic": ["A", "B"],
            "llm_sentiment": [3, 4],
            "sentiment_gpt5": [5, 2],
            "sentiment_claude": [1, 4],
        })
        result, _, _ = engineer_features(
            df, features=["model_disagreement"], shift=0
        )
        # Ticker A: std([5, 1]) = 2.828..., Ticker B: std([2, 4]) = 1.414...
        a_val = result[result["tic"] == "A"]["model_disagreement"].values[0]
        b_val = result[result["tic"] == "B"]["model_disagreement"].values[0]
        assert a_val > 0
        assert b_val > 0

    def test_derived_cols_excluded_from_disagreement(self):
        """sentiment_7d_ma, etc. should not be counted as source models."""
        df = pd.DataFrame({
            "date": ["2024-01-01"],
            "tic": ["A"],
            "llm_sentiment": [3],
            "sentiment_7d_ma": [3.0],  # derived, should be excluded
        })
        result, _, _ = engineer_features(
            df, features=["model_disagreement"], shift=0
        )
        assert result["model_disagreement"].values[0] == pytest.approx(0.0)


class TestDependencyOrder:
    """Verify that sentiment_momentum auto-computes sentiment_7d_ma if needed."""

    def test_momentum_alone_works(self, sample_df):
        """Requesting momentum alone should still work (auto-computes MA)."""
        df, extra_cols, _ = engineer_features(
            sample_df, features=["sentiment_momentum"]
        )
        assert "sentiment_momentum" in extra_cols
        # MA should be computed internally but not in extra_cols
        assert "sentiment_7d_ma" not in extra_cols
        assert "sentiment_7d_ma" in df.columns  # still exists internally


# ── FeatureScaler tests ──────────────────────────────────────


class TestFeatureScaler:
    @pytest.fixture
    def fitted_scaler(self, sample_df_with_risk):
        df, extra_cols, meta = engineer_features(sample_df_with_risk, shift=0)
        scaler = FeatureScaler().fit(
            df, extra_cols,
            shift=1,
            imputation=meta["imputation"],
            fit_period="2024-01-01 ~ 2024-01-14",
        )
        return scaler, df, extra_cols

    def test_fit_records_stats(self, fitted_scaler):
        scaler, _, extra_cols = fitted_scaler
        assert scaler._fitted
        assert scaler.feature_set == extra_cols
        for col in extra_cols:
            assert col in scaler.mean_
            assert col in scaler.std_

    def test_transform_z_scores(self, fitted_scaler):
        scaler, df, extra_cols = fitted_scaler
        df_copy = df.copy()
        scaler.transform(df_copy, extra_cols)
        for col in extra_cols:
            # Z-scored column should have mean ≈ 0 (within float precision)
            assert abs(df_copy[col].mean()) < 0.5  # loose check, small sample

    def test_transform_before_fit_raises(self):
        scaler = FeatureScaler()
        df = pd.DataFrame({"a": [1, 2, 3]})
        with pytest.raises(RuntimeError, match="before fit"):
            scaler.transform(df, ["a"])

    def test_zero_std_uses_one(self):
        """If std is 0 (constant column), use 1.0 to avoid division by zero."""
        df = pd.DataFrame({"const": [3.0, 3.0, 3.0]})
        scaler = FeatureScaler().fit(df, ["const"])
        assert scaler.std_["const"] == 1.0

    def test_save_load_roundtrip(self, fitted_scaler, tmp_path):
        scaler, df, extra_cols = fitted_scaler
        path = str(tmp_path / "scaler.json")
        scaler.save(path)
        loaded = FeatureScaler.load(path)
        assert loaded.feature_set == scaler.feature_set
        assert loaded.shift == scaler.shift
        assert loaded.fit_period == scaler.fit_period
        assert loaded._fitted
        for col in extra_cols:
            assert loaded.mean_[col] == pytest.approx(scaler.mean_[col])
            assert loaded.std_[col] == pytest.approx(scaler.std_[col])

    def test_save_includes_schema_version(self, fitted_scaler, tmp_path):
        scaler, _, _ = fitted_scaler
        path = str(tmp_path / "scaler.json")
        scaler.save(path)
        with open(path) as f:
            data = json.load(f)
        assert data["schema_version"] == 1

    def test_transform_consistency_after_load(self, fitted_scaler, tmp_path):
        """Transform results should be identical before and after save/load."""
        scaler, df, extra_cols = fitted_scaler
        df1 = df.copy()
        scaler.transform(df1, extra_cols)

        path = str(tmp_path / "scaler.json")
        scaler.save(path)
        loaded = FeatureScaler.load(path)
        df2 = df.copy()
        loaded.transform(df2, extra_cols)

        for col in extra_cols:
            np.testing.assert_array_almost_equal(
                df1[col].values, df2[col].values, decimal=10
            )


class TestFeatureScalerVersionCheck:
    def test_future_version_raises(self, tmp_path):
        """load() should fail-fast on unknown schema version."""
        path = str(tmp_path / "scaler.json")
        with open(path, "w") as f:
            json.dump({
                "schema_version": 99,
                "mean": {"a": 0.0},
                "std": {"a": 1.0},
            }, f)
        with pytest.raises(ValueError, match="schema version 99"):
            FeatureScaler.load(path)

    def test_missing_version_treated_as_v0(self, tmp_path):
        """No schema_version key → version 0, should load fine (≤ v1)."""
        path = str(tmp_path / "scaler.json")
        with open(path, "w") as f:
            json.dump({
                "mean": {"a": 0.0},
                "std": {"a": 1.0},
            }, f)
        scaler = FeatureScaler.load(path)
        assert scaler._fitted
        assert scaler.feature_set == ["a"]


class TestFeatureScalerContract:
    def test_validate_matching_contract(self, sample_df_with_risk):
        df, extra_cols, meta = engineer_features(sample_df_with_risk, shift=0)
        scaler = FeatureScaler().fit(df, extra_cols)
        scaler.validate_contract(extra_cols)  # should not raise

    def test_validate_missing_column(self):
        scaler = FeatureScaler()
        scaler.feature_set = ["a", "b", "c"]
        scaler._fitted = True
        with pytest.raises(ValueError, match="Missing.*'c'"):
            scaler.validate_contract(["a", "b"])

    def test_validate_extra_column(self):
        scaler = FeatureScaler()
        scaler.feature_set = ["a", "b"]
        scaler._fitted = True
        with pytest.raises(ValueError, match="Unexpected.*'c'"):
            scaler.validate_contract(["a", "b", "c"])

    def test_validate_wrong_order(self):
        scaler = FeatureScaler()
        scaler.feature_set = ["a", "b", "c"]
        scaler._fitted = True
        with pytest.raises(ValueError, match="order mismatch at position 0"):
            scaler.validate_contract(["b", "a", "c"])

    def test_validate_same_set_different_order(self):
        scaler = FeatureScaler()
        scaler.feature_set = ["sentiment_7d_ma", "risk_7d_ma"]
        scaler._fitted = True
        with pytest.raises(ValueError, match="order mismatch"):
            scaler.validate_contract(["risk_7d_ma", "sentiment_7d_ma"])


# ── Integration: engineer → scaler → transform ───────────────


class TestIntegration:
    def test_full_pipeline(self, sample_df_with_risk, tmp_path):
        """End-to-end: engineer → fit scaler → save → load → validate → transform."""
        # 1. Engineer features
        df, extra_cols, meta = engineer_features(sample_df_with_risk, shift=1)
        assert len(extra_cols) == 4

        # 2. Fit scaler on "train" subset (first 5 days per ticker)
        dates = sorted(df["date"].unique())
        train_dates = dates[:5]
        trade_dates = dates[5:]
        train = df[df["date"].isin(train_dates)].copy()
        trade = df[df["date"].isin(trade_dates)].copy()

        scaler = FeatureScaler().fit(
            train, extra_cols,
            shift=meta["shift"],
            imputation=meta["imputation"],
            fit_period=f"{train_dates[0]} ~ {train_dates[-1]}",
        )

        # 3. Transform both
        scaler.transform(train, extra_cols)
        scaler.transform(trade, extra_cols)

        # 4. Save / load / validate / re-transform
        path = str(tmp_path / "scaler.json")
        scaler.save(path)
        loaded = FeatureScaler.load(path)
        loaded.validate_contract(extra_cols)

        # Re-engineer on fresh df for verification
        df2, extra_cols2, _ = engineer_features(sample_df_with_risk, shift=1)
        trade2 = df2[df2["date"].isin(trade_dates)].copy()
        loaded.transform(trade2, extra_cols2)

        # Values should match
        for col in extra_cols:
            np.testing.assert_array_almost_equal(
                trade[col].values, trade2[col].values, decimal=10
            )

    def test_no_features_returns_unchanged(self, sample_df):
        """Requesting empty features list should return df unchanged."""
        df, extra_cols, _ = engineer_features(sample_df, features=[])
        assert extra_cols == []
        assert "sentiment_7d_ma" not in df.columns
