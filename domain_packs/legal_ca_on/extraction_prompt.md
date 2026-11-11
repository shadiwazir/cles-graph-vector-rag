# Extraction prompt (draft v0)

You read one Ontario court decision and return JSON matching `extraction_schema.json`.

Rules:
- Use only the text provided. Do not add outside knowledge.
- `stages[].known_so_far` contains only what a lawyer would know at that stage. It must not
  contain the court's reasoning or disposition from later stages.
- `citations[].treatment` describes how this decision treats the cited case.
- Keep names exactly as written. If a publication ban or anonymisation applies, copy it into
  `restrictions`.
- If a field is unknown, omit it. Never guess.
