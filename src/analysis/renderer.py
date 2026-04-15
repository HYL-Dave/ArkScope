"""Thin renderer facade for Phase D analysis artifacts."""

from __future__ import annotations

from html import escape
from pathlib import Path
from string import Template
from typing import Any, Dict, Optional

from .contracts import IntegrityResult, RenderedReport

_TEMPLATES_DIR = Path(__file__).with_name("templates")


def _load_template(name: str) -> Template:
    """Load a renderer template from the local templates directory."""
    return Template((_TEMPLATES_DIR / name).read_text(encoding="utf-8"))


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


def _render_strategy_sections_html(strategies: Dict[str, Any]) -> str:
    """Render compact per-strategy sections for the HTML report."""
    blocks = []
    for name, section in strategies.items():
        parts = [
            f"<h2>{escape(name.title())}</h2>",
            f"<p>Status: {escape(str(section.get('status')))}</p>",
        ]
        score = section.get("score")
        if score is not None:
            parts.append(f"<p>Score: {score:.1f}</p>")
        parts.extend(
            f"<p>{escape(str(line))}</p>" for line in section.get("summary_lines", [])
        )
        parts.extend(
            f"<p>Signal: {escape(str(signal))}</p>" for signal in section.get("signals", [])
        )
        parts.extend(
            f"<p>Risk: {escape(str(risk))}</p>" for risk in section.get("risks", [])
        )
        blocks.append("".join(parts))
    return "".join(blocks)


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
    context_summary = artifact.context_summary

    if fmt == "html":
        degradation_html = (
            "<h2>Degradation</h2>" + "".join(f"<p>{escape(item)}</p>" for item in degradation_summary)
            if degradation_summary else ""
        )
        content = _load_template("report_html.tpl").safe_substitute(
            ticker=escape(str(artifact.request.ticker)),
            action=escape(str(decision_action)),
            summary=escape(str(summary)),
            mode=escape(str(context_summary.get("mode", ""))),
            depth=escape(str(context_summary.get("depth", ""))),
            backend_type=escape(str(context_summary.get("provider_status", {}).get("backend_type", ""))),
            news_count=escape(str(context_summary.get("news_count", 0))),
            social_count=escape(str(context_summary.get("social_count", 0))),
            strategy_sections=_render_strategy_sections_html(strategy_sections),
            degradation_section=degradation_html,
        )
    else:
        degradation_md = ""
        if degradation_summary:
            degradation_md = "\n".join(
                [
                    "## Degradation",
                    *[f"- {item}" for item in degradation_summary],
                ]
            )
        content = _load_template("report_markdown.tpl").safe_substitute(
            ticker=str(artifact.request.ticker),
            action=str(decision_action),
            summary=str(summary),
            mode=str(context_summary.get("mode", "")),
            depth=str(context_summary.get("depth", "")),
            backend_type=str(context_summary.get("provider_status", {}).get("backend_type", "")),
            news_count=str(context_summary.get("news_count", 0)),
            social_count=str(context_summary.get("social_count", 0)),
            strategy_sections=_render_strategy_sections_markdown(strategy_sections),
            degradation_section=degradation_md,
        ).strip() + "\n"

    return RenderedReport(
        format="html" if fmt == "html" else "markdown",
        content=content,
        metadata={
            "integrity_status": integrity_result.status,
            "mode": artifact.request.mode,
            "depth": artifact.request.depth,
        },
    )
