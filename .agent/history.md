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

## 2026-11-11 Phase 2 built (extraction cache + graph)
- Done: added openai, neo4j deps. llm/ (protocol, OpenAI-compatible client, cost), extraction/ (extractor, extract stage with cache/threads/dry-run), graph/ (client, generic mapping-driven writer, graph_load stage), pack: graph_mapping.yaml + GraphMapping validation, Case.in_corpus + decision_date index, tighter extraction_schema, settings for concurrency and prices. ADR 0011, docs 03-05 updated, refs gr.2. 48 tests pass (incl. Neo4j), ruff clean. Dry-run extract: 15 pending, ~87k input tokens. Verified graph_load end to end with a hand-written fixture (then cleaned DB).
- Files affected: src/cles/{llm,extraction,graph}/*, src/cles/domain/pack.py, config.py, cli.py, domain_packs/legal_ca_on/*, tests/*, docs/*, .env.example, pyproject.toml, uv.lock.
- Pending: user decisions - LLM model, API key, approval to run extraction on 15 samples (cost); then iterate prompt, load graph from real extractions.

## 2026-11-12 Local LLM trial (Ollama)
- Done: ran extraction on the 15 samples with qwen2.5:1.5b (5/15 valid) and gemma3:1b (3/15) via 16k-context derived models; analysed failures; added parser-known fields override, `tidy`, outcome enum in schema; removed junk local extractions from DB. See refs gr.3.
- Files affected: src/cles/extraction/extractor.py, extract.py, domain/pack.py, domain_packs/legal_ca_on/{pack.yaml,extraction_schema.json}, tests/test_extraction.py, .agent/memory/refs/*.
- Next: user decision on a stronger model (API or bigger local) for the real sample run.

## 2026-11-13 qwen2.5:7b run and sample graph
- Done: 7B local run on 15 samples (12 ok / 1 invalid / 2 failed, 2h49), scored, loaded 12 extractions into Neo4j; added error storage for failed rows and LLM_TIMEOUT_SECONDS. See refs gr.3.
- Files affected: src/cles/extraction/extract.py, llm/openai_client.py, config.py, .env.example, .agent/memory/refs/gr.3.md.
- Pending: user decision on next step (review outputs / run remaining 3 with larger context + timeout / try OpenAI model).

## 2026-11-14 Review of extraction outputs, prompt v1, leak check
- Done: reviewed all 12 7B outputs against the PDFs; found leaks and thin/filler stage cuts; added pack leak_check + find_leaks in extractor (retry with feedback), prompt v1, schema tweaks, tests, fixture update; trial of v1 on 4 short docs (all ok, no leaks). Notes in refs gr.3.
- Files affected: domain_packs/legal_ca_on/{pack.yaml,extraction_prompt.md,extraction_schema.json}, src/cles/domain/pack.py, src/cles/extraction/extractor.py, tests/test_extraction.py, tests/fixtures/*, docs/03-architecture.md, refs.
- Next: user decision - finish the other 11 docs with the 7B (long, ~2-3 h) or try an OpenAI model; then hand-review and Phase 2 sign-off.

## 2026-11-14 OpenAI extraction run on 15 samples
- Done: gpt-5.4-mini run (14 ok + 1 invalid, retry with MAX_ATTEMPTS=3 -> 15/15), cost about $0.22, 48 s. Spot-checked against PDFs, graph rebuilt from the 15 extractions. docs/04 and refs gr.4 updated.
- Files affected: src/cles/extraction/extractor.py (MAX_ATTEMPTS), docs/04-implementation-plan.md, .agent/memory/refs/*.
- Pending: user decision on outcome/remedy split; Phase 2 sign-off; commit.

## 2026-11-14 Disposition/remedy split
- Done: split outcome into disposition + remedies (pack 0.2.0: outcomes.yaml, graph schema/mapping/templates, extraction schema + prompt rules + if/then schema rule, advice schema), tests, ADR 0012, docs 03/04, refs gr.5. Re-extracted 15 samples twice with gpt-5.4-mini (15/15 ok both times; $0.163 then $0.209), reviewed remedies against PDFs, rebuilt the graph.
- Files affected: domain_packs/legal_ca_on/*, src/cles/domain/{pack,check}.py, tests/*, docs/*, .agent/memory/refs/*.
- Pending: user review; commit (message proposed in chat).

## 2026-11-15 Phase 3 built (retrieval, verifier, advisor, API, evaluation, observability)
- Done: user confirmed 727 and 717 labels (domain rule saved in memory/domain-rules.md) and committed Phase 2; started Phase 3. Built retrieval (search/fusion/graph/rerank/hybrid), citation verifier, advisor + prompt + guard + audit, FastAPI app, record_manifest stage, evaluation harness + dev set, OpenTelemetry (spans, metrics), observability Compose profile (collector, Phoenix, Prometheus, Grafana + provisioned dashboard), shared llm/structured helper. ADR 0013, docs 03-05, README, refs rt.3. 90 tests pass, ruff clean. Verified: traces in Phoenix (project cles, case text redacted), metrics in Prometheus, dashboard in Grafana, API starts and /health OK, guard refuses external generator by default.
- Files affected: src/cles/{retrieval,inference,evaluation,observability,llm}/*, src/cles/{manifest,stage,config,cli}.py, domain_packs/legal_ca_on/{pack.yaml,query_templates.yaml}, infra/docker-compose.yml, infra/observability/*, eval/retrieval_dev.yaml, tests/*, docs/*, README.md, .env.example.
- Pending: user approval for a real-model API run on a public question (cost small); commit; Phase 3 sign-off; offer Phase 4.

## 2026-11-15 First real-model API run
- Done: user approved one public sample question and committed Phase 3. Ran POST /advise on a synthetic scenario with gpt-5.4-mini: 14 s, 9 citations all verified, moderate evidence. Notes in refs rt.3. Services stopped.
- Files affected: docs/04-implementation-plan.md, .agent/memory/refs/rt.3.md, .agent/history.md.
- Pending: user sign-off on Phase 3; then offer Phase 4.

## 2026-11-15 Fixes + Phase 4 built (training data)
- Done: (1) likelihood cap by evidence + advice schema enums/dismissed rule + prompt v1 (user-requested fixes); (2) Phase 4: pack training.yaml and target_prompt.md, Flyway V3 training_targets, training/{dataset,target,leakage,build_dataset,check_dataset}, ADR 0014, docs 03-05, refs ml.3. Tests with fake LLM and fake retriever for split, targets, L1-L5. Dry run on 15 samples: 59 examples, est $0.89.
- Files affected: domain_packs/legal_ca_on/*, infra/postgres/migrations/V3__training_targets.sql, src/cles/training/*, src/cles/inference/{calibration,advisor}.py, src/cles/domain/pack.py, config.py, cli.py, tests/*, docs/*.
- Pending: user approval for the paid build on 15 samples; then check_dataset, review examples, commit, Phase 4 sign-off, offer Phase 5.

## 2026-11-16 First real training-data build
- Done: user committed Phase 4 code and approved the paid build. Built dataset on 15 samples (59 examples, 0 violations), reviewed quality, added hindsight-word check + cache re-validation (2 regenerated), tracked artifacts/datasets with DVC and pushed. Notes in refs ml.3.
- Files affected: src/cles/training/{target,build_dataset}.py, tests/test_training.py, .gitignore, artifacts/datasets.dvc, docs/03-04, refs.
- Pending: user decision on early-stage framing (options A/B/C in ml.3), commit, Phase 4 sign-off, offer Phase 5.

## 2026-11-16 Option B: stage-aware advice
- Done: user committed and chose option B. Added stage + next_event to the advice schema (conditional expected_outcome), prompts v2, stage likelihood caps, early-stage route-name check, rebuilt dataset (59 examples, 0 violations, about $0.63 total), re-tracked with DVC. ADR 0015, docs, refs ml.4. 129 tests expected.
- Files affected: domain_packs/legal_ca_on/{advice_schema.json,advice_prompt.md,target_prompt.md,pack.yaml,training.yaml}, src/cles/{domain/pack.py,inference/calibration.py,inference/advisor.py,training/*}, tests/*, docs/*, artifacts/datasets.dvc.
- Pending: user commit, decision on updating INSTRUCTIONS section 8, Phase 4 sign-off, offer Phase 5.

## 2026-11-16 INSTRUCTIONS section 8 synced
- Done: user asked to update INSTRUCTIONS.md section 8 to match the stage-aware advice schema (stage, next_event, optional expected_outcome early, expected_remedies, likelihood caps). Only section 8 changed.
- Files affected: INSTRUCTIONS.md, .agent/history.md.
- Pending: user commits; Phase 4 sign-off; offer Phase 5.

## 2026-11-16 Docling side question
- Done: answered the user's side question about Docling. Tested docling 2.150.0 in an isolated scratch venv on 3 sample PDFs; results in refs da.2. No project code or dependencies changed.
- Files affected: .agent/memory/refs/da.2.md, refs/INDEX.md, .agent/history.md.
- Pending: user commit of section 8 sync (staged), Phase 4 sign-off, then Phase 5.

## 2026-11-17 Phase 5 built (fine-tuning)
- Done: user approved Phase 5. Research (GPU prices, base models, Unsloth/vLLM versions), token statistics of the dataset (mean 5.1k, max 6.9k), train group (trl, peft, datasets, accelerate, mlflow), configs, sft_config/sft_data/train_sft, leakage re-check, MLflow lineage, dry-run template preview, trusted_generator_hosts and llm_extra_body settings, vLLM serve profile, runbook, ADR 0016, docs 03-05, refs ml.5. CPU smoke test passed (58 min). Tests added (tests/test_sft.py).
- Files affected: configs/sft/*, src/cles/training/{sft_config,sft_data,train_sft}.py, src/cles/{config,cli}.py, src/cles/inference/guard.py, src/cles/llm/openai_client.py, infra/docker-compose.yml, docs/*, tests/test_sft.py, pyproject.toml, uv.lock, .gitignore, .env.example.
- Pending: user commit; decisions on base model and provider for the real run (after the real corpus is processed); Phase 5 sign-off; Phase 6.

## 2026-11-12 PoC scope, playbook and pipeline script
- Done: user added 93 PDFs in data/criminal_and_civil (2020-2026, criminal and civil), declared goal 1 (PoC on about 100 files) the short-term scope and asked to keep my cost/scope answer in memory and docs. Wrote refs pr.1 (goals, cost, caveats) and pl.2 (playbook design); docs/06 PoC budget section, docs/04 goals table, new docs/07-run-playbook.md (Mermaid flow, steps, paid gate, exit codes, scheduler hooks); README rewritten with every step; scripts/pipeline.sh (preflight, infra, data, dataset, train, train-dry, all, status, reset; paid gate with MAX_COST_USD and CONFIRM_PAID; logs under artifacts/pipeline/). Preflight passed (135 tests). Ingest of the 93 PDFs: 92 inserted, 1 unchanged, 0 failed. The 15 old samples remain in the DB (107 documents).
- Files affected: scripts/pipeline.sh, README.md, docs/04, docs/06, docs/07, .agent/memory/refs/{pr.1,pl.2,INDEX}.md, .agent/history.md.
- Decisions: PIPELINE_DATA_DIR (default data/criminal_and_civil) overrides DATA_DIR because .env still says data; script supplies unverified default prices (0.75/4.50) because .env had none and the dry-run estimate was null.
- Next: embed, build_indexes, extract (paid, user-approved scope), graph_load, build_dataset, check_dataset, train-dry; user commit.

## 2026-11-12 PoC rerun on the 93 new PDFs
- Done: ran ingest, embed, build_indexes, extract (paid, $1.24, 92 ok), graph_load (107), record_manifest, build_dataset (paid, $7.50; 407 examples, 359 train, 48 eval, split 2026-10-07), check_dataset (0 violations), train-dry (48 of 359 over 8192 tokens). Dataset: artifacts/datasets/23afd5bb. Results noted in docs/06 and refs pr.1, durations in docs/07.
- Decisions: treated the user's rerun request as approval of the estimated spend; ceilings 10 and 8 USD. Kept the 15 old samples in the DB. No GPU training (needs rented machine).
- Next: user reviews; decide max_seq_length (raise vs fewer passages); DVC tracking of artifacts/datasets (and data/) not done; commit proposal; offer Phase 6 or GPU PoC.

## 2026-11-12 DVC tracking of the PoC data
- Done: added .dvcignore entry for *:Zone.Identifier, `dvc add data artifacts/datasets`, `dvc push` to the local remote (97 files). data.dvc and artifacts/datasets.dvc updated.
- Next: user commit; explain open items (script coverage, GPU) and discuss the GPU choice.

## 2026-11-13 RunPod pod, scripts and pilot
- Done: user created an L40S pod on RunPod (manual option). Wrote configs/sft/qwen3_8b_poc.yaml and scripts/gpu_setup.sh (push, setup, run, wait), pushed repo and dataset 23afd5bb, set up the venv, fixed the unsloth install, ran a 3-step pilot (ok, about 2.5k tokens/s). Fixed my wait bugs and the model cache location. Refs ml.6, docs/06.
- Files affected: scripts/gpu_setup.sh, configs/sft/qwen3_8b_poc.yaml, docs/06, .agent/memory/refs/{ml.6,INDEX}.md, .agent/history.md, (pod) /workspace/*.
- Decisions: 3-step pilot instead of 100; full run about 45 steps. Wait on marker files.
- Next: user go-ahead for the full run (about 35 min, about $0.65); then copy the adapter back, stop the pod, serve and evaluate.

## 2026-11-13 PoC fine-tune completed
- Done: full QLoRA run on the L40S pod (46 steps, 36 min, train loss 0.936 mean, eval loss 0.961), adapter copied to artifacts/runs/3a752888, MLflow db copied to artifacts/mlflow-gpu.db. Results in refs ml.6 and docs/06. Pod left running at the user's request.
- Next: user stops the pod (or keeps it for serving); serving and evaluation are Phase 6 and need user confirmation; commit.

## 2026-11-13 End of session
- Done: user will stop the pod today and continue tomorrow. Asked how long Phase 6 takes: answered about half a day for the evaluation-only scope (48 held-out examples; fine-tuned vs base+retrieval vs OpenAI baseline; about $2.5 extra), about a day with a vLLM serving test and a lawyer review sheet; dashboards, alerts, drift checks and judge calibration are goal 2.
- Next: user commit (staged); confirm Phase 6 scope; restart the pod or attach a new pod to the volume (venv, model cache and repo are on /workspace; the L40S may be unavailable on restart, any 24 GB or larger GPU in EU-NL-1 works).

## 2026-11-14 Tag and Phase 6 evaluation build
- Done: tag v0.5.0-poc-finetune (annotated) on a503d70, approved by the user. Built Phase 6 evaluation only (stages eval_generate, eval_score, systems.yaml, ADR 0017, docs 05/07, tests); OpenAI baseline generated ($0.46) and scored. 4 old integration tests fail because they assume the 15-sample corpus (107 documents loaded now). Pod migrating to another machine (same volume).
- Next: new SSH line from the user; push code; run base and finetuned generation on the pod; score all three; user stops the pod; fix the 4 tests; commit proposal.

## 2026-11-14 Conversation support and page (step 2 of the live-test plan)
- Done: user approved option A. Added conversation.py, history in POST /advise, static page at /, setting conversation_history_tokens, ADR 0018, refs rt.4, README section, 150 tests pass, ruff clean. Smoke test with OpenAI on a public sample scenario (about $0.1): works; second turn had all citations removed by the verifier (noted).
- Files affected: src/cles/inference/{conversation.py,app.py,static/index.html}, src/cles/config.py, tests/{test_conversation.py,test_api.py,test_retrieval_integration.py,test_advisor.py}, docs/adr/{0018,README}, README.md, refs.
- Next: pod (user migrating): push code, run base and finetuned evaluation, score; then vLLM serving and the live test; commit proposal covering evaluation plus conversation page.

## 2026-11-14 Evaluation run on the pod
- Done: pod restarted by the user (same host, new port); pushed code; generated base and fine-tuned answers on 48 held-out examples (batch 12), copied back, scored all three systems with OpenAI. Results in docs/05 and refs ml.7. Pod left running at the user's request to stop it.
- Findings: fine-tune wins on schema, stage and citation grounding; no gain on outcome prediction; overconfident (9 wrong "high" top routes).
- Next: user stops the pod; commit proposal (evaluation + conversation page + tests); decide next (second-round experiments, live serving test).

## 2026-11-14 Results explorer
- Done: user committed the evaluation commit and stopped the pod. Built the results explorer (explorer.py, explorer.html, tests, pipeline explore step, README, docs 05/07, refs ml.7). eval_score stores per-citation checks. Wrote the MLflow and observability standpoint summary for the user (in chat). Server stopped after testing.
- Files affected: src/cles/evaluation/{explorer.py,score.py,static/explorer.html}, tests/test_explorer.py, scripts/pipeline.sh, README.md, docs/05, docs/07, refs.
- Next: user explores the results; second round (retrieval diversity cap, calibration-aware targets, more data) tracked as separate MLflow experiments; observability stack later.

## 2026-11-14 Tools in every run (MLflow, DVC, observability) and Phoenix licence
- Done: user's Phoenix licence research (PDF) recorded (ADR 0007 update, INSTRUCTIONS risk and concern rows, compose hardening, ob.2). User's principle saved (auto-memory feedback-tools-in-every-change). Built ADR 0019 scope: per-stage and per-system MLflow runs, mlflow_import (3 training runs imported, adapter registered as cles-advisor v1), OTel gauges, Grafana dashboard cles-quality, Prometheus alerts with promtool tests, drift_check, Flyway V4 (audit environment), POST /feedback, export_extractions, DVC tracking of exports, eval outputs, adapters, dvc.yaml metrics, pipeline steps (infra full stack, snapshot, drift, judge, alerts-test, mlflow-import), judge + calibration + labels in the explorer (blind mode), without-retrieval baseline definition, docs 03/05/07, README, refs ob.2, ob.3, ml.7. 168 tests pass, ruff clean. Paid: judge about $1.8 including one wasted attempt.
- Files affected: many (see git status): src/cles/{tracking,lineage,mlflow_import}.py, src/cles/evaluation/*, src/cles/extraction/export.py, src/cles/stage.py, src/cles/inference/{app,advisor}.py, infra/*, scripts/pipeline.sh, eval/*, domain_packs/legal_ca_on/judge_*, dvc.yaml, metrics/eval.json, tests, docs, memory.
- Not done (needs the user or a GPU): lawyer labels and judge calibration, acceptance thresholds, fine-tuned-without-retrieval baseline (GPU), alert receiver, DagsHub/cloud DVC decision, retrieval benchmark for the 93 new decisions, GPU/DB exporters.
- Next: user commit; user explores results and labels answers (blind mode); decisions on second-round experiments.

## 2026-11-14 Web console
- Done: built the web console (ADR 0020, refs pr.2): one app and port with the product home page (ask), results explorer, platform tools with live health, about; compose changes to allow embedding; pipeline `console`; tests. User said they are not a lawyer (labels cannot be legal opinions), DagsHub not needed (local DVC), acceptance thresholds to be discussed later, next GPU run decided after the console.
- Files affected: src/cles/console/*, src/cles/inference/app.py, src/cles/evaluation/explorer.py, src/cles/config.py, infra/docker-compose.yml, scripts/pipeline.sh, tests/test_console.py, docs/adr/0020, README.md, docs/07, refs.
- Next: user commit (two staged batches), reviews the console, decides on the GPU run (serve the fine-tuned model with vLLM behind an SSH tunnel so the Ask page uses it), thresholds discussion.

## 2026-11-14 Commits and tags
- Done: user committed 022ee09 (tools in every run) and 9fd428c (web console) after the staging split; tags v0.6.0-poc-evaluation-tooling (022ee09) and v0.7.0-poc-console (9fd428c) applied with the user's approval. Nothing pushed.
- Next: user tries the console; decision on the next GPU run (serve the fine-tuned model for the Ask page); acceptance thresholds discussion; optional: show retrieved passages in the explorer.

## 2026-11-14 Acceptance criteria and serving preparation
- Done: acceptance thresholds discussed and agreed (ADR 0021, docs/05, refs ml.8); implemented accept_check, eval/acceptance.yaml, console and Grafana display, pipeline accept step, command-line env precedence in pipeline.sh, gpu_setup.sh serve and serve-wait (untested on a GPU). Verdict of the latest check: rejected (provisional), one blocking criterion (high_is_reliable).
- Files affected: eval/acceptance.yaml, src/cles/evaluation/{accept,scoring}.py, src/cles/console/*, src/cles/observability/metrics.py, src/cles/{config,cli}.py, infra/observability/grafana/dashboards/cles-quality.json, scripts/{pipeline,gpu_setup}.sh, tests/test_acceptance.py, docs/05, docs/06, docs/adr/0021, refs.
- Next: user starts the pod (same volume, same region); I check disk space, serve with vLLM, tunnel, run the console against it; compare a few answers with the evaluation outputs; stop the pod.

## 2026-11-15 Serving verified on a GPU
- Done: user started an L40S pod (EU-NL-1, same volume). First vLLM start failed with "Disk quota exceeded" (60 GB volume full; uv cache 25 GB); cleared the uv cache (14 GB, regenerable), user later grew the volume to 75 GB. vLLM 0.33.0 then served Qwen3-8B plus the adapter as `cles`; SSH tunnel on 8001; console answered a real /advise request (3 routes, 7 citations, 0 failed, 36 s). User tried the three examples in the browser; serving works. Console and tunnel closed; user stops the pod.
- Findings: verified citations were not always relevant to the question (verifier checks quotes, not fit). My serve monitor grepped for "cles" in truncated output and missed the ready state; match on the HTTP status or exit marker instead.
- Files affected: docs/06 (serving section), .agent/history.md, memory.
- Next: when the user starts a pod again, run the 48 evaluation examples against the served 16-bit model and score them (checks the 4-bit vs 16-bit gap); optionally the fine-tuned-without-retrieval baseline.

## 2026-11-15 Served backend for the evaluation
- Done: added the `served` backend to eval_generate (greedy, free text, same token limit as `hf`; runs on the laptop through the tunnel) and the system `finetuned_served` in eval/systems.yaml, so the 48 examples can be generated by the 16-bit vLLM server and scored next to the 4-bit systems. Reason: the shared OpenAI client forces JSON mode and default sampling, which would make the comparison unfair. Test added (183 pass); dry run resolves 48 examples. docs/06 step 5 added.
- Files affected: src/cles/evaluation/generate.py, eval/systems.yaml, tests/test_eval_models.py, docs/06, .agent/history.md.
- Next: user starts the pod; serve, tunnel, run the two commands in docs/06 step 5, compare with the `finetuned` row, stop the pod.

## 2026-11-16 16-bit serving check
- Done: user started an L40S pod (same volume, 75 GB); vLLM served the adapter again (first start took ~10 min: flashinfer JIT on a fresh pod; my monitor pattern missed the ready state, the server was up). Ran the 48 held-out examples through the served 16-bit model from the laptop (backend `served`, system `finetuned_served`, $0) and scored them with eval_score (MLflow runs logged). Result: structure identical to the 4-bit run (schema 100%, stage 100%); failed citations 5 of 229 (4-bit: 8 of 258); top route right 50% (46%); wrong "high" 7 (9); "high" right 50% (47%). Differences are within noise, so the 4-bit numbers carry over; the overconfidence problem is unchanged and acceptance stays rejected (provisional). Acceptance check not rerun for this system.
- Files affected: metrics/eval.json (new finetuned_served section), artifacts/eval/finetuned_served/ (local), docs/05 (new subsection), .agent/history.md.
- Next: user stops the pod; commit the metrics and docs. Second round (retrieval diversity cap, calibration-aware targets, more data) remains the way to address overconfidence.

## 2026-11-16 Improvement plan
- Done: documented the discussion on how to improve the results and overcome the overconfidence as docs/08-improvement-plan.md (four steps: serving-time calibration replay, rebuilt targets, larger evaluation set, retrieval; each a separate MLflow experiment) and refs ml.9 (reasoning, numbers, checked dataset facts: first-route likelihood high 143 / medium 204 / low 12 in the 359 training targets). Nothing started.
- Files affected: docs/08-improvement-plan.md, .agent/memory/refs/ml.9.md, refs/INDEX.md, README.md, .agent/history.md.
- Next: user decides when to come back; recommended first step is the free calibration replay on the stored outputs.

## 2026-11-16 Heterogeneous data: honest measurement (step 0 of docs/08)
- Done: after the user's question on splitting heterogeneous legal data, examined the dataset (107 decisions) and built the free parts: decision-level cluster-bootstrap intervals (evaluation/statistics.py), model-free baselines baseline_prior and baseline_precedent scored with the systems (evaluation/baselines.py; in report.md, metrics/eval.json, gauges, MLflow runs), tracked acceptance criterion outcome_vs_precedent, dataset diagnostics in check_dataset (outcome shift, cross-split case-family candidates; pack config family_ignore_*). ADR 0022, docs/05 and docs/08 updated, refs ml.9. Restarted the local docker stack (stale network; containers recreated, volumes kept) to rescore.
- Findings: the 48 examples are 12 decisions (real n = 12); outcome shift train 79% vs eval 42% dismissed; the precedent vote is right 58% (14/24), the fine-tune 46-50%, the base 62%, OpenAI 50%, all intervals overlap; when precedents agree the vote is right 5/8, better than the model's "high" (47-50%). No case family crosses the split. Acceptance still rejected (provisional); outcome_vs_precedent fails (tracked).
- Files affected: src/cles/evaluation/{statistics,baselines,scoring,score}.py, src/cles/training/{diagnostics,check_dataset}.py, src/cles/domain/pack.py, domain_packs/legal_ca_on/training.yaml, eval/acceptance.yaml, metrics/eval.json, tests/test_eval_statistics.py, tests/test_eval_models.py, docs/05, docs/08, docs/adr/0022 and README, refs ml.9/INDEX.
- Next: user decides; recommended next step is docs/08 step 1 (replay "high only if the precedents agree" on the stored outputs, no GPU); then step 2 (target rebuild) and step 3 (rolling folds, locked test set); more PDFs split by date raise the number of independent decisions.

## 2026-11-16 Step 1 (calibration replay) and new PDFs
- Done: implemented apply_precedent_rule (inference/calibration.py, setting precedent_rule_min_decisions=2) and replayed it on all stored answers inside eval_score (systems `<system>+rule`: report section, metrics, MLflow runs, gauges). Result: fine-tuned "high" 17 -> 7, wrong 9 -> 3, precision 47% -> 57% (4/7); other systems similar direction; all within noise at 12 decisions; gate still not reached. Exploratory sensitivity recorded, no variant selected. 195 tests pass. Citations unchanged after the new documents entered the database.
- New data: user added data/mix (328 PDFs; 93 duplicates by content of criminal_and_civil; 235 new). Ingested with DATA_DIR=data/mix (free): 235 inserted, 93 unchanged, 0 failed. Started embed + build_indexes in the background (local, free). Extraction dry run: 235 pending, 1.83M input and 0.59M output tokens (price variables unset, so no estimate; scaled about $3.1). Nothing paid has run.
- Files affected: src/cles/inference/calibration.py, src/cles/config.py, src/cles/evaluation/score.py, tests/test_eval_statistics.py, metrics/eval.json, docs/05, docs/08, refs ml.9; database (235 new documents and chunks).
- Next: user decides whether to run the paid steps (extract about $3, dataset about $19, then retrain and evaluate on the GPU), and whether to wire the rule into the advisor.

## 2026-11-16 Approved: extraction and advisor rule
- Done: user approved the paid extraction and the advisor wiring. Wired apply_precedent_rule into Advisor (setting precedent_rule_enabled, default on; outcomes of retrieved decisions from the extractions table; visible warning when a route is lowered); 3 tests; docs/05 and docs/08 updated. Started `scripts/pipeline.sh data` with DATA_DIR=data/mix, LLM prices 0.75/4.50, CONFIRM_PAID=1, MAX_COST_USD=6 (estimate 4.02 USD) in the background: extract, export, DVC snapshot, graph load, manifest.
- Next: when the data step ends, check the result and cost; user decides question 3 (plain split vs rolling folds with locked test) before the dataset is rebuilt.

## 2026-11-16 Extraction of the new PDFs done
- Done: `pipeline.sh data` with DATA_DIR=data/mix: extract 233 ok, 2 invalid, 0 failed, cost 3.03 USD (estimate 4.02, ceiling 6); export (386 ok rows), graph load (340 decisions), manifest. The 2 invalid (2025 ONCA 897, 2026 ONCA 528) were rejected by the hindsight guard (decision wording in a pre-decision stage) and stay excluded. DVC snapshot of data, exports, eval and runs pushed to the local remote; manifest re-recorded with the new raw hash (0af4ad73...). 196 tests pass.
- Corpus now: 340 decisions with extractions; outcomes 229 dismissed (67%), 56 allowed, 53 allowed in part, 2 other; criminal 185, civil 152 (it was 93 and 14 before: the corpus is now much more civil); by year 2026: 159, 2025: 67, 2024: 35, 2023: 41, earlier 38.
- Files affected: artifacts/exports.dvc, artifacts/eval.dvc, data.dvc (commit to pin), database and graph (new decisions), refs.
- Next: user decides question 3 (plain split vs rolling folds with a locked test set); the dataset step (about 19 USD, needs approval) comes after that decision.

## 2026-11-16 Rolling-origin folds built (ADR 0023)
- Done: user chose rolling folds with a locked test window (3 dev folds + newest 35 decisions as test) after asking about case type (recorded: case_type is extracted and stored in the graph only; dismissal rates are equal, 68% criminal vs 66% civil, remedies differ; experiments a-d in docs/08). Built: plan_folds/fold_split (training/dataset.py), build_folds stage (one dataset folder per fold under artifacts/folds/<run>/<fold>/, training examples shared through a cache, evaluation examples need no paid target, case_type written into every example, default FOLDS_TARGETS=cached = no paid call), shared collect_examples/write_dataset in build_dataset (evaluation targets are no longer paid for there either), folds_report stage (baselines per fold, pooled over dev folds with decision-level intervals, per case type, new baseline_precedent_same_type, locked test fold needing FOLDS_INCLUDE_TEST and FOLDS_TEST_REASON, every use logged in eval/test_log.jsonl), pipeline step `folds`, dvc metrics entry, ADR 0023, docs/07, docs/08, README. 206 tests pass.
- Decision on ordering: do not pay for training targets before the target design (docs/08 step 2) is settled, because new targets change the prompt hashes; folds are built and evaluated without paid targets first.
- Reproducibility note: only 1 of the 15 PDFs at the top of data/ is also in data/mix, so the full corpus (342 decisions) needs data/ (top level) plus data/mix; PIPELINE_DATA_DIR takes one folder.
- Files affected: src/cles/training/{dataset,build_dataset,build_folds}.py, src/cles/evaluation/{baselines,score,folds}.py, src/cles/{config,cli}.py, scripts/pipeline.sh, dvc.yaml, tests/{test_training,test_sft,test_folds_report}.py, docs/adr/0023, docs/07, docs/08, README, refs.
- Next: real-data dry run of build_folds (running; free, retrieval only) gives the plan and the exact number of targets still missing; then run `pipeline.sh folds` for the dev-fold baseline evaluation (no paid call); the test fold stays locked.

## 2026-11-16 First fold run on the real data
- Done: first real `build_folds` failed after ~23 min (KeyError: context dates came from extracted decisions only; 2025 ONCA 897 has a rejected extraction): context dates now come from the documents table (also in build_dataset), regression test. Second run: 4 fold datasets written (train examples only the 4 cached targets; evaluation examples 135/144/130/157), check_dataset per fold clean (0 violations, no family candidates, outcome shift 0.32/0.32/0.55/0.46), folds_report on the dev folds (test locked, no eval/test_log.jsonl entry), DVC snapshot pushed. Found that my same-type baseline edit had silently not landed (equal to the plain vote); fixed, tests added, audited all other scripted edits (all present); rerun of folds_report only.
- Results: pooled over about 101 dev decisions: majority predictor 61% [52-71], precedent vote 60% [51-68], same-type vote 55% [47-64]; the window's base rate drives the scores (45-69%). docs/05 updated.
- Files affected: src/cles/training/build_dataset.py, src/cles/evaluation/baselines.py, tests/test_training.py, tests/test_eval_statistics.py, metrics/folds.json, docs/05, refs ml.9, artifacts/folds.dvc.
- Next: step 2 (target redesign: computed likelihood, mixed route order, balanced outcomes), then generate targets (about 17.50 USD, needs approval) and train per fold on the GPU; meanwhile free work: per-type reporting already in; unused: calibration replay across folds once model outputs exist.

## 2026-11-17 Step 2 built: evidence sets the likelihood (ADR 0024)
- Incident: the Neo4j graph was empty (0 Case nodes) although graph_load reported 340. Cause: tests/test_graph.py's `driver` fixture ran `MATCH (n) DETACH DELETE n` against the project's own Neo4j, so every full test run wiped the graph. Consequences: the first fold datasets (and any prompt built after the first test run) had no graph facts (566 of 566 evaluation prompts "(none)"), and the console advisor had none on 2026-11-15. The old dataset 23afd5bb was built while the graph existed (graph facts in 403 of 407 prompts). Fixed: the fixture now skips when the graph is populated unless TEST_NEO4J_WIPE=1; graph reloaded from Postgres (2507 case nodes, 8471 nodes); the full suite leaves it untouched. Baseline and fold numbers do not depend on the graph (they use the extraction export), so they stand.
- Free finding first: on the dev folds, top route = plurality of the retrieved decisions' outcomes, rated high only for unanimous (>= 2) precedents, was right 86% when high (22 examples, 18 decisions, interval 68-100), 57% medium, 54% low (13), overall 60%.
- Built: inference/evidence.py (precedent_level, apply_evidence, render_precedents; hash tie-break so the order never carries hindsight), PRECEDENT OUTCOMES section in the prompt (build_messages, ablation blanks it), TargetSpec.precedent_outcomes, check_target (late stages: the real path is one of the routes), generate_target applies the evidence then the caps, target prompt v3 and advice prompt v3, prepare_examples/build_dataset/build_folds pass the outcomes, advisor option PRECEDENT_LEAD_ENABLED (default off), ADR 0024, docs/05, docs/08. The pack version was not bumped on purpose (the extraction schema version embeds it and would orphan the paid extractions). 213 tests pass, 4 graph tests skipped by design.
- Started the free folds rebuild with the new prompts and the restored graph (background); stale first fold dataset artifacts/folds/37c3409a is to be removed after.
- Next: read the new target estimate from the rebuild; user approves the paid target generation (the earlier estimate was about 17.50 USD for all folds; the cache is empty because the prompts changed); then train per fold on the GPU, evaluate on the dev folds, replay the evidence-led serving on model outputs, then decide PRECEDENT_LEAD_ENABLED. Optional before that: OpenAI baseline on the dev folds (about 4.5 USD) to test the evidence-led serving on a general model without a GPU.

## 2026-11-17 Targets generated, baseline running
- Done (approved by the user): `pipeline.sh folds-targets` generated 1174 training targets for the folds: estimate 20.09 USD, cost 20.75 USD, ceiling 25 (enforced in the stage: refuses above it for the estimate, stops starting calls past it; test added). The fold datasets are in artifacts/folds/ddc147d1 (train 753/885/1028/1157 examples, 12-17 per fold missing after failed checks, evaluation sets 135/144/130/157), check_dataset clean on all four folds (0 violations), graph facts and the PRECEDENT OUTCOMES line present in the prompts. build_folds now writes the fold datasets before generating targets (evaluation sets do not depend on them) and again after.
- Target check: late-stage target top route = real outcome 70%, precedent plurality = real outcome 69%, plurality among the routes 97%: no hindsight tilt from the route set.
- Family check refined: parties in more than 4 decisions are repeat players and ignored; candidates ranked by shared names; summary reports count and the strongest. Real companions found across splits (2026 ONCA 464/514 share 16 parties, 450/563 share 9); recorded in ADR 0023 as a warning.
- Started `pipeline.sh folds-eval` (user approved, about 4.45 USD): OpenAI baseline on the three dev folds, scored per fold with +rule and +lead variants, pooled by folds_report. Old stale fold dir artifacts/folds/37c3409a (built with an empty graph) is to be removed.

## 2026-11-17 OpenAI baseline on the dev folds (partial) and a cache flaw
- Done (approved, about 4.4 USD): OpenAI answers on dev1 (1.42 USD) and dev2 (1.53 USD); during dev3 the OpenAI account ran out of credits (HTTP 429, 127 of 130 requests failed). Found a flaw: failed requests were written to the cache as empty answers, so a rerun would have skipped them and scored them as wrong. Fixed: failed requests are reported, never cached, and the stage exits non-zero; the 127 poisoned rows were removed from dev3's cache; tests added. Also fixed my +lead replay crashing on malformed answers (calibrate_answer) and made folds_report leave out systems with a partial fold. 218 tests pass.
- Preliminary results (dev1 + dev2, 137 late-stage examples): raw OpenAI top route 58%, "high" on 72 routes, right 67%; +rule 14 high, 100%; +lead top route 64%, 15 high, 93% (14/15); precedent vote 66%, training majority 69%. Documented in docs/05 and ADR 0024.
- Blocked: dev3 needs OpenAI credits (about 1.4 USD). Then `pipeline.sh folds-eval` finishes it (cached answers are kept) and the pooled three-fold report is written.
- Next: user adds credits; decide PRECEDENT_LEAD_ENABLED after dev3 and a fine-tuned model replay; GPU: train adapters per fold on the new targets (about 1-2 USD GPU each) and evaluate; remove nothing else.

## 2026-11-17 OpenAI baseline complete on the three dev folds
- Done: user added credits; folds-eval retried the 127 failed dev3 requests (1.35 USD; total baseline 4.30 USD; 0 empty answers). Pooled dev (201 late-stage examples, about 101 decisions): openai raw top route 53% [44-62], high on 110 routes, right 58% [47-69]; +rule 22 high, 19 right (86% [68-100]), top route 53%; +lead 21 high, 19 right (90% [75-100]), top route 58% [50-66]; precedent vote 60%, training majority 61%. Per fold +lead 64/64/44%, majority 69/69/45%. Schema valid 77%, citations failing 7.5%. docs/05 and ADR 0024 updated with the final numbers.
- Reading: calibration is solved by evidence (high 90% right, gate 2/3 met for +rule and +lead, failed by the raw model at 58%); top-route accuracy stays at the base rate level; the evidence-led serving is the better product behaviour; PRECEDENT_LEAD_ENABLED still off until a fine-tuned model is replayed.
- Next: GPU: train an adapter per fold on the new targets (about 1-2 USD GPU each, folds dev1-dev3 then test only for a release candidate), generate and score on each dev fold, replay +rule/+lead, then decide PRECEDENT_LEAD_ENABLED; commit.

## 2026-11-17 Fold training on the GPU pod started
- Done: pod L40S (EU-NL-1, same 75 GB volume, 59 GB used). Added scripts/gpu_folds.sh (on the pod: per fold train_sft then eval_generate with the fold's adapter, stops at the first failure, resumable) and gpu_setup.sh modes push-folds (code + dev folds, never the locked test fold), folds, pull-folds; EVAL_ADAPTER override; fold adapters registered as cles-advisor-folds, MLflow tag dataset_fold. First launch failed after 3 minutes: train_sft computed a validation loss on the fold's evaluation set, whose examples no longer have a target (my earlier change); fixed with with_target (the fold trains without a validation loss), test added, relaunched. Dry runs: token lengths max 9116 (limit 12288, none dropped); estimates dev1 1.2 h / 1.35 USD, dev3 1.7 h / 1.84 USD; whole run about 5 h and 6 USD including answer generation.
- Training dev1 running (96 steps, GPU 91%). Monitor armed.
- Next: when folds.exit is 0: pull-folds, eval_score per dev fold with openai + finetuned, folds_report (raw / +rule / +lead pooled), decide PRECEDENT_LEAD_ENABLED, tell the user to stop the pod.

## 2026-11-17 Fold training finished (three dev folds)
- Done: dev1, dev2 trained (74 and 88 min) and answers generated (69 and 72 min). dev3 died at 14:46 while saving its step-100 checkpoint: the 75 GB volume was full (0-byte scheduler.pt), the pod restarted (user resized the storage), the driver died without an exit marker. Added resume (SFT_RESUME_FROM, driver reads /workspace/runs/resume-<fold>.txt), save_total_limit=2, empty-path settings mean unset; deleted the corrupt checkpoint and the finished folds' checkpoints (adapters checked intact first); dev3 resumed from step 80 (37 min), answers generated in 66 min; finished 17:31. My ssh wait falsely reported the pod unreachable (transient failures). Answers pulled (135/144/130, none empty), 11 MLflow runs imported without registering.
- Result (pooled dev, 201 late-stage examples, 104 decisions): fine-tuned top route 61% (= training majority 61%, precedent vote 60%, openai raw 53%); 20 top routes rated high, 19 right (95% [83-100]); schema 99%, stage 98.5%, citations failing 5.2% (gate 5%), 5 foreign citations (gate 0). +lead lowers the fine-tuned top route to 59% and changes nothing for high: PRECEDENT_LEAD_ENABLED stays off for it. Acceptance would still be rejected (provisional) on the two citation gates.
- Cost: about 9.4 h of pod time (about 10 USD) against an estimate of 6 USD (answer generation takes about 70 min per fold, I had estimated 15). Agent cannot stop the pod (key unauthorized, call blocked); user stops it.
- Files affected: src/cles/{config,training/sft_config,training/train_sft}.py, scripts/gpu_folds.sh, docs/05, docs/06, ADR 0024, refs, folds artifacts (answers per fold), metrics/folds.json.
- Next: facts-stage fix in the targets (reject weak-evidence facts targets with citations), then regenerate targets and retrain if wanted; the locked test fold only for a release candidate with a stated reason; decide whether to serve the fold adapter in the console.
