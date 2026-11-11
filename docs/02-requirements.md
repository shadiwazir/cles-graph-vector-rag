# 02. Requirements

## Functional

| ID | Requirement |
|----|-------------|
| F1 | Ingest decision PDFs: parse, clean, split into parent/child chunks, embed, store. Re-runs are idempotent. |
| F2 | Extract structured metadata, entities, citations (with treatment) and stage cuts per decision with an LLM; cache every result. |
| F3 | Build the graph from extractions using the domain pack schema. |
| F4 | Retrieve by vector + full-text (RRF) and graph traversal, filtered by `as_of`. |
| F5 | Generate structured advice (see `advice_schema.json`) from the case text, question and retrieved context. |
| F6 | Verify every cited case, paragraph and quote; flag overruled authorities. |
| F7 | Build leakage-free training data with stage cuts, and fine-tune the SLM (QLoRA). |
| F8 | Switch domain by changing the domain pack only. |
| F9 | Evaluate retrieval, citations, faithfulness and outcome accuracy on later-dated cases. |

## Non-functional

| ID | Requirement |
|----|-------------|
| N1 | Reproducible: every store and model traces to a code commit, data version, pack version and config. |
| N2 | Resumable and cost-controlled: stage contract, cache, `--dry-run`, cost estimate. |
| N3 | Confidential: lawyer text stays on our infrastructure; telemetry redacts it by default. |
| N4 | Observable: logs, metrics, traces, audit table, answer-quality metrics. |
| N5 | Configurable: provider, models, devices, paths come from settings only. |
| N6 | Maintainable: small typed modules, tests, ruff. |
| N7 | Runs on a laptop for development; ingestion and training run on a GPU machine. |

## Constraints

- A case's own outcome must never reach its own training input, retrieval or evaluation (leakage rules L1 to L5 in `INSTRUCTIONS.md`).
- No legal claim is shown without a verified citation.
