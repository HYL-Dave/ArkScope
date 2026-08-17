from __future__ import annotations

import ast
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]


def _tree(relative_path: str) -> ast.Module:
    return ast.parse((_ROOT / relative_path).read_text(encoding="utf-8"))


def _function(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    assert len(matches) == 1, f"expected one {name}, found {len(matches)}"
    return matches[0]


def _class(tree: ast.AST, name: str) -> ast.ClassDef:
    matches = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == name
    ]
    assert len(matches) == 1, f"expected one {name}, found {len(matches)}"
    return matches[0]


def _argument_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    return {
        argument.arg
        for argument in (
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        )
    }


def _defaulted_positional_names(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    positional = [*function.args.posonlyargs, *function.args.args]
    count = len(function.args.defaults)
    return {argument.arg for argument in positional[-count:]} if count else set()


def _route_paths(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    paths: set[str] = set()
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call) or not decorator.args:
            continue
        value = decorator.args[0]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            paths.add(value.value)
    return paths


def test_agent_query_signatures_and_replay_schema_have_no_obsolete_attachment_surface():
    for relative_path, function_names in (
        (
            "src/agents/anthropic_agent/agent.py",
            ("run_query", "run_query_stream"),
        ),
        (
            "src/agents/openai_agent/agent.py",
            ("run_query", "run_query_sync", "run_query_stream"),
        ),
    ):
        tree = _tree(relative_path)
        for function_name in function_names:
            function = _function(tree, function_name)
            assert "attachments" not in _argument_names(function), (
                relative_path,
                function_name,
            )

    replay_tree = _tree("src/agents/shared/replay.py")
    replay_trace = _class(replay_tree, "ReplayTrace")
    trace_fields = {
        node.target.id
        for node in replay_trace.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert "attachments_shape" not in trace_fields

    replay_capture = _class(replay_tree, "ReplayCapture")
    methods = {
        node.name: node
        for node in replay_capture.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "attachments_shape" not in _argument_names(methods["set_initial"])
    assert "entrypoint" in _argument_names(methods["__init__"])
    assert "entrypoint" not in _defaulted_positional_names(methods["__init__"])


def test_card_translation_remains_independent_of_conversation_history():
    route = _function(
        _tree("src/api/routes/analysis_cards.py"),
        "translate_card_route",
    )
    assert "/analysis/cards/{run_id}/translate" in _route_paths(route)
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "translate_card"
        for node in ast.walk(route)
    )

    translate = _function(_tree("src/card_synthesis.py"), "translate_card")
    arguments = _argument_names(translate)
    assert {"card", "lang", "model", "model_timeout_s"} <= arguments
    assert arguments.isdisjoint({"history", "messages", "conversation"})


def test_interactive_cli_modules_and_documented_command_are_absent():
    assert not (_ROOT / "src/agents/__main__.py").exists()
    assert not (_ROOT / "src/agents/cli.py").exists()
    assert "python -m src.agents" not in (_ROOT / "README.md").read_text(
        encoding="utf-8"
    )


def test_model_callable_research_and_tool_owners_remain_registered():
    query_tree = _tree("src/api/routes/query.py")
    assert "/query" in _route_paths(_function(query_tree, "query_agent"))
    assert "/query/stream" in _route_paths(
        _function(query_tree, "query_agent_stream")
    )
    assert "/research/runs" in _route_paths(
        _function(_tree("src/api/routes/research.py"), "create_research_run")
    )

    from src.tools.registry import create_default_registry

    names = set(create_default_registry().list_names())
    assert {
        "execute_python_analysis",
        "get_fundamentals_analysis",
        "get_ticker_news",
        "get_ticker_prices",
        "search_news_by_keyword",
    } <= names


def test_obsolete_attachment_pipeline_and_dependency_are_absent():
    for relative_path in (
        "src/agents/shared/attachments.py",
        "tests/test_attachments.py",
        "tests/replay_fixtures/attachment_turn.json",
    ):
        assert not (_ROOT / relative_path).exists(), relative_path

    requirements = (_ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "pymupdf" not in requirements

    replay_source = (_ROOT / "src/agents/shared/replay.py").read_text(
        encoding="utf-8"
    )
    for retired_name in (
        "attachments_shape",
        "classify_attachments",
        "digest_bytes",
        "_size_class",
        "_supported_attachment_pairs",
    ):
        assert retired_name not in replay_source


def test_discord_runtime_config_and_dependency_are_absent():
    assert not (_ROOT / "src/monitor/discord_bot.py").exists()

    requirements = (_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "discord.py" not in requirements.lower()

    env_template = (_ROOT / "config/.env.template").read_text(encoding="utf-8")
    profile = (_ROOT / "config/user_profile.yaml").read_text(encoding="utf-8")
    assert "DISCORD_" not in env_template
    assert 'type: "discord"' not in profile
    assert "DISCORD_" not in profile

    replay_source = (_ROOT / "src/agents/shared/replay.py").read_text(
        encoding="utf-8"
    )
    assert "api | discord | test" not in replay_source
    assert "entrypoint: str  # api | test" in replay_source


def test_monitor_engine_and_scheduler_remain_available():
    engine = _class(_tree("src/monitor/engine.py"), "MonitorEngine")
    assert {
        "notify",
        "run_loop",
        "scan_once",
    } <= {
        node.name
        for node in engine.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    scheduler = _class(_tree("src/monitor/scheduler.py"), "MonitorScheduler")
    assert {
        "_scan_and_notify",
        "_scan_blocking",
        "run_once",
        "start",
        "stop",
    } <= {
        node.name
        for node in scheduler.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    from src.tools.registry import create_default_registry

    assert create_default_registry().get("scan_alerts") is not None


def test_monitor_router_retains_local_channels_without_retired_transport():
    from src.monitor.notifiers import NotificationRouter

    router = NotificationRouter(
        [
            {"type": "console", "enabled": True},
            {"type": "log", "enabled": True},
            {"type": "future_transport", "enabled": True},
        ]
    )
    assert router.active_channels == 2
    assert [type(notifier).__name__ for notifier in router._notifiers] == [
        "ConsoleNotifier",
        "LogNotifier",
    ]

    notifiers_tree = _tree("src/monitor/notifiers.py")
    assert not any(
        isinstance(node, ast.ClassDef) and node.name == "DiscordNotifier"
        for node in ast.walk(notifiers_tree)
    )
    router_class = _class(notifiers_tree, "NotificationRouter")
    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "set_discord_bot"
        for node in router_class.body
    )
    assert "DiscordNotifier" not in (_ROOT / "src/monitor/__init__.py").read_text(
        encoding="utf-8"
    )


def test_model_registry_has_no_terminal_catalog_membership_axis():
    assert not (_ROOT / "src/agents/shared/model_catalog.py").exists()

    model_source = (_ROOT / "src/model_capabilities.py").read_text(
        encoding="utf-8"
    )
    assert "in_cli_catalog" not in model_source

    model_capability = _class(ast.parse(model_source), "ModelCapability")
    fields = {
        node.target.id
        for node in model_capability.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert "in_cli_catalog" not in fields
