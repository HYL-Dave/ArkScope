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
# Keys THIS loader actually set from config/.env (i.e. absent from the real env
# at load time). A key present in os.environ but NOT in this set came from the
# real environment — which is the EFFECTIVE source, since the loader never
# clobbers (set-if-absent). Lets read-only credential displays report the true
# effective origin instead of guessing from file contents.
_loaded_keys: set = set()


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
                _loaded_keys.add(key)
    _loaded = True


def keys_loaded_from_file() -> frozenset:
    """Key names ensure_env_loaded() set from config/.env (effective file-sourced
    keys). Present-but-not-listed keys are real environment variables."""
    return frozenset(_loaded_keys)


def reload_var_from_file(name: str) -> bool:
    """Re-resolve ONE var from config/.env, overwriting os.environ.

    Used when an app-managed override is cleared: the var falls back to its
    config/.env value (tracked as file-sourced), or is removed entirely when the
    file doesn't define it. Returns True if the var is now set."""
    env_path = Path(__file__).resolve().parents[1] / "config" / ".env"
    value = None
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            if key.strip() == name:
                value = val.strip().strip('"').strip("'")
    if value:
        os.environ[name] = value
        _loaded_keys.add(name)
        return True
    os.environ.pop(name, None)
    _loaded_keys.discard(name)
    return False
