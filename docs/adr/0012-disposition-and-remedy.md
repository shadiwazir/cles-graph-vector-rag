# 0012. Disposition and remedy as separate outcome facets [gr.5]

**Status:** accepted

**Context.** The first extraction used one `outcome` label mixing what the court decided (allowed, dismissed) with what it ordered (sentence varied, new trial, remitted). The same appeal then got different labels depending on emphasis: three appeals that were allowed came back as `sentence_varied` or `remitted`. Outcome prediction and advice need both facets, and filtering by disposition needs one clean value.

**Options.**
1. Keep one label and widen the list (every combination becomes a label): list explodes, labels overlap.
2. One disposition plus a free-text remedy: not queryable.
3. A disposition (single value) plus remedies (a list of values from a fixed list).

**Decision.** Option 3. `outcomes.yaml` has two lists: `outcomes` (the disposition) and `remedies`. In the graph, `Case-[:RESULTED_IN]->Outcome` stays and `Case-[:ORDERED]->Remedy` is added. The extraction schema constrains both with enums, and a JSON Schema `if/then` rule rejects a dismissed appeal that lists remedies (the retry then tells the model why). The prompt gives direction rules: `sentence_increased` vs `sentence_reduced`, acquittals set aside plus new trial, no remedy for costs orders. Pack version moved to 0.2.0, so extractions are re-run (schema version is part of the cache key).

**Consequences.** Two more things to predict, and finer graph queries (`remedies_by_issue`). Remaining soft spots after review of the 15 samples: the model's choice between `appeal_allowed` and `appeal_allowed_in_part` when a court "allows the appeal" on one aspect (727, 717), and the sentence direction must be checked by prompt and review, since no deterministic check exists yet.
