# 05. Testing plan

## Strategy

| Level | Tooling | Scope |
|-------|---------|-------|
| Unit | pytest | parser, chunker, pack loader, RRF, Cypher builder (injection safety), citation verifier, leakage rules, redaction |
| Integration | pytest + Docker Compose | migrations apply, ingestion into Postgres, graph load, retrieval with `as_of` |
| Pipeline | `cles run` on the sample PDFs in `data/` | stages follow the contract; re-run is idempotent |
| Evaluation | `cles.evaluation` | retrieval recall/MRR, citation pass rate, faithfulness, outcome accuracy on later-dated cases |
| Human | Lawyer review of a fixed sample | final gate before real use |

Run: `uv run pytest`, `uv run ruff check .`.

## Phase 0 acceptance

- `uv run pytest` passes.
- `docker compose up -d` starts postgres and neo4j healthy; flyway exits 0 and creates the tables.
- Compose fails with a clear message if a password is unset.
- `uv run cles run validate_pack` prints a JSON summary with `status: ok`.

## Phase 1 acceptance

- All sample PDFs parse with a title and date; child chunks never exceed 400 estimated tokens.
- `cles run ingest` twice: the second run reports every file as `unchanged`.
- After `embed` and `build_indexes`, every child chunk has a 768-dimension embedding and the HNSW index exists.
- `tests/test_store_integration.py` needs the Compose Postgres and is skipped when it is unreachable.

## Phase 2 acceptance

- Extraction logic (valid, retry, invalid, provider error, cost, cache key) passes with a fake client.
- Graph writer on Neo4j: idempotent re-write, replaced relationships, cited stubs keep `in_corpus` correct (skipped when Neo4j is unreachable).
- With a real model: every sample document reaches `ok`; outputs are reviewed by hand against the PDFs (stage cuts must not contain reasoning or the disposition).

## Phase 3 acceptance

- Retrieval: relevant case ranked first for a targeted question; `as_of` removes the case itself and later cases; excluded ids never return; an unrelated question gives weak evidence.
- Verifier: unknown case, after-`as_of` case, missing paragraph and invented quote are each rejected and removed; real quotes pass; ellipsis quotes keep order.
- Advisor: failed citations are removed and counted; model confidence is capped by retrieval; generation failure is reported; an audit row is written without question text.
- Guard: the API refuses to start with an external generator unless explicitly allowed.
- Telemetry: spans and metrics reach Phoenix and Prometheus; the span carries no case text by default.
- Evaluation dev set: recall@1 and MRR reported (all 1.0 on the 15-decision sample, a plumbing check only).

## Phase 4 acceptance

- Split: training documents strictly older than evaluation documents; same-date documents stay together; a corpus with no training documents is rejected.
- Examples: input equals the runtime prompt and never contains the hindsight block; retrieval excludes the case and uses `as_of` correctly (training: own date; evaluation: split date).
- Targets: first route equals the real outcome and remedies; authorities and quotes come from the example's retrieved passages; no self-mention; likelihood capped by evidence; retries with feedback; failures are cached and reported.
- Leakage: each of L1 to L5 has a test that a violating example is caught; `check_dataset` passes on a built dataset.

- Stage-aware advice: early-stage routes may omit `expected_outcome`, later stages must have it; `stage` equals the example's stage; early first-route names that read as an appeal result are rejected; likelihood is capped by evidence and by stage.

## Phase 5 acceptance

- Config: shipped YAML files load; parameters flatten for tracking.
- Data: prompt-completion split; over-long examples are dropped and counted, not truncated; estimate needs a configured throughput.
- Safety: `train_sft` refuses a dataset that breaks a leakage rule; the guard allows case text only to localhost and to hosts listed in `TRUSTED_GENERATOR_HOSTS`.
- Dry run on the sample dataset prints token statistics and the chat-template rendering (prompt end and answer start).
- CPU smoke run: finishes, saves an adapter, logs params, lineage tags, loss metrics and artifacts to MLflow.
- On the GPU machine (not testable here): Unsloth run completes; a 100-step pilot gives tokens per second; vLLM serves the adapter as `cles`; the API answers through it.

