"""Attended security-lifecycle investigation and local case reads."""

from __future__ import annotations

from datetime import date, datetime, timezone
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.api.dependencies import (
    get_security_lifecycle_read_service,
    get_security_lifecycle_store,
)
from src.api.permissions import require_db_write
from src.agents.config import task_route
from src.card_synthesis import translate_text, translation_harness
from src.content_translation_failures import classify_content_translation_failure
from src.fixed_task_runtime_config import resolve_fixed_task_runtime
from src.security_lifecycle_disposition import LIFECYCLE_QUEUE_BUCKETS
from src.security_lifecycle_investigation import (
    LifecycleStoreUnavailable,
    LifecycleWritesUnavailable,
    SecurityLifecycleInvestigationStore,
    canonical_assessment_decimal,
    observation_fingerprint,
)
from src.security_lifecycle_manual_evidence import (
    add_manual_evidence,
    canonical_manual_https_url,
)
from src.security_lifecycle_translation import (
    EvidenceTranslationConflict,
    EvidenceTranslationFailure,
    EvidenceTranslationResult,
    prepare_evidence_translation,
    translate_evidence,
)
from src.tools.security_lifecycle_tools import SecurityLifecycleReadService


router = APIRouter(prefix="/security-lifecycle", tags=["security-lifecycle"])


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _request_text(
    value: str | None,
    *,
    name: str,
    required: bool,
) -> str | None:
    if value is None:
        if required:
            raise ValueError(name)
        return None
    normalized = value.strip()
    if "\0" in value or (required and not normalized):
        raise ValueError(name)
    return normalized or None


def _case_identity(case: dict) -> dict[str, str]:
    return {
        "source": str(case["source"]),
        "source_ref": str(case["source_ref"]),
        "ticker": str(case["ticker"]),
    }


class ManualEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, max_length=16000)
    url: str | None = Field(default=None, max_length=1000)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value):
        return _request_text(value, name="manual_text", required=value is not None)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value):
        if value is None:
            return None
        try:
            return canonical_manual_https_url(value)
        except ValueError as exc:
            raise ValueError("manual_url") from exc

    @model_validator(mode="after")
    def validate_shape(self):
        if (self.text is None) == (self.url is None):
            raise ValueError("manual_evidence_shape")
        return self


class CitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_kind: Literal["observation", "evidence"]
    evidence_id: str | None = Field(default=None, max_length=80)
    cited_content_sha256: str | None = Field(default=None, max_length=64)

    @field_validator("evidence_id")
    @classmethod
    def validate_evidence_id(cls, value):
        return _request_text(
            value,
            name="citation",
            required=value is not None,
        )

    @model_validator(mode="after")
    def validate_reference_shape(self):
        if self.reference_kind == "observation":
            if self.evidence_id is not None or not re.fullmatch(
                r"[0-9a-f]{64}", self.cited_content_sha256 or ""
            ):
                raise ValueError("citation")
        elif self.evidence_id is None or self.cited_content_sha256 is not None:
            raise ValueError("citation")
        return self


AssessmentOutcome = Literal[
    "undetermined",
    "listing_ended",
    "venue_transfer",
    "symbol_changed",
    "acquisition_cash",
    "acquisition_stock",
    "acquisition_mixed",
    "acquisition_terms_unknown",
    "issuer_security_change",
    "no_tracked_security_change",
    "other",
    "not_applicable",
]


class AssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relevance: Literal[
        "undetermined", "direct_tracked_security", "issuer_related", "unrelated"
    ]
    confidence: Literal["unknown", "low", "medium", "high"]
    conclusion: str = Field(min_length=1, max_length=4000)
    impact_summary: str = Field(min_length=1, max_length=4000)
    outcomes: list[AssessmentOutcome] = Field(min_length=1, max_length=12)
    citations: list[CitationRequest] = Field(default_factory=list, max_length=100)
    counterparty_name: str | None = Field(default=None, max_length=240)
    counterparty_ticker: str | None = Field(default=None, max_length=20)
    counterparty_cik: str | None = Field(default=None, max_length=10)
    successor_ticker: str | None = Field(default=None, max_length=20)
    destination_venue: str | None = Field(default=None, max_length=120)
    effective_date: str | None = Field(default=None, max_length=10)
    consideration_currency: str | None = Field(default=None, max_length=3)
    cash_per_security_decimal: str | None = Field(default=None, max_length=128)
    exchange_ratio_decimal: str | None = Field(default=None, max_length=128)

    @field_validator("conclusion", "impact_summary")
    @classmethod
    def validate_required_text(cls, value, info):
        return _request_text(value, name=info.field_name, required=True)

    @field_validator(
        "counterparty_name",
        "counterparty_ticker",
        "successor_ticker",
        "destination_venue",
    )
    @classmethod
    def validate_optional_text(cls, value, info):
        return _request_text(value, name=info.field_name, required=False)

    @field_validator("counterparty_cik")
    @classmethod
    def validate_counterparty_cik(cls, value):
        if value is not None and not re.fullmatch(r"[0-9]{10}", value):
            raise ValueError("counterparty_cik")
        return value

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, value):
        if value is None:
            return None
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("effective_date") from exc
        if parsed.isoformat() != value:
            raise ValueError("effective_date")
        return value

    @field_validator("consideration_currency")
    @classmethod
    def validate_consideration_currency(cls, value):
        if value is not None and not re.fullmatch(r"[A-Z]{3}", value):
            raise ValueError("consideration_currency")
        return value

    @field_validator("cash_per_security_decimal", "exchange_ratio_decimal")
    @classmethod
    def validate_decimal(cls, value, info):
        if value is not None:
            canonical_assessment_decimal(
                value,
                name=info.field_name.removesuffix("_decimal"),
            )
        return value

    @model_validator(mode="after")
    def validate_outcomes(self):
        if "undetermined" in self.outcomes and len(set(self.outcomes)) != 1:
            raise ValueError("conflicting_outcomes")
        return self


class AcknowledgementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Literal["evidence_insufficient"]
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("note")
    @classmethod
    def validate_note(cls, value):
        return _request_text(value, name="note", required=False)


class EvidenceTranslationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locale: Literal["en", "zh-Hant"]


def _translate_evidence_text(text: str, locale: str) -> EvidenceTranslationResult:
    try:
        route = task_route("card_translation")
        provider = route.provider
        model = route.model
        if provider not in {"anthropic", "openai"}:
            raise ValueError("translation_route_provider")
        if not model or len(model) > 160 or "\0" in model:
            raise ValueError("translation_route_model")
        harness = translation_harness(provider)
        runtime = resolve_fixed_task_runtime("card_translation")
    except Exception:
        raise EvidenceTranslationFailure(
            "translation_route_unavailable",
            retryable=False,
            provider=None,
            model=None,
            harness=None,
        ) from None

    try:
        result = translate_text(
            text,
            lang=locale,
            model_timeout_s=runtime.model_timeout_s,
            provider=provider,
            model=model,
        )
    except EvidenceTranslationFailure:
        raise
    except Exception as exc:
        failure = classify_content_translation_failure(exc)
        raise EvidenceTranslationFailure(
            failure.code,
            retryable=failure.retryable,
            provider=provider,
            model=model,
            harness=harness,
        ) from None

    try:
        return EvidenceTranslationResult(**result)
    except (TypeError, ValueError):
        raise EvidenceTranslationFailure(
            "translation_output_invalid",
            retryable=False,
            provider=provider,
            model=model,
            harness=harness,
        ) from None


def _store_error(exc: LifecycleStoreUnavailable) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "code": f"security_lifecycle_{exc.store}_store_unavailable",
            "store": exc.store,
        },
    )


def _not_found(exc: KeyError) -> HTTPException:
    code = str(exc.args[0]) if exc.args else "security_lifecycle_not_found"
    return HTTPException(status_code=404, detail={"code": code})


