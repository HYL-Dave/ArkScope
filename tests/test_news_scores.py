"""
Tests for multi-model news scoring: detect_score_columns, resolve_score_columns,
FileBackend model selection, and migrate_to_supabase score import logic.

Run:
    pytest tests/test_news_scores.py -v
"""

import pandas as pd
import pytest


# ===========================================================================
# detect_score_columns
# ===========================================================================

class TestDetectScoreColumns:
    """Tests for auto-detecting score columns from DataFrame column names."""

    def _detect(self, columns):
        from src.tools.backends.file_backend import detect_score_columns
        df = pd.DataFrame(columns=columns)
        return detect_score_columns(df)

    def test_legacy_haiku_columns(self):
        cols = self._detect(["sentiment_haiku", "risk_haiku", "title"])
        assert len(cols) == 2
        types = {c[0] for c in cols}
        assert types == {"sentiment", "risk"}
        for c in cols:
            assert c[1] == "haiku"
            assert c[2] is None

    def test_gpt_5_2_xhigh_columns(self):
        cols = self._detect([
            "sentiment_gpt_5_2_xhigh", "risk_gpt_5_2_xhigh",
            "ticker", "title",
        ])
        assert len(cols) == 2
        for c in cols:
            assert c[1] == "gpt_5_2"
            assert c[2] == "xhigh"

    def test_mixed_models(self):
        cols = self._detect([
            "sentiment_haiku", "risk_haiku",
            "sentiment_gpt_5_2_xhigh", "risk_gpt_5_2_xhigh",
            "sentiment_o4_mini_medium",
            "ticker",
        ])
        assert len(cols) == 5
        models = {c[1] for c in cols}
        assert models == {"haiku", "gpt_5_2", "o4_mini"}

    def test_excludes_score_suffix(self):
        """sentiment_score and risk_score should NOT be detected as model columns."""
        cols = self._detect([
            "sentiment_score", "risk_score",
            "sentiment_haiku", "title",
        ])
        assert len(cols) == 1
        assert cols[0][3] == "sentiment_haiku"

    def test_empty_dataframe(self):
        cols = self._detect(["ticker", "title", "published_at"])
        assert cols == []

    def test_all_effort_levels(self):
        efforts = ["none", "minimal", "low", "medium", "high", "xhigh"]
        columns = [f"sentiment_test_{e}" for e in efforts]
        cols = self._detect(columns)
        assert len(cols) == 6
        detected_efforts = {c[2] for c in cols}
        assert detected_efforts == set(efforts)


# ===========================================================================
# resolve_score_columns
# ===========================================================================

class TestResolveScoreColumns:
    """Tests for picking the best score columns based on model preference or priority."""

    def _resolve(self, score_cols, preferred_model=None):
        from src.tools.backends.file_backend import resolve_score_columns
        return resolve_score_columns(score_cols, preferred_model)

    def test_preferred_model(self):
        cols = [
            ("sentiment", "haiku", None, "sentiment_haiku"),
            ("risk", "haiku", None, "risk_haiku"),
            ("sentiment", "gpt_5_2", "xhigh", "sentiment_gpt_5_2_xhigh"),
            ("risk", "gpt_5_2", "xhigh", "risk_gpt_5_2_xhigh"),
        ]
        sent, risk = self._resolve(cols, preferred_model="gpt-5.2")
        assert sent == "sentiment_gpt_5_2_xhigh"
        assert risk == "risk_gpt_5_2_xhigh"

    def test_preferred_model_already_suffix_format(self):
        cols = [
            ("sentiment", "gpt_5_2", "xhigh", "sentiment_gpt_5_2_xhigh"),
            ("risk", "gpt_5_2", "xhigh", "risk_gpt_5_2_xhigh"),
        ]
        sent, risk = self._resolve(cols, preferred_model="gpt_5_2")
        assert sent == "sentiment_gpt_5_2_xhigh"
        assert risk == "risk_gpt_5_2_xhigh"

    def test_auto_priority_picks_newest(self):
        cols = [
            ("sentiment", "haiku", None, "sentiment_haiku"),
            ("risk", "haiku", None, "risk_haiku"),
            ("sentiment", "gpt_5_2", "xhigh", "sentiment_gpt_5_2_xhigh"),
            ("risk", "gpt_5_2", "xhigh", "risk_gpt_5_2_xhigh"),
        ]
        sent, risk = self._resolve(cols)
        assert sent == "sentiment_gpt_5_2_xhigh"
        assert risk == "risk_gpt_5_2_xhigh"

    def test_auto_priority_fallback_to_haiku(self):
        cols = [
            ("sentiment", "haiku", None, "sentiment_haiku"),
            ("risk", "haiku", None, "risk_haiku"),
        ]
        sent, risk = self._resolve(cols)
        assert sent == "sentiment_haiku"
        assert risk == "risk_haiku"

    def test_preferred_model_not_found(self):
        cols = [
            ("sentiment", "haiku", None, "sentiment_haiku"),
            ("risk", "haiku", None, "risk_haiku"),
        ]
        sent, risk = self._resolve(cols, preferred_model="gpt-6")
        assert sent is None
        assert risk is None

    def test_empty_cols(self):
        sent, risk = self._resolve([])
        assert sent is None
        assert risk is None

    def test_partial_columns(self):
        """Only sentiment available, no risk."""
        cols = [
            ("sentiment", "gpt_5_2", "xhigh", "sentiment_gpt_5_2_xhigh"),
        ]
        sent, risk = self._resolve(cols)
        assert sent == "sentiment_gpt_5_2_xhigh"
        assert risk is None


