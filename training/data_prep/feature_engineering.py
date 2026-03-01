"""
Feature engineering for RL training pipeline.

Derives sentiment/risk features from raw LLM scores:
  - Rolling averages, momentum, volatility
  - Multi-model disagreement (conditional)
  - Z-score standardization via FeatureScaler

Design contracts:
  - All rolling windows are backward-looking only (no future data)
  - shift(1) default: assumes scores available after market close
  - Rolling computed on full df (train+trade), split at caller
  - fillna is semantic per feature type (not blanket 0)
  - FeatureScaler records feature_set order as single source of truth
"""

from __future__ import annotations

import json
import logging
import re
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Available features ────────────────────────────────────────

AVAILABLE_FEATURES = [
    "sentiment_7d_ma",
    "sentiment_momentum",
    "sentiment_volatility",
    "risk_7d_ma",
    "model_disagreement",
]

DEFAULT_FEATURES = [
    "sentiment_7d_ma",
    "sentiment_momentum",
    "sentiment_volatility",
    "risk_7d_ma",
]

# Semantic fillna values per feature
_IMPUTATION = {
    "sentiment_7d_ma": 3.0,       # neutral sentiment
    "sentiment_momentum": 0.0,    # no change
    "sentiment_volatility": 0.0,  # no volatility
    "risk_7d_ma": 3.0,            # neutral risk
    "model_disagreement": 0.0,    # consensus
}


# ── Individual feature functions ──────────────────────────────


def _sentiment_7d_ma(group: pd.Series) -> pd.Series:
    """7-day rolling mean of llm_sentiment, per-ticker."""
    return group.rolling(7, min_periods=1).mean()


def _sentiment_momentum(df: pd.DataFrame) -> pd.Series:
    """Sentiment minus its 7-day MA (requires sentiment_7d_ma computed first)."""
    return df["llm_sentiment"] - df["sentiment_7d_ma"]


def _sentiment_volatility(group: pd.Series) -> pd.Series:
    """7-day rolling std of llm_sentiment, per-ticker."""
    return group.rolling(7, min_periods=1).std()


def _risk_7d_ma(group: pd.Series) -> pd.Series:
    """7-day rolling mean of llm_risk, per-ticker."""
    return group.rolling(7, min_periods=1).mean()


def _model_disagreement(df: pd.DataFrame) -> pd.Series:
    """Cross-model disagreement: std across multiple sentiment columns.

    Detects columns matching 'sentiment_*' (excluding 'sentiment_7d_ma',
    'sentiment_momentum', 'sentiment_volatility' which are derived features).
    If fewer than 2 source columns found, returns zeros.
    """
    derived = {"sentiment_7d_ma", "sentiment_momentum", "sentiment_volatility"}
    sent_cols = [
        c for c in df.columns
        if c.startswith("sentiment_") and c not in derived
    ]
    if len(sent_cols) < 2:
        return pd.Series(0.0, index=df.index)
    return df[sent_cols].std(axis=1)


# ── Main API ──────────────────────────────────────────────────


def engineer_features(
    df: pd.DataFrame,
    features: Optional[List[str]] = None,
    sentiment_col: str = "llm_sentiment",
    risk_col: str = "llm_risk",
    shift: int = 1,
) -> Tuple[pd.DataFrame, List[str], Dict]:
    """Compute derived features on a date×ticker panel DataFrame.

    All rolling windows are backward-looking (pandas default).
    shift(1) provides additional signal lag protection against look-ahead bias.

    This function should be called on the full DataFrame (train+trade)
    BEFORE splitting — so trade period can use train-period rolling history.

    Args:
        df: DataFrame with columns [date, tic, llm_sentiment, ...].
            Must be sorted by (date, tic) or will be sorted internally.
        features: List of feature names to compute. None = DEFAULT_FEATURES.
        sentiment_col: Column name for sentiment scores.
        risk_col: Column name for risk scores.
        shift: Signal lag. 1 = use previous day's value (conservative).

    Returns:
        (augmented_df, extra_col_names, metadata_dict)
        extra_col_names preserves insertion order (used as feature_set).
        metadata_dict records shift and imputation policy.
    """
    if features is None:
        features = list(DEFAULT_FEATURES)

    # Validate requested features
    unknown = set(features) - set(AVAILABLE_FEATURES)
    if unknown:
        raise ValueError(
            f"Unknown features: {sorted(unknown)}. "
            f"Available: {AVAILABLE_FEATURES}"
        )

    df = df.copy()
    has_risk = risk_col in df.columns
    has_sentiment = sentiment_col in df.columns

    if not has_sentiment:
        raise ValueError(f"DataFrame must have '{sentiment_col}' column")

    # Ensure sorted by (tic, date) for correct per-ticker rolling.
    # Preserve original index (env uses duplicate day-indices like 0,0,1,1,...).
    if "date" in df.columns:
        df = df.sort_values(["tic", "date"])

    extra_cols = []
    imputation = {}

    # Compute features in dependency order
    grouped_sentiment = df.groupby("tic")[sentiment_col]

    if "sentiment_7d_ma" in features:
        df["sentiment_7d_ma"] = grouped_sentiment.transform(_sentiment_7d_ma)
        extra_cols.append("sentiment_7d_ma")
        imputation["sentiment_7d_ma"] = _IMPUTATION["sentiment_7d_ma"]

    if "sentiment_momentum" in features:
        # Requires sentiment_7d_ma — compute it if not already done
        if "sentiment_7d_ma" not in df.columns:
            df["sentiment_7d_ma"] = grouped_sentiment.transform(_sentiment_7d_ma)
        df["sentiment_momentum"] = _sentiment_momentum(df)
        extra_cols.append("sentiment_momentum")
        imputation["sentiment_momentum"] = _IMPUTATION["sentiment_momentum"]

    if "sentiment_volatility" in features:
        df["sentiment_volatility"] = grouped_sentiment.transform(_sentiment_volatility)
        extra_cols.append("sentiment_volatility")
        imputation["sentiment_volatility"] = _IMPUTATION["sentiment_volatility"]

    if "risk_7d_ma" in features:
        if has_risk:
            grouped_risk = df.groupby("tic")[risk_col]
            df["risk_7d_ma"] = grouped_risk.transform(_risk_7d_ma)
            extra_cols.append("risk_7d_ma")
            imputation["risk_7d_ma"] = _IMPUTATION["risk_7d_ma"]
        else:
            logger.info(
                "Skipping risk_7d_ma: '%s' column not present in DataFrame",
                risk_col,
            )

    if "model_disagreement" in features:
        df["model_disagreement"] = _model_disagreement(df)
        extra_cols.append("model_disagreement")
        imputation["model_disagreement"] = _IMPUTATION["model_disagreement"]

    # Apply signal lag: shift per-ticker, then fillna with semantic defaults
    if shift > 0 and extra_cols:
        for col in extra_cols:
            df[col] = df.groupby("tic")[col].shift(shift)

    # Semantic fillna
    for col in extra_cols:
        df[col] = df[col].fillna(imputation[col])

    # Restore original sort order (date, tic), preserve index
    if "date" in df.columns:
        df = df.sort_values(["date", "tic"])

    metadata = {
        "shift": shift,
        "imputation": imputation,
        "features_computed": list(extra_cols),
    }

    return df, extra_cols, metadata


