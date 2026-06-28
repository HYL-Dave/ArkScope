#!/usr/bin/env python3
"""Sanitized, read-only IBKR news-body retention probe (N6; outward-gated)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from typing import Callable, Iterable, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_sources.ibkr_source import IBKRDataSource  # noqa: E402
from src.ibkr_gateway_lock import ibkr_gateway_lock  # noqa: E402


@dataclass(frozen=True)
class ProbeSpec:
    label: str
    provider: str
    article_id: str


DEFAULT_PROBES = (
    ProbeSpec("recent_body", "DJ-N", "DJ-N$1ec6faa0"),
    ProbeSpec("recent_missing", "DJ-RTA", "DJ-RTA$1ec30364"),
    ProbeSpec("old_body", "BRFG", "BRFG$13738953"),
    ProbeSpec("old_missing", "BRFUPDN", "BRFUPDN$164da0f7"),
    ProbeSpec("alert", "BRFUPDN", "BRFUPDN$1ec59008"),
)

_IBKR_FIELDS = {
    "host": "IBKR_HOST",
    "port": "IBKR_PORT",
    "client_id": "IBKR_CLIENT_ID",
}
_HTML_TAG = re.compile(r"<[^>]+>")


def _apply_effective_ibkr_env(profile_db: Optional[Path]) -> None:
    """Apply DB-over-file IBKR settings without creating or mutating the profile DB."""
    from src.env_keys import ensure_env_loaded, keys_loaded_from_file

    ensure_env_loaded()
    file_keys = keys_loaded_from_file()
    path = profile_db or Path(
        os.environ.get("ARKSCOPE_PROFILE_DB") or ROOT / "data" / "profile_state.db"
    )
    if not path.is_file():
        return
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT field,value FROM data_provider_config WHERE provider='ibkr'"
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    for field, value in rows:
        env_var = _IBKR_FIELDS.get(field)
        if not env_var or not value:
            continue
        if env_var in os.environ and env_var not in file_keys:
            continue
        os.environ[env_var] = value


def _probe_one(source, probe: ProbeSpec) -> dict:
    base = {"label": probe.label, "provider": probe.provider}
    try:
        raw = source.fetch_news_article_body_strict(
            probe.provider, probe.article_id
        )
    except Exception as exc:
        return {
            **base,
            "present": False,
            "length": 0,
            "html_tags": 0,
            "response_class": "error",
            "error_type": type(exc).__name__,
        }
    text = str(raw) if raw is not None else ""
    return {
        **base,
        "present": bool(text),
        "length": len(text),
        "html_tags": len(_HTML_TAG.findall(text)),
        "response_class": "body" if text else "empty",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-db", type=Path)
    return parser


def main(
    argv=None,
    *,
    source_factory: Callable[[], object] = IBKRDataSource,
    probes: Iterable[ProbeSpec] = DEFAULT_PROBES,
    lock_factory: Callable = ibkr_gateway_lock,
) -> int:
    args = build_parser().parse_args(argv)
    _apply_effective_ibkr_env(args.profile_db)
    source = source_factory()
    try:
        with lock_factory():
            results = [_probe_one(source, probe) for probe in probes]
    finally:
        source.disconnect()
    print(json.dumps(results, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
