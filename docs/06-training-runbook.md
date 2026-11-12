# 06. Training runbook (fine-tuning on a rented GPU)

Fine-tuning runs on a rented GPU machine, not on the development laptop (GTX 1050, 3 GB). The stage is `train_sft`; the model is served afterwards with vLLM.

## What you need

| Item | Value |
|------|-------|
| GPU | one with at least 24 GB; 48 to 80 GB gives headroom for 8k-token sequences (A100 80GB, L40S 48GB, H100) |
| Dataset | `artifacts/datasets/<id>/` (built by `build_dataset`, checked by `check_dataset`) |
| Config | `configs/sft/qwen3_8b_qlora.yaml` (copy and edit; point `SFT_CONFIG` at it) |
| Base model | `Qwen/Qwen3-8B` by default (check the licence on its model card; Apache 2.0 reported). Llama 3.1 8B is an option under the Llama community licence. |

## Steps

1. **Rent the machine.** Compare live prices first (figures seen in Nov 2026, from third-party sites, verify on the provider pages): A100 80GB about $1.1 to $2.8 per hour, H100 about $1.5 to $4, L40S about $0.7 to $1.1; marketplace hosts (Vast.ai) are cheapest but vary and can be interrupted. Prefer a provider with a persistent volume.
2. **Set up.** `git clone` the repo; `uv sync --group train`; `uv pip install unsloth` (the `unsloth` backend; it must be importable before `transformers`). Torch must match the machine's CUDA driver.
3. **Copy the dataset.** `rsync -av artifacts/datasets/<id> <host>:<repo>/artifacts/datasets/` (a DVC cloud remote is optional for now, see ADR 0016).
4. **Environment.** `.env` needs no API keys. Set `MLFLOW_TRACKING_URI=sqlite:///artifacts/mlflow.db` (a file store on the machine; MLflow 3 deprecates the file backend), and `HF_TOKEN` if the model is gated.
5. **Dry run.** `uv run cles run train_sft --dry-run`: re-checks the leakage rules, drops nothing silently (reports examples longer than `max_seq_length`), prints token statistics.
6. **Pilot (about 100 steps).** Set `max_steps: 100` and run `uv run cles run train_sft`; read tokens per second from the log and put it in `estimate.tokens_per_second` with `gpu_price_per_hour`. The next dry run then prints hours and cost for the full run. Do this before committing to the full run.
7. **Full run.** `uv run cles run train_sft`. Adapter, config and dataset manifest are logged to MLflow with lineage tags (git commit, DVC hashes, dataset hashes, base model) and saved in `artifacts/runs/<id>/adapter/`.
8. **Bring results home.** `rsync` `artifacts/runs/<id>` and `artifacts/mlflow.db` (with `mlartifacts/`) back; `dvc add artifacts/runs/<id>`. Stop the machine.
9. **Serve.** On a GPU host: `BASE_MODEL=Qwen/Qwen3-8B ADAPTER_DIR=./artifacts/runs/<id> docker compose --env-file .env -f infra/docker-compose.yml --profile serve up -d vllm`. The adapter is served as model `cles` at `http://<host>:8000/v1`.
10. **Plug into the API.** `LLM_BASE_URL=http://<host>:8000/v1`, `LLM_MODEL=cles`, `OPENAI_API_KEY=anything`, and list the host in `TRUSTED_GENERATOR_HOSTS` (it is a machine you control, so case text may go there).
11. **Evaluate.** Compare against the baselines (base model with retrieval, the OpenAI model) on the evaluation split, per stage (Phase 6).

## Budget estimate for the real corpus (10,000 decisions)

Scaled linearly from the 15-decision sample, at unverified OpenAI prices and an assumed GPU throughput. All figures are rough; the pilot step replaces the throughput assumption.

| Item | Basis | Estimate |
|------|-------|----------|
| Extraction (`extract`) | about $0.014 per decision | about $140 |
| Training targets (`build_dataset`) | about $0.009 per example, about 3.9 examples per decision (39,000) | about $350 |
| Fine-tuning data volume | 39,000 examples x 5.1k tokens | about 200M tokens per epoch |
| GPU, A100 80GB | assume 3k tokens/s, $1.4 to $2.8 per hour | about 18 h, $26 to $52 per epoch |
| GPU, H100 | assume 6k tokens/s, $2.9 to $4 per hour | about 9 h, $27 to $37 per epoch |
| GPU, L40S 48GB | assume 1.5k tokens/s, $0.8 to $1.1 per hour | about 37 h, $30 to $40 per epoch |

Data building (about $500) costs more than a training epoch (about $30 to $50): spend care on extraction and target quality before spending on GPU hours. The provider batch API (about half price) would roughly halve the two data items.

## Notes

- Loss is computed on the advice only (prompt-completion format); examples longer than `max_seq_length` are dropped, never truncated.
- The adapter is trained on the 4-bit base and served on the 16-bit base; if quality differs, merge the adapter into the 16-bit model or serve the 4-bit model.
- Smoke test of the pipeline on a laptop CPU: `SFT_CONFIG=configs/sft/smoke_cpu.yaml MLFLOW_TRACKING_URI=sqlite:///artifacts/mlflow.db uv run cles run train_sft` (0.5B model, 2 steps; checks data, trainer, tracking and adapter saving, not quality).
