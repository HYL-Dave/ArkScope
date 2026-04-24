"""Offline RL inference core (Phase B0).

Three small building blocks:
  - load_model(model_dir)      -> (sb3_model, metadata_dict)
  - predict_from_frame(...)    -> action np.ndarray of shape (stock_dim,)
  - decode_action(...)         -> structured dict (top buys/sells, distribution)

Deliberately narrow for B0:
  - no IBKR / live data concerns
  - no indicator computation here (caller supplies the DataFrame)
  - no T+1 outcome tracking
  - no DB writes

Live inference (B1) will produce a day_frame from IBKR + parquet,
then call predict_from_frame() here. Report generation (B2) wraps
decode_action() plus realised-return backfill.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np
import pandas as pd

from training.data_prep.state_builder import (
    StateSchema,
    build_observation,
    schema_from_metadata,
)


@dataclass
class ObsNormalizer:
    """Applies VecNormalize-equivalent per-element observation normalization.

    Reproduces SB3 ``VecNormalize._normalize_obs`` math manually so inference
    and replay tools can skip the VecEnv wrapper. Stats are loaded from
    ``model_dir/vecnormalize.pkl`` which is written during training when
    ``--vecnormalize-obs`` is enabled.
    """

    mean: np.ndarray
    var: np.ndarray
    clip_obs: float
    epsilon: float = 1e-8

    def normalize(self, obs: np.ndarray) -> np.ndarray:
        obs = np.asarray(obs, dtype=float)
        out = (obs - self.mean) / np.sqrt(self.var + self.epsilon)
        return np.clip(out, -self.clip_obs, self.clip_obs)


@dataclass
class InferenceArtifacts:
    """What load_model() returns — model + schema + raw metadata + optional normalizer."""

    model: Any  # stable_baselines3.PPO (avoid import cost unless used)
    schema: StateSchema
    metadata: dict
    model_dir: Path
    obs_normalizer: Optional[ObsNormalizer] = None


def load_model(model_dir: Path) -> InferenceArtifacts:
    """Load an SB3 PPO model and its schema from a training artifact directory.

    Expects:
        model_dir/
            model_sb3.zip     — SB3 archive (full env-compatible model)
            metadata.json     — ModelMetadata-compatible dict with schema fields

    Raises:
        FileNotFoundError: missing model_sb3.zip or metadata.json
        KeyError:          metadata lacks schema fields (run patch_model_metadata.py)
    """
    model_dir = Path(model_dir)
    zip_path = model_dir / "model_sb3.zip"
    meta_path = model_dir / "metadata.json"

    if not zip_path.exists():
        raise FileNotFoundError(f"Missing SB3 archive: {zip_path}")
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing metadata: {meta_path}")

    with open(meta_path) as f:
        metadata = json.load(f)

    schema = schema_from_metadata(metadata)

    # Import lazily so importing this module is cheap
    from gymnasium import spaces
    from stable_baselines3 import PPO

    # Override the four fields whose deserialization fails across numpy 2.x → 1.x
    # version skew (archive saved with numpy 2.x, runtime has 1.x — the internal
    # `numpy._core.numeric` layout does not resolve across that boundary).
    # We reconstruct gym spaces from the authoritative schema and null out
    # the training-time-only state (_last_obs / _last_episode_starts) since
    # inference does not need a rollout buffer.
    custom_objects = {
        "observation_space": spaces.Box(
            low=-np.inf, high=np.inf, shape=(schema.state_dim,)
        ),
        "action_space": spaces.Box(
            low=-1.0, high=1.0, shape=(schema.stock_dim,)
        ),
        "_last_obs": None,
        "_last_episode_starts": None,
        "learning_rate": 0.0,
        "lr_schedule": lambda _: 0.0,
        "clip_range": lambda _: 0.0,
    }
    model = PPO.load(
        str(zip_path), device="cpu", custom_objects=custom_objects
    )

    obs_normalizer = _try_load_obs_normalizer(model_dir, metadata)

    return InferenceArtifacts(
        obs_normalizer=obs_normalizer,
        model=model,
        schema=schema,
        metadata=metadata,
        model_dir=model_dir,
    )


def predict_from_frame(
    artifacts: InferenceArtifacts,
    day_frame: pd.DataFrame,
    *,
    shares: Optional[Sequence[float]] = None,
    cash: Optional[float] = None,
    deterministic: bool = True,
) -> np.ndarray:
    """Run one forward pass of the loaded policy.

    Args:
        artifacts: from load_model().
        day_frame: one row per ticker, with all columns in schema.required_columns().
            Must cover every ticker in schema.ticker_order (order does not matter;
            builder will reindex).
        shares: optional per-ticker holdings (length = stock_dim). Defaults to zeros.
            For B0 (cross-sectional dry-run) zero holdings are correct.
        cash: optional cash balance. Defaults to schema.initial_amount (1M).
        deterministic: SB3 predict() deterministic flag.

    Returns:
        1-D np.ndarray of shape (schema.stock_dim,) with values in [-1, 1].
    """
    obs = build_observation(
        day_frame=day_frame,
        schema=artifacts.schema,
        shares=shares,
        cash=cash,
    )
    if obs.shape != (artifacts.schema.state_dim,):
        raise ValueError(
            f"Observation shape {obs.shape} does not match "
            f"schema.state_dim {artifacts.schema.state_dim}"
        )
    # If the model was trained with VecNormalize, apply the same per-element
    # normalization using the stats loaded from vecnormalize.pkl. Without this,
    # a normalized policy would see raw-scale features and produce garbage.
    if artifacts.obs_normalizer is not None:
        obs = artifacts.obs_normalizer.normalize(obs)
    action, _state = artifacts.model.predict(obs, deterministic=deterministic)
    action = np.asarray(action, dtype=float).reshape(-1)
    if action.shape != (artifacts.schema.stock_dim,):
        raise ValueError(
            f"Action shape {action.shape} does not match "
            f"stock_dim {artifacts.schema.stock_dim}"
        )
    return action


def decode_action(
    action: np.ndarray,
    ticker_order: Sequence[str],
    *,
    top_n: int = 10,
    buy_threshold: float = 0.1,
    sell_threshold: float = -0.1,
) -> dict:
    """Convert an action vector into a structured signal summary.

    The env maps action ∈ [-1, 1] to action * hmax shares. For B0 we treat
    the raw action value as a cross-sectional score and sort by it.

    Args:
        action: 1-D array of size stock_dim, values in [-1, 1].
        ticker_order: must match artifacts.schema.ticker_order.
        top_n: how many top buys / top sells to surface.
        buy_threshold / sell_threshold: classify signal label per ticker.

    Returns:
        Dict with top_buys, top_sells, distribution summary, and full signal
        list keyed by ticker. Caller chooses whether to persist / render.
    """
    action = np.asarray(action, dtype=float).reshape(-1)
    if len(ticker_order) != action.size:
        raise ValueError(
            f"ticker_order length {len(ticker_order)} != action size {action.size}"
        )

    scored = list(zip(ticker_order, action.tolist()))
    scored_by_action_desc = sorted(scored, key=lambda x: x[1], reverse=True)

    def _label(x: float) -> str:
        if x >= buy_threshold:
            return "buy"
        if x <= sell_threshold:
            return "sell"
        return "hold"

    top_buys = [
        {"ticker": t, "action": round(a, 4), "signal": _label(a)}
        for t, a in scored_by_action_desc[:top_n]
        if a > 0
    ]
    top_sells = [
        {"ticker": t, "action": round(a, 4), "signal": _label(a)}
        for t, a in scored_by_action_desc[::-1][:top_n]
        if a < 0
    ]

    labels = [_label(a) for _, a in scored]
    distribution = {
        "buy": labels.count("buy"),
        "sell": labels.count("sell"),
        "hold": labels.count("hold"),
    }

    return {
        "distribution": distribution,
        "top_buys": top_buys,
        "top_sells": top_sells,
        "stats": {
            "mean": round(float(action.mean()), 4),
            "std": round(float(action.std()), 4),
            "min": round(float(action.min()), 4),
            "max": round(float(action.max()), 4),
        },
        "signals": {t: round(a, 4) for t, a in scored},
    }

def _try_load_obs_normalizer(
    model_dir: Path, metadata: dict
) -> Optional[ObsNormalizer]:
    """Load VecNormalize stats from model_dir/vecnormalize.pkl if present.

    The file is a serialized VecNormalize wrapper written by SB3's
    ``VecNormalize.save()`` during training. For pure inference we extract
    the running stats (obs_rms.mean, obs_rms.var) + clip_obs + epsilon and
    apply them manually — no VecEnv wrapper needed on our side.

    Returns None when the file is absent (model was trained without
    ``--vecnormalize-obs``) or when loading fails (e.g. cross-environment
    version skew); inference then runs on raw observations.
    """
    stats_file = "vecnormalize.pkl"
    obs_norm_meta = metadata.get("obs_normalization") or {}
    if obs_norm_meta:
        stats_file = obs_norm_meta.get("stats_file", stats_file)
    path = model_dir / stats_file
    if not path.exists():
        return None
    try:
        import gymnasium as gym
        from gymnasium import spaces
        from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

        # VecNormalize.load requires a venv; construct a minimal gymnasium
        # env whose observation / action spaces match the saved wrapper.
        # The dummy env is never actually stepped by inference.
        schema = schema_from_metadata(metadata)

        class _StubEnv(gym.Env):
            def __init__(self):
                super().__init__()
                self.observation_space = spaces.Box(
                    low=-np.inf, high=np.inf,
                    shape=(schema.state_dim,), dtype=np.float32,
                )
                self.action_space = spaces.Box(
                    low=-1.0, high=1.0,
                    shape=(schema.stock_dim,), dtype=np.float32,
                )

            def reset(self, *, seed=None, options=None):
                return np.zeros(schema.state_dim, dtype=np.float32), {}

            def step(self, _action):
                return (
                    np.zeros(schema.state_dim, dtype=np.float32),
                    0.0, True, False, {},
                )

        dummy = DummyVecEnv([lambda: _StubEnv()])
        vec_norm = VecNormalize.load(str(path), dummy)
        return ObsNormalizer(
            mean=np.asarray(vec_norm.obs_rms.mean, dtype=float),
            var=np.asarray(vec_norm.obs_rms.var, dtype=float),
            clip_obs=float(getattr(vec_norm, "clip_obs", 10.0)),
            epsilon=float(getattr(vec_norm, "epsilon", 1e-8)),
        )
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "Failed to load obs normalizer from %s: %s; falling back to raw obs",
            path, exc,
        )
        return None
