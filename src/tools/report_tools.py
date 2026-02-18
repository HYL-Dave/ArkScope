"""
Report tool functions (3 tools).

24. save_report    — Save an agent-generated research report
25. list_reports   — List saved research reports
26. get_report     — Retrieve a saved research report
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

logger = logging.getLogger(__name__)

# Reports directory (relative to project root)
_REPORTS_DIR = "data/reports"


def _ensure_reports_dir(base: Path) -> Path:
    """Ensure the reports directory exists."""
    reports_dir = base / _REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def _generate_filename(tickers: List[str], title: str) -> str:
    """Generate a unique filename for a report."""
    today = date.today().isoformat()
    ticker_str = "_".join(t.upper() for t in tickers[:3])
    # Short hash for uniqueness
    content_hash = hashlib.md5(
        f"{title}{datetime.now().isoformat()}".encode()
    ).hexdigest()[:8]
    return f"{today}_{ticker_str}_{content_hash}.md"


def save_report(
    dal: "DataAccessLayer",
    title: str,
    tickers: List[str],
    report_type: str,
    summary: str,
    content: str,
    conclusion: Optional[str] = None,
    confidence: Optional[float] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    tools_used: Optional[List[str]] = None,
    tool_calls: Optional[int] = None,
    duration_seconds: Optional[float] = None,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
) -> dict:
    """
    Save an agent-generated research report.

    Writes full Markdown content to data/reports/ and metadata to DB.

    Args:
        dal: DataAccessLayer instance
        title: Report title (e.g. "AFRM Entry Analysis")
        tickers: List of analyzed tickers
        report_type: Type (entry_analysis, sector_review, earnings_review, etc.)
        summary: 1-2 sentence conclusion
        content: Full Markdown report content
        conclusion: Trading conclusion (BUY, HOLD, SELL, WATCH, NEUTRAL)
        confidence: Confidence score 0-1
        provider: LLM provider (openai, anthropic)
        model: Model used (claude-opus-4-6, gpt-5.2)
        tools_used: List of tool names used during analysis
        tool_calls: Total number of tool calls
        duration_seconds: Analysis duration
        tokens_in: Input tokens consumed
        tokens_out: Output tokens consumed

    Returns:
        Dict with: id, file_path, title, created_at
    """
    # 1. Write Markdown file
    if dal._base:
        reports_dir = _ensure_reports_dir(dal._base)
    else:
        reports_dir = Path(_REPORTS_DIR)
        reports_dir.mkdir(parents=True, exist_ok=True)

    filename = _generate_filename(tickers, title)
    file_path = reports_dir / filename
    rel_path = f"{_REPORTS_DIR}/{filename}"

    # Build Markdown with front matter
    md_lines = [
        f"# {title}",
        "",
        f"**Date**: {date.today().isoformat()}",
        f"**Tickers**: {', '.join(t.upper() for t in tickers)}",
        f"**Type**: {report_type}",
    ]
    if conclusion:
        md_lines.append(f"**Conclusion**: {conclusion}")
    if confidence is not None:
        md_lines.append(f"**Confidence**: {confidence:.0%}")
    if model:
        md_lines.append(f"**Model**: {model}")
    if duration_seconds is not None:
        md_lines.append(f"**Duration**: {duration_seconds:.1f}s")
    md_lines.extend(["", "---", "", summary, "", "---", ""])
    md_lines.append(content)

    file_path.write_text("\n".join(md_lines), encoding="utf-8")
    logger.info(f"Report saved: {rel_path}")

    # 2. Write metadata to DB (if available)
    report_id = None
    if hasattr(dal, '_backend') and hasattr(dal._backend, 'insert_report'):
        try:
            report_id = dal._backend.insert_report(
                title=title,
                tickers=[t.upper() for t in tickers],
                report_type=report_type,
                summary=summary,
                conclusion=conclusion,
                confidence=confidence,
                provider=provider,
                model=model,
                file_path=rel_path,
                tools_used=tools_used,
                tool_calls=tool_calls,
                duration_seconds=duration_seconds,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )
        except Exception as e:
            logger.warning(f"Failed to save report metadata to DB: {e}")

    return {
        "id": report_id,
        "file_path": rel_path,
        "title": title,
        "created_at": datetime.now().isoformat(),
    }


def list_reports(
    dal: "DataAccessLayer",
    ticker: Optional[str] = None,
    days: int = 30,
    report_type: Optional[str] = None,
    limit: int = 20,
) -> List[dict]:
    """
    List saved research reports.

    Args:
        dal: DataAccessLayer instance
        ticker: Filter by ticker (e.g. "AFRM")
        days: Lookback period in days (default: 30)
        report_type: Filter by type (e.g. "entry_analysis")
        limit: Max reports to return (default: 20)

    Returns:
        List of report summaries (id, title, tickers, summary, created_at, etc.)
    """
    # Try DB first
    if hasattr(dal, '_backend') and hasattr(dal._backend, 'query_reports'):
        try:
            import pandas as pd
            df = dal._backend.query_reports(
                ticker=ticker,
                days=days,
                report_type=report_type,
                limit=limit,
            )
            if not df.empty:
                return df.to_dict(orient="records")
        except Exception as e:
            logger.warning(f"DB report query failed: {e}")

    # Fallback: scan Markdown files
    if dal._base:
        reports_dir = dal._base / _REPORTS_DIR
    else:
        reports_dir = Path(_REPORTS_DIR)

    if not reports_dir.exists():
        return []

    results = []
    for md_file in sorted(reports_dir.glob("*.md"), reverse=True):
        if len(results) >= limit:
            break

        # Parse filename: YYYY-MM-DD_TICKER_hash.md
        parts = md_file.stem.split("_")
        if len(parts) < 2:
            continue

        file_date = parts[0] if len(parts[0]) == 10 else None
        file_tickers = [p for p in parts[1:-1] if p.isalpha() and p.isupper()]

        # Apply ticker filter
        if ticker and ticker.upper() not in file_tickers:
            continue

        # Read first few lines for title/summary
        try:
            lines = md_file.read_text(encoding="utf-8").split("\n", 20)
            title = lines[0].lstrip("# ").strip() if lines else md_file.stem
        except Exception:
            title = md_file.stem

        results.append({
            "file_path": f"{_REPORTS_DIR}/{md_file.name}",
            "title": title,
            "tickers": file_tickers,
            "date": file_date,
        })

    return results


def get_report(
    dal: "DataAccessLayer",
    report_id: Optional[int] = None,
    file_path: Optional[str] = None,
) -> dict:
    """
    Retrieve a saved research report.

    Provide either report_id (DB lookup) or file_path (direct file read).

    Args:
        dal: DataAccessLayer instance
        report_id: Report ID from DB
        file_path: Relative path to Markdown file

    Returns:
        Dict with: title, content, metadata (if from DB)
    """
    # Get file path from DB if report_id provided
    if report_id and hasattr(dal, '_backend') and hasattr(dal._backend, 'get_report_metadata'):
        try:
            meta = dal._backend.get_report_metadata(report_id)
            if meta:
                file_path = meta.get("file_path")
        except Exception as e:
            logger.warning(f"DB report lookup failed: {e}")

    if not file_path:
        return {"error": "No report_id or file_path provided"}

    # Read Markdown content
    if dal._base:
        full_path = dal._base / file_path
    else:
        full_path = Path(file_path)

    if not full_path.exists():
        return {"error": f"Report file not found: {file_path}"}

    try:
        content = full_path.read_text(encoding="utf-8")
    except Exception as e:
        return {"error": f"Failed to read report: {e}"}

    result = {
        "file_path": file_path,
        "content": content,
    }

    # Add DB metadata if available
    if report_id and hasattr(dal, '_backend') and hasattr(dal._backend, 'get_report_metadata'):
        try:
            meta = dal._backend.get_report_metadata(report_id)
            if meta:
                result.update(meta)
        except Exception:
            pass

    return result