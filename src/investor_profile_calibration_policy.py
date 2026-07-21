"""Pure topic and proposal policy for guided Investor Profile calibration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from src.investor_profile import InvestorProfile, normalize_profile_payload


@dataclass(frozen=True)
class CalibrationTopic:
    id: str
    fields: tuple[str, ...]


CALIBRATION_TOPICS = (
    CalibrationTopic("loss_response", ("risk_appetite", "drawdown_tolerance_pct")),
    CalibrationTopic("financial_capacity", ("risk_capacity",)),
    CalibrationTopic("time_horizon", ("holding_horizon",)),
    CalibrationTopic("single_position_limit", ("concentration_limit_pct",)),
    CalibrationTopic("risk_avoidances", ("avoidances",)),
    CalibrationTopic("behavioral_patterns", ("behavioral_flags",)),
    CalibrationTopic("investment_approach", ("primary_preset", "preferred_edge")),
    CalibrationTopic("assistant_style", ("default_stance",)),
)

CALIBRATION_TOPIC_IDS = tuple(topic.id for topic in CALIBRATION_TOPICS)
NEVER_PROPOSABLE_FIELDS = frozenset({"enabled", "freeform_notes", "skill_mode"})
OPENING_PROMPTS = {
    "loss_response.opening.v1": (
        "Suppose an important holding falls 18% over a short period while its "
        "long-term thesis is not clearly broken. What would you usually do?"
    ),
}
OPENING_PROMPT_ID = "loss_response.opening.v1"


def fields_for_topics(topic_ids: Iterable[str]) -> tuple[str, ...]:
    """Return the reviewed field union in backend catalog order."""
    selected = set(topic_ids)
    return tuple(
        field
        for topic in CALIBRATION_TOPICS
        if topic.id in selected
        for field in topic.fields
    )


def clamp_proposal_patch(
    raw_patch: Mapping[str, Any] | None,
    *,
    covered_topics: Iterable[str],
    current_profile: InvestorProfile,
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Normalize only covered fields without expanding a partial proposal."""
    source = dict(raw_patch or {})
    legal_fields = fields_for_topics(covered_topics)
    legal_field_set = set(legal_fields)
    rejected_fields = tuple(sorted(str(field) for field in source if field not in legal_field_set))
    legal_patch = {field: source[field] for field in legal_fields if field in source}
    if not legal_patch:
        return None, rejected_fields

    normalized = normalize_profile_payload(legal_patch, existing=current_profile)
    patch = {field: getattr(normalized, field) for field in legal_fields if field in legal_patch}
    return patch, rejected_fields


def validate_addressed_topic(addressed_topic_id: str, current_topic_id: str) -> str:
    """Require the model to address the server-selected catalog topic."""
    if current_topic_id not in CALIBRATION_TOPIC_IDS or addressed_topic_id != current_topic_id:
        raise ValueError(
            "calibration_catalog_validation_failed: addressed topic does not match current topic"
        )
    return addressed_topic_id


def validate_next_topic(
    next_topic_id: str | None,
    *,
    covered_topics: Iterable[str],
) -> str | None:
    """Accept only a known topic that remains uncovered after the turn."""
    if next_topic_id is None:
        return None
    if next_topic_id not in CALIBRATION_TOPIC_IDS or next_topic_id in set(covered_topics):
        raise ValueError(
            "calibration_catalog_validation_failed: next topic is unknown or already covered"
        )
    return next_topic_id
