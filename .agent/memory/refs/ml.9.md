# ml.9 Improvement plan: overconfidence and what could raise the results, 2026-11-16

- Trigger: after the 16-bit serving check (docs/05) the user asked what would improve the results and how to overcome the overconfidence. The answer was documented as docs/08; no step started.
- Measured basis: fine-tuned 4-bit "high" top routes 17, right 8 (47%); 16-bit 50%; wrong "high" 9 then 7; majority baseline 42%; top route 46% (4-bit), 50% (16-bit), base 62%, OpenAI 50%; 24 late-stage examples, error about +-20 points.
- Checked in the dataset (23afd5bb, train.jsonl, 359 examples): first-route likelihood is high 143, medium 204, low 12. The first route always equals the real outcome (by construction of the target), and the likelihood is written by the target LLM that knows the outcome, then capped by evidence (`cap_likelihood`, training/target.py). So the model is taught to lead with a confident route.
- Two separate problems: (a) overconfidence, a target-design problem that is fixable; (b) outcome accuracy, which probably stays near 50% with this data volume; the honest goal is calibration, not accuracy.
- Why serving-time calibration first: free, deterministic, no GPU, replayable on the stored outputs; it shows how far calibration alone gets. Caveat: a rule fitted to 48 answers overfits; derive it from a principle (precedents agree on the outcome) and validate on unseen examples.
- Why computed likelihood in targets: the number should come from code (outcomes of retrieved similar decisions), the model explains the route; this removes the leak "the target writer knew the answer".
- Why more evaluation data before trusting gates: a 2/3 gate on a handful of "high" answers cannot separate a gain from luck (Wilson interval is wide).
- Retrieval: citations were verified but not always relevant in the 2026-11-15 console test (a sexual-assault sentencing decision quoted for a statement-admissibility case); the verifier checks that a quote exists, not that it fits.
- Honest limit: no promise that any step reaches the 67% gate; if not, record that the serving-time calibration is required.
- Related: [ml.7] evaluation, [ml.8] acceptance, ADR 0017, ADR 0021.
