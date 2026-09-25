"""Reject observed non-article captures, without claiming textual completeness.

This is a conservative classifier for the capture format, not a content-length
heuristic or a substitute for comparing the capture with the source page.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from markdown_it import MarkdownIt


ASSESSMENT_VERSION = 2
_MARKDOWN = MarkdownIt("commonmark")
_DISCLOSURE = re.compile(
    r"^(?:analyst|seeking alpha)'s disclosure\s*(?::|$)",
    re.IGNORECASE,
)
_DISCLOSURE_SENTENCES = (
    "I/we have no stock, option or similar derivative position in any of the "
    "companies mentioned, and no plans to initiate any such positions within the next 72 hours.",
    "I wrote this article myself, and it expresses my own opinions.",
    "I am not receiving compensation for it (other than from Seeking Alpha).",
    "I am not receiving compensation for it.",
    "I have no business relationship with any company whose stock is mentioned in this article.",
    "Past performance is no guarantee of future results.",
    "No recommendation or advice is being given as to whether any investment is suitable "
    "for a particular investor.",
    "Any views or opinions expressed above may not reflect those of Seeking Alpha as a whole.",
    "Seeking Alpha is not a licensed securities dealer, broker or US investment adviser "
    "or investment bank.",
    "Our analysts are third party authors that include both professional investors and "
    "individual investors who may not be licensed or certified by any institute or regulatory body.",
)
# Match whole observed boilerplate paragraphs; any added prose remains narrative.
_DISCLOSURE_PARAGRAPH = re.compile(
    r"(?:(?:" + "|".join(re.escape(sentence) for sentence in _DISCLOSURE_SENTENCES)
    + r")(?:\s+|$))+",
    re.IGNORECASE,
)
_COMMENT_HEADING = re.compile(r"^comments\s*\([\d,]+\)\s*$", re.IGNORECASE)
_COMMENT_SORT_CONTROL = re.compile(
    r"sort (?:by|replies)(?: (?:newest|oldest|most liked))?", re.IGNORECASE,
)


def _plain_heading(text: str) -> str:
    return text.strip().lstrip("#").strip().strip("*_ ").replace("\u2019", "'")


def narrative_text(block: str) -> str:
    """References remain in stored Markdown, but cannot establish prose/evidence."""
    if "[" not in block and "<" not in block:
        return block
    parts = []
    heading = ""
    for token in _MARKDOWN.parse(block):
        if token.type == "heading_open":
            heading = "#" * int(token.tag[1:]) + " "
        elif token.type == "heading_close":
            heading = ""
        elif token.type == "inline":
            text = _narrative_inline(token.children or [])
            if text.strip():
                parts.append(heading + text)
        elif token.type in {"fence", "code_block"}:
            parts.append(token.content)
    return "\n".join(parts)


def _narrative_inline(tokens):
    parts = []
    depth = 0
    url_label = False
    reference_seen = False
    outside_reference = False
    for index, token in enumerate(tokens):
        if token.type == "link_open":
            depth += 1
            reference_seen = True
            label = []
            for child in tokens[index + 1:]:
                if child.type == "link_close":
                    break
                if child.type in {"text", "code_inline"}:
                    label.append(child.content)
            try:
                parsed = urlsplit("".join(label).strip())
                url_label = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
            except ValueError:
                url_label = False
        elif token.type == "link_close":
            depth -= 1
            url_label = False
        elif token.type == "image":
            reference_seen = True
        elif token.type in {"text", "code_inline"}:
            if not url_label:
                parts.append(token.content)
            if depth == 0 and any(character.isalnum() for character in token.content):
                outside_reference = True
        elif token.type in {"softbreak", "hardbreak"}:
            parts.append("\n")
    if reference_seen and not outside_reference:
        return ""
    text = "".join(parts)
    stripped = text.strip()
    if stripped == "[Embedded visual or media not captured]" or (
        stripped.startswith("[Image reference unavailable: ") and stripped.endswith("]")
        and "\n" not in stripped
    ):
        return ""
    return text


def assess_body(body: str | None, *, title: str = "") -> dict:
    """`available` means retained narrative, never a verified complete article."""
    reason = None
    status = "available"
    if not isinstance(body, str) or not body.strip():
        status, reason = "not_captured", "sa_article_body_missing"
    else:
        blocks = re.split(r"\n\s*\n", body.strip())
        content = []
        disclosures = False
        for index, block in enumerate(blocks):
            block = narrative_text(block)
            plain = _plain_heading(block)
            if not plain:
                continue
            if _DISCLOSURE.match(plain) or _DISCLOSURE_PARAGRAPH.fullmatch(" ".join(plain.split())):
                disclosures = True
                continue
            if (plain.casefold() == _plain_heading(title or "").casefold()
                    or (index == 0 and not title and re.fullmatch(r"#\s+[^\n]+", block))
                    or re.fullmatch(r"author\s*:[^\n]+", plain, re.IGNORECASE)):
                continue
            content.append(block.strip())
        first = _plain_heading(content[0]) if content else ""
        if _COMMENT_HEADING.match(first) or (
            first.casefold() == "comments" and len(content) > 1
            and _COMMENT_SORT_CONTROL.fullmatch(" ".join(_plain_heading(content[1]).split()))
        ):
            status, reason = "unusable", "sa_article_body_comment_thread"
        elif not any(not re.fullmatch(r"#{1,6}\s+[^\n]+", block) for block in content):
            status = "unusable"
            reason = "sa_article_body_disclosure_only" if disclosures else "sa_article_body_metadata_only"
    return {"status": status, "reason_code": reason,
            "assessment_version": ASSESSMENT_VERSION, "completeness": "not_verified"}


def usable_body(body: str | None, *, title: str = "") -> str:
    return body if assess_body(body, title=title)["status"] == "available" else ""
