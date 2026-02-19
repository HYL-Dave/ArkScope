"""Tests for TokenTracker (Phase 1 of agent evolution)."""

import time
from types import SimpleNamespace

import pytest

from src.agents.shared.token_tracker import TokenTracker, TurnUsage


# ── TurnUsage ──────────────────────────────────────────────────


class TestTurnUsage:
    def test_total_tokens(self):
        t = TurnUsage(turn=1, provider="anthropic", model="claude", input_tokens=100, output_tokens=50)
        assert t.total_tokens == 150

    def test_timestamp_auto(self):
        before = time.time()
        t = TurnUsage(turn=1, provider="openai", model="gpt", input_tokens=0, output_tokens=0)
        after = time.time()
        assert before <= t.timestamp <= after


# ── TokenTracker basics ────────────────────────────────────────


class TestTokenTrackerBasics:
    def test_empty_tracker(self):
        tracker = TokenTracker()
        assert tracker.turn_count == 0
        assert tracker.total_tokens == 0
        assert tracker.total_input_tokens == 0
        assert tracker.total_output_tokens == 0
        assert tracker.last_input_tokens == 0
        assert tracker.turns == []

    def test_record_single(self):
        tracker = TokenTracker()
        usage = tracker.record("anthropic", "claude-sonnet", input_tokens=1000, output_tokens=200)

        assert usage.turn == 1
        assert usage.provider == "anthropic"
        assert usage.model == "claude-sonnet"
        assert usage.input_tokens == 1000
        assert usage.output_tokens == 200

        assert tracker.turn_count == 1
        assert tracker.total_input_tokens == 1000
        assert tracker.total_output_tokens == 200
        assert tracker.total_tokens == 1200
        assert tracker.last_input_tokens == 1000

    def test_record_multiple_turns(self):
        tracker = TokenTracker()
        tracker.record("anthropic", "claude", input_tokens=1000, output_tokens=200)
        tracker.record("anthropic", "claude", input_tokens=1500, output_tokens=300)
        tracker.record("anthropic", "claude", input_tokens=2000, output_tokens=250)

        assert tracker.turn_count == 3
        assert tracker.total_input_tokens == 4500
        assert tracker.total_output_tokens == 750
        assert tracker.total_tokens == 5250
        # last_input_tokens shows the most recent turn's input (context growth indicator)
        assert tracker.last_input_tokens == 2000

    def test_turns_returns_copy(self):
        tracker = TokenTracker()
        tracker.record("openai", "gpt", input_tokens=100, output_tokens=50)
        turns = tracker.turns
        turns.clear()
        assert tracker.turn_count == 1  # original not affected

    def test_repr(self):
        tracker = TokenTracker()
        tracker.record("openai", "gpt", input_tokens=10000, output_tokens=2000)
        assert "turns=1" in repr(tracker)
        assert "12,000" in repr(tracker)

    def test_summary(self):
        tracker = TokenTracker()
        tracker.record("anthropic", "claude", input_tokens=1000, output_tokens=200)
        tracker.record("anthropic", "claude", input_tokens=1500, output_tokens=300)

        s = tracker.summary()
        assert s == {
            "total_input_tokens": 2500,
            "total_output_tokens": 500,
            "total_tokens": 3000,
            "turn_count": 2,
            "last_input_tokens": 1500,
        }


# ── Anthropic integration ─────────────────────────────────────


def _mock_anthropic_response(input_tokens: int, output_tokens: int, model: str = "claude-sonnet-4"):
    """Create a mock Anthropic response with usage."""
    return SimpleNamespace(
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        model=model,
        stop_reason="end_turn",
        content=[],
    )


