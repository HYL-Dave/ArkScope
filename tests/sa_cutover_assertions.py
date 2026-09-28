"""Exact idle-checkpoint contract shared by simulated and installed cutovers."""

from copy import deepcopy


def assert_financial_checkpoint_preserved(before: dict, after: dict) -> None:
    for checkpoint in (before, after):
        assert not checkpoint["browser"].get("saAcquisitionPending"), "saAcquisitionPending is not idle"
        assert checkpoint["native"]["active"] is None, "native.active is not idle"
    left, right = deepcopy(before), deepcopy(after)
    for checkpoint in (left, right):
        checkpoint["browser"]["companyFinancialRefresh"].pop("next_wake_at", None)

    def compare(a, b, field):
        assert type(a) is type(b), field
        if isinstance(a, dict):
            assert a.keys() == b.keys(), field + ".keys"
            for key in a:
                compare(a[key], b[key], field + "." + key)
        else:
            assert a == b, field
    compare(left, right, "checkpoint")
