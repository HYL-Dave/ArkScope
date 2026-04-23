"""State vector builder for RL inference.

Pure-function reconstruction of the exact observation vector that
`training.envs.stocktrading_llm.StockTradingEnv._initiate_state()`
produces at reset (initial=True, multi-stock).

Design intent:
- Live inference MUST NOT depend on the training CSV artifact.
- Input is any DataFrame (from CSV / DB aggregation / IBKR live) that
  contains the columns declared in the model's schema.
- Ticker universe and feature schema come from the model's metadata,
  not from the input DataFrame.

State layout (matches env._initiate_state, multi-stock, initial=True):

    [initial_amount]                                     # 1
    + close_per_ticker                                   # stock_dim
    + num_stock_shares                                   # stock_dim
    + [indicator_i_per_ticker for i in tech_indicator_list]  # K*stock_dim
    + [extra_j_per_ticker for j in extra_feature_cols]   # F*stock_dim
    + llm_sentiment_per_ticker                           # stock_dim

    state_dim = 1 + 2*stock_dim + (1 + K + F)*stock_dim
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StateSchema:
    """Declares how a model's observation vector is composed.

    Must come from model metadata, not inferred from DataFrame columns.
    """

    ticker_order: Sequence[str]
    tech_indicator_list: Sequence[str]
    extra_feature_cols: Sequence[str] = field(default_factory=tuple)
    llm_sentiment_col: str = "llm_sentiment"
    initial_amount: float = 1_000_000.0

    @property
    def stock_dim(self) -> int:
        return len(self.ticker_order)

    @property
    def state_dim(self) -> int:
        k = len(self.tech_indicator_list)
        f = len(self.extra_feature_cols)
        return 1 + 2 * self.stock_dim + (1 + k + f) * self.stock_dim

    def required_columns(self) -> List[str]:
        return (
            ["tic", "close"]
            + list(self.tech_indicator_list)
            + list(self.extra_feature_cols)
            + [self.llm_sentiment_col]
        )


def build_observation(
    day_frame: pd.DataFrame,
    schema: StateSchema,
    shares: Optional[Iterable[float]] = None,
    initial_amount: Optional[float] = None,
    cash: Optional[float] = None,
) -> np.ndarray:
    """Build a 1-D observation vector for a single day.

    Args:
        day_frame: DataFrame containing one row per ticker for a single day.
            Must include all columns declared in schema.required_columns().
            Row order does not matter; rows will be reindexed by schema.ticker_order.
        schema: Model state schema (ticker order, feature lists, sentiment col, etc).
        shares: Per-ticker share holdings (length = stock_dim). Defaults to zeros.
        initial_amount: Override schema.initial_amount. If None, uses schema's.
            Used only when cash is None.
        cash: Current cash balance to put at state[0]. If provided, overrides
            initial_amount (for mid-episode reconstruction where cash != initial).

    Returns:
        1-D np.ndarray of length schema.state_dim. dtype=float64.

    Raises:
        KeyError: if day_frame is missing any required columns.
        ValueError: if day_frame does not contain exactly schema.stock_dim rows
            matching schema.ticker_order, or if shares has wrong length.
    """
    required = schema.required_columns()
    missing = [c for c in required if c not in day_frame.columns]
    if missing:
        raise KeyError(
            f"day_frame is missing columns: {missing}. "
            f"Required: {required}"
        )

    # Reindex by ticker_order so positional concatenation is deterministic
    # and the DataFrame's internal row order cannot affect the result.
    frame = day_frame.set_index("tic").reindex(list(schema.ticker_order))
    if frame["close"].isna().any():
        missing_tickers = frame.index[frame["close"].isna()].tolist()
        raise ValueError(
            f"day_frame missing rows for tickers: {missing_tickers[:10]}"
            f"{'...' if len(missing_tickers) > 10 else ''}"
        )

    if shares is None:
        shares_arr = np.zeros(schema.stock_dim, dtype=float)
    else:
        shares_arr = np.asarray(list(shares), dtype=float)
        if shares_arr.shape != (schema.stock_dim,):
            raise ValueError(
                f"shares length {shares_arr.shape[0]} != stock_dim "
                f"{schema.stock_dim}"
            )

    if cash is not None:
        cash_val = float(cash)
    elif initial_amount is not None:
        cash_val = float(initial_amount)
    else:
        cash_val = float(schema.initial_amount)

    pieces: List[np.ndarray] = [
        np.array([cash_val], dtype=float),
        frame["close"].to_numpy(dtype=float),
        shares_arr,
    ]
    for tech in schema.tech_indicator_list:
        pieces.append(frame[tech].to_numpy(dtype=float))
    for col in schema.extra_feature_cols:
        pieces.append(frame[col].to_numpy(dtype=float))
    pieces.append(frame[schema.llm_sentiment_col].to_numpy(dtype=float))

    state = np.concatenate(pieces)

    if state.shape[0] != schema.state_dim:
        raise ValueError(
            f"state_dim mismatch: built {state.shape[0]}, "
            f"expected {schema.state_dim}"
        )
    return state


def schema_from_metadata(meta: dict) -> StateSchema:
    """Construct a StateSchema from a ModelMetadata dict.

    Required keys in meta:
        ticker_order: List[str]
        tech_indicator_list: List[str]
    Optional keys (with defaults):
        extra_feature_cols: List[str] = []
        llm_sentiment_col: str = "llm_sentiment"
        initial_amount: float = 1_000_000

    Tolerates absent keys by falling back to sensible defaults — but
    callers doing live inference should treat absent ticker_order or
    tech_indicator_list as a hard error, because state composition
    cannot be inferred.
    """
    required_keys = ("ticker_order", "tech_indicator_list")
    missing = [k for k in required_keys if k not in meta]
    if missing:
        raise KeyError(
            f"metadata is missing required schema keys: {missing}. "
            f"Run scripts/patch_model_metadata.py on this model first."
        )
    return StateSchema(
        ticker_order=tuple(meta["ticker_order"]),
        tech_indicator_list=tuple(meta["tech_indicator_list"]),
        extra_feature_cols=tuple(meta.get("extra_feature_cols", [])),
        llm_sentiment_col=meta.get("llm_sentiment_col", "llm_sentiment"),
        initial_amount=float(meta.get("initial_amount", 1_000_000)),
    )