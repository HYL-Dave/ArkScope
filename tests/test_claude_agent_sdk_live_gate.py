from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest


def test_live_gate_has_two_distinct_sessions_and_never_retries():
    from tests.live import sdk_driver_smoke as gate

    calls: list[str] = []

    async def run_once(spec):
        calls.append(spec.name)
        return {"name": spec.name, "passed": True}

    budget = gate.GateBudget(limit=2)
    results = asyncio.run(gate.run_admission_sessions(run_once, budget=budget))

    assert calls == ["allowed_mcp", "locked_surface"]
    assert [row["name"] for row in results] == calls
    assert budget.claimed == 2

    calls.clear()

    async def fail_first(spec):
        calls.append(spec.name)
        raise gate.LiveGateError("bounded failure")

    failure_budget = gate.GateBudget(limit=2)
    with pytest.raises(gate.LiveGateError, match="bounded failure"):
        asyncio.run(
            gate.run_admission_sessions(fail_first, budget=failure_budget)
        )
    assert calls == ["allowed_mcp"]
    assert failure_budget.claimed == 1


def test_gate_budget_rejects_a_third_session():
    from tests.live import sdk_driver_smoke as gate

    budget = gate.GateBudget(limit=2)
    budget.claim()
    budget.claim()
    with pytest.raises(gate.LiveGateError, match="session budget"):
        budget.claim()


def test_init_projection_requires_exact_auth_tool_and_server_inventory():
    from tests.live import sdk_driver_smoke as gate

    projected = gate.summarize_init(
        {
            "apiKeySource": "none",
            "tools": ["mcp__ark__admission_probe"],
            "mcp_servers": [{"name": "ark", "status": "connected"}],
            "session_id": "must-not-leave",
            "cwd": "/private/path",
        },
        expected_tools=("mcp__ark__admission_probe",),
        expected_servers=("ark",),
    )

    assert projected == {
        "api_key_source": "none",
        "tools": ["mcp__ark__admission_probe"],
        "mcp_servers": [{"name": "ark", "status": "connected"}],
    }

    with pytest.raises(gate.LiveGateError, match="tool inventory"):
        gate.summarize_init(
            {"apiKeySource": "none", "tools": ["Bash"], "mcp_servers": []},
            expected_tools=(),
            expected_servers=(),
        )

    with pytest.raises(gate.LiveGateError, match="server inventory"):
        gate.summarize_init(
            {
                "apiKeySource": "none",
                "tools": [],
                "mcp_servers": [{"name": "ambient", "status": "connected"}],
            },
            expected_tools=(),
            expected_servers=(),
        )


def test_live_credential_selection_is_read_only_and_prefers_active(tmp_path):
    from tests.live import sdk_driver_smoke as gate

    path = tmp_path / "profile.db"
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE llm_credentials ("
            "id INTEGER PRIMARY KEY, provider TEXT, auth_type TEXT, active INTEGER)"
        )
        conn.executemany(
            "INSERT INTO llm_credentials VALUES (?, ?, ?, ?)",
            (
                (1, "anthropic", "claude_code_oauth", 0),
                (2, "anthropic", "setup_token", 1),
                (3, "openai", "chatgpt_oauth", 1),
            ),
        )

    before = path.read_bytes()
    assert gate.read_oauth_credential_id(path) == "local:2"
    assert path.read_bytes() == before


def test_live_gate_uses_the_same_closed_child_environment_as_product_paths():
    from tests.live import sdk_driver_smoke as gate

    child = gate.build_claude_child_environment(
        token="setup-token",
        config_dir="/tmp/isolated-claude",
        source={
            "HOME": "/tmp/home",
            "PATH": "/usr/bin",
            "LANG": "C.UTF-8",
            "OPENAI_API_KEY": "secret",
            "ANTHROPIC_API_KEY": "secret",
            "AWS_SECRET_ACCESS_KEY": "secret",
        },
    )

    assert child["HOME"] == "/tmp/home"
    assert child["PATH"] == "/usr/bin"
    assert child["LANG"] == "C.UTF-8"
    assert child["OPENAI_API_KEY"] == ""
    assert child["ANTHROPIC_API_KEY"] == ""
    assert child["AWS_SECRET_ACCESS_KEY"] == ""
    assert child["CLAUDE_CODE_OAUTH_TOKEN"] == "setup-token"


def test_live_gate_places_project_configuration_traps_in_the_child_cwd(tmp_path):
    from tests.live import sdk_driver_smoke as gate

    paths = gate._write_adversarial_traps(tmp_path)

    child_cwd = Path(paths["cwd"])
    assert (child_cwd / "CLAUDE.md").is_file()
    assert (child_cwd / ".mcp.json").is_file()
    assert (Path(paths["config"]) / "settings.json").is_file()


