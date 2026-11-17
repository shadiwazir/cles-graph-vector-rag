"""Stage: supervised fine-tuning (QLoRA) of the advisor model on a built dataset.

Run on a GPU machine with `uv sync --group train` (plus Unsloth for the `unsloth` backend, see
docs/06-training-runbook.md). `--dry-run` loads only the tokenizer: it checks the dataset
against the leakage rules, measures token lengths and prints a time and cost estimate.
"""

import contextlib
import json
import logging
import os
import sys
from pathlib import Path

import yaml

from cles.config import Settings, get_settings
from cles.domain.pack import DomainPack, load_pack
from cles.manifest import dvc_hash, git_commit
from cles.stage import StageContext, stage_main
from cles.training.check_dataset import latest_dataset
from cles.training.leakage import check_example, check_split
from cles.training.sft_config import SftConfig, load_sft_config
from cles.training.sft_data import (
    estimate_run,
    keep_within,
    length_stats,
    load_jsonl,
    to_prompt_completion,
    token_length,
)

log = logging.getLogger(__name__)
EXPERIMENT = "cles-sft"


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    cfg = load_sft_config(settings.sft_config)
    pack = load_pack(settings.domain_packs_dir, settings.domain_pack)
    if cfg.backend == "unsloth" and not ctx.dry_run:
        import unsloth  # noqa: F401  (must be imported before transformers and trl)

    folder = settings.dataset_dir or latest_dataset(settings.training_out_dir)
    manifest = json.loads((folder / "manifest.json").read_text())
    train, evaluation = (load_jsonl(folder / f"{n}.jsonl") for n in ("train", "eval"))
    _check_leakage(train + evaluation, manifest, pack)

    from transformers import AutoTokenizer  # after unsloth, see above

    tokenizer = AutoTokenizer.from_pretrained(cfg.base_model)
    train, eval_set, summary = _measure(train, evaluation, tokenizer, cfg)
    summary.update(dataset=str(folder), base_model=cfg.base_model, backend=cfg.backend)
    summary["template_preview"] = _template_preview(train, tokenizer, cfg)
    if ctx.dry_run:
        return summary
    scored = with_target(eval_set)  # only examples that have a target can give a validation loss
    summary["eval_examples_with_target"] = len(scored)
    return summary | _train(cfg, settings, train, scored, manifest, folder, ctx.run_id)


def with_target(examples: list[dict]) -> list[dict]:
    """The examples that carry a target (system, user and assistant message). The evaluation
    examples of a fold are prompts only, so a fold trains without a validation loss."""
    return [e for e in examples if len(e["messages"]) == 3]


def _check_leakage(examples: list[dict], manifest: dict, pack: DomainPack) -> None:
    """Refuse to train on a dataset that breaks a leakage rule."""
    from datetime import date

    split_date = date.fromisoformat(manifest["split_date"])
    problems = check_split(examples)
    for example in examples:
        problems += check_example(example, pack, split_date)
    if problems:
        raise RuntimeError(f"dataset breaks leakage rules ({len(problems)}): {problems[:3]}")


def _template_preview(train: list[dict], tokenizer, cfg: SftConfig) -> dict:
    """How the model's chat template renders one example: check that the end of the prompt and
    the start of the answer look right (for example Qwen3 'thinking' blocks) before paying for
    a run."""
    if not train:
        return {}
    messages = train[0]["messages"]
    kwargs = {"tokenize": False, "enable_thinking": cfg.enable_thinking}
    prompt = tokenizer.apply_chat_template(messages[:2], add_generation_prompt=True, **kwargs)
    full = tokenizer.apply_chat_template(messages, **kwargs)
    return {"prompt_ends_with": prompt[-120:], "answer_starts_with": full[len(prompt) :][:80]}


def _measure(train, evaluation, tokenizer, cfg: SftConfig):
    """Drop examples longer than the limit and report lengths and the run estimate."""
    train = train[: cfg.train_max_examples] if cfg.train_max_examples else train
    train_len = [token_length(e, tokenizer, cfg.enable_thinking) for e in train]
    eval_len = [token_length(e, tokenizer, cfg.enable_thinking) for e in evaluation]
    train, dropped_train = keep_within(train, train_len, cfg.max_seq_length)
    eval_set, dropped_eval = keep_within(evaluation, eval_len, cfg.max_seq_length)
    kept_tokens = sum(n for n in train_len if n <= cfg.max_seq_length)
    est = cfg.estimate
    summary = {
        "train_examples": len(train),
        "eval_examples": len(eval_set),
        "dropped_too_long": dropped_train + dropped_eval,
        "train_lengths": length_stats(train_len),
        **estimate_run(kept_tokens, cfg.epochs, est.tokens_per_second, est.gpu_price_per_hour),
    }
    return train, eval_set, summary