class TestAnthropicRecording:
    def test_record_anthropic(self):
        tracker = TokenTracker()
        resp = _mock_anthropic_response(1500, 300, "claude-opus-4-6")
        usage = tracker.record_anthropic(resp)

        assert usage is not None
        assert usage.provider == "anthropic"
        assert usage.model == "claude-opus-4-6"
        assert usage.input_tokens == 1500
        assert usage.output_tokens == 300
        assert tracker.total_tokens == 1800

    def test_record_anthropic_model_override(self):
        tracker = TokenTracker()
        resp = _mock_anthropic_response(100, 50, "original-model")
        usage = tracker.record_anthropic(resp, model="override-model")
        assert usage.model == "override-model"

    def test_record_anthropic_model_from_response(self):
        tracker = TokenTracker()
        resp = _mock_anthropic_response(100, 50, "from-response")
        usage = tracker.record_anthropic(resp)
        assert usage.model == "from-response"

    def test_record_anthropic_no_usage(self):
        tracker = TokenTracker()
        resp = SimpleNamespace(content=[], stop_reason="end_turn")  # no .usage
        usage = tracker.record_anthropic(resp)
        assert usage is None
        assert tracker.turn_count == 0

    def test_multi_turn_anthropic_session(self):
        """Simulate a typical 3-turn Anthropic session with growing context."""
        tracker = TokenTracker()

        # Turn 1: initial query
        tracker.record_anthropic(_mock_anthropic_response(800, 200))
        # Turn 2: after tool call result added to messages
        tracker.record_anthropic(_mock_anthropic_response(1500, 300))
        # Turn 3: after second tool call
        tracker.record_anthropic(_mock_anthropic_response(2200, 400))

        assert tracker.turn_count == 3
        assert tracker.total_input_tokens == 4500
        assert tracker.total_output_tokens == 900
        # Context is growing: 800 → 1500 → 2200
        assert tracker.last_input_tokens == 2200


# ── OpenAI integration ─────────────────────────────────────────


def _mock_openai_result(usages: list[tuple[int, int]], model: str = "gpt-5.2"):
    """Create a mock OpenAI RunResult with raw_responses containing usage."""
    raw_responses = []
    for inp, out in usages:
        raw_responses.append(
            SimpleNamespace(
                usage=SimpleNamespace(input_tokens=inp, output_tokens=out),
                model=model,
                output=[],
            )
        )
    return SimpleNamespace(
        final_output="answer",
        raw_responses=raw_responses,
    )


class TestOpenAIRecording:
    def test_record_openai_result(self):
        tracker = TokenTracker()
        result = _mock_openai_result([(1000, 200), (1500, 300)])
        recorded = tracker.record_openai_result(result, model="gpt-5.2")

        assert len(recorded) == 2
        assert tracker.turn_count == 2
        assert tracker.total_input_tokens == 2500
        assert tracker.total_output_tokens == 500
        assert all(t.provider == "openai" for t in recorded)

    def test_record_openai_no_raw_responses(self):
        tracker = TokenTracker()
        result = SimpleNamespace(final_output="answer")  # no raw_responses
        recorded = tracker.record_openai_result(result, model="gpt-5.2")
        assert recorded == []
        assert tracker.turn_count == 0

    def test_record_openai_no_usage_in_response(self):
        tracker = TokenTracker()
        result = SimpleNamespace(
            final_output="answer",
            raw_responses=[SimpleNamespace(output=[], model="gpt-5.2")],  # no .usage
        )
        recorded = tracker.record_openai_result(result, model="gpt-5.2")
        assert recorded == []
        assert tracker.turn_count == 0

    def test_record_openai_prompt_tokens_fallback(self):
        """OpenAI may use prompt_tokens instead of input_tokens."""
        tracker = TokenTracker()
        result = SimpleNamespace(
            final_output="answer",
            raw_responses=[
                SimpleNamespace(
                    usage=SimpleNamespace(
                        input_tokens=0,
                        output_tokens=0,
                        prompt_tokens=900,
                        completion_tokens=150,
                    ),
                    model="gpt-5.2",
                    output=[],
                ),
            ],
        )
        recorded = tracker.record_openai_result(result, model="gpt-5.2")
        assert len(recorded) == 1
        assert recorded[0].input_tokens == 900
        assert recorded[0].output_tokens == 150

    def test_record_openai_model_from_response(self):
        tracker = TokenTracker()
        result = _mock_openai_result([(100, 50)], model="gpt-5.2-turbo")
        recorded = tracker.record_openai_result(result)  # no model override
        assert recorded[0].model == "gpt-5.2-turbo"


