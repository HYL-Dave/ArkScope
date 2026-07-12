from __future__ import annotations

import pytest

from src.fixed_task_runtime_config import (
    DEFAULT_MODEL_TIMEOUT_S,
    FIXED_TASK_RUNTIME_TASKS,
    FixedTaskRuntimeStore,
    resolve_all_fixed_task_runtime,
    resolve_fixed_task_runtime,
)
from src.model_routing import TASKS


@pytest.fixture(autouse=True)
def _clear_fixed_task_env(monkeypatch):
    monkeypatch.delenv("ARKSCOPE_CARD_SYNTHESIS_TIMEOUT_S", raising=False)
    monkeypatch.delenv("ARKSCOPE_CARD_TRANSLATION_TIMEOUT_S", raising=False)


@pytest.fixture()
def store(tmp_path):
    return FixedTaskRuntimeStore(tmp_path / "profile_state.db")


def test_registry_is_the_exact_fixed_task_membership():
    assert tuple(FIXED_TASK_RUNTIME_TASKS) == (
        "card_synthesis",
        "card_translation",
    )
    assert {definition.task for definition in FIXED_TASK_RUNTIME_TASKS.values()} == {
        "card_synthesis",
        "card_translation",
    }
    assert set(FIXED_TASK_RUNTIME_TASKS) <= {task.id for task in TASKS}


def test_defaults_are_900_seconds(store):
    settings = resolve_all_fixed_task_runtime(store=store)

    assert set(settings) == set(FIXED_TASK_RUNTIME_TASKS)
    for task, value in settings.items():
        assert value.task == task
        assert value.model_timeout_s == DEFAULT_MODEL_TIMEOUT_S == 900.0
        assert value.source == "default"
        assert value.db_saved is False
        assert value.warning is None


def test_set_many_persists_both_tasks_in_one_db(store):
    written = store.set_many(
        {"card_synthesis": 1200.0, "card_translation": 600.0}
    )

    assert written["card_synthesis"].model_timeout_s == 1200.0
    assert written["card_translation"].model_timeout_s == 600.0
    reopened = FixedTaskRuntimeStore(store.db_path)
    rows = reopened.get_all()
    assert rows["card_synthesis"].model_timeout_s == 1200.0
    assert rows["card_translation"].model_timeout_s == 600.0

    resolved = resolve_all_fixed_task_runtime(store=reopened)
    assert resolved["card_synthesis"].source == "db"
    assert resolved["card_synthesis"].db_saved is True
    assert resolved["card_translation"].source == "db"


def test_env_overrides_db_without_rewriting_saved_value(store, monkeypatch):
    store.set_many({"card_synthesis": 600.0})
    monkeypatch.setenv("ARKSCOPE_CARD_SYNTHESIS_TIMEOUT_S", "1200")

    got = resolve_all_fixed_task_runtime(store=store)["card_synthesis"]

    assert got.model_timeout_s == 1200.0
    assert got.source == "env"
    assert got.db_saved is True
    assert store.get_all()["card_synthesis"].model_timeout_s == 600.0


def test_invalid_env_keeps_db_value_and_surfaces_warning(store, monkeypatch):
    store.set_many({"card_synthesis": 700.0})
    monkeypatch.setenv("ARKSCOPE_CARD_SYNTHESIS_TIMEOUT_S", "not-a-number")

    got = resolve_fixed_task_runtime("card_synthesis", store=store)

    assert got.model_timeout_s == 700.0
    assert got.source == "db"
    assert got.db_saved is True
    assert "ARKSCOPE_CARD_SYNTHESIS_TIMEOUT_S" in (got.warning or "")


def test_invalid_env_without_db_keeps_default_and_surfaces_warning(
    store, monkeypatch
):
    monkeypatch.setenv("ARKSCOPE_CARD_TRANSLATION_TIMEOUT_S", "59")

    got = resolve_fixed_task_runtime("card_translation", store=store)

    assert got.model_timeout_s == 900.0
    assert got.source == "default"
    assert got.db_saved is False
    assert "between 60 and 3600" in (got.warning or "")


def test_db_read_failure_returns_defaults_with_warning(store, monkeypatch):
    def fail():
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(store, "get_all", fail)

    settings = resolve_all_fixed_task_runtime(store=store)

    for value in settings.values():
        assert value.model_timeout_s == 900.0
        assert value.source == "default"
        assert value.db_saved is False
        assert "DB read failed" in (value.warning or "")


def test_delete_all_is_idempotent(store):
    store.set_many({"card_synthesis": 700.0, "card_translation": 800.0})

    assert store.delete_all() is True
    assert store.get_all() == {}
    assert store.delete_all() is False


@pytest.mark.parametrize(
    "value",
    [59, 3601, float("nan"), float("inf"), float("-inf"), "not-a-number"],
)
def test_store_rejects_invalid_runtime_values(store, value):
    with pytest.raises(ValueError):
        store.set_many({"card_synthesis": value})
    assert store.get_all() == {}


def test_store_rejects_unknown_task(store):
    with pytest.raises(ValueError, match="unknown fixed task"):
        store.set_many({"ai_research": 900.0})
    assert store.get_all() == {}


def test_set_many_validates_every_value_before_writing(store):
    store.set_many({"card_synthesis": 700.0})

    with pytest.raises(ValueError):
        store.set_many({"card_synthesis": 800.0, "card_translation": 59.0})

    rows = store.get_all()
    assert rows["card_synthesis"].model_timeout_s == 700.0
    assert "card_translation" not in rows
