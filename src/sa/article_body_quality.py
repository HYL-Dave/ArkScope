"""Reject observed non-article captures, without claiming textual completeness.

This is a conservative classifier for the capture format, not a content-length
heuristic or a substitute for comparing the capture with the source page.
"""

from __future__ import annotations

import re


ASSESSMENT_VERSION = 1
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
            plain = _plain_heading(block)
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
