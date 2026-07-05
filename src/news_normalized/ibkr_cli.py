"""Collect IBKR news through the normalized local writer in an isolated process."""

from __future__ import annotations

import argparse
from contextlib import contextmanager, nullcontext, redirect_stderr
from dataclasses import asdict, is_dataclass
import io
import json
import logging
import sqlite3
from typing import Any, Iterable


DEFAULT_MAX_ARTICLES = 50_000
DEFAULT_MAX_BODY_FETCHES = 50_000
_COUNT_KEYS = (
    "articles_seen",
    "articles_inserted",
    "bodies_fetched",
    "legacy_rows_inserted",
    "legacy_rows_updated",
    "projection_skipped_no_ticker",
)


def _parse_tickers(value: str) -> list[str]:
    tickers = [item.strip().upper() for item in value.split(",") if item.strip()]
    if not tickers:
        raise argparse.ArgumentTypeError("--tickers must contain at least one ticker")
    return tickers


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write IBKR news directly to normalized SQLite tables."
    )
    parser.add_argument("--tickers", required=True, type=_parse_tickers)
    parser.add_argument(
        "--max-articles", type=int, default=DEFAULT_MAX_ARTICLES,
        help="Maximum headline records to process in this worker run.",
    )
    parser.add_argument(
        "--max-body-fetches", type=int, default=DEFAULT_MAX_BODY_FETCHES,
        help="Maximum article-body requests to spend in this worker run.",
    )
    parser.add_argument(
        "--gateway-lock-held",
        action="store_true",
        help="Parent scheduler already holds the shared IBKR Gateway lock.",
    )
    args = parser.parse_args(argv)
    if args.max_articles < 0 or args.max_body_fetches < 0:
        parser.error("budgets must be non-negative")
    return args


def _mapping(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return dict(value)
    return {}


def _continuation_counts(value: Any) -> dict[str, Any] | None:
    data = _mapping(value)
    if not data:
        return None
    ticker_count = len(data.get("deferred_tickers") or ())
    body_count = len(data.get("deferred_body_ids") or ())
    has_cursor = bool(data.get("cursor"))
    if not ticker_count and not body_count and not has_cursor:
        return None
    return {
        "deferred_ticker_count": ticker_count,
        "deferred_body_count": body_count,
        "has_cursor": has_cursor,
    }


def sanitize_worker_result(result: Any) -> dict[str, Any]:
    data = _mapping(result)
    payload: dict[str, Any] = {"status": str(data.get("status") or "unknown")}
    for key in _COUNT_KEYS:
        try:
            payload[key] = int(data.get(key) or 0)
        except (TypeError, ValueError):
            payload[key] = 0

    errors = data.get("errors") or {}
    error_count = len(errors) if isinstance(errors, dict) else 0
    payload["error_count"] = error_count
    payload["error_classes"] = ["ProviderError"] if error_count else []

    continuation = _continuation_counts(data.get("continuation"))
    if continuation is not None:
        payload["continuation"] = continuation
    return payload


_MAX_ERROR_LEN = 600


def _is_retryable_worker_error(message: str) -> bool:
    return "market_data.db write lock busy" in message


def sanitize_worker_error(exc: BaseException) -> dict[str, Any]:
    message = str(exc)[:_MAX_ERROR_LEN]
    retryable = _is_retryable_worker_error(message)
    payload = {"status": "failed"}
    for key in _COUNT_KEYS:
        payload[key] = 0
    payload["error_count"] = 1
    payload["error_classes"] = [type(exc).__name__]
    payload["error"] = message if retryable else ""
    payload["retryable"] = retryable
    return payload


@contextmanager
def _suppress_provider_stderr_logging():
    previous_disable = logging.root.manager.disable
    try:
        logging.disable(logging.CRITICAL)
        with redirect_stderr(io.StringIO()):
            yield
    finally:
        logging.disable(previous_disable)


def _apply_provider_config() -> None:
    from src.data_provider_config import DataProviderConfigStore, apply_env

    apply_env(DataProviderConfigStore())


def _run_worker(
    tickers: Iterable[str],
    *,
    max_articles: int,
    max_body_fetches: int,
    gateway_lock_held: bool,
) -> Any:
    from data_sources.ibkr_client_id import ibkr_client_id_for
    from data_sources.ibkr_source import IBKRDataSource
    from src.ibkr_gateway_lock import ibkr_gateway_lock
    from src.market_data_admin import resolve_market_db_path
    from src.market_data_direct import market_write_lock
    from src.news_normalized.ibkr_adapter import IBKRNormalizedProvider
    from src.news_normalized.ibkr_runtime import IBKRRuntimeGateway
    from src.news_normalized.models import WriterBudget
    from src.news_normalized.store import NormalizedNewsStore
    from src.news_normalized.writer import write_news_batch

    source = IBKRDataSource(client_id=ibkr_client_id_for("news"))
    gateway = IBKRRuntimeGateway(source)
    conn = None
    gateway_lock = nullcontext() if gateway_lock_held else ibkr_gateway_lock()
    try:
        with gateway_lock:
            provider = IBKRNormalizedProvider(
                gateway,
                acquire_gateway_lock=False,
            )
            conn = sqlite3.connect(resolve_market_db_path(), timeout=10.0)
            store = NormalizedNewsStore(conn)
            return write_news_batch(
                store,
                provider,
                tickers,
                WriterBudget(max_articles, max_body_fetches),
                project_legacy=True,
                write_lock_factory=market_write_lock,
            )
    finally:
        if conn is not None:
            conn.close()
        gateway.close()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        with _suppress_provider_stderr_logging():
            _apply_provider_config()
            result = _run_worker(
                args.tickers,
                max_articles=args.max_articles,
                max_body_fetches=args.max_body_fetches,
                gateway_lock_held=args.gateway_lock_held,
            )
        payload = sanitize_worker_result(result)
        code = 0
    except Exception as exc:  # noqa: BLE001 - stdout must remain sanitized.
        payload = sanitize_worker_error(exc)
        code = 1
    print(json.dumps(payload, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
