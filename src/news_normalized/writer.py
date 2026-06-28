"""Bounded normalized-news ingestion shared by provider adapters."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from typing import Callable, Iterable, Optional, Protocol

from src.market_data_direct import (
    _ensure_provider_sync_tables,
    _finish_provider_run,
    _start_provider_run,
    _upsert_provider_meta,
)

from .models import (
    ArticleCandidate,
    BodyCandidate,
    BodyStatus,
    WriterBudget,
    WriterContinuation,
    WriterResult,
)


class NewsProvider(Protocol):
    source: str

    def operation(self):
        return nullcontext()

    def fetch_articles(
        self, ticker: str, since_iso: Optional[str]
    ) -> Iterable[ArticleCandidate]: ...

    def fetch_body(self, candidate: ArticleCandidate) -> BodyCandidate: ...


_TERMINAL_BODY_STATUSES = {
    BodyStatus.FETCHED,
    BodyStatus.EMPTY,
    BodyStatus.EXPIRED,
}


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def write_news_batch(
    store,
    provider: NewsProvider,
    tickers: Iterable[str],
    budget: WriterBudget,
    *,
    continuation: Optional[WriterContinuation] = None,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> WriterResult:
    """Persist metadata first, then spend bounded provider calls on article bodies."""
    source = provider.source.strip().casefold()
    requested_tickers = _unique(str(ticker).strip().upper() for ticker in tickers)
    work_tickers = (
        continuation.deferred_tickers if continuation is not None else requested_tickers
    )
    deferred_body_ids = list(
        continuation.deferred_body_ids if continuation is not None else ()
    )
    still_deferred_bodies: list[str] = []
    deferred_tickers: list[str] = []
    errors: dict[str, str] = {}
    articles_seen = 0
    articles_inserted = 0
    bodies_fetched = 0
    body_fetch_attempts = 0
    tickers_scanned = 0

    def record_resumed_body_error(
        article: ArticleCandidate, error: str
    ) -> None:
        ticker = article.primary_ticker or next(iter(article.related_tickers), None)
        if ticker:
            _upsert_provider_meta(
                store.conn,
                provider=source,
                ticker=ticker,
                interval="news",
                last_bar_datetime=article.published_at,
                rows_added=0,
                error=error,
            )

    _ensure_provider_sync_tables(store.conn)
    run_id = _start_provider_run(
        store.conn, provider=source, interval="news", domain="news"
    )
    operation = getattr(provider, "operation", nullcontext)
    try:
        with operation():
            for provider_id in deferred_body_ids:
                restored = store.candidate_by_provider_id(source, provider_id)
                if restored is None:
                    errors[f"body:{provider_id}"] = (
                        "deferred article is missing from normalized store"
                    )
                    continue
                if restored.body.status in _TERMINAL_BODY_STATUSES:
                    continue
                if body_fetch_attempts >= budget.max_body_fetches:
                    still_deferred_bodies.append(provider_id)
                    continue
                body_fetch_attempts += 1
                try:
                    body = provider.fetch_body(restored)
                    store.update_body(restored, body)
                    if body.status is BodyStatus.FETCHED:
                        bodies_fetched += 1
                    elif body.status is BodyStatus.FAILED:
                        still_deferred_bodies.append(provider_id)
                        error = body.error or "body fetch failed"
                        errors[f"body:{provider_id}"] = error
                        record_resumed_body_error(restored, error)
                except Exception as exc:  # provider failure remains resumable
                    store.update_body(
                        restored,
                        BodyCandidate(status=BodyStatus.FAILED, error=str(exc)),
                    )
                    errors[f"body:{provider_id}"] = str(exc)
                    record_resumed_body_error(restored, str(exc))
                    still_deferred_bodies.append(provider_id)

            total = len(work_tickers)
            for ticker_index, ticker in enumerate(work_tickers):
                if articles_seen >= budget.max_articles:
                    deferred_tickers.extend(work_tickers[ticker_index:])
                    break
                tickers_scanned += 1
                inserted_for_ticker = 0
                budget_hit = False
                ticker_error: Optional[str] = None
                try:
                    since = store.latest_cursor(source, ticker)
                    candidates = provider.fetch_articles(ticker, since)
                    for candidate in candidates:
                        if articles_seen >= budget.max_articles:
                            deferred_tickers.extend(work_tickers[ticker_index:])
                            budget_hit = True
                            break
                        articles_seen += 1
                        incoming_body = candidate.body
                        pending = replace(candidate, body=BodyCandidate())
                        upsert = store.upsert(
                            candidate
                            if incoming_body.status is not BodyStatus.PENDING
                            else pending
                        )
                        if upsert.quarantined:
                            key = candidate.provider_article_id or f"ticker:{ticker}"
                            errors[key] = "article identity conflict quarantined"
                            continue
                        inserted_for_ticker += int(upsert.inserted)
                        articles_inserted += int(upsert.inserted)

                        provider_id = candidate.provider_article_id
                        if incoming_body.status is not BodyStatus.PENDING:
                            if incoming_body.status is BodyStatus.FAILED:
                                ticker_error = incoming_body.error or "body fetch failed"
                                errors[f"body:{provider_id or ticker}"] = ticker_error
                            continue
                        if not provider_id:
                            continue
                        restored = store.candidate_by_provider_id(source, provider_id)
                        if restored is None:
                            errors[f"body:{provider_id}"] = (
                                "article is missing after metadata upsert"
                            )
                            continue
                        if restored.body.status in _TERMINAL_BODY_STATUSES:
                            continue
                        if body_fetch_attempts >= budget.max_body_fetches:
                            still_deferred_bodies.append(provider_id)
                            continue
                        body_fetch_attempts += 1
                        try:
                            body = provider.fetch_body(restored)
                            store.update_body(restored, body)
                            if body.status is BodyStatus.FETCHED:
                                bodies_fetched += 1
                            elif body.status is BodyStatus.FAILED:
                                still_deferred_bodies.append(provider_id)
                                ticker_error = body.error or "body fetch failed"
                                errors[f"body:{provider_id}"] = ticker_error
                        except Exception as exc:  # metadata remains durable
                            store.update_body(
                                restored,
                                BodyCandidate(status=BodyStatus.FAILED, error=str(exc)),
                            )
                            errors[f"body:{provider_id}"] = str(exc)
                            ticker_error = str(exc)
                            still_deferred_bodies.append(provider_id)

                    newest = store.latest_cursor(source, ticker)
                    _upsert_provider_meta(
                        store.conn,
                        provider=source,
                        ticker=ticker,
                        interval="news",
                        last_bar_datetime=newest,
                        rows_added=inserted_for_ticker,
                        error=ticker_error,
                    )
                    if not budget_hit and progress_cb:
                        progress_cb(ticker_index + 1, total, ticker)
                except Exception as exc:  # one ticker must not abort the batch
                    errors[ticker] = str(exc)
                    _upsert_provider_meta(
                        store.conn,
                        provider=source,
                        ticker=ticker,
                        interval="news",
                        last_bar_datetime=None,
                        rows_added=inserted_for_ticker,
                        error=str(exc),
                    )
                if budget_hit:
                    break
    except Exception as exc:
        _finish_provider_run(
            store.conn,
            run_id,
            status="failed",
            tickers_scanned=tickers_scanned,
            gaps_found=0,
            rows_added=articles_inserted,
            error=str(exc),
        )
        raise

    _finish_provider_run(
        store.conn,
        run_id,
        status="succeeded",
        tickers_scanned=tickers_scanned,
        gaps_found=0,
        rows_added=articles_inserted,
        error=None,
    )
    continuation_out = None
    if deferred_tickers or still_deferred_bodies:
        continuation_out = WriterContinuation(
            deferred_tickers=_unique(deferred_tickers),
            deferred_body_ids=_unique(still_deferred_bodies),
        )
    status = "partial" if continuation_out is not None or errors else "succeeded"
    return WriterResult(
        status=status,
        articles_seen=articles_seen,
        articles_inserted=articles_inserted,
        bodies_fetched=bodies_fetched,
        errors=errors,
        continuation=continuation_out,
    )