def _load_model(cfg: SftConfig):
    """Base model with LoRA adapters attached, and its tokenizer."""
    lora = cfg.lora
    if cfg.backend == "unsloth":
        from unsloth import FastLanguageModel

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=cfg.base_model,
            max_seq_length=cfg.max_seq_length,
            load_in_4bit=cfg.load_in_4bit,
        )
        model = FastLanguageModel.get_peft_model(
            model,
            r=lora.r,
            lora_alpha=lora.alpha,
            lora_dropout=lora.dropout,
            target_modules=lora.target_modules,
            use_gradient_checkpointing="unsloth",
            random_state=cfg.seed,
        )
        return model, tokenizer

    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(cfg.base_model)
    model = AutoModelForCausalLM.from_pretrained(cfg.base_model)
    model = get_peft_model(
        model,
        LoraConfig(
            r=lora.r,
            lora_alpha=lora.alpha,
            lora_dropout=lora.dropout,
            target_modules=lora.target_modules,
            task_type="CAUSAL_LM",
        ),
    )
    return model, tokenizer


def _trainer_args(cfg: SftConfig, out: Path, has_eval: bool):
    from trl import SFTConfig

    kwargs = dict(
        output_dir=str(out / "checkpoints"),
        per_device_train_batch_size=cfg.per_device_batch_size,
        gradient_accumulation_steps=cfg.grad_accum_steps,
        num_train_epochs=cfg.epochs,
        max_steps=cfg.max_steps,
        learning_rate=cfg.learning_rate,
        lr_scheduler_type=cfg.lr_scheduler,
        weight_decay=cfg.weight_decay,
        logging_steps=cfg.logging_steps,
        eval_strategy="steps" if has_eval else "no",
        eval_steps=cfg.eval_steps,
        save_steps=cfg.save_steps,
        max_length=cfg.max_seq_length,
        bf16=cfg.bf16,
        seed=cfg.seed,
        report_to="mlflow",
        completion_only_loss=True,  # loss on the advice only, not on the prompt
    )
    # Newer versions take the warmup ratio as a float in `warmup_steps`; older ones as warmup_ratio.
    fields = SFTConfig.__dataclass_fields__
    kwargs["warmup_ratio" if "warmup_ratio" in fields else "warmup_steps"] = cfg.warmup_ratio
    if "chat_template_kwargs" in fields:
        kwargs["chat_template_kwargs"] = {"enable_thinking": cfg.enable_thinking}
    return SFTConfig(**kwargs)


def _train(cfg, settings: Settings, train, eval_set, manifest, folder: Path, run_id: str) -> dict:
    import mlflow
    from datasets import Dataset
    from trl import SFTTrainer

    out = settings.training_out_dir.parent / "runs" / run_id[:8]
    out.mkdir(parents=True, exist_ok=True)
    os.environ["MLFLOW_TRACKING_URI"] = settings.mlflow_tracking_uri
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(EXPERIMENT)

    model, tokenizer = _load_model(cfg)
    eval_records = [to_prompt_completion(e) for e in eval_set[: cfg.eval_max_examples]]
    trainer = SFTTrainer(
        model=model,
        args=_trainer_args(cfg, out, bool(eval_records)),
        train_dataset=Dataset.from_list([to_prompt_completion(e) for e in train]),
        eval_dataset=Dataset.from_list(eval_records) if eval_records else None,
        processing_class=tokenizer,
    )

    with mlflow.start_run(run_name=f"{cfg.name}-{run_id[:8]}") as active:
        mlflow.log_params(cfg.params())
        mlflow.set_tags(_lineage(cfg, manifest, folder))
        result = trainer.train()
        adapter = out / "adapter"
        trainer.model.save_pretrained(adapter)
        tokenizer.save_pretrained(adapter)
        (out / "sft_config.yaml").write_text(yaml.safe_dump(cfg.model_dump()))
        mlflow.log_artifacts(str(adapter), "adapter")
        mlflow.log_artifact(str(out / "sft_config.yaml"))
        mlflow.log_artifact(str(folder / "manifest.json"), "dataset")
        version = None
        if settings.mlflow_registered_model:
            client = mlflow.MlflowClient()
            with contextlib.suppress(mlflow.exceptions.MlflowException):  # already exists
                client.create_registered_model(settings.mlflow_registered_model)
            version = client.create_model_version(
                settings.mlflow_registered_model,
                source=f"{active.info.artifact_uri}/adapter",
                run_id=active.info.run_id,
            ).version
    return {
        "mlflow_run_id": active.info.run_id,
        "adapter": str(adapter),
        "train_loss": result.training_loss,
        "registered_version": version,
    }


def _lineage(cfg: SftConfig, manifest: dict, folder: Path) -> dict:
    """What this model was trained from, so the adapter can be traced to code and data."""
    return {
        "git_commit": git_commit(),
        "raw_data_dvc_hash": dvc_hash(Path("data.dvc")) or "",
        "datasets_dvc_hash": dvc_hash(Path("artifacts/datasets.dvc")) or "",
        "dataset_run_id": manifest["run_id"],
        "dataset_fold": (manifest.get("fold") or {}).get("name", ""),
        "dataset_train_sha256": manifest["files"]["train"]["sha256"],
        "dataset_eval_sha256": manifest["files"]["eval"]["sha256"],
        "pack_version": manifest["pack_version"],
        "base_model": cfg.base_model,
    }


if __name__ == "__main__":
    stage_main("train_sft", run, argv=sys.argv[1:])
