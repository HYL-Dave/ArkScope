"""Bounded SEC filing-chain acquisition and deterministic cited facts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from typing import Any, Iterable, Mapping, Sequence

from data_sources.sec_transport import (
    SecRequestBudget,
    SecTransportFailure,
)
from src.security_lifecycle_fact_kernel import normalize_automation_fact_value


_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")
_CIK = re.compile(r"^\d{10}$")
_ACCESSION = re.compile(r"^[A-Za-z0-9.\-]{1,160}$")
_IDENTITY_FORMS = frozenset({"25", "25-NSE", "8-A12B", "8-K12B"})
_M_AND_A_FORMS = frozenset({"DEFM14A", "DEFA14A"})
_MAX_EXCERPT_BYTES = 4096
_RULE_VERSION = "3"
_SOURCE_DEADLINE_RULE_ID = "sec.explicit_transaction_termination_date"
_SOURCE_DEADLINE_RULE_VERSION = "4"
_MONTH_NAME = (
    r"(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)"
)
_MONTH_DATE_TEXT = rf"{_MONTH_NAME}\s+\d{{1,2}},\s+\d{{4}}"
_EFFECTIVE_MONTH_DATE = re.compile(
    rf"\beffective(?:\s+(?:as of|on))?\s+(?P<date>{_MONTH_DATE_TEXT})\b",
    re.IGNORECASE,
)
_EFFECTIVE_ISO_DATE = re.compile(
    r"\beffective(?:\s+(?:as of|on))?\s+(?P<date>\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)
_TRADING_BEGIN_DATE = re.compile(
    rf"\btrading will begin\b.{{0,160}}?\bon\s+"
    rf"(?P<date>{_MONTH_DATE_TEXT})\b",
    re.IGNORECASE,
)
_SOURCE_DEADLINE_PHRASE = re.compile(
    r"\b(?:outside date|termination date|may be terminated if)\b",
    re.IGNORECASE,
)
_ANY_MONTH_DATE = re.compile(rf"\b(?P<date>{_MONTH_DATE_TEXT})\b", re.IGNORECASE)
_ANY_ISO_DATE = re.compile(r"\b(?P<date>\d{4}-\d{2}-\d{2})\b")
_SOURCE_DATE_TEXT = rf"(?:{_MONTH_DATE_TEXT}|\d{{4}}-\d{{2}}-\d{{2}})"
_TERMINATE_IF_BY = re.compile(
    rf"\bmay be terminated if\b[^.]{{0,480}}?\bby\s+"
    rf"(?P<date>{_SOURCE_DATE_TEXT})\b",
    re.IGNORECASE,
)
_CURRENT_DEADLINE = re.compile(
    rf"\b(?:outside|termination) date\s+(?:is|shall be|remains)\s+"
    rf"(?P<date>{_SOURCE_DATE_TEXT})\b",
    re.IGNORECASE,
)
_EXTENDED_DEADLINE = re.compile(
    rf"\b(?:outside|termination) date\s+(?:has been|was)\s+extended"
    rf"(?:\s+from\s+(?P<supersedes_date>{_SOURCE_DATE_TEXT}))?\s+to\s+"
    rf"(?P<date>{_SOURCE_DATE_TEXT})\b",
    re.IGNORECASE,
)
_COORDINATE_TARGET = re.compile(
    rf"\A\s*(?:,\s*)?(?:or|and)\s+{_SOURCE_DATE_TEXT}\b",
    re.IGNORECASE,
)
_EXTENSION_ACTION = re.compile(
    rf"\bextended\b(?:\s+from\s+{_SOURCE_DATE_TEXT})?\s+to\s+"
    rf"{_SOURCE_DATE_TEXT}\b",
    re.IGNORECASE,
)
_NEW_REPLACING = re.compile(
    r"\bnew ticker symbol\s+(?P<new>[A-Z][A-Z0-9.\-]{0,19})\s*,?\s*"
    r"replacing\s+(?P<old>[A-Z][A-Z0-9.\-]{0,19})\b",
    re.IGNORECASE,
)
_CONTINUES_TICKER = re.compile(
    r"\bcontinue(?:s)? to trade under (?:(?:its|the) current|the)?\s*"
    r"ticker symbol\s*,?\s*[\u201c\"']?"
    r"(?P<ticker>[A-Z][A-Z0-9.\-]{0,19})[\u201d\"']?\b",
    re.IGNORECASE,
)
_POSTFIX_TICKER = re.compile(
    r"\bunder\s+(?:the\s+)?[\u201c\"']"
    r"(?P<ticker>[A-Z][A-Z0-9.\-]{0,19})[\u201d\"']\s+ticker symbol\b",
    re.IGNORECASE,
)
_REGISTERED_COMMON_SECURITY = re.compile(
    r"(?i:\bcommon (?:stock|shares)\b).{0,240}?\b"
    r"(?P<ticker>[A-Z][A-Z0-9.\-]{0,19})\b\s+"
    r"(?i:(?:New York Stock Exchange|NASDAQ Global Market|"
    r"Nasdaq Global Select Market|Nasdaq Capital Market|Nasdaq Stock Market))"
)
_UNCHANGED_COMMON_STOCK = re.compile(
    r"\b(?P<ticker>[A-Z][A-Z0-9.\-]{0,19}) common stock (?:is|are) unchanged\b",
    re.IGNORECASE,
)
_TERMINAL_DELISTING = re.compile(
    r"\b(?P<ticker>[A-Z][A-Z0-9.\-]{0,19})\s+common stock\b.*?"
    r"\b(?:removed|withdrawn|delisted)\s+from\s+(?:listing|quotation)\b",
    re.IGNORECASE,
)
_CIK_IN_TEXT = re.compile(r"\bCIK\s+(?P<cik>\d{1,10})\b", re.IGNORECASE)
_ASSET_PURCHASE = re.compile(
    r"\b(?:asset acquisition|asset purchase agreement|"
    r"agreement to acquire certain assets)\b",
    re.IGNORECASE,
)
_ASSET_COUNTERPARTY = re.compile(
    r"\bagreement to acquire certain assets of\s+"
    r"(?P<name>[A-Z][A-Za-z0-9&.' \-]{1,120}?)(?=,\s+(?:a|an)\b)"
)
_CORPORATE_UNIFICATION = re.compile(
    r"\b(?:corporate unification|completed the unification of "
    r"(?:their )?dual listed company structure)\b",
    re.IGNORECASE,
)
_SAME_NUMBER_COMMON_SHARES = re.compile(
    r"\brepresent the same number of common shares\b",
    re.IGNORECASE,
)
_VENUES = (
    (re.compile(r"\bNew York Stock Exchange\b", re.IGNORECASE), "NYSE"),
    (re.compile(r"\bNYSE\b", re.IGNORECASE), "NYSE"),
    (re.compile(r"\bNasdaq Global Select Market\b", re.IGNORECASE), "NASDAQ"),
    (re.compile(r"\bNasdaq Capital Market\b", re.IGNORECASE), "NASDAQ"),
    (re.compile(r"\bNasdaq(?: Stock Market)?\b", re.IGNORECASE), "NASDAQ"),
)


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._suppressed = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        del attrs
        if tag.casefold() in {"script", "style"}:
            self._suppressed += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style"} and self._suppressed:
            self._suppressed -= 1

    def handle_data(self, data: str) -> None:
        if not self._suppressed:
            self.parts.append(data)


@dataclass(frozen=True)
class IdentityContext:
    case_id: str
    cik: str
    issuer_name: str
    current_ticker: str
    ticker_aliases: tuple[str, ...]
    ibkr_conids: tuple[int, ...]
    filing_date: str
    accession: str
    filing_form: str
    filing_items: tuple[str, ...]
    event_kinds: tuple[str, ...]
    primary_start: str
    primary_end: str
    widened_start: str
    widened_end: str


@dataclass(frozen=True)
class FilingRecord:
    cik: str
    form: str
    filing_date: str
    accession: str
    primary_document: str
    description: str
    items: tuple[str, ...]
    source_url: str


@dataclass(frozen=True)
class FilingChainSelection:
    filings: tuple[FilingRecord, ...]
    window: str
    widen_count: int
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class SecEvidence:
    evidence_id: str
    source_family: str
    adapter: str
    kind: str
    source_url: str
    title: str
    publisher: str
    source_published_at: str
    retrieved_at: str
    excerpt: str
    content_sha256: str
    document_sha256: str
    source_locator: Mapping[str, Any]


@dataclass(frozen=True)
class SecFact:
    fact_type: str
    value: Any
    evidence_id: str
    span_start_byte: int
    span_end_byte: int
    cited_text: str
    cited_text_sha256: str
    rule_id: str
    rule_version: str


@dataclass(frozen=True)
class SecSourceDeadline:
    date: str
    evidence_id: str
    span_start_byte: int
    span_end_byte: int
    cited_text: str
    cited_text_sha256: str
    rule_id: str
    rule_version: str
    kind: str = "current"
    supersedes_date: str | None = None


@dataclass(frozen=True)
class SecEvidenceResult:
    context: IdentityContext
    selection: FilingChainSelection
    evidence: tuple[SecEvidence, ...]
    facts: tuple[SecFact, ...]
    conflicts: Mapping[str, tuple[str, ...]]
    blockers: tuple[str, ...]
    symbol_transitions: tuple[tuple[str, str], ...]
    source_deadlines: tuple[SecSourceDeadline, ...]
    diagnostics: Mapping[str, int]


def _required_text(name: str, value: object, *, limit: int) -> str:
    result = str(value or "").strip()
    if not result or len(result) > limit or "\0" in result:
        raise ValueError(name)
    return result


def _normalized_ticker(value: object) -> str:
    result = str(value or "").strip().upper()
    if not _TICKER.fullmatch(result):
        raise ValueError("ticker")
    return result


def _normalized_cik(value: object) -> str:
    result = str(value or "").strip().zfill(10)
    if not _CIK.fullmatch(result):
        raise ValueError("cik")
    return result


def _normalized_date(name: str, value: object) -> str:
    result = str(value or "").strip()
    try:
        parsed = date.fromisoformat(result)
    except ValueError as exc:
        raise ValueError(name) from exc
    if parsed.isoformat() != result:
        raise ValueError(name)
    return result


def _timestamp(value: object) -> str:
    result = _required_text("retrieved_at", value, limit=40)
    parsed_value = result[:-1] + "+00:00" if result.endswith("Z") else result
    try:
        parsed = datetime.fromisoformat(parsed_value)
    except ValueError as exc:
        raise ValueError("retrieved_at") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("retrieved_at")
    return result


def build_identity_context(
    *,
    case_id: str,
    observation: Mapping[str, Any],
    ticker_aliases: Iterable[str] = (),
    ibkr_conids: Iterable[int] = (),
) -> IdentityContext:
    filing_date = _normalized_date("filing_date", observation.get("filing_date"))
    anchor = date.fromisoformat(filing_date)
    current_ticker = _normalized_ticker(observation.get("ticker"))
    aliases = tuple(
        sorted({_normalized_ticker(value) for value in (*ticker_aliases, current_ticker)})
    )
    conids = tuple(sorted({int(value) for value in ibkr_conids}))
    if any(value <= 0 for value in conids):
        raise ValueError("ibkr_conids")
    accession = _required_text("accession", observation.get("source_ref"), limit=160)
    if not _ACCESSION.fullmatch(accession):
        raise ValueError("accession")
    items = tuple(
        sorted(
            {
                _required_text("filing_item", item, limit=20)
                for item in observation.get("filing_items", ())
            }
        )
    )
    kinds = tuple(
        sorted(
            {
                _required_text("event_kind", kind, limit=64)
                for kind in observation.get("event_kinds", ())
            }
        )
    )
    return IdentityContext(
        case_id=_required_text("case_id", case_id, limit=160),
        cik=_normalized_cik(observation.get("cik")),
        issuer_name=_required_text(
            "issuer_name", observation.get("issuer_name"), limit=240
        ),
        current_ticker=current_ticker,
        ticker_aliases=aliases,
        ibkr_conids=conids,
        filing_date=filing_date,
        accession=accession,
        filing_form=_required_text(
            "filing_form", observation.get("filing_form"), limit=30
        ).upper(),
        filing_items=items,
        event_kinds=kinds,
        primary_start=(anchor - timedelta(days=30)).isoformat(),
        primary_end=(anchor + timedelta(days=45)).isoformat(),
        widened_start=(anchor - timedelta(days=120)).isoformat(),
        widened_end=(anchor + timedelta(days=120)).isoformat(),
    )


def _recent_rows(payload: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    recent = payload.get("filings", {}).get("recent", {})
    if not isinstance(recent, Mapping):
        raise ValueError("submissions_recent")
    fields = (
        "form",
        "filingDate",
        "accessionNumber",
        "primaryDocument",
        "primaryDocDescription",
        "items",
        "cik",
        "ticker",
    )
    values = {field: recent.get(field, []) for field in fields}
    if any(not isinstance(value, list) for value in values.values()):
        raise ValueError("submissions_recent")
    count = max((len(value) for value in values.values()), default=0)
    return tuple(
        {
            field: values[field][index] if index < len(values[field]) else ""
            for field in fields
        }
        for index in range(count)
    )


def _parse_items(value: object) -> tuple[str, ...]:
    return tuple(
        sorted({item.strip() for item in str(value or "").split(",") if item.strip()})
    )


def _admitted(
    form: str,
    items: Sequence[str],
    *,
    is_observation_filing: bool,
) -> bool:
    if form in _IDENTITY_FORMS or form in _M_AND_A_FORMS:
        return True
    return form in {"8-K", "8-K/A"} and (
        is_observation_filing or bool({"2.01", "3.01"}.intersection(items))
    )


def _identity_relevant(record: FilingRecord) -> bool:
    return record.form in _IDENTITY_FORMS or (
        record.form in {"8-K", "8-K/A"} and "3.01" in record.items
    )


def _filing_record(context: IdentityContext, row: Mapping[str, Any]) -> FilingRecord | None:
    row_cik = str(row.get("cik") or context.cik).strip()
    try:
        cik = _normalized_cik(row_cik)
    except ValueError:
        return None
    if cik != context.cik:
        return None
    try:
        filing_date = _normalized_date("filing_date", row.get("filingDate"))
        accession = _required_text("accession", row.get("accessionNumber"), limit=160)
        form = _required_text("form", row.get("form"), limit=30).upper()
        primary_document = _required_text(
            "primary_document", row.get("primaryDocument"), limit=255
        )
    except ValueError:
        return None
    items = _parse_items(row.get("items"))
    if not _admitted(
        form,
        items,
        is_observation_filing=accession == context.accession,
    ):
        return None
    accession_path = accession.replace("-", "")
    return FilingRecord(
        cik=cik,
        form=form,
        filing_date=filing_date,
        accession=accession,
        primary_document=primary_document,
        description=str(row.get("primaryDocDescription") or "").strip()[:240],
        items=items,
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/"
            f"{cik.lstrip('0')}/{accession_path}/{primary_document}"
        ),
    )


def select_filing_chain(
    context: IdentityContext, submissions: Mapping[str, Any]
) -> FilingChainSelection:
    payload_cik = submissions.get("cik")
    if payload_cik not in (None, "") and _normalized_cik(payload_cik) != context.cik:
        return FilingChainSelection((), "primary", 0, ("sec_evidence_insufficient",))
    records = tuple(
        record
        for row in _recent_rows(submissions)
        if (record := _filing_record(context, row)) is not None
    )

    def within(start: str, end: str) -> tuple[FilingRecord, ...]:
        unique = {
            record.accession: record
            for record in records
            if start <= record.filing_date <= end
        }
        return tuple(sorted(unique.values(), key=lambda item: (item.filing_date, item.accession)))

    primary = within(context.primary_start, context.primary_end)
    if any(_identity_relevant(record) for record in primary):
        return FilingChainSelection(primary, "primary", 0, ())
    widened = within(context.widened_start, context.widened_end)
    blockers = () if widened else ("sec_evidence_insufficient",)
    return FilingChainSelection(widened, "widened_120_day", 1, blockers)


def _visible_text(document: str) -> str:
    parser = _VisibleText()
    try:
        parser.feed(document)
        rendered = " ".join(parser.parts)
    except Exception:
        rendered = document
    return re.sub(r"\s+", " ", rendered).strip()


def _bounded_utf8(value: str, limit: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= limit:
        return value.strip()
    return encoded[:limit].decode("utf-8", errors="ignore").strip()


def _sentence_spans(value: str) -> tuple[tuple[int, int, str], ...]:
    spans: list[tuple[int, int, str]] = []
    start = 0
    for match in re.finditer(r"(?<=[.!?])\s+", value):
        end = match.start()
        if value[start:end].strip():
            spans.append((start, end, value[start:end]))
        start = match.end()
    if value[start:].strip():
        spans.append((start, len(value), value[start:]))
    return tuple(spans)


def _candidate_sentence(sentence: str, context: IdentityContext) -> bool:
    folded = sentence.casefold()
    if _CIK_IN_TEXT.search(sentence) is not None:
        return True
    if _NEW_REPLACING.search(sentence) is not None:
        return True
    if _CONTINUES_TICKER.search(sentence) is not None:
        return True
    if _POSTFIX_TICKER.search(sentence) is not None:
        return True
    if _REGISTERED_COMMON_SECURITY.search(sentence) is not None:
        return True
    if _UNCHANGED_COMMON_STOCK.search(sentence) is not None:
        return True
    if _TERMINAL_DELISTING.search(sentence) is not None:
        return True
    if "transfer from" in folded or "common stock" in folded:
        return True
    if _EFFECTIVE_MONTH_DATE.search(sentence) is not None:
        return True
    if _EFFECTIVE_ISO_DATE.search(sentence) is not None:
        return True
    if _TRADING_BEGIN_DATE.search(sentence) is not None:
        return True
    if _SOURCE_DEADLINE_PHRASE.search(sentence) is not None and (
        _ANY_MONTH_DATE.search(sentence) is not None
        or _ANY_ISO_DATE.search(sentence) is not None
    ):
        return True
    if _ASSET_PURCHASE.search(sentence) is not None:
        return True
    if _CORPORATE_UNIFICATION.search(sentence) is not None:
        return True
    if _SAME_NUMBER_COMMON_SHARES.search(sentence) is not None:
        return True
    return any(
        marker in folded
        for marker in (
            "asset acquisition",
            "corporate unification",
            "no tracked-security identity change",
            "does not change the tracked security identity",
        )
    ) or any(alias.casefold() in folded for alias in context.ticker_aliases)


def _focused_candidate(
    sentence: str, context: IdentityContext
) -> tuple[int, int, str]:
    if len(sentence.encode("utf-8")) <= _MAX_EXCERPT_BYTES:
        return 0, len(sentence), sentence
    spans: list[tuple[int, int]] = []
    for pattern in (
        _CIK_IN_TEXT,
        _NEW_REPLACING,
        _CONTINUES_TICKER,
        _POSTFIX_TICKER,
        _REGISTERED_COMMON_SECURITY,
        _UNCHANGED_COMMON_STOCK,
        _TERMINAL_DELISTING,
        _EFFECTIVE_MONTH_DATE,
        _EFFECTIVE_ISO_DATE,
        _TRADING_BEGIN_DATE,
        _SOURCE_DEADLINE_PHRASE,
        _ANY_MONTH_DATE,
        _ANY_ISO_DATE,
        _ASSET_PURCHASE,
        _CORPORATE_UNIFICATION,
        _SAME_NUMBER_COMMON_SHARES,
        re.compile(r"\bcommon stock\b", re.IGNORECASE),
        re.compile(r"\btransfer from\b", re.IGNORECASE),
        re.compile(r"\bno tracked-security identity change\b", re.IGNORECASE),
        re.compile(r"\bdoes not change the tracked security identity\b", re.IGNORECASE),
    ):
        spans.extend(match.span() for match in pattern.finditer(sentence))
    for alias in context.ticker_aliases:
        spans.extend(
            match.span()
            for match in re.finditer(rf"\b{re.escape(alias)}\b", sentence, re.IGNORECASE)
        )
    if not spans:
        focused = _bounded_utf8(sentence, _MAX_EXCERPT_BYTES)
        return 0, len(focused), focused
    start = min(item[0] for item in spans)
    end = max(item[1] for item in spans)
    focused = _bounded_utf8(sentence[start:end], _MAX_EXCERPT_BYTES)
    return start, start + len(focused), focused


def _evidence_excerpts(
    rendered: str, context: IdentityContext
) -> tuple[tuple[str, tuple[tuple[int, int], ...]], ...]:
    candidates = [
        (start, end, sentence)
        for start, end, sentence in _sentence_spans(rendered)
        if _candidate_sentence(sentence, context)
    ]
    if not candidates:
        excerpt = _bounded_utf8(rendered, _MAX_EXCERPT_BYTES)
        return ((excerpt, ((0, len(excerpt)),)),)

    chunks: list[tuple[str, tuple[tuple[int, int], ...]]] = []
    texts: list[str] = []
    ranges: list[tuple[int, int]] = []
    byte_count = 0
    for start, end, sentence in candidates:
        relative_start, relative_end, sentence = _focused_candidate(sentence, context)
        start, end = start + relative_start, start + relative_end
        addition = len(sentence.encode("utf-8")) + (1 if texts else 0)
        if texts and byte_count + addition > _MAX_EXCERPT_BYTES:
            chunks.append((" ".join(texts), tuple(ranges)))
            texts = []
            ranges = []
            byte_count = 0
            addition = len(sentence.encode("utf-8"))
        texts.append(sentence)
        ranges.append((start, end))
        byte_count += addition
    if texts:
        chunks.append((" ".join(texts), tuple(ranges)))
    return tuple(chunks)


def _fact(
    *,
    evidence: SecEvidence,
    fact_type: str,
    value: Any,
    sentence_start: int,
    sentence_end: int,
    rule_id: str,
) -> SecFact:
    cited = evidence.excerpt[sentence_start:sentence_end]
    byte_start = len(evidence.excerpt[:sentence_start].encode("utf-8"))
    byte_end = byte_start + len(cited.encode("utf-8"))
    normalized_value = normalize_automation_fact_value(fact_type, value)
    return SecFact(
        fact_type=fact_type,
        value=normalized_value,
        evidence_id=evidence.evidence_id,
        span_start_byte=byte_start,
        span_end_byte=byte_end,
        cited_text=cited,
        cited_text_sha256=hashlib.sha256(cited.encode("utf-8")).hexdigest(),
        rule_id=rule_id,
        rule_version=_RULE_VERSION,
    )


def _normalized_month_date_text(value: str) -> str:
    return datetime.strptime(value, "%B %d, %Y").date().isoformat()


def _normalized_source_date_text(value: str) -> str:
    return (
        _normalized_month_date_text(value)
        if _ANY_MONTH_DATE.fullmatch(value) is not None
        else _normalized_date("source_deadline", value)
    )


def _source_deadlines(
    evidence: SecEvidence,
) -> tuple[tuple[SecSourceDeadline, ...], bool]:
    rows: list[SecSourceDeadline] = []
    ambiguous = False
    for start, end, sentence in _sentence_spans(evidence.excerpt):
        target_matches = [
            (match, kind)
            for pattern, kind in (
                (_TERMINATE_IF_BY, "termination_condition"),
                (_CURRENT_DEADLINE, "current"),
                (_EXTENDED_DEADLINE, "extension"),
            )
            for match in pattern.finditer(sentence)
        ]
        extension_action_count = len(_EXTENSION_ACTION.findall(sentence))
        if len(target_matches) != 1 or extension_action_count > 1:
            if len(target_matches) > 1 or extension_action_count > 1:
                ambiguous = True
            continue
        target_match, kind = target_matches[0]
        target_date = target_match.group("date")
        if _COORDINATE_TARGET.match(sentence[target_match.end("date") :]) is not None:
            ambiguous = True
            continue
        supersedes_text = target_match.groupdict().get("supersedes_date")
        supersedes_date = (
            _normalized_source_date_text(supersedes_text)
            if supersedes_text is not None
            else None
        )
        byte_start = len(evidence.excerpt[:start].encode("utf-8"))
        byte_end = byte_start + len(sentence.encode("utf-8"))
        rows.append(
            SecSourceDeadline(
                date=_normalized_source_date_text(target_date),
                evidence_id=evidence.evidence_id,
                span_start_byte=byte_start,
                span_end_byte=byte_end,
                cited_text=sentence,
                cited_text_sha256=hashlib.sha256(sentence.encode("utf-8")).hexdigest(),
                rule_id=_SOURCE_DEADLINE_RULE_ID,
                rule_version=_SOURCE_DEADLINE_RULE_VERSION,
                kind=kind,
                supersedes_date=supersedes_date,
            )
        )
    return tuple(rows), ambiguous


def _resolve_source_deadline(
    rows: Sequence[SecSourceDeadline],
) -> SecSourceDeadline | None:
    active: SecSourceDeadline | None = None
    for row in rows:
        if row.kind in {"current", "termination_condition"}:
            if active is None:
                active = row
            elif row.date != active.date:
                return None
            continue
        if row.kind != "extension":
            return None

        predecessor = row.supersedes_date
        if predecessor is None:
            if active is None:
                return None
            predecessor = active.date
        elif active is not None and active.date != predecessor:
            return None
        if date.fromisoformat(row.date) <= date.fromisoformat(predecessor):
            return None
        active = row
    return active


def _venue_mentions(sentence: str) -> tuple[tuple[int, str], ...]:
    found: list[tuple[int, int, str]] = []
    occupied: list[tuple[int, int]] = []
    for pattern, value in _VENUES:
        for match in pattern.finditer(sentence):
            if any(start <= match.start() < end for start, end in occupied):
                continue
            occupied.append(match.span())
            found.append((match.start(), match.end(), value))
    return tuple((start, value) for start, _end, value in sorted(found))


def _extract_facts(evidence: SecEvidence, context: IdentityContext) -> tuple[SecFact, ...]:
    facts: list[SecFact] = []
    support: dict[str, tuple[int, int]] = {}

    def emit(fact_type: str, value: Any, start: int, end: int, rule_id: str) -> None:
        facts.append(
            _fact(
                evidence=evidence,
                fact_type=fact_type,
                value=value,
                sentence_start=start,
                sentence_end=end,
                rule_id=rule_id,
            )
        )
        support.setdefault(fact_type, (start, end))

    for start, end, sentence in _sentence_spans(evidence.excerpt):
        folded = sentence.casefold()
        cik_match = _CIK_IN_TEXT.search(sentence)
        if cik_match is not None:
            cik = _normalized_cik(cik_match.group("cik"))
            if cik == context.cik:
                emit("issuer_cik", cik, start, end, "sec.explicit_cik")
        elif "issuer_cik" not in support:
            context_cik = re.search(
                rf"(?<!\d){re.escape(context.cik)}(?!\d)", sentence
            )
            if context_cik is not None:
                emit(
                    "issuer_cik",
                    context.cik,
                    start,
                    end,
                    "sec.inline_xbrl_cik_token",
                )

        registered = _REGISTERED_COMMON_SECURITY.search(sentence)
        if registered is not None:
            ticker = registered.group("ticker").upper()
            if ticker in context.ticker_aliases:
                emit(
                    "source_ticker",
                    ticker,
                    start,
                    end,
                    "sec.registered_security_symbol",
                )
                support.setdefault("registered_current_security", (start, end))
                registered_venues = tuple(
                    dict.fromkeys(
                        value
                        for _position, value in _venue_mentions(registered.group(0))
                    )
                )
                if len(registered_venues) == 1:
                    emit(
                        "source_venue",
                        registered_venues[0],
                        start,
                        end,
                        "sec.registered_security_venue",
                    )

        transition = _NEW_REPLACING.search(sentence)
        if transition is not None:
            old = transition.group("old").upper()
            new = transition.group("new").upper()
            if old != new and (
                old in context.ticker_aliases or new in context.ticker_aliases
            ):
                emit("source_ticker", old, start, end, "sec.explicit_symbol_change")
                emit("successor_ticker", new, start, end, "sec.explicit_symbol_change")

        postfix_ticker = _POSTFIX_TICKER.search(sentence)
        if postfix_ticker is not None:
            ticker = postfix_ticker.group("ticker").upper()
            fact_type = (
                "source_ticker"
                if ticker in context.ticker_aliases
                else "successor_ticker"
            )
            emit(
                fact_type,
                ticker,
                start,
                end,
                "sec.explicit_postfix_ticker_symbol",
            )

        continuation = _CONTINUES_TICKER.search(sentence)
        if continuation is not None:
            ticker = continuation.group("ticker").upper()
            if ticker in context.ticker_aliases:
                emit("source_ticker", ticker, start, end, "sec.explicit_symbol_continuity")

        unchanged = _UNCHANGED_COMMON_STOCK.search(sentence)
        if unchanged is not None:
            ticker = unchanged.group("ticker").upper()
            if ticker in context.ticker_aliases:
                emit("source_ticker", ticker, start, end, "sec.explicit_security_unchanged")

        if re.search(r"\bcommon stock\b", sentence, re.IGNORECASE):
            emit("security_class", "common_stock", start, end, "sec.explicit_security_class")

        terminal = _TERMINAL_DELISTING.search(sentence)
        trading_begin_date = _TRADING_BEGIN_DATE.search(sentence)
        effective_month_date = _EFFECTIVE_MONTH_DATE.search(sentence)
        effective_iso_date = _EFFECTIVE_ISO_DATE.search(sentence)
        identity_date_context = any(
            marker in folded
            for marker in (
                "common shares",
                "common stock",
                "delist",
                "listing",
                "ticker symbol",
                "trading",
            )
        )
        date_value = None
        date_rule = None
        if trading_begin_date is not None:
            date_value = _normalized_month_date_text(
                trading_begin_date.group("date")
            )
            date_rule = "sec.explicit_trading_start_date"
        elif identity_date_context and effective_month_date is not None:
            date_value = _normalized_month_date_text(
                effective_month_date.group("date")
            )
            date_rule = "sec.explicit_effective_date"
        elif identity_date_context and effective_iso_date is not None:
            date_value = _normalized_date(
                "effective_date", effective_iso_date.group("date")
            )
            date_rule = "sec.explicit_effective_date"
        if (
            terminal is not None
            and str(evidence.source_locator.get("form") or "").upper() in {"25", "25-NSE"}
            and evidence.source_locator.get("filing_chain_complete") is True
            and date_value is not None
        ):
            ticker = terminal.group("ticker").upper()
            if ticker in context.ticker_aliases:
                emit("source_ticker", ticker, start, end, "sec.explicit_terminal_delisting")
                emit(
                    "tracked_security_effect",
                    "terminal_delisting",
                    start,
                    end,
                    "sec.explicit_terminal_delisting",
                )

        if "transfer from" in folded or (
            "transfer" in folded and "listing" in folded
        ):
            venues = tuple(
                dict.fromkeys(value for _position, value in _venue_mentions(sentence))
            )
            if len(venues) >= 2 and venues[0] != venues[1]:
                emit("source_venue", venues[0], start, end, "sec.explicit_venue_transfer")
                emit(
                    "destination_venue",
                    venues[1],
                    start,
                    end,
                    "sec.explicit_venue_transfer",
                )

        if date_value is not None and date_rule is not None:
            emit(
                "effective_date",
                date_value,
                start,
                end,
                date_rule,
            )

        asset_purchase = _ASSET_PURCHASE.search(sentence)
        if asset_purchase is not None and "transaction_structure" not in support:
            counterparty = _ASSET_COUNTERPARTY.search(sentence)
            transaction: dict[str, str] = {
                "kind": "asset_acquisition",
                "terms_status": "not_extracted",
            }
            if counterparty is not None:
                transaction = {
                    "kind": "asset_acquisition",
                    "terms_status": "partial",
                    "counterparty_name": re.sub(
                        r"\s+", " ", counterparty.group("name")
                    ).strip(),
                }
            emit(
                "transaction_structure",
                transaction,
                start,
                end,
                "sec.explicit_asset_acquisition",
            )
        elif (
            _CORPORATE_UNIFICATION.search(sentence) is not None
            and "transaction_structure" not in support
        ):
            emit(
                "transaction_structure",
                {"kind": "corporate_unification", "terms_status": "not_extracted"},
                start,
                end,
                "sec.explicit_corporate_unification",
            )

        if _SAME_NUMBER_COMMON_SHARES.search(sentence) is not None:
            support.setdefault("same_share_continuity", (start, end))

        if "no tracked-security identity change" in folded:
            emit(
                "tracked_security_effect",
                "no_identity_change",
                start,
                end,
                "sec.explicit_no_identity_change",
            )
        elif "does not change the tracked security identity" in folded:
            effect = (
                "asset_acquisition_no_registrant_change"
                if "transaction_structure" in support
                else "no_identity_change"
            )
            emit(
                "tracked_security_effect",
                effect,
                start,
                end,
                "sec.explicit_no_identity_change",
            )

    values = _fact_values(facts)
    if "tracked_security_effect" not in values:
        source = values.get("source_ticker", set())
        successor = values.get("successor_ticker", set())
        venues = values.get("destination_venue", set())
        transactions = [
            fact.value
            for fact in facts
            if fact.fact_type == "transaction_structure"
            and isinstance(fact.value, Mapping)
        ]
        transaction_kinds = {
            str(transaction.get("kind") or "") for transaction in transactions
        }
        registered_continuity = (
            source == {context.current_ticker}
            and "registered_current_security" in support
            and not successor
            and not venues
        )
        if registered_continuity and "asset_acquisition" in transaction_kinds:
            start, end = support["transaction_structure"]
            emit(
                "tracked_security_effect",
                "asset_acquisition_no_registrant_change",
                start,
                end,
                "sec.derived_asset_purchase_registrant_continuity",
            )
        elif (
            registered_continuity
            and "corporate_unification" in transaction_kinds
            and "same_share_continuity" in support
        ):
            start, end = support["same_share_continuity"]
            emit(
                "tracked_security_effect",
                "no_identity_change",
                start,
                end,
                "sec.derived_unification_share_continuity",
            )
        elif len(source) == len(successor) == 1 and source != successor:
            key = "successor_ticker"
            effect = "symbol_and_venue_change" if venues else "symbol_change"
            start, end = support[key]
            emit(
                "tracked_security_effect",
                effect,
                start,
                end,
                "sec.derived_explicit_identity_shape",
            )
        elif venues and len(source) == 1 and not successor:
            ticker = next(iter(source))
            continuity_start, continuity_end = support["source_ticker"]
            emit(
                "successor_ticker",
                ticker,
                continuity_start,
                continuity_end,
                "sec.derived_explicit_identity_shape",
            )
            start, end = support["destination_venue"]
            emit(
                "tracked_security_effect",
                "venue_change_only",
                start,
                end,
                "sec.derived_explicit_identity_shape",
            )

    unique = {
        (
            fact.fact_type,
            _canonical_fact_value(fact.value),
            fact.evidence_id,
            fact.span_start_byte,
            fact.span_end_byte,
        ): fact
        for fact in facts
    }
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (
                item.fact_type,
                _canonical_fact_value(item.value),
                item.evidence_id,
                item.span_start_byte,
            ),
        )
    )


def _canonical_fact_value(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _fact_values(facts: Iterable[SecFact]) -> dict[str, set[Any]]:
    result: dict[str, set[Any]] = {}
    for fact in facts:
        value = (
            _canonical_fact_value(fact.value)
            if isinstance(fact.value, (Mapping, list, tuple))
            else fact.value
        )
        result.setdefault(fact.fact_type, set()).add(value)
    return result


def detect_fact_conflicts(
    facts: Iterable[SecFact],
) -> dict[str, tuple[str, ...]]:
    values = _fact_values(facts)
    return {
        fact_type: tuple(sorted(current))
        for fact_type, current in sorted(values.items())
        if len(current) > 1
    }


def _empty_result(
    context: IdentityContext,
    selection: FilingChainSelection,
    budget: SecRequestBudget,
    blockers: Iterable[str],
) -> SecEvidenceResult:
    return SecEvidenceResult(
        context=context,
        selection=selection,
        evidence=(),
        facts=(),
        conflicts={},
        blockers=tuple(dict.fromkeys(blockers)),
        symbol_transitions=(),
        source_deadlines=(),
        diagnostics=budget.diagnostics(),
    )


def collect_sec_evidence(
    *,
    context: IdentityContext,
    transport: Any,
    retrieved_at: str,
    budget: SecRequestBudget | None = None,
) -> SecEvidenceResult:
    at = _timestamp(retrieved_at)
    shared_budget = budget or SecRequestBudget.lifecycle()
    submissions_url = f"https://data.sec.gov/submissions/CIK{context.cik}.json"
    try:
        submissions = transport.get_json(
            submissions_url,
            budget=shared_budget,
            max_bytes=min(4 * 1_048_576, shared_budget.max_total_bytes),
        )
    except SecTransportFailure as exc:
        selection = FilingChainSelection((), "primary", 0, (exc.code,))
        return _empty_result(context, selection, shared_budget, (exc.code,))
    if not isinstance(submissions, Mapping):
        raise ValueError("submissions_payload")
    selection = select_filing_chain(context, submissions)
    if not selection.filings:
        return _empty_result(context, selection, shared_budget, selection.blockers)

    evidence_rows: list[SecEvidence] = []
    blockers: list[str] = list(selection.blockers)
    completed_documents = 0
    for filing in selection.filings:
        try:
            response = transport.get(
                filing.source_url,
                budget=shared_budget,
                document=True,
                max_bytes=shared_budget.max_document_bytes,
                accept="text/html, application/xhtml+xml, text/plain",
            )
        except SecTransportFailure as exc:
            blockers.append(exc.code)
            break
        if response.status_code == 403:
            blockers.append("sec_access_denied")
            break
        if response.status_code != 200:
            blockers.append("sec_document_unavailable")
            continue
        document = response.body.decode(response.encoding or "utf-8", errors="replace")
        rendered = _visible_text(document)
        if not rendered:
            blockers.append("sec_document_unavailable")
            continue
        completed_documents += 1
        document_digest = hashlib.sha256(response.body).hexdigest()
        for excerpt, rendered_ranges in _evidence_excerpts(rendered, context):
            excerpt_digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
            evidence_id = "sle_" + hashlib.sha256(
                f"{context.cik}\0{filing.accession}\0{document_digest}\0{excerpt_digest}".encode()
            ).hexdigest()[:32]
            evidence = SecEvidence(
                evidence_id=evidence_id,
                source_family="regulator",
                adapter="sec_edgar",
                kind="regulator_excerpt",
                source_url=filing.source_url,
                title=filing.description or f"{filing.form} filing",
                publisher="SEC EDGAR",
                source_published_at=filing.filing_date,
                retrieved_at=at,
                excerpt=excerpt,
                content_sha256=excerpt_digest,
                document_sha256=document_digest,
                source_locator={
                    "accession": filing.accession,
                    "form": filing.form,
                    "items": list(filing.items),
                    "primary_document": filing.primary_document,
                    "rendered_text_ranges": [list(item) for item in rendered_ranges],
                    "rule_id": "sec.visible_text_excerpt",
                    "rule_version": _RULE_VERSION,
                },
            )
            evidence_rows.append(evidence)

    filing_chain_complete = (
        completed_documents == len(selection.filings) and not selection.blockers
    )
    evidence_rows = [
        replace(
            evidence,
            source_locator={
                **dict(evidence.source_locator),
                "filing_chain_complete": filing_chain_complete,
            },
        )
        for evidence in evidence_rows
    ]
    facts = [
        fact
        for evidence in evidence_rows
        for fact in _extract_facts(evidence, context)
    ]
    deadline_rows: list[SecSourceDeadline] = []
    deadline_ambiguous = False
    for evidence in evidence_rows:
        extracted, ambiguous = _source_deadlines(evidence)
        deadline_rows.extend(extracted)
        deadline_ambiguous = deadline_ambiguous or ambiguous
    active_deadline = _resolve_source_deadline(deadline_rows)
    if deadline_ambiguous or (deadline_rows and active_deadline is None):
        blockers.append("sec_evidence_insufficient")
        resolved_deadlines: tuple[SecSourceDeadline, ...] = ()
    else:
        resolved_deadlines = (active_deadline,) if active_deadline is not None else ()

    conflicts = detect_fact_conflicts(facts)
    if conflicts:
        blockers.append("source_conflict")
    values = _fact_values(facts)
    sources = sorted(values.get("source_ticker", set()))
    successors = sorted(values.get("successor_ticker", set()))
    transitions = tuple(
        (source, successor)
        for source in sources
        for successor in successors
        if source != successor
    )
    if not evidence_rows and not blockers:
        blockers.append("sec_evidence_insufficient")
    return SecEvidenceResult(
        context=context,
        selection=selection,
        evidence=tuple(evidence_rows),
        facts=tuple(facts),
        conflicts=conflicts,
        blockers=tuple(dict.fromkeys(blockers)),
        symbol_transitions=transitions,
        source_deadlines=resolved_deadlines,
        diagnostics=shared_budget.diagnostics(),
    )
