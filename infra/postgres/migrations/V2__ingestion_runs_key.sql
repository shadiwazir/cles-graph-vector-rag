-- One `cles run` chain shares a run_id across stages, so the key is (run_id, stage).
ALTER TABLE ingestion_runs DROP CONSTRAINT ingestion_runs_pkey;
ALTER TABLE ingestion_runs ADD PRIMARY KEY (run_id, stage);
