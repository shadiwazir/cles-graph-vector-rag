"""Training configuration (YAML) for supervised fine-tuning."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class LoraSettings(BaseModel):
    r: int = 64
    alpha: int = 128
    dropout: float = 0.0
    target_modules: list[str] = Field(
        default_factory=lambda: [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ]
    )


class EstimateSettings(BaseModel):
    tokens_per_second: float | None = None
    gpu_price_per_hour: float | None = None


class SftConfig(BaseModel):
    name: str
    backend: Literal["unsloth", "plain"] = "unsloth"
    base_model: str
    load_in_4bit: bool = True
    max_seq_length: int = 8192
    enable_thinking: bool = False
    lora: LoraSettings = Field(default_factory=LoraSettings)
    epochs: float = 2
    max_steps: int = -1  # a positive value overrides epochs (smoke tests)
    learning_rate: float = 2e-4
    lr_scheduler: str = "cosine"
    warmup_ratio: float = 0.03
    weight_decay: float = 0.0
    per_device_batch_size: int = 2
    grad_accum_steps: int = 8
    logging_steps: int = 10
    eval_steps: int = 250
    save_steps: int = 250
    eval_max_examples: int = 200
    train_max_examples: int | None = None
    seed: int = 3407
    bf16: bool = True
    estimate: EstimateSettings = Field(default_factory=EstimateSettings)

    def params(self) -> dict:
        """Flat view for experiment tracking."""
        flat = self.model_dump(exclude={"lora", "estimate"})
        flat.update({f"lora_{k}": v for k, v in self.lora.model_dump().items()})
        return flat


def load_sft_config(path: Path) -> SftConfig:
    return SftConfig(**yaml.safe_load(path.read_text()))
