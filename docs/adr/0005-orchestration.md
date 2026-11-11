# 0005. No orchestrator now; thin runner; flowlit on a parallel path [pl.1]

**Status:** accepted

**Context.** Stages are batch jobs, idempotent and resumable, with no schedule and one machine. A framework (Airflow, Prefect, Dagster) would add services and concepts that are not needed yet. flowlit (owned by the project author) is a YAML DAG engine: concurrent, in-memory only, tested in one real client.

**Options.** (1) Adopt a framework now. (2) Plain stage commands plus `cles run`. (3) (2) plus flowlit as a second runner on a parallel path.

**Decision.** Option 3. The stage contract (`python -m cles.<stage>`, flags, JSON summary, exit code) keeps stages independent of any runner. flowlit plans in `pipelines/flowlit/` call the same commands; flowlit is an optional pinned dependency and never gates a phase. Compare on same results, glue code, speed-up from concurrency, failure handling, telemetry.

**Consequences.** Switching runner costs nothing. Adopt a real orchestrator when ingestion becomes scheduled/incremental, runs span machines, or a shared UI and run history are needed. The later MLOps loop (retrain, compare with the registered champion, promote) fits a runner with branching.
