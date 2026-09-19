"""The removed translation surface cannot execute or recreate its storage."""

import importlib.util
import sqlite3
from dataclasses import asdict
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.api.routes.analysis_cards import router
from src.card_runs import CardRunStore
from src.fixed_task_runtime_config import FIXED_TASK_RUNTIME_TASKS, validate_fixed_task_runtime_updates
from src.model_routing import TASK_IDS, TaskRoute, catalog


def test_translation_has_no_task_option_runtime_or_route():
    assert "card_translation" not in TASK_IDS
    assert all(task.id != "card_translation" for task in catalog().tasks)
    assert "card_translation" not in FIXED_TASK_RUNTIME_TASKS
    assert not any(route.path.endswith("/translate") for route in router.routes)
    with pytest.raises(ValidationError):
        TaskRoute(task="card_translation", provider="openai", model="gpt-6-astra")
    with pytest.raises(ValueError, match="unknown fixed task"):
        validate_fixed_task_runtime_updates({"card_translation": 900})


def test_translation_implementation_and_writers_are_absent():
    from src import card_synthesis

    for name in ("translate_card", "translate_text", "translation_harness"):
        assert not hasattr(card_synthesis, name)
    for name in ("get_translation", "set_translation", "translation_versions"):
        assert not hasattr(CardRunStore, name)
    assert importlib.util.find_spec("src.content_translation_failures") is None
    assert not (Path(__file__).resolve().parents[1] / "docs/superpowers/evidence/2026-09-08-sdk152-fixed-output/live_api_canary.py").exists()


def test_retired_endpoint_does_not_resolve_credentials_or_create_storage(monkeypatch, tmp_path):
    from src.api.routes import analysis_cards

    def forbidden():
        pytest.fail("A removed route cannot resolve storage or credentials")

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[analysis_cards.get_card_store] = forbidden
    monkeypatch.setattr(analysis_cards, "_capture_execution", lambda *args: forbidden())
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "must-not-exist.db"))
    with TestClient(app) as client:
        result = client.post("/analysis/cards/1/translate", json={"lang": "zh-Hant", "refresh": True})
    assert result.status_code == 404
    assert not (tmp_path / "must-not-exist.db").exists()


def test_new_card_store_has_only_original_analysis_storage(tmp_path):
    path = tmp_path / "profile.db"
    store = CardRunStore(path)
    run = store.record(ticker="AAPL", result_card={"conclusion": "Original analysis"})
    assert store.get(run.id).result_card == run.result_card
    assert "translations" not in asdict(store.get(run.id))
    with sqlite3.connect(path) as conn:
        assert "translations_json" not in {row[1] for row in conn.execute("PRAGMA table_info(ai_card_runs)")}
        assert not conn.execute("SELECT name FROM sqlite_schema WHERE name LIKE 'ai_card_translation%'").fetchall()


def test_existing_translations_do_not_change_original_card_reads(tmp_path):
    path = tmp_path / "profile.db"
    store = CardRunStore(path)
    run = store.record(ticker="AAPL", result_card={"conclusion": "Original analysis"})
    with sqlite3.connect(path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(ai_card_runs)")}
        if "translations_json" not in columns:
            conn.execute("ALTER TABLE ai_card_runs ADD COLUMN translations_json TEXT")
        conn.execute("UPDATE ai_card_runs SET translations_json = ?", ('{"zh-Hant":{"conclusion":"retired output"}}',))
    reopened = CardRunStore(path).get(run.id)
    assert reopened.result_card == run.result_card
    assert "translations" not in asdict(reopened)
