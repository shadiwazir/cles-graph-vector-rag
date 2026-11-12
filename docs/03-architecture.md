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
| `llm/` | `LLMClient` protocol, OpenAI-compatible client, cost estimate | done |
| `extraction/extractor.py`, `extract.py` | Prompt, JSON validation, one retry; `extract` stage with cache, threads, dry-run estimate | done |
| `graph/client.py`, `writer.py`, `load.py` | Constraints from the pack; generic mapping-driven writer; `graph_load` stage | done |
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
- outcomes and remedies are unique
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

## Extraction and graph (Phase 2)

```mermaid
flowchart LR
    CH[(chunks: parents)] --> X[extract stage]
    X -->|JSON mode, validate, 1 retry| LLM[OpenAI-compatible API]
    X --> EX[(extractions cache)]
    EX --> L[graph_load stage] --> W[GraphWriter]
    M[graph_mapping.yaml] --> W
    W --> N[(Neo4j)]
```

Commands: `cles run extract graph_load` (`--dry-run` on `extract` prints token and cost estimates).

- Needs `LLM_MODEL` and `OPENAI_API_KEY` in `.env` for a real run; set `LLM_PRICE_*` to get cost figures.
- Cache key `(doc_id, schema_version, model)`; `schema_version` = pack version + hash of prompt and schema. `invalid` and `failed` rows are retried on the next run.
- `graph_load` takes the newest `ok` extraction per document for the current `schema_version`.
- `graph_mapping.yaml` (per pack) maps extraction fields to nodes and relationships; the loader validates it against `graph_schema.yaml`.
- Re-writing a document replaces its relationships. Cited cases outside the corpus are stubs (`in_corpus = false`).
- Known gaps: no entity resolution (name variants are separate nodes); no `Statute` nodes yet (`PART_OF` unmapped); no batch API.
- Identity fields come from the parser, not the model: `known_fields` in `pack.yaml` (case id, title, date) are passed to the model as known facts and override its output. `tidy` drops nulls and matches enum values case-insensitively before validation.
- Local models: any OpenAI-compatible endpoint works, for example Ollama (`LLM_BASE_URL=http://localhost:11434/v1`, `OPENAI_API_KEY=ollama`, `LLM_MODEL=<name>`). Ollama's default context is small; use a model variant with `num_ctx 16384` or more. 1B-class models (qwen2.5:1.5b, gemma3:1b) reached only 5 and 3 valid results out of 15 and were semantically weak, so they are only useful for testing the pipeline.
- Leakage guard in extraction: the pack's `leak_check` (regexes on each stage's `known_so_far`) rejects text that describes the Court of Appeal's own decision; the reason is sent back to the model in the retry, and a second failure stores the row as `invalid`. Prompt v1 defines the four stages as cumulative and forbids hindsight.
- Outcome facets: `outcome` is the disposition (one value); `remedies` is a list. A schema rule rejects remedies on a dismissed appeal. Graph: `Case-[:RESULTED_IN]->Outcome`, `Case-[:ORDERED]->Remedy`.
