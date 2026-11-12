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

## Leakage tests (Phase 4)

- no disposition text or outcome label in any example input (L1)
- retrieval for a case excludes itself and later cases (L2, L3)
- held-out cases are later than all training cases (L4) and absent from the evaluation index (L5)

Acceptance thresholds for evaluation are set after the first baseline run.
