"""Thin renderer facade for Phase D analysis artifacts."""

from __future__ import annotations

from html import escape
from typing import Any, Dict, Optional

from .contracts import IntegrityResult, RenderedReport


def _render_strategy_sections_markdown(strategies: Dict[str, Any]) -> str:
    """Render compact per-strategy sections for the markdown report."""
    blocks = []
    for name, section in strategies.items():
        lines = [f"## {name.title()}", f"- status: {section.get('status')}"]
        score = section.get("score")
        if score is not None:
            lines.append(f"- score: {score:.1f}")
        for summary_line in section.get("summary_lines", []):
            lines.append(f"- {summary_line}")
        for signal in section.get("signals", []):
            lines.append(f"- signal: {signal}")
        for risk in section.get("risks", []):
            lines.append(f"- risk: {risk}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def render_report(
    integrity_result: IntegrityResult,
    *,
    fmt: str = "markdown",
) -> Optional[RenderedReport]:
    """Render a minimal fallback report from an integrity-checked artifact."""
    artifact = integrity_result.artifact
    summary = artifact.final_decision.get("summary") or artifact.report_sections.get("executive_summary") or ""
    if not summary:
        return None

    decision_action = artifact.final_decision.get("action", "unknown")
    strategy_sections = artifact.report_sections.get("strategies", {})
    degradation_summary = artifact.degradation_summary

    if fmt == "html":
        strategy_html = "".join(
            f"<h2>{escape(name.title())}</h2>"
            f"<p>Status: {escape(str(section.get('status')))}</p>"
            + (
                f"<p>Score: {section.get('score'):.1f}</p>"
                if section.get("score") is not None else ""
            )
            + "".join(f"<p>{escape(str(line))}</p>" for line in section.get("summary_lines", []))
            for name, section in strategy_sections.items()
        )
        degradation_html = ""
        if degradation_summary:
            degradation_html = "<h2>Degradation</h2>" + "".join(
                f"<p>{escape(item)}</p>" for item in degradation_summary
            )
        content = (
            "<html><body>"
            f"<h1>{artifact.request.ticker}</h1>"
            f"<p>Action: {escape(str(decision_action))}</p>"
            f"<p>{summary}</p>"
            f"{strategy_html}"
            f"{degradation_html}"
            "</body></html>"
        )
    else:
        parts = [
            f"# {artifact.request.ticker}",
            "",
            f"Action: {decision_action}",
            "",
            summary,
        ]
        if strategy_sections:
            parts.extend(["", _render_strategy_sections_markdown(strategy_sections)])
        if degradation_summary:
            parts.extend(
                [
                    "",
                    "## Degradation",
                    *[f"- {item}" for item in degradation_summary],
                ]
            )
        content = "\n".join(parts).strip() + "\n"

    return RenderedReport(
        format="html" if fmt == "html" else "markdown",
        content=content,
        metadata={
            "integrity_status": integrity_result.status,
            "mode": artifact.request.mode,
            "depth": artifact.request.depth,
        },
    )
