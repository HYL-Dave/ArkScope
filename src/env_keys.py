"""
Idempotent loader for API keys from ``config/.env`` into ``os.environ``.

The CLI loads keys via ``src.agents.cli._load_env`` at import, but that module
drags in heavy TUI deps (rich / prompt_toolkit). The API sidecar and the §2 card
pipeline need ANTHROPIC_API_KEY / OPENAI_API_KEY / FINNHUB_API_KEY without that
weight, so this provides the same "set only if absent" behaviour resolved from
the repo root (cwd-independent) and guarded so repeated calls are free.
"""

from __future__ import annotations

import os
from pathlib import Path

_loaded = False


def ensure_env_loaded() -> None:
    """Load ``config/.env`` into ``os.environ`` once. No-op if already loaded."""
    global _loaded
    if _loaded:
        return
    # src/env_keys.py -> parents[1] == repo root, regardless of cwd.
    env_path = Path(__file__).resolve().parents[1] / "config" / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Only set if not already present — never clobber a real env var.
            if key and value and key not in os.environ:
                os.environ[key] = value
    _loaded = True
