"""Layer 5 finance-domain summary prompt + transcript renderer (P1.4 commit 5).

Two pure helpers:

  - :func:`render_layer_5_transcript`: renders a list of ProjectedMessage
    items into a single transcript string suitable for feeding to a
    summarizer LLM. Reasoning passthrough rule: thinking blocks render
    as labelled regions (``[REASONING (verbatim)]...[/REASONING]`` or
    ``[REASONING DROPPED]``) so the summarizer can SEE that the agent
    reasoned but is told (via the prompt rules) NOT to copy or interpret
    those regions. The labelling itself is what we control — we never
    paraphrase reasoning into plain assistant prose at projection or
    rendering time.

  - :func:`build_layer_5_system_prompt`: assembles the finance-domain
    system prompt (spec §3.6.1, seven sections + prompt rules). Returns
    a string. Tests lock the section structure.

Library-not-runner (spec §1.2 #1): no imports from
``src.agents.{anthropic,openai}_agent``. Prompts are plain strings —
provider-agnostic.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from .transcript import format_messages_as_transcript
from .types import ProjectedMessage


_SCRATCHPAD_MARKER = "<scratchpad_summary>"
_COMPACTION_MARKER = "<compaction_summary>"
_ANCHOR_MARKER = "<anchor>"


def render_layer_5_transcript(
    messages: Iterable[ProjectedMessage],
    *,
    prior_summary: Optional[str] = None,
) -> str:
    """Render projected messages as a transcript for the Layer 5 prompt.

    Reuses :func:`format_messages_as_transcript` for the per-item
    rendering (which already handles ``is_compaction_summary`` and
    ``is_anchor`` distinctly), then optionally prepends a
    ``[PRIOR SUMMARY]`` block when an existing compaction summary is
    being absorbed into a new one.

    The transcript is read-only: existing summaries are reproduced
    verbatim under the ``[PRIOR SUMMARY]`` tag so the summarizer treats
    them as ground truth and incorporates them rather than re-deriving.
    """
    body = format_messages_as_transcript(messages)
    if prior_summary and prior_summary.strip():
        # Strip any wrapping marker so we don't double-tag.
        clean = prior_summary
        for marker in (_SCRATCHPAD_MARKER, _COMPACTION_MARKER):
            if clean.startswith(marker):
                clean = clean[len(marker):].lstrip("\n")
                break
        return f"[PRIOR SUMMARY]:\n{clean}\n\n{body}"
    return body


_LAYER_5_SYSTEM_PROMPT = """\
You are summarising the prior turns of a finance research conversation
so the agent can continue with a much shorter prompt. The summary will
be inserted in place of the older messages and read by the same agent
on the next turn.

WRITE THE SUMMARY UNDER THESE SEVEN SECTIONS, IN THIS ORDER:

  1. Active context — current ticker(s), the user's open question, the
     agent's stated intent / current strategy.
  2. Tool calls made — for each notable tool call: tool_name, key
     args summary, key result fields. If a result was overflowed
     (look for ``[overflow_record=<id>]`` markers), note the
     ``record_id`` so the agent can re-fetch.
  3. Findings — facts the agent has confirmed, with source markers
     when available. Do not interpret beyond what the transcript
     shows.
  4. Open hypotheses / pending checks — what is still being
     investigated.
  5. Errors / data gaps — any partial-failure messages, especially
     ``data_quality.errors`` lines from tool outputs. Preserve them
     verbatim if present.
  6. Subagent results — any return values from delegate_to_subagent
     calls that should not be lost.
  7. Pending tool calls — tool calls planned but not yet issued.

