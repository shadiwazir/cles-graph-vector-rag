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
