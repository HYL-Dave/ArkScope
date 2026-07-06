"""Track A: personalization section in the shared system prompt."""

from src.agents.shared.prompts import build_system_prompt

_HEADER = "─── INVESTOR PROFILE / ASSISTANT STANCE ───"


def test_empty_context_keeps_system_prompt_byte_identical():
    assert build_system_prompt() == build_system_prompt(personalization_context="")
    assert build_system_prompt("fresh") == build_system_prompt(
        "fresh", personalization_context=""
    )
    assert build_system_prompt(personalization_context="   ") == build_system_prompt()
    assert _HEADER not in build_system_prompt()


def test_context_appends_after_base_prompt():
    base = build_system_prompt()
    block = "[Investor Profile]\nPrimary preset: growth\n\n[Assistant Stance]\nMode: complementary"
    out = build_system_prompt(personalization_context=block)
    assert _HEADER in out
    assert block in out
    # appended AFTER the base content, never prepended/interleaved
    assert out.index(_HEADER) >= len(base.rstrip("\n")) - len("\n")
    # freshness + personalization co-exist, freshness first
    both = build_system_prompt("FRESHNESS-X", personalization_context=block)
    assert both.index("FRESHNESS-X") < both.index(_HEADER)
