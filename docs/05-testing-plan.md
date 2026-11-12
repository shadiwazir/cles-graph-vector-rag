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

## Leakage tests (Phase 4)

- no disposition text or outcome label in any example input (L1)
- retrieval for a case excludes itself and later cases (L2, L3)
- held-out cases are later than all training cases (L4) and absent from the evaluation index (L5)

Acceptance thresholds for evaluation are set after the first baseline run.
