"""Confidentiality guard: lawyer-supplied case text must not reach a third party by accident."""

from urllib.parse import urlparse

from cles.config import ConfigError, Settings

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


def is_external(base_url: str) -> bool:
    return (urlparse(base_url).hostname or "") not in _LOCAL_HOSTS


def check_generator_allowed(settings: Settings) -> None:
    """Refuse to send case text to an external model unless explicitly allowed
    (ALLOW_EXTERNAL_GENERATOR=true, only for public or synthetic cases)."""
    if is_external(settings.llm_base_url) and not settings.allow_external_generator:
        raise ConfigError(
            f"LLM_BASE_URL {settings.llm_base_url} is an external service. Case text would be "
            "sent to a third party. Set ALLOW_EXTERNAL_GENERATOR=true only for public or "
            "synthetic cases."
        )
