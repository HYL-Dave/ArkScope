"""Model-catalog content admission, with synthetic credentials and no CLI."""

import base64
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from src.agents.shared.output_boundary import output_scope
from src.auth_drivers.codex_account_usage import (
    CodexAccountUsageAdapter,
    CodexAccountUsageError,
    _model_catalog_page,
)
from tests.test_subscription_account_usage import _model_list_payload, _token_record


def _adapter(monkeypatch, pages, *, plan="plus"):
    adapter = CodexAccountUsageAdapter(executable="unused")
    calls = []

    class Session:
        def request(self, request_id, method, params):
            calls.append((request_id, method, deepcopy(params)))
            return deepcopy(pages[min(len(calls) - 1, len(pages) - 1)])

    monkeypatch.setattr(
        adapter,
        "_run_authenticated",
        lambda *, record, operation: (
            SimpleNamespace(account_id="account-fixture", plan_type=plan),
            operation(Session()),
        ),
    )
    return adapter, calls


@pytest.mark.parametrize("field", ["id", "model"])
@pytest.mark.parametrize("identifier", [
    "Consolidated", "Manufacturing", "gpt-5.3-codex-spark-v2",
    "123456789012345678901234", "model_" + "a" * 64,
    "eyJ.ordinary.model", "e30.e30.c2ln",
])
def test_public_catalog_identifiers_are_not_diagnostic_tokens(monkeypatch, field, identifier):
    page = _model_list_payload()
    page["data"][0][field] = identifier
    adapter, calls = _adapter(monkeypatch, [page])

    models, plan = adapter.read_model_catalog_with_plan(record=_token_record())

    assert getattr(models[0], "catalog_id" if field == "id" else "model") == identifier
    assert plan == "plus"
    assert len(calls) == 1


@pytest.mark.parametrize("field", ["id", "model", "displayName", "description", "nextCursor", "key"])
@pytest.mark.parametrize("credential_field", ["access", "refresh", "id"])
@pytest.mark.parametrize("encoded", [False, True])
def test_catalog_rejects_captured_credentials_before_cursor_reuse(
    monkeypatch, field, credential_field, encoded,
):
    secret = "catalog-bearer-fixture-secret"
    record = _token_record()
    if credential_field == "access":
        record = replace(record, access_token=secret)
    elif credential_field == "refresh":
        record = replace(record, refresh_token=secret)
    else:
        record = replace(record, metadata={**record.metadata, "id_token": secret})
    value = base64.urlsafe_b64encode(secret.encode()).decode().rstrip("=") if encoded else secret
    page = _model_list_payload()
    if field == "nextCursor":
        page[field] = value
    elif field == "key":
        page["data"][0][value] = "public"
    else:
        page["data"][0][field] = value
    adapter, calls = _adapter(monkeypatch, [page])

    with pytest.raises(CodexAccountUsageError, match="^protocol_incompatible$") as failure:
        adapter.read_model_catalog_with_plan(record=record)

    assert secret not in str(failure.value)
    assert value not in str(failure.value)
    assert len(calls) == 1


def test_catalog_rejects_captured_credential_in_returned_plan(monkeypatch):
    record = _token_record()
    adapter, calls = _adapter(monkeypatch, [_model_list_payload()], plan=record.access_token)
    with pytest.raises(CodexAccountUsageError, match="^protocol_incompatible$"):
        adapter.read_model_catalog_with_plan(record=record)
    assert len(calls) == 1


def test_catalog_guard_does_not_borrow_unrelated_execution_secrets(monkeypatch):
    page = _model_list_payload()
    page["data"][0]["description"] = "A public catalog description."
    adapter, _ = _adapter(monkeypatch, [page])
    with output_scope("catalog"):
        models = adapter.read_model_catalog(record=_token_record())
    assert models[0].description == page["data"][0]["description"]


@pytest.mark.parametrize("identifier", [
    "", "model name", "a" * 81, "model/new", "model\n",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJsZWFrIn0.SIG",
])
def test_catalog_keeps_lexical_and_explicit_jwt_constraints(identifier):
    page = _model_list_payload()
    page["data"][0]["model"] = identifier
    with pytest.raises(CodexAccountUsageError, match="^protocol_incompatible$"):
        _model_catalog_page(page)


def test_public_pagination_cursor_and_long_description_remain_lossless(monkeypatch):
    first = _model_list_payload()
    first["data"][0]["hidden"] = True
    first["nextCursor"] = "opaque-public-cursor-12345678901234567890"
    second = _model_list_payload()
    second["data"][0]["model"] = "gpt-next-fixture"
    second["data"][0]["description"] = "Consolidated Comprehensive Stockholders Manufacturing"
    adapter, calls = _adapter(monkeypatch, [first, second])
    models = adapter.read_model_catalog(record=_token_record())
    assert len(models) == 1
    assert models[0].description == second["data"][0]["description"]
    assert [call[2]["cursor"] for call in calls] == [None, first["nextCursor"]]
