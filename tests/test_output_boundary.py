"""Offline, synthetic-secret owners for the shared output boundary."""

from __future__ import annotations

import asyncio
import base64
import copy
from concurrent.futures import ThreadPoolExecutor
import importlib
import importlib.util
import json
import pickle
import random
import threading
from urllib.parse import quote, quote_plus

import pytest


MODULE = "src.agents.shared.output_boundary"
MARKER = "[REDACTED]"
SECRET = "fake-secret+/value=42"
UNICODE_SECRET = 'fake-\u5bc6\U0001f512 /+?"\\\n-end'


def boundary():
    assert importlib.util.find_spec(MODULE) is not None, "missing shared output boundary"
    return importlib.import_module(MODULE)


def representations(secret):
    raw = secret.encode("utf-8")
    return {
        "raw": secret,
        "json-unicode": json.dumps(secret, ensure_ascii=False)[1:-1],
        "json-ascii": json.dumps(secret, ensure_ascii=True)[1:-1],
        "url-default": quote(secret),
        "url-all": quote(secret, safe=""),
        "url-plus": quote_plus(secret),
        "base64": base64.b64encode(raw).decode("ascii"),
        "base64-unpadded": base64.b64encode(raw).decode("ascii").rstrip("="),
        "base64-url": base64.urlsafe_b64encode(raw).decode("ascii"),
        "base64-url-unpadded": base64.urlsafe_b64encode(raw).decode("ascii").rstrip("="),
    }


CASES = list(representations(UNICODE_SECRET).items())


def test_shared_output_boundary_exists():
    boundary()


def test_public_business_values_are_unchanged():
    api = boundary()
    guard = api.OutputGuard([SECRET])
    value = {
        "institutionalization": [
            "internationalization counterrevolutionaries",
            "123456789012345678901234567890.000100",
            "-1.234567890123456789E+123",
            "0000320193-26-000123",
            "0123456789abcdef" * 4,
            "https://example.test/news/annual-report?cursor=public_cursor_123456789",
            "eyJvZmZzZXQiOjEyMzQ1Njc4OTB9",
        ],
        "numbers": [None, True, False, 123456789012345678901234567890, 1.25],
    }
    before = copy.deepcopy(value)
    assert guard.check(value) is None
    assert value == before
    prose = json.dumps(value, ensure_ascii=False)
    assert guard.prose(prose) == prose
    stream = guard.stream()
    assert "".join(stream.feed(c) for c in prose) + stream.finish() == prose


@pytest.mark.parametrize("name,encoded", CASES, ids=[name for name, _ in CASES])
def test_known_representations_in_values_and_keys_are_rejected(name, encoded):
    api = boundary()
    guard = api.OutputGuard([UNICODE_SECRET])
    for value in (encoded, {"data": [None, {"value": encoded}]}, {"data": [{encoded: 1}]}):
        with pytest.raises(api.OutputBoundaryError) as error:
            guard.check(value)
        assert error.value.code == "known_secret"
        assert UNICODE_SECRET not in str(error.value)
        assert encoded not in repr(error.value)
    assert guard.prose("before:" + encoded + ":after!") == "before:" + MARKER + ":after!"


@pytest.mark.parametrize("name,encoded", CASES, ids=[name for name, _ in CASES])
def test_every_split_and_single_character_feeds_protect_encoded_secrets(name, encoded):
    api = boundary()
    guard = api.OutputGuard([UNICODE_SECRET])
    for split in range(len(encoded) + 1):
        stream = guard.stream()
        output = stream.feed(encoded[:split]) + stream.feed(encoded[split:]) + stream.finish()
        assert output == MARKER, (name, split)
    stream = guard.stream()
    assert "".join(stream.feed(c) for c in encoded) + stream.finish() == MARKER