## Model evaluation (Phase 6, evaluation only) [ml.7] (ADR 0017)

- Unit tests (`tests/test_eval_models.py`): answer parsing (think blocks, code fences, bad JSON, schema errors); outcome and remedy scoring; early-stage handling; citations outside the context; likelihood cap violations; aggregation per stage with the majority baseline.
- Run: `eval_generate` once per system (`EVAL_SYSTEM=openai|base|finetuned`), then `eval_score` writes `artifacts/eval/report.md` and `report.json`.
- Exploring the result: `scripts/pipeline.sh explore` (`cles.evaluation.explorer`, tests in `tests/test_explorer.py`) shows statistics and the answers of all systems side by side.
- Reading the result: 12 examples per stage; differences under about 15 points are noise. Compare with the majority-class reference, not with 100 percent.

### Result of the PoC evaluation (2026-11-14)

48 held-out examples (12 per stage, 12 decisions), adapter `3a752888`, same prompts for all systems. Full tables per stage: `artifacts/eval/report.md` (local, not versioned).

| Metric | base Qwen3-8B | fine-tuned | OpenAI gpt-5.4-mini |
|--------|---------------|------------|---------------------|
| matches the advice schema | 90% | **100%** | 90% |
| stage identified correctly | 75% | **100%** | 77% |
| top route = real outcome (24 late-stage examples) | **62%** | 46% | 50% |
| any route names the real outcome (48) | 56% | **58%** | 46% |
| citations failing verification | 79 | **8** | 19 |
| citations outside the supplied context | 7 | **0** | 0 |
| wrong top routes rated "high" | 0 | **9** | 1 |

Reference: always predicting "dismissed" is right for 42% (10 of 24).

- The fine-tune learned the behaviour it was trained for: schema, stage, and citing only verifiable passages from the context (8 failed citations against 79 for the base model).
- It did not learn to predict the outcome better. With 24 late-stage examples the error is about +-20 points, so the three systems are statistically indistinguishable on outcome; the fine-tune is not better than the base model plus retrieval.
- It is overconfident: 9 wrong top routes rated "high". Cause (likely): in the training targets the first route always equals the real outcome, so the model learns to lead with a confident route it cannot know. Production caps (`cap_likelihood`) clamp by evidence and stage, but not all of these.
- Not measured: whether the advice is useful to a lawyer (needs lawyer review), and any effect of the 12-decision evaluation set being from one narrow time window.

### 16-bit serving check (2026-11-16)

The adapter was trained and evaluated on the 4-bit base; vLLM serves the 16-bit base. The same 48 prompts went through the served model (`finetuned_served`, backend `served`: temperature 0, no JSON mode, same token limit as the 4-bit run) and were scored with the same code.

| Metric | fine-tuned, 4-bit | fine-tuned, 16-bit served |
|--------|-------------------|---------------------------|
| matches the advice schema / stage correct | 100% / 100% | 100% / 100% |
| citations failing verification | 8 of 258 | 5 of 229 |
| top route = real outcome (24) | 46% | 50% |
| any route names the real outcome (48) | 58% | 58% |
| wrong top routes rated "high" | 9 | 7 |
| top route rated "high" and right | 47% (8/17) | 50% |
| likelihood above the evidence cap | 6 | 2 |

- The 4-bit results carry over to the served model: structure is identical and the other differences are within noise for 48 examples (about +-15 points). The weak spot is unchanged: a "high" top route is right about half the time, below the 67% gate.
- The acceptance check was not rerun for this system (it is defined for `finetuned`); the verdict stays "rejected (provisional)".
- Run: tunnel open, `EVAL_SYSTEM=finetuned_served LLM_BASE_URL=http://localhost:8001/v1 LLM_MODEL=cles LLM_EXTRA_BODY='{"chat_template_kwargs":{"enable_thinking":false}}' uv run cles run eval_generate`, then `eval_score` (docs/06).

