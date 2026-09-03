"""Contracts for the withheld agent-facing Python execution capability."""

from __future__ import annotations

import inspect
from dataclasses import fields
from pathlib import Path
from unittest.mock import MagicMock

from src.agents.shared.prompts import SYSTEM_PROMPT

def test_prompt_discloses_that_arbitrary_python_execution_is_unavailable():
    assert "execute_python_analysis" not in SYSTEM_PROMPT
    assert "Arbitrary Python execution is unavailable" in SYSTEM_PROMPT
    assert "Do not invent precise calculations" in SYSTEM_PROMPT


def test_prompt_routes_supported_precise_math_to_deterministic_tools():
    assert "deterministic financial calculation tools" in SYSTEM_PROMPT
    assert "calculate_dcf" in SYSTEM_PROMPT
    assert "calculate_peer_statistics" in SYSTEM_PROMPT


def test_prompt_preserves_the_tool_vs_subagent_boundary():
    assert "SUBAGENT DELEGATION" in SYSTEM_PROMPT
    assert "TOOL vs SUBAGENT" in SYSTEM_PROMPT
    section = SYSTEM_PROMPT[SYSTEM_PROMPT.index("TOOL vs SUBAGENT") :][:700]
    assert "existing data tools" in section
    assert "code_analyst" in section


def test_registry_withholds_python_execution_from_agents():
    from src.tools.registry import create_default_registry

    assert create_default_registry().get("execute_python_analysis") is None


def test_anthropic_bridge_withholds_python_execution():
    from src.agents.anthropic_agent.tools import get_anthropic_tools

    assert all(
        tool["name"] != "execute_python_analysis" for tool in get_anthropic_tools()
    )


def test_openai_bridge_withholds_python_execution():
    from src.agents.openai_agent.tools import create_openai_tools

    assert all(
        not getattr(tool, "name", "").endswith("execute_python_analysis")
        for tool in create_openai_tools(MagicMock())
    )


def test_direct_code_dispatch_executes_without_a_nested_model_call():
    from src.tools.code_executor import execute_python_code

    result = execute_python_code(
        code='print(data["left"] + data["right"])',
        data_json='{"left": 19, "right": 23}',
    )

    assert result.success is True
    assert result.output.strip() == "42"


def test_executor_and_result_contract_have_no_hidden_or_background_mode():
    from src.tools.code_executor import CodeExecutionResult, execute_python_code

    assert set(inspect.signature(execute_python_code).parameters) == {
        "code",
        "data_json",
        "timeout",
        "blocked_modules",
    }
    assert {field.name for field in fields(CodeExecutionResult)} == {
        "success",
        "output",
        "error",
        "execution_time",
    }


def test_nested_code_generator_and_its_config_are_retired():
    from src.agents.config import AgentConfig

    root = Path(__file__).resolve().parents[1]
    assert not (root / "src/tools/code_generator.py").exists()
    assert {"code_model", "code_max_retries", "code_backend"}.isdisjoint(
        AgentConfig.model_fields
    )


def test_current_tool_catalog_records_python_execution_as_withheld():
    root = Path(__file__).resolve().parents[1]
    catalog = (root / "docs/design/ARKSCOPE_TOOL_CATALOG.md").read_text(
        encoding="utf-8"
    )
    active_rows = (
        line
        for line in catalog.splitlines()
        if line.startswith("|") and "`execute_python_analysis`" in line
    )
    assert list(active_rows) == []
    assert "`execute_python_analysis` is withheld" in catalog
    assert "OS sandbox" in catalog


def test_product_spec_records_the_unimplemented_permission_and_sandbox_boundary():
    root = Path(__file__).resolve().parents[1]
    product_spec = (root / "docs/design/ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md").read_text(
        encoding="utf-8"
    )
    boundary = product_spec.split("**Implementation boundary (2026-09-03):**", 1)[1]
    boundary = boundary.split("### 4.4", 1)[0]

    assert "not an implemented" in boundary
    assert "records intent only" in boundary
    assert "not an OS sandbox" in boundary
    normalized_boundary = boundary.replace("\n> ", " ")
    assert "filesystem, network, process, or resource isolation" in normalized_boundary
    assert "not registered on any agent surface" in normalized_boundary


def test_execution_tool_is_absent_from_both_agent_bridges():
    from src.agents.anthropic_agent.tools import get_anthropic_tools
    from src.agents.openai_agent.tools import create_openai_tools

    assert all(
        tool["name"] != "execute_python_analysis" for tool in get_anthropic_tools()
    )
    assert all(
        not getattr(tool, "name", "").endswith("execute_python_analysis")
        for tool in create_openai_tools(MagicMock())
    )
