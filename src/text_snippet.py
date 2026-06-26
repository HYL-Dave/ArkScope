"""Markdown → plain-text snippet for list/feed display.

A read-time display helper: turn a chunk of Markdown (e.g. Seeking Alpha
``body_markdown`` / ``summary``) into a clean, single-line plain-text snippet for
a feed list. This NEVER mutates stored data — the raw markdown remains the source
of truth for FTS, detail views, and agent evidence; only what the list *shows* is
cleaned here.

Deliberately NOT a Markdown renderer: no HTML is produced or trusted. Constructs
are flattened to their text (headings/emphasis/links/images/code/lists/tables),
raw HTML tags are stripped, well-known SA boilerplate lines (author byline,
analyst/disclosure, editor's note) are dropped, whitespace is compressed, and the
result is truncated on a word boundary so a token is never cut in half.
"""
from __future__ import annotations

import html
import re
from typing import Optional

# Boilerplate metadata lines that pollute SA feed snippets (matched at line start,
# after emphasis markers are stripped so ``*Author: …*`` is caught). Apostrophe is
# optional and may be straight (') or curly (’).
_BOILERPLATE_LINE = re.compile(
    r"\s*(?:author\b"
    r"|(?:analyst|seeking\s+alpha)[’']?s\s+disclosure\b"
    r"|disclosure\b"
    r"|editor[’']?s\s+note\b)",
    re.IGNORECASE,
)

_FENCE = re.compile(r"```[^\n]*\n?")                 # fenced-code fence + optional lang
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")       # ![alt](url) → alt
_LINK_INLINE = re.compile(r"\[([^\]]*)\]\([^)]*\)")  # [text](url) → text
_LINK_REF = re.compile(r"\[([^\]]*)\]\[[^\]]*\]")    # [text][id] → text
_HTML_TAG = re.compile(r"<[^>\n]+>")                 # <tag …> / autolink → removed
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_BOLD_ALT = re.compile(r"__([^_]+)__")
_ITALIC = re.compile(r"\*([^*\n]+)\*")
_ITALIC_ALT = re.compile(r"(?<![\w_])_([^_\n]+)_(?![\w_])")  # only true _emphasis_ pairs
_STRIKE = re.compile(r"~~([^~]+)~~")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_BLOCKQUOTE = re.compile(r"^\s{0,3}>\s?")
_LIST_MARKER = re.compile(r"^\s{0,3}(?:[-*+]\s+|\d+\.\s+)")
_TABLE_SEP = re.compile(r"^[\s|:.-]*$")              # |---|:--| separator rows
_REPEAT_PUNCT = re.compile(r"([!?])\1+")
_WS = re.compile(r"\s+")
_LEAD_SEP = re.compile(r"^[-—–:|·•,;\s]+")  # separators orphaned after a dropped title heading


def _norm(s: Optional[str]) -> str:
    """Normalize for title comparison: collapse whitespace, strip, lowercase."""
    return _WS.sub(" ", s or "").strip().lower()


def markdown_to_plain_snippet(
    text: Optional[str], *, limit: int = 200, drop_title: Optional[str] = None
) -> str:
    """Flatten ``text`` (Markdown) into a clean plain-text snippet of at most
    ``limit`` characters, truncated on a word boundary (``…`` appended). Returns
    ``""`` for empty/None input. Pure: does not touch any stored data.

    ``drop_title``: when given, leading whole lines that merely duplicate this
    title are dropped (SA bodies open with a ``# {title}`` heading that repeats
    the title shown above the snippet). Matched per-line and case/space-insensitive
    so a running sentence that happens to start with the title words is never cut —
    only a standalone title line is removed."""
    if not text:
        return ""

    s = text.replace("\r\n", "\n").replace("\r", "\n")
    s = html.unescape(s)                       # AT&amp;T → AT&T, &#37; → %, &nbsp; → space

    # span-level constructs (whole text, before line handling)
    s = _FENCE.sub("", s).replace("```", "")   # code fences (keep inner content)
    s = _IMAGE.sub(r"\1", s)                   # images → alt text (before links)
    s = _LINK_INLINE.sub(r"\1", s)
    s = _LINK_REF.sub(r"\1", s)
    s = _HTML_TAG.sub("", s)                   # never render/trust HTML
    s = s.replace("`", "")                     # inline code ticks
    s = _BOLD.sub(r"\1", s)
    s = _BOLD_ALT.sub(r"\1", s)
    s = _STRIKE.sub(r"\1", s)
    s = _ITALIC.sub(r"\1", s)
    s = _ITALIC_ALT.sub(r"\1", s)

    # line-level constructs: drop blanks/boilerplate/table-separators, strip markers
    out = []
    for line in s.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if _BOILERPLATE_LINE.match(stripped):
            continue
        if "|" in line and _TABLE_SEP.match(stripped):
            continue
        line = _HEADING.sub("", line)
        line = _BLOCKQUOTE.sub("", line)
        line = _LIST_MARKER.sub("", line)
        line = line.replace("|", " ")          # table cell separators → space
        out.append(line)

    if drop_title:                             # drop a leading heading that repeats the title
        dt = _norm(drop_title)
        while out and _norm(out[0]) == dt:
            out.pop(0)
    s = " ".join(out)

    s = _REPEAT_PUNCT.sub(r"\1", s)            # collapse !!!! / ???
    s = _WS.sub(" ", s).strip()
    s = _LEAD_SEP.sub("", s)                   # tidy separators orphaned by the dropped title

    if len(s) > limit:
        cut = s[:limit]
        sp = cut.rfind(" ")
        if sp > 0:
            cut = cut[:sp]
        s = cut.rstrip() + "…"
    return s
