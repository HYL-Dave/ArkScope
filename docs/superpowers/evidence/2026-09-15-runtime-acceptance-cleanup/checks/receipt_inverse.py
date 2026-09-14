"""Disposable negative control: bypass both current receipt write guards."""


def pytest_runtest_call(item):
    if item.name != "test_incomplete_receipt_blocks_all_lifecycle_writes":
        raise AssertionError("inverse control must target only the moved receipt owner")
    from src import security_lifecycle, security_lifecycle_investigation

    patch = item._request.getfixturevalue("monkeypatch")
    for module in (security_lifecycle, security_lifecycle_investigation):
        patch.setattr(module, "assert_lifecycle_writes_available", lambda conn: None)
