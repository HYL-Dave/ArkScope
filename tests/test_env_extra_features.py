"""Tests for extra_feature_cols support in PPO and CPPO environments."""

import numpy as np
import pandas as pd
import pytest

from training.config import INDICATORS


def _make_env_df(n_tickers=2, n_days=5, extra_cols=None):
    """Build a minimal DataFrame suitable for env construction.

    Returns df with integer index (one row per ticker per day),
    sorted by (date, tic) with integer-based index reset.
    """
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
                "turbulence": 0.0,
            }
            for ind in INDICATORS:
                row[ind] = 0.5
            for col in (extra_cols or []):
                row[col] = 1.5
            rows.append(row)

    df = pd.DataFrame(rows)
    # The env expects integer-based index where each unique index = one day
    # For multi-stock: each day has n_tickers rows at the same index
    day_indices = []
    for day_idx in range(n_days):
        day_indices.extend([day_idx] * n_tickers)
    df.index = day_indices
    return df


def _make_ppo_env(n_tickers=2, n_days=5, extra_cols=None):
    """Create a PPO env with optional extra features."""
    from training.envs.stocktrading_llm import StockTradingEnv

    extra = extra_cols or []
    df = _make_env_df(n_tickers, n_days, extra)
    N = n_tickers
    K = len(INDICATORS)
    F = len(extra)
    state_space = 1 + 2 * N + (1 + K + F) * N  # PPO formula

    env = StockTradingEnv(
        df=df,
        stock_dim=N,
        hmax=100,
        initial_amount=1_000_000,
        num_stock_shares=[0] * N,
        buy_cost_pct=[0.001] * N,
        sell_cost_pct=[0.001] * N,
        reward_scaling=1e-4,
        state_space=state_space,
        action_space=N,
        tech_indicator_list=INDICATORS,
        extra_feature_cols=extra,
    )
    return env


def _make_cppo_env(n_tickers=2, n_days=5, extra_cols=None):
    """Create a CPPO env with optional extra features."""
    from training.envs.stocktrading_llm_risk import StockTradingEnv

    extra = extra_cols or []
    df = _make_env_df(n_tickers, n_days, extra)
    N = n_tickers
    K = len(INDICATORS)
    F = len(extra)
    state_space = 1 + 2 * N + (2 + K + F) * N  # CPPO formula: +risk(N)

    env = StockTradingEnv(
        df=df,
        stock_dim=N,
        hmax=100,
        initial_amount=1_000_000,
        num_stock_shares=[0] * N,
        buy_cost_pct=[0.001] * N,
        sell_cost_pct=[0.001] * N,
        reward_scaling=1e-4,
        state_space=state_space,
        action_space=N,
        tech_indicator_list=INDICATORS,
        extra_feature_cols=extra,
    )
    return env


# ── PPO Environment Tests ────────────────────────────────────


class TestPPOEnvExtraFeatures:
    def test_no_extra_features_backward_compat(self):
        """Without extra features, state vector should be unchanged."""
        env = _make_ppo_env(extra_cols=None)
        N = 2
        K = len(INDICATORS)
        expected_len = 1 + 2 * N + (1 + K) * N
        assert len(env.state) == expected_len

    def test_with_extra_features(self):
        """Extra features should increase state vector size."""
        extra = ["sentiment_7d_ma", "risk_7d_ma"]
        env = _make_ppo_env(extra_cols=extra)
        N = 2
        K = len(INDICATORS)
        F = 2
        expected_len = 1 + 2 * N + (1 + K + F) * N
        assert len(env.state) == expected_len

    def test_extra_features_position(self):
        """Extra features should be between indicators and sentiment."""
        extra = ["feat_a"]
        env = _make_ppo_env(n_tickers=2, extra_cols=extra)
        N = 2
        K = len(INDICATORS)
        # Layout: [cash(1)] + [close(N)] + [shares(N)] + [indicators(K*N)] + [extra(F*N)] + [sentiment(N)]
        # Extra features start at: 1 + 2*N + K*N
        extra_start = 1 + 2 * N + K * N
        extra_end = extra_start + N
        # Each extra feature value is 1.5 (set in _make_env_df)
        for i in range(extra_start, extra_end):
            assert env.state[i] == pytest.approx(1.5), f"state[{i}] = {env.state[i]}"

    def test_step_preserves_state_size(self):
        """State size should remain consistent after stepping."""
        extra = ["sentiment_7d_ma"]
        env = _make_ppo_env(n_days=5, extra_cols=extra)
        initial_len = len(env.state)
        actions = np.zeros(env.stock_dim)
        for _ in range(3):
            state, _, done, _, _ = env.step(actions)
            if done:
                break
            assert len(state) == initial_len

    def test_reset_preserves_state_size(self):
        """State size should be consistent after reset."""
        extra = ["sentiment_7d_ma", "risk_7d_ma"]
        env = _make_ppo_env(extra_cols=extra)
        initial_len = len(env.state)
        state, _ = env.reset()
        assert len(state) == initial_len

    def test_state_mismatch_raises(self):
        """Wrong state_space should trigger ValueError."""
        from training.envs.stocktrading_llm import StockTradingEnv

        extra = ["feat_a"]
        df = _make_env_df(2, 5, extra)
        with pytest.raises(ValueError, match="State vector length mismatch"):
            StockTradingEnv(
                df=df,
                stock_dim=2,
                hmax=100,
                initial_amount=1_000_000,
                num_stock_shares=[0, 0],
                buy_cost_pct=[0.001, 0.001],
                sell_cost_pct=[0.001, 0.001],
                reward_scaling=1e-4,
                state_space=999,  # wrong!
                action_space=2,
                tech_indicator_list=INDICATORS,
                extra_feature_cols=extra,
            )


