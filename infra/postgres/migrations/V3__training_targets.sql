-- Cache of paid training-target generations, keyed by the exact input so a re-run never pays twice.
CREATE TABLE training_targets (
    example_id TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    model      TEXT NOT NULL,
    result     JSONB NOT NULL,
    status     TEXT NOT NULL CHECK (status IN ('ok', 'invalid', 'failed')),
    cost_usd   NUMERIC(10, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (example_id, input_hash, model)
);