def _invalid(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": str(exc)})


def _case_fingerprint(case: dict) -> str:
    observation = case.get("observation")
    if observation is None:
        raise ValueError("source_observation_missing")
    return observation_fingerprint(observation)


@router.get("/cases")
def list_cases(
    ticker: str | None = Query(default=None),
    workflow_state: str | None = Query(default=None),
    relevance: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    proposal_type: str | None = Query(default=None),
    queue_bucket: str | None = Query(default=None),
    source_presence: Literal["present", "source_missing"] = Query(
        default="present"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    service: SecurityLifecycleReadService = Depends(
        get_security_lifecycle_read_service
    ),
):
    try:
        if (
            queue_bucket is not None
            and queue_bucket not in LIFECYCLE_QUEUE_BUCKETS
        ):
            raise ValueError("queue_bucket")
        return service.list_cases(
            ticker=ticker,
            workflow_state=workflow_state,
            relevance=relevance,
            event_type=event_type,
            proposal_type=proposal_type,
            queue_bucket=queue_bucket,
            source_presence=source_presence,
            limit=limit,
        )
    except LifecycleStoreUnavailable as exc:
        raise _store_error(exc) from None
    except ValueError as exc:
        raise _invalid(exc) from None


@router.get("/cases/{case_id}")
def get_case(
    case_id: str,
    service: SecurityLifecycleReadService = Depends(
        get_security_lifecycle_read_service
    ),
):
    try:
        return service.get_case(case_id)
    except LifecycleStoreUnavailable as exc:
        raise _store_error(exc) from None
    except KeyError as exc:
        raise _not_found(exc) from None


@router.get("/investigations/{run_id}")
def get_investigation(
    run_id: str,
    store: SecurityLifecycleInvestigationStore = Depends(
        get_security_lifecycle_store
    ),
):
    try:
        return store.get_investigation_run(run_id)
    except KeyError as exc:
        raise _not_found(exc) from None


@router.post("/cases/{case_id}/evidence")
def create_manual_evidence(
    case_id: str,
    body: ManualEvidenceRequest,
    service: SecurityLifecycleReadService = Depends(
        get_security_lifecycle_read_service
    ),
    store: SecurityLifecycleInvestigationStore = Depends(
        get_security_lifecycle_store
    ),
):
    try:
        case = service.get_case(case_id)
        require_db_write("security_lifecycle_add_evidence", {"case_id": case_id})
        evidence_id = add_manual_evidence(
            store=store,
            case_id=case_id,
            text=body.text,
            url=body.url,
            at=_utc_now(),
            case_identity=_case_identity(case),
        )
        return {"evidence_id": evidence_id}
    except LifecycleStoreUnavailable as exc:
        raise _store_error(exc) from None
    except KeyError as exc:
        raise _not_found(exc) from None
    except (LifecycleWritesUnavailable, ValueError) as exc:
        raise _invalid(exc) from None


@router.post("/evidence/{evidence_id}/translations")
def translate_evidence_route(
    evidence_id: str,
    body: EvidenceTranslationRequest,
    store: SecurityLifecycleInvestigationStore = Depends(
        get_security_lifecycle_store
    ),
):
    try:
        _, cached = prepare_evidence_translation(
            store,
            evidence_id=evidence_id,
            locale=body.locale,
        )
        if cached is not None:
            return {**cached, "cached": True}
        require_db_write(
            "security_lifecycle_translate_evidence",
            {"evidence_id": evidence_id, "locale": body.locale},
        )
        return translate_evidence(
            store,
            evidence_id=evidence_id,
            locale=body.locale,
            translator=_translate_evidence_text,
            at=_utc_now(),
        )
    except KeyError as exc:
        raise _not_found(exc) from None
    except EvidenceTranslationConflict as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code}) from None
    except EvidenceTranslationFailure as exc:
        raise HTTPException(status_code=502, detail=exc.detail()) from None
    except (LifecycleWritesUnavailable, ValueError) as exc:
        raise _invalid(exc) from None


@router.post("/cases/{case_id}/assessments")
def create_assessment(
    case_id: str,
    body: AssessmentRequest,
    service: SecurityLifecycleReadService = Depends(
        get_security_lifecycle_read_service
    ),
    store: SecurityLifecycleInvestigationStore = Depends(
        get_security_lifecycle_store
    ),
):
    try:
        case = service.get_case(case_id)
        fingerprint = _case_fingerprint(case)
        require_db_write(
            "security_lifecycle_create_assessment", {"case_id": case_id}
        )
        values = body.model_dump()
        citations = [item.model_dump() for item in body.citations]
        values.pop("citations")
        assessment_id = store.create_assessment(
            case_id=case_id,
            author="human",
            citations=citations,
            observation_fingerprint_sha256=fingerprint,
            at=_utc_now(),
            case_identity=_case_identity(case),
            **values,
        )
        return {"assessment_id": assessment_id}
    except LifecycleStoreUnavailable as exc:
        raise _store_error(exc) from None
    except KeyError as exc:
        raise _not_found(exc) from None
    except (LifecycleWritesUnavailable, TypeError, ValueError) as exc:
        raise _invalid(exc if isinstance(exc, ValueError) else ValueError(str(exc))) from None