@pytest.mark.parametrize(
    "secrets,text,expected",
    [
        (["abc", "bcdef"], "!abcdef!", "!" + MARKER + "!"),
        (["ab", "abcde", "defg"], "!abcdefg!", "!" + MARKER + "!"),
        (["aba", "bab"], "!abababa!", "!" + MARKER + "!"),
        (["xyz"], "!xyzxyz!", "!" + MARKER + "!"),
        (["xy", "12345678901234567890"], "!xy!xy!", "!" + MARKER + "!" + MARKER + "!"),
        (["\u5bc6\U0001f512", "\U0001f512\u6587"], "!\u5bc6\U0001f512\u6587!", "!" + MARKER + "!"),
    ],
)
def test_overlapping_matches_use_raw_offsets_across_every_split(secrets, text, expected):
    guard = boundary().OutputGuard(secrets)
    for split in range(len(text) + 1):
        stream = guard.stream()
        assert stream.feed(text[:split]) + stream.feed(text[split:]) + stream.finish() == expected
    stream = guard.stream()
    assert "".join(stream.feed(c) for c in text) + stream.finish() == expected
    assert guard.prose(text) == expected


def test_normal_finish_preserves_every_unmatched_partial_prefix():
    guard = boundary().OutputGuard([SECRET])
    forms = representations(SECRET).values()
    for encoded in forms:
        for split in range(1, len(encoded)):
            partial = encoded[:split]
            if any(pattern in partial for pattern in forms):
                continue
            stream = guard.stream()
            assert stream.feed("public!" + partial) + stream.finish() == "public!" + partial
            assert stream.finish() == ""


def test_abort_discards_every_pending_partial_prefix():
    guard = boundary().OutputGuard([SECRET])
    for encoded in representations(SECRET).values():
        for split in range(1, len(encoded)):
            stream = guard.stream()
            emitted = stream.feed(encoded[:split])
            assert emitted == ""
            assert stream.abort() is None
            assert stream.finish() == ""
            assert stream.abort() is None


def test_normal_prose_preserves_public_word_ending_in_jwt_prefix():
    api = boundary()
    guard = api.OutputGuard(["eyJ-fake-known-captured-12345"])
    for public in ("source", "active", "estimate", "e"):
        assert guard.prose(public) == public
        stream = guard.stream()
        assert "".join(stream.feed(c) for c in public) + stream.finish() == public
    assert api.OutputGuard(["source"]).prose("source") == MARKER


def test_stream_retains_only_a_bounded_suffix_and_makes_progress():
    api = boundary()
    guard = api.OutputGuard([SECRET])
    stream = guard.stream()
    longest = max(map(len, representations(SECRET).values()))
    total = 0
    emitted = 0
    for _ in range(256):
        chunk = "public!" * 1024
        total += len(chunk)
        part = stream.feed(chunk)
        emitted += len(part)
        assert 0 <= total - emitted <= longest - 1
        assert len(stream._pending) <= longest - 1
        assert not hasattr(stream, "__dict__")
    emitted += len(stream.finish())
    assert emitted == total
    assert stream._pending == ""


@pytest.mark.parametrize("secret", ["x", "xy", "\u5bc6", " "])
def test_very_short_secrets_are_not_ignored(secret):
    api = boundary()
    guard = api.OutputGuard([secret])
    with pytest.raises(api.OutputBoundaryError, match="known_secret"):
        guard.check({secret: "public"})
    assert guard.prose("!" + secret + "!") == "!" + MARKER + "!"


@pytest.mark.parametrize("secret", ["E", MARKER, "a[", "]b"])
def test_marker_and_marker_edge_collisions_fail_closed(secret):
    api = boundary()
    guard = api.OutputGuard([secret])
    with pytest.raises(api.OutputBoundaryError, match="known_secret"):
        guard.check(secret)
    assert guard.prose("public!") == "public!"
    stream = guard.stream()
    with pytest.raises(api.OutputBoundaryError, match="redaction_marker_conflict"):
        stream.feed(secret + "!" * 200)
        stream.finish()
    assert stream.finish() == ""
    assert stream._pending == ""


def test_marker_inside_known_secret_cannot_be_created_by_prose():
    api = boundary()
    guard = api.OutputGuard(["xyz", "a[REDACTED]b"])
    with pytest.raises(api.OutputBoundaryError, match="redaction_marker_conflict"):
        guard.prose("axyzb")


@pytest.mark.parametrize("split", range(6))
def test_marker_inside_known_secret_cannot_be_created_at_any_split(split):
    api = boundary()
    stream = api.OutputGuard(["xyz", "a[REDACTED]b"]).stream()
    text = "axyzb"
    with pytest.raises(api.OutputBoundaryError, match="redaction_marker_conflict"):
        stream.feed(text[:split])
        stream.feed(text[split:])
        stream.finish()
    assert stream.finish() == ""
    assert stream._pending == ""


