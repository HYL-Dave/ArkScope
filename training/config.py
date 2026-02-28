"""
Training configuration — local replacement for finrl.config + finrl.main.

Provides constants and utility functions previously imported from the finrl
package, eliminating that heavy dependency.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Directory constants ──────────────────────────────────────
TRAINED_MODEL_DIR = "trained_models"
RESULTS_DIR = "results"

# ── Technical indicators (stockstats column names) ───────────
INDICATORS = [
    "macd",
    "boll_ub",
    "boll_lb",
    "rsi_30",
    "cci_30",
    "dx_30",
    "close_30_sma",
    "close_60_sma",
]


def check_and_make_directories(directories: list[str]) -> None:
    """Create directories if they don't exist (replaces finrl.main helper)."""
    for d in directories:
        os.makedirs(d, exist_ok=True)


# ── Sentiment scaling presets ────────────────────────────────
# Controls how much LLM sentiment scores influence trading actions.
#
# Upstream FinRL_DeepSeek has two variants:
#   _01 files: "weak" scaling (±0.1%) — barely perceptible influence
#   non-_01 files: "strong" scaling (±10%) — significant influence
#
# Our code originally imported the non-_01 (strong) variant, while
# upstream train_ppo_llm.py actually used the _01 (weak) variant.
# See training/UPSTREAM.md for full lineage details.

SENTIMENT_SCALES = {
    "strong": {
        # ±10% scaling (our default, from env_stocktrading_llm.py)
        "strong_mismatch": 0.9,     # sentiment strongly disagrees with action
        "moderate_mismatch": 0.95,  # sentiment moderately disagrees
        "hold_dampen": 0.98,        # neutral sentiment dampens action
        "strong_match": 1.1,        # sentiment strongly agrees with action
        "moderate_match": 1.05,     # sentiment moderately agrees
    },
    "weak": {
        # ±0.1% scaling (upstream _01 variant, used by original train_ppo_llm.py)
        "strong_mismatch": 0.999,
        "moderate_mismatch": 0.9995,
        "hold_dampen": 1.0,         # no hold dampening in _01 variant
        "strong_match": 1.001,
        "moderate_match": 1.0005,
    },
}
