"""Bounded normalized-news ingestion shared by provider adapters."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional, Protocol

from src.market_data_direct import (
    _ensure_provider_sync_tables,
    _finish_provider_run,
    _start_provider_run,
    _upsert_provider_meta,
)

from .legacy_projection import ProjectionResult, project_article_uncommitted
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
    BodyStatus.UNAVAILABLE,
    BodyStatus.EXPIRED,
}


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _unique_ints(values: Iterable[int]) -> tuple[int, ...]:
    return tuple(dict.fromkeys(int(value) for value in values))


def combine_writer_leg_statuses(retry_status: str, fresh_status: str) -> str:
    if retry_status == "failed" and fresh_status == "failed":
        return "failed"
    if retry_status != "succeeded" or fresh_status != "succeeded":
        return "partial"
    return "succeeded"


def _body_fetch_due(body: BodyCandidate) -> bool:
    if not body.next_retry_at:
        return True
    parseable = (
        body.next_retry_at[:-1] + "+00:00"
        if body.next_retry_at.endswith("Z")
        else body.next_retry_at
    )
    try:
        retry_at = datetime.fromisoformat(parseable)
    except ValueError:
        return True
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    return retry_at <= datetime.now(timezone.utc)


# Raised by src.market_data_direct.market_write_lock on contention timeout.
_MARKET_LOCK_BUSY_MARKER = "market_data.db write lock busy"


def _is_market_lock_busy(exc: BaseException) -> bool:
    """Market-lock contention is batch-fatal and retryable: run_source classifies
    it as skipped_lock_busy, so it must never be swallowed into resumable
    per-article/provider errors (that would surface as a durable partial result
    and misattribute lock waits as ProviderError in worker telemetry)."""
    return _MARKET_LOCK_BUSY_MARKER in str(exc)


def write_news_batch(
    store,
    provider: NewsProvider,
    tickers: Iterable[str],
    budget: WriterBudget,
    *,
    continuation: Optional[WriterContinuation] = None,
    retry_body_ids: Iterable[int] = (),
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    project_legacy: bool = False,
    write_lock_factory: Optional[Callable[[], Any]] = None,
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
    retry_article_ids = _unique_ints(retry_body_ids)
    still_deferred_bodies: list[str] = []
    deferred_tickers: list[str] = []
    errors: dict[str, str] = {}
    retry_errors: dict[str, str] = {}
    articles_seen = 0
    articles_inserted = 0
    bodies_fetched = 0
    legacy_rows_inserted = 0
    legacy_rows_updated = 0
    projection_skipped_no_ticker = 0
    projection_skip_article_ids: set[int] = set()
    body_fetch_attempts = 0
    retry_bodies_attempted = 0
    retry_bodies_fetched = 0
    tickers_scanned = 0

    def write_lock():
        return write_lock_factory() if write_lock_factory is not None else nullcontext()

    def record_projection(result: ProjectionResult, article_id: Optional[int]) -> None:
        nonlocal legacy_rows_inserted
        nonlocal legacy_rows_updated
        nonlocal projection_skipped_no_ticker
        skipped_no_ticker = result.skipped_no_ticker
        if article_id is not None and result.skipped_no_ticker:
            if article_id in projection_skip_article_ids:
                skipped_no_ticker = 0
            else:
                projection_skip_article_ids.add(article_id)
        legacy_rows_inserted += result.inserted
        legacy_rows_updated += result.updated
        projection_skipped_no_ticker += skipped_no_ticker

    def upsert_candidate(candidate: ArticleCandidate):
        if not project_legacy:
            with write_lock():
                return store.upsert(candidate)

        projection = ProjectionResult()
        with write_lock():
            store.conn.execute("BEGIN IMMEDIATE")
            try:
                upsert = store.upsert_uncommitted(candidate)
                if upsert.article_id is not None and not upsert.quarantined:
                    projection = project_article_uncommitted(store.conn, upsert.article_id)
                store.conn.commit()
            except Exception:
                store.conn.rollback()
                raise
        record_projection(projection, upsert.article_id)
        return upsert

    def update_body(candidate: ArticleCandidate, body: BodyCandidate) -> None:
        if not project_legacy:
            with write_lock():
                store.update_body(candidate, body)
            return

        projection = ProjectionResult()
        article_id: Optional[int] = None
        with write_lock():
            store.conn.execute("BEGIN IMMEDIATE")
            try:
                article_id = store.update_body_uncommitted(candidate, body)
                projection = project_article_uncommitted(store.conn, article_id)
                store.conn.commit()
            except Exception:
                store.conn.rollback()
                raise
        record_projection(projection, article_id)

    def record_resumed_body_error(
        article: ArticleCandidate, error: str
    ) -> None:
        ticker = article.primary_ticker or next(iter(article.related_tickers), None)
        if ticker:
            with write_lock():
                _upsert_provider_meta(
                    store.conn,
                    provider=source,
                    ticker=ticker,
                    interval="news",
                    last_bar_datetime=article.published_at,
                    rows_added=0,
                    error=error,
                )

    with write_lock():
        _ensure_provider_sync_tables(store.conn)
        run_id = _start_provider_run(
            store.conn, provider=source, interval="news", domain="news"
        )
    operation = getattr(provider, "operation", nullcontext)
    try:
        with operation():
            for article_id in retry_article_ids:
                restored = store.candidate_by_article_id(article_id)
                if restored is None or restored.source.strip().casefold() != source:
                    retry_errors[f"retry:{article_id}"] = (
                        "retry article is missing from normalized store"
                    )
                    continue
                if restored.body.status in _TERMINAL_BODY_STATUSES:
                    continue
                if not _body_fetch_due(restored.body):
                    continue
                retry_bodies_attempted += 1
                try:
                    body = provider.fetch_body(restored)
                    update_body(restored, body)
                    if body.status is BodyStatus.FETCHED:
                        bodies_fetched += 1
                        retry_bodies_fetched += 1
                    elif body.status is BodyStatus.FAILED:
                        retry_errors[f"retry:{article_id}"] = (
                            body.error or "body fetch failed"
                        )
                except Exception as exc:  # provider failure remains retryable
                    if _is_market_lock_busy(exc):
                        raise
                    update_body(
                        restored,
                        BodyCandidate(status=BodyStatus.FAILED, error=str(exc)),
                    )
                    retry_errors[f"retry:{article_id}"] = str(exc)

            for provider_id in deferred_body_ids:
                restored = store.candidate_by_provider_id(source, provider_id)
                if restored is None:
                    errors[f"body:{provider_id}"] = (
                        "deferred article is missing from normalized store"
                    )
                    continue
                if restored.body.status in _TERMINAL_BODY_STATUSES:
                    continue
                if not _body_fetch_due(restored.body):
                    still_deferred_bodies.append(provider_id)
                    continue
                if body_fetch_attempts >= budget.max_body_fetches:
                    still_deferred_bodies.append(provider_id)
                    continue
                body_fetch_attempts += 1
                try:
                    body = provider.fetch_body(restored)
                    update_body(restored, body)
                    if body.status is BodyStatus.FETCHED:
                        bodies_fetched += 1
                    elif body.status is BodyStatus.FAILED:
                        persisted = store.candidate_by_provider_id(source, provider_id)
                        if (
                            persisted is not None
                            and persisted.body.status not in _TERMINAL_BODY_STATUSES
                        ):
                            still_deferred_bodies.append(provider_id)
                        error = body.error or "body fetch failed"
                        errors[f"body:{provider_id}"] = error
                        record_resumed_body_error(restored, error)
                except Exception as exc:  # provider failure remains resumable
                    if _is_market_lock_busy(exc):
                        raise
                    update_body(
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
                        try:
                            upsert = upsert_candidate(
                                candidate
                                if incoming_body.status is not BodyStatus.PENDING
                                else pending
                            )
                        except Exception as exc:
                            if not project_legacy or _is_market_lock_busy(exc):
                                raise
                            key = candidate.provider_article_id or f"ticker:{ticker}"
                            errors[key] = str(exc)
                            ticker_error = str(exc)
                            continue
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
                        if not _body_fetch_due(restored.body):
                            still_deferred_bodies.append(provider_id)
                            continue
                        if body_fetch_attempts >= budget.max_body_fetches:
                            still_deferred_bodies.append(provider_id)
                            continue
                        body_fetch_attempts += 1
                        try:
                            body = provider.fetch_body(restored)
                            update_body(restored, body)
                            if body.status is BodyStatus.FETCHED:
                                bodies_fetched += 1
                            elif body.status is BodyStatus.FAILED:
                                persisted = store.candidate_by_provider_id(
                                    source, provider_id
                                )
                                if (
                                    persisted is not None
                                    and persisted.body.status
                                    not in _TERMINAL_BODY_STATUSES
                                ):
                                    still_deferred_bodies.append(provider_id)
                                ticker_error = body.error or "body fetch failed"
                                errors[f"body:{provider_id}"] = ticker_error
                        except Exception as exc:  # metadata remains durable
                            if _is_market_lock_busy(exc):
                                raise
                            update_body(
                                restored,
                                BodyCandidate(status=BodyStatus.FAILED, error=str(exc)),
                            )
                            errors[f"body:{provider_id}"] = str(exc)
                            ticker_error = str(exc)
                            still_deferred_bodies.append(provider_id)

                    newest = store.latest_cursor(source, ticker)
                    with write_lock():
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
                    if _is_market_lock_busy(exc):
                        raise
                    errors[ticker] = str(exc)
                    with write_lock():
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
        with write_lock():
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

    with write_lock():
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
    retry_status = "partial" if retry_errors else "succeeded"
    fresh_status = "partial" if continuation_out is not None or errors else "succeeded"
    status = combine_writer_leg_statuses(retry_status, fresh_status)
    return WriterResult(
        status=status,
        articles_seen=articles_seen,
        articles_inserted=articles_inserted,
        bodies_fetched=bodies_fetched,
        errors={**retry_errors, **errors},
        continuation=continuation_out,
        legacy_rows_inserted=legacy_rows_inserted,
        legacy_rows_updated=legacy_rows_updated,
        projection_skipped_no_ticker=projection_skipped_no_ticker,
        retry_status=retry_status,
        fresh_status=fresh_status,
        retry_bodies_attempted=retry_bodies_attempted,
        retry_bodies_fetched=retry_bodies_fetched,
        tickers_scanned=tickers_scanned,
    )