### Decision-level view and model-free baselines (2026-11-16) [ml.9] (ADR 0022)

The 48 examples are 12 decisions with four stages each; the independent unit is the decision, so rates carry a 95% cluster-bootstrap interval over decisions. Two predictors that need no model are scored the same way: `baseline_prior` (most common training outcome) and `baseline_precedent` (most common outcome among the retrieved context decisions).

| predictor | top route right (24 late-stage) | 95% interval over 12 decisions |
|-----------|----------------------------------|--------------------------------|
| base Qwen3-8B | 62% | 46% to 79% |
| fine-tuned 4-bit | 46% | 25% to 67% |
| fine-tuned 16-bit served | 50% | 25% to 75% |
| OpenAI gpt-5.4-mini | 50% | 21% to 75% |
| baseline_prior | 42% | 17% to 75% |
| baseline_precedent | 58% | 33% to 83% |

- No system is distinguishable from the precedent vote on outcomes: every interval overlaps. The fine-tune does not beat it (46 to 50% against 58%); the acceptance criterion `outcome_vs_precedent` (tracked) fails.
- When the retrieved precedents all agree (8 of the 24), the vote is right 5 of 8 (62%). The fine-tuned model's "high" is right 47 to 50% (8 of 17), so "high only if the precedents agree" is a better rule than the model's own rating (to replay, docs/08 step 1).
- Dataset diagnostics (`check_dataset`, warnings): outcome shift between training (79% dismissed, 93 decisions) and evaluation (42% dismissed, 12 decisions) is 0.37; no case family crosses the split.
- Tests: `tests/test_eval_statistics.py` (cluster rate and interval, baselines, outcome shift, family candidates).

## Acceptance criteria (agreed 2026-11-14) [ml.8] (ADR 0021)

Specified in `eval/acceptance.yaml`, checked by `scripts/pipeline.sh accept` (`accept_check`). Acceptance is **provisional**: no lawyer review is performed in this PoC, and 48 held-out examples are too few for outcome accuracy. Thresholds are set by reasoning, not tuned to a result, and tighten as data grows.

| Criterion | Tier | Rule | Latest (fine-tuned) |
|-----------|------|------|---------------------|
| Matches the advice schema | blocking | at least 98% | 100% pass |
| Stage identified | blocking | at least 90% | 100% pass |
| Citations outside the supplied context | blocking | 0 | 0 pass |
| Citations failing verification (before the verifier removes them) | blocking | at most 5% | 4.1% pass |
| A top route rated "high" is reliable | blocking | right at least 2 times in 3 (needs 5+ cases) | 8 of 17 = 47% **fail** |
| Outcome at least the majority class | tracked | point estimate | 46% vs 42% pass (noise) |
| Outcome, lower bound of the 95% interval, at least the majority class | tracked, blocking from 100 late-stage examples | interval rule | 30% fail |
| Outcome within 10 points of base plus retrieval | tracked | non-inferiority | 46% vs 62% fail |
| Likelihoods above the evidence cap | tracked | at most 3 | 6 fail |

Verdict of the latest check: **rejected (provisional)**, one blocking criterion failed (`high_is_reliable`). The adapter in the MLflow registry has the alias `candidate`; it gets `accepted` only when every blocking criterion passes. The console shows the verdict, `cles_acceptance` gauges feed Grafana, and `eval-score` prints it (the `accept` step exits 6 on failure).

Policy: a hard gate that the model fails is the honest result. Gates are not relaxed to make a model pass; they are tightened on a schedule as the evaluation set grows (the outcome rule becomes blocking at 100 late-stage examples).

## Leakage tests (Phase 4)

- no disposition text or outcome label in any example input (L1)
- retrieval for a case excludes itself and later cases (L2, L3)
- held-out cases are later than all training cases (L4) and absent from the evaluation index (L5)

Acceptance thresholds for evaluation are set after the first baseline run.
