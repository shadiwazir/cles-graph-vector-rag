# 0008. Stage-cut training examples with leakage rules [ml.2]

**Status:** accepted

**Context.** Lawyers query at any stage of a case. A single "facts to outcome" example per judgment would not match that, and putting the outcome in the input would make evaluation meaningless.

**Decision.** Each judgment yields several examples, one per stage of the case it reveals. Input: what is known at that stage plus retrieved context (RAFT style). Target: structured advice built from the decision's reasoning and outcome, citing only authorities present in the example's context. Leakage rules L1 to L5 (see `INSTRUCTIONS.md` section 9) are enforced by `as_of` filters, self-exclusion, a time-based split and an evaluation index built before the split date.

**Consequences.** Extraction is heavier and costlier; retrieval must exist before training data can be built.
