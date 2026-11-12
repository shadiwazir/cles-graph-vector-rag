# 0011. JSON-mode extraction and a declarative graph mapping [gr.2]

**Status:** accepted

**Context.** Phase 2 turns each decision into a validated JSON object (paid LLM call) and then into graph nodes and relationships. The graph loader must stay domain-agnostic (ADR 0002), and 10k extractions must be affordable and resumable.

**Options.**
1. Provider "structured outputs" (strict JSON Schema): strongest guarantee, but only some providers support it and its schema subset forbids optional fields and some keywords our schema uses.
2. JSON mode plus our own validation and one corrective retry.
3. For the graph: hard-coded mapping per label (fast to write, legal-specific code), or a declarative mapping in the pack.

**Decision.** Option 2 for extraction: `response_format=json_object`, validate with `jsonschema`, retry once with the validation errors, then store the row as `invalid`. Results are cached by `(doc_id, schema_version, model)`; `schema_version` is the pack version plus a hash of the prompt and schema, so any prompt change re-extracts. Concurrency is a thread pool; DB writes stay on the main thread. Prices are settings (they change), so cost is only computed when configured; `--dry-run` estimates tokens and cost without a call.

Option 3 (declarative) for the graph: `graph_mapping.yaml` lists a root node and a set of links (field, label, key field, properties, relationship, direction). The pack loader checks every label, property and relationship against `graph_schema.yaml`, including relationship direction. The generic writer replaces a document's relationships on each write (no stale edges) and uses `ON CREATE` constants so a cited case outside the corpus is a stub (`in_corpus = false`) that is never downgraded.

**Consequences.** A new domain needs a mapping file, not code. Entity resolution is not done: keys are case-folded names (judges, lawyers, parties), so name variants create separate nodes until a later resolution step. Stub cases have no `decision_date`, so `as_of` templates exclude them; revisit in Phase 3. The provider batch API (about half price) is not used yet; the cache and resumability make adding it later straightforward.
