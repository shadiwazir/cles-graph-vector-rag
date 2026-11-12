# CLES: Cognitive Legal Expert System

Advisory copilot for lawyers: hybrid retrieval (pgvector + Neo4j) feeding a fine-tuned SLM.
See `INSTRUCTIONS.md` (build spec), `AGENTS.md` (agent rules) and `docs/`.

## Quick start

```bash
cp .env.example .env              # set POSTGRES_PASSWORD and NEO4J_PASSWORD
uv sync
docker compose --env-file .env -f infra/docker-compose.yml up -d
uv run pytest
uv run cles run validate_pack
```

## Run the API

```bash
uv sync --extra embed
cles run ingest embed build_indexes extract graph_load record_manifest
ALLOW_EXTERNAL_GENERATOR=true uv run uvicorn cles.inference.app:create_app --factory --port 8000
```

`ALLOW_EXTERNAL_GENERATOR=true` is needed when the generator is a third-party service; use public or synthetic cases only. With a local model (for example Ollama at `http://localhost:11434/v1`) it is not needed.
