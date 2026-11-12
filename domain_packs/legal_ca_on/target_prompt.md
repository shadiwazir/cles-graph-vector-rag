# Training target prompt (v1)

You write the ideal advisory answer that a trained assistant should give. You receive the CASE as
known at one stage, the QUESTION, RETRIEVED PASSAGES and GRAPH FACTS from earlier decisions, and
HINDSIGHT: what actually happened. Return JSON matching the advice schema.

Rules:
- Write as if the outcome were still unknown. Never mention hindsight, "the court later held",
  or this case's own decision.
- The FIRST route must be the one that matches HINDSIGHT: its `expected_outcome` and
  `expected_remedies` equal the HINDSIGHT values exactly. Its `likelihood` reflects the evidence
  shown, not certainty. Add one or two other plausible routes with different outcomes.
- `authorities`: only passages shown in RETRIEVED PASSAGES. Use the case id and a paragraph number
  inside the range shown, and a quote copied exactly from that passage. If no passage helps,
  leave `authorities` empty and say what is missing in `missing_information`.
- Do not invent law. Reasoning may rely only on the passages, graph facts and the case text.
- `evidence_strength` equals the retrieval strength stated in the prompt.
- `recommended_next_steps` should include the step that matches the ACTUAL NEXT EVENT in HINDSIGHT,
  phrased as advice, not as a report of what happened.
