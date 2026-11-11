# AGENT INSTRUCTIONS: Project CLES (Cognitive Legal Expert System)
## Approach 1: Dual-Database Architecture (GraphRAG + Vector DB)

### 1. System Vision & Objective
You are building **Project CLES**, a production-grade, domain-specific legal expert system designed to predict court case outcomes and generate strategic legal advice. 

This repository implements **Approach 1**: A hybrid dual-database retrieval architecture.
- **Parametric Layer:** A fine-tuned Small Language Model (SLM, e.g., Llama 3.1 8B Instruct) trained via QLoRA/SFT on synthetic Chain-of-Thought (CoT) legal reasoning pairs.
- **Non-Parametric Knowledge Layer:** 
  1. `pgvector` (PostgreSQL extension) for dense-lexical hybrid search (HNSW vector distance + BM25 full-text `tsvector`).
  2. `Neo4j` for macro-level structural GraphRAG (traversing relationships between Judges, Statutes, Legal Principles, and Case Outcomes).

---

### 2. Architecture & Technology Stack
- **Language:** Python 3.11+
- **Database Layer:**
  - `PostgreSQL 16` with `pgvector` extension
  - `Neo4j 5.x` (Cypher query language)
- **Orchestration & Containerization:** `docker-compose`, Docker containers
- **MLOps & Tracking:** `MLflow` (tracking runs, hyperparameters, LoRA adapters)
- **Fine-Tuning Stack:** `Axolotl` / `Unsloth` / `PyTorch FSDP` / `PEFT (QLoRA)`
- **Embedding Model:** `BAAI/bge-base-en-v1.5` (768 dimensions)

---

### 3. Required File & Directory Structure
When generating code, adhere strictly to this project layout:
```text
cles-graph-vector-rag/
├── docker-compose.yml
├── .env.example
├── scripts/
│   └── init_db.sql
├── src/
│   ├── ingestion/
│   │   ├── layout_parser.py        # PDF extraction (LlamaParse / Marker)
│   │   ├── cot_extractor.py        # Synthetic CoT generation script
│   │   └── postgres_ingestor.py    # Chunking & pgvector embedding pipeline
│   ├── graph/
│   │   ├── neo4j_client.py         # Driver & graph builder
│   │   └── cypher_queries.py       # Cypher sub-graph extraction templates
│   ├── training/
│   │   ├── axolotl_config.yaml     # QLoRA SFT training parameters
│   │   └── train_sft.py            # MLflow-integrated training script
│   └── inference/
│       ├── hybrid_retriever.py     # Dual-retrieval (pgvector + Neo4j)
│       └── app.py                  # Serving route / API endpoint
└── AGENTS.md
```


### 4. Baseline Code Templates & Configuration Specifications

#### A. Containerized Environment (`docker-compose.yml`)
Provision PostgreSQL (`pgvector`), Neo4j, and MLflow services:
```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: cles_postgres
    restart: always
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-cles_db}
      POSTGRES_USER: ${POSTGRES_USER:-cles_admin}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-cles_secret_pass}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./scripts/init_db.sql:/docker-entrypoint-initdb.d/init_db.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-cles_admin} -d ${POSTGRES_DB:-cles_db}"]
      interval: 5s
      timeout: 5s
      retries: 5

  neo4j:
    image: neo4j:5.18-community
    container_name: cles_neo4j
    restart: always
    ports:
      - "7474:7474" # HTTP
      - "7687:7687" # Bolt
    environment:
      NEO4J_AUTH: ${NEO4J_AUTH:-neo4j/cles_secret_pass}
    volumes:
      - neo4j_data:/data

  mlflow:
    image: ghcr.io/mlflow/mlflow:v2.11.3
    container_name: cles_mlflow
    restart: always
    ports:
      - "5000:5000"
    environment:
      - BACKEND_STORE_URI=postgresql://${POSTGRES_USER:-cles_admin}:${POSTGRES_PASSWORD:-cles_secret_pass}@postgres:5432/${POSTGRES_DB:-cles_db}
      - ARTIFACT_ROOT=/mlflow/artifacts
    volumes:
      - mlflow_artifacts:/mlflow/artifacts
    command: >
      mlflow server
      --host 0.0.0.0
      --port 5000
      --backend-store-uri postgresql://${POSTGRES_USER:-cles_admin}:${POSTGRES_PASSWORD:-cles_secret_pass}@postgres:5432/${POSTGRES_DB:-cles_db}
      --default-artifact-root /mlflow/artifacts
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  pgdata:
  neo4j_data:
  mlflow_artifacts:

```

#### B. Relational & Vector Schema (scripts/init_db.sql)
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS legal_cases (
    case_id VARCHAR(64) PRIMARY KEY,
    title TEXT NOT NULL,
    jurisdiction VARCHAR(100),
    judge VARCHAR(100),
    year INT,
    source_path TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS case_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id VARCHAR(64) REFERENCES legal_cases(case_id) ON DELETE CASCADE,
    parent_chunk_id UUID NULL,
    section_type VARCHAR(50),
    chunk_index INT NOT NULL,
    contextual_summary TEXT,
    raw_text TEXT NOT NULL,
    embedding vector(768),
    tsv_content tsvector GENERATED ALWAYS AS (to_tsvector('english', raw_text)) STORED
);

CREATE INDEX IF NOT EXISTS idx_cases_jurisdiction ON legal_cases(jurisdiction);
CREATE INDEX IF NOT EXISTS idx_cases_judge ON legal_cases(judge);
CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON case_chunks USING gin(tsv_content);
CREATE INDEX IF NOT EXISTS idx_chunks_vector_hnsw ON case_chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

```

#### C. Graph Cypher Schema Definition
The Neo4j module must build and query nodes using this exact schema:

- **Nodes**: `Case`, `Judge`, `Lawyer`, `Statute`, `LegalPrinciple`, `Outcome`

- **Edges**: `(:Case)-[:TRIED_BY]->(:Judge)`, `(:Case)-[:APPLIED_STATUTE]->(:Statute)`, `(:Case)-[:RELIED_ON_PRINCIPLE]->(:LegalPrinciple)`, `(:Case)-[:RESULTED_IN]->(:Outcome)`

### 5. Step-by-Step Implementation Task Checklist
When asked to implement this codebase, execute the following steps in order:

1. **Infrastructure Verification:** Generate `docker-compose.yml`, .`env.example`, and `init_db.sql`. Ensure database scripts run cleanly on startup.

2. **Ingestion & Processing Scripts:**

- Build `layout_parser.py` to extract raw text and sections from PDF documents.

- Build `cot_extractor.py` to format synthetic extraction outputs into the JSONL CoT structure (`Facts -> Judicial Thinking -> Turning Points -> Predicted Verdict -> Advice`).

- Implement `postgres_ingestor.py` to compute `BAAI/bge-base-en-v1.5` embeddings and populate `legal_cases` and `case_chunks`.

3. **Graph Ingestion Module:** Implement `neo4j_client.py` to construct graph nodes and edges from case metadata and extracted CoT JSONs.

4. **Fine-Tuning Module:** Generate `axolotl_config.yaml` configured for QLoRA (`r=64`, `alpha=128`, `bf16=true`, sequence length `16384`) targeting Llama 3.1 8B Instruct.

5. **Runtime Hybrid Retrieval Engine:** Build `hybrid_retriever.py` to execute parallel queries across `pgvector` and `Neo4j`, compiling the augmented context for the fine-tuned SLM.