# ── FeatureScaler ─────────────────────────────────────────────


class FeatureScaler:
    """Z-score scaler: fit on train, transform on train/trade/backtest.

    Saves/loads with schema version and ordered feature_set for contract
    validation. The feature_set order is the single source of truth for
    state vector construction.
    """

    SCHEMA_VERSION = 1

    def __init__(self) -> None:
        self.mean_: Dict[str, float] = {}
        self.std_: Dict[str, float] = {}
        self.feature_set: List[str] = []
        self.shift: int = 1
        self.imputation_policy: Dict = {}
        self.fit_period: str = ""
        self._fitted = False

    def fit(
        self,
        df: pd.DataFrame,
        cols: List[str],
        shift: int = 1,
        imputation: Optional[Dict] = None,
        fit_period: str = "",
    ) -> "FeatureScaler":
        """Fit scaler on training data.

        Args:
            df: Training DataFrame (already has derived feature columns).
            cols: Ordered list of feature column names.
            shift: Signal lag used during feature engineering.
            imputation: fillna policy dict (feature_name -> fill_value).
            fit_period: Human-readable training period string.
        """
        self.feature_set = list(cols)
        self.shift = shift
        self.imputation_policy = imputation or {}
        self.fit_period = fit_period
        for col in cols:
            self.mean_[col] = float(df[col].mean())
            s = float(df[col].std())
            self.std_[col] = s if s > 1e-8 else 1.0
        self._fitted = True
        return self

    def transform(self, df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
        """Z-score transform columns in-place."""
        if not self._fitted:
            raise RuntimeError("FeatureScaler.transform() called before fit()")
        for col in cols:
            df[col] = (df[col] - self.mean_[col]) / self.std_[col]
        return df

    def validate_contract(self, extra_cols: List[str]) -> None:
        """Fail fast if feature set or order doesn't match.

        Provides diagnostic error messages: lists missing/extra columns
        and first order mismatch position.
        """
        expected = set(self.feature_set)
        actual = set(extra_cols)
        if expected != actual:
            missing = expected - actual
            extra = actual - expected
            raise ValueError(
                f"Feature contract mismatch. "
                f"Missing: {sorted(missing) or 'none'}. "
                f"Unexpected: {sorted(extra) or 'none'}. "
                f"Expected: {self.feature_set}, got: {list(extra_cols)}"
            )
        if list(extra_cols) != self.feature_set:
            for i, (e, a) in enumerate(zip(self.feature_set, extra_cols)):
                if e != a:
                    raise ValueError(
                        f"Feature order mismatch at position {i}: "
                        f"expected '{e}', got '{a}'. "
                        f"Full expected: {self.feature_set}"
                    )
            raise ValueError(
                f"Feature order mismatch: {self.feature_set} vs {list(extra_cols)}"
            )

    def save(self, path: str) -> None:
        """Save scaler to JSON with schema version."""
        with open(path, "w") as f:
            json.dump(
                {
                    "schema_version": self.SCHEMA_VERSION,
                    "feature_set": self.feature_set,
                    "shift": self.shift,
                    "imputation_policy": self.imputation_policy,
                    "fit_period": self.fit_period,
                    "mean": self.mean_,
                    "std": self.std_,
                },
                f,
                indent=2,
            )

    @classmethod
    def load(cls, path: str) -> "FeatureScaler":
        """Load scaler from JSON. Fail-fast on unknown schema version."""
        with open(path) as f:
            data = json.load(f)

        version = data.get("schema_version", 0)
        if version > cls.SCHEMA_VERSION:
            raise ValueError(
                f"FeatureScaler schema version {version} is newer than "
                f"supported version {cls.SCHEMA_VERSION}. "
                f"Upgrade your code or re-train with current version."
            )

        s = cls()
        s.mean_ = data["mean"]
        s.std_ = data["std"]
        s.feature_set = data.get("feature_set", list(data["mean"].keys()))
        s.shift = data.get("shift", 1)
        s.imputation_policy = data.get("imputation_policy", {})
        s.fit_period = data.get("fit_period", "")
        s._fitted = True
        return s