# ── Mixed provider session ─────────────────────────────────────


class TestMixedProviderSession:
    def test_mixed_providers(self):
        """Track usage across different providers in one tracker."""
        tracker = TokenTracker()
        tracker.record("anthropic", "claude", input_tokens=1000, output_tokens=200)
        tracker.record("openai", "gpt-5.2", input_tokens=500, output_tokens=100)

        assert tracker.turn_count == 2
        assert tracker.total_tokens == 1800
        assert tracker.turns[0].provider == "anthropic"
        assert tracker.turns[1].provider == "openai"


# ── Cache token tracking ──────────────────────────────────────


class TestCacheTokenFields:
    """Tests for prompt caching token tracking (Anthropic + OpenAI)."""

    def test_turn_usage_default_cache_zero(self):
        usage = TurnUsage(
            turn=1, provider="anthropic", model="claude-opus-4-6",
            input_tokens=100, output_tokens=50,
        )
        assert usage.cache_creation_tokens == 0
        assert usage.cache_read_tokens == 0

    def test_turn_usage_explicit_cache(self):
        usage = TurnUsage(
            turn=1, provider="anthropic", model="claude-opus-4-6",
            input_tokens=100, output_tokens=50,
            cache_creation_tokens=5000, cache_read_tokens=3000,
        )
        assert usage.cache_creation_tokens == 5000
        assert usage.cache_read_tokens == 3000

    def test_record_with_cache_tokens(self):
        tracker = TokenTracker()
        usage = tracker.record(
            provider="anthropic", model="test",
            input_tokens=100, output_tokens=50,
            cache_creation_tokens=6000,
        )
        assert usage.cache_creation_tokens == 6000
        assert usage.cache_read_tokens == 0

    def test_record_defaults_cache_to_zero(self):
        tracker = TokenTracker()
        usage = tracker.record(
            provider="openai", model="test",
            input_tokens=100, output_tokens=50,
        )
        assert usage.cache_creation_tokens == 0
        assert usage.cache_read_tokens == 0


class TestAnthropicCacheRecording:
    """Anthropic API returns cache_creation_input_tokens + cache_read_input_tokens."""

    def _mock_response(self, cache_create=0, cache_read=0):
        return SimpleNamespace(
            model="claude-opus-4-6",
            usage=SimpleNamespace(
                input_tokens=100, output_tokens=50,
                cache_creation_input_tokens=cache_create,
                cache_read_input_tokens=cache_read,
            ),
        )

    def test_cache_creation(self):
        tracker = TokenTracker()
        usage = tracker.record_anthropic(self._mock_response(cache_create=6500))
        assert usage.cache_creation_tokens == 6500
        assert usage.cache_read_tokens == 0

    def test_cache_read(self):
        tracker = TokenTracker()
        usage = tracker.record_anthropic(self._mock_response(cache_read=6500))
        assert usage.cache_creation_tokens == 0
        assert usage.cache_read_tokens == 6500

    def test_both_cache_fields(self):
        tracker = TokenTracker()
        usage = tracker.record_anthropic(
            self._mock_response(cache_create=1000, cache_read=5000)
        )
        assert usage.cache_creation_tokens == 1000
        assert usage.cache_read_tokens == 5000

    def test_missing_cache_attrs(self):
        """Old API responses without cache fields."""
        tracker = TokenTracker()
        resp = SimpleNamespace(
            model="claude-opus-4-6",
            usage=SimpleNamespace(input_tokens=100, output_tokens=50),
        )
        usage = tracker.record_anthropic(resp)
        assert usage.cache_creation_tokens == 0
        assert usage.cache_read_tokens == 0

    def test_none_cache_attrs(self):
        """Explicit None values treated as 0."""
        tracker = TokenTracker()
        resp = SimpleNamespace(
            model="claude-opus-4-6",
            usage=SimpleNamespace(
                input_tokens=100, output_tokens=50,
                cache_creation_input_tokens=None,
                cache_read_input_tokens=None,
            ),
        )
        usage = tracker.record_anthropic(resp)
        assert usage.cache_creation_tokens == 0
        assert usage.cache_read_tokens == 0


