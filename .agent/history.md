# History

## 2026-10-21 Phase 1 analysis
- Done: read Agent.md, INSTRUCTIONS_suggested.md, architecture image; profiled data/ (15 ONCA PDFs) and local env (GPU 3GB, Docker present).
- Files affected: .agent/memory/project-state.md, .agent/history.md (created).
- Decisions: no INSTRUCTIONS.md yet; findings presented to user for discussion.
- Next: user feedback on findings/questions, then iterate; write INSTRUCTIONS.md only after approval.

## 2026-10-22 Phase 1 discussion, round 2
- Done: user answered findings. Decisions so far: real data = 10,000+ ONCA-style cases (15 PDFs are samples); fine-tuning kept but deferred, runs on cloud GPU; LLM provider OpenAI by default but configurable; final names are AGENTS.md + INSTRUCTIONS.md + docs/ (all created by agent, structure not mandatory); graph/domain should be swappable (domain pack idea); code must be simple, readable, best-practice (user wants to learn); all prior recommendations accepted (staged delivery, fix compose/MLflow, Court+CITES edges, RRF, eval plan, disclaimer).
- Files affected: .agent/history.md.
- Decisions: propose Unsloth+TRL for fine-tune, domain-pack design, device-configurable embeddings, RAFT-style training examples with leakage guards. INSTRUCTIONS.md still unwritten.
- Next: get user's confirmation on proposed design + open questions, then show full INSTRUCTIONS.md text for approval before writing it.

## 2026-10-22 Drafted AGENTS.md and INSTRUCTIONS.md
- Done: user confirmed product understanding (lawyer-facing advisory copilot, any-stage case input, advice not just verdict, correctness via RAG + verification) and approved Unsloth+TRL and domain-pack design. Wrote both files to disk per user request; paused for review.
- Files affected: AGENTS.md (new), INSTRUCTIONS.md (new), .agent/history.md.
- Decisions: stage-cut training examples; leakage rules L1-L5; citation verifier; generic Postgres schema (JSONB metadata); domain pack folder; phases 0-6 with usable baseline at end of Phase 3 before GPU spend. docs/ not yet created (Phase 0 task).
- Next: wait for user review/approval. After approval, offer to start Phase 0.

## 2026-10-22 Added data versioning, observability, evaluation guide
- Done: user answered (local DVC now, evaluate DagsHub later; Phoenix acceptable; wants explanations; role = architect/platform engineer). Searched web for DagsHub and Phoenix vs Langfuse (secondhand, conflicting vendor claims, flagged for verification). Added sections 17-19, principles P7-P10, ADR practice, telemetry/DVC rows, tasks per phase, confidentiality rule (external generator only on public/synthetic data) to INSTRUCTIONS.md; updated AGENTS.md (ADRs, telemetry and confidentiality rules).
- Files affected: INSTRUCTIONS.md, AGENTS.md, .agent/history.md.
- Decisions: DVC for raw data, extraction export, datasets, adapters; stores rebuilt not versioned; build_manifest + request_audit tables; OTel-only instrumentation, Phoenix backend (replaceable); LLM-as-judge only as calibrated trend signal.
- Next: user reviews updated files; then approval and offer to start Phase 0.

## 2026-10-22 Jev added as optional judge backend
- Done: read TypeSafe Jev docs intro; added section 19.3a (judge backend interface, Jev optional, public/synthetic data only, verify licence/pricing/self-hosting, calibrate before trust).
- Files affected: INSTRUCTIONS.md, .agent/history.md.
- Next: user review and approval of INSTRUCTIONS.md/AGENTS.md; then offer Phase 0.

## 2026-10-22 Removed learning statements from instruction files
- Done: removed "user is learning from the code" wording from AGENTS.md (section 2) and INSTRUCTIONS.md (P4, section 12 title). Saved the hint in memory (.agent/memory/project-state.md and Claude memory file project-learning-purpose.md).
- Files affected: AGENTS.md, INSTRUCTIONS.md, .agent/memory/project-state.md, .agent/history.md.
- Next: user approval of INSTRUCTIONS.md/AGENTS.md; then offer Phase 0.

## 2026-10-22 Doc style and reference-tag convention
- Done: user clarified the convention: concise dev-to-dev docs and code comments, detailed reasoning in AI memory; does not apply to INSTRUCTIONS.md/AGENTS.md; ADRs keep detail. Created .agent/memory/refs/INDEX.md (tag scheme [area.n], area codes) and updated Claude memory feedback file.
- Files affected: .agent/memory/refs/INDEX.md, .agent/memory/project-state.md, .agent/history.md.
- Decisions: tag format [<area>.<n>] with area codes pr/ar/da/gr/rt/ml/ob/pl; INSTRUCTIONS.md and AGENTS.md untouched.
- Next: user approval of INSTRUCTIONS.md/AGENTS.md; then offer Phase 0.

