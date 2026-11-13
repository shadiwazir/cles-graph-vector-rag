# 0017. Model evaluation design: same prompts, real outcomes, single attempt [ml.7]

**Status:** accepted (Phase 6, evaluation only)

**Context.** The fine-tune has to be judged against alternatives on the held-out decisions. Loss alone does not say whether the advice is right. The training targets were written by an LLM with hindsight, so they are not ground truth. The evaluation set is small (48 examples, 12 per stage, 12 decisions).

**Options considered.**
- Re-run retrieval and the advisor for every system (end to end) versus reuse the prompts stored in the dataset. Re-running mixes retrieval changes into the comparison and costs time; the stored prompts are already leakage-checked (older decisions only).
- Score against the hindsight target versus against the real outcome of the decision. The target is another model's opinion, shaped by the same prompt; the real disposition and remedies are facts.
- Let each model retry on invalid JSON (as the advisor does in production) versus one attempt. Retries hide format failures, which a fine-tune is expected to remove.
- Serve with vLLM versus generate with Unsloth on the pod. vLLM needs its own environment (torch pins conflict) and 16 GB more disk for a first look at 48 prompts.

**Decision.**
1. Every system gets the exact system and user messages stored in `eval.jsonl` (retrieval context included). Systems: the OpenAI model (paid, public decisions only), Qwen3-8B without the adapter, Qwen3-8B with the adapter. Differences then come from the model.
2. Ground truth is the real disposition and remedies of the decision. Routes at the early stages name procedural paths, not appeal results, so the top-route outcome is scored only for the late stages; "any route names the real outcome" is reported for all stages, and "always dismissed" (the majority class) is the reference to beat.
3. One attempt per example, greedy decoding, JSON checked against the pack's advice schema. Valid JSON and schema validity are metrics.
4. Citations go through the deterministic verifier (ADR 0009) and are also compared with the decisions supplied in the prompt: a citation outside the supplied context is reported separately.
5. Calibration: count likelihoods above the evidence and stage cap, and top routes rated "high" that were wrong.
6. Generation for the Qwen systems uses Unsloth on the pod (same 4-bit load as training); each stage writes `artifacts/eval/<system>/outputs.jsonl`, which doubles as the cache, so reruns are free. Scoring is a separate stage with no paid calls.

**Consequences.** With 12 examples per stage, differences under about 15 points are noise: the report shows counts next to rates and the result is a demonstration, not proof. The OpenAI baseline runs in JSON mode while the local models run raw, a small advantage for it on format metrics. The OpenAI model also wrote the training targets, so it is the teacher without hindsight, a fair upper-bound reference rather than an independent rival. Stronger conclusions need a larger evaluation set (the full corpus) and lawyer review (not in this scope).
