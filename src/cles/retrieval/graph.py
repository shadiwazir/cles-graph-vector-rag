"""Run the pack's named Cypher templates against Neo4j.

Templates are validated at pack load (declared labels only, `$as_of` required), and every
value is passed as a parameter.
"""

from datetime import date

from neo4j import Driver

from cles.domain.pack import DomainPack

_NO_LIMIT_DATE = date.max  # as_of=None means "no date limit"


class GraphRetriever:
    def __init__(self, driver: Driver, pack: DomainPack):
        self._driver = driver
        self.templates = pack.query_templates

    def run(self, template: str, as_of: date | None, **params) -> list[dict]:
        cypher = self.templates[template]
        with self._driver.session() as session:
            return session.run(cypher, as_of=as_of or _NO_LIMIT_DATE, **params).data()

    def expand_from_cases(
        self, case_ids: list[str], as_of: date | None, limit: int = 5
    ) -> dict[str, list[dict]]:
        """Graph facts around the cases found by passage search (multi-hop context)."""
        if not case_ids:
            return {}
        out = {}
        for name in ("case_profile", "citation_treatment", "related_cases_by_provision"):
            if name in self.templates:
                out[name] = self.run(name, as_of, case_ids=case_ids, limit=limit)
        return out