def test_live_session_binds_adversarial_sources_to_actual_sdk_paths(monkeypatch):
    from claude_agent_sdk import AssistantMessage, ResultMessage, SystemMessage, TextBlock
    from tests.live import sdk_driver_smoke as gate

    observed: dict[str, bool] = {}

    async def fake_query(*, prompt, options):
        cwd = Path(options.cwd)
        config = Path(options.env["CLAUDE_CONFIG_DIR"])
        assert options.model == gate.LIVE_MODEL
        assert options.fallback_model is None
        observed.update(
            {
                "project_memory": (cwd / "CLAUDE.md").is_file(),
                "project_mcp": (cwd / ".mcp.json").is_file(),
                "user_settings": (config / "settings.json").is_file(),
            }
        )
        yield SystemMessage(
            subtype="init",
            data={"apiKeySource": "none", "tools": [], "mcp_servers": []},
        )
        yield AssistantMessage(content=[TextBlock("done")], model=gate.LIVE_MODEL)
        yield ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="test-session",
            usage={"input_tokens": 1, "output_tokens": 1},
        )

    monkeypatch.setattr(gate, "query", fake_query)
    spec = next(row for row in gate.SESSION_SPECS if row.name == "locked_surface")

    result = asyncio.run(
        gate._run_live_session(spec, token="setup-token", cli_path=Path("/bin/true"))
    )

    assert observed == {
        "project_memory": True,
        "project_mcp": True,
        "user_settings": True,
    }
    assert result["passed"] is True
    assert result["observed_model"] == gate.LIVE_MODEL


@pytest.mark.parametrize("session_name", ("allowed_mcp", "locked_surface"))
@pytest.mark.parametrize("assistant_model", ("claude-unrequested-model", None))
def test_each_live_session_rejects_unrequested_or_unobserved_assistant_model(
    monkeypatch, session_name, assistant_model
):
    from claude_agent_sdk import AssistantMessage, ResultMessage, SystemMessage, TextBlock
    from tests.live import sdk_driver_smoke as gate

    async def fake_query(*, prompt, options):
        yield SystemMessage(
            subtype="init",
            data={
                "apiKeySource": "none",
                "tools": list(spec.expected_tools),
                "mcp_servers": [
                    {"name": name, "status": "connected"}
                    for name in spec.expected_servers
                ],
            },
        )
        if assistant_model is not None:
            yield AssistantMessage(
                content=[TextBlock("done")],
                model=assistant_model,
            )
        yield ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="test-session",
            usage={"input_tokens": 1, "output_tokens": 1},
        )

    monkeypatch.setattr(gate, "query", fake_query)
    spec = next(row for row in gate.SESSION_SPECS if row.name == session_name)

    with pytest.raises(gate.LiveGateError, match="model"):
        asyncio.run(
            gate._run_live_session(
                spec,
                token="setup-token",
                cli_path=Path("/bin/true"),
            )
        )


def test_evidence_contract_rejects_raw_prose_or_secret_fields():
    from tests.live import sdk_driver_smoke as gate

    evidence = gate.build_evidence(
        sessions_started=2,
        runtime={
            "sdk_version": "0.2.152",
            "cli_version": "2.1.259",
            "cli_sha256": "a" * 64,
        },
        sessions=(
            {
                "name": "allowed_mcp",
                "passed": True,
                "observed_model": gate.LIVE_MODEL,
                "api_key_source": "none",
                "tools": ["mcp__ark__admission_probe"],
                "mcp_servers": [{"name": "ark", "status": "connected"}],
                "tool_calls": ["mcp__ark__admission_probe"],
                "probe_call_count": 1,
                "num_turns": 2,
                "input_tokens": 10,
                "output_tokens": 2,
                "trap_mcp_started": False,
                "trap_write_observed": False,
                "ambient_instruction_observed": False,
            },
            {
                "name": "locked_surface",
                "passed": True,
                "observed_model": gate.LIVE_MODEL,
                "api_key_source": "none",
                "tools": [],
                "mcp_servers": [],
                "tool_calls": [],
                "probe_call_count": 0,
                "num_turns": 1,
                "input_tokens": 8,
                "output_tokens": 3,
                "trap_mcp_started": False,
                "trap_write_observed": False,
                "ambient_instruction_observed": False,
            },
        ),
    )

    gate.validate_evidence(evidence)
    assert evidence["session_count"] == 2
    assert evidence["sessions_started"] == 2
    assert evidence["application_retries"] == 0
    assert evidence["fallback_model"] is None
    assert [row["observed_model"] for row in evidence["sessions"]] == [
        gate.LIVE_MODEL,
        gate.LIVE_MODEL,
    ]
    assert "prompt" not in repr(evidence).lower()
    assert "answer" not in repr(evidence).lower()

    bad = {**evidence, "raw_prompt": "do not persist me"}
    with pytest.raises(gate.LiveGateError, match="evidence fields"):
        gate.validate_evidence(bad)

    bad_session = {
        **evidence,
        "sessions": [
            {**evidence["sessions"][0], "tool_calls": ["Bash"]},
            evidence["sessions"][1],
        ],
    }
    with pytest.raises(gate.LiveGateError, match="session contract"):
        gate.validate_evidence(bad_session)

    bad_auth = {
        **evidence,
        "sessions": [
            {**evidence["sessions"][0], "api_key_source": "unknown"},
            evidence["sessions"][1],
        ],
    }
    with pytest.raises(gate.LiveGateError, match="session contract"):
        gate.validate_evidence(bad_auth)

    for session_index in range(2):
        bad_model_sessions = [dict(row) for row in evidence["sessions"]]
        bad_model_sessions[session_index]["observed_model"] = "claude-unrequested-model"
        with pytest.raises(gate.LiveGateError, match="session contract"):
            gate.validate_evidence(
                {**evidence, "sessions": bad_model_sessions}
            )

    missing_model_sessions = [dict(row) for row in evidence["sessions"]]
    del missing_model_sessions[0]["observed_model"]
    with pytest.raises(gate.LiveGateError, match="session evidence fields"):
        gate.validate_evidence({**evidence, "sessions": missing_model_sessions})
