"""OpenAI-compatible chat client (works with any endpoint that speaks the same API)."""

from cles.config import ConfigError, Settings
from cles.llm.base import LLMClient, LLMResponse


class OpenAIChatClient:
    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        timeout: float = 600,
        extra_body: dict | None = None,
    ):
        from openai import OpenAI  # imported here so tests and dry runs need no key

        self.model = model
        self._extra_body = extra_body or None
        self._client = OpenAI(
            api_key=api_key, base_url=base_url, timeout=timeout
        )  # SDK retries transient errors

    def complete_json(self, messages: list[dict[str, str]]) -> LLMResponse:
        # json_object mode is the common denominator across compatible providers; the caller
        # validates the result against the JSON Schema itself.
        reply = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            extra_body=self._extra_body,
        )
        usage = reply.usage
        return LLMResponse(
            text=reply.choices[0].message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=self.model,
        )


def make_client(settings: Settings) -> LLMClient:
    if settings.llm_provider != "openai":
        raise ConfigError(f"unsupported LLM_PROVIDER '{settings.llm_provider}'")
    if not settings.llm_model:
        raise ConfigError("LLM_MODEL is not set. Add it to .env.")
    if settings.openai_api_key is None or not settings.openai_api_key.get_secret_value():
        raise ConfigError("OPENAI_API_KEY is not set. Add it to .env.")
    return OpenAIChatClient(
        settings.llm_model,
        settings.openai_api_key.get_secret_value(),
        settings.llm_base_url,
        settings.llm_timeout_seconds,
        settings.llm_extra_body,
    )
