"""Closed policy contract for guided Investor Profile calibration."""

from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from src.investor_profile import normalize_profile_payload


EXPECTED_TOPICS = (
    ("loss_response", ("risk_appetite", "drawdown_tolerance_pct")),
    ("financial_capacity", ("risk_capacity",)),
    ("time_horizon", ("holding_horizon",)),
    ("single_position_limit", ("concentration_limit_pct",)),
    ("risk_avoidances", ("avoidances",)),
    ("behavioral_patterns", ("behavioral_flags",)),
    ("investment_approach", ("primary_preset", "preferred_edge")),
    ("assistant_style", ("default_stance",)),
)

EXPECTED_OPENING = (
    "Suppose an important holding falls 18% over a short period while its "
    "long-term thesis is not clearly broken. What would you usually do?"
)


def _policy():
    import src.investor_profile_calibration_policy as policy

    return policy


def test_catalog_order_and_topic_ids_are_exact():
    policy = _policy()

    assert tuple((topic.id, topic.fields) for topic in policy.CALIBRATION_TOPICS) == EXPECTED_TOPICS
    assert policy.CALIBRATION_TOPIC_IDS == tuple(topic_id for topic_id, _fields in EXPECTED_TOPICS)


def test_catalog_fields_and_deny_list_exactly_partition_profile_body():
    from src.api.routes.investor_profile import InvestorProfileBody

    policy = _policy()
    catalog_fields = {
        field for topic in policy.CALIBRATION_TOPICS for field in topic.fields
    }
    denied = policy.NEVER_PROPOSABLE_FIELDS

    assert len(catalog_fields) == 10
    assert denied == frozenset({"enabled", "freeform_notes", "skill_mode"})
    assert catalog_fields.isdisjoint(denied)
    assert catalog_fields | denied == set(InvestorProfileBody.model_fields)


def test_covered_topics_derive_only_the_reviewed_field_union():
    policy = _policy()
    cases = (
        ((), ()),
        (("loss_response",), ("risk_appetite", "drawdown_tolerance_pct")),
        (
            ("assistant_style", "investment_approach"),
            ("primary_preset", "preferred_edge", "default_stance"),
        ),
        (
            ("not_a_catalog_topic", "financial_capacity", "financial_capacity"),
            ("risk_capacity",),
        ),
    )

    for covered_topics, expected_fields in cases:
        assert policy.fields_for_topics(covered_topics) == expected_fields


def test_clamp_preserves_partial_patch_and_normalizes_only_legal_fields():
    policy = _policy()
    current = normalize_profile_payload(
        {
            "risk_appetite": 4,
            "drawdown_tolerance_pct": 12,
            "primary_preset": "value",
            "preferred_edge": ["quality"],
            "default_stance": "neutral",
        }
    )
    patch, rejected = policy.clamp_proposal_patch(
        {
            "preferred_edge": [" growth ", "growth", "quality"],
            "risk_appetite": "7",
        },
        covered_topics=("loss_response", "investment_approach"),
        current_profile=current,
    )

    assert patch == {
        "risk_appetite": 7,
        "preferred_edge": ["growth", "quality"],
    }
    assert tuple(patch) == ("risk_appetite", "preferred_edge")
    assert rejected == ()
    assert "drawdown_tolerance_pct" not in patch
    assert "primary_preset" not in patch
    assert "risk_mismatch" not in patch


def test_clamp_drops_unknown_uncovered_denied_and_derived_fields_without_values():
    policy = _policy()
    secret_value = "do not persist this rejected value"
    patch, rejected = policy.clamp_proposal_patch(
        {
            "risk_appetite": 6,
            "risk_capacity": 9,
            "enabled": True,
            "freeform_notes": secret_value,
            "skill_mode": "suggest_only",
            "risk_mismatch": "none",
            "unknown_agent_field": {"value": secret_value},
        },
        covered_topics=("loss_response",),
        current_profile=normalize_profile_payload({}),
    )

    assert patch == {"risk_appetite": 6}
    assert rejected == tuple(
        sorted(
            {
                "enabled",
                "freeform_notes",
                "risk_capacity",
                "risk_mismatch",
                "skill_mode",
                "unknown_agent_field",
            }
        )
    )
    assert all(isinstance(field, str) for field in rejected)
    assert secret_value not in json.dumps(rejected)


def test_clamp_with_no_legal_fields_returns_no_proposal():
    policy = _policy()
    cases = (
        (None, ()),
        ({}, ()),
        ({"enabled": True}, ("enabled",)),
        ({"risk_capacity": 5, "risk_mismatch": "none"}, ("risk_capacity", "risk_mismatch")),
    )

    for raw_patch, expected_rejected in cases:
        patch, rejected = policy.clamp_proposal_patch(
            raw_patch,
            covered_topics=("loss_response",),
            current_profile=normalize_profile_payload({}),
        )
        assert patch is None
        assert rejected == expected_rejected


def test_next_topic_accepts_any_uncovered_catalog_topic():
    policy = _policy()

    for topic_id in policy.CALIBRATION_TOPIC_IDS:
        covered = tuple(candidate for candidate in policy.CALIBRATION_TOPIC_IDS if candidate != topic_id)
        assert policy.validate_addressed_topic(topic_id, topic_id) == topic_id
        assert policy.validate_next_topic(topic_id, covered_topics=covered) == topic_id
    assert policy.validate_next_topic(None, covered_topics=()) is None


def test_next_topic_rejects_unknown_and_already_covered_topics():
    policy = _policy()

    invalid_next_cases = (
        ("unknown_topic", ()),
        ("loss_response", ("loss_response",)),
        ("assistant_style", ("loss_response", "assistant_style")),
    )
    for next_topic_id, covered_topics in invalid_next_cases:
        with pytest.raises(ValueError, match="calibration_catalog_validation_failed"):
            policy.validate_next_topic(next_topic_id, covered_topics=covered_topics)

    for addressed_topic_id, current_topic_id in (
        ("unknown_topic", "loss_response"),
        ("financial_capacity", "loss_response"),
        ("loss_response", "unknown_topic"),
    ):
        with pytest.raises(ValueError, match="calibration_catalog_validation_failed"):
            policy.validate_addressed_topic(addressed_topic_id, current_topic_id)


def test_opening_prompt_catalog_is_versioned_and_exact():
    policy = _policy()

    assert policy.OPENING_PROMPT_ID == "loss_response.opening.v1"
    assert policy.OPENING_PROMPTS == {"loss_response.opening.v1": EXPECTED_OPENING}
    assert policy.OPENING_PROMPTS[policy.OPENING_PROMPT_ID].encode() == EXPECTED_OPENING.encode()


def test_catalog_serialization_preserves_backend_display_order():
    policy = _policy()
    payload = [asdict(topic) for topic in policy.CALIBRATION_TOPICS]

    assert payload == [
        {"id": topic_id, "fields": fields}
        for topic_id, fields in EXPECTED_TOPICS
    ]
    round_trip = json.loads(json.dumps(payload))
    assert [item["id"] for item in round_trip] == [topic_id for topic_id, _fields in EXPECTED_TOPICS]
    assert [item["fields"] for item in round_trip] == [list(fields) for _topic_id, fields in EXPECTED_TOPICS]
