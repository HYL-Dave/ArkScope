"""
Memory tool functions (4 tools).

27. save_memory      — Save knowledge to long-term memory
28. recall_memories  — Search long-term memory
29. list_memories    — List saved memories (metadata only)
30. delete_memory    — Delete a memory by ID
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

logger = logging.getLogger(__name__)

# Memory directory (relative to project root)
_MEMORY_DIR = "data/agent_memory"

_VALID_CATEGORIES = {"analysis", "insight", "preference", "fact", "note"}


def _ensure_memory_dir(base: Path) -> Path:
    """Ensure the memory directory exists."""
    memory_dir = base / _MEMORY_DIR
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


def _generate_filename(category: str, title: str) -> str:
    """Generate a unique filename for a memory."""
    today = date.today().isoformat()
    content_hash = hashlib.md5(
        f"{title}{datetime.now().isoformat()}".encode()
    ).hexdigest()[:8]
    return f"{today}_{category}_{content_hash}.md"


def save_memory(
    dal: "DataAccessLayer",
    title: str,
    content: str,
    category: str = "note",
    tickers: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    importance: int = 5,
    source: str = "agent_auto",
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """
    Save a piece of knowledge to long-term memory.

    Writes Markdown file to data/agent_memory/ and metadata to DB.

    Args:
        dal: DataAccessLayer instance
        title: Short descriptive title
        content: Full content to remember (Markdown supported)
        category: analysis|insight|preference|fact|note
        tickers: Related ticker symbols
        tags: Free-form tags for categorization
        importance: 1-10 (10=critical, 5=normal, 1=trivial)
        source: agent_auto|user_manual|subagent
        provider: LLM provider (anthropic, openai)
        model: Model used

    Returns:
        Dict with: id, file_path, title, created_at
    """
    # Validate category
    if category not in _VALID_CATEGORIES:
        category = "note"

    # Normalize tickers
    if tickers:
        tickers = [t.upper() for t in tickers]

    # Clamp importance
    importance = max(1, min(10, importance))

    # 1. Write Markdown file
    if dal._base:
        memory_dir = _ensure_memory_dir(dal._base)
    else:
        memory_dir = Path(_MEMORY_DIR)
        memory_dir.mkdir(parents=True, exist_ok=True)

    filename = _generate_filename(category, title)
    file_path = memory_dir / filename
    rel_path = f"{_MEMORY_DIR}/{filename}"

    # Build Markdown with front matter
    md_lines = [
        f"# {title}",
        "",
        f"**Date**: {date.today().isoformat()}",
        f"**Category**: {category}",
    ]
    if tickers:
        md_lines.append(f"**Tickers**: {', '.join(tickers)}")
    if tags:
        md_lines.append(f"**Tags**: {', '.join(tags)}")
    md_lines.append(f"**Importance**: {importance}/10")
    if source:
        md_lines.append(f"**Source**: {source}")
    md_lines.extend(["", "---", ""])
    md_lines.append(content)

    file_path.write_text("\n".join(md_lines), encoding="utf-8")
    logger.info(f"Memory saved: {rel_path}")

    # 2. Write metadata to DB (if available)
    memory_id = None
    if hasattr(dal, '_backend') and hasattr(dal._backend, 'insert_memory'):
        try:
            memory_id = dal._backend.insert_memory(
                title=title,
                content=content,
                category=category,
                tickers=tickers,
                tags=tags,
                importance=importance,
                source=source,
                provider=provider,
                model=model,
                file_path=rel_path,
            )
        except Exception as e:
            logger.warning(f"Failed to save memory to DB: {e}")

    return {
        "id": memory_id,
        "file_path": rel_path,
        "title": title,
        "created_at": datetime.now().isoformat(),
    }


def recall_memories(
    dal: "DataAccessLayer",
    query: str = "",
    category: Optional[str] = None,
    tickers: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    days: int = 90,
    limit: int = 10,
) -> List[dict]:
    """
    Search long-term memory for relevant past knowledge.

    Args:
        dal: DataAccessLayer instance
        query: Search query (keywords or natural language)
        category: Filter by category
        tickers: Filter by related tickers
        tags: Filter by tags
        days: Lookback period in days (default: 90)
        limit: Max memories to return (default: 10)

    Returns:
        List of memory dicts (id, title, category, content, tickers, tags,
        importance, created_at)
    """
    # Try DB first
    if hasattr(dal, '_backend') and hasattr(dal._backend, 'query_memories'):
        try:
            df = dal._backend.query_memories(
                query=query,
                category=category,
                tickers=tickers,
                tags=tags,
                days=days,
                limit=limit,
            )
            if not df.empty:
                return df.to_dict(orient="records")
        except Exception as e:
            logger.warning(f"DB memory query failed: {e}")

    # Fallback: scan Markdown files
    if dal._base:
        memory_dir = dal._base / _MEMORY_DIR
    else:
        memory_dir = Path(_MEMORY_DIR)

    if not memory_dir.exists():
        return []

    results = []
    query_lower = query.lower() if query else ""

    for md_file in sorted(memory_dir.glob("*.md"), reverse=True):
        if len(results) >= limit:
            break

        # Parse filename: YYYY-MM-DD_category_hash.md
        parts = md_file.stem.split("_", 2)
        file_date = parts[0] if len(parts) >= 1 and len(parts[0]) == 10 else None
        file_category = parts[1] if len(parts) >= 2 else None

        # Apply category filter
        if category and file_category != category:
            continue

        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Apply query filter (simple substring match for file fallback)
        if query_lower and query_lower not in text.lower():
            continue

        # Apply ticker filter
        if tickers:
            text_upper = text.upper()
            if not any(t.upper() in text_upper for t in tickers):
                continue

        # Extract title from first line
        lines = text.split("\n", 1)
        title = lines[0].lstrip("# ").strip() if lines else md_file.stem

        results.append({
            "file_path": f"{_MEMORY_DIR}/{md_file.name}",
            "title": title,
            "category": file_category,
            "content": text,
            "date": file_date,
        })

    return results


def list_memories(
    dal: "DataAccessLayer",
    category: Optional[str] = None,
    days: int = 90,
    limit: int = 20,
) -> List[dict]:
    """
    List saved memories (metadata only, no full content).

    Args:
        dal: DataAccessLayer instance
        category: Filter by category
        days: Lookback period in days (default: 90)
        limit: Max memories to return (default: 20)

    Returns:
        List of memory metadata dicts
    """
    # Try DB first
    if hasattr(dal, '_backend') and hasattr(dal._backend, 'list_memories_meta'):
        try:
            df = dal._backend.list_memories_meta(
                category=category,
                days=days,
                limit=limit,
            )
            if not df.empty:
                return df.to_dict(orient="records")
        except Exception as e:
            logger.warning(f"DB memory list failed: {e}")

    # Fallback: scan Markdown files
    if dal._base:
        memory_dir = dal._base / _MEMORY_DIR
    else:
        memory_dir = Path(_MEMORY_DIR)

    if not memory_dir.exists():
        return []

    results = []
    for md_file in sorted(memory_dir.glob("*.md"), reverse=True):
        if len(results) >= limit:
            break

        parts = md_file.stem.split("_", 2)
        file_date = parts[0] if len(parts) >= 1 and len(parts[0]) == 10 else None
        file_category = parts[1] if len(parts) >= 2 else None

        if category and file_category != category:
            continue

        try:
            lines = md_file.read_text(encoding="utf-8").split("\n", 10)
            title = lines[0].lstrip("# ").strip() if lines else md_file.stem
        except Exception:
            title = md_file.stem

        results.append({
            "file_path": f"{_MEMORY_DIR}/{md_file.name}",
            "title": title,
            "category": file_category,
            "date": file_date,
        })

    return results


def delete_memory(
    dal: "DataAccessLayer",
    memory_id: int,
) -> dict:
    """
    Delete a memory by its ID.

    Deletes from DB and removes the corresponding Markdown file.

    Args:
        dal: DataAccessLayer instance
        memory_id: Memory ID to delete

    Returns:
        Dict with: deleted (bool), id, or error message
    """
    file_path = None

    # Delete from DB
    if hasattr(dal, '_backend') and hasattr(dal._backend, 'delete_memory'):
        try:
            file_path = dal._backend.delete_memory(memory_id)
        except Exception as e:
            logger.warning(f"DB memory delete failed: {e}")
            return {"deleted": False, "error": f"DB delete failed: {e}"}

    if file_path is None:
        return {"deleted": False, "error": f"Memory #{memory_id} not found"}

    # Delete corresponding file
    if file_path:
        if dal._base:
            full_path = dal._base / file_path
        else:
            full_path = Path(file_path)

        if full_path.exists():
            try:
                full_path.unlink()
                logger.info(f"Memory file deleted: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete memory file: {e}")

    return {"deleted": True, "id": memory_id}