# ===========================================================================
# detect_score_columns from migrate_to_supabase
# ===========================================================================

class TestMigrateDetectScoreColumns:
    """Test the detect_score_columns in the migration script."""

    def test_same_behavior(self):
        import sys
        sys.path.insert(0, ".")
        try:
            from scripts.migrate_to_supabase import detect_score_columns
            df = pd.DataFrame(columns=[
                "sentiment_gpt_5_2_xhigh", "risk_gpt_5_2_xhigh",
                "sentiment_haiku", "risk_haiku",
                "sentiment_score", "title",
            ])
            cols = detect_score_columns(df)
            assert len(cols) == 4
            models = {c[1] for c in cols}
            assert "gpt_5_2" in models
            assert "haiku" in models
        finally:
            sys.path.pop(0)


# ===========================================================================
# FileBackend model selection integration
# ===========================================================================

class TestFileBackendModelSelection:
    """Integration tests for FileBackend's model-aware query_news."""

    @pytest.fixture
    def backend_with_data(self, tmp_path):
        """Create a FileBackend with test data containing multiple model scores."""
        from src.tools.backends.file_backend import FileBackend

        news_dir = tmp_path / "data" / "news"
        news_dir.mkdir(parents=True)
        (tmp_path / "config").mkdir()
        (tmp_path / "data" / "prices").mkdir(parents=True)

        df = pd.DataFrame({
            "ticker": ["NVDA", "AAPL", "NVDA"],
            "title": ["NVDA news 1", "AAPL news", "NVDA news 2"],
            "published_at": pd.to_datetime([
                "2026-01-15", "2026-01-16", "2026-01-17",
            ]),
            "source_api": ["ibkr", "ibkr", "ibkr"],
            "url": ["http://a", "http://b", "http://c"],
            "publisher": ["pub1", "pub2", "pub3"],
            "description": ["desc1", "desc2", "desc3"],
            "sentiment_haiku": [3, 4, 2],
            "risk_haiku": [2, 1, 4],
            "sentiment_gpt_5_2_xhigh": [4, None, 3],
            "risk_gpt_5_2_xhigh": [1, None, 5],
        })
        df.to_parquet(news_dir / "ibkr_scored_final.parquet", index=False)

        return FileBackend(base_path=tmp_path)

    def test_default_picks_gpt_5_2(self, backend_with_data):
        """Without specifying model, should pick gpt_5_2 (higher priority)."""
        df = backend_with_data.query_news(scored_only=False, days=365)
        nvda_first = df[df["ticker"] == "NVDA"].iloc[0]
        # gpt_5_2 has score=3 for "NVDA news 2" (most recent)
        assert nvda_first["sentiment_score"] == 3

    def test_specific_model_haiku(self, backend_with_data):
        """Requesting haiku model should return haiku scores."""
        df = backend_with_data.query_news(model="haiku", scored_only=False, days=365)
        assert len(df) == 3
        assert df["sentiment_score"].notna().sum() == 3

    def test_specific_model_gpt_5_2(self, backend_with_data):
        """Requesting gpt_5_2 model should return only those scores."""
        df = backend_with_data.query_news(model="gpt-5.2", scored_only=True, days=365)
        # Only 2 articles have gpt_5_2 scores (AAPL has None)
        assert len(df) == 2

    def test_nonexistent_model(self, backend_with_data):
        """Requesting a model that doesn't exist returns no scores."""
        df = backend_with_data.query_news(model="gpt-6", scored_only=True, days=365)
        assert len(df) == 0


# ===========================================================================
# SQL migration file
# ===========================================================================

class TestSQLMigration:
    """Verify migration SQL file exists and has correct structure."""

    def test_migration_file_exists(self):
        from pathlib import Path
        sql_path = Path("sql/002_add_news_scores.sql")
        assert sql_path.exists(), "sql/002_add_news_scores.sql must exist"

    def test_migration_contains_key_elements(self):
        from pathlib import Path
        content = Path("sql/002_add_news_scores.sql").read_text()
        assert "CREATE TABLE IF NOT EXISTS news_scores" in content
        assert "news_latest_scores" in content
        assert "score_type" in content
        assert "reasoning_effort" in content
        assert "ON CONFLICT" in content