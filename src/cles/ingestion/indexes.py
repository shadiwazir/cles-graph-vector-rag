"""Vector index management (operational, not a migration: see INSTRUCTIONS.md 6.1)."""

import psycopg

INDEX_NAME = "idx_chunks_vec"


def drop_vector_index(conn: psycopg.Connection) -> None:
    conn.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
    conn.commit()


def create_vector_index(conn: psycopg.Connection) -> None:
    conn.execute(
        f"""CREATE INDEX IF NOT EXISTS {INDEX_NAME} ON chunks
            USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"""
    )
    conn.commit()
