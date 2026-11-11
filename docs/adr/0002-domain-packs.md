# 0002. Domain packs keep the domain swappable [gr.1]

**Status:** accepted

**Context.** The legal domain should be replaceable without touching pipeline code. Graph schema alone is not enough: prompts, output templates, outcomes and section hints also differ per domain.

**Options.** (1) Hard-code the legal schema. (2) Config-only graph schema. (3) A pack folder with schema, prompts, JSON schemas, outcomes, section hints and Cypher templates.

**Decision.** Option 3, `domain_packs/<name>/`, selected by `DOMAIN_PACK`. Postgres is generic (`documents.metadata` JSONB). Neo4j labels and relationship types cannot be Cypher parameters, so the graph writer builds Cypher only from the validated whitelist and passes all values as parameters. The loader rejects templates with undeclared labels or without `$as_of`.

**Consequences.** A new domain is a new folder. Cost: a slightly more abstract graph layer. Pack versions go into `build_manifest`.