def test_marker_inside_known_secret_cannot_be_created_by_single_character_feeds():
    api = boundary()
    stream = api.OutputGuard(["xyz", "a[REDACTED]b"]).stream()
    with pytest.raises(api.OutputBoundaryError, match="redaction_marker_conflict"):
        for char in "axyzb":
            stream.feed(char)
        stream.finish()
    assert stream.finish() == ""
    assert stream._pending == ""


def test_marker_inside_known_secret_preserves_unrelated_public_text():
    api = boundary()
    guard = api.OutputGuard(["xyz", "a[REDACTED]b"])
    with pytest.raises(api.OutputBoundaryError, match="known_secret"):
        guard.check("a[REDACTED]b")
    public = "ordinary public source"
    assert guard.check(public) is None
    assert guard.prose(public) == public
    stream = guard.stream()
    assert "".join(stream.feed(char) for char in public) + stream.finish() == public


def test_raw_matching_does_not_guess_unknown_credentials_or_recursive_encodings():
    api = boundary()
    secret = "fake+/ space?"
    guard = api.OutputGuard([secret])
    public = "unknown-credential-like-word-12345678901234567890"
    assert guard.prose(public) == public
    assert guard.check(quote(quote(secret, safe=""), safe="")) is None
    assert guard.check(secret.upper()) is None


def test_empty_secrets_are_absent_and_registration_is_deduplicated():
    api = boundary()
    guard = api.OutputGuard([None, ""])
    assert guard.prose("public") == "public"
    for _ in range(api.MAX_SECRETS * 2):
        guard.add_secret(SECRET)
    assert guard.prose(SECRET) == MARKER


def test_late_registration_protects_pending_and_future_text():
    api = boundary()
    guard = api.OutputGuard(["fake-existing-secret-with-long-prefix"])
    stream = guard.stream()
    assert stream.feed("child-secret-") == ""
    guard.add_secret("child-secret-captured")
    assert stream.feed("captured!") + stream.finish() == MARKER + "!"
    assert guard.prose("child-secret-captured") == MARKER


def test_default_scopes_are_isolated_and_explicit_inheritance_keeps_child_secrets():
    api = boundary()
    assert api.current_output_guard() is None
    with api.output_scope("parent-secret") as parent:
        with api.output_scope("unrelated-secret") as unrelated:
            assert unrelated is not parent
            assert unrelated.check("parent-secret") is None
            assert parent.check("unrelated-secret") is None
        assert api.current_output_guard() is parent
        with api.output_scope("child-secret", inherit=True) as child:
            assert child is parent
            api.remember_output_secret("refreshed-secret")
        for secret in ("parent-secret", "child-secret", "refreshed-secret"):
            with pytest.raises(api.OutputBoundaryError, match="known_secret"):
                parent.check(secret)
    assert api.current_output_guard() is None
    with pytest.raises(api.OutputBoundaryError, match="no_output_scope"):
        api.remember_output_secret(SECRET)
    with api.output_scope(SECRET, inherit=True) as root:
        assert api.current_output_guard() is root
    assert api.current_output_guard() is None


def test_interleaved_async_scopes_are_isolated():
    api = boundary()

    async def run():
        started = asyncio.Event()
        release = asyncio.Event()

        async def first():
            with api.output_scope("first-secret") as guard:
                stream = guard.stream()
                beginning = stream.feed("first-")
                started.set()
                await release.wait()
                assert api.current_output_guard() is guard
                assert guard.check("second-secret") is None
                return beginning + stream.feed("secret") + stream.finish()

        async def second():
            await started.wait()
            with api.output_scope("second-secret") as guard:
                assert guard.check("first-secret") is None
                release.set()
                await asyncio.sleep(0)
                return guard.prose("second-secret")

        assert await asyncio.gather(first(), second()) == [MARKER, MARKER]
        assert api.current_output_guard() is None

    asyncio.run(run())


