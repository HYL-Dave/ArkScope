"""
Shared utilities for PPO and CPPO training scripts.

Provides:
- _file_hash(): Chunked MD5 hash for data files
- save_training_artifacts(): Save model, metadata, and scaler to unified directory
- detect_features_in_csv(): Detect pre-computed features in a CSV DataFrame
"""

from __future__ import annotations

import hashlib
import logging
import os
import warnings
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional

import torch

from training.config import TRAINED_MODEL_DIR

if TYPE_CHECKING:
    from training.data_prep.feature_engineering import FeatureScaler
    from training.model_registry import ModelMetadata

logger = logging.getLogger(__name__)


def file_hash(path: str, chunk_size: int = 65536) -> str:
    """Chunked MD5 hash, memory-safe for large CSV files.

    Returns first 6 hex chars of MD5 digest.
    """
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()[:6]


def generate_model_id(
    algorithm: str,
    data_tag: str,
    epochs: int,
    seed: int,
    data_path: Optional[str] = None,
) -> str:
    """Generate a collision-resistant model_id.

    Format: {algo}_{tag}_{epochs}ep_s{seed}_{YYYYMMDDTHHMMSSZ}_{hash6}
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    data_h = file_hash(data_path) if data_path else "hf"
    algo = algorithm.lower()
    return f"{algo}_{data_tag}_{epochs}ep_s{seed}_{ts}_{data_h}"


def save_training_artifacts(
    model_id: str,
    algorithm: str,
    model_state_dict: dict,
    score_source: str,
    extra_cols: List[str],
    stock_dim: int,
    state_dim: int,
    train_period: str,
    epochs: int,
    seed: int,
    hyperparams: Dict,
    score_type: str = "sentiment",
    data_path: Optional[str] = None,
    scaler: Optional["FeatureScaler"] = None,
) -> str:
    """Save model + metadata + scaler to unified model directory.

    All I/O is concentrated here so callers only need a rank-0 guard
    around a single function call.

    Returns:
        Absolute path to the saved model.pth
    """
    from training.model_registry import ModelMetadata, ModelRegistry

    model_dir = os.path.join(TRAINED_MODEL_DIR, model_id)
    os.makedirs(model_dir, exist_ok=True)

    # 1. Save model weights
    abs_model_path = os.path.join(model_dir, "model.pth")
    torch.save(model_state_dict, abs_model_path)

    # 2. Relative path for cross-machine portability
    rel_model_path = os.path.join(model_id, "model.pth")

    # 3. Data hash (chunked, memory-safe)
    data_h = file_hash(data_path) if data_path else ""

    # 4. Save metadata to registry
    training_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = ModelMetadata(
        model_id=model_id,
        algorithm=algorithm.upper(),
        score_source=score_source,
        score_type=score_type,
        feature_set=list(extra_cols),
        stock_dim=stock_dim,
        state_dim=state_dim,
        train_period=train_period,
        epochs=epochs,
        hyperparams=hyperparams,
        backtest_results={},
        training_date=training_date,
        model_path=rel_model_path,
        data_hash=data_h,
    )
    registry = ModelRegistry(models_dir=TRAINED_MODEL_DIR)
    registry.save_metadata(meta)

    # 5. Save scaler if present
    if scaler is not None:
        scaler.save(os.path.join(model_dir, "feature_scaler.json"))

    logger.info("Saved training artifacts to %s", model_dir)
    print(f"  Model saved: {abs_model_path}")
    print(f"  Registry updated: {model_id}")
    if scaler:
        print(f"  Scaler saved: {os.path.join(model_dir, 'feature_scaler.json')}")

    return abs_model_path


def _find_scaler_path(data_path: str) -> str | None:
    """Find the scaler JSON co-located with a CSV file.

    Search order:
      1. feature_scaler_{tag}.json  (tag derived from CSV filename)
      2. feature_scaler.json        (legacy fallback)
    Returns the first path that exists, or the tag-based path if neither exists.
    """
    import re

    csv_dir = os.path.dirname(os.path.abspath(data_path))
    csv_name = os.path.splitext(os.path.basename(data_path))[0]  # e.g. "train_claude_opus_both"
    # Strip leading "train_" or "trade_" prefix to get the tag
    tag = re.sub(r"^(train|trade)_", "", csv_name)
    tagged_path = os.path.join(csv_dir, f"feature_scaler_{tag}.json")
    legacy_path = os.path.join(csv_dir, "feature_scaler.json")

    if os.path.exists(tagged_path):
        return tagged_path
    if os.path.exists(legacy_path):
        return legacy_path
    # Neither exists — return tagged path (for error messages / future creation)
    return tagged_path


def detect_and_load_features(
    df,
    args_features,
    data_path: Optional[str] = None,
) -> tuple:
    """Detect pre-computed features or compute on-the-fly.

    Implements the Path A / Path B logic from the plan:
      - Path A: CSV already has standardized features + scaler.json
      - Path B: Compute features on-the-fly from raw CSV

    Args:
        df: The loaded DataFrame
        args_features: Value of args.features (None=disabled, []=defaults, list=specific)
        data_path: Path to the CSV file (for scaler co-location)

    Returns:
        (df, extra_cols, scaler) — scaler is None if no features
    """
    from training.data_prep.feature_engineering import (
        AVAILABLE_FEATURES,
        FeatureScaler,
        engineer_features,
    )

    # Check if CSV already contains feature columns
    candidate_feat_cols = [c for c in df.columns if c in AVAILABLE_FEATURES]
    scaler_path = _find_scaler_path(data_path) if data_path else None

    # Path A: CSV already has features + matching scaler
    if candidate_feat_cols and scaler_path and os.path.exists(scaler_path):
        scaler = FeatureScaler.load(scaler_path)
        try:
            scaler.validate_contract(candidate_feat_cols)
        except ValueError:
            raise ValueError(
                f"CSV contains feature columns {candidate_feat_cols} but "
                f"feature_scaler.json contract mismatch. Data may be corrupted."
            )
        # Three conditions met — confirmed Path A product
        if args_features is not None:
            warnings.warn("Features already present in CSV, skipping re-computation.")
        # Order from scaler.feature_set (single source of truth)
        extra_cols = list(scaler.feature_set)
        print(f"  Loaded existing scaler from {scaler_path}, features: {extra_cols}")
        # Don't re-fit or re-transform — CSV is already standardized
        return df, extra_cols, scaler

    # Features in CSV but no scaler → fail-fast
    if candidate_feat_cols and (not scaler_path or not os.path.exists(scaler_path)):
        raise FileNotFoundError(
            f"CSV contains feature columns {candidate_feat_cols} but no "
            f"feature_scaler.json found at {scaler_path}. "
            f"Cannot proceed without matching scaler."
        )

    # Path B: Compute features on-the-fly
    if args_features is not None:
        feat_list = args_features if args_features else None  # [] → None = defaults
        df, extra_cols, feat_meta = engineer_features(df, features=feat_list)

        # Fit scaler on the full training df
        # (caller is responsible for train/trade split if applicable)
        scaler = FeatureScaler()
        scaler.fit(
            df,
            extra_cols,
            shift=feat_meta.get("shift", 1),
            imputation=feat_meta.get("imputation", {}),
        )
        scaler.transform(df, extra_cols)

        # Save scaler alongside data if we have a data_path
        if data_path:
            out_scaler_path = _find_scaler_path(data_path)
            scaler.save(out_scaler_path)
            print(f"  Scaler fitted and saved: {out_scaler_path}")

        print(f"  Computed features: {extra_cols}")
        return df, extra_cols, scaler

    # No features requested
    return df, [], None
