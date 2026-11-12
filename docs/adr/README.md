# Architecture decision records

One file per decision: context, options, decision, consequences. Numbers are never reused; a changed
decision gets a new ADR that supersedes the old one.

| # | Decision |
|---|----------|
| 0001 | Dual retrieval stores: pgvector + Neo4j |
| 0002 | Domain packs keep the domain swappable |
| 0003 | Fine-tuning with Unsloth + TRL on a rented GPU |
| 0004 | Flyway for Postgres migrations; no Neo4j migration tool |
| 0005 | No orchestrator now; thin runner; flowlit on a parallel path |
| 0006 | DVC for data versioning; stores are rebuildable |
| 0007 | OpenTelemetry-only instrumentation; Phoenix as backend |
| 0008 | Stage-cut training examples with leakage rules |
| 0009 | Deterministic citation verification |
| 0010 | Provider interface and external-generator guard |
| 0011 | JSON-mode extraction and a declarative graph mapping |
| 0012 | Disposition and remedy as separate outcome facets |
| 0013 | Retrieval, verification and advisor design |
| 0014 | Training targets: hindsight-conditioned, evidence-capped, context-only citations |
| 0015 | Stage-aware advice: procedural paths first, appeal result downstream |
