from __future__ import annotations

import argparse
import json
from typing import Any


MAX_ERROR_LEN = 240


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ArkScope direct-local prices worker")
    parser.add_argument("--source", choices=("ibkr_prices", "price_backfill"), required=True)
    parser.add_argument("--tickers", required=True)
    parser.add_argument("--lookback-days", type=int, default=5)
    parser.add_argument("--provider", choices=("ibkr", "polygon"), default="ibkr")
    parser.add_argument("--gateway-lock-held", action="store_true")
    return parser.parse_args(argv)


def _apply_provider_config() -> None:
    from src.data_provider_config import apply_env

    apply_env()


def _is_retryable_error(message: str) -> bool:
    return "market_data.db write lock busy" in message


def sanitize_result(result: dict[str, Any]) -> dict[str, Any]:
    errors = result.get("errors") if isinstance(result.get("errors"), dict) else {}
    return {
        "status": "succeeded",
        "provider": result.get("provider"),
        "tickers_scanned": int(result.get("tickers_scanned") or 0),
        "gaps_found": int(result.get("gaps_found") or 0),
        "rows_added": int(result.get("rows_added") or 0),
        "error_count": len(errors),
        "error_tickers": sorted(str(key) for key in errors)[:25],
    }


def sanitize_error(exc: BaseException) -> dict[str, Any]:
    message = str(exc)[:MAX_ERROR_LEN]
    return {
        "status": "failed",
        "error_class": exc.__class__.__name__,
        "error": message,
        "retryable": _is_retryable_error(message),
    }


def _run_worker(
    *,
    source: str,
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
            source=args.source,
            tickers=args.tickers,
            lookback_days=args.lookback_days,
            provider=args.provider,
            gateway_lock_held=args.gateway_lock_held,
        )
        payload = sanitize_result(result)
        code = 0
    except Exception as exc:  # noqa: BLE001 - worker boundary sanitizes every failure
        payload = sanitize_error(exc)
        code = 1
    print(json.dumps(payload, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
