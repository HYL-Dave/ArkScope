"""C15 retirement boundaries, separate from retained schema and data."""

from importlib.util import find_spec

import pytest


@pytest.mark.parametrize("module", (
    "src.security_lifecycle_listing_migration",
    "src.security_lifecycle_provider_migration",
))
def test_obsolete_converter_is_absent_without_forwarding_module(module):
    assert find_spec(module) is None


@pytest.mark.parametrize("consumer", ("migration", "disposal"))
def test_current_investigation_helpers_have_a_current_owner(consumer):
    from importlib import import_module

    module = import_module(f"src.lifecycle_investigation.{consumer}")
    assert module._sha_file.__module__ == "src.lifecycle_investigation.sqlite_helpers"
    assert module.q.__module__ == "src.lifecycle_investigation.sqlite_helpers"
    if consumer == "migration":
        assert module._encode_cell.__module__ == "src.lifecycle_investigation.sqlite_helpers"
