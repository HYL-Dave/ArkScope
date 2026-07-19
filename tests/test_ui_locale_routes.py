from __future__ import annotations

import sqlite3

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.api.routes import profile as routes
from src.api.routes.profile import (
    UI_LOCALE_KEY,
    UiLocaleBody,
    get_ui_locale,
    set_ui_locale,
)
from src.profile_state import ProfileStateStore


@pytest.fixture()
def store(tmp_path):
    return ProfileStateStore(tmp_path / "profile_state.db")


def _stored_setting_count(store: ProfileStateStore) -> int:
    with sqlite3.connect(store.db_path) as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM profile_settings WHERE key = ?",
                (UI_LOCALE_KEY,),
            ).fetchone()[0]
        )


def test_get_ui_locale_defaults_to_zh_hant_without_writing(store):
    assert _stored_setting_count(store) == 0

    assert get_ui_locale(store=store) == {
        "locale": "zh-Hant",
        "source": "default",
    }

    assert _stored_setting_count(store) == 0


def test_get_ui_locale_returns_stored_zh_hant(store):
    store.set_setting(UI_LOCALE_KEY, "zh-Hant")

    assert get_ui_locale(store=store) == {
        "locale": "zh-Hant",
        "source": "stored",
    }


def test_get_ui_locale_returns_stored_en(store):
    store.set_setting(UI_LOCALE_KEY, "en")

    assert get_ui_locale(store=store) == {
        "locale": "en",
        "source": "stored",
    }


def test_get_ui_locale_rejects_corrupt_value_without_mutation_or_leak(store):
    store.set_setting(UI_LOCALE_KEY, "fr-private-value")

    with pytest.raises(HTTPException) as exc_info:
        get_ui_locale(store=store)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == {"code": "invalid_ui_locale"}
    assert "fr-private-value" not in str(exc_info.value.detail)
    assert store.get_setting(UI_LOCALE_KEY) == "fr-private-value"


def test_put_ui_locale_accepts_both_supported_values(store, monkeypatch):
    calls: list[tuple[str, dict[str, str]]] = []
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda action, detail: calls.append((action, detail)),
    )

    for locale in ("zh-Hant", "en"):
        assert set_ui_locale(UiLocaleBody(locale=locale), store=store) == {
            "locale": locale,
            "source": "stored",
        }
        assert store.get_setting(UI_LOCALE_KEY) == locale

    assert calls == [
        ("set_ui_locale", {"locale": "zh-Hant"}),
        ("set_ui_locale", {"locale": "en"}),
    ]


def test_put_ui_locale_gates_before_writing(monkeypatch):
    events: list[tuple[str, object]] = []

    class Store:
        def set_setting(self, key: str, value: str) -> None:
            events.append(("write", (key, value)))

    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda action, detail: events.append(("permission", (action, detail))),
    )

    assert set_ui_locale(UiLocaleBody(locale="en"), store=Store()) == {
        "locale": "en",
        "source": "stored",
    }
    assert events == [
        ("permission", ("set_ui_locale", {"locale": "en"})),
        ("write", (UI_LOCALE_KEY, "en")),
    ]


def test_put_ui_locale_rejects_unknown_payload_without_writing(monkeypatch):
    events: list[object] = []
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda *args, **kwargs: events.append((args, kwargs)),
    )

    with pytest.raises(ValidationError):
        UiLocaleBody(locale="fr")

    assert events == []
