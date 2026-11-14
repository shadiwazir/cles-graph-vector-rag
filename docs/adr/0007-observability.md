# 0007. OpenTelemetry-only instrumentation; Phoenix as backend [ob.2]

**Status:** accepted

**Context.** MLflow covers training only. The running system needs logs, metrics, traces and answer-quality signals, and case text may be privileged.

**Options.** Phoenix (single container; licence and ownership claims conflicted in sources, verify); Langfuse (heavier: ClickHouse, Redis, object storage; feature gating claims conflicted); vendor SDKs.

**Decision.** Instrument with OpenTelemetry only; an OTel Collector routes to Phoenix (LLM traces), Prometheus/Grafana (metrics) and log files. Everything self-hosted in the `observability` Compose profile. `TELEMETRY_CAPTURE_CONTENT` defaults to `redacted`. A separate append-only `request_audit` table stores metadata, not case text.

**Consequences.** The backend is replaceable by changing Collector config. LLM-as-judge is a calibrated trend signal, never an acceptance gate.

**Update 2026-11-14: licence resolved** (user research, third-party sources, see [ob.2]). The Phoenix server and evaluation library are Elastic License 2.0 (source-available, not OSI): free to self-host for internal use with no feature gates; the only restriction that matters is offering Phoenix to third parties as a hosted service. The project is a PoC used internally and never exposed, so this is accepted. Only the OTel and client packages are Apache 2.0; we use plain OpenTelemetry exporters, so the backend stays replaceable (MLflow Tracing or Opik are the fallbacks). Dynatrace closed the Arize acquisition on 1 October 2026: roadmap risk, no licence change. Phoenix 21 turns authentication on by default in Docker; the image stays pinned at `version-20.27.0` and an upgrade needs `PHOENIX_ENABLE_AUTH` set explicitly. Patent notices (IP_NOTICE) were not inspected.
