# 0023. Rolling-origin folds with a locked test window [ml.9]

**Status:** accepted (user decision, 2026-11-16); folds, evaluation of the model-free predictors and the test lock are implemented; model training per fold is planned.

**Context.** ADR 0022 showed that one split gives 12 independent decisions, an outcome mix that differs from training (79% against 42% dismissed), and an evaluation set that every tuning decision (rule, thresholds, prompts) reuses. Legal decisions are heterogeneous (criminal and civil, different issues), so a single time window is one draw from a varying distribution. The corpus is now 340 decisions, 45% civil.

**Options considered.**
1. A plain split on the larger data: one date, the newest 10% (about 35 decisions) held out. Simple and cheap, but the interval is still about +-16 points, the window is one burst of weeks, and the same set is reused for every choice.
2. Random k-fold by decision. Rejected: it lets later decisions into earlier ones' context and ignores that law and the court change over time (rules L1 to L5).
3. Rolling-origin (expanding window) folds with a locked test window. Chosen.

**Decision.**
1. Decisions are sorted by date. The newest `FOLD_WINDOW` (35) form the `test` fold; before it come `FOLD_DEV_COUNT` (3) development folds of the same size. Fold k trains on every decision strictly older than its window and is evaluated on the window (same-date decisions stay together). With 340 decisions: training on 200, 235, 270 and 305 decisions; evaluation windows of about 35 (2026-06-24 to 2026-10-30).
2. Each fold is an ordinary dataset folder (`artifacts/folds/<run>/<fold>/` with train.jsonl, eval.jsonl, manifest.json), so `check_dataset`, `train_sft` and `eval_generate` work on it with `DATASET_DIR`. Leakage rules L1 to L5 hold per fold; the future of a fold does not exist in it.
3. Dev folds are for comparing and tuning (rules, targets, prompts, thresholds). The test fold is never used for a choice: `folds_report` evaluates it only with `FOLDS_INCLUDE_TEST=true` and a `FOLDS_TEST_REASON`, and each use is appended to `eval/test_log.jsonl` (git-tracked), so how often it was looked at is on record.
4. Results are reported per fold, pooled over the dev folds (disjoint windows: each decision counts once) with 95% cluster-bootstrap intervals over decisions, and split by case type. `baseline_precedent_same_type` (the precedent vote over same-type decisions) is a free test of whether the type matters.
5. Cost handling: training targets are cached by prompt hash and shared by all folds (a training example's context depends on its own date only), evaluation examples need no target and are never paid for. `FOLDS_TARGETS=cached` (default) makes no paid call; `generate` pays for the missing targets behind the paid gate. Targets are generated only after the target design (docs/08 step 2) is settled, because new targets change the prompt hashes and would replace old-style targets that were paid for.

**Consequences.**
- About 140 decisions are evaluated in total (105 dev, 35 test) instead of 12; the pooled dev interval is about +-9 to 10 points.
- Four adapters are needed (three dev folds, one for the test), about 1 to 2 USD of GPU each; targets are shared. Early folds train on fewer decisions, so compare systems within a fold, not across folds.
- The outcome mix differs between windows (49% to 69% dismissed); that spread is now visible instead of hidden.
- The 12 decisions of the old evaluation (October 2026) fall inside the test window and must no longer be used for tuning.
- The test fold is protected by process, not by access control: the log makes any use visible, it cannot prevent one.
