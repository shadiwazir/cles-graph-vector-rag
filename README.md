# CLES: Cognitive Legal Expert System

Advisory copilot for lawyers: hybrid retrieval (pgvector + Neo4j) feeding a fine-tuned SLM.
See `INSTRUCTIONS.md` (build spec), `AGENTS.md` (agent rules) and `docs/`.

Two goals: (1) a proof of concept to learn from, on about 100 decisions (current); (2) a production-grade product on the full corpus (later). Docs: `docs/04` (plan), `docs/06` (training and costs), `docs/07` (run playbook).

## Quick start

```bash
cp .env.example .env              # set POSTGRES_PASSWORD, NEO4J_PASSWORD, OPENAI_API_KEY, LLM_MODEL
uv sync
docker compose --env-file .env -f infra/docker-compose.yml up -d
uv run pytest
uv run cles run validate_pack
```

## Run the whole pipeline (proof of concept)

`scripts/pipeline.sh <step>` runs every step; it only calls `cles run <stage>`, so a scheduler can call it too. Full details, exit codes and scheduler hooks: `docs/07-run-playbook.md`.

1. Put the PDFs in `data/criminal_and_civil/` (flat folder; or set `PIPELINE_DATA_DIR`).
2. `scripts/pipeline.sh preflight`: checks tools, `.env`, PDFs, runs the tests and validates the domain pack.
3. `scripts/pipeline.sh infra`: starts Postgres and Neo4j (Flyway migrates the schema) and waits until healthy.
4. `scripts/pipeline.sh data`: `ingest embed build_indexes`, then the **paid** gate, then `extract graph_load record_manifest`.
5. `scripts/pipeline.sh dataset`: the **paid** gate, then `build_dataset check_dataset`.
6. `scripts/pipeline.sh train-dry`: leakage re-check, token statistics and template preview (no GPU).
7. `scripts/pipeline.sh train` on a rented GPU machine (see `docs/06-training-runbook.md`).
8. `scripts/pipeline.sh status`: row counts and the latest runs.

Or all of steps 2 to 6 at once: `CONFIRM_PAID=1 scripts/pipeline.sh all`.

Paid steps (`extract`, `build_dataset`) print an estimate first and stop (exit 3) unless `CONFIRM_PAID=1`; they also stop (exit 4) if the estimate exceeds `MAX_COST_USD` (default 10). Logs and per-stage JSON summaries go to `artifacts/pipeline/<timestamp>/`. Start from an empty database with `CONFIRM_RESET=1 scripts/pipeline.sh reset`.

Single stages: `uv run cles run <stage> [--limit N] [--dry-run]` (`ingest embed build_indexes extract graph_load record_manifest evaluate build_dataset check_dataset train_sft`).

## Run the API

```bash
uv sync --extra embed
cles run ingest embed build_indexes extract graph_load record_manifest
ALLOW_EXTERNAL_GENERATOR=true uv run uvicorn cles.inference.app:create_app --factory --port 8000
```

`ALLOW_EXTERNAL_GENERATOR=true` is needed when the generator is a third-party service; use public or synthetic cases only. With a local model (for example Ollama at `http://localhost:11434/v1`) it is not needed.

## Optional profiles

- Observability (Phoenix, Prometheus, Grafana): `docker compose --env-file .env -f infra/docker-compose.yml --profile observability up -d`.
- Training tracking (MLflow) and serving (vLLM): profiles `training` and `serve`; see `docs/06-training-runbook.md`.
