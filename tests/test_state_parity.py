"""State parity test — C gate for RL inference.

Proves that `training.data_prep.state_builder.build_observation()`
produces the exact same observation vector as
`training.envs.stocktrading_llm.StockTradingEnv._initiate_state()`.

This is a prerequisite for live inference: if the two diverge by even
one element, inference signals will be silently wrong.

The test uses a small subset of the real training CSV (first 2 days,
all tickers) as the parity oracle. The CSV is a training artifact;
live inference will build the DataFrame from IBKR / DB / FeatureEngineer
but feed it through the same builder.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Absolute path to the training CSV (the ext model's training data)
_REPO_ROOT = Path(__file__).resolve().parents[1]
_CSV_PATH = _REPO_ROOT / "training" / "data_prep" / "output" / "train_polygon_multi_both_ext.csv"


def _load_first_days(csv_path: Path, n_days: int = 2) -> pd.DataFrame:
    """Load the first n_days of the training CSV, preserving env's day-indexed layout."""
    if not csv_path.exists():
        pytest.skip(f"Training CSV not found at {csv_path}")

    df = pd.read_csv(csv_path, index_col=0)
    # Normalize date column if it came in as datetime
    df["date"] = df["date"].astype(str)
    unique_dates = sorted(df["date"].unique())[:n_days]
    df = df[df["date"].isin(unique_dates)].copy()
    df = df.sort_values(["date", "tic"]).reset_index(drop=True)
    # Env expects integer index where each unique value = one day
    df.index = df["date"].factorize()[0]
    return df


def _make_env(df: pd.DataFrame):
    """Reconstruct the env exactly as train_ppo_sb3.py:make_env_fn does."""
    from training.config import INDICATORS
    from training.envs.stocktrading_llm import StockTradingEnv

    stock_dim = df["tic"].nunique()
    k = len(INDICATORS)
    state_space = 1 + 2 * stock_dim + (1 + k + 0) * stock_dim  # F=0 (ext model)

    env = StockTradingEnv(
        df=df,
        stock_dim=stock_dim,
        hmax=100,
        initial_amount=1_000_000,
        num_stock_shares=[0] * stock_dim,
        buy_cost_pct=[0.001] * stock_dim,
        sell_cost_pct=[0.001] * stock_dim,
        reward_scaling=1e-4,
        state_space=state_space,
        action_space=stock_dim,
        tech_indicator_list=INDICATORS,
        extra_feature_cols=[],
    )
    return env, stock_dim, state_space


def _schema_from_env_setup(ticker_order):
    """Build a StateSchema that matches the env used above."""
    from training.config import INDICATORS
    from training.data_prep.state_builder import StateSchema

    return StateSchema(
        ticker_order=tuple(ticker_order),
        tech_indicator_list=tuple(INDICATORS),
        extra_feature_cols=(),
        llm_sentiment_col="llm_sentiment",
        initial_amount=1_000_000,
    )


def test_schema_state_dim_matches_env_state_space():
    """Sanity: schema.state_dim formula must agree with env's state_space."""
    df = _load_first_days(_CSV_PATH, n_days=2)
    env, stock_dim, env_state_space = _make_env(df)

    ticker_order = sorted(df["tic"].unique())
    schema = _schema_from_env_setup(ticker_order)

    assert schema.stock_dim == stock_dim
    assert schema.state_dim == env_state_space


def test_day0_reset_state_matches_builder():
    """Day 0 reset observation must equal builder output element-wise."""
    from training.data_prep.state_builder import build_observation

    df = _load_first_days(_CSV_PATH, n_days=2)
    env, _, _ = _make_env(df)

    # env's observation at day 0 (from reset)
    gt_state, _ = env.reset()
    gt_arr = np.asarray(gt_state, dtype=float)

    # Builder's observation at day 0
    day_frame = df.loc[0, :].reset_index(drop=True)
    ticker_order = sorted(day_frame["tic"].unique())
    schema = _schema_from_env_setup(ticker_order)

    my_state = build_observation(
        day_frame=day_frame,
        schema=schema,
        shares=None,  # defaults to zeros, matches env's num_stock_shares=[0]*N
        cash=None,    # uses schema.initial_amount = 1M, matches env's initial_amount
    )

    assert my_state.shape == gt_arr.shape
    np.testing.assert_allclose(
        my_state, gt_arr, rtol=0, atol=0,
        err_msg="Builder and env disagree on day 0 state"
    )


def test_day1_zero_action_state_matches_builder():
    """After env.step(zero_action), state should match builder with shares=0, cash=1M.

    Zero action means no buy/sell (action * hmax = 0 shares), so state[0]
    (cash) is unchanged and state[stock_dim+1 : 2*stock_dim+1] (shares) is
    still all zeros. Only close / indicators / sentiment change, driven by
    the next row in the df.
    """
    from training.data_prep.state_builder import build_observation

    df = _load_first_days(_CSV_PATH, n_days=2)
    env, stock_dim, _ = _make_env(df)

    env.reset()
    zero_action = np.zeros(stock_dim, dtype=np.float32)
    gt_state, _reward, _terminal, _trunc, _info = env.step(zero_action)
    gt_arr = np.asarray(gt_state, dtype=float)

    day_frame = df.loc[1, :].reset_index(drop=True)
    ticker_order = sorted(day_frame["tic"].unique())
    schema = _schema_from_env_setup(ticker_order)

    # Extract cash and shares from env's state to feed builder
    env_cash = gt_arr[0]
    env_shares = gt_arr[1 + schema.stock_dim : 1 + 2 * schema.stock_dim]

    my_state = build_observation(
        day_frame=day_frame,
        schema=schema,
        shares=env_shares,
        cash=env_cash,
    )

    np.testing.assert_allclose(
        my_state, gt_arr, rtol=0, atol=0,
        err_msg="Builder and env disagree on day 1 state (zero action)"
    )


def test_ticker_order_is_alphabetical():
    """Regression guard: the ticker order used by builder must be alphabetical.

    `self.df.loc[day, :]` returns rows in the DataFrame's internal order,
    which is set by `sort_values(['date', 'tic'])` in prepare_training_data.py.
    If this convention ever changes, the builder's `sorted()` assumption
    would silently diverge.
    """
    df = _load_first_days(_CSV_PATH, n_days=1)
    day_tics = df.loc[0, "tic"].tolist()
    assert day_tics == sorted(day_tics), (
        "Training DataFrame is no longer tic-sorted within each day. "
        "Builder's alphabetical assumption is broken."
    )