def test_cancellation_aborts_partial_suffix_and_restores_scope():
    api = boundary()

    async def run():
        ready = asyncio.Event()
        streams = []

        async def cancelled_run():
            with api.output_scope(SECRET) as guard:
                stream = guard.stream()
                streams.append(stream)
                assert stream.feed(SECRET[:8]) == ""
                ready.set()
                await asyncio.Future()

        with api.output_scope("outer-secret") as outer:
            task = asyncio.create_task(cancelled_run())
            await ready.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert api.current_output_guard() is outer
        assert streams[0].finish() == ""
        assert streams[0]._pending == ""
        assert api.current_output_guard() is None

    asyncio.run(run())


def test_inherited_scope_exit_does_not_abort_parent_streams():
    api = boundary()
    with api.output_scope(SECRET) as guard:
        stream = guard.stream()
        assert stream.feed(SECRET[:4]) == ""
        with api.output_scope(inherit=True):
            pass
        assert stream.feed(SECRET[4:]) + stream.finish() == MARKER


def test_activate_borrows_retained_guard_and_restores_context_before_public_yield():
    api = boundary()
    first = api.OutputGuard(["first-secret"])
    second = api.OutputGuard(["second-secret"])

    async def events(guard, secret):
        for _ in range(2):
            with api.activate_output_guard(guard):
                await asyncio.sleep(0)
                assert api.current_output_guard() is guard
                result = guard.prose(secret)
            yield result

    async def run():
        with api.output_scope("outer-secret") as outer:
            one = events(first, "first-secret")
            two = events(second, "second-secret")
            for source in (one, two, one, two):
                assert await anext(source) == MARKER
                assert api.current_output_guard() is outer
            await one.aclose()
            await two.aclose()
            assert api.current_output_guard() is outer
            stream = first.stream()
            stream.feed("first-")
            with pytest.raises(RuntimeError, match="synthetic failure"):
                with api.activate_output_guard(first):
                    with api.activate_output_guard(second):
                        assert api.current_output_guard() is second
                    assert api.current_output_guard() is first
                    raise RuntimeError("synthetic failure")
            assert api.current_output_guard() is outer
            assert stream.feed("secret") + stream.finish() == MARKER
        assert api.current_output_guard() is None

    asyncio.run(run())


@pytest.mark.parametrize("method", [pickle.dumps, copy.copy, copy.deepcopy])
def test_guards_and_streams_have_safe_repr_and_refuse_serialization(method):
    api = boundary()
    guard = api.OutputGuard([SECRET])
    stream = guard.stream()
    stream.feed(SECRET[:8])
    for value in (guard, stream):
        assert SECRET not in repr(value)
        assert SECRET[:8] not in repr(value)
        with pytest.raises(api.OutputBoundaryError, match="not_serializable"):
            method(value)
        with pytest.raises(api.OutputBoundaryError, match="not_serializable"):
            value.__getstate__()


class Hostile:
    def __repr__(self):
        raise AssertionError("must not render rejected value")

    __str__ = __repr__


@pytest.mark.parametrize("value", [Hostile(), b"fake-secret", {1: "value"}, (1, 2), {1, 2}, float("nan"), float("inf")])
def test_non_json_values_fail_without_repr_coercion(value):
    api = boundary()
    with pytest.raises(api.OutputBoundaryError, match="invalid_value") as error:
        api.OutputGuard().check(value)
    assert str(error.value) == "invalid_value"


def test_errors_cannot_store_arbitrary_rejected_details():
    api = boundary()
    for detail in (SECRET, Hostile(), {SECRET: SECRET}):
        error = api.OutputBoundaryError(detail)
        assert error.code == "output_boundary_error"
        assert error.args == ("output_boundary_error",)


def test_secret_bounds_and_invalid_secret_registration_fail_atomically():
    api = boundary()
    guard = api.OutputGuard([SECRET])
    for value, code in ((Hostile(), "invalid_secret"), (b"secret", "invalid_secret"), ("\ud800", "invalid_secret"), ("x" * (api.MAX_SECRET_CHARS + 1), "secret_limit")):
        with pytest.raises(api.OutputBoundaryError, match=code):
            guard.add_secret(value)
        assert guard.prose(SECRET) == MARKER
    full = api.OutputGuard([f"fake-number-{index}!" for index in range(api.MAX_SECRETS)])
    with pytest.raises(api.OutputBoundaryError, match="secret_limit"):
        full.add_secret("over-limit-secret!")
    assert full.check("over-limit-secret!") is None


