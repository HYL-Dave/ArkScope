"""
Model Registry — track trained RL models with metadata and backtest results.

Provides:
- ModelMetadata: dataclass for model info (algorithm, features, results)
- list_models(): list all registered models
- get_model(): get a specific model's metadata
- save_metadata(): save model metadata after training
- get_latest_model(): get the most recently trained model
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """Metadata for a trained RL model."""

    model_id: str                    # e.g. "ppo_claude_opus_20260301"
    algorithm: str                   # "PPO" | "CPPO"
    score_source: str                # "claude_opus" | "gpt5_high" | "polygon"
    score_type: str = "sentiment"    # "sentiment" | "both"
    feature_set: List[str] = field(default_factory=list)
    stock_dim: int = 0               # number of unique tickers
    state_dim: int = 0               # observation space dimension
    train_period: str = ""           # "2013-01-01 ~ 2018-12-31"
    test_period: str = ""            # "2019-01-01 ~ 2023-12-31"
    epochs: int = 0
    hyperparams: Dict = field(default_factory=dict)
    backtest_results: Dict = field(default_factory=dict)
    training_date: str = ""          # ISO date
    model_path: str = ""             # relative path to .pth
    data_hash: str = ""              # MD5 of training CSV

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "ModelMetadata":
        # Filter out unknown keys for forward-compat
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**filtered)


class ModelRegistry:
    """File-based registry of trained RL models.

    Models are stored in structured directories under models_dir:
        trained_models/
        +-- registry.json
        +-- ppo_claude_opus_20260301/
        |   +-- model.pth
        |   +-- metadata.json
        +-- ...
    """

    def __init__(self, models_dir: str = "trained_models") -> None:
        self._dir = Path(models_dir)
        self._registry_path = self._dir / "registry.json"

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        """Parse training_date string to datetime for reliable sorting.

        Accepts ISO-8601 variants: 2026-03-01, 2026-03-01T12:00:00,
        2026-3-1, etc.  Unparseable strings sort to epoch (oldest).
        """
        if not date_str:
            return datetime.min
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return datetime.min

    def list_models(self) -> List[ModelMetadata]:
        """List all registered models, sorted by training_date descending."""
        index = self._load_index()
        models = [ModelMetadata.from_dict(m) for m in index]
        models.sort(key=lambda m: self._parse_date(m.training_date), reverse=True)
        return models

    def get_model(self, model_id: str) -> Optional[ModelMetadata]:
        """Get metadata for a specific model."""
        index = self._load_index()
        for m in index:
            if m.get("model_id") == model_id:
                return ModelMetadata.from_dict(m)
        return None

    def get_latest_model(self, algorithm: Optional[str] = None) -> Optional[ModelMetadata]:
        """Get the most recently trained model, optionally filtered by algorithm."""
        models = self.list_models()
        if algorithm:
            models = [m for m in models if m.algorithm.upper() == algorithm.upper()]
        return models[0] if models else None

    def save_metadata(self, meta: ModelMetadata) -> None:
        """Save model metadata to registry.

        Creates the model directory and updates registry.json.
        """
        self._dir.mkdir(parents=True, exist_ok=True)

        # Save individual metadata.json
        model_dir = self._dir / meta.model_id
        model_dir.mkdir(parents=True, exist_ok=True)
        meta_path = model_dir / "metadata.json"
        with open(meta_path, "w") as f:
            json.dump(meta.to_dict(), f, indent=2, default=str)

        # Update registry index
        index = self._load_index()
        # Replace if exists, append if new
        index = [m for m in index if m.get("model_id") != meta.model_id]
        index.append(meta.to_dict())
        self._save_index(index)

        logger.info("Saved model metadata: %s", meta.model_id)

    def _load_index(self) -> List[Dict]:
        """Load registry.json, return empty list if not found."""
        if not self._registry_path.exists():
            return []
        try:
            with open(self._registry_path) as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load registry.json: %s", e)
            return []

    def _save_index(self, index: List[Dict]) -> None:
        """Save registry.json."""
        self._dir.mkdir(parents=True, exist_ok=True)
        with open(self._registry_path, "w") as f:
            json.dump(index, f, indent=2, default=str)
