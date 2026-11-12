# gr.2 Extraction and graph mapping (ADR 0011)
- No OPENAI_API_KEY / LLM_MODEL in .env yet: extraction built and tested with a FakeClient; real run needs user's key, model and cost approval. Dry run on 15 samples: ~87k estimated input tokens, ~37k output estimate; no prices configured so cost null.
- Chose json_object mode (portable across OpenAI-compatible providers) over strict structured outputs (schema subset limits). Own jsonschema validation + 1 corrective retry.
- Generic writer needs a mapping because generic code cannot know that `judges` means Judge nodes: added graph_mapping.yaml to the pack and validated against graph_schema (labels, props, relationship direction). Pack loader now also requires graph_mapping.yaml; graph identifiers must be plain names (Cypher injection guard).
- Judge/lawyer/party keys are case-folded names; Court/Outcome/StatuteProvision/Case keys not normalised.
- Cited cases not in corpus become stub Case nodes (in_corpus=false via ON CREATE); decision_date null so as_of templates exclude them -> Phase 3 revisit (good_law template).
- Hand-written fixture tests/fixtures/extraction_2026_ONCA_724.json (from the real PDF text) is a fixture, not LLM output; used to verify graph_load end to end, then removed from DB.
- Statute nodes and PART_OF not mapped yet. REPRESENTED (lawyer->party) not mapped (needs pairing).