def test_total_representation_budget_rejects_without_partial_registration():
    api = boundary()
    guard = api.OutputGuard()
    for index in range(api.MAX_SECRETS):
        secret = chr(0x400 + index) * api.MAX_SECRET_CHARS
        try:
            guard.add_secret(secret)
        except api.OutputBoundaryError as error:
            assert error.code == "representation_limit"
            assert guard.check(secret) is None
            break
    else:
        pytest.fail("unbounded representation storage")


def test_json_depth_nodes_strings_cycles_and_shared_references_are_bounded():
    api = boundary()
    guard = api.OutputGuard()
    value = "public!"
    for _ in range(api.MAX_JSON_DEPTH):
        value = [value]
    assert guard.check(value) is None
    with pytest.raises(api.OutputBoundaryError, match="value_limit"):
        guard.check([value])
    assert guard.check([None] * (api.MAX_JSON_NODES - 1)) is None
    with pytest.raises(api.OutputBoundaryError, match="value_limit"):
        guard.check([None] * api.MAX_JSON_NODES)
    with pytest.raises(api.OutputBoundaryError, match="value_limit"):
        guard.check({str(index): None for index in range(api.MAX_JSON_NODES // 2 + 1)})
    shared = {"public": [None]}
    assert guard.check([shared, shared]) is None
    cycle = []
    cycle.append(cycle)
    with pytest.raises(api.OutputBoundaryError, match="invalid_value"):
        guard.check(cycle)
    assert guard.check("!" * api.MAX_TEXT_CHARS) is None
    with pytest.raises(api.OutputBoundaryError, match="value_limit"):
        guard.check(["!" * (api.MAX_TEXT_CHARS // 2 + 1)] * 2)
    with pytest.raises(api.OutputBoundaryError, match="value_limit"):
        guard.prose("!" * (api.MAX_TEXT_CHARS + 1))


def test_invalid_or_oversized_feed_aborts_without_releasing_pending_text():
    api = boundary()
    guard = api.OutputGuard([SECRET])
    for value, code in ((Hostile(), "invalid_value"), ("!" * (api.MAX_STREAM_CHUNK_CHARS + 1), "value_limit")):
        stream = guard.stream()
        stream.feed(SECRET[:8])
        with pytest.raises(api.OutputBoundaryError, match=code):
            stream.feed(value)
        assert stream.finish() == ""
        assert stream._pending == ""
        with pytest.raises(api.OutputBoundaryError, match="stream_closed"):
            stream.feed("public!")


def test_prose_chunks_large_values_and_closed_streams_cannot_resume():
    api = boundary()
    guard = api.OutputGuard([SECRET])
    public = "!" * (65_536 - len(SECRET) // 2)
    assert guard.prose(public + SECRET + "!") == public + MARKER + "!"
    stream = guard.stream()
    stream.finish()
    with pytest.raises(api.OutputBoundaryError, match="stream_closed"):
        stream.feed("public!")


@pytest.mark.parametrize(
    "secret,standard,urlsafe",
    [("\u083f!", "4KC/IQ==", "4KC_IQ=="), ("\u083e!!", "4KC+ISE=", "4KC-ISE=")],
)
def test_base64_alphabets_and_both_padding_lengths(secret, standard, urlsafe):
    api = boundary()
    guard = api.OutputGuard([secret])
    for encoded in (standard, urlsafe, standard.rstrip("="), urlsafe.rstrip("=")):
        with pytest.raises(api.OutputBoundaryError, match="known_secret"):
            guard.check(encoded)
        for split in range(len(encoded) + 1):
            stream = guard.stream()
            assert stream.feed(encoded[:split]) + stream.feed(encoded[split:]) + stream.finish() == MARKER


def test_stream_matches_independent_raw_mask_oracle_under_varied_chunking():
    api = boundary()
    secrets = ["aba", "babca", "bc", "cabc", "abcdef", "de"]
    patterns = set().union(*(representations(secret).values() for secret in secrets))
    guard = api.OutputGuard(secrets)
    rng = random.Random(9211)
    for _ in range(400):
        text = "".join(rng.choice("abcdef!") for _ in range(rng.randrange(1, 160)))
        hidden = [False] * len(text)
        for offset in range(len(text)):
            for pattern in patterns:
                if text.startswith(pattern, offset):
                    hidden[offset:offset + len(pattern)] = [True] * len(pattern)
        expected = []
        for offset, char in enumerate(text):
            if not hidden[offset]:
                expected.append(char)
            elif offset == 0 or not hidden[offset - 1]:
                expected.append(MARKER)
        stream = guard.stream()
        output = []
        offset = 0
        while offset < len(text):
            size = rng.randrange(1, 15)
            output.append(stream.feed(text[offset:offset + size]))
            offset += size
        output.append(stream.finish())
        assert "".join(output) == "".join(expected)


def test_registration_after_emission_makes_no_retroactive_detection_claim():
    api = boundary()
    guard = api.OutputGuard()
    stream = guard.stream()
    already_public = stream.feed(SECRET[:8])
    assert already_public == SECRET[:8]
    guard.add_secret(SECRET)
    assert stream.feed(SECRET + "!") + stream.finish() == MARKER + "!"
    assert already_public == SECRET[:8]


def test_failed_activation_or_root_registration_preserves_previous_context():
    api = boundary()
    with api.output_scope(SECRET) as outer:
        with pytest.raises(api.OutputBoundaryError, match="invalid_value"):
            with api.activate_output_guard(Hostile()):
                pytest.fail("invalid guard activated")
        with pytest.raises(api.OutputBoundaryError, match="invalid_value"):
            with api.output_scope(inherit=Hostile()):
                pytest.fail("invalid inheritance accepted")
        with pytest.raises(api.OutputBoundaryError, match="invalid_secret"):
            with api.output_scope(Hostile()):
                pytest.fail("invalid secret accepted")
        assert api.current_output_guard() is outer


def test_shared_json_policy_accepts_one_million_nodes():
    assert boundary().OutputGuard().check([None] * 999_999) is None


def test_shared_text_policy_accepts_32_mib_ascii_without_reduction():
    guard = boundary().OutputGuard()
    public = "!" * (32 * 1024**2)
    assert guard.check(public) is None
    assert guard.prose(public) == public


def test_feed_accepts_full_provider_text_blocks_above_64_kib():
    guard = boundary().OutputGuard([SECRET])
    prefix = "!" * (65_536 - len(SECRET) // 2)
    suffix = "!" * 200_000
    stream = guard.stream()
    output = stream.feed(prefix + SECRET + suffix)
    assert len(stream._pending) <= max(map(len, representations(SECRET).values())) - 1
    assert output + stream.finish() == prefix + MARKER + suffix


@pytest.mark.parametrize("race", ["registration", "matcher-publication"])
def test_concurrent_registration_cannot_lose_secrets_or_publish_stale_matcher(monkeypatch, race):
    api = boundary()
    paused = threading.Event()
    resume = threading.Event()

    class ObservedLock:
        def __init__(self):
            self.lock = threading.RLock()

        def __enter__(self):
            if threading.current_thread().name.endswith("_1"):
                resume.set()
            return self.lock.__enter__()

        def __exit__(self, *args):
            return self.lock.__exit__(*args)

    # Signal an attempted acquisition, not a sleep or a probabilistic race.
    # Without locking, the second registration instead completes before resume.
    monkeypatch.setattr(api, "RLock", ObservedLock, raising=False)
    first_secret = "first-thread-secret"
    second_secret = "second-thread-secret"
    guard = api.OutputGuard([first_secret] if race == "matcher-publication" else [])
    original = api._Matcher if race == "matcher-publication" else api._representations

    def pause_first(value):
        if threading.current_thread().name.endswith("_0"):
            paused.set()
            assert resume.wait(5), "thread rendezvous timed out"
        return original(value)

    monkeypatch.setattr(api, "_Matcher" if race == "matcher-publication" else "_representations", pause_first)

    def register_second():
        try:
            guard.add_secret(second_secret)
        finally:
            resume.set()

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="output-boundary") as pool:
        first = pool.submit(guard.check, "public!") if race == "matcher-publication" else pool.submit(guard.add_secret, first_secret)
        try:
            assert paused.wait(5), "first operation did not reach rendezvous"
            second = pool.submit(register_second)
            first.result(timeout=5)
            second.result(timeout=5)
        finally:
            resume.set()
    for secret in (first_secret, second_secret):
        for encoded in representations(secret).values():
            with pytest.raises(api.OutputBoundaryError, match="known_secret"):
                guard.check(encoded)