# ── CPPO Environment Tests ───────────────────────────────────


class TestCPPOEnvExtraFeatures:
    def test_no_extra_features_backward_compat(self):
        """Without extra features, state vector should be unchanged."""
        env = _make_cppo_env(extra_cols=None)
        N = 2
        K = len(INDICATORS)
        expected_len = 1 + 2 * N + (2 + K) * N
        assert len(env.state) == expected_len

    def test_with_extra_features(self):
        """Extra features should increase state vector size."""
        extra = ["sentiment_7d_ma", "risk_7d_ma"]
        env = _make_cppo_env(extra_cols=extra)
        N = 2
        K = len(INDICATORS)
        F = 2
        expected_len = 1 + 2 * N + (2 + K + F) * N
        assert len(env.state) == expected_len

    def test_risk_at_tail_no_extra(self):
        """CPPO invariant: risk scores must be last N elements (no extra features)."""
        env = _make_cppo_env(n_tickers=2, extra_cols=None)
        N = 2
        # Risk values are 2 for all tickers (set in _make_env_df)
        risk_tail = env.state[-N:]
        assert all(r == pytest.approx(2.0) for r in risk_tail)

    def test_risk_at_tail_with_extra(self):
        """CPPO invariant: risk scores must be last N elements (with extra features)."""
        extra = ["sentiment_7d_ma", "risk_7d_ma", "sentiment_volatility"]
        env = _make_cppo_env(n_tickers=2, extra_cols=extra)
        N = 2
        risk_tail = env.state[-N:]
        assert all(r == pytest.approx(2.0) for r in risk_tail)

    def test_risk_tail_invariant_after_step(self):
        """CPPO risk tail invariant should hold after stepping."""
        extra = ["sentiment_7d_ma"]
        env = _make_cppo_env(n_tickers=2, n_days=5, extra_cols=extra)
        N = 2
        actions = np.zeros(N)
        for _ in range(3):
            state, _, done, _, _ = env.step(actions)
            if done:
                break
            risk_tail = state[-N:]
            assert all(r == pytest.approx(2.0) for r in risk_tail)

    def test_extra_features_between_indicators_and_sentiment(self):
        """Extra features should be between indicators and sentiment in CPPO state."""
        extra = ["feat_a"]
        env = _make_cppo_env(n_tickers=2, extra_cols=extra)
        N = 2
        K = len(INDICATORS)
        # CPPO layout: [cash(1)] + [close(N)] + [shares(N)] + [indicators(K*N)]
        #              + [extra(F*N)] + [sentiment(N)] + [risk(N)]
        extra_start = 1 + 2 * N + K * N
        extra_end = extra_start + N
        for i in range(extra_start, extra_end):
            assert env.state[i] == pytest.approx(1.5), f"state[{i}] = {env.state[i]}"
        # Sentiment at: extra_end to extra_end + N
        sent_start = extra_end
        for i in range(sent_start, sent_start + N):
            assert env.state[i] == pytest.approx(3.0), f"state[{i}] = {env.state[i]}"

    def test_single_stock_risk_tail(self):
        """CPPO risk tail invariant for single stock."""
        extra = ["sentiment_7d_ma"]
        env = _make_cppo_env(n_tickers=1, extra_cols=extra)
        assert env.state[-1] == pytest.approx(2.0)

    def test_single_stock_no_extra(self):
        """Single stock CPPO without extra features."""
        env = _make_cppo_env(n_tickers=1, extra_cols=None)
        assert env.state[-1] == pytest.approx(2.0)


# ── Empty extra_feature_cols edge cases ──────────────────────


class TestEmptyExtraFeatures:
    def test_ppo_empty_list_same_as_none(self):
        """extra_feature_cols=[] should behave like None."""
        env_none = _make_ppo_env(extra_cols=None)
        env_empty = _make_ppo_env(extra_cols=[])
        assert len(env_none.state) == len(env_empty.state)

    def test_cppo_empty_list_same_as_none(self):
        """extra_feature_cols=[] should behave like None for CPPO."""
        env_none = _make_cppo_env(extra_cols=None)
        env_empty = _make_cppo_env(extra_cols=[])
        assert len(env_none.state) == len(env_empty.state)
