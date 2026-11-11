# flowlit suite (user's own libraries, PyPI)
- flowlit: lightweight event-driven workflow engine; YAML plan of steps/deps, DAG validated, asyncio concurrency, in-memory only (no persistence), executors noop/sleep/shell/http, branching when/when_not/else, output passing `${{ steps.<id>.output.<path> }}`. v0.5.0 (2026-09-25), MIT, py>=3.11.
- flowlit-integration: second layer, reusable executors (no business logic), grows each version; clients can add own executors. Page could not be fetched by WebFetch.
- Original target: MCP server so an AI agent drives workflows from chat. Tested in only one real client so far.
- User wants to evaluate flowlit in this project on a PARALLEL path, not in the main plan (avoid two moving parts).
- Decisions agreed 2026-10-22: Flyway (Docker one-shot) for Postgres migrations, schema_version in build_manifest; no Neo4j migration tool (reload graph from extraction cache); no orchestrator now, thin runner, stages independent. Future vision: load new data -> train -> compare metrics -> decide publish (MLOps loop), manual vs automatic undecided.
