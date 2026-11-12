# 0015. Stage-aware advice: procedural paths first, appeal result downstream [ml.4]

**Status:** accepted (supersedes the early-stage part of ADR 0014)

**Context.** The first dataset forced every target's first route to equal the appeal's real disposition, at every stage. For a lawyer at the start of a matter (facts only, or proceedings under way) that produced contrived routes such as "Appeal dismissed; order upheld" before any decision exists. The product must advise at any stage, but the corpus is appeals: it reveals trial and tribunal results only through what the appeal decisions report.

**Options.**
1. Keep one framing at every stage (eventual appellate disposition).
2. Reshape early-stage advice around the next procedural paths, with the appellate result as a downstream expectation.
3. Outcome-labelled targets only for late stages; outcome-free targets for early stages.

**Decision.** Option 2.
- The advice has a `stage` (facts, procedural_history, lower_court_decision, grounds_of_appeal; identified by the model at runtime, given at training time) and every route has a `next_event`.
- Early stages: `expected_outcome` is optional and means "the disposition expected if this path reaches the Court of Appeal"; later stages: it is required. Routes are named after procedural paths. The pack lists patterns (`training.yaml`) that mark a first-route name as an appeal result before a decision exists; such targets are rejected and regenerated with the reason.
- Training target: the first route is the path that actually happened (its `next_event` is the actual next event, phrased as advice) and ends in the real disposition and remedies; other routes are plausible alternatives.
- Likelihood caps: by evidence (weak: low, moderate: medium, strong: high) and by stage (`likelihood_caps_by_stage`: before a decision exists nothing is above medium), applied at runtime and when building targets.

**Consequences.** The advice schema now differs from the skeleton in `INSTRUCTIONS.md` section 8 (new `stage` and `next_event`; `expected_outcome` conditional). The dataset still carries the corpus base rate (about 60 percent dismissals) and only appeal-reported views of earlier stages; the name patterns are a heuristic and some result-like phrasing still gets through (for example "sentence is reduced on appeal" at an early stage). Evaluation should report accuracy per stage.
