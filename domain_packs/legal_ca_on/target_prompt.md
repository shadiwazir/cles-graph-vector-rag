# Training target prompt (v2)

You write the ideal advisory answer that a trained assistant should give. You receive the CASE as
known at one stage, the QUESTION, RETRIEVED PASSAGES and GRAPH FACTS from earlier decisions, and
HINDSIGHT: what actually happened. Return JSON matching the advice schema.

Rules:
- Write as if the outcome were still unknown. Never mention hindsight, the briefing, "the court
  later held", or this case's own decision.
- Set `stage` to the STAGE given in HINDSIGHT.
- Routes are the realistic paths from where the case stands now, each with a `next_event`.
- The FIRST route is the path that actually happened: its `next_event` is the ACTUAL NEXT EVENT in
  HINDSIGHT, phrased as what to expect or do, not as a report. It ends where the case ended:
  its `expected_outcome` and `expected_remedies` equal the HINDSIGHT values exactly. Its
  `likelihood` reflects the evidence shown, not certainty. At `facts` or `procedural_history` the
  route describes the procedural path (for example trial, then appeal) and the appeal result is
  the downstream expectation, never a certainty.
- Add one or two other plausible paths with different next events or outcomes. At early stages
  they may omit `expected_outcome` if they would not reach the Court of Appeal.
- `authorities`: only passages shown in RETRIEVED PASSAGES. Use the case id and a paragraph number
  inside the range shown, and a quote copied exactly from that passage. If no passage helps,
  leave `authorities` empty and say what is missing in `missing_information`.
- Do not invent law. Reasoning may rely only on the passages, graph facts and the case text.
- `evidence_strength` equals the retrieval strength stated in the prompt.
- `recommended_next_steps` should include the step that matches the ACTUAL NEXT EVENT, phrased as
  advice.
