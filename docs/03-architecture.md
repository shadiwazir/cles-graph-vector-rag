# 03. Architecture

Authoritative detail is in `INSTRUCTIONS.md`; this page is the working overview and is updated with the code.

## Components

```mermaid
flowchart LR
    subgraph Offline
        PDF[PDFs] --> P[parser] --> C[chunker] --> E[embedder]
        P --> X[extraction<br/>LLM, cached]
        X --> G[graph loader]
        X --> T[training builder]
    end
    E --> PG[(Postgres + pgvector)]
    X --> PG
    G --> N[(Neo4j)]
    T --> J[/train.jsonl/] --> S[QLoRA SFT] --> M[(MLflow)]
    subgraph Runtime
        Q[FastAPI] --> R[hybrid retriever]
        R --> PG
        R --> N
        Q --> L[SLM via vLLM]
        L --> V[citation verifier]
    end
```

## Modules (`src/cles/`)

| Module | Role | Status |
|--------|------|--------|
| `config.py` | `Settings`, the only reader of the environment | done |
| `observability/logging.py` | JSON logs with `request_id`, `redact()` | done |
| `stage.py` | Stage contract: args, JSON summary, exit code | done |
| `cli.py` | `cles run <stage...>` thin runner | done |
| `domain/pack.py`, `domain/check.py` | Pack loader and validator; `validate_pack` stage | done |
| `ingestion/parser.py` | PDF text to `ParsedDocument` (paragraphs, sections, metadata) using the pack's `sections.yaml` | done |
| `ingestion/chunker.py` | Parent (section) and child (at most 400 tokens) chunks with deterministic ids | done |
| `ingestion/store.py`, `ingest.py` | Idempotent write of documents and chunks; `ingest` stage with quarantine | done |
| `ingestion/embedder.py`, `embed.py` | bge-base embeddings (`cpu`/`cuda`/`auto`); `embed` stage, resumable | done |
| `ingestion/indexes.py`, `build_indexes.py` | HNSW index create/drop; `build_indexes` stage | done |
| `db.py` | Connection and `recorded_run` (writes `ingestion_runs`) | done |
| `extraction/`, `graph/` | Phase 2 | planned |
| `retrieval/`, `inference/`, `evaluation/` | Phase 3 | planned |
| `training/` | Phases 4 and 5 | planned |

## Infrastructure (`infra/`)

- `docker-compose.yml`: `postgres` (pgvector pg16), `flyway` (one-shot migrations), `neo4j` 5.26, `mlflow` (profile `training`).
- Migrations: `infra/postgres/migrations/V<n>__*.sql`. `infra/postgres/init/` only creates the `mlflow` database (runs on first start of an empty volume).
- Compose reads secrets from `.env` and fails if a password is missing.

## Domain pack

`domain_packs/<name>/` holds the graph schema, prompts, JSON schemas, outcomes, section hints and Cypher templates. `load_pack()` validates:

- all required files exist
- relationship endpoints reference declared node labels
- both JSON schemas are valid
- outcomes are unique
- every Cypher template uses only declared labels and relationships and filters on `$as_of`

## Stage contract

Each stage is `python -m cles.<module>` with `--limit`, `--dry-run`, `--run-id`; it logs to stderr, prints one JSON summary line to stdout and exits non-zero on failure. Stages are registered in `cli.STAGES`.

## Ingestion (Phase 1)

```mermaid
flowchart LR
    PDF[data/*.pdf] --> P[parse_pdf] --> C[build_chunks] --> S[store_document]
    S --> D[(documents)]
    S --> CH[(chunks, no embedding)]
    CH --> E[embed stage] --> CH2[(chunks with vectors)]
    CH2 --> B[build_indexes] --> I[HNSW index]
```

Commands: `cles run ingest embed build_indexes` (all accept `--limit`, `--dry-run`).

- `doc_id` is the file name (`2026_ONCA_719.pdf` becomes `2026 ONCA 719`); the citation line inside the PDF is unreliable (footnote digits get glued on).
- Re-running `ingest` skips unchanged files (`content_hash`), replaces a changed file, and reports a file with identical content under another name as a duplicate.
- A PDF that fails to parse is quarantined: listed in the stage summary and `ingestion_runs.stats`, and the run continues.
- `embed` drops the HNSW index when more than 1000 chunks are pending; `build_indexes` recreates it.
- Chunk sizes use a cheap token estimate (about 1.3 per word); the embedder truncates at 512 tokens.
- Known gaps: footnotes stay inside paragraph text; only all-caps headings are detected; scanned PDFs are rejected (no OCR yet).
