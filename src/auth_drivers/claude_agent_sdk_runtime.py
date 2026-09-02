"""Fail-closed admission for ArkScope's bundled Claude Agent SDK runtime."""

from __future__ import annotations

import os
import platform
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from importlib import metadata
from pathlib import Path
from typing import Mapping


REVIEWED_CLAUDE_AGENT_SDK_VERSION = "0.2.151"
REVIEWED_CLAUDE_CLI_VERSION = "2.1.258"

# Sources that can outrank or reroute setup-token authentication in the child.
CLAUDE_INHERITED_AUTH_ENV = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_FOUNDRY_API_KEY",
    "ANTHROPIC_AWS_API_KEY",
    "ANTHROPIC_BEDROCK_MANTLE_API_KEY",
    "AWS_BEARER_TOKEN_BEDROCK",
    "ANTHROPIC_AWS_AUTH",
    "ANTHROPIC_IDENTITY_TOKEN",
    "ANTHROPIC_IDENTITY_TOKEN_FILE",
    "ANTHROPIC_PROFILE",
    "ANTHROPIC_CUSTOM_HEADERS",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_BEDROCK_BASE_URL",
    "ANTHROPIC_VERTEX_BASE_URL",
    "ANTHROPIC_FOUNDRY_BASE_URL",
    "ANTHROPIC_AWS_BASE_URL",
    "ANTHROPIC_BEDROCK_MANTLE_BASE_URL",
    "ANTHROPIC_UNIX_SOCKET",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
    "CLAUDE_CODE_USE_ANTHROPIC_AWS",
    "CLAUDE_CODE_USE_MANTLE",
    "CLAUDE_CODE_USE_GATEWAY",
)

# This duplicates the primary ``tools=[]`` lock at the CLI policy layer.
REVIEWED_DISALLOWED_TOOLS = (
    "Bash",
    "Edit",
    "Write",
    "Read",
    "WebFetch",
    "WebSearch",
    "Glob",
    "Grep",
    "Task",
    "Skill",
)

# Values required to launch the bundled CLI and establish normal TLS. Every
# other variable present in the parent is explicitly blanked in options.env so
# the SDK's os.environ merge cannot forward unrelated application secrets.
CLAUDE_CHILD_ENV_ALLOWLIST = frozenset(
    {
        "HOME",
        "PATH",
        "PATHEXT",
        "SystemRoot",
        "WINDIR",
        "LANG",
        "LANGUAGE",
        "TZ",
        "TEMP",
        "TMP",
        "TMPDIR",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "NODE_EXTRA_CA_CERTS",
    }
)
_SDK_ENV_VALUES = {
    "CLAUDE_CODE_ENTRYPOINT": "sdk-py",
    # Keep active host tracing/baggage out of the provider child. The SDK only
    # injects these when the corresponding key is absent from options.env.
    "TRACEPARENT": "",
    "TRACESTATE": "",
    "BAGGAGE": "",
}

_CLI_VERSION = re.compile(r"(?P<version>\d+\.\d+\.\d+)(?:\s+\(Claude Code\))?\Z")


class ClaudeAgentSdkRuntimeIncompatible(RuntimeError):
    """The installed SDK/CLI pair is not the reviewed execution runtime."""


class ClaudeSubscriptionAuthSourceUnverified(RuntimeError):
    """The CLI did not prove that this turn used subscription authentication."""


@dataclass(frozen=True)
class ReviewedClaudeAgentRuntime:
    sdk_version: str
    sdk_module_version: str
    cli_metadata_version: str
    cli_binary_version: str
    cli_path: Path


def discard_claude_sdk_stderr(_line: str) -> None:
    """Drain CLI stderr without exposing provider or environment diagnostics."""


