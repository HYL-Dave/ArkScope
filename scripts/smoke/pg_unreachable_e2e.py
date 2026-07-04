from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


POISON_DSN = "postgresql://pg-poison.invalid/arkscope?connect_timeout=1"


@dataclass(frozen=True)
class CheckSpec:
    name: str
    method: str
    path: str
    expected_status: int | tuple[int, ...]
    assert_body: Callable[[Any], None] | None = None


@dataclass
class CheckResult:
    name: str
    ok: bool
    status_code: int | None = None
    detail: str = ""


@dataclass
class SmokeReport:
    ok: bool
    poison_label: str
    pg_attempts: list[str]
    checks: list[CheckResult]

    def to_sanitized_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "poison_label": sanitize_secret(self.poison_label),
            "pg_attempts": [sanitize_secret(x) for x in self.pg_attempts],
            "checks": [
                asdict(check) | {"detail": sanitize_secret(check.detail)}
                for check in self.checks
            ],
        }


def sanitize_secret(value: Any) -> str:
    text = str(value)
    text = re.sub(r"(postgres(?:ql)?://[^:/@]+):([^@]+)@", r"\1:***@", text)
    text = re.sub(
        r"(?i)(api[_-]?key|token|password|secret)=([^&\s]+)",
        r"\1=***",
        text,
    )
    return text


_SENSITIVE_CONNECT_KWARGS = {"password", "sslpassword", "passfile"}


class PgPoison:
    def __init__(self) -> None:
        self.attempts: list[str] = []

    def connect(self, *args: Any, **kwargs: Any) -> None:
        if args:
            label: Any = args[0]
        elif "dsn" in kwargs:
            label = kwargs["dsn"]
        else:
            # kwargs dict repr defeats the URL/key=value sanitizer regexes —
            # redact credential values before the label is recorded.
            label = {
                key: ("***" if key in _SENSITIVE_CONNECT_KWARGS else value)
                for key, value in kwargs.items()
            }
        self.attempts.append(sanitize_secret(label))
        raise RuntimeError("PG_UNREACHABLE_E2E_POISON: PostgreSQL connection attempted")


def _assert_key(key: str) -> Callable[[Any], None]:
    def inner(body: Any) -> None:
        assert isinstance(body, dict)
        assert key in body

    return inner


def _assert_market_status(body: Any) -> None:
    assert body["pg_fallback_active"] is False
    assert body["prices_authority"] == "local"
    assert body["routing_enabled"] is True


def _assert_update_retired(body: Any) -> None:
    detail = body.get("detail") if isinstance(body, dict) else None
    payload = detail if isinstance(detail, dict) else body
    assert payload.get("code") in {
        "pg_market_update_retired",
        "pg_market_bootstrap_retired",
    }


def _assert_list_or_dict(_: Any) -> None:
    assert True


REQUIRED_CHECKS: tuple[CheckSpec, ...] = (
    CheckSpec("healthz", "GET", "/healthz", 200, _assert_key("status")),
    CheckSpec("system_status", "GET", "/status", 200, _assert_key("data_sources")),
    CheckSpec("provider_config", "GET", "/providers/config", 200, _assert_key("providers")),
    CheckSpec("provider_health", "GET", "/providers/health", 200, _assert_list_or_dict),
    CheckSpec("schedule_status", "GET", "/schedule", 200, _assert_key("sources")),
    CheckSpec("market_status", "GET", "/market-data/status", 200, _assert_market_status),
    CheckSpec(
        "market_update_retired",
        "POST",
        "/market-data/update",
        409,
        _assert_update_retired,
    ),
    CheckSpec("price_read", "GET", "/prices/NVDA?interval=15min&days=7", 200, _assert_key("bars")),
    CheckSpec("price_coverage", "GET", "/market-data/coverage/NVDA", 200, _assert_list_or_dict),
    CheckSpec("news_status", "GET", "/news/status", 200, _assert_list_or_dict),
    CheckSpec("news_feed", "GET", "/news/feed?days=7&limit=5", 200, _assert_key("items")),
    CheckSpec("news_ticker", "GET", "/news/NVDA?days=30", 200, _assert_key("articles")),
    CheckSpec("news_sentiment", "GET", "/news/NVDA/sentiment?days=9999", 200, _assert_key("ticker")),
    CheckSpec("fundamentals_stored", "GET", "/fundamentals/NVDA?stored=true", 200, _assert_list_or_dict),
    CheckSpec("iv_history", "GET", "/options/AMD/history", 200, _assert_key("points")),
    CheckSpec("sa_feed", "GET", "/sa/feed?limit=5", 200, _assert_list_or_dict),
    CheckSpec("sa_health", "GET", "/sa/market-news/health", 200, _assert_key("severity")),
    CheckSpec("macro_status", "GET", "/macro/status", 200, _assert_key("local_first_active")),
    CheckSpec("macro_health", "GET", "/macro/health", (200, 503), _assert_key("severity")),
    CheckSpec("macro_ipo", "GET", "/macro/ipo-calendar?limit=5", 200, _assert_list_or_dict),
    CheckSpec("reports", "GET", "/reports", 200, _assert_list_or_dict),
    CheckSpec("universe_summaries", "DIRECT", "get_universe_summaries", 200, _assert_list_or_dict),
)


