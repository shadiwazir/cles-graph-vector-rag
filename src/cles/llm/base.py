"""Provider-neutral LLM interface. Provider, model and endpoint come from Settings."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMClient(Protocol):
    model: str

    def complete_json(self, messages: list[dict[str, str]]) -> LLMResponse:
        """Return the model's reply, asked to be a single JSON object."""
        ...


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    price_in_per_mtok: float | None,
    price_out_per_mtok: float | None,
) -> float | None:
    """Cost in USD, or None when prices are not configured."""
    if price_in_per_mtok is None or price_out_per_mtok is None:
        return None
    return (input_tokens * price_in_per_mtok + output_tokens * price_out_per_mtok) / 1_000_000