PROMPT RULES — STRICTLY FOLLOWED:

  - Stay within 2000 words; aim for 1000.
  - PRESERVE ALL ``record_id`` values exactly as shown in the
    transcript (do not abbreviate or paraphrase ids).
  - PRESERVE ALL ``data_quality.errors`` lines verbatim.
  - If a ``[PRIOR SUMMARY]`` block appears at the top of the
    transcript, treat it as ground truth and INCORPORATE its content
    into the new summary — do not duplicate it, do not contradict it,
    and do not drop facts from it.
  - DO NOT reproduce ``[REASONING (verbatim)]`` blocks. They are
    shown to you so you know the agent reasoned, but reasoning text
    must NOT be copied into the summary or treated as confirmed
    findings. Only conclusions explicitly stated by the assistant
    (outside reasoning blocks) qualify as findings.
  - If a ``[REASONING DROPPED]`` marker appears, mention only that
    a redacted reasoning step occurred at that point — do not invent
    its content.
  - Output plain text only. No markdown headers, no JSON, no XML.
  - Keep ``[ANCHOR]`` content verbatim if present (it is current
    state, not history).
"""


def build_layer_5_system_prompt() -> str:
    """Return the finance-domain Layer 5 summarizer system prompt.

    Static template — same for every call, so the cheap-tier LLM caches
    it. Section structure locked by
    :class:`TestLayer5SummaryPrompt::test_seven_sections_present`.
    """
    return _LAYER_5_SYSTEM_PROMPT


def build_layer_5_user_prompt(transcript: str) -> str:
    """Build the user-side prompt that delivers the transcript.

    Kept separate from the system prompt so the system prompt stays
    cacheable across sessions.
    """
    return (
        "Summarise the following transcript. Follow the system rules "
        "exactly. The summary will replace these messages in the agent's "
        "next prompt — do not omit anything load-bearing.\n\n"
        f"---TRANSCRIPT START---\n{transcript}\n---TRANSCRIPT END---"
    )


# ---------------------------------------------------------------------------
# Output cap helpers (commit 5 medium #5: cap in code, not just prompt)
# ---------------------------------------------------------------------------


# Belt-and-braces dual cap: word count first (matches the prompt's
# "≤2000 words"), then char cap as a backstop for pathological tokens.
LAYER_5_WORD_CAP = 2000
LAYER_5_CHAR_CAP = 12_000


_CHAR_CAP_MARKER = f" [TRUNCATED:char_cap={LAYER_5_CHAR_CAP}]"
_WORD_CAP_MARKER = f" [TRUNCATED:word_cap={LAYER_5_WORD_CAP}]"


def cap_summary(summary: str) -> str:
    """Hard-cap the LLM-returned summary in code; the prompt asks for
    ≤2000 words but we cannot trust the model to obey. If either the
    word or char cap is exceeded, truncate and append a marker so a
    downstream reader knows the cut happened.

    The char cap is hard: marker bytes are reserved BEFORE truncation so
    ``len(cap_summary(s)) <= LAYER_5_CHAR_CAP`` for every input. The word
    cap is approximate (the marker counts as one word, so capped output
    has ~``LAYER_5_WORD_CAP + 1`` words) — words are a lossy unit anyway.
    """
    if not isinstance(summary, str):
        return ""
    words = summary.split()
    if len(words) > LAYER_5_WORD_CAP:
        summary = " ".join(words[:LAYER_5_WORD_CAP]) + _WORD_CAP_MARKER
    if len(summary) > LAYER_5_CHAR_CAP:
        budget = LAYER_5_CHAR_CAP - len(_CHAR_CAP_MARKER)
        summary = summary[:budget] + _CHAR_CAP_MARKER
    return summary


# ---------------------------------------------------------------------------
# Marker helpers
# ---------------------------------------------------------------------------


def wrap_compaction_summary(summary_text: str) -> str:
    """Wrap a Layer 5 summary in the canonical ``<compaction_summary>``
    marker. Idempotent: if the input already starts with the marker, the
    text is returned unchanged."""
    if summary_text.startswith(_COMPACTION_MARKER):
        return summary_text
    stripped = summary_text.strip()
    return f"{_COMPACTION_MARKER}\n{stripped}"


def wrap_anchor(anchor_text: str) -> str:
    """Wrap a Layer 6 anchor block in the canonical ``<anchor>`` marker."""
    if anchor_text.startswith(_ANCHOR_MARKER):
        return anchor_text
    stripped = anchor_text.strip()
    return f"{_ANCHOR_MARKER}\n{stripped}"