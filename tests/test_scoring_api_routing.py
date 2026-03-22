"""Regression tests for GPT-5.4 scoring scripts using the Responses API."""

from types import SimpleNamespace

import scripts.scoring.openai_summary as summary_mod
import scripts.scoring.score_risk_openai as risk_mod
import scripts.scoring.score_sentiment_openai as sentiment_mod


def _fake_usage(input_tokens=11, output_tokens=7, total_tokens=18):
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


class TestScoringResponsesApiRouting:
    def test_sentiment_gpt54_uses_responses(self, monkeypatch):
        sentiment_mod.set_api_keys(["test-key"], None)
        sentiment_mod.TOTAL_PROMPT_TOKENS = 0
        sentiment_mod.TOTAL_COMPLETION_TOKENS = 0
        sentiment_mod.TOTAL_TOKENS = 0

        def fake_responses_create(**kwargs):
            assert kwargs["model"] == "gpt-5.4"
            assert kwargs["tool_choice"] == {"type": "function", "name": "record_score"}
            return SimpleNamespace(
                usage=_fake_usage(),
                output=[
                    SimpleNamespace(
                        type="function_call",
                        name="record_score",
                        arguments='{"score": 5}',
                    )
                ],
                output_text="",
            )

        def fail_chat(**kwargs):
            raise AssertionError("gpt-5.4 sentiment scoring should not use chat.completions")

        monkeypatch.setattr(sentiment_mod.openai.responses, "create", fake_responses_create)
        monkeypatch.setattr(sentiment_mod.openai.chat.completions, "create", fail_chat)

        score = sentiment_mod.score_headline(
            headline="NVIDIA raises guidance",
            symbol="NVDA",
            model="gpt-5.4",
            reasoning_effort="xhigh",
            retry=1,
            pause=0,
        )

        assert score == 5
        assert sentiment_mod.TOTAL_TOKENS == 18

    def test_risk_gpt54_uses_responses(self, monkeypatch):
        risk_mod.set_api_keys(["test-key"], None)
        risk_mod.TOTAL_PROMPT_TOKENS = 0
        risk_mod.TOTAL_COMPLETION_TOKENS = 0
        risk_mod.TOTAL_TOKENS = 0

        def fake_responses_create(**kwargs):
            assert kwargs["model"] == "gpt-5.4"
            assert kwargs["tool_choice"] == {"type": "function", "name": "record_score"}
            return SimpleNamespace(
                usage=_fake_usage(),
                output=[
                    SimpleNamespace(
                        type="function_call",
                        name="record_score",
                        arguments='{"score": 4}',
                    )
                ],
                output_text="",
            )

        def fail_chat(**kwargs):
            raise AssertionError("gpt-5.4 risk scoring should not use chat.completions")

        monkeypatch.setattr(risk_mod.openai.responses, "create", fake_responses_create)
        monkeypatch.setattr(risk_mod.openai.chat.completions, "create", fail_chat)

        score = risk_mod.score_headline(
            headline="Company warns about covenant pressure",
            symbol="XYZ",
            model="gpt-5.4",
            reasoning_effort="xhigh",
            retry=1,
            pause=0,
        )

        assert score == 4
        assert risk_mod.TOTAL_TOKENS == 18

    def test_summary_gpt54_uses_responses(self, monkeypatch):
        summary_mod.set_api_keys(["test-key"], None)
        summary_mod.TOTAL_PROMPT_TOKENS = 0
        summary_mod.TOTAL_COMPLETION_TOKENS = 0
        summary_mod.TOTAL_TOKENS = 0
        summary_mod.MAX_COMPLETION_TOKENS = 0

        def fake_responses_create(**kwargs):
            assert kwargs["model"] == "gpt-5.4"
            assert kwargs["tool_choice"] == {"type": "function", "name": "record_summary"}
            return SimpleNamespace(
                usage=_fake_usage(),
                output=[
                    SimpleNamespace(
                        type="function_call",
                        name="record_summary",
                        arguments='{"summary": "Revenue grew and management raised guidance."}',
                    )
                ],
                output_text="",
            )

        def fail_chat(**kwargs):
            raise AssertionError("gpt-5.4 summarization should not use chat.completions")

        monkeypatch.setattr(summary_mod.openai.responses, "create", fake_responses_create)
        monkeypatch.setattr(summary_mod.openai.chat.completions, "create", fail_chat)

        summary, prompt_tokens, completion_tokens = summary_mod.summarize_article(
            text="Revenue grew strongly and management raised guidance for the year.",
            symbol="NVDA",
            model="gpt-5.4",
            reasoning_effort="high",
            retry=1,
            pause=0,
        )

        assert summary == "Revenue grew and management raised guidance."
        assert prompt_tokens == 11
        assert completion_tokens == 7
        assert summary_mod.TOTAL_TOKENS == 18
