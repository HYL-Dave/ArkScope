"""Tests for the model-route store — user-selected per-task routes in profile_state.db.

A route is a STRUCTURED row (task → provider/model/effort), NOT EAV: provider/model/
effort are written together so a save can never leave a half-applied route, and
``updated_at`` is route-level. The store is storage-only — no task/provider CHECK
(the registry in model_routing.py owns validation), so new tasks need no migration.
"""

from __future__ import annotations

import pytest
import sqlite3

from src.model_route_store import ModelRouteRow, ModelRouteStore


@pytest.fixture()
def store(tmp_path):
    return ModelRouteStore(tmp_path / "profile_state.db")


def test_set_get_roundtrip(store):
    row = store.set("ai_research", "openai", "gpt-5.4-mini", "xhigh")
    assert (row.task, row.provider, row.model, row.effort) == (
        "ai_research", "openai", "gpt-5.4-mini", "xhigh")
    assert row.updated_at  # route-level timestamp
    assert store.get("ai_research") == row


def test_get_missing_returns_none(store):
    assert store.get("card_synthesis") is None


def test_set_is_atomic_upsert_one_row_per_task(store):
    store.set("ai_research", "openai", "gpt-5.4-mini", "xhigh")
    store.set("ai_research", "anthropic", "claude-opus-4-8", "high")  # overwrite, not duplicate
    got = store.get("ai_research")
    assert (got.provider, got.model, got.effort) == ("anthropic", "claude-opus-4-8", "high")
    assert list(store.get_all().keys()) == ["ai_research"]  # single row


def test_effort_defaults_to_default(store):
    assert store.set("card_translation", "openai", "gpt-5.4-mini").effort == "default"


def test_get_all_keyed_by_task(store):
    store.set("ai_research", "openai", "gpt-5.4-mini", "low")
    store.set("card_synthesis", "anthropic", "claude-opus-4-8", "high")
    allrows = store.get_all()
    assert set(allrows) == {"ai_research", "card_synthesis"}
    assert allrows["card_synthesis"].model == "claude-opus-4-8"


def test_delete_reverts_to_absent(store):
    store.set("ai_research", "openai", "gpt-5.4-mini", "low")
    assert store.delete("ai_research") is True
    assert store.get("ai_research") is None
    assert store.delete("ai_research") is False  # idempotent — nothing to delete


def test_schema_idempotent_across_instances(tmp_path):
    db = tmp_path / "profile_state.db"
    ModelRouteStore(db).set("ai_research", "openai", "gpt-5.4-mini", "low")
    # a second instance on the same DB must not error on CREATE and must see the row
    assert ModelRouteStore(db).get("ai_research").model == "gpt-5.4-mini"


def test_batch_save_rolls_back_every_route_when_a_later_write_fails(store):
    store.set("card_synthesis", "anthropic", "claude-sonnet-5", "high")
    before = store.get_all()
    with sqlite3.connect(store._db_path) as conn:
        conn.execute("""CREATE TRIGGER reject_investigation BEFORE INSERT ON model_route
            WHEN NEW.task = 'lifecycle_investigation'
            BEGIN SELECT RAISE(ABORT, 'synthetic later-row failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="synthetic later-row failure"):
        store.set_many([
            ("card_synthesis", "anthropic", "claude-sonnet-5", "xhigh"),
            ("lifecycle_investigation", "anthropic", "claude-sonnet-5", "xhigh"),
        ])
    assert store.get_all() == before


def test_batch_save_commits_all_requested_routes_and_leaves_other_tasks_untouched(store):
    other = store.set("card_translation", "openai", "gpt-5.3-codex-spark", "xhigh")
    saved = store.set_many([
        ("card_synthesis", "anthropic", "claude-sonnet-5", "high"),
        ("lifecycle_investigation", "anthropic", "claude-sonnet-5", "xhigh"),
    ])
    assert len(saved) == 2
    assert all(store.get(row.task) == row for row in saved)
    assert store.get("card_translation") == other
