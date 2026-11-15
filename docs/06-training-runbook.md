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

## RunPod session for the PoC [ml.6]

Pod: one L40S 48 GB on demand (about $1.09 per hour), template PyTorch 2.8.0 / CUDA 12.8.1, volume 60 GB on `/workspace`, SSH over direct TCP (the proxy SSH cannot copy files). Prices seen on 2026-11-13.

1. Laptop: `scripts/gpu_setup.sh push root@<ip> <port>` copies the repo and the newest dataset to `/workspace/cles` (no `.env`, no `.git`).
2. Pod: `cd /workspace/cles && scripts/gpu_setup.sh setup` creates `/workspace/venv`, installs the project, the train group and Unsloth, writes a minimal `.env` and runs the dry run. It uses `configs/sft/qwen3_8b_poc.yaml` (sequence length 12288, batch 1 x 16, eval every 10 steps).
3. Pilot: a 3-step run (the full run is only about 45 steps on 359 examples, so the 100-step pilot of step 6 does not apply). Start with `scripts/gpu_setup.sh run pilot configs/sft/pilot.yaml` and wait with `scripts/gpu_setup.sh wait pilot` (it blocks on `/workspace/runs/pilot.exit`; do not wait with `pgrep -f` over ssh, it matches itself). Measured 2026-11-13: 44 to 52 s per step of 16 sequences, about 2.5k tokens per second, no out-of-memory at 12288 tokens.
4. Full run: `scripts/gpu_setup.sh run full configs/sft/qwen3_8b_poc.yaml`, about 45 steps, about 35 minutes (about $0.65).
   Result of the PoC full run (2026-11-13): 46 steps in about 36 minutes, train loss 1.33 to 0.82, eval loss 1.07 to 0.96 (eval flattens while train keeps falling: mild overfitting, expected with 359 examples), about 10.7 GB GPU memory (a 24 GB card would also work at this length). Adapter: `artifacts/runs/<id>/adapter` (678 MB). Details in the MLflow run.
5. Every ssh command must source `/workspace/env.sh` (non-interactive ssh does not read `.bashrc`); otherwise the model downloads to the container disk, which is erased on stop. `gpu_setup.sh run` does this.
6. Stop the pod after each step; delete the volume when the PoC is finished (it bills about $4.20 per month even when the pod is stopped).

## Serving the adapter for the console (vLLM behind an SSH tunnel) [ml.8]

Needs a GPU pod in the same region as the volume (the adapter is on the volume). A 24 GB card is enough for one user at 12k tokens; 48 GB gives headroom. The 16-bit base (about 16 GB) is downloaded once to the volume; vLLM lives in its own venv (`/workspace/venv-vllm`) because it pins its own torch. Not yet exercised on a GPU: expect first-run snags.

1. Pod: `scripts/gpu_setup.sh push root@<ip> <port>` if the code changed, then `scripts/gpu_setup.sh serve` and `scripts/gpu_setup.sh serve-wait` (blocks until the model `cles` answers; vLLM listens on the pod's localhost only).
2. Laptop, tunnel: `ssh -N -L 8001:localhost:8000 -p <port> -i ~/.ssh/id_ed25519 root@<ip>`.
3. Laptop, console: `LLM_BASE_URL=http://localhost:8001/v1 LLM_MODEL=cles OPENAI_API_KEY=local ADAPTER_VERSION="cles-advisor v1 (candidate)" LLM_EXTRA_BODY='{"chat_template_kwargs":{"enable_thinking":false}}' scripts/pipeline.sh console` (command-line values win over `.env`; `localhost` passes the confidentiality guard, so no `ALLOW_EXTERNAL_GENERATOR`).
4. The adapter was trained on the 4-bit base and the evaluation used the 4-bit load; vLLM serves the 16-bit base. Compare a few answers with the evaluation outputs before trusting the console.
5. Stop the pod when done; the volume keeps the model cache and the venv.

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

## Budget estimate for a proof of concept (about 100 decisions) [pr.1]

Goal 1 (PoC and learning) needs no more than this. Same method as above: linear scaling from the 15-decision sample, unverified prices, assumed throughput.

| Item | Basis | Estimate |
|------|-------|----------|
| Extraction | 100 x about $0.014, doubled for prompt tweaks | $1.5 to 3 |
| Training targets | about 390 examples x $0.009 | about $3.5 |
| Baseline answers (evaluation) | about 40 eval examples, one call each | under $1 |
| GPU | about 2M tokens per epoch (6M for 3), 1 to 2 h training, plus pilot, setup, 1 to 2 h serving | $5 to 20 |
| **Total** | | **about $15 to 30** (API about $5 to 8) |

- A 24 GB card (about $0.3 to 0.5 per hour, unverified) with a smaller base such as Qwen3-4B is the cheaper PoC option. The laptop GPU (3 GB) cannot train an 8B model.
- What it shows: the pipeline works end to end; the model learns the JSON format, stage handling, citing only supplied context and hedging on weak evidence. What it does not show: domain accuracy (about 40 eval examples gives roughly +-15 points on outcome accuracy) or rich retrieval (random decisions rarely cite each other, so the graph is thin). Treat results as a demonstration.
- Prefer a topical cluster spread over several years to a random sample: shared statutes, issues and citations give the graph and the time filter something to do.
- Further savings: two stages per decision instead of four; the provider batch API (about half price); stop the machine right after each step.
- Staging: 100 files first; about 1,000 files (about $150) only if the PoC looks promising; then the full corpus.
- Cheaper middle option: skip the fine-tune and compare base model plus retrieval with the OpenAI baseline.

### Measured on the PoC run (2026-11-12, 105 decisions)

| Item | Estimate above | Measured |
|------|----------------|----------|
| Extraction (92 new decisions) | $1.5 to 3 | $1.24 (about $0.0135 per decision) |
| Training targets | about $3.5 | $7.50 (estimate by the stage: $7.04) for 407 examples, about $0.018 each |
| API total | $5 to 8 | about $8.75 |

- Targets cost twice the per-example figure from the 15-decision sample: with more decisions to retrieve from, prompts grew from a mean of 5.1k to 7.4k tokens. Evidence is "strong" for 287 of 359 training examples (it was mostly "moderate" in the sample).
- 416 examples planned, 407 built (9 targets missing: the generator output failed the checks), 359 train and 48 eval, split date 2026-10-07, 0 leakage violations.
- Token statistics (Qwen3-8B tokenizer): max 8849, p90 8238. With `max_seq_length: 8192`, 48 of 359 training examples would be dropped. Before the GPU run, either raise `max_seq_length` (12288 needs more GPU memory) or retrieve fewer passages per example. Decide after a pilot.
- GPU budget: 4.6M tokens per epoch counted by the trainer, so the GPU figures above still hold (about 6M tokens per epoch if nothing is dropped).

## Notes

- Loss is computed on the advice only (prompt-completion format); examples longer than `max_seq_length` are dropped, never truncated.
- The adapter is trained on the 4-bit base and served on the 16-bit base; if quality differs, merge the adapter into the 16-bit model or serve the 4-bit model.
- Smoke test of the pipeline on a laptop CPU: `SFT_CONFIG=configs/sft/smoke_cpu.yaml MLFLOW_TRACKING_URI=sqlite:///artifacts/mlflow.db uv run cles run train_sft` (0.5B model, 2 steps; checks data, trainer, tracking and adapter saving, not quality).