def _expected(status: int, expected: int | tuple[int, ...]) -> bool:
    return status in expected if isinstance(expected, tuple) else status == expected


def run_route_checks(
    client: Any,
    checks: Iterable[CheckSpec] = REQUIRED_CHECKS,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for check in checks:
        try:
            if check.method == "DIRECT" and check.name == "universe_summaries":
                results.append(run_universe_summary_check())
                continue
            response = client.request(check.method, check.path)
            body = response.json()
            if not _expected(response.status_code, check.expected_status):
                results.append(
                    CheckResult(check.name, False, response.status_code, str(body)[:500])
                )
                continue
            if check.assert_body is not None:
                check.assert_body(body)
            results.append(CheckResult(check.name, True, response.status_code, ""))
        except Exception as exc:
            results.append(CheckResult(check.name, False, None, sanitize_secret(repr(exc))))
    return results


def run_universe_summary_check() -> CheckResult:
    try:
        from src.tools.analysis_tools import get_universe_summaries

        out = get_universe_summaries(None, days=7)
        assert isinstance(out, dict)
        return CheckResult("universe_summaries", True, None, "")
    except Exception as exc:
        return CheckResult("universe_summaries", False, None, sanitize_secret(repr(exc)))


def _make_live_client():
    from fastapi.testclient import TestClient
    from src.api.app import create_app

    return TestClient(create_app())


def run_smoke(
    *,
    poison_dsn: str = POISON_DSN,
    client_factory: Callable[[], Any] = _make_live_client,
) -> SmokeReport:
    old_disable_scheduler = os.environ.get("ARKSCOPE_DISABLE_SCHEDULER")
    old_e2e_marker = os.environ.get("ARKSCOPE_PG_UNREACHABLE_E2E")
    os.environ["ARKSCOPE_DISABLE_SCHEDULER"] = "1"
    os.environ["ARKSCOPE_PG_UNREACHABLE_E2E"] = "1"

    from src.api import dependencies

    dependencies.get_dal.cache_clear()
    dependencies.get_registry.cache_clear()

    from src.tools import data_access as data_access_mod

    original_loader = data_access_mod.DataAccessLayer._load_env_db_dsn
    data_access_mod.DataAccessLayer._load_env_db_dsn = lambda self: poison_dsn

    import psycopg2

    poison = PgPoison()
    original_connect = psycopg2.connect
    psycopg2.connect = poison.connect

    checks: list[CheckResult] = []
    try:
        with client_factory() as client:
            checks = run_route_checks(client)
    except Exception as exc:
        checks.append(CheckResult("app_start_or_lifespan", False, None, sanitize_secret(repr(exc))))
    finally:
        data_access_mod.DataAccessLayer._load_env_db_dsn = original_loader
        psycopg2.connect = original_connect
        _restore_env("ARKSCOPE_DISABLE_SCHEDULER", old_disable_scheduler)
        _restore_env("ARKSCOPE_PG_UNREACHABLE_E2E", old_e2e_marker)
        dependencies.get_dal.cache_clear()
        dependencies.get_registry.cache_clear()

    ok = all(check.ok for check in checks) and not poison.attempts
    return SmokeReport(
        ok=ok,
        poison_label=poison_dsn,
        pg_attempts=poison.attempts,
        checks=checks,
    )


def _restore_env(name: str, old_value: str | None) -> None:
    if old_value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = old_value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--poison-dsn", default=POISON_DSN)
    parser.add_argument("--output")
    return parser.parse_args(sys.argv[1:] if argv is None else argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_smoke(poison_dsn=args.poison_dsn)
    payload = report.to_sanitized_dict()
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
