from __future__ import annotations

import argparse
import json
import re
from typing import Any


MAX_ERROR_LEN = 240
_PRICE_RESULT_STATUSES = frozenset({"succeeded", "partial", "failed"})
_PRICE_COUNT_FIELDS = (
    "tickers_scanned",
    "succeeded_ticker_count",
    "gaps_found",
    "rows_added",
    "unresolved_after_fetch_count",
)
_SAFE_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9 ._-]{0,11}$")
_SAFE_ERROR_CODES = frozenset({"ibkr_gateway_unavailable"})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ArkScope direct-local prices worker")
    parser.add_argument("--tickers", required=True)
    parser.add_argument("--lookback-days", type=int, default=5)
    parser.add_argument("--provider", choices=("ibkr", "polygon"), default="ibkr")
    parser.add_argument("--gateway-lock-held", action="store_true")
    return parser.parse_args(argv)


def _apply_provider_config() -> None:
    from src.data_provider_config import DataProviderConfigStore, apply_env

    apply_env(DataProviderConfigStore())


def _is_retryable_error(message: str) -> bool:
    return "market_data.db write lock busy" in message


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"invalid {field}")
    return value


def _ticker_ids(value: Any, field: str) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        raise ValueError(f"invalid {field}")
    if any(not isinstance(item, str) for item in value):
        raise ValueError(f"invalid {field}")
    result = sorted({item.strip().upper() for item in value})
    if any(not _SAFE_TICKER.fullmatch(item) for item in result):
        raise ValueError(f"invalid {field}")
    return result


def sanitize_result(result: dict[str, Any]) -> dict[str, Any]:
    status = result.get("status")
    if status not in _PRICE_RESULT_STATUSES:
        raise ValueError("invalid price collection status")
    provider = result.get("provider")
    if provider not in {"ibkr", "polygon"}:
        raise ValueError("invalid provider")
    counts = {
        field: _nonnegative_int(result.get(field), field)
        for field in _PRICE_COUNT_FIELDS
    }
    errors = result.get("errors")
    if not isinstance(errors, dict):
        raise ValueError("invalid errors")
    error_tickers = _ticker_ids(list(errors), "error_tickers")
    unresolved = _ticker_ids(
        result.get("unresolved_after_fetch_tickers"),
        "unresolved_after_fetch_tickers",
    )
    error_count = len(error_tickers)
    if counts["unresolved_after_fetch_count"] != len(unresolved):
        raise ValueError("invalid unresolved_after_fetch_count")
    if not set(unresolved).issubset(error_tickers):
        raise ValueError("unresolved tickers must be issue tickers")
    scanned = counts["tickers_scanned"]
    if counts["succeeded_ticker_count"] != scanned - error_count:
        raise ValueError("invalid succeeded_ticker_count")
    expected = (
        "succeeded" if error_count == 0
        else "failed" if scanned > 0 and error_count == scanned
        else "partial"
    )
    if scanned <= 0 or status != expected:
        raise ValueError("status does not match price collection facts")
    return {
        "status": status,
        "provider": provider,
        **counts,
        "error_count": error_count,
        "error_tickers": error_tickers[:25],
        "unresolved_after_fetch_tickers": unresolved[:25],
    }


def sanitize_error(exc: BaseException) -> dict[str, Any]:
    raw = str(exc)
    retryable = _is_retryable_error(raw)
    payload = {
        "status": "failed",
        "error_class": exc.__class__.__name__,
        "error": raw[:MAX_ERROR_LEN] if retryable else "",
        "retryable": retryable,
    }
    error_code = getattr(exc, "error_code", None)
    if error_code in _SAFE_ERROR_CODES:
        payload["error_code"] = error_code
    return payload


def _run_worker(
    *,
    tickers: str,
    lookback_days: int,
    provider: str,
    gateway_lock_held: bool,
) -> dict[str, Any]:
    from src.market_data_direct import backfill_prices_direct

    return backfill_prices_direct(
        tickers_arg=tickers,
        lookback_days=lookback_days,
        provider=provider,
        acquire_gateway_lock=not gateway_lock_held,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        _apply_provider_config()
        result = _run_worker(
            tickers=args.tickers,
            lookback_days=args.lookback_days,
            provider=args.provider,
            gateway_lock_held=args.gateway_lock_held,
        )
        payload = sanitize_result(result)
        code = 1 if payload["status"] == "failed" else 0
    except Exception as exc:  # noqa: BLE001 - worker boundary sanitizes every failure
        payload = sanitize_error(exc)
        code = 1
    print(json.dumps(payload, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
