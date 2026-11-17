# 0024. The retrieved precedents set the likelihood and the order of the routes [ml.9]

**Status:** accepted (user direction, step 2 of docs/08, 2026-11-17); targets generated for the folds (20.75 USD); the advisor option is off by default; no model trained on them yet.

**Context.** The fine-tuned model rates its top route "high" about half the time it is right (47% to 50%, gate 67%). Two causes were found in the training data (ADR 0022): the first route of every target is the real outcome, and its likelihood is written by a model that knows the outcome, so the model learns to lead with a confident route it cannot know. The folds (ADR 0023) then showed that, for outcomes, retrieval adds nothing beyond the base rate (precedent vote 60%, training majority 61%). What the precedents do give is a calibration signal: on the dev folds, taking the plurality outcome of the retrieved decisions as the top route and rating it "high" only when at least two decisions have a known outcome and all agree, that route was right 86% of the time (22 examples, 18 decisions, 95% interval 68% to 100%), "medium" 57% and "low" 54% (13 examples, too few to say).

**Options considered.**
1. Keep the writer's likelihoods and only cap them (ADR for the cap-only rule, docs/05): it lowers wrong "high" routes but leaves the route choice to the model.
2. Shuffle the route order randomly in the targets. Removes the "real outcome first" habit but gives the model noise to imitate.
3. Let code compute both the likelihood and the order from the precedents; the model explains the routes. Chosen.

**Decision.**
1. `inference/evidence.py` is the single place for the principle (fixed in advance, not fitted): a route's outcome is "high" when at least `PRECEDENT_RULE_MIN_DECISIONS` (2) retrieved decisions have a known outcome and all equal it, "medium" when at least half do, "low" otherwise. Routes are ordered by the share of precedents behind their outcome; ties are broken by a hash of a seed and the outcome, never by the writer's order (which would carry hindsight).
2. The prompt states the outcomes of the retrieved decisions (a computed `PRECEDENT OUTCOMES` section, runtime and training alike), so the rating is a function the model can see. The advice prompt (v3) states the principle; the "fine-tuned without retrieval" ablation blanks the section.
3. Training targets (late stages): the writer includes the real path as one of the routes, anywhere, without ranking or rating (target prompt v3: write "medium"); `check_target` requires some route to match the real outcome and remedies; `generate_target` then sets likelihoods and order with `apply_evidence` and still applies the evidence and stage caps. Early stages keep their rule (the first route is the real procedural path).
4. The advisor can apply the same function at serving time (`PRECEDENT_LEAD_ENABLED`, default off), replacing the cap-only rule. It is switched on only after it is replayed on model outputs of the development folds.
5. Outcome class balancing is not part of this step: once the top route follows the evidence, the label is no longer the training signal for the choice of route.

**Consequences.**
- All training prompts change (the new section, and graph facts restored), so every cached target is replaced; this is the full target cost (about 17.50 USD by the earlier estimate) and is paid once, for the folds, after approval.
- The model no longer learns to predict outcomes; it learns to explain routes whose rating and order are given by the evidence. That is the honest division of labour found in ADR 0022: the base rate and the precedents carry the outcome, the model carries structure, citations and prose.
- Top-route accuracy of the evidence-led answer is the precedent vote (about 60% on the dev folds), a baseline to beat, not a ceiling set by the model.
- The 86% for "high" comes from 22 examples; the 2/3 gate is expected to hold but with a wide interval, and "high" is rare (11% of late-stage examples).
- Checked on the generated targets (late stages, dev3 training set, 507 examples): the target's top route is the real outcome 70% of the time, the precedent plurality equals the real outcome 69% of the time, and the plurality outcome is among the routes in 97% of the targets. So the route set is not tilted toward the truth (a writer that adds the real path to a set chosen with hindsight would make the evidence-ordered top route correct more often than the plurality is). In-sample the plurality is more often right (69%) than on held-out folds (60%) because a training example retrieves its own history.
- Replay on OpenAI answers (three dev folds, docs/05): the raw model rated 55% of its top routes high and was right 58% of the time (110 routes); with the evidence-led serving 21 top routes are rated high and 19 are right (90%, interval 75 to 100), and the top route is right 58% instead of 53%, within noise of the precedent vote (60%) and the training majority (61%).
- 1.4% of the targets (12 to 17 per fold) failed the checks after retries (for example the writer mentioned "hindsight") and are left out of the training sets.
- Retrieval quality now matters more: the outcomes line is only as good as the retrieved decisions.
- A route outcome that no retrieved decision supports is rated "low" however the model reasons; this is intended.
