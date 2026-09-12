"""The unused OpenAI sync facade must not return as a second Research path."""

import ast
import inspect
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_openai_sync_implementation_is_removed():
    tree = ast.parse((ROOT / "src/agents/openai_agent/agent.py").read_text())
    names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "run_query_sync" not in names
    assert {"run_query", "run_query_stream"} <= names


def test_openai_sync_entrypoint_is_not_exported():
    from src.agents import openai_agent

    assert "run_query_sync" not in openai_agent.__all__
    assert not hasattr(openai_agent, "run_query_sync")


def test_retained_research_entrypoints_are_available():
    from src.agents.anthropic_agent import agent as anthropic
    from src.agents.openai_agent import agent as openai

    assert inspect.iscoroutinefunction(openai.run_query)
    assert inspect.isasyncgenfunction(inspect.unwrap(openai.run_query_stream))
    assert callable(anthropic.run_query)
    assert not inspect.iscoroutinefunction(anthropic.run_query)
    assert inspect.isasyncgenfunction(inspect.unwrap(anthropic.run_query_stream))