## 2026-10-22 Flyway/orchestrator discussion
- Done: user agreed to: Flyway via Docker, no orchestrator now (thin runner), no Neo4j migration tool. Wants flowlit tried on a parallel path. Recorded facts in .agent/memory/flowlit-suite.md.
- Files affected: .agent/memory/flowlit-suite.md, .agent/history.md. INSTRUCTIONS.md NOT yet changed (waiting for final agreement on the flowlit parallel-path wording).
- Next: confirm edits list with user, then update INSTRUCTIONS.md.

## 2026-10-22 INSTRUCTIONS.md updated: Flyway, stage contract, orchestration
- Done: applied agreed edits: Flyway one-shot migrations (6.1), Neo4j reload-from-cache (6.2), stage contract + orchestration/flowlit parallel path (7.0, 7.0a, 7.1), build_manifest.schema_version, layout rows, Phase 0 tasks, risks, compose line.
- Files affected: INSTRUCTIONS.md, .agent/history.md.
- Next: offer Phase 0 start when user confirms.

## 2026-10-22 Phase 0 foundations built
- Done: pyproject/uv env, .gitignore, .env.example, Settings, JSON logging+redact, stage contract, `cles run`, domain pack loader + validate_pack stage + legal_ca_on v0 pack, Compose (postgres, flyway, neo4j, mlflow profile training), V1 baseline migration, docs 01-05, ADRs 0001-0010, refs notes, 11 tests (pass), ruff clean. Verified: compose up healthy, flyway applied V1 (7 tables incl. flyway history), mlflow DB created, missing-password fails fast.
- Files affected: pyproject.toml, .gitignore, .env.example, .env (local, ignored), README.md, src/cles/**, tests/**, domain_packs/legal_ca_on/**, infra/**, docs/**, .agent/memory/refs/**.
- Decisions: HNSW index kept in V1 (faithful to INSTRUCTIONS); neo4j healthcheck uses cypher-shell with password from env interpolation.
- Pending: DVC init (needs git init, ask user); MLflow health check result; Phase 0 sign-off.

## 2026-10-22 Phase 0 verification complete (except DVC)
- Done: MLflow crash-looped (SQLAlchemy tried psycopg v3); fixed by backend URI scheme postgresql+psycopg2:// in infra/docker-compose.yml. Verified MLflow /health 200. Stack torn down (down -v). Tests 11 pass, ruff clean.
- Files affected: infra/docker-compose.yml, .agent/history.md.
- Pending: DVC init needs git init (ask user); Phase 0 sign-off.

## 2026-11-10 git init and DVC
- Done: `git init -b main`; removed /data/ from .gitignore (DVC manages it); `dvc init`; local remote `~/dvc-store/cles` set as default; `dvc add data` (15 files) and `dvc push` (16 files pushed). Staged all files except ignored ones (.env excluded). No commit yet: waiting for user approval of the commit message.
- Files affected: .gitignore, .dvc/*, .dvcignore, data.dvc, docs/04-implementation-plan.md, .agent/history.md.
- Next: user approves/edit commit message; ask about tag; Phase 0 sign-off; offer Phase 1.

## 2026-11-10 Phase 1 ingestion built
- Done: user committed Phase 0 and approved Phase 1. Added pymupdf, psycopg, pgvector; optional extra `embed` (sentence-transformers). Built parser, chunker, store, ingest/embed/build_indexes stages, db.recorded_run, pack SectionConfig (sections.yaml now has noise_lines, heading patterns, section keywords, metadata patterns). Fixed commit bug in store (see refs da.1). 35 tests pass (incl. Postgres integration), ruff clean. Ingest of 15 PDFs: 15 docs, 45 parents, 227 children; second run unchanged=15.
- Files affected: src/cles/ingestion/*, src/cles/db.py, src/cles/domain/pack.py, src/cles/config.py, domain_packs/legal_ca_on/sections.yaml, tests/*, docs/03-05, .agent/memory/refs/*.
- Pending: embed + build_indexes result on the 15 docs (running); user commit approval.

## 2026-11-10 Phase 1 verification
- Done: embed of 227 child chunks OK (cpu; torch did not use the GTX 1050), HNSW index built. `cles run embed build_indexes` failed first because chained stages share run_id and ingestion_runs PK was run_id only -> added Flyway V2 (PK (run_id, stage)) and updated db.recorded_run. Re-run OK. Sanity similarity queries run. 35 tests pass, ruff clean.
- Files affected: infra/postgres/migrations/V2__ingestion_runs_key.sql, src/cles/db.py, src/cles/observability/logging.py (quiet http loggers), docs.
- Next: user review and commit; Phase 1 sign-off; offer Phase 2.
