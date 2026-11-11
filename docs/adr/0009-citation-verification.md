# 0009. Deterministic citation verification [rt.1]

**Status:** accepted

**Context.** Fluent output is not correct output, and a fine-tuned model can invent plausible citations.

**Decision.** After generation, plain code (no LLM) checks that each cited case and paragraph exist and that the quote appears in that paragraph (whitespace-normalised). Failures are removed or flagged and counted. The graph flags overruled authorities. Weak retrieval produces `evidence_strength = weak` and a visible warning.

**Consequences.** Citations are verifiable by construction; the model is used for reasoning and format, facts come from retrieval.
