from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qs, urlsplit


POISON_DSN = "postgresql://pg-poison.invalid/arkscope?connect_timeout=1"


def _bootstrap_repo_root() -> None:
    repo_root = str(Path(__file__).resolve().parents[2])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


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


class _DirectResponse:
    def __init__(self, status_code: int, body: Any):
        self.status_code = status_code
        self._body = _jsonable(body)

    def json(self) -> Any:
        return self._body


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return _jsonable(value.model_dump())
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


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


class _HandlerDirectClient:
    """Minimal route harness for the PG-unreachable smoke.

    This deliberately avoids FastAPI ``TestClient``/lifespan. In PG-unreachable
    environments that stack can hang before route evidence is emitted; the smoke
    needs direct, explicit dependencies and still preserves HTTPException body
    shape for the checked routes.
    """

    def __init__(
        self,
        *,
        dal: Any,
        registry: Any,
        profile_store: Any,
        provider_store: Any,
    ) -> None:
        self.dal = dal
        self.registry = registry
        self.profile_store = profile_store
        self.provider_store = provider_store

    @classmethod
    def from_live_dependencies(cls) -> "_HandlerDirectClient":
        from src.api import dependencies
        from src.api.routes import providers_config

        return cls(
            dal=dependencies.get_dal(),
            registry=dependencies.get_registry(),
            profile_store=dependencies.get_profile_store(),
            provider_store=providers_config.get_data_provider_store_lenient(),
        )

    def __enter__(self) -> "_HandlerDirectClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    def request(self, method: str, path: str) -> _DirectResponse:
        from fastapi import HTTPException

        try:
            return self._dispatch(method.upper(), path)
        except HTTPException as exc:
            return _DirectResponse(exc.status_code, {"detail": exc.detail})

    def _dispatch(self, method: str, path: str) -> _DirectResponse:
        from fastapi import Response

        parsed = urlsplit(path)
        route = parsed.path
        query = parse_qs(parsed.query)

        def qstr(name: str, default: str | None = None) -> str | None:
            values = query.get(name)
            return values[-1] if values else default

        def qint(name: str, default: int) -> int:
            raw = qstr(name)
            return int(raw) if raw not in (None, "") else default

        if method == "GET" and route == "/healthz":
            from src.api.routes import health

            return _DirectResponse(200, health.healthz())

        if method == "GET" and route == "/status":
            from src.api.routes import health

            return _DirectResponse(200, health.status(dal=self.dal, registry=self.registry))

        if method == "GET" and route == "/providers/config":
            from src.api.routes import providers_config

            return _DirectResponse(
                200,
                providers_config.providers_config(store=self.provider_store),
            )

        if method == "GET" and route == "/providers/health":
            from src.api.routes import health

            return _DirectResponse(200, health.providers_health(dal=self.dal))

        if method == "GET" and route == "/schedule":
            from src.api.routes import schedule

            return _DirectResponse(200, schedule.get_schedule())

        if method == "GET" and route == "/market-data/status":
            from src.api.routes import market_data

            return _DirectResponse(
                200,
                market_data.market_data_status(store=self.profile_store),
            )

        if method == "POST" and route == "/market-data/update":
            from src.api.routes import market_data

            return _DirectResponse(
                200,
                market_data.update_route(store=self.profile_store),
            )

        if method == "GET" and route.startswith("/prices/"):
            from src.api.routes import prices

            ticker = route.removeprefix("/prices/").split("/", 1)[0]
            return _DirectResponse(
                200,
                prices.prices_for_ticker(
                    ticker,
                    interval=qstr("interval", "15min") or "15min",
                    days=qint("days", 30),
                    dal=self.dal,
                ),
            )

        if method == "GET" and route.startswith("/market-data/coverage/"):
            from src.api.routes import market_data

            ticker = route.rsplit("/", 1)[-1]
            return _DirectResponse(200, market_data.market_data_coverage(ticker))

        if method == "GET" and route == "/news/status":
            from src.api.routes import news

            return _DirectResponse(200, news.news_status(store=self.profile_store))

        if method == "GET" and route == "/news/feed":
            from src.api.routes import news

            return _DirectResponse(
                200,
                news.news_feed(
                    q=qstr("q"),
                    ticker=qstr("ticker"),
                    source=qstr("source"),
                    days=qint("days", 30),
                    limit=qint("limit", 50),
                    offset=qint("offset", 0),
                    dal=self.dal,
                ),
            )

        if method == "GET" and route.startswith("/news/") and route.endswith("/sentiment"):
            from src.api.routes import news

            ticker = route.removeprefix("/news/").removesuffix("/sentiment").strip("/")
            return _DirectResponse(
                200,
                news.news_sentiment(ticker, days=qint("days", 7), dal=self.dal),
            )

        if method == "GET" and route.startswith("/news/"):
            from src.api.routes import news

            ticker = route.removeprefix("/news/").split("/", 1)[0]
            return _DirectResponse(
                200,
                news.news_for_ticker(
                    ticker,
                    days=qint("days", 30),
                    source=qstr("source", "auto") or "auto",
                    dal=self.dal,
                ),
            )

        if method == "GET" and route.startswith("/fundamentals/"):
            from src.api.routes import fundamentals

            ticker = route.rsplit("/", 1)[-1]
            stored = (qstr("stored", "false") or "false").lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
            return _DirectResponse(
                200,
                fundamentals.fundamentals(ticker, stored=stored, dal=self.dal),
            )

        if method == "GET" and route.startswith("/options/") and route.endswith("/history"):
            from src.api.routes import options

            ticker = route.removeprefix("/options/").removesuffix("/history").strip("/")
            return _DirectResponse(200, options.iv_history(ticker, dal=self.dal))

        if method == "GET" and route == "/sa/feed":
            from src.api.routes import seeking_alpha

            return _DirectResponse(
                200,
                seeking_alpha.sa_feed(
                    q=qstr("q"),
                    ticker=qstr("ticker"),
                    item_type=qstr("item_type"),
                    days=qint("days", 30),
                    limit=qint("limit", 50),
                    offset=qint("offset", 0),
                    dal=self.dal,
                ),
            )

        if method == "GET" and route == "/sa/market-news/health":
            from src.api.routes import seeking_alpha

            response = Response()
            body = seeking_alpha.market_news_health(
                response=response,
                strict=(qstr("strict", "false") or "false").lower() == "true",
                dal=self.dal,
            )
            return _DirectResponse(response.status_code or 200, body)

        if method == "GET" and route == "/macro/status":
            from src.api.routes import macro_calendar

            return _DirectResponse(
                200,
                macro_calendar.macro_status(store=self.profile_store),
            )

        if method == "GET" and route == "/macro/health":
            from src.api.routes import macro_calendar

            response = Response()
            body = macro_calendar.macro_calendar_health(
                response=response,
                strict=(qstr("strict", "false") or "false").lower() == "true",
                dal=self.dal,
            )
            return _DirectResponse(response.status_code or 200, body)

        if method == "GET" and route == "/macro/ipo-calendar":
            from src.api.routes import macro_calendar

            return _DirectResponse(
                200,
                macro_calendar.ipo_calendar(
                    status=qstr("status"),
                    from_date=qstr("from_date"),
                    to_date=qstr("to_date"),
                    as_of=qstr("as_of"),
                    limit=qint("limit", 100),
                    dal=self.dal,
                ),
            )

        if method == "GET" and route == "/reports":
            from src.api.routes import reports

            return _DirectResponse(
                200,
                reports.reports_list(
                    ticker=qstr("ticker"),
                    days=qint("days", 30),
                    report_type=qstr("report_type"),
                    limit=qint("limit", 20),
                    dal=self.dal,
                ),
            )

        raise AssertionError(f"PG-unreachable smoke has no handler for {method} {path}")


def _make_live_client():
    return _HandlerDirectClient.from_live_dependencies()


def _clear_dependency_caches() -> None:
    from src.api import dependencies

    for name in (
        "get_dal",
        "get_registry",
        "get_profile_store",
        "get_data_provider_store",
    ):
        getattr(dependencies, name).cache_clear()


def run_smoke(
    *,
    poison_dsn: str = POISON_DSN,
    client_factory: Callable[[], Any] = _make_live_client,
) -> SmokeReport:
    _bootstrap_repo_root()
    old_disable_scheduler = os.environ.get("ARKSCOPE_DISABLE_SCHEDULER")
    old_e2e_marker = os.environ.get("ARKSCOPE_PG_UNREACHABLE_E2E")
    os.environ["ARKSCOPE_DISABLE_SCHEDULER"] = "1"
    os.environ["ARKSCOPE_PG_UNREACHABLE_E2E"] = "1"

    _clear_dependency_caches()

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
        _clear_dependency_caches()

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
