# 0007. OpenTelemetry-only instrumentation; Phoenix as backend [ob.2]

**Status:** accepted

**Context.** MLflow covers training only. The running system needs logs, metrics, traces and answer-quality signals, and case text may be privileged.

**Options.** Phoenix (single container; licence and ownership claims conflicted in sources, verify); Langfuse (heavier: ClickHouse, Redis, object storage; feature gating claims conflicted); vendor SDKs.

**Decision.** Instrument with OpenTelemetry only; an OTel Collector routes to Phoenix (LLM traces), Prometheus/Grafana (metrics) and log files. Everything self-hosted in the `observability` Compose profile. `TELEMETRY_CAPTURE_CONTENT` defaults to `redacted`. A separate append-only `request_audit` table stores metadata, not case text.

**Consequences.** The backend is replaceable by changing Collector config. LLM-as-judge is a calibrated trend signal, never an acceptance gate.
