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


def env_file_path() -> Path:
    """The repo's ``config/.env`` path, resolved from this file (cwd-independent)."""
    return Path(__file__).resolve().parents[1] / "config" / ".env"


def unquote_env_value(value: str) -> str:
    """Unwrap an env value: strip surrounding quotes FIRST, then whitespace.

    Order matters — a leading/trailing space INSIDE the quotes (as in
    config/.env's ``EODHD_API_KEY``) is only removed if the quotes come off
    before the whitespace. The loop tolerates outer whitespace and accidental
    double-wrapping; an unmatched or lone quote is left intact so a value that
    legitimately begins with a quote is not corrupted.
    """
    s = value.strip()
    while len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1].strip()
    return s


def read_env_file_values() -> dict[str, str]:
    env_path = env_file_path()
    out: dict[str, str] = {}
    if not env_path.exists():
        return out
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = unquote_env_value(value)
        if key and value:
            out[key] = value
    return out


def peek_env_file_value(name: str) -> str | None:
    return read_env_file_values().get(name)


def ensure_env_loaded() -> None:
    """Load ``config/.env`` into ``os.environ`` once. No-op if already loaded."""
    ensure_env_loaded_excluding(set())


def ensure_env_loaded_excluding(excluded_keys: set[str] | frozenset[str]) -> None:
    """Load ``config/.env`` once, skipping explicit keys.

    Strict provider config uses this to keep legacy-env-only variables alive
    while preventing managed provider keys from becoming runtime authority.
    """
    global _loaded
    if _loaded:
        return
    excluded = set(excluded_keys or set())
    for key, value in read_env_file_values().items():
        if key in excluded:
            continue
        # Only set if not already present — never clobber a real env var.
        if key not in os.environ:
            os.environ[key] = value
            _loaded_keys.add(key)
    _loaded = True


def discard_loaded_key(name: str) -> bool:
    """Remove a key only when this loader supplied it from config/.env."""
    if name not in _loaded_keys:
        return False
    os.environ.pop(name, None)
    _loaded_keys.discard(name)
    return True


def keys_loaded_from_file() -> frozenset:
    """Key names ensure_env_loaded() set from config/.env (effective file-sourced
    keys). Present-but-not-listed keys are real environment variables."""
    return frozenset(_loaded_keys)


def reload_var_from_file(name: str) -> bool:
    """Re-resolve ONE var from config/.env, overwriting os.environ.

    Used when an app-managed override is cleared: the var falls back to its
    config/.env value (tracked as file-sourced), or is removed entirely when the
    file doesn't define it. Returns True if the var is now set."""
    value = read_env_file_values().get(name)
    if value:
        os.environ[name] = value
        _loaded_keys.add(name)
        return True
    os.environ.pop(name, None)
    _loaded_keys.discard(name)
    return False
