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
