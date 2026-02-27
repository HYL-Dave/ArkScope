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
