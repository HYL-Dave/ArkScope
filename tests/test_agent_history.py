"""C-2c gap #2: deterministic proof of the OpenAI multi-turn input construction.

The live OpenAI smoke is flaky (SDK streaming hiccups + slow tools), so per
gpt-5.5's gap #2 ("mock SDK regression OR low-cost live smoke") this pins the
exact `input` the OpenAI Agents SDK Runner receives: a bare question string with
no history (single-turn, unchanged), or a message-list (history + this turn)
when prior context exists. Mirrors the Anthropic `messages=[*history, current]`
seeding, which was verified live.
"""

from __future__ import annotations

from src.agents.openai_agent.agent import _compose_stream_input


def test_no_history_passes_bare_question_string():
    assert _compose_stream_input([], "最近 SA 對 SMCI 的焦點？") == "最近 SA 對 SMCI 的焦點？"


def test_history_passes_message_list_with_current_turn_last():
    history = [
        {"role": "user", "content": "最近 SA 對 SMCI 的焦點？"},
        {"role": "assistant", "content": "SMCI: 3 看多 2 看空。"},
    ]
    assert _compose_stream_input(history, "它的估值現在合理嗎？") == [
        {"role": "user", "content": "最近 SA 對 SMCI 的焦點？"},
        {"role": "assistant", "content": "SMCI: 3 看多 2 看空。"},
        {"role": "user", "content": "它的估值現在合理嗎？"},  # current turn appended last
    ]
