"""Collect evidence-first listing and M&A observations from SEC submissions.

The collector only creates review records. It never changes profile_state.db or
removes a ticker from the active universe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
import re
import sqlite3
from pathlib import Path
from typing import Callable, Optional

from src.market_data_admin import resolve_market_db_path
from src.market_data_direct import market_write_lock
from src.security_lifecycle import (
    CorporateRelationship,
    LifecycleObservation,
    SecurityLifecycleStore,
)


_M_AND_A_FORMS = frozenset({"DEFM14A", "DEFA14A"})
_FORM_25 = frozenset({"25", "25-NSE"})
_MERGER_TERMS = re.compile(
    r"\b(?:merger|acquisition|acquired|wholly owned subsidiary)\b", re.IGNORECASE
)
_ENTITY = (
    r"[A-Z][A-Za-z0-9&'’.,()\- ]{0,120}?"
    r"(?:Inc\.|Corporation|Corp\.|LLC|L\.L\.C\.|Ltd\.|Limited|plc|L\.P\.)"
)
_SUBSIDIARY_RE = re.compile(
    rf"(?:the\s+)?Company\s+(?:has\s+)?became\s+(?:an?\s+)?wholly owned "
    rf"subsidiary of\s+(?P<acquirer>{_ENTITY})",
    re.IGNORECASE,
)
_ACQUIRED_BY_RE = re.compile(
    rf"acquisition of\s+(?:the\s+)?Company\s+by\s+(?P<acquirer>{_ENTITY})",
    re.IGNORECASE,
)
_NAMED_SUBSIDIARY_RE = re.compile(
    rf"(?P<target>{_ENTITY})\s+became\s+(?:an?\s+)?wholly owned subsidiary of\s+"
    rf"(?P<acquirer>{_ENTITY})",
    re.IGNORECASE,
)


# A Form 25 strikes one named class of securities, so the issuer's equity is
# only implicated when that class is the equity. Both shapes SEC serves place
# the class immediately before the `(Description of class of securities)`
# caption: the exchange notice rendered through `xslF25X02`, and the
# issuer-filed HTML notice. The raw XML exposes it as a single element instead.
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
# Layout furniture only. Punctuation that can legitimately end a class name,
# such as `.` or `:`, is deliberately left alone.
_FORM25_SEPARATORS = " \t\r\n_—–-*"
_FORM25_EQUITY_TERMS = re.compile(
    r"\b(?:common stock|common shares?|ordinary shares?|capital stock|"
    r"class\s+[A-Z]\s+(?:common|ordinary))\b",
    re.IGNORECASE,
)
_FORM25_OTHER_SECURITY_TERMS = re.compile(
    r"\b(?:notes?|bonds?|debentures?|warrants?|units?|rights?|preferred|"
    r"depositary shares?)\b",
    re.IGNORECASE,
)
# A class description lists the instruments being removed, and each may then be
# described in terms of the equity. Deciding on whether the equity is mentioned
# anywhere is wrong in both directions: it dismisses a genuine common-stock
# removal carrying attached rights, and it flags a warrant or unit removal that
# only names the equity it converts into. So the underlying is dropped first,
# then each listed instrument is judged separately, and equity anywhere keeps
# the notice reportable — a combined listing must not change conclusion just
# because the equity is named second.
_FORM25_UNDERLYING_CONNECTOR = re.compile(
    r"\b(?:to\s+purchase|to\s+receive|to\s+acquire|to\s+subscribe|"
    r"consisting\s+of|representing|evidencing|convertible\s+into|"
    r"exercisable\s+for|entitling|underlying)\b",
    re.IGNORECASE,
)
_FORM25_CLAUSE_BREAK = re.compile(r",|\band\b", re.IGNORECASE)


@dataclass(frozen=True)
class Form25Security:
    """The class of securities a Form 25 removes.

    ``description`` is the verbatim caption text, empty when the filing body was
    unavailable or did not carry one. ``covers_other_security`` is true only on a
    positive non-equity match, so an undetermined filing stays reportable rather
    than being silently dismissed.
    """

    description: str
    covers_other_security: bool


def classify_form25_security(document: Optional[str]) -> Form25Security:
    description = _form25_class_description(document)
    if not description:
        return Form25Security(description="", covers_other_security=False)
    kinds = {
        _form25_instrument_kind(segment)
        for segment in _form25_listed_instruments(description)
    }
    # Equity anywhere among the listed instruments keeps the notice reportable,
    # so a combined listing reaches the same conclusion in either order.
    return Form25Security(
        description=description,
        covers_other_security=("other" in kinds and "equity" not in kinds),
    )


def _form25_listed_instruments(description: str) -> list[str]:
    """Split a class description into the instruments it actually lists.

    Everything from the first underlying connector onwards describes what the
    instrument resolves to rather than what is being removed, and is dropped
    before splitting. What remains is split on clause breaks so each listed
    instrument is judged on its own.
    """
    connector = _FORM25_UNDERLYING_CONNECTOR.search(description)
    head = (description[: connector.start()] if connector else description).strip()
    return [
        segment.strip()
        for segment in _FORM25_CLAUSE_BREAK.split(head or description)
        if segment.strip()
    ]


def _form25_instrument_kind(segment: str) -> str:
    """Return ``equity``, ``other``, or ``""`` for one listed instrument.

    The last instrument term wins because English compounds put the head last:
    `Common Stock Purchase Warrants` is warrants. An unrecognised instrument
    returns empty so the caller keeps reporting it.
    """
    kind = ""
    position = -1
    for candidate, pattern in (
        ("equity", _FORM25_EQUITY_TERMS),
        ("other", _FORM25_OTHER_SECURITY_TERMS),
    ):
        for match in pattern.finditer(segment):
            if match.start() > position:
                kind, position = candidate, match.start()
    return kind


def _form25_class_description(document: Optional[str]) -> str:
    raw = str(document or "")
    if not raw.strip():
        return ""
    tagged = _FORM25_CLASS_TAG.search(raw)
    if tagged is not None:
        return _clean_entity(_plain_text(tagged.group("value")))[:240]
    text = _plain_text(raw)
    caption = _FORM25_CLASS_CAPTION.search(text)
    if caption is None:
        return ""
    preceding = text[: caption.start()]
    # The class sits between the address caption and the class caption. Falling
    # back to the last closing parenthesis keeps older layouts readable.
    address_captions = _FORM25_ADDRESS_CAPTION.findall(preceding)
    if address_captions:
        candidate = preceding.rpartition(address_captions[-1])[2]
    else:
        candidate = preceding.rpartition(")")[2]
    return _clean_entity(candidate.strip(_FORM25_SEPARATORS))[:240]


@dataclass(frozen=True)
class SubmissionEventBatch:
    events: tuple[LifecycleObservation, ...]
    relationships: tuple[CorporateRelationship, ...]


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


def _clean_entity(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \t\r\n,;:")


def _excerpt(text: str, match: re.Match[str], *, radius: int = 180) -> str:
    start = max(match.start() - radius, 0)
    end = min(match.end() + radius, len(text))
    return text[start:end].strip()[:600]


def _relationship_candidate(
    *,
    ticker: str,
    cik: str,
    issuer_name: str,
    source_ref: str,
    evidence_url: str,
    filing_date: str,
    observed_at: str,
    document: str,
) -> Optional[CorporateRelationship]:
    text = _plain_text(document)
    if not _MERGER_TERMS.search(text):
        return None
    match = _SUBSIDIARY_RE.search(text) or _ACQUIRED_BY_RE.search(text)
    target_name = issuer_name
    if match is None:
        named = _NAMED_SUBSIDIARY_RE.search(text)
        if named is None:
            return None
        match = named
        target_name = _clean_entity(named.group("target"))
        # A named target must be the filing issuer; otherwise this filing is not
        # enough to assign target/acquirer roles safely.
        normalized_target = re.sub(r"[^a-z0-9]", "", target_name.casefold())
        normalized_issuer = re.sub(r"[^a-z0-9]", "", issuer_name.casefold())
        if normalized_target != normalized_issuer:
            return None
    acquirer_name = _clean_entity(match.group("acquirer"))
    if not acquirer_name or acquirer_name.casefold() == target_name.casefold():
        return None
    return CorporateRelationship(
        action_type="acquisition",
        target_ticker=ticker,
        target_cik=cik,
        target_name=target_name,
        acquirer_ticker=None,
        acquirer_cik=None,
        acquirer_name=acquirer_name,
        status="candidate",
        effective_date=filing_date,
        source="sec_edgar",
        source_ref=source_ref,
        evidence_url=evidence_url,
        evidence_excerpt=_excerpt(text, match),
        observed_at=observed_at,
    )


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
            {
                item.strip()
                for item in str(value or "").split(",")
                if item.strip()
            }
        )
    )


def parse_submission_events(
    *,
    ticker: str,
    cik: str,
    submissions: dict,
    document_loader: Callable[[str], Optional[str]],
    observed_at: str,
    start_date: str,
) -> SubmissionEventBatch:
    """Convert official filing metadata into review observations.

    Item 3.01 is intentionally a review signal: it also covers listing-rule
    failures and transfers. Form 25 is a pending removal notice, not proof that
    the security is already inactive. M&A relationships remain candidates even
    when the filing text contains an explicit role phrase.
    """
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form") if isinstance(recent, dict) else None
    if not isinstance(forms, list):
        return SubmissionEventBatch(events=(), relationships=())
    issuer_name = str(submissions.get("name") or ticker).strip()[:240]
    events: list[LifecycleObservation] = []
    relationships: list[CorporateRelationship] = []
    for index, raw_form in enumerate(forms):
        form = str(raw_form or "").strip().upper()
        filing_date = str(_recent_value(recent, "filingDate", index)).strip()
        if not filing_date or filing_date < start_date:
            continue
        accession = str(_recent_value(recent, "accessionNumber", index)).strip()
        primary_document = str(_recent_value(recent, "primaryDocument", index)).strip()
        if not accession or not primary_document:
            continue
        description = str(
            _recent_value(recent, "primaryDocDescription", index)
        ).strip()[:1000]
        items = _parse_items(_recent_value(recent, "items", index))
        url = _filing_url(cik, accession, primary_document)

        def add_event(
            event_type: str,
            state: str,
            event_description: str,
            *,
            evidence_suffix: str = "",
        ) -> None:
            text = description or event_description
            if evidence_suffix:
                text = f"{text} {evidence_suffix}".strip()
            events.append(
                LifecycleObservation(
                    ticker=ticker.upper(),
                    cik=cik,
                    issuer_name=issuer_name,
                    event_type=event_type,
                    lifecycle_state=state,
                    filing_date=filing_date,
                    effective_date=filing_date if event_type == "acquisition_completed" else None,
                    source="sec_edgar",
                    source_ref=accession,
                    filing_form=form,
                    filing_items=items,
                    evidence_url=url,
                    description=text,
                    observed_at=observed_at,
                )
            )

        if form in _FORM_25:
            # Reading the body is new network work for this branch. A failure
            # stays local to the filing: `run_incremental` catches per ticker,
            # so raising here would discard the issuer's other events too.
            try:
                form25_document = document_loader(url)
            except Exception:
                form25_document = None
            security = classify_form25_security(form25_document)
            if security.covers_other_security:
                continue
            add_event(
                "listing_removal_notice",
                "pending_delisting",
                "SEC notification of removal from listing or registration.",
                evidence_suffix=(
                    f"Class of securities: {security.description}."
                    if security.description
                    else ""
                ),
            )
            continue

        if form in {"8-K", "8-K/A"} and "3.01" in items:
            add_event(
                "listing_status_review",
                "review_required",
                "SEC Item 3.01 listing status requires review.",
            )

        needs_document = (
            (form in {"8-K", "8-K/A"} and bool({"1.01", "2.01", "5.01"} & set(items)))
            or form in _M_AND_A_FORMS
        )
        if not needs_document:
            continue
        document = document_loader(url)
        text = _plain_text(document or "")
        if not text or not _MERGER_TERMS.search(text):
            continue
        if form in _M_AND_A_FORMS:
            add_event("merger_proxy", "review_required", "SEC merger proxy filing.")
        elif "2.01" in items:
            add_event(
                "acquisition_completed",
                "review_required",
                "SEC Item 2.01 indicates a completed acquisition or disposition; "
                "merger language was observed in the filing.",
            )
        elif "1.01" in items:
            add_event(
                "merger_agreement",
                "review_required",
                "SEC Item 1.01 contains merger or acquisition language.",
            )
        relationship = _relationship_candidate(
            ticker=ticker.upper(),
            cik=cik,
            issuer_name=issuer_name,
            source_ref=accession,
            evidence_url=url,
            filing_date=filing_date,
            observed_at=observed_at,
            document=text,
        )
        if relationship is not None:
            relationships.append(relationship)

    events.sort(key=lambda item: (item.filing_date, item.event_type), reverse=True)
    relationships.sort(
        key=lambda item: (item.effective_date or "", item.target_name, item.acquirer_name),
        reverse=True,
    )
    return SubmissionEventBatch(events=tuple(events), relationships=tuple(relationships))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _default_start_date(observed_at: str) -> str:
    parseable = observed_at[:-1] + "+00:00" if observed_at.endswith("Z") else observed_at
    return (datetime.fromisoformat(parseable).date() - timedelta(days=120)).isoformat()


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
    all_events: list[LifecycleObservation] = []
    all_relationships: list[CorporateRelationship] = []
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
                all_events.extend(batch.events)
                all_relationships.extend(batch.relationships)
            except Exception:
                errors[ticker] = "sec_request_failed"
            finally:
                if progress_cb is not None:
                    progress_cb(index, len(tickers), ticker)
    finally:
        if owns_client:
            client.close()

    if all_events or all_relationships:
        target = db_path or resolve_market_db_path()
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        with market_write_lock():
            conn = sqlite3.connect(target, timeout=10.0)
            try:
                store = SecurityLifecycleStore(conn)
                for event in all_events:
                    store.upsert_observation(event)
                for relationship in all_relationships:
                    store.upsert_relationship(relationship)
            finally:
                conn.close()

    return {
        "status": "partial" if errors else "succeeded",
        "tickers_scanned": len(tickers),
        "events_observed": len(all_events),
        "relationships_observed": len(all_relationships),
        "review_required": sum(
            event.lifecycle_state == "review_required" for event in all_events
        ),
        "errors": errors,
    }
