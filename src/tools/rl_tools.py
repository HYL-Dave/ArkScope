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
    "RL Pipeline is not enabled. No trained models are available yet.\n\n"
    "To enable:\n"
    "1. Train a model: python training/train_ppo_llm.py\n"
    "2. Set rl_pipeline.enabled: true in config/user_profile.yaml\n\n"
    "The RL Pipeline will provide daily-frequency trading signals based on "
    "PPO/CPPO reinforcement learning models trained on historical price data "
    "and LLM sentiment scores."
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
            result["models"].append({
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
            })

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

        # Phase 1c: return model info + placeholder for actual inference
        # Actual inference (load .pth, construct state, forward pass) will be
        # implemented in Phase 1b after training enhancement is complete.
        return json.dumps({
            "status": "model_found",
            "model_id": model.model_id,
            "algorithm": model.algorithm,
            "ticker": ticker.upper(),
            "note": (
                "Inference not yet implemented. This tool currently confirms "
                "model availability. Full inference (state construction → "
                "forward pass → action interpretation) will be added in "
                "Phase 1b after training enhancement is complete."
            ),
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
            "backtest_results": model.backtest_results,
        }

        return json.dumps(result, default=str)

    except Exception as e:
        logger.error("get_rl_backtest_report failed: %s", e)
        return json.dumps({"error": f"Failed to get backtest report: {e}"})
