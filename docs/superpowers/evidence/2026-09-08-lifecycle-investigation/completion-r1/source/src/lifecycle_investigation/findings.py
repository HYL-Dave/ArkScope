"""Source/identity bindings for human review, never a model's mutation authority."""

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.lifecycle_investigation.sources import source_passages
from src.security_lifecycle_web_finding import WebFinding, _contains, _date_text


class PassageCitation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    passage_id: str = Field(pattern=r"^source-[1-9][0-9]*:p[1-9][0-9]*$")
    supports: list[Literal["security_identity", "listing_ended", "active_listing", "active_otc",
        "same_security_continuation", "effective_date", "announcement_date", "acquisition_announced", "contradiction"]] = Field(min_length=1)


class Finding(WebFinding):
    version: Literal[2]
    citations: list[PassageCitation]
    limitations: list[Annotated[str, Field(min_length=1, max_length=400)]] = Field(default_factory=list, max_length=4,
        description="Non-action-changing limitations, such as the unknown exact date of an otherwise clearly completed event. Never put a genuine identity/OTC/conflicting-status question here.")
    unresolved_conditions: list[str] = Field(description="ONLY questions that could change whether this exact security is active, ended, or renamed. An optional source failure or unknown exact date alone belongs in limitations, not here.")


def _phrase(text, phrase):
    return _contains(" ".join(text.split()), " ".join(phrase.rstrip(".").split()))


def _issuer(text, name):
    # Legal suffixes are not security identifiers. The same source must still bind ticker, class and venue.
    core = re.sub(r",?\s+(?:Inc\.?|Incorporated|Corp\.?|Corporation|Ltd\.?|Limited|LLC)\.?$", "", name.strip(), flags=re.I)
    return _phrase(text, core)


_PAR_VALUE_SUFFIX = re.compile(
    r"(?:,\s*|\s+\(?)(?:\$\d+(?:\.\d+)?\s+par\s+value|par\s+value\s+\$\d+(?:\.\d+)?)"
    r"(?:\s+per\s+share)?\)?\.?$", re.I)


def _security_class_variants(name):
    name = _PAR_VALUE_SUFFIX.sub("", name.strip())
    variants = {name}
    if name.lower() in {"common stock", "common shares", "ordinary shares", "ordinary stock"}:
        variants.update({"common stock", "common shares", "ordinary shares", "ordinary stock"})
    return variants


def _security_class(text, name):
    # Face value is descriptive; named share classes and instrument types survive.
    return any(_phrase(text, variant) for variant in _security_class_variants(name))


def _defined_security_terms(text, name, venue):
    terms = set()
    for definition in re.finditer(r'\(\s*(?:the\s+)?["\u201c]([A-Za-z][A-Za-z ]{2,70})["\u201d]\s*\)', text, re.I):
        term = definition[1]
        if not re.search(r"\b(?:stock|shares|securities|notes|bonds|units)\b", term, re.I):
            continue
        prefix = " ".join(text[:definition.start()].split())
        for variant in _security_class_variants(name):
            for match in re.finditer(r"(?<!\w)" + re.escape(variant) + r"(?!\w)", prefix, re.I):
                description = prefix[match.start():]
                description = re.sub(r"\s+on\s+(?:the\s+)?" + re.escape(" ".join(venue.split())) + r"$", "", description, flags=re.I)
                description = _PAR_VALUE_SUFFIX.sub("", description).rstrip(" ,")
                # Only a class description, optional face value and exact venue may
                # precede its definition. A different instrument/issuer is not that class.
                if description.casefold() == variant.casefold():
                    terms.add(term)
    return terms


