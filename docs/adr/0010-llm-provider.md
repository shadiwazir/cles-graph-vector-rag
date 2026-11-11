# 0010. Provider interface and external-generator guard [rt.2]

**Status:** accepted

**Context.** OpenAI is the initial provider but may change. The Phase 3 baseline uses a third-party generator, while lawyer case text may be privileged.

**Decision.** One small interface (`complete(messages, schema)`); provider, model and base URL are settings, so any OpenAI-compatible endpoint works. Extraction results are cached and every paid call supports `--dry-run` and a cost estimate. The API refuses an external generator unless `ALLOW_EXTERNAL_GENERATOR=true`, and baseline testing uses only public or synthetic cases. At deployment the local SLM keeps case text in-house.

**Consequences.** Provider switch is configuration. The guard is a deliberate friction point.
