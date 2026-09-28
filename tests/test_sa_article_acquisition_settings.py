import json

import pytest

from src.data_source_routing import DataSourcePolicyFailure


def settings_module():
    from src.sa import article_acquisition_settings
    return article_acquisition_settings


def test_default_article_settings():
    assert settings_module().parse_article_settings(None).model_dump() == {
        "max_articles_per_job": 0, "body_scope": "all_retained",
        "body_lookback_days": 0, "comment_scope": "current",
    }


@pytest.mark.parametrize("key", ["max_articles_per_job", "body_lookback_days"])
@pytest.mark.parametrize("value", [True, False, 1.5, -1, 2**53, "1", None])
def test_rejects_invalid_limits(key, value):
    with pytest.raises(DataSourcePolicyFailure, match="sa_article_settings_invalid"):
        settings_module().parse_article_settings(json.dumps({key: value}))


@pytest.mark.parametrize("raw", ["{", "[]", "null", '{"unknown": 1}',
                                 '{"body_scope":"former"}', '{"comment_scope":true}'])
def test_invalid_saved_settings_never_become_unlimited(raw):
    module = settings_module()
    with pytest.raises(DataSourcePolicyFailure, match="sa_article_settings_invalid"):
        module.parse_article_settings(raw)
    view = module.article_settings_view(raw)
    assert view["values"] is None
    assert view["error_code"] == "sa_article_settings_invalid"


def test_explicit_roundtrip_and_safe_integer_boundary():
    module = settings_module()
    value = dict(max_articles_per_job=8, body_lookback_days=2**53 - 1,
                 body_scope="current", comment_scope="tracked")
    assert module.parse_article_settings(json.dumps(value)).model_dump() == value


def test_load_uses_readonly_profile_setting(monkeypatch):
    module = settings_module()
    calls = []
    def read(key, dal):
        calls.append((key, dal))
        return '{"max_articles_per_job":9}'
    monkeypatch.setattr(module, "read_setting", read)
    assert module.load_article_settings("private-dal").max_articles_per_job == 9
    assert calls == [("data_sources.sa_article_acquisition.settings", "private-dal")]
