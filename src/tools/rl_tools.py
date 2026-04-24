"""
RL Pipeline agent tools — query model status, predictions, and backtest reports.

All 3 tools respect the `rl_pipeline.enabled` config flag:
- disabled (default): return informational message, no PyTorch import
- enabled: read from model registry and perform inference

Design: tools are always registered in ToolRegistry. The enabled/disabled
guard is at execution time, not registration time. This way the LLM always
sees the tool schemas and knows whether RL is available via the response.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

_DISABLED_MSG = (
    "RL Pipeline is currently disabled and should be treated as EXPERIMENTAL.\n\n"
    "Status: the existing production-trained checkpoints (trained_models/ppo_sb3_*)"
    " have been diagnosed with policy collapse — deterministic actions are nearly"
    " state-invariant across dates (see scripts/rl_policy_sensitivity_probe.py and"
    " scripts/rl_ensemble_scan.py). A corrective training run with VecNormalize"
    " observation alignment is in progress; until it is validated end-to-end,"
    " RL tools must NOT be used to generate investment recommendations in the"
    " main decision path.\n\n"
    "The tools remain registered so the agent can inspect model metadata /"
    " backtest reports for research and diagnosis, but any numerical output"
    " should carry an experimental label when surfaced to the user.\n\n"
    "To re-enable after the corrective run passes validation:\n"
    "1. Train a model: python training/train_ppo_sb3.py --vecnormalize-obs ...\n"
    "2. Set rl_pipeline.enabled: true in config/user_profile.yaml"
)


def _is_enabled() -> bool:
    """Check if RL pipeline is enabled in config."""
    try:
        from src.agents.config import get_agent_config
        return get_agent_config().rl_pipeline_enabled
    except Exception:
        return False


def _get_models_dir() -> str:
    """Get models directory from config."""
    try:
        from src.agents.config import get_agent_config
        return get_agent_config().rl_models_dir
    except Exception:
        return "trained_models"


def get_rl_model_status(dal: Any) -> str:
    """List all trained RL models with backtest performance summary.

    Returns model IDs, algorithms, training dates, and key metrics
    (Sharpe, IR, max drawdown) for each registered model.
    """
    if not _is_enabled():
        return _DISABLED_MSG

    try:
        from training.model_registry import ModelRegistry
        registry = ModelRegistry(models_dir=_get_models_dir())
        models = registry.list_models()

        if not models:
            return json.dumps({
                "status": "enabled_no_models",
                "message": "RL Pipeline is enabled but no trained models found.",
                "models_dir": _get_models_dir(),
            })

        result = {
            "status": "active",
            "model_count": len(models),
            "models": [],
        }
        for m in models:
            bt = m.backtest_results or {}
            entry = {
                "model_id": m.model_id,
                "algorithm": m.algorithm,
                "score_source": m.score_source,
                "training_date": m.training_date,
                "stock_dim": m.stock_dim,
                "train_period": m.train_period,
                "test_period": m.test_period,
                "sharpe_ratio": bt.get("sharpe_ratio"),
                "information_ratio": bt.get("information_ratio"),
                "max_drawdown": bt.get("max_drawdown"),
                "cvar_95": bt.get("cvar_95"),
            }
            # Propagate ir_note when IR is None
            if entry["information_ratio"] is None and bt.get("ir_note"):
                entry["ir_note"] = bt["ir_note"]
            result["models"].append(entry)

        return json.dumps(result, default=str)

    except Exception as e:
        logger.error("get_rl_model_status failed: %s", e)
        return json.dumps({"error": f"Failed to load model status: {e}"})


def get_rl_prediction(dal: Any, ticker: str, model_id: str = "latest") -> str:
    """Get RL model prediction for a ticker.

    Uses the specified model (or latest) to generate a daily-frequency
    trading signal based on current market state.

    Note: This is a daily-frequency signal, not a real-time trading instruction.
    The prediction reflects what the RL agent would do given current data.

    Args:
        dal: DataAccessLayer (unused currently, reserved for state construction)
        ticker: Stock ticker symbol
        model_id: Model ID to use, or "latest" for most recent
    """
    if not _is_enabled():
        return _DISABLED_MSG

    try:
        from training.model_registry import ModelRegistry
        registry = ModelRegistry(models_dir=_get_models_dir())

        if model_id == "latest":
            model = registry.get_latest_model()
        else:
            model = registry.get_model(model_id)

        if model is None:
            return json.dumps({
                "error": f"Model '{model_id}' not found.",
                "available_models": [m.model_id for m in registry.list_models()],
            })

        # Inference wiring exists (src.rl.inference.predict_from_frame), but
        # the production models have been diagnosed with policy collapse:
        # deterministic actions are near state-invariant across dates. Until
        # the VecNormalize corrective run is validated, this tool surfaces
        # metadata only and labels any prediction as experimental.
        return json.dumps({
            "status": "experimental_metadata_only",
            "model_id": model.model_id,
            "algorithm": model.algorithm,
            "ticker": ticker.upper(),
            "note": (
                "EXPERIMENTAL: the existing production PPO checkpoints suffer "
                "from policy collapse (see scripts/rl_policy_sensitivity_probe.py "
                "and scripts/rl_ensemble_scan.py). Deterministic actions are "
                "near state-invariant, so inference output is not actionable "
                "and must not be surfaced as a trading recommendation. "
                "A corrective training run with VecNormalize observation "
                "alignment is in progress; until it is validated end-to-end, "
                "this tool returns metadata only."
            ),
            "experimental": True,
            "model_info": {
                "feature_set": model.feature_set,
                "stock_dim": model.stock_dim,
                "train_period": model.train_period,
                "training_date": model.training_date,
            },
        }, default=str)

    except Exception as e:
        logger.error("get_rl_prediction failed: %s", e)
        return json.dumps({"error": f"Failed to get prediction: {e}"})


def get_rl_backtest_report(dal: Any, model_id: str = "latest") -> str:
    """Get backtest performance report for a trained RL model.

    Returns detailed metrics: Sharpe ratio, information ratio, CVaR,
    max drawdown, win rate, equity curve summary, and training parameters.

    Args:
        dal: DataAccessLayer (unused, for interface consistency)
        model_id: Model ID, or "latest" for most recent
    """
    if not _is_enabled():
        return _DISABLED_MSG

    try:
        from training.model_registry import ModelRegistry
        registry = ModelRegistry(models_dir=_get_models_dir())

        if model_id == "latest":
            model = registry.get_latest_model()
        else:
            model = registry.get_model(model_id)

        if model is None:
            return json.dumps({
                "error": f"Model '{model_id}' not found.",
                "available_models": [m.model_id for m in registry.list_models()],
            })

        bt = model.backtest_results or {}
        result = {
            "model_id": model.model_id,
            "algorithm": model.algorithm,
            "score_source": model.score_source,
            "score_type": model.score_type,
            "feature_set": model.feature_set,
            "stock_dim": model.stock_dim,
            "state_dim": model.state_dim,
            "train_period": model.train_period,
            "test_period": model.test_period,
            "epochs": model.epochs,
            "training_date": model.training_date,
            "hyperparams": model.hyperparams,
            "backtest_results": bt,
        }
        # Include ir_note at top level for easy Agent access
        if bt.get("information_ratio") is None and bt.get("ir_note"):
            result["ir_note"] = bt["ir_note"]

        return json.dumps(result, default=str)

    except Exception as e:
        logger.error("get_rl_backtest_report failed: %s", e)
        return json.dumps({"error": f"Failed to get backtest report: {e}"})