def validate_finding(target, payload, sources, supplied):
    finding = Finding.model_validate(payload)
    all_passages = {item["passage_id"]: item for key, source in sources.items() for item in source_passages(key, source)}
    blockers, citations, used = set(), [], []
    for citation in finding.citations:
        item = all_passages.get(citation.passage_id)
        if item is None:
            blockers.add("source_citation_mismatch")
        elif citation.passage_id not in supplied:
            blockers.add("source_citation_not_supplied")
        else:
            source = sources[item["source_id"]]
            if source["mime_type"] == "application/json" and set(citation.supports) != {"security_identity"}:
                blockers.add("source_metadata_not_notice")
            citations.append((item, citation.supports))
            used.append({**item, "url": source["url"], "title": source["title"], "publisher": source["publisher"],
                "published_at": source["published_at"], "retrieved_at": source["retrieved_at"],
                "coverage": source["coverage"], "corpus": source["corpus"]})
    if not citations:
        blockers.add("source_passage_missing")
    for field in ("ticker", "issuer_name", "security_class", "venue"):
        expected = getattr(target, field)
        actual = finding.source_ticker if field == "ticker" else getattr(finding, field)
        matches = _issuer(actual, expected) if expected is not None and field == "issuer_name" else _security_class(actual, expected) if expected is not None and field == "security_class" else _phrase(actual, expected) if expected is not None else True
        if not matches:
            blockers.add("security_identity_mismatch")
    if target.identity_status == "conflicting":
        blockers.add("security_identity_mismatch")
    identity_text = {}
    for item, claims in citations:
        if "security_identity" in claims:
            identity_text.setdefault(item["source_id"], []).append(item["text"])
    identities, definitions, binding_gaps = set(), {}, []
    for source_id, parts in identity_text.items():
        text = "\n".join(parts)
        matches = {"issuer_name": _issuer(text, finding.issuer_name), "security_class": _security_class(text, finding.security_class),
            "venue": _phrase(text, finding.venue), "ticker": _contains(text, target.ticker, symbol=True)}
        if all(matches.values()):
            identities.add(source_id)
            definitions[source_id] = {term for part in parts
                for term in _defined_security_terms(part, finding.security_class, finding.venue)}
        else:
            binding_gaps.append({"source_id": source_id, "missing_identity_fields": [key for key, found in matches.items() if not found]})
    if not identities:
        blockers.add("security_identity_not_supported")
    for source_id in identities:
        possible = [item for item in all_passages.values() if item["source_id"] == source_id and item["passage_id"] in supplied
            and _defined_security_terms(item["text"], finding.security_class, finding.venue)]
        missing = [item["passage_id"] for item in possible if not any(item["passage_id"] == cited["passage_id"] and "security_identity" in claims for cited, claims in citations)]
        if missing:
            binding_gaps.append({"source_id": source_id, "inspect_definition_passages": missing})
    target_citations = [(item, claims) for item, claims in citations if item["source_id"] in identities and
        (_security_class(item["text"], finding.security_class) or
         any(_contains(item["text"], term) for term in definitions.get(item["source_id"], ())))]
    support = {claim for _, claims in target_citations for claim in claims}
    if finding.contradictions or any("contradiction" in claims for _, claims in citations):
        blockers.add("material_contradiction")
    if finding.unresolved_conditions:
        blockers.add("finding_incomplete")
    action = None
    event = {"listing_ended": "listing_ended", "symbol_continuation": "same_security_continuation"}.get(finding.event_kind)
    if event:
        events = [(item, claims) for item, claims in target_citations if event in claims]
        if not events:
            blockers.add("listing_change_not_supported")
        if finding.timing != "completed":
            blockers.add("event_not_completed")
        if finding.effective_date is not None:
            dated = [(item, claims) for item, claims in citations if "effective_date" in claims
                and isinstance(finding.effective_date_text, str) and finding.effective_date_text in item["text"]]
            def date_continues_event(item):
                for event_item, _ in events:
                    if event_item["source_id"] != item["source_id"]:
                        continue
                    if event_item["passage_id"] == item["passage_id"]:
                        return True
                    text = sources[item["source_id"]]["text"]
                    if (event_item["end_char"] <= item["start_char"] and not text[event_item["end_char"]:item["start_char"]].strip()
                            and not re.search(r'[.!?]["\u201d)]*$', event_item["text"].strip())):
                        return True
                return False
            if ((finding.timing == "completed" and finding.effective_date > target.as_of) or _date_text(finding.effective_date_text) != finding.effective_date
                    or not any(date_continues_event(item) for item, _ in dated)):
                blockers.add("effective_date_not_supported")
        elif finding.effective_date_text is not None:
            blockers.add("effective_date_not_supported")
        if support & {"active_listing", "active_otc"}:
            blockers.add("active_listing_conflict")
        if finding.event_kind == "listing_ended":
            action = "terminal_delisting"
            if finding.successor_ticker is not None:
                blockers.add("removal_and_continuation_mixed")
        else:
            action = "symbol_continuation"
            if (finding.successor_ticker in {None, target.ticker} or not any(
                    _contains(item["text"], target.ticker, symbol=True) and
                    _contains(item["text"], finding.successor_ticker, symbol=True) for item, _ in events)):
                blockers.add("same_security_continuation_not_supported")
    elif finding.event_kind == "active_listing":
        if not support & {"active_listing", "active_otc"}:
            blockers.add("active_listing_not_supported")
    if finding.announcement_date is not None and (_date_text(finding.announcement_date_text) != finding.announcement_date or
        not any("announcement_date" in claims and finding.announcement_date_text in item["text"] for item, claims in citations)):
        blockers.add("announcement_date_not_supported")
    return {"finding": finding.model_dump(), "action": None if blockers else action,
        "block_reasons": sorted(blockers), "passages": used, "binding_gaps": binding_gaps}
