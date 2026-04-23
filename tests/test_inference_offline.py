"""Smoke tests for Phase B0 offline inference.

Guards the three B0 promises:
  (1) load_model() succeeds on a real artifact despite numpy version skew
  (2) predict_from_frame() returns a stock_dim-sized action in [-1, 1]
  (3) decode_action() produces a well-formed signal dict

Intentionally narrow — does NOT validate signal quality. That is B2's job.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MODEL_DIR = (
    _REPO_ROOT
    / "trained_models"
    / "ppo_sb3_train_polygon_multi_both_ext_100ep_s42_20260415T165924Z_9c0a66"
)
_CSV_PATH = _REPO_ROOT / "training" / "data_prep" / "output" / "train_polygon_multi_both_ext.csv"


@pytest.fixture(scope="module")
def artifacts():
    if not (_MODEL_DIR / "model_sb3.zip").exists():
        pytest.skip(f"Model archive not found at {_MODEL_DIR}")
    if not (_MODEL_DIR / "metadata.json").exists():
        pytest.skip(f"Model metadata not found at {_MODEL_DIR}")

    from src.rl.inference import load_model
    return load_model(_MODEL_DIR)


@pytest.fixture(scope="module")
def last_day_frame():
    if not _CSV_PATH.exists():
        pytest.skip(f"Training CSV not found at {_CSV_PATH}")
    df = pd.read_csv(_CSV_PATH, index_col=0)
    df["date"] = df["date"].astype(str)
    last_date = sorted(df["date"].unique())[-1]
    return df[df["date"] == last_date].reset_index(drop=True)


def test_load_model_returns_schema_and_model(artifacts):
    assert artifacts.model is not None
    assert artifacts.schema.stock_dim == 143
    assert artifacts.schema.state_dim == 1717
    assert artifacts.metadata["model_id"].startswith("ppo_sb3_")
    assert len(artifacts.schema.ticker_order) == 143
    assert artifacts.schema.tech_indicator_list[0] == "macd"


def test_predict_from_frame_returns_bounded_action(artifacts, last_day_frame):
    from src.rl.inference import predict_from_frame
    action = predict_from_frame(artifacts, last_day_frame)
    assert action.shape == (artifacts.schema.stock_dim,)
    assert action.dtype == np.float64
    # SB3 Box action space clips to [-1, 1]; allow tiny numeric slop
    assert np.all(action >= -1.0 - 1e-6)
    assert np.all(action <= 1.0 + 1e-6)
    # Actions should be non-trivial — the zero-vector case would indicate
    # the model wasn't actually loaded or the obs fed is degenerate.
    assert float(np.abs(action).max()) > 1e-3


def test_decode_action_shape_and_counts(artifacts, last_day_frame):
    from src.rl.inference import decode_action, predict_from_frame

    action = predict_from_frame(artifacts, last_day_frame)
    decoded = decode_action(
        action,
        artifacts.schema.ticker_order,
        top_n=5,
    )

    dist = decoded["distribution"]
    assert dist["buy"] + dist["sell"] + dist["hold"] == artifacts.schema.stock_dim

    assert len(decoded["top_buys"]) <= 5
    assert len(decoded["top_sells"]) <= 5

    if decoded["top_buys"]:
        assert decoded["top_buys"][0]["action"] >= decoded["top_buys"][-1]["action"]
        assert decoded["top_buys"][0]["signal"] in {"buy", "hold"}

    if decoded["top_sells"]:
        assert decoded["top_sells"][0]["action"] <= decoded["top_sells"][-1]["action"]
        assert decoded["top_sells"][0]["signal"] in {"sell", "hold"}

    assert "mean" in decoded["stats"]
    assert len(decoded["signals"]) == artifacts.schema.stock_dim


def test_predict_is_deterministic(artifacts, last_day_frame):
    """Same input + deterministic=True should yield identical action twice."""
    from src.rl.inference import predict_from_frame

    a1 = predict_from_frame(artifacts, last_day_frame, deterministic=True)
    a2 = predict_from_frame(artifacts, last_day_frame, deterministic=True)
    np.testing.assert_allclose(a1, a2, rtol=0, atol=0)