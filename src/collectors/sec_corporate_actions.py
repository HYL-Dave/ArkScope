"""Collect provider observations for SEC listing and corporate-action filings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import sqlite3
from typing import Callable, Optional

from src.market_data_admin import resolve_market_db_path
from src.market_data_direct import market_write_lock
from src.security_lifecycle import (
    LifecycleObservation,
    ObservationKind,
    SecurityLifecycleStore,
)


_M_AND_A_FORMS = frozenset({"DEFM14A", "DEFA14A"})
_FORM_25 = frozenset({"25", "25-NSE"})
_MERGER_TERMS = re.compile(
    r"\b(?:merger|acquisition|acquired|wholly owned subsidiary)\b", re.IGNORECASE
)
_FORM25_CLASS_TAG = re.compile(
    r"<descriptionClassSecurity>(?P<value>.*?)</descriptionClassSecurity>",
    re.IGNORECASE | re.DOTALL,
)
_FORM25_CLASS_CAPTION = re.compile(
    r"\(\s*Description of class of securities\s*\)", re.IGNORECASE
)
_FORM25_ADDRESS_CAPTION = re.compile(
    r"principal executive offices\s*\)", re.IGNORECASE
)
_FORM25_SEPARATORS = " \t\r\n_—–-*"
_DESCRIPTION_LIMIT = 1000


@dataclass(frozen=True)
class SubmissionObservationBatch:
    observations: tuple[LifecycleObservation, ...]


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._suppressed = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.casefold() in {"script", "style"}:
            self._suppressed += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style"} and self._suppressed:
            self._suppressed -= 1

    def handle_data(self, data: str) -> None:
        if not self._suppressed:
            self.parts.append(data)


def _plain_text(document: str) -> str:
    parser = _VisibleText()
    try:
        parser.feed(str(document or ""))
        value = " ".join(parser.parts)
    except Exception:
        value = str(document or "")
    return re.sub(r"\s+", " ", value).strip()


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \t\r\n,;:")


def _form25_class_description(document: Optional[str]) -> str:
    raw = str(document or "")
    if not raw.strip():
        return ""
    tagged = _FORM25_CLASS_TAG.search(raw)
    if tagged is not None:
        return _clean_text(_plain_text(tagged.group("value")))
    text = _plain_text(raw)
    caption = _FORM25_CLASS_CAPTION.search(text)
    if caption is None:
        return ""
    preceding = text[: caption.start()]
    address_captions = _FORM25_ADDRESS_CAPTION.findall(preceding)
    if address_captions:
        candidate = preceding.rpartition(address_captions[-1])[2]
    else:
        candidate = preceding.rpartition(")")[2]
    return _clean_text(candidate.strip(_FORM25_SEPARATORS))


def _recent_value(recent: dict, field: str, index: int, default=""):
    values = recent.get(field)
    if not isinstance(values, list) or index >= len(values):
        return default
    return values[index]


def _filing_url(cik: str, accession: str, primary_document: str) -> str:
    accession_path = accession.replace("-", "")
    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{cik.lstrip('0')}/{accession_path}/{primary_document}"
    )


def _parse_items(value: object) -> tuple[str, ...]:
    return tuple(
        sorted(
            {item.strip() for item in str(value or "").split(",") if item.strip()}
        )
    )


def _bounded_description(*parts: str) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())[
        :_DESCRIPTION_LIMIT
    ]


def _load_document(
    loader: Callable[[str], Optional[str]], url: str
) -> Optional[str]:
    try:
        return loader(url)
    except Exception:
        return None


def _open_migration_guard() -> sqlite3.Connection | None:
    profile_path = Path(
        os.environ.get("ARKSCOPE_PROFILE_DB")
        or Path(__file__).resolve().parents[2] / "data" / "profile_state.db"
    )
    if not profile_path.is_file():
        return None
    conn = sqlite3.connect(f"file:{profile_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def parse_submission_events(
    *,
    ticker: str,
    cik: str,
    submissions: dict,
    document_loader: Callable[[str], Optional[str]],
    observed_at: str,
    start_date: str,
) -> SubmissionObservationBatch:
    """Convert each relevant filing into one observation with many kinds."""
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form") if isinstance(recent, dict) else None
    if not isinstance(forms, list):
        return SubmissionObservationBatch(observations=())
    issuer_name = str(submissions.get("name") or ticker).strip()[:240]
    observations: list[LifecycleObservation] = []

    for index, raw_form in enumerate(forms):
        form = str(raw_form or "").strip().upper()
        filing_date = str(_recent_value(recent, "filingDate", index)).strip()
        if not filing_date or filing_date < start_date:
            continue
        accession = str(_recent_value(recent, "accessionNumber", index)).strip()
        primary_document = str(
            _recent_value(recent, "primaryDocument", index)
        ).strip()
        if not accession or not primary_document:
            continue
        source_description = str(
            _recent_value(recent, "primaryDocDescription", index)
        ).strip()
        items = _parse_items(_recent_value(recent, "items", index))
        url = _filing_url(cik, accession, primary_document)
        kinds: dict[str, Optional[str]] = {}
        description = source_description

        if form in _FORM_25:
            class_description = _form25_class_description(
                _load_document(document_loader, url)
            )
            description = _bounded_description(
                source_description
                or "SEC notification of removal from listing or registration.",
                f"Class of securities: {class_description}."
                if class_description
                else "",
            )
            kinds["listing_removal_notice"] = None
        else:
            if form in {"8-K", "8-K/A"} and "3.01" in items:
                kinds["listing_status_review"] = None

            needs_document = (
                form in _M_AND_A_FORMS
                or (
                    form in {"8-K", "8-K/A"}
                    and bool({"1.01", "2.01", "5.01"} & set(items))
                )
            )
            document_text = ""
            if needs_document:
                document_text = _plain_text(
                    _load_document(document_loader, url) or ""
                )
            if form in _M_AND_A_FORMS and _MERGER_TERMS.search(document_text):
                kinds["merger_proxy"] = None
            if form in {"8-K", "8-K/A"} and "2.01" in items and document_text:
                kinds["acquisition_completed"] = filing_date
            elif (
                form in {"8-K", "8-K/A"}
                and "1.01" in items
                and _MERGER_TERMS.search(document_text)
            ):
                kinds["merger_agreement"] = None
            if document_text and (
                "acquisition_completed" in kinds
                or "merger_agreement" in kinds
                or "merger_proxy" in kinds
            ):
                description = _bounded_description(
                    source_description or form, document_text
                )

        if not kinds:
            continue
        observations.append(
            LifecycleObservation(
                ticker=ticker.upper(),
                cik=cik,
                issuer_name=issuer_name,
                filing_date=filing_date,
                source="sec_edgar",
                source_ref=accession,
                filing_form=form,
                filing_items=items,
                evidence_url=url,
                description=_bounded_description(description),
                observed_at=observed_at,
                kinds=tuple(
                    ObservationKind(event_type, effective_date)
                    for event_type, effective_date in sorted(kinds.items())
                ),
            )
        )

    observations.sort(
        key=lambda item: (item.filing_date, item.source_ref, item.ticker), reverse=True
    )
    return SubmissionObservationBatch(observations=tuple(observations))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _default_start_date(observed_at: str) -> str:
    parseable = observed_at[:-1] + "+00:00" if observed_at.endswith("Z") else observed_at
    return (
        datetime.fromisoformat(parseable).date() - timedelta(days=120)
    ).isoformat()


def run_incremental(
    *,
    tickers_arg: Optional[str] = None,
    progress_cb=None,
    client=None,
    db_path: Optional[str] = None,
    observed_at: Optional[str] = None,
    start_date: Optional[str] = None,
) -> dict:
    tickers = tuple(
        dict.fromkeys(
            ticker.strip().upper()
            for ticker in str(tickers_arg or "").split(",")
            if ticker.strip()
        )
    )
    if not tickers:
        raise ValueError("ticker_scope_required")
    owns_client = client is None
    if owns_client:
        from data_sources.sec_edgar_source import SECEdgarDataSource

        client = SECEdgarDataSource()
    observed_at = observed_at or _utc_now()
    start_date = start_date or _default_start_date(observed_at)
    all_observations: list[LifecycleObservation] = []
    errors: dict[str, str] = {}
    try:
        for index, ticker in enumerate(tickers, start=1):
            try:
                cik = client.get_cik(ticker)
                if not cik:
                    errors[ticker] = "cik_unavailable"
                    continue
                submissions = client.fetch_submissions(cik)
                if not isinstance(submissions, dict):
                    errors[ticker] = "submissions_unavailable"
                    continue
                batch = parse_submission_events(
                    ticker=ticker,
                    cik=str(cik).zfill(10),
                    submissions=submissions,
                    document_loader=lambda url: client.fetch_filing_document_text(
                        url, max_bytes=1_048_576
                    ),
                    observed_at=observed_at,
                    start_date=start_date,
                )
                all_observations.extend(batch.observations)
            except Exception:
                errors[ticker] = "sec_request_failed"
            finally:
                if progress_cb is not None:
                    progress_cb(index, len(tickers), ticker)
    finally:
        if owns_client:
            client.close()

    if all_observations:
        target = db_path or resolve_market_db_path()
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        with market_write_lock():
            conn = sqlite3.connect(target, timeout=10.0)
            migration_guard = None
            try:
                migration_guard = _open_migration_guard()
                store = SecurityLifecycleStore(conn, migration_conn=migration_guard)
                for observation in all_observations:
                    store.upsert_observation(observation)
            finally:
                if migration_guard is not None:
                    migration_guard.close()
                conn.close()

    return {
        "status": "partial" if errors else "succeeded",
        "tickers_scanned": len(tickers),
        "observations_observed": len(all_observations),
        "kinds_observed": sum(
            len(observation.kinds) for observation in all_observations
        ),
        "errors": errors,
    }
