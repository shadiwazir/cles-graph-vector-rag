# 0022. Heterogeneous data: the decision is the unit, and model-free baselines [ml.9]

**Status:** accepted (user direction, 2026-11-16); first part implemented, rest planned in docs/08.

**Context.** Legal decisions are heterogeneous: no two cases share facts, so a held-out case is never "the same problem as a training case", as it can be for prices or physics. What repeats is the legal issue (ground of appeal, standard of review, type of error) and the stage. Three consequences showed up in the data (dataset 23afd5bb, 107 decisions):
- The 48 evaluation examples are 12 decisions with four stages each. Examples of one decision are not independent, so the real sample is 12 decisions (24 late-stage examples are still 12 decisions); the earlier "+-20 points" was too optimistic.
- Outcome prior shift: 79% of the 93 training decisions are dismissed, against 42% (5 of 12) of the evaluation decisions (distance 0.37). A model learns a base rate the evaluation does not have, and "better than the majority class" means something different on each side.
- Without a model-free reference we cannot tell whether a fine-tune learned anything about outcomes beyond what retrieval already shows. On the 12 evaluation decisions a plain vote among the retrieved decisions' outcomes is right for 58% of the late-stage examples (always-dismissed 42%), as good as or better than every fine-tuned or OpenAI result and within noise of the base model.

**Options considered.**
1. Keep an example-level random or time split and a larger count of examples. Rejected: more examples per decision do not add independent evidence.
2. A random split by decision. Rejected: in law the future cannot be used to predict the past (the law and the court change), and it leaks later decisions into earlier ones' context (rules L1 to L5).
3. Time-based split, but measure at the decision level, add model-free baselines, diagnose the split, then widen to rolling time folds with a locked test set. Chosen.

**Decision.**
1. The decision is the unit of evaluation. Rates carry a 95% cluster-bootstrap interval over decisions (`evaluation/statistics.py`), reported next to every system in `report.md`, `metrics/eval.json` and MLflow.
2. Two model-free baselines are scored exactly like a model's top route and sit in the same tables, MLflow experiment and acceptance check: `baseline_prior` (most common training outcome) and `baseline_precedent` (most common outcome of the context decisions; ties to the better-ranked one). A new tracked acceptance criterion `outcome_vs_precedent` asks the model to beat the second. When all context decisions agree, the precedent vote's accuracy is the reference for a model rating a route "high".
3. `check_dataset` reports, as warnings and not failures: the outcome shift between training and evaluation decisions, and candidate case families across the split (decisions that share a non-state party; the pack lists the parties to ignore). Panel and date proved useless as a family signal (a panel decides many unrelated appeals in a week); shared party names work but initials name different people, so a candidate needs a human look.
4. Planned (docs/08, not yet built): rolling time folds with a locked test set and a dev set for tuning; stratification and balance by issue type and outcome; calibration anchored to the precedent evidence.

**Consequences.**
- The honest reading today: no system is distinguishable from the precedent vote on outcomes at 12 decisions; the fine-tune's value is structure and grounded citations (acceptance blocking criteria), not outcome prediction.
- Calibration has a natural anchor: the precedent vote is right 5 of 8 times (62%) when the precedents agree, while the fine-tuned model's "high" is right 47 to 50%. A serving-time rule "high only if the precedents agree" is therefore worth replaying (docs/08, step 1).
- More decisions raise the number of independent units; adding PDFs helps measurement most. They must be split by date so the evaluation stays newer than training.
- The new baselines add two systems to the MLflow `cles-eval` runs and to the quality gauges; they cost nothing (no model, no paid call).
- Family detection will have false positives (shared initials) and false negatives (companions without a shared name). It is a guard that warns, not a proof of independence.
