import importlib


def policy_module():
    return importlib.import_module("src.news_normalized.body_policy")


def body(
    digest,
    *,
    raw="raw",
    clean="clean",
    fetched_at=None,
    clean_error=None,
):
    return policy_module().PreparedBody(
        body_sha256=digest,
        raw_body=raw,
        raw_format="text",
        body_text=clean,
        cleaner_version="test-v1" if clean is not None else None,
        clean_error=clean_error,
        fetched_at=fetched_at,
    )


def test_active_body_prefers_clean_content_then_length():
    short = body("a" * 64, raw="short", clean="short", fetched_at="2026-06-29")
    long = body("b" * 64, raw="long complete body", clean="long complete body")
    broken = body(
        "c" * 64,
        raw="x" * 100,
        clean=None,
        clean_error="clean failed",
        fetched_at="2026-06-30",
    )

    assert policy_module().choose_active_body((short, long, broken)) == long


def test_active_body_prefers_raw_length_after_clean_length():
    short_raw = body("a" * 64, raw="body", clean="same")
    long_raw = body("b" * 64, raw="body with markup", clean="same")

    assert policy_module().choose_active_body((short_raw, long_raw)) == long_raw


def test_active_body_prefers_later_fetch_time_after_lengths():
    old = body("a" * 64, fetched_at="2026-06-28T00:00:00Z")
    new = body("b" * 64, fetched_at="2026-06-29T00:00:00Z")

    assert policy_module().choose_active_body((old, new)) == new


def test_active_body_uses_lexicographically_smaller_digest_as_final_tie():
    left = body("a" * 64)
    right = body("b" * 64)

    assert policy_module().choose_active_body((right, left)) == left


def test_active_body_rejects_empty_input():
    try:
        policy_module().choose_active_body(())
    except ValueError as exc:
        assert str(exc) == "at least one body is required"
    else:
        raise AssertionError("empty body selection must fail")
