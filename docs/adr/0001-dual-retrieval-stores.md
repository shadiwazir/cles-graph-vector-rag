# 0001. Dual retrieval stores: pgvector + Neo4j [ar.1]

**Status:** accepted

**Context.** Legal questions need passage similarity ("cases that read like this") and structure
("cases applying this provision, treated as good law, decided before this date"). One store does
the first well and the second poorly.

**Options.**
1. Postgres + pgvector only: simple, but multi-hop traversal becomes recursive SQL.
2. Neo4j only (with its vector index): one store, but weaker full-text and a heavier role for Neo4j.
3. pgvector for passages and full-text, Neo4j for structure.

**Decision.** Option 3. Vectors stay in Postgres; Neo4j holds entities and relationships only. Results are fused in the retriever (RRF for text + vector; graph results added as context).

**Consequences.** Two stores to run and keep consistent; both are rebuildable from the extraction cache (ADR 0006). One responsibility per store.
