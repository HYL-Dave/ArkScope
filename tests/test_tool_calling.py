"""Contract tests for direct, caller-authored Python analysis."""

from __future__ import annotations

import inspect
from dataclasses import fields
from pathlib import Path
from unittest.mock import MagicMock

from src.agents.shared.prompts import SYSTEM_PROMPT

_PUBLIC_PARAMETERS = {"code", "data_json", "timeout"}


def _openai_execution_tool():
    from src.agents.openai_agent.tools import create_openai_tools

    return next(
        tool
        for tool in create_openai_tools(MagicMock())
        if getattr(tool, "name", "").endswith("execute_python_analysis")
    )


def _anthropic_execution_tool() -> dict:
    from src.agents.anthropic_agent.tools import get_anthropic_tools

    return next(
        tool
        for tool in get_anthropic_tools()
        if tool["name"] == "execute_python_analysis"
    )


def test_prompt_requires_auditable_calculation_and_caller_authored_code():
    assert "ALWAYS use execute_python_analysis" in SYSTEM_PROMPT
    assert "DO NOT CALCULATE MENTALLY" in SYSTEM_PROMPT.upper()
    section = SYSTEM_PROMPT[SYSTEM_PROMPT.index("CODE EXECUTION") :]
    assert "write" in section.lower() and "Python code" in section
    assert "inspect" in section.lower() and "error" in section.lower()
    assert "auto-generates" not in section


def test_prompt_preserves_the_tool_vs_subagent_boundary():
    assert "SUBAGENT DELEGATION" in SYSTEM_PROMPT
    assert "TOOL vs SUBAGENT" in SYSTEM_PROMPT
    section = SYSTEM_PROMPT[SYSTEM_PROMPT.index("TOOL vs SUBAGENT") :][:700]
    assert "execute_python_analysis" in section
    assert "code_analyst" in section


def test_registry_exposes_only_the_direct_code_contract():
    from src.tools.registry import create_default_registry

    tool = create_default_registry().get("execute_python_analysis")
    assert tool is not None
    assert {parameter.name for parameter in tool.parameters} == _PUBLIC_PARAMETERS
    assert next(parameter for parameter in tool.parameters if parameter.name == "code").required
    assert "mentally" in tool.description.lower()
    assert "restricted" in tool.description.lower()
    assert "sandbox" not in tool.description.lower()


def test_anthropic_bridge_exposes_only_the_direct_code_contract():
    tool = _anthropic_execution_tool()
    assert set(tool["input_schema"]["properties"]) == _PUBLIC_PARAMETERS
    assert tool["input_schema"]["required"] == ["code"]
    assert "restricted" in tool["description"].lower()
    assert "sandbox" not in tool["description"].lower()


def test_openai_bridge_exposes_only_the_direct_code_contract():
    tool = _openai_execution_tool()
    assert set(tool.params_json_schema["properties"]) == _PUBLIC_PARAMETERS
    assert "restricted" in tool.description.lower()
    assert "sandbox" not in tool.description.lower()


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


def test_current_tool_catalog_has_the_exact_direct_contract():
    root = Path(__file__).resolve().parents[1]
    catalog = (root / "docs/design/ARKSCOPE_TOOL_CATALOG.md").read_text(
        encoding="utf-8"
    )
    row = next(
        line for line in catalog.splitlines() if "`execute_python_analysis`" in line
    )
    assert "code*" in row
    assert "data_json?" in row
    assert "timeout?" in row
    assert "task?" not in row
    assert "background?" not in row


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
    assert "filesystem, network, process, or resource isolation" in boundary


def test_execution_tool_remains_present_in_both_agent_bridges():
    from src.agents.anthropic_agent.tools import get_anthropic_tools
    from src.agents.openai_agent.tools import create_openai_tools

    assert any(
        tool["name"] == "execute_python_analysis" for tool in get_anthropic_tools()
    )
    assert any(
        getattr(tool, "name", "").endswith("execute_python_analysis")
        for tool in create_openai_tools(MagicMock())
    )
