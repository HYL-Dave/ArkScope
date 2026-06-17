"""Model-tier defaults + opus-4-8 capability (user/gpt-5.5 decision 2026-06-18).

Tiers (Option 1): cheaper default + frontier advanced. Anthropic advanced moves
to Opus 4.8, which REQUIRES capability-table entries (max output / effort /
adaptive thinking) — not just a string swap. Conservative: NOT added to
_COMPACTION_MODELS (4.8 server-side compaction unverified; advanced tier is used
for single-call synthesis, not long conversations).
"""

from __future__ import annotations

from src.agents.anthropic_agent.agent import (
    _get_model_max_output,
    _supports_adaptive_thinking,
    _supports_effort,
)
from src.agents.config import AgentConfig


def test_opus_4_8_capability_table_present():
    assert _get_model_max_output("claude-opus-4-8") == 128000
    assert _supports_adaptive_thinking("claude-opus-4-8") is True
    assert _supports_effort("claude-opus-4-8") is True


def test_opus_4_7_capability_still_present():  # regression: don't drop the legacy model
    assert _get_model_max_output("claude-opus-4-7") == 128000
    assert _supports_effort("claude-opus-4-7") is True


def test_default_model_tiers_option1():
    c = AgentConfig()
    assert c.anthropic_model == "claude-sonnet-4-6"       # cheaper default
    assert c.anthropic_model_advanced == "claude-opus-4-8"  # frontier advanced
    assert c.openai_model == "gpt-5.4"
    assert c.openai_model_advanced == "gpt-5.5"
