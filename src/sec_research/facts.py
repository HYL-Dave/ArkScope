"""Immutable exact observations from a single SEC Company Facts response."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib

from .common import (
    SourceError,
    SourceRef,
    accession_value,
    date_value,
    decode_object,
    json_pointer,
    normalize_cik,
    source_ref,
    text_value,
    validate_payload_cik,
)


@dataclass(frozen=True)
class FactObservation:
    fact_id: str
    cik: str
    namespace: str
    concept: str
    value: str
    unit: str
    start: str | None
    end: str
    fiscal_year: int | None
    fiscal_period: str | None
    form: str
    accession: str
    filed_date: str
    frame: str | None
    source: SourceRef


@dataclass(frozen=True)
class FactsSnapshot:
    cik: str
    sha256: str
    facts: tuple[FactObservation, ...]


def _mapping(value: object, pointer: str) -> dict:
    if not isinstance(value, dict):
        raise SourceError("sec_facts_shape_invalid", pointer)
    return value


def _observation(
    row: object, *, cik: str, namespace: str, concept: str, unit: str, source: SourceRef,
) -> FactObservation:
    pointer = source.pointer
    values = _mapping(row, pointer)
    value = values.get("val")
    if not (type(value) is int or isinstance(value, Decimal) and value.is_finite()):
        raise SourceError("sec_fact_value_invalid", pointer + "/val")
    start = date_value(values.get("start"), pointer + "/start", optional=True)
    end = date_value(values.get("end"), pointer + "/end")
    if start is not None and start > end:
        raise SourceError("sec_fact_period_invalid", pointer + "/start")
    fiscal_year = values.get("fy")
    if fiscal_year is not None and (
        type(fiscal_year) is not int or not 1 <= fiscal_year <= 9999
    ):
        raise SourceError("sec_fact_fiscal_year_invalid", pointer + "/fy")
    fact_id = "secfact_" + hashlib.sha256(
        (source.sha256 + "\n" + pointer).encode("utf-8")
    ).hexdigest()
    return FactObservation(
        fact_id=fact_id,
        cik=cik,
        namespace=namespace,
        concept=concept,
        value=str(value),
        unit=unit,
        start=start,
        end=end,
        fiscal_year=fiscal_year,
        fiscal_period=text_value(values.get("fp"), pointer + "/fp", optional=True),
        form=text_value(values.get("form"), pointer + "/form"),
        accession=accession_value(values.get("accn"), pointer + "/accn"),
        filed_date=date_value(values.get("filed"), pointer + "/filed"),
        frame=text_value(values.get("frame"), pointer + "/frame", optional=True),
        source=source,
    )


def parse_companyfacts(body: bytes, *, cik: str) -> FactsSnapshot:
    """Parse one whole source; selecting latest/quarter/as-of is a separate query.

    A malformed source raises before any snapshot is returned. No transport,
    storage, currency inference or numeric derivation occurs here.
    """
    canonical_cik = normalize_cik(cik)
    payload = decode_object(body)
    validate_payload_cik(payload, canonical_cik, required=True)
    digest = source_ref(body, "").sha256
    namespaces = _mapping(payload.get("facts"), "/facts")
    observations: list[FactObservation] = []
    for namespace, raw_concepts in namespaces.items():
        text_value(namespace, "/facts")
        namespace_pointer = json_pointer("facts", namespace)
        concepts = _mapping(raw_concepts, namespace_pointer)
        for concept, raw_metadata in concepts.items():
            text_value(concept, namespace_pointer)
            concept_pointer = json_pointer("facts", namespace, concept)
            metadata = _mapping(raw_metadata, concept_pointer)
            units = _mapping(metadata.get("units"), concept_pointer + "/units")
            for unit, raw_rows in units.items():
                text_value(unit, concept_pointer + "/units")
                unit_pointer = json_pointer("facts", namespace, concept, "units", unit)
                if not isinstance(raw_rows, list):
                    raise SourceError("sec_facts_shape_invalid", unit_pointer)
                for index, row in enumerate(raw_rows):
                    observations.append(_observation(
                        row,
                        cik=canonical_cik,
                        namespace=namespace,
                        concept=concept,
                        unit=unit,
                        source=SourceRef(digest, unit_pointer + f"/{index}"),
                    ))
    return FactsSnapshot(canonical_cik, digest, tuple(observations))