def build_claude_child_environment(
    *,
    token: str,
    config_dir: str,
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Overlay the SDK's inherited environment with a closed, non-secret view."""
    parent = os.environ if source is None else source
    child = {
        name: (
            value
            if name in CLAUDE_CHILD_ENV_ALLOWLIST or name.startswith("LC_")
            else ""
        )
        for name, value in parent.items()
    }
    for name in CLAUDE_INHERITED_AUTH_ENV:
        child[name] = ""
    child.update(_SDK_ENV_VALUES)
    child["CLAUDE_CODE_OAUTH_TOKEN"] = token
    child["CLAUDE_CONFIG_DIR"] = config_dir
    return child


def _distribution_version() -> str:
    return metadata.version("claude-agent-sdk")


def _sdk_module_version() -> str:
    from claude_agent_sdk._version import __version__

    return __version__


def _cli_metadata_version() -> str:
    from claude_agent_sdk._cli_version import __cli_version__

    return __cli_version__


def _bundled_cli_path() -> Path:
    import claude_agent_sdk

    package_dir = Path(claude_agent_sdk.__file__).resolve().parent
    executable = "claude.exe" if platform.system() == "Windows" else "claude"
    return package_dir / "_bundled" / executable


def _version_probe_env() -> dict[str, str]:
    # The version probe needs no credential or provider configuration.
    inherited = (
        "PATH",
        "PATHEXT",
        "SystemRoot",
        "WINDIR",
        "TEMP",
        "TMP",
    )
    return {name: os.environ[name] for name in inherited if name in os.environ}


def _probe_cli_version(cli_path: Path) -> str:
    try:
        completed = subprocess.run(
            [str(cli_path), "--version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3.0,
            check=False,
            cwd=str(cli_path.parent),
            env=_version_probe_env(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ClaudeAgentSdkRuntimeIncompatible(
            "The bundled Claude Code CLI could not be verified."
        ) from exc
    if completed.returncode != 0:
        raise ClaudeAgentSdkRuntimeIncompatible(
            "The bundled Claude Code CLI version probe failed."
        )
    match = _CLI_VERSION.fullmatch(completed.stdout.strip())
    if match is None:
        raise ClaudeAgentSdkRuntimeIncompatible(
            "The bundled Claude Code CLI returned an unrecognized version."
        )
    return match.group("version")


def require_subscription_auth_source(data: object) -> None:
    """Accept only the reviewed literal emitted by the bundled CLI init frame."""
    if (
        not isinstance(data, dict)
        or "apiKeySource" not in data
        or data.get("apiKeySource") is None
    ):
        raise ClaudeSubscriptionAuthSourceUnverified(
            "Claude subscription auth source evidence is missing or malformed; "
            "refusing to continue the model call."
        )
    if data.get("apiKeySource") != "none":
        raise ClaudeSubscriptionAuthSourceUnverified(
            "Claude subscription auth is not active; refusing to bill or use "
            "another credential source."
        )


@lru_cache(maxsize=1)
def require_reviewed_claude_agent_runtime() -> ReviewedClaudeAgentRuntime:
    """Return the exact reviewed SDK/CLI pair or fail before provider access."""
    cli_path = _bundled_cli_path()
    if not cli_path.is_file():
        raise ClaudeAgentSdkRuntimeIncompatible(
            "The reviewed bundled Claude Code CLI is not installed."
        )
    cli_path = cli_path.resolve()
    if cli_path.parent.name != "_bundled":
        raise ClaudeAgentSdkRuntimeIncompatible(
            "The bundled Claude Code CLI resolved outside the SDK bundle."
        )

    runtime = ReviewedClaudeAgentRuntime(
        sdk_version=_distribution_version(),
        sdk_module_version=_sdk_module_version(),
        cli_metadata_version=_cli_metadata_version(),
        cli_binary_version=_probe_cli_version(cli_path),
        cli_path=cli_path,
    )
    observed = (
        runtime.sdk_version,
        runtime.sdk_module_version,
        runtime.cli_metadata_version,
        runtime.cli_binary_version,
    )
    expected = (
        REVIEWED_CLAUDE_AGENT_SDK_VERSION,
        REVIEWED_CLAUDE_AGENT_SDK_VERSION,
        REVIEWED_CLAUDE_CLI_VERSION,
        REVIEWED_CLAUDE_CLI_VERSION,
    )
    if observed != expected:
        raise ClaudeAgentSdkRuntimeIncompatible(
            "The installed Claude Agent SDK runtime is not reviewed for ArkScope "
            f"(expected SDK {REVIEWED_CLAUDE_AGENT_SDK_VERSION} and CLI "
            f"{REVIEWED_CLAUDE_CLI_VERSION})."
        )
    return runtime
