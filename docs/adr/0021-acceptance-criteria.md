# 0021. Acceptance criteria as a versioned file and a stage [ml.8]

**Status:** accepted (user decisions, 2026-11-14)

**Context.** INSTRUCTIONS section 14 asks for acceptance thresholds set with the user and recorded in docs/05. Other thresholds exist (drift tolerances, alert rules, judge calibration) but none answers "is this model version good enough to adopt".

**Decision.**
1. Criteria live in `eval/acceptance.yaml` (git-tracked): system, metric, scope all, comparison, value or reference (a baseline or another system with a margin), tier, optional `min_n`, optional `mode: wilson_lower`, optional `blocking_from_n`.
2. Two tiers. Blocking criteria decide the verdict (accepted_provisional, rejected, incomplete when something is not measured). Tracked criteria are reported and trended.
3. Outcome accuracy is tracked, not blocking, in the PoC: at 24 late-stage examples the error is about 20 points. The real rule is the interval rule (lower bound of the 95% Wilson interval at least the majority class), which becomes blocking from 100 late-stage examples.
4. Overconfidence is gated as calibration, not as a count: when the top route is rated "high" it must be right at least 2 times in 3, with at least 5 such cases. The fine-tuned model fails it (8 of 17), and that is the result.
5. A model that fails a hard gate stays rejected; gates are not relaxed to get a pass. They are tightened on a schedule as data grows. Acceptance is provisional because lawyer review is not performed.
6. `accept_check` writes `artifacts/eval/acceptance.json`, emits `cles_acceptance` gauges, and sets the registry alias `accepted` or `candidate` on the latest `cles-advisor` version. `scripts/pipeline.sh accept` exits 6 when a blocking criterion fails; `eval-score` only prints the verdict.

**Consequences.** Thresholds are reasoned starting points, to be revisited with more data and a lawyer. The criteria judge one system (the fine-tuned one); another model version needs its entry in `eval/systems.yaml` and a change of `system`.
