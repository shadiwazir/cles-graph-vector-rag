"""Postgres access: connection and run recording."""

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from cles.config import Settings


def connect(settings: Settings) -> psycopg.Connection:
    return psycopg.connect(settings.postgres_dsn())


@contextmanager
def recorded_run(conn: psycopg.Connection, stage: str, run_id: str) -> Iterator[dict]:
    """Write an `ingestion_runs` row for a stage. The caller fills the yielded stats dict;
    it is saved when the block ends, also if the block raises."""
    rid = uuid.UUID(run_id)
    conn.execute("INSERT INTO ingestion_runs (run_id, stage) VALUES (%s, %s)", (rid, stage))
    conn.commit()
    stats: dict = {}
    try:
        yield stats
    finally:
        conn.rollback()  # drop any half-finished transaction before recording the result
        conn.execute(
            "UPDATE ingestion_runs SET finished_at = now(), stats = %s "
            "WHERE run_id = %s AND stage = %s",
            (json.dumps(stats, default=str), rid, stage),
        )
        conn.commit()
