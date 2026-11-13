# pl.2 Run playbook and pipeline script (2026-11-12)

- User asked for a run playbook plus scripts to run everything as an automation pipeline they may hook to later, with every step in README.md.
- Design: one bash driver `scripts/pipeline.sh <step>` (preflight, infra, data, dataset, train, train-dry, all, status, reset). It only calls `uv run cles run <stage>`, so it stays orchestrator-agnostic (cron, CI, flowlit later; see pl.1). Exit codes are stable (0 ok, 1 stage failed, 2 bad usage, 3 paid step not confirmed, 4 estimate above ceiling). Each run writes `artifacts/pipeline/<timestamp>/` with per-stage logs and `summary.jsonl`.
- Paid gate: `extract` and `build_dataset` first run `--dry-run`, print the estimate, and continue only with `CONFIRM_PAID=1` and estimate <= `MAX_COST_USD` (default 10). Prices default to 0.75/4.50 USD per Mtok (unverified, third-party) when `.env` has none; `.env` had none, so the dry-run estimate was null until the script set them.
- Data folder: `PIPELINE_DATA_DIR` (default `data/criminal_and_civil`) overrides `DATA_DIR` from `.env`, which is `data` (the old 15 samples). Ingest globs `*.pdf` non-recursively.
- `reset` drops the Postgres and Neo4j volumes and needs `CONFIRM_RESET=1`; it also deletes the paid extraction and target caches.
- Training is not in `all` (needs a GPU); `all` ends with `train-dry`.
