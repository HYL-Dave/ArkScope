"""Inspectability checks for an LLM finding, never automatic listing authority.

Exact passages and field agreement make a finding reviewable. They do not prove
that a publisher or model is truthful; a fresh action-bound human confirmation
and the tracking writer's independent guards are still required.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from src.lifecycle_public_sources import PublicSourcePage, SourcePassage, SourceReadError, cite_passage
from src.lifecycle_source_context import parse_source_context
from src.security_lifecycle_web_contract import PublicInvestigationInput


class FindingFormatError(ValueError):
    pass


_DATE_TEXT_DESCRIPTION = (
    "A bare calendar date copied verbatim from a cited event passage, not a whole sentence. "
    "For example September 1, 2026 or 2026-09-01; omit prefixes such as Published or effective, "
    "time-of-day and timezone. Map that exact date to the corresponding YYYY-MM-DD field. "
    "If the source provides only a relative date or the date is not established, use null, not a guess."
)


class FindingCitation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: str = Field(pattern=r"^source-[1-9][0-9]*$")
    quote: str = Field(min_length=1, max_length=16000, description=(
        "One unique contiguous verbatim span of ONE supplied source passage. Preserve whitespace, "
        "punctuation and spelling. No ellipsis, paraphrase or joined fragments unless literally present "
        "in the passage. Use separate citations for separate spans."
    ))
    supports: list[Literal[
        "security_identity", "listing_ended", "active_listing", "active_otc",
        "same_security_continuation", "effective_date", "announcement_date",
        "acquisition_announced", "contradiction",
    ]] = Field(min_length=1, description=(
        "Claims this exact quotation supports for the target security, not other instruments of the issuer. "
        "Event quotations must name the target security class and have an issuer/symbol identity anchor. "
        "For effective_date, include the listing_ended or same_security_continuation claim and its actual "
        "date in that same event quotation."
    ))


class WebFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_ticker: str = Field(min_length=1, max_length=20)
    issuer_name: str = Field(min_length=1, max_length=240)
    security_class: str = Field(min_length=1, max_length=120)
    venue: str = Field(min_length=1, max_length=120)
    event_kind: Literal["listing_ended", "symbol_continuation", "active_listing", "acquisition_announced", "trading_suspended", "unresolved"]
    timing: Literal["completed", "scheduled", "unknown"]
    successor_ticker: str | None = Field(default=None, pattern=r"^[A-Z0-9]{1,8}(?:[ .-][A-Z0-9]{1,8})?$", max_length=20)
    effective_date: str | None = None
    effective_date_text: str | None = Field(default=None, max_length=120, description=_DATE_TEXT_DESCRIPTION)
    announcement_date: str | None = None
    announcement_date_text: str | None = Field(default=None, max_length=120, description=_DATE_TEXT_DESCRIPTION)
    summary: str = Field(min_length=1, max_length=2000)
    contradictions: list[str]
    unresolved_conditions: list[str]
    citations: list[FindingCitation]

    @field_validator("effective_date", "announcement_date")
    @classmethod
    def canonical_date(cls, value):
        if value is not None and date.fromisoformat(value).isoformat() != value:
            raise ValueError("source_date")
        return value

    @field_validator("summary", "source_ticker", "issuer_name", "security_class", "venue")
    @classmethod
    def nonblank(cls, value):
        if value != value.strip() or not value or any(ord(character) < 32 for character in value):
            raise ValueError("finding_text")
        return value


def strict_schema(model: type[BaseModel]) -> dict:
    """All providers receive the same required/nullable structured-output shape."""
    schema = model.model_json_schema()

    def visit(value):
        if isinstance(value, dict):
            value.pop("default", None)
            if value.get("type") == "object":
                value["additionalProperties"] = False
                value["required"] = list(value.get("properties", {}))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    return schema


@dataclass(frozen=True)
class ValidatedFinding:
    finding: WebFinding
    passages: tuple[SourcePassage, ...]
    action: str | None
    block_reasons: tuple[str, ...]
    unique_passage_count: int
    independent_source_count: None = None


def _contains(quote: str, phrase: str, *, symbol=False) -> bool:
    boundary = r"A-Za-z0-9.\-" if symbol else r"\w"
    return re.search(rf"(?<![{boundary}]){re.escape(phrase)}(?![{boundary}])", quote, flags=re.IGNORECASE) is not None


def _date_text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    for pattern in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%B %d %Y"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def validate_finding(request: PublicInvestigationInput, payload: dict,
                     pages: Mapping[str, PublicSourcePage], *, unread_source_count=0, source_context=None) -> ValidatedFinding:
    try:
        finding = WebFinding.model_validate(payload)
    except ValidationError:
        raise FindingFormatError("web_finding_invalid") from None
    if type(unread_source_count) is not int or unread_source_count < 0:
        raise FindingFormatError("source_read_count")
    blockers = set()
    contexts = None if source_context is None else parse_source_context(source_context, pages)
    passages = []
    admitted = []
    for citation in finding.citations:
        page = pages.get(citation.source_id)
        if page is None:
            blockers.add("source_citation_unavailable")
            continue
        start = page.text.find(citation.quote)
        if start < 0 or page.text.find(citation.quote, start + 1) >= 0:
            blockers.add("source_citation_mismatch")
            continue
        start_byte = len(page.text[:start].encode("utf-8"))
        end_byte = start_byte + len(citation.quote.encode("utf-8"))
        if contexts is not None and not contexts[citation.source_id].contains(start_byte, end_byte):
            blockers.add("source_citation_not_supplied")
            continue
        if page.mime_type == "application/json" and any(value != "security_identity" for value in citation.supports):
            blockers.add("source_metadata_not_notice")
            continue
        try:
            passage = cite_passage(page, start_byte, end_byte, citation.quote)
        except SourceReadError as exc:
            blockers.add(str(exc))
            continue
        passages.append(passage)
        admitted.append(citation)
    if not admitted:
        blockers.add("source_passage_missing")
    if any(getattr(request, "ticker" if field == "source_ticker" else field) is not None
           and getattr(finding, field) != getattr(request, "ticker" if field == "source_ticker" else field)
           for field in ("source_ticker", "issuer_name", "security_class", "venue")):
        blockers.add("security_identity_mismatch")
    identity_sources = {citation.source_id for citation in admitted if "security_identity" in citation.supports
                        and all(_contains(citation.quote, value, symbol=field == "ticker") for field, value in (
        ("ticker", request.ticker), ("issuer_name", request.issuer_name),
        ("security_class", finding.security_class), ("venue", finding.venue),
    ))}
    if not identity_sources:
        blockers.add("security_identity_not_supported")
    # Claim labels cannot combine one security's identity with another one's
    # event/date. These are inspectable bindings, not semantic proof of a claim.
    target_citations = [citation for citation in admitted
        if _contains(citation.quote, finding.security_class)
        and (citation.source_id in identity_sources
             or (_contains(citation.quote, request.issuer_name)
                 and _contains(citation.quote, request.ticker, symbol=True)))]
    target_support = {value for citation in target_citations for value in citation.supports}
    support = {value for citation in admitted for value in citation.supports}
    if finding.contradictions or "contradiction" in support:
        blockers.add("material_contradiction")
    if finding.unresolved_conditions:
        blockers.add("finding_incomplete")
    # Unread supplements are disclosed by the journal/review packet, not proof
    # of a missing action field. Essential gaps and contradictions still block.

    action = None
    if finding.event_kind in {"listing_ended", "symbol_continuation"}:
        event_claim = "listing_ended" if finding.event_kind == "listing_ended" else "same_security_continuation"
        event_citations = [citation for citation in target_citations if event_claim in citation.supports]
        if finding.timing == "unknown":
            blockers.add("event_timing_unknown")
        if finding.effective_date is None:
            blockers.add("effective_date_missing")
        elif (_date_text(finding.effective_date_text) != finding.effective_date
              or not any("effective_date" in item.supports and finding.effective_date_text in item.quote for item in event_citations)):
            blockers.add("effective_date_not_supported")
        if finding.effective_date is not None and (
            (finding.timing == "completed" and finding.effective_date > request.as_of)
            or (finding.timing == "scheduled" and finding.effective_date <= request.as_of)
        ):
            blockers.add("event_timing_conflict")
        if finding.event_kind == "listing_ended":
            action = "terminal_delisting"
            if "listing_ended" not in target_support:
                blockers.add("listing_change_not_supported")
            if target_support & {"active_listing", "active_otc"}:
                blockers.add("active_listing_conflict")
            if finding.successor_ticker is not None:
                blockers.add("removal_and_continuation_mixed")
        else:
            action = "symbol_continuation"
            if finding.successor_ticker in {None, request.ticker}:
                blockers.add("successor_missing")
            if ("same_security_continuation" not in target_support or finding.successor_ticker is None
                    or not any("same_security_continuation" in item.supports
                               and _contains(item.quote, request.ticker, symbol=True)
                               and _contains(item.quote, finding.successor_ticker, symbol=True) for item in event_citations)):
                blockers.add("same_security_continuation_not_supported")
    elif finding.event_kind != "active_listing":
        blockers.add("event_not_actionable")
    if finding.announcement_date is not None and (
        _date_text(finding.announcement_date_text) != finding.announcement_date
        or not any("announcement_date" in item.supports and finding.announcement_date_text in item.quote for item in admitted)
    ):
        blockers.add("announcement_date_not_supported")
    return ValidatedFinding(finding, tuple(passages), None if blockers else action, tuple(sorted(blockers)),
                            len({passage.cited_text_sha256 for passage in passages}))