class TestOpenAICacheRecording:
    """OpenAI auto-caching: usage.prompt_tokens_details.cached_tokens."""

    def _mock_result(self, cached_tokens=0):
        details = SimpleNamespace(cached_tokens=cached_tokens) if cached_tokens else None
        resp = SimpleNamespace(
            model="gpt-5.2",
            usage=SimpleNamespace(
                input_tokens=200, output_tokens=100,
                prompt_tokens=0, completion_tokens=0,
                prompt_tokens_details=details,
            ),
        )
        return SimpleNamespace(raw_responses=[resp])

    def test_cached_tokens_recorded(self):
        tracker = TokenTracker()
        turns = tracker.record_openai_result(self._mock_result(8000), model="gpt-5.2")
        assert turns[0].cache_read_tokens == 8000
        assert turns[0].cache_creation_tokens == 0

    def test_no_cache_details(self):
        tracker = TokenTracker()
        turns = tracker.record_openai_result(self._mock_result(0), model="gpt-5.2")
        assert turns[0].cache_read_tokens == 0

    def test_missing_details_attr(self):
        tracker = TokenTracker()
        resp = SimpleNamespace(
            model="gpt-5.2",
            usage=SimpleNamespace(
                input_tokens=200, output_tokens=100,
                prompt_tokens=0, completion_tokens=0,
            ),
        )
        result = SimpleNamespace(raw_responses=[resp])
        turns = tracker.record_openai_result(result, model="gpt-5.2")
        assert turns[0].cache_read_tokens == 0


class TestSummaryCacheFields:
    def test_summary_no_cache_omits_keys(self):
        tracker = TokenTracker()
        tracker.record("anthropic", "test", 100, 50)
        s = tracker.summary()
        assert "cache_creation_tokens" not in s
        assert "cache_read_tokens" not in s

    def test_summary_with_cache_creation(self):
        tracker = TokenTracker()
        tracker.record("anthropic", "test", 100, 50, cache_creation_tokens=6500)
        s = tracker.summary()
        assert s["cache_creation_tokens"] == 6500
        assert s["cache_read_tokens"] == 0

    def test_summary_with_cache_read(self):
        tracker = TokenTracker()
        tracker.record("anthropic", "test", 100, 50, cache_read_tokens=6500)
        s = tracker.summary()
        assert s["cache_read_tokens"] == 6500

    def test_summary_multi_turn_aggregation(self):
        tracker = TokenTracker()
        tracker.record("anthropic", "test", 100, 50, cache_creation_tokens=6500)
        tracker.record("anthropic", "test", 100, 50, cache_read_tokens=6500)
        tracker.record("anthropic", "test", 100, 50, cache_read_tokens=6500)
        s = tracker.summary()
        assert s["cache_creation_tokens"] == 6500
        assert s["cache_read_tokens"] == 13000

    def test_summary_mixed_providers(self):
        tracker = TokenTracker()
        tracker.record("anthropic", "claude", 100, 50, cache_creation_tokens=5000)
        tracker.record("openai", "gpt", 200, 100, cache_read_tokens=8000)
        s = tracker.summary()
        assert s["cache_creation_tokens"] == 5000
        assert s["cache_read_tokens"] == 8000