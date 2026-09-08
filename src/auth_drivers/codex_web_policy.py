"""Two explicit Codex Web purposes; no arbitrary caller-provided CLI override."""

from src.auth_drivers.codex_app_server_runtime import closed_codex_config_overrides


def web_codex_configuration(purpose: str) -> dict:
    if purpose not in {"lifecycle_web_search", "lifecycle_web_analysis"}:
        raise ValueError("codex_purpose_unsupported")
    return {
        **closed_codex_config_overrides(),
        "web_search": "live" if purpose == "lifecycle_web_search" else "disabled",
        "model_providers.openai.request_max_retries": 0,
        "model_providers.openai.stream_max_retries": 0,
        "project_doc_max_bytes": 0,
    }


def validate_web_codex_configuration(config: dict, purpose: str) -> None:
    for path, expected in web_codex_configuration(purpose).items():
        value = config
        for part in path.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if type(value) is not type(expected) or value != expected:
            raise ValueError("codex_web_configuration_mismatch")
