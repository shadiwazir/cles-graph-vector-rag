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

## Leakage tests (Phase 4)

- no disposition text or outcome label in any example input (L1)
- retrieval for a case excludes itself and later cases (L2, L3)
- held-out cases are later than all training cases (L4) and absent from the evaluation index (L5)

Acceptance thresholds for evaluation are set after the first baseline run.
