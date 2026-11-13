# 07. Run playbook

How to run the whole pipeline, by hand or from a scheduler. One driver, `scripts/pipeline.sh`, calls the stages through `cles run`, so anything that can run a shell command can run the pipeline [pl.2].

## Flow

```mermaid
flowchart TD
    A[preflight<br/>tools, .env, PDFs, tests, pack] --> B[infra<br/>Postgres + Neo4j, Flyway]
    B --> C[ingest, embed, build_indexes]
    C --> G1{{paid gate: extract}}
    G1 -->|CONFIRM_PAID=1 and estimate within ceiling| D[extract]
    G1 -->|otherwise| X1([stop, exit 3 or 4])
    D --> E[graph_load, record_manifest]
    E --> G2{{paid gate: build_dataset}}
    G2 -->|confirmed| F[build_dataset, check_dataset]
    G2 -->|otherwise| X2([stop, exit 3 or 4])
    F --> H[train-dry<br/>leakage re-check, token stats]
    H --> I[train<br/>rented GPU, see docs/06]
    I --> J[serve with vLLM, evaluate]
```

The steps up to `train-dry` run on the laptop. `train` needs a GPU machine and is not part of `all`.

## Steps

| Step | What it runs | Paid | Notes |
|------|--------------|------|-------|
| `preflight` | tool and `.env` checks, PDF count, `pytest`, `validate_pack` | no | `SKIP_TESTS=1` skips pytest |
| `infra` | `docker compose up -d postgres neo4j`, waits for healthy | no | Flyway migrates the schema first |
| `data` | `ingest embed build_indexes extract graph_load record_manifest` | `extract` | gate before `extract` |
| `dataset` | `build_dataset check_dataset` | `build_dataset` | gate before the build |
| `train-dry` | `train_sft --dry-run` | no | leakage re-check, token statistics, template preview |
| `train` | `train_sft` | no (GPU time) | run on the GPU machine |
| `all` | `preflight infra data dataset train-dry` | yes | |
| `status` | row counts, latest runs, datasets | no | |
| `reset` | drops Postgres and Neo4j volumes | no | `CONFIRM_RESET=1`; also deletes the paid caches |

## Paid gate

`extract` and `build_dataset` first run with `--dry-run` and print an estimate. They continue only if `CONFIRM_PAID=1` and the estimate is at most `MAX_COST_USD` (default 10). Prices come from `LLM_PRICE_INPUT_PER_MTOK` and `LLM_PRICE_OUTPUT_PER_MTOK` (script defaults 0.75 and 4.50, unverified: check the provider page). Real cost is usually different (hidden reasoning tokens raise it; the estimate also ignores the cache). Every call is cached, so a rerun does not pay twice.

## Settings

| Variable | Default | Meaning |
|----------|---------|---------|
| `PIPELINE_DATA_DIR` | `data/criminal_and_civil` | PDF folder; overrides `DATA_DIR` from `.env` (ingest is not recursive) |
| `CONFIRM_PAID` | unset | `1` allows paid LLM calls |
| `MAX_COST_USD` | 10 | ceiling for one paid step's estimate |
| `PIPELINE_LOG_DIR` | `artifacts/pipeline` | logs go to `<dir>/<timestamp>/` |
| `SKIP_TESTS` | unset | `1` skips pytest in `preflight` |

## Exit codes and logs

| Code | Meaning |
|------|---------|
| 0 | ok |
| 1 | a stage failed |
| 2 | bad usage, missing tool, `.env` value or PDFs |
| 3 | paid step not confirmed (or reset not confirmed) |
| 4 | estimate above `MAX_COST_USD` |

Each run writes `artifacts/pipeline/<timestamp>/`: `<stage>.log` (stdout), `<stage>.log.err` (stderr) and `summary.jsonl` (one JSON summary line per stage, from the stage contract). A scheduler only needs the exit code and `summary.jsonl`.

## Hooking it to a scheduler

- **cron or CI job:** `CONFIRM_PAID=1 MAX_COST_USD=5 scripts/pipeline.sh all`; alert on a non-zero exit.
- **Staged approval:** run without `CONFIRM_PAID`; exit 3 means "estimate printed, waiting for a human". Rerun with `CONFIRM_PAID=1` after review.
- **flowlit or another orchestrator:** one task per step (`preflight`, `infra`, `data`, `dataset`, `train-dry`), or call the stages directly: `python -m cles.<module> --run-id ...` (ADR 0005).
- **GPU training:** a separate job on the GPU machine: `scripts/pipeline.sh train` after copying the dataset (docs/06).

## Rerun on new data

1. Put the PDFs in a folder (not nested) and set `PIPELINE_DATA_DIR`.
2. `scripts/pipeline.sh data`. Ingest skips files it has seen (by hash); extraction skips decisions it has extracted with the same schema version and model.
3. `scripts/pipeline.sh dataset` writes a new dataset folder; the split date moves with the data.
4. For a clean start (different corpus, no old documents): `CONFIRM_RESET=1 scripts/pipeline.sh reset`, then `infra` and the rest.

## Duration notes (laptop, 105 decisions)

`embed` on CPU about 10 min; `extract` about 4 min; `dataset` about 30 min (the dry-run estimate alone takes over 2 min). Run long steps in the background (`setsid nohup scripts/pipeline.sh dataset > out.log &`) and follow `artifacts/pipeline/<timestamp>/summary.jsonl`.

## Proof-of-concept run (goal 1)

The PoC uses about 100 decisions [pr.1]. Expected cost is about $15 to 35 in total; measured API cost was about $8.75 (see docs/06). Cost-saving options: fewer stages per decision, the provider batch API, a smaller base model, and stopping the GPU machine right after each step.