@router.post("/assessments/{assessment_id}/accept")
def accept_assessment(
    assessment_id: str,
    service: SecurityLifecycleReadService = Depends(
        get_security_lifecycle_read_service
    ),
    store: SecurityLifecycleInvestigationStore = Depends(
        get_security_lifecycle_store
    ),
):
    try:
        draft = store.get_assessment(assessment_id)
        case = service.get_case(str(draft["case_id"]))
        fingerprint = _case_fingerprint(case)
        at = _utc_now()
        require_db_write(
            "security_lifecycle_accept_assessment",
            {"assessment_id": assessment_id},
        )
        assessment = store.accept_assessment(
            assessment_id,
            observation_fingerprint_sha256=fingerprint,
            acceptance_authority="human",
            at=at,
        )
        proposal_result = store.generate_action_proposals(
            case_id=str(draft["case_id"]),
            observation_fingerprint_sha256=fingerprint,
            sources_by_ticker=service.sources_by_ticker(),
            at=at,
        )
        return {"assessment": assessment, **proposal_result}
    except LifecycleStoreUnavailable as exc:
        raise _store_error(exc) from None
    except KeyError as exc:
        raise _not_found(exc) from None
    except (LifecycleWritesUnavailable, ValueError) as exc:
        raise _invalid(exc) from None


@router.post("/cases/{case_id}/acknowledgements")
def acknowledge_case(
    case_id: str,
    body: AcknowledgementRequest,
    service: SecurityLifecycleReadService = Depends(
        get_security_lifecycle_read_service
    ),
    store: SecurityLifecycleInvestigationStore = Depends(
        get_security_lifecycle_store
    ),
):
    try:
        case = service.get_case(case_id)
        fingerprint = _case_fingerprint(case)
        require_db_write(
            "security_lifecycle_acknowledge_case", {"case_id": case_id}
        )
        acknowledgement_id = store.acknowledge_case(
            case_id=case_id,
            reason=body.reason,
            note=body.note,
            author="human",
            observation_fingerprint_sha256=fingerprint,
            at=_utc_now(),
        )
        return {"acknowledgement_id": acknowledgement_id}
    except LifecycleStoreUnavailable as exc:
        raise _store_error(exc) from None
    except KeyError as exc:
        raise _not_found(exc) from None
    except (LifecycleWritesUnavailable, ValueError) as exc:
        raise _invalid(exc) from None


@router.post("/acknowledgements/{acknowledgement_id}/reopen")
def reopen_acknowledgement(
    acknowledgement_id: str,
    store: SecurityLifecycleInvestigationStore = Depends(
        get_security_lifecycle_store
    ),
):
    try:
        require_db_write(
            "security_lifecycle_reopen_acknowledgement",
            {"acknowledgement_id": acknowledgement_id},
        )
        store.reopen_acknowledgement(acknowledgement_id, at=_utc_now())
        return {"acknowledgement_id": acknowledgement_id, "status": "reopened"}
    except KeyError as exc:
        raise _not_found(exc) from None
    except (LifecycleWritesUnavailable, ValueError) as exc:
        raise _invalid(exc) from None


@router.post("/action-proposals/{proposal_id}/dismiss")
def dismiss_proposal(
    proposal_id: str,
    store: SecurityLifecycleInvestigationStore = Depends(
        get_security_lifecycle_store
    ),
):
    try:
        require_db_write(
            "security_lifecycle_dismiss_proposal", {"proposal_id": proposal_id}
        )
        return store.dismiss_proposal(proposal_id, at=_utc_now())
    except KeyError as exc:
        raise _not_found(exc) from None
    except (LifecycleWritesUnavailable, ValueError) as exc:
        raise _invalid(exc) from None
