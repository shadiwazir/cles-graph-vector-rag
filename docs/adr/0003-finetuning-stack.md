# 0003. Fine-tuning with Unsloth + TRL on a rented GPU [ml.1]

**Status:** accepted (base model and provider deferred to Phase 5)

**Context.** The developer laptop has a 3 GB GPU, far below QLoRA needs for an 8B model. Data size (about 10k cases, long examples) fits one 48 to 80 GB GPU.

**Options.** Axolotl (YAML-driven, strong multi-GPU via FSDP/DeepSpeed); Unsloth + TRL `SFTTrainer` (plain Python, fastest and lowest VRAM on one GPU); raw FSDP (a sharding technique, not an alternative framework).

**Decision.** Unsloth + TRL, one GPU, adapter-only. Axolotl is the fallback if multi-GPU is needed. Base model is configurable; Llama 3.1 8B is dated and is re-evaluated in Phase 5. GPU provider is chosen from live prices at that time.

**Consequences.** Training script stays short and readable and logs to MLflow. Less suitable for multi-GPU scale-out.
