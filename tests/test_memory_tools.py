"""Tests for memory tools (Phase 15 — Episodic Memory).

Tests save_memory, recall_memories, list_memories, delete_memory
with file-based fallback (no DB required).
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.tools.memory_tools import (
    _MEMORY_DIR,
    _VALID_CATEGORIES,
    _generate_filename,
    delete_memory,
    list_memories,
    recall_memories,
    save_memory,
)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def mock_dal(tmp_path):
    """Create a mock DAL pointing to a tmp directory (no DB)."""
    dal = MagicMock()
    dal._base = tmp_path
    # No DB backend — force file fallback
    del dal._backend
    return dal


@pytest.fixture
def mock_dal_with_db(tmp_path):
    """Create a mock DAL with a mock DB backend."""
    dal = MagicMock()
    dal._base = tmp_path
    dal._backend = MagicMock()
    dal._backend.insert_memory = MagicMock(return_value=42)
    dal._backend.query_memories = MagicMock()
    dal._backend.list_memories_meta = MagicMock()
    dal._backend.delete_memory = MagicMock()
    return dal


# ── Filename Generation ──────────────────────────────────────


class TestFilenameGeneration:
    def test_filename_format(self):
        name = _generate_filename("analysis", "Test Title")
        parts = name.split("_")
        # YYYY-MM-DD_category_hash.md
        assert len(parts[0]) == 10  # date
        assert parts[1] == "analysis"
        assert name.endswith(".md")

    def test_unique_filenames(self):
        name1 = _generate_filename("note", "Same Title")
        name2 = _generate_filename("note", "Same Title")
        # Hash includes datetime.now(), so should be different
        assert name1 != name2


# ── Save Memory ──────────────────────────────────────────────


class TestSaveMemory:
    def test_basic_save(self, mock_dal):
        result = save_memory(
            mock_dal,
            title="Test Memory",
            content="Some important content",
        )
        assert result["title"] == "Test Memory"
        assert result["file_path"].startswith(_MEMORY_DIR)
        assert result["file_path"].endswith(".md")
        assert result["id"] is None  # No DB

        # File should exist
        full_path = mock_dal._base / result["file_path"]
        assert full_path.exists()

    def test_save_with_tickers_and_tags(self, mock_dal):
        result = save_memory(
            mock_dal,
            title="AFRM Analysis",
            content="Bullish on dip",
            category="analysis",
            tickers=["afrm", "nvda"],
            tags=["entry", "dip_buying"],
            importance=8,
        )
        # Read the file and verify content
        full_path = mock_dal._base / result["file_path"]
        text = full_path.read_text(encoding="utf-8")
        assert "AFRM Analysis" in text
        assert "**Category**: analysis" in text
        assert "AFRM" in text  # tickers uppercased
        assert "NVDA" in text
        assert "entry" in text
        assert "**Importance**: 8/10" in text

    def test_save_markdown_structure(self, mock_dal):
        result = save_memory(
            mock_dal,
            title="My Note",
            content="Line 1\nLine 2",
            category="note",
            source="user_manual",
        )
        full_path = mock_dal._base / result["file_path"]
        text = full_path.read_text(encoding="utf-8")
        assert text.startswith("# My Note\n")
        assert "**Source**: user_manual" in text
        assert "---" in text
        assert "Line 1\nLine 2" in text

    def test_invalid_category_defaults_to_note(self, mock_dal):
        result = save_memory(
            mock_dal,
            title="Test",
            content="Content",
            category="invalid_cat",
        )
        full_path = mock_dal._base / result["file_path"]
        text = full_path.read_text(encoding="utf-8")
        assert "**Category**: note" in text

    def test_importance_clamped(self, mock_dal):
        result = save_memory(
            mock_dal,
            title="Test",
            content="Content",
            importance=99,
        )
        full_path = mock_dal._base / result["file_path"]
        text = full_path.read_text(encoding="utf-8")
        assert "**Importance**: 10/10" in text

    def test_save_with_db(self, mock_dal_with_db):
        result = save_memory(
            mock_dal_with_db,
            title="DB Memory",
            content="Content",
            category="fact",
            tickers=["TSLA"],
        )
        assert result["id"] == 42
        mock_dal_with_db._backend.insert_memory.assert_called_once()
        call_kwargs = mock_dal_with_db._backend.insert_memory.call_args
        assert call_kwargs[1]["title"] == "DB Memory"
        assert call_kwargs[1]["category"] == "fact"
        assert call_kwargs[1]["tickers"] == ["TSLA"]

    def test_save_db_failure_graceful(self, mock_dal_with_db):
        mock_dal_with_db._backend.insert_memory.side_effect = Exception("DB down")
        result = save_memory(
            mock_dal_with_db,
            title="Test",
            content="Content",
        )
        # Should still succeed (file saved, DB best-effort)
        assert result["id"] is None
        assert result["file_path"].endswith(".md")

    def test_directory_auto_created(self, tmp_path):
        dal = MagicMock()
        dal._base = tmp_path
        del dal._backend
        # Memory dir doesn't exist yet
        memory_dir = tmp_path / _MEMORY_DIR
        assert not memory_dir.exists()

        save_memory(dal, title="Test", content="Content")
        assert memory_dir.exists()


# ── Recall Memories ──────────────────────────────────────────


class TestRecallMemories:
    def _save_samples(self, dal):
        """Save a few sample memories for testing recall."""
        save_memory(dal, title="AFRM Entry Analysis", content="Bullish on AFRM dip",
                    category="analysis", tickers=["AFRM"], importance=8)
        save_memory(dal, title="NVDA Earnings Note", content="NVDA beat estimates Q4",
                    category="insight", tickers=["NVDA"], tags=["earnings"])
        save_memory(dal, title="User preference conservative", content="Prefers pullbacks",
                    category="preference")

    def test_recall_all(self, mock_dal):
        self._save_samples(mock_dal)
        results = recall_memories(mock_dal)
        assert len(results) == 3

    def test_recall_by_query(self, mock_dal):
        self._save_samples(mock_dal)
        results = recall_memories(mock_dal, query="AFRM")
        assert len(results) >= 1
        assert any("AFRM" in r["title"] for r in results)

    def test_recall_by_category(self, mock_dal):
        self._save_samples(mock_dal)
        results = recall_memories(mock_dal, category="preference")
        assert len(results) == 1
        assert results[0]["category"] == "preference"

    def test_recall_by_tickers(self, mock_dal):
        self._save_samples(mock_dal)
        results = recall_memories(mock_dal, tickers=["NVDA"])
        assert len(results) >= 1
        assert any("NVDA" in r.get("content", "") for r in results)

    def test_recall_empty(self, mock_dal):
        results = recall_memories(mock_dal, query="nonexistent")
        assert results == []

    def test_recall_limit(self, mock_dal):
        self._save_samples(mock_dal)
        results = recall_memories(mock_dal, limit=1)
        assert len(results) == 1

    def test_recall_with_db(self, mock_dal_with_db):
        import pandas as pd
        mock_dal_with_db._backend.query_memories.return_value = pd.DataFrame([
            {"id": 1, "title": "DB Memory", "content": "Content",
             "category": "note", "tickers": None, "tags": None,
             "importance": 5, "source": "agent_auto",
             "created_at": "2026-02-19T12:00:00"},
        ])
        results = recall_memories(mock_dal_with_db, query="test")
        assert len(results) == 1
        assert results[0]["title"] == "DB Memory"


# ── List Memories ────────────────────────────────────────────


class TestListMemories:
    def test_list_all(self, mock_dal):
        save_memory(mock_dal, title="Mem 1", content="C1", category="note")
        save_memory(mock_dal, title="Mem 2", content="C2", category="analysis")
        results = list_memories(mock_dal)
        assert len(results) == 2

    def test_list_by_category(self, mock_dal):
        save_memory(mock_dal, title="Mem 1", content="C1", category="note")
        save_memory(mock_dal, title="Mem 2", content="C2", category="analysis")
        results = list_memories(mock_dal, category="analysis")
        assert len(results) == 1
        assert results[0]["category"] == "analysis"

    def test_list_limit(self, mock_dal):
        for i in range(5):
            save_memory(mock_dal, title=f"Mem {i}", content=f"C{i}")
        results = list_memories(mock_dal, limit=3)
        assert len(results) == 3

    def test_list_empty(self, mock_dal):
        results = list_memories(mock_dal)
        assert results == []

    def test_list_with_db(self, mock_dal_with_db):
        import pandas as pd
        mock_dal_with_db._backend.list_memories_meta.return_value = pd.DataFrame([
            {"id": 1, "title": "DB Mem", "category": "note",
             "tickers": None, "tags": None, "importance": 5,
             "created_at": "2026-02-19T12:00:00"},
        ])
        results = list_memories(mock_dal_with_db)
        assert len(results) == 1


# ── Delete Memory ────────────────────────────────────────────


class TestDeleteMemory:
    def test_delete_with_db(self, mock_dal_with_db):
        # DB returns file_path of deleted memory
        mock_dal_with_db._backend.delete_memory.return_value = "data/agent_memory/test.md"
        result = delete_memory(mock_dal_with_db, memory_id=1)
        assert result["deleted"] is True
        assert result["id"] == 1

    def test_delete_not_found(self, mock_dal_with_db):
        mock_dal_with_db._backend.delete_memory.return_value = None
        result = delete_memory(mock_dal_with_db, memory_id=999)
        assert result["deleted"] is False
        assert "not found" in result["error"]

    def test_delete_with_file_cleanup(self, mock_dal_with_db):
        # Save a memory first so file exists
        save_result = save_memory(
            mock_dal_with_db, title="To Delete", content="Tmp",
        )
        rel_path = save_result["file_path"]
        full_path = mock_dal_with_db._base / rel_path
        assert full_path.exists()

        # Now delete — DB returns the file_path
        mock_dal_with_db._backend.delete_memory.return_value = rel_path
        result = delete_memory(mock_dal_with_db, memory_id=42)
        assert result["deleted"] is True
        assert not full_path.exists()

    def test_delete_db_failure(self, mock_dal_with_db):
        mock_dal_with_db._backend.delete_memory.side_effect = Exception("DB down")
        result = delete_memory(mock_dal_with_db, memory_id=1)
        assert result["deleted"] is False


# ── Valid Categories ─────────────────────────────────────────


class TestValidCategories:
    def test_all_categories(self):
        assert _VALID_CATEGORIES == {"analysis", "insight", "preference", "fact", "note"}


# ── Registry Integration ────────────────────────────────────


class TestMemoryToolRegistry:
    def test_memory_tools_registered(self):
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        names = registry.list_names()
        assert "save_memory" in names
        assert "recall_memories" in names
        assert "list_memories" in names
        assert "delete_memory" in names

    def test_total_tool_count(self):
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        assert len(registry.list_all()) == 30
