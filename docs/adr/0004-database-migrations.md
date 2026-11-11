# 0004. Flyway for Postgres migrations; no Neo4j migration tool [ar.2]

**Status:** accepted

**Context.** `docker-entrypoint-initdb.d` scripts run only on an empty volume, so they cannot evolve a populated database. Re-embedding 10k cases to change a column is not acceptable, and `request_audit` and `build_manifest` cannot be regenerated.

**Options.** Flyway (Java, CLI or Docker); pyway (Python, Flyway-like, last release found April 2024, unverified); Alembic (needs SQLAlchemy, unused here); dbmate.

**Decision.** Flyway Community as a one-shot Compose service. `V1__baseline.sql` holds the schema; the init script only creates the `mlflow` database. `build_manifest.schema_version` records the applied version. MLflow upgrades its own database.

Neo4j: constraints from the pack with `IF NOT EXISTS`; non-additive pack changes reload the graph from the `extractions` table (idempotent, no LLM cost).

**Consequences.** No Python dependency for migrations. HNSW index builds after bulk loads are an operational step. Revisit a Neo4j tool if the graph ever holds data that cannot be rebuilt.
