CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()

CREATE TABLE documents (
    doc_id        TEXT PRIMARY KEY,            -- stable id, e.g. citation '2026 ONCA 719'
    title         TEXT NOT NULL,
    doc_date      DATE,                        -- decision date, drives the as_of filter
    source_path   TEXT NOT NULL,
    content_hash  TEXT NOT NULL,               -- sha256 of the file, for idempotent ingestion
    domain_pack   TEXT NOT NULL,
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (content_hash)
);

CREATE TABLE chunks (
    chunk_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id          TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    parent_chunk_id UUID REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    level           TEXT NOT NULL CHECK (level IN ('parent', 'child')),
    section_type    TEXT,
    chunk_index     INT  NOT NULL,
    para_start      INT,
    para_end        INT,
    token_count     INT  NOT NULL,
    text            TEXT NOT NULL,
    embedding       vector(768),               -- only child chunks are embedded
    tsv             tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    UNIQUE (doc_id, level, chunk_index)
);

CREATE TABLE extractions (
    doc_id         TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    schema_version TEXT NOT NULL,              -- pack version + prompt hash
    model          TEXT NOT NULL,
    result         JSONB NOT NULL,             -- validated against extraction_schema.json
    status         TEXT NOT NULL CHECK (status IN ('ok', 'invalid', 'failed')),
    cost_usd       NUMERIC(10, 4),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (doc_id, schema_version, model)
);

CREATE TABLE ingestion_runs (
    run_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage       TEXT NOT NULL,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    stats       JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE build_manifest (
    manifest_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    git_commit       TEXT NOT NULL,
    raw_data_hash    TEXT,                     -- DVC hash of data/
    extraction_hash  TEXT,                     -- DVC hash of the extraction export
    pack_name        TEXT NOT NULL,
    pack_version     TEXT NOT NULL,
    embedding_model  TEXT NOT NULL,
    schema_version   TEXT NOT NULL,            -- latest applied Flyway version
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes            TEXT
);

CREATE TABLE request_audit (
    request_id        UUID PRIMARY KEY,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    manifest_id       UUID REFERENCES build_manifest(manifest_id),
    adapter_version   TEXT,
    prompt_version    TEXT NOT NULL,
    retrieved_ids     TEXT[] NOT NULL,
    evidence_strength TEXT NOT NULL,
    citations_total   INT NOT NULL,
    citations_failed  INT NOT NULL,
    latency_ms        INT NOT NULL,
    question_text     TEXT,                    -- NULL unless explicitly enabled
    feedback          TEXT
);

CREATE INDEX idx_docs_date   ON documents (doc_date);
CREATE INDEX idx_docs_meta   ON documents USING gin (metadata jsonb_path_ops);
CREATE INDEX idx_chunks_doc  ON chunks (doc_id);
CREATE INDEX idx_chunks_tsv  ON chunks USING gin (tsv);
CREATE INDEX idx_chunks_vec  ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
