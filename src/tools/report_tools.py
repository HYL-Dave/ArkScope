"""
Report tool functions (3 tools).

24. save_report    — Save an agent-generated research report
25. list_reports   — List saved research reports
26. get_report     — Retrieve a saved research report
"""

from __future__ import annotations

import hashlib
import errno
import logging
import os
import re
import stat
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

from src.app_records_store import get_app_records_store

logger = logging.getLogger(__name__)

# Reports directory (relative to project root)
_REPORTS_DIR = "data/reports"


class _ReportAccessError(ValueError):
    pass


def _report_name(file_path: str) -> str:
    if not isinstance(file_path, str):
        raise _ReportAccessError("report_path_invalid")
    parts = file_path.split("/")
    if (len(parts) != 3 or parts[:2] != ["data", "reports"]
            or not parts[2].endswith(".md") or parts[2] == ".md"
            or "\\" in file_path or any(ord(char) < 32 for char in file_path)):
        raise _ReportAccessError("report_path_invalid")
    return parts[2]


@contextmanager
def _reports_directory(base: Path | None, *, create: bool = False):
    if os.name != "posix" or not all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")):
        raise _ReportAccessError("report_secure_io_unavailable")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(Path(base or Path.cwd()).resolve(strict=True), flags)
    try:
        # Pin each directory; a path check followed by Path.read_text would race.
        for part in ("data", "reports"):
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _read_report(directory: int, name: str) -> str:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise _ReportAccessError("report_path_unsafe")
        with os.fdopen(fd, "r", encoding="utf-8", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(fd)


def _file_error(error: Exception, *, writing: bool = False) -> dict:
    code = "report_write_failed" if writing else "report_read_failed"
    if isinstance(error, _ReportAccessError):
        code = str(error)
    elif isinstance(error, FileNotFoundError) and not writing:
        code = "report_not_found"
    elif isinstance(error, OSError) and error.errno in {errno.ELOOP, errno.ENOTDIR}:
        code = "report_path_unsafe"
    messages = {
        "report_path_invalid": "Only canonical data/reports/*.md paths are accepted",
        "report_path_unsafe": "Report path is not a private regular report file",
        "report_secure_io_unavailable": "Secure report file access is unavailable on this platform",
        "report_not_found": "Report file not found",
        "report_read_failed": "Failed to read report",
        "report_write_failed": "Failed to save report",
    }
    return {"error": messages[code], "code": code}


def _generate_filename(tickers: List[str], title: str) -> str:
    """Generate a unique filename for a report."""
    today = date.today().isoformat()
    ticker_str = "_".join(re.sub(r"[^A-Z0-9.-]+", "-", t.upper()).strip(".-") or "TICKER"
                          for t in tickers[:3])
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
        model: Model used (claude-opus-4-7, gpt-5.4)
        tools_used: List of tool names used during analysis
        tool_calls: Total number of tool calls
        duration_seconds: Analysis duration
        tokens_in: Input tokens consumed
        tokens_out: Output tokens consumed

    Returns:
        Dict with: id, file_path, title, created_at
    """
    filename = _generate_filename(tickers, title)
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

    try:
        _report_name(rel_path)
        with _reports_directory(dal._base, create=True) as directory:
            fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write("\n".join(md_lines))
    except (OSError, ValueError) as error:
        return _file_error(error, writing=True)
    logger.info(f"Report saved: {rel_path}")

    # 2. Write metadata to DB (if available)
    report_id = None
    _store = get_app_records_store(dal)
    if hasattr(_store, 'insert_report'):
        try:
            report_id = _store.insert_report(
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
        except Exception:
            logger.warning("Failed to save report metadata to DB")

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
    _store = get_app_records_store(dal)
    if hasattr(_store, 'query_reports'):
        try:
            df = _store.query_reports(
                ticker=ticker,
                days=days,
                report_type=report_type,
                limit=limit,
            )
            if not df.empty:
                return df.to_dict(orient="records")
        except Exception:
            logger.warning("DB report query failed")

    # Fallback: scan Markdown files
    results = []
    try:
        with _reports_directory(dal._base) as directory:
            for name in sorted(os.listdir(directory), reverse=True):
                if len(results) >= limit:
                    break
                rel_path = f"{_REPORTS_DIR}/{name}"
                try:
                    _report_name(rel_path)
                    parts = Path(name).stem.split("_")
                    if len(parts) < 2:
                        continue
                    file_tickers = [part for part in parts[1:-1] if part.isalpha() and part.isupper()]
                    if ticker and ticker.upper() not in file_tickers:
                        continue
                    content = _read_report(directory, name)
                except (OSError, ValueError):
                    continue
                results.append({
                    "file_path": rel_path,
                    "title": content.split("\n", 1)[0].lstrip("# ").strip(),
                    "tickers": file_tickers,
                    "date": parts[0] if len(parts[0]) == 10 else None,
                })
    except (OSError, ValueError):
        logger.warning("Report directory unavailable for listing")
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
    # Resolve metadata ONCE (used for both file_path resolution and the result below).
    meta = None
    _store = get_app_records_store(dal)
    if report_id and hasattr(_store, 'get_report_metadata'):
        try:
            meta = _store.get_report_metadata(report_id)
            if meta:
                file_path = meta.get("file_path")
        except Exception:
            logger.warning("DB report lookup failed")

    if not file_path:
        return {"error": "No report_id or file_path provided"}

    try:
        name = _report_name(file_path)
        with _reports_directory(dal._base) as directory:
            content = _read_report(directory, name)
    except (OSError, ValueError) as error:
        return _file_error(error)

    return {
        **(meta or {}),
        "file_path": file_path,
        "content": content,
    }
