# 0014. Training targets: hindsight-conditioned, evidence-capped, context-only citations [ml.3]

**Status:** accepted (extends ADR 0008)

**Context.** Each training example needs a target: the ideal advice for the case as known at one stage. The only ground truth we have is what actually happened (disposition, remedies, the decision's issues and later events). Two failure modes must be avoided: leaking the outcome into the input (ADR 0008, rules L1 to L5), and teaching the model to state outcomes with confidence that the input does not support, which would train hallucination.

**Options.**
1. Human-written targets: best quality, impossible at 40,000 examples.
2. Targets generated from the case and context only, without hindsight: honest, but the target then rarely matches reality, so the model learns plausible-sounding but unanchored advice.
3. Targets generated with hindsight shown to the writer only, then constrained so the answer stays honest about its evidence.

**Decision.** Option 3.
- The writer sees the runtime prompt (case at that stage, question, retrieved passages, graph facts) plus a HINDSIGHT block (outcome, remedies, issues, principles, provisions, the actual next event). The HINDSIGHT block never enters the training input; the input is built by the same function as at runtime.
- Constraints, enforced in code with retries that tell the model what was wrong: the first route's outcome and remedies equal the real ones; every authority is a case, paragraph and quote present in the example's own retrieved passages (not merely somewhere in the corpus); the answer never mentions the case itself.
- Likelihoods are capped by the retrieval evidence (weak, moderate, strong), the same rule the runtime applies, and `evidence_strength` equals the retrieval strength. With little context the target therefore says so and lists what is missing.
- Retrieval for an example uses `as_of` = the case's date (training) or the split date (evaluation) and excludes the case itself. The split is by time: the newest documents are evaluation, ties on the split date stay together.
- Paid generations are cached in `training_targets`, keyed by example, a hash of the exact writer input, and the model, so a re-run costs nothing. `--dry-run` estimates tokens and cost.
- `cles run check_dataset` re-checks L1 to L5 on the written files, independently of the builder.

**Consequences.** The model learns what typically happens (routes ranked by real outcomes) while its stated confidence follows its evidence. Cost is the main driver: roughly one long call per stage (about $0.015 per example at the sampled model and prices, to be re-measured; the provider batch API would halve it). Known limits: the writer sees only the extraction's summary of what happened, not the full reasoning; the first route always matches reality, so outcome frequencies in the data reflect the corpus, not a calibrated forecast; on a corpus where all cases fall in a short period most examples have little context (as in the 15-decision sample